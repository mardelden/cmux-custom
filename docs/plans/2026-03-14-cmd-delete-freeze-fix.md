# Fix: Terminal freeze on Cmd+Delete after huge single-line output

**Status:** Root cause identified, fix pending
**Branch:** `cmux-persistent-session-ids`
**Date:** 2026-03-14

## Problem

After `curl` returns a huge JSON blob (5M chars, no newlines), pressing **Cmd+Delete** freezes the terminal for 2+ minutes. Regular backspace and Option+backspace work fine.

## Investigation

### What we tried (did NOT help)
- `setopt prompt_cr prompt_sp`
- Disabling Starship prompt
- Key timing instrumentation (confirmed `interpretKeyEvents` returns in 6ms)

### What we built to diagnose
- **Stall detector with auto-sampling:** When the main thread blocks >2s, automatically runs `/usr/bin/sample <pid> 1` and saves to `/tmp/cmux-stall-<epoch>.txt`. 30-second cooldown.
- **IO callback coalescer:** `ThreadSafeCallbackCoalescer<T>` collapses rapid-fire IO thread callbacks into one main-thread dispatch per run-loop cycle. Independently valuable optimization.

### Root cause (from `/usr/bin/sample` stack trace)

```
flagsChanged → Surface.linkAtPin → onig_search → search_in_range → match_at → onigenc_step_back
```

When Cmd is released after Cmd+Delete, `flagsChanged` fires. Ghostty calls `linkAtPin` which:
1. Calls `screen.selectLine()` — selects the **entire logical line** (5M chars, no newlines)
2. Runs Oniguruma regex on the full string for URL detection
3. Regex engine takes minutes on a 5M-char string

The fix belongs in `ghostty/src/Surface.zig` → `linkAtPin()` function. The link detection should be limited to visible text only, not the entire logical line.

## Fix approach

Modify `linkAtPin` in the Ghostty submodule (`ghostty/src/Surface.zig`, line 4469) to limit the text passed to regex. Options:
1. **Clamp selection to visible columns** — only extract/regex the visible portion of the line
2. **Length guard** — skip regex if the extracted string exceeds a threshold (e.g., 10K chars)
3. **Both** — clamp to visible + length guard as safety net

Option 1 is the correct fix since no one interacts with URLs in the non-visible portion of a line.

## Related changes (keep)

| Change | File | Rationale |
|--------|------|-----------|
| Stall detector + auto-sample | `GhosttyTerminalView.swift` | Reusable diagnostic tool |
| IO callback coalescer | `GhosttyTerminalView.swift` | Independent perf optimization |
| `maxDocumentHeight` cap | `GhosttyTerminalView.swift` | Prevents AppKit scroll perf issues |
| Ratio-based scroll positioning | `GhosttyTerminalView.swift` | Fixes scroll accuracy with capped doc height |
| `tick.slow` timing log | `GhosttyTerminalView.swift` | Lightweight, useful for perf debugging |

## Related changes (discard)

| Change | Rationale |
|--------|-----------|
| `key.surfaceKey.slow` timing (ctrl + keyDown paths) | Confirmed key sending is fast, not needed |
| `key.interpretKeyEvents.slow` + mods logging | Same — confirmed not the bottleneck |
| `scroll.sync.slow` timing | Investigation-only instrumentation |
