# Setup: a status bot for your agents

Ten minutes, once per Slack workspace. A human can follow this directly; an agent running `/agent-work-card --setup` walks you through the same steps and runs the checks at the end.

## 1. Create the Slack app

1. Go to https://api.slack.com/apps and choose **Create New App** > **From scratch**. Name it something like `Coding Agents` and pick your workspace.
2. Under **OAuth & Permissions**, add these **Bot Token Scopes**:
   - `chat:write` to post and edit the card
   - `channels:history` and `groups:history` to read your replies in the card's thread
   - `channels:read` and `groups:read` to find the channel and confirm the bot is in it
   - `reactions:read` to notice a 👍 on a question
   - `users:read` to resolve who replied
3. Under **App Home**, give the bot a display name. That name is what you will `/invite`.
4. **Install to Workspace** and approve. Copy the **Bot User OAuth Token**; it starts with `xoxb-`.

## 2. Put the token somewhere the agent can read and nobody else can see

Either an environment variable in the shell your agent runs from:

```sh
export AGENT_WORK_CARD_BOT_TOKEN=xoxb-...
```

or a file, readable only by you:

```sh
mkdir -p ~/.agent-work-card
printf '%s' 'xoxb-...' > ~/.agent-work-card/bot-token
chmod 600 ~/.agent-work-card/bot-token
```

If you use a secrets manager, have it export the variable; the file is the fallback. Never paste the token into a chat with the agent and never commit it.

## 3. Create the channel and invite the bot

Create `#agent-work` (or any channel you prefer) and, in that channel, run `/invite @<your bot display name>`. Private channels work too.

## 4. Tell the bot who you are

Mentions only work with your Slack member id. In Slack: your profile > three dots > **Copy member ID**. Then:

```sh
cat > ~/.agent-work-card/config.json <<'JSON'
{ "human_user_id": "U0XXXXXXXXX" }
JSON
```

The channel id is filled in automatically by the first preflight or post.

## 5. Run the checks

From the skill folder:

```sh
python3 scripts/slack_card.py preflight --channel '#agent-work'
```

Every line of the JSON report must say `"ok": true`. The exit code is 0 only when all pass. If a check fails, the `detail` field says exactly what to do.

## 6. Post a test card

```sh
cat > /tmp/test-card.json <<'JSON'
[
  {"type": "section", "text": {"type": "mrkdwn", "text": "🟦 *Status card test*"}},
  {"type": "context", "elements": [{"type": "mrkdwn", "text": "Planning · setup check"}]}
]
JSON
python3 scripts/slack_card.py validate --blocks /tmp/test-card.json
python3 scripts/slack_card.py post --blocks /tmp/test-card.json --text "🟦 Status card test" --channel '#agent-work'
```

You should see the card in the channel. You are done. From now on, start any long piece of work with `/agent-work-card <what you are building>` and the agent keeps the card for you.
