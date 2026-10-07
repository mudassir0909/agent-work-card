# Start: `/agent-work-card <work title>`

Follow this when the skill is invoked with a title. The title becomes the card's name. Everything here is deterministic; do not improvise around a failed check.

## Prerequisite checks, in this order

Run:

```sh
python3 scripts/slack_card.py preflight
```

- Exit 0: continue.
- Exit 1: read the JSON report, tell the human which check failed and the `detail` for it, point them to `references/setup.md`, and **stop**. Do not post a card, do not start the work, do not try to work around a missing token or channel.

Then confirm the title is usable: one line, no secrets, no customer names you would not want in Slack. If the human gave no title, ask for one before anything else.

## Open the card

1. Create a state file for this stream at `~/.agent-work-card/runs/<yyyymmdd-hhmm>-<slug>.json` holding `{ "title", "card_ts", "channel_id", "state": "planning", "started": <ISO8601> }`. This is the source of truth if your context is reset mid-run.
2. Build the root card from the template in `SKILL.md` with state 🟦, the title, the status line `Planning · intake`, and the signature. `validate`, then `post`. Record `card_ts` in the state file.
3. Reply in the thread: `▶️ Started: <title>`.

Only now begin the actual work, and from here on follow the card contract in `SKILL.md`: update in place on every state change, every question to the human goes through 🔴 plus a thread mention first, every action item on the human is a row in the waiting-on table, and the run ends with ✅ or ⚫ and a final mention reply.

## If something is off mid-run

- Slack call fails with `not_in_channel`: the bot was removed. Tell the human in the terminal, point to setup step 3, pause the card updates, keep the state file current.
- Context reset: read the state file, `update` the card to reflect reality before doing anything else.
- The human asks you to stop: set ⚫ with the reason, final mention reply, stop.
