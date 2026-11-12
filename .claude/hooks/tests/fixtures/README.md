# Hook payload fixtures

These files are PreToolUse payloads that the hook tests feed to the hooks on stdin.
Each test loads a fixture and replaces only `tool_input` (and sometimes `cwd`).

## Status: derived from real captured payloads (`*.captured.json`)

The fixtures derive from real PreToolUse payloads captured from Claude Code on 2026-11-12
(main session and workflow subagents). Every value that could identify a session or hold
private data was scrubbed:

| Kept from the capture | Replaced |
|---|---|
| the exact key set and key order | `session_id`, `prompt_id`: fixed fake UUIDs |
| `hook_event_name` (`PreToolUse`) | `agent_id`: fixed fake id of the captured length |
| `permission_mode` | `tool_use_id`: `toolu_FakeFixture...` |
| `tool_name` | `transcript_path`, `scratchpad_dir`: neutral paths under `/tmp/claude-fixture/` |
| `agent_type` (`workflow-subagent`) | `cwd`: the project root (the tests resolve relative paths against it) |
| `effort` | `tool_input`: synthetic values with the captured key set |

No captured `tool_input` content, transcript path or id was copied. The files were run
through `tools/ws/denylist-scan`.

Key sets, as captured:

- every payload: `session_id`, `transcript_path`, `cwd`, `scratchpad_dir`, `prompt_id`,
  `permission_mode`, `effort`, `hook_event_name`, `tool_name`, `tool_input`, `tool_use_id`;
- subagent payloads add `agent_id` and `agent_type` (after `permission_mode`). Main-session
  payloads have neither.

What the capture showed, and the hooks rely on:

- A subagent's `cwd` is the session's working directory (the project root or the folder the
  main session was in), **not** its worktree. So `ship-guard` treats any payload with
  `agent_id` as a lane, wherever its `cwd` is.
- The main session's `cwd` follows its last `cd`. It can sit anywhere, even under `.tmp-session/`.

| Fixture | Shape | Harness key |
|---|---|---|
| `main-bash.captured.json` | main session, Bash | `main-bash` |
| `main-read.captured.json` | main session, Read | `main-read` |
| `subagent-bash.captured.json` | subagent, Bash | `sub-bash`; also `sub-wt-bash` with `cwd` set to `.tmp-session/wt/s1-lane-a` |
| `subagent-write.captured.json` | subagent, Write | `sub-write` |

## Refreshing them

1. Add a temporary logging hook to `.claude/settings.local.json` (never to `settings.json`):
   a `PreToolUse` hook whose command appends stdin to `.tmp-session/hook-capture/payloads.jsonl`.
2. Run one Bash call and one Read from the main session, and one Bash call and one Write
   from a subagent.
3. Rebuild the fixtures with a scrubber that copies only the key order and the structural
   values in the table above, and writes synthetic values for everything else. Never copy
   captured `tool_input` content.
4. Run the denylist scan on this folder and the hook tests.
5. Remove the logging hook and delete `.tmp-session/hook-capture/`.
