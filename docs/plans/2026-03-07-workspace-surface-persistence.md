# Workspace/Surface persistence

**Status:** Completed
**Branch:** `cmux-persistent-session-ids`
**Date:** 2026-03-07

## Problem

Workspace and surface IDs were regenerated on every app restart, breaking any external tooling or scripts that referenced specific sessions.

## Solution

Persist workspace and surface IDs across restarts using SessionPersistence (schema v2). IDs are saved when the app quits and restored on launch.

## Files changed

- `Sources/SessionPersistence.swift` — Schema v2 with stable IDs
- `Sources/Workspace.swift` — Save/restore workspace IDs
- `Sources/GhosttyTerminalView.swift` — Surface ID persistence
- `Sources/Panels/TerminalPanel.swift` — Panel ID persistence
- `Sources/Panels/BrowserPanel.swift` — Panel ID persistence
- `Sources/Panels/MarkdownPanel.swift` — Panel ID persistence
- `Sources/TabManager.swift` — Tab ID persistence
- `scripts/reloads.sh` — Staging reload script
