#!/usr/bin/env python3
"""Post and manage your status bot status cards in Slack.

Token: $AGENT_WORK_CARD_BOT_TOKEN, else ~/.agent-work-card/bot-token
Channel id cache: ~/.agent-work-card/config.json

Commands:
  post          --blocks FILE --text FALLBACK [--channel '#agent-work']
  update        --ts TS --blocks FILE --text FALLBACK
  reply         --thread TS --text TEXT [--blocks FILE]
  check-reply   --thread TS --after TS          exit 0 + JSON if a human replied after TS, else exit 1
  poll-replies  --thread TS --after TS [--timeout 540] [--interval 20]   exit 2 on timeout
  check-reaction --ts TS                        exit 0 + JSON if any human reaction on the message
  validate      --blocks FILE                   run blocks.validate (no auth needed)
  preflight     [--channel '#agent-work']       deterministic setup checks; JSON report; exit 0 only if all pass

Blocks go top-level on the message (never inside attachments). Blocks file may be '-' for stdin.
post prints 'TS CHANNEL_ID' on success; reply prints the reply TS.
Write methods use JSON bodies; read methods (conversations.replies, reactions.get) require
form-encoded params, which api() handles automatically.
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

API = "https://slack.com/api/"
TOKEN_FILE = os.path.expanduser("~/.agent-work-card/bot-token")
CONFIG_FILE = os.path.expanduser("~/.agent-work-card/config.json")
DEFAULT_CHANNEL = "#agent-work"
JSON_METHODS = {"chat.postMessage", "chat.update"}


def token_or_none():
    tok = os.environ.get("AGENT_WORK_CARD_BOT_TOKEN", "").strip()
    if not tok and os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            tok = f.read().strip()
    return tok or None


def token():
    tok = os.environ.get("AGENT_WORK_CARD_BOT_TOKEN", "").strip()
    if not tok and os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            tok = f.read().strip()
    if not tok:
        sys.exit(
            "No bot token. Set AGENT_WORK_CARD_BOT_TOKEN or write it to "
            + TOKEN_FILE
        )
    return tok


def config():
    for path in (CONFIG_FILE,):
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    return {}


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def api(method, payload, auth=True):
    headers = {}
    if auth:
        headers["Authorization"] = "Bearer " + token()
    if method in JSON_METHODS:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json; charset=utf-8"
    else:
        data = urllib.parse.urlencode(
            {k: v if isinstance(v, str) else json.dumps(v) for k, v in payload.items()}
        ).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(API + method, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.load(resp)
    if not body.get("ok"):
        err = body.get("error", "unknown_error")
        detail = json.dumps(body.get("errors", ""))[:500] if "errors" in body else ""
        if err in ("not_in_channel", "channel_not_found"):
            sys.exit(
                f"Slack error '{err}': invite the bot first. In Slack, open the "
                f"channel and run: /invite @<your bot>"
            )
        sys.exit(f"Slack error from {method}: {err} {detail}")
    return body


def read_blocks(path):
    raw = sys.stdin.read() if path == "-" else open(path).read()
    return json.loads(raw)


def channel_id():
    cid = config().get("channel_id")
    if not cid:
        sys.exit("No cached channel_id. Run 'post' once first; it caches the id.")
    return cid


def is_human(msg):
    return "bot_id" not in msg and msg.get("subtype") is None and msg.get("user")


def cmd_post(a):
    body = api(
        "chat.postMessage",
        {
            "channel": a.channel,
            "text": a.text,
            "blocks": read_blocks(a.blocks),
            "unfurl_links": False,
        },
    )
    cfg = config()
    cfg["channel_id"] = body["channel"]
    save_config(cfg)
    print(body["ts"], body["channel"])


def cmd_update(a):
    api(
        "chat.update",
        {
            "channel": channel_id(),
            "ts": a.ts,
            "text": a.text,
            "blocks": read_blocks(a.blocks),
            "attachments": [],
        },
    )
    print("updated", a.ts)


def cmd_reply(a):
    payload = {"channel": channel_id(), "thread_ts": a.thread, "text": a.text}
    if a.blocks:
        payload["blocks"] = read_blocks(a.blocks)
    body = api("chat.postMessage", payload)
    print(body["ts"])


def human_replies(thread, after):
    body = api(
        "conversations.replies",
        {"channel": channel_id(), "ts": thread, "oldest": after, "limit": "50"},
    )
    return [
        {"ts": m["ts"], "user": m.get("user"), "text": m.get("text", "")}
        for m in body.get("messages", [])
        if is_human(m) and float(m["ts"]) > float(after)
    ]


def cmd_check_reply(a):
    replies = human_replies(a.thread, a.after)
    if replies:
        print(json.dumps(replies, indent=2))
        sys.exit(0)
    sys.exit(1)


def cmd_poll_replies(a):
    deadline = time.time() + a.timeout
    while time.time() < deadline:
        replies = human_replies(a.thread, a.after)
        if replies:
            print(json.dumps(replies, indent=2))
            sys.exit(0)
        time.sleep(a.interval)
    print("timeout: no human reply", file=sys.stderr)
    sys.exit(2)


def cmd_check_reaction(a):
    body = api(
        "reactions.get",
        {"channel": channel_id(), "timestamp": a.ts, "full": "true"},
    )
    reactions = body.get("message", {}).get("reactions", [])
    if reactions:
        print(json.dumps(reactions, indent=2))
        sys.exit(0)
    sys.exit(1)


def cmd_validate(a):
    api("blocks.validate", {"blocks": read_blocks(a.blocks)}, auth=False)
    print("blocks valid")


def cmd_preflight(a):
    """Deterministic checks. Never prints the token. Exit 0 only if every check passes."""
    report = {"checks": [], "ok": True}

    def check(name, ok, detail):
        report["checks"].append({"check": name, "ok": bool(ok), "detail": detail})
        if not ok:
            report["ok"] = False

    tok = token_or_none()
    check("token", tok is not None,
          "found" if tok else f"set AGENT_WORK_CARD_BOT_TOKEN or write it to {TOKEN_FILE}")
    cfg = config()
    bot_user = None
    if tok:
        try:
            who = api("auth.test", {})
            bot_user = who.get("user_id")
            check("auth", True, f"bot '{who.get('user')}' in workspace '{who.get('team')}'")
        except SystemExit as e:
            check("auth", False, str(e))
    else:
        check("auth", False, "skipped, no token")

    name = (a.channel or cfg.get("channel_name") or DEFAULT_CHANNEL).lstrip("#")
    cid = cfg.get("channel_id")
    if tok and report["checks"][-1]["ok"]:
        try:
            if not cid:
                cursor = None
                while True:
                    payload = {"types": "public_channel,private_channel", "limit": "200",
                               "exclude_archived": "true"}
                    if cursor:
                        payload["cursor"] = cursor
                    body = api("conversations.list", payload)
                    for c in body.get("channels", []):
                        if c.get("name") == name:
                            cid = c["id"]
                    cursor = body.get("response_metadata", {}).get("next_cursor")
                    if cid or not cursor:
                        break
            check("channel", cid is not None,
                  f"#{name} -> {cid}" if cid else f"no channel named #{name} visible to the bot")
            if cid:
                info = api("conversations.info", {"channel": cid})
                member = info.get("channel", {}).get("is_member", False)
                check("bot_in_channel", member,
                      "bot is a member" if member else f"run /invite @<your bot> in #{name}")
                cfg["channel_id"] = cid
                cfg["channel_name"] = name
                save_config(cfg)
        except SystemExit as e:
            check("channel", False, str(e))
    else:
        check("channel", False, "skipped")

    hid = cfg.get("human_user_id")
    check("human_user_id", bool(hid),
          f"{hid}" if hid else f"add human_user_id to {CONFIG_FILE} (Slack profile > three dots > Copy member ID)")

    try:
        api("blocks.validate", {"blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "preflight"}}]}, auth=False)
        check("blocks_api", True, "reachable")
    except SystemExit as e:
        check("blocks_api", False, str(e))

    print(json.dumps(report, indent=2))
    sys.exit(0 if report["ok"] else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("post")
    sp.add_argument("--blocks", required=True)
    sp.add_argument("--text", required=True)
    sp.add_argument("--channel", default=DEFAULT_CHANNEL)
    sp.set_defaults(fn=cmd_post)

    sp = sub.add_parser("update")
    sp.add_argument("--ts", required=True)
    sp.add_argument("--blocks", required=True)
    sp.add_argument("--text", required=True)
    sp.set_defaults(fn=cmd_update)

    sp = sub.add_parser("reply")
    sp.add_argument("--thread", required=True)
    sp.add_argument("--text", required=True)
    sp.add_argument("--blocks")
    sp.set_defaults(fn=cmd_reply)

    sp = sub.add_parser("check-reply")
    sp.add_argument("--thread", required=True)
    sp.add_argument("--after", required=True)
    sp.set_defaults(fn=cmd_check_reply)

    sp = sub.add_parser("poll-replies")
    sp.add_argument("--thread", required=True)
    sp.add_argument("--after", required=True)
    sp.add_argument("--timeout", type=int, default=540)
    sp.add_argument("--interval", type=int, default=20)
    sp.set_defaults(fn=cmd_poll_replies)

    sp = sub.add_parser("check-reaction")
    sp.add_argument("--ts", required=True)
    sp.set_defaults(fn=cmd_check_reaction)

    sp = sub.add_parser("validate")
    sp.add_argument("--blocks", required=True)
    sp.set_defaults(fn=cmd_validate)

    sp = sub.add_parser("preflight")
    sp.add_argument("--channel", default=None)
    sp.set_defaults(fn=cmd_preflight)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
