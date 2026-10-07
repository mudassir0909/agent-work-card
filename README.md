# agent-work-card

A skill for coding agents: one live status card in Slack per stream of long-running work, edited in place, with the thread as the timeline and an @mention only when the human is needed. The human reads; the agent writes.

Shared after the Cursor Sydney meetup, 7 October 2026. The scenario shown in the talk was made up; this skill is the real one, with the company-specific names removed.

## Two commands

```
/agent-work-card --setup          walk through references/setup.md, then run the checks
/agent-work-card <work title>     run the checks, open the card, start the work
```

`references/setup.md` is written for humans as well; you can follow it yourself in ten minutes.

## Install

1. Copy this folder to `~/.claude/skills/agent-work-card/` (or your agent's skills directory).
2. Run `/agent-work-card --setup` once per Slack workspace. It needs a Slack app with a bot user; the scopes and the token placement are in the setup doc.
3. Start any long piece of work with `/agent-work-card <what you are building>`.

## What's in here

- `SKILL.md`: the routing and the card contract the agent follows.
- `references/setup.md`: human-readable setup, ends with a deterministic preflight.
- `references/start.md`: the start route, prerequisite checks first, then the card.
- `references/block-kit-notes.md`: the Slack Block Kit constraints the validator does not catch.
- `scripts/slack_card.py`: post, update, reply, poll replies, check reactions, validate, preflight. Standard library only.
