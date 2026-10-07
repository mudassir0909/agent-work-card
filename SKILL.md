---
name: agent-work-card
description: Post and maintain a living status card in the #agent-work Slack channel through your status bot for any long-running agent task, so the human can watch and unblock it from Slack. Provides a compact rich Block Kit card updated in place, an append-only thread timeline, a Blocked state that @mentions the human, a Waiting-on data table of every action item on them, two-way unblocking via thread replies or reactions, and a signature footer. Use when a task will run long enough that the human may walk away, when another skill (e.g. an orchestrator skill) says to load it, or when the user asks for Slack status cards or progress updates in #agent-work.
argument-hint: "--setup | <work title>"
---

# Agent Work Card

## Routing

- `/agent-work-card --setup`: read `references/setup.md` and walk the human through it step by step, running `scripts/slack_card.py preflight` at the end. The document is written for humans too; they may follow it without you.
- `/agent-work-card <work title>`: read `references/start.md`. It runs the deterministic prerequisite checks, opens the root card for that title, and hands over to the contract below.
- No argument: ask which of the two they want. Never guess, never post a card without a title.


One work stream = one root card message in `#agent-work`, posted by your status bot. The root card is a living dashboard, rewritten in place via `chat.update` on every state change. Its thread is an append-only timeline. Parallel streams each own their own card and thread, and polling is always scoped to the stream's own thread, so streams never collide even on one bot token.

All Slack calls go through `scripts/slack_card.py` (commands in its docstring: `post`, `update`, `reply`, `check-reply`, `poll-replies`, `check-reaction`, `validate`). Never hand-write curl calls. Write blocks JSON to a tmp file in the scratchpad, run `validate`, then `post` or `update`. Read [references/block-kit-notes.md](references/block-kit-notes.md) before composing anything beyond the templates below; it holds the block constraints that `blocks.validate` does not catch (one `plan` per message, `task_card` never with `plan`, no attachments, no buttons).

## Setup

