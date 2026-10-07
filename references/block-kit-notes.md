# Block Kit notes for agent cards

Hard-won facts about the agent-native blocks, every one of them verified live against `chat.postMessage` / `chat.update`. Read before composing anything beyond the SKILL.md templates. Full schemas live at `https://docs.slack.dev/reference/block-kit/blocks/<slug>-block.md` (append `.md` to any docs.slack.dev page to fetch markdown).

## Vocabulary

- `plan` block: `title` (plain text) plus up to 50 task rows, each `{task_id, title, status}` with optional `details` and `output` as single `rich_text` objects. Statuses: `pending` (empty circle), `in_progress` (spinner), `complete` (check), `error`. Renders COLLAPSED by default (a one-line title bar with a chevron) and is the ONLY collapsible block in Block Kit, so it holds the card's longest list.
- `task_card` block: a standalone task row, same shape as a plan task. Stricter status enum: only `in_progress`, `complete`, `error` (`pending` is rejected).
- `markdown` block: standard markdown (not mrkdwn), renders GFM task lists as real checkboxes, BUT checked items get strikethrough, which reads as deleted. Never use it for checklists.
- `section` + `context`: title line and muted metadata lines, mrkdwn (`*bold*`, `_italic_`, `` `code` ``). Inline code renders as loud orange pills; use it sparingly, never for decoration. `context` is the muted small text; put low-priority reference info there.
- `data_table` block: rich paginated table (`page_size` defaults to 5). First row is the header; header cells must be `raw_text`, body cells may be `rich_text` (including `link` elements). Minimum 2 rows (header + 1): omit the block when there is nothing to list. 20,000-char cap across all cells per message.
- `data_visualization` block: pie/bar/area/line charts, max 2 per message. Rarely worth it on a status card.
- `rich_text` objects (used inside plan/task_card/data_table): `{"type": "rich_text", "elements": [{"type": "rich_text_section", "elements": [{"type": "text", "text": "..."}, {"type": "link", "url": "...", "text": "..."}]}]}`.

## Constraints that `blocks.validate` does NOT catch

`blocks.validate` (public, no auth, `slack_card.py validate`) is necessary but not sufficient. These were all accepted by validate and rejected by the real post:

1. **One `plan` block per message.** Error text: "Cannot have more than 1 plan block".
2. **`task_card` and `plan` cannot coexist in one message.** Bare `invalid_blocks`, no detail. Two standalone task_cards together are fine; each alone is fine.
3. **`data_table` and `plan` DO coexist** (verified), as do `section`, `context`, and `markdown` with either.

Always treat the real post/update as the final check, and keep a fallback in mind for any new block combination.

## Rendering facts

- NEVER put blocks inside `attachments`. Attachments render as a collapsed legacy box with a "Show more" link and an "Added by <bot>" footer, and a message once posted with attachments keeps them until `chat.update` sends `"attachments": []` (the script always does).
- The top-level `text` is the push-notification and screen-reader fallback; it never renders in-channel when blocks are present. Write it to read well on a phone lock screen.
- Mentions `<@Uxxxx>` render in mrkdwn (`section`, `context`, thread replies) but not in the plain `text` fallback and not inside `markdown` blocks.
- The bot has no interactivity endpoint: never add buttons, selects, or other interactive elements. Human input arrives only as thread replies and reactions.
- Emoji at the start of the title line is the only state signal visible from the channel list; there is no color bar without attachments.

## API facts baked into `slack_card.py`

- Write methods (`chat.postMessage`, `chat.update`) take JSON bodies. Read methods (`conversations.replies`, `reactions.get`) reject JSON with `invalid_arguments` and need form-encoded params.
- Thread replies never appear in `conversations.history`; watching a card means watching its thread via `conversations.replies`.
- Reactions accumulate on a long-lived message, so a bare `check-reaction` false-fires on old ones; ask for reactions on a fresh question reply, or snapshot a baseline and fire on change.
- Bot scopes: `chat:write`, `reactions:read`, `channels:history`. No `channels:read`, so channels are resolved by name on the first post and the id is cached in config.
