# Make maxDocumentHeight configurable

**Status:** Planned
**Date:** 2026-03-14

## Context

The `maxDocumentHeight` cap (500,000 px) in `GhosttySurfaceScrollView` prevents AppKit scroll view performance degradation with huge scrollback (multi-million pixel documents). Scroll position uses ratio-based calculation so the cap doesn't affect accuracy.

Currently hardcoded as a static constant. Should be user-configurable following cmux's existing `@AppStorage` + `UserDefaults` pattern.

## Design decisions

- **Default: 10,000** — Ratio-based scroll positioning means the actual value barely matters; smaller is better for AppKit performance
- **0 = unlimited** — For users who want no cap (at the cost of potential AppKit slowdowns)
- **Snapshotted once per app session** — Matches the `sessionPortBase` pattern. Changing requires restart.
- **Settings location:** Automation section, after port range settings

## Changes

### `Sources/cmuxApp.swift`
- Add `@AppStorage("scrollbackDocumentHeightLimit")` with default `500_000`
- Add `SettingsCard` in Automation section with number text field

### `Sources/GhosttyTerminalView.swift`
- Replace hardcoded `maxDocumentHeight = 500_000` with `UserDefaults` read
- 0 maps to `.greatestFiniteMagnitude` (unlimited)

### `Resources/Localizable.xcstrings`
- Add localization keys for setting label and subtitle