- Token: `$AGENT_WORK_CARD_BOT_TOKEN`, else `~/.agent-work-card/bot-token`. If neither resolves, ask the human for it before anything else.
- Config `~/.agent-work-card/config.json`: `channel_id` (cached by the first `post`, which resolves `#agent-work` by name) and `human_user_id` (the human's Slack user id for mentions). If `human_user_id` is missing, take it from the `user` field of the human's first detected thread reply or reaction and save it.
- `not_in_channel` / `channel_not_found` means the bot needs `/invite @<your bot>` in `#agent-work`; the script prints this. Relay it and wait.

## The contract

1. **Post at the start**, before the first question to the human: state 🟦, title line, status line, signature. Record the returned `card_ts` in the caller's own state file, along with the current blocks JSON (`card.json`) so the card can be regenerated after context compaction.
2. **Update in place on every state change** and post a thread `reply` for every event worth an audit trail. Never let the card lie about what is running now.
3. **Never ask the human anything silently.** Before every question, in any phase, through any channel (AskUserQuestion included): card to 🔴 Blocked, question as a thread reply with the mention, then the terminal prompt. Flip back once answered.
4. **Every action item on the human is a row in the Waiting-on table** the moment it arises, removed the moment it is done. An item that exists only in a thread reply does not exist.
5. **Finish with the Done state** and a final mention reply. Never leave a card green after the work stopped; use ⚫ Aborted if it ended without finishing.

## Card template

Compact by design, so several cards fit on one screen. Every fact appears exactly once.

```json
[
  {"type": "section", "text": {"type": "mrkdwn", "text": "🟢 *<Work name>*"}},
  {"type": "context", "elements": [{"type": "mrkdwn",
    "text": "Running · <phase or stage> · <progress a/b>"}]},
  {"type": "section", "text": {"type": "mrkdwn",
    "text": "🔄 *<what is running now>* · <who or how> · <attempt or eta>\n⚠️ *<what is failing and retrying>* · <why> · attempt 2/3"}},
  {"type": "data_table", "caption": "Waiting on <Name>",
   "rows": [
    [{"type": "raw_text", "text": "Action"}, {"type": "raw_text", "text": "Type"}, {"type": "raw_text", "text": "Since"}],
    [{"type": "rich_text", "elements": [{"type": "rich_text_section", "elements": [
       {"type": "link", "url": "https://github.com/<org>/<repo>/pull/1292", "text": "Review PR #1292"}]}]},
     {"type": "raw_text", "text": "PR review"}, {"type": "raw_text", "text": "10:04Z"}]
   ]},
  {"type": "plan", "title": "<Checklist name> · 4 of 16", "tasks": [
    {"task_id": "c1", "title": "All existing tests pass (pnpm test)", "status": "complete"},
    {"task_id": "c2", "title": "Sessions persist across server restart", "status": "in_progress"},
    {"task_id": "c3", "title": "No changes outside src/auth/", "status": "pending"}
  ]},
  {"type": "context", "elements": [{"type": "mrkdwn",
    "text": "✍️ <model> · <chat title> · session <id8> · <owner>'s <machine> · <branch>"}]}
]
```

Element by element:

- **Title line**: state emoji first, always: 🟦 planning, 🟢 running, 🔍 verifying, 🔴 blocked, ✅ done, ⚫ aborted. It is the only state signal visible from the channel list.
- **Status line** (muted context): the state in words, the phase or stage, the progress count. Counts live here and nowhere else.
- **Active section**: only what is running or retrying, one line each, at most ~3; extras become a count. Finished work is never a line. This section IS the "now"; no other status prose anywhere.
- **Waiting-on table**: every open action item on the human, one row each (see below). Omit the block when the queue is empty; the table needs at least one body row.
- **Plan block**: the long checklist of outcomes (a definition of done, acceptance criteria, milestones), collapsed by Slack into a one-line bar with a chevron. It is the only collapsible block, so it gets the longest list. Row statuses: `pending` unmet, `in_progress` being checked, `complete` verified, `error` failed with the defect in `details`. Omit it if the work has no checklist.
- **Signature** (see below), always last.
- **Fallback `--text`**: reads well as a phone push notification, e.g. `"🔴 Auth refactor BLOCKED: need decision on session storage"`. Blocked and Done fallbacks carry the substance.

## Blocked variant

Insert a needs-you section after the active section, flip the title emoji to 🔴 and the status line to `Blocked on you · ...`, and make the fallback text carry the question:

```json
{"type": "section", "text": {"type": "mrkdwn",
  "text": "*🔴 <Agent> needs you, <@U0BCS78PW9X>:* Should sessions live in Redis or Postgres?\n*Options:* `redis` (faster, new dependency) / `postgres` (already wired, slower)\n_Reply in this thread, or react ✅ to take my recommendation: redis._"}}
```

Post the same question as a thread reply with the mention (that pushes a notification even if they are not subscribed to the thread), then follow the two-way protocol.

## Done variant

Title `✅ *<Work name>*`, status line `Done · <stats>`, no active section, plan fully `complete`, plus a wrap-up section with deliverables (branches, PRs, files, links). Final thread reply `✅ Done, <@{human_user_id}>` with the same summary.

## Waiting-on-human ledger

The `data_table` captioned `Waiting on <Name>` lists EVERY open action item on the human: PR reviews (they review only PRs listed and tagged here; a PR absent from this table will not get reviewed), deploys or scripts they must run, credentials, rulings, approvals. Columns: Action (rich_text with a `link` where one exists), Type, Since. Add the row the moment the item arises, alongside the mention ping in the thread; remove it the moment it is done; drop the block when empty. The ping notifies; the table remembers after the ping scrolls away.

## Mentioning the human

Mention as `<@{human_user_id}>` in mrkdwn sections and thread replies (it does not render in the `--text` fallback or in `markdown` blocks) whenever the work needs them: the Blocked needs-you section, every question reply, every timeline entry that says the work is waiting on them in any wording, and the final Done reply. Writing "needs <name>" without `<@...>` sends no notification and is a protocol violation. Phrase it so the sentence reads correctly once substituted: "<Agent> needs you, `<@...>`" or "`<@...>`, ruling needed on X", never "`<@...>` needs you". Do not mention on routine progress; a ping must mean "you are needed or it is over", or they will mute it.

## Thread timeline

One compact `reply` per event worth an audit trail:

- `▶️ <step> started: <what> (<who>)`
- `✔️ <step> done` / `🔍 <step> check: PASS (4/4)` / `↩️ <step> check: FAIL (<why>), retrying (attempt 2/3)`
- `🔴 BLOCKED: <question>` (with the mention)
- `🙋 Human replied: <gist>. Resuming.` (also when they answered in the terminal, so the thread stays complete)
- `🧭 <stage> → <stage>: <why>`
- `⚠️ <finding that changes the picture>` (with the mention if it needs them)

Timeline entries can carry a standalone `task_card` block to spotlight one item; never a `plan`.

## Two-way protocol (blocked on human)

1. Update the card to Blocked and post the question as a thread reply with the mention. Record that reply's ts as `QTS`.
2. Put the same question in the terminal and end the turn, unless other work can proceed, in which case keep working and poll in parallel. Mid-run, ask as plain text, NOT AskUserQuestion: it must not matter which channel answers first. During interactive phases AskUserQuestion is allowed, but only after step 1 has gone out.
3. Poll in the background: `Bash(run_in_background: true, timeout: 600000)` with `slack_card.py poll-replies --thread <card_ts> --after <QTS> --timeout 540`. Exit 0 means a reply arrived (JSON on stdout); exit 2 means timeout, so relaunch.
4. Reactions accumulate on the long-lived card, so a bare `check-reaction` on the card false-fires on old ones. Ask for reactions on the fresh `QTS` reply and watch that; if watching the card itself, snapshot a baseline first and fire only on change.
5. Whichever channel answers first wins; acknowledge in the other (thread reply `🙋 ...` if answered in terminal). Update the card back to Running.

## Signature

The last context block identifies who sent the card, always present, always one line:

`✍️ <model name> · <chat title> · session <first 8 chars of session id> · <owner>'s <machine> · <branch>`

Derivations: model name from the current model identity; chat title from the session name if the harness shows one, else the work name; session id from the harness session (visible in the scratchpad path); machine via `scutil --get ComputerName`, prefixed with the owner's first name possessive when the name does not already include it (e.g. "the human's MacBook Air"); branch from the working tree (or the project name when there is no branch).
