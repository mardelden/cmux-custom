# Fix: Terminal freeze on Cmd+Delete after huge single-line output

**Status:** Fix implemented, testing
**Branch:** `perf-optimizations` (cmux) + `fix-link-regex-stall` (ghostty submodule)
**Date:** 2026-03-14

## Problem

After `curl` returns a huge JSON blob (5M chars, no newlines), pressing **Cmd+Delete** freezes the terminal for 2+ minutes. Regular backspace and Option+backspace work fine.

## Root cause

```
flagsChanged → Surface.linkAtPin → onig_search → search_in_range → match_at → onigenc_step_back
```

When Cmd is released after Cmd+Delete, `flagsChanged` fires. Ghostty calls `linkAtPin` which:
1. Calls `screen.selectLine()` — selects the **entire logical line** (5M chars, no newlines)
2. Runs Oniguruma regex on the full string for URL detection
3. Regex engine takes minutes on a 5M-char string

## Fix

**File:** `ghostty/src/Surface.zig` → `linkAtPin()` (line ~4514)

Added a length guard: skip regex if the extracted line exceeds 10K chars. No clickable URL exists in such lines.

```zig
if (str_len > 10_000) return null;
```

**Ghostty branch:** `fix-link-regex-stall` on `mardelden/ghostty-custom`
**Commit:** `1246c4e76`

### Merging checklist

After testing is verified:
1. Push ghostty branch: `cd ghostty && git push origin fix-link-regex-stall`
2. Merge to fork main: `git checkout main && git merge fix-link-regex-stall && git push origin main`
3. **Update submodule pointer in cmux-custom:** `cd .. && git add ghostty && git commit -m "Update ghostty submodule — fix link regex stall"`

## Investigation summary

### What we tried (did NOT help)
- `setopt prompt_cr prompt_sp`
- Disabling Starship prompt
- Key timing instrumentation (confirmed `interpretKeyEvents` returns in 6ms)

### What we built to diagnose
- **Stall detector with auto-sampling:** captures `/usr/bin/sample` when main thread blocks >2s
- **IO callback coalescer:** collapses rapid-fire IO callbacks into one main-thread dispatch per cycle

## Related changes (committed on `perf-optimizations`)

| Change | File | Rationale |
|--------|------|-----------|
| Stall detector + auto-sample | `GhosttyTerminalView.swift` | Reusable diagnostic tool |
| IO callback coalescer | `GhosttyTerminalView.swift` | Independent perf optimization |
| `maxDocumentHeight` cap (configurable) | `GhosttyTerminalView.swift` + `cmuxApp.swift` | Prevents AppKit scroll perf issues |
| Ratio-based scroll positioning | `GhosttyTerminalView.swift` | Fixes scroll accuracy with capped doc height |
| `tick.slow` timing log | `GhosttyTerminalView.swift` | Lightweight perf debugging |
