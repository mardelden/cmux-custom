#!/usr/bin/env python3
"""
End-to-end rendering tests for fold behavior.

These tests type real commands (e.g. `seq 30`) into a running cmux debug build
and verify that folds are created with the correct dimensions and that visible
text matches expectations (head/tail lines visible, middle lines folded).

IMPORTANT: Commands must be sent to a SEPARATE workspace from the one running
this test script. Otherwise keystrokes queue behind the Python process and
only execute after the script exits.

Requires a running cmux debug build with shell integration enabled.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from cmux import cmux, cmuxError

SOCKET_PATH = os.environ.get("CMUX_SOCKET", "/tmp/cmux-debug.sock")

passed = 0
failed = 0


def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        msg = f"  FAIL: {name}"
        if detail:
            msg += f" -- {detail}"
        print(msg)


def _setup_test_workspace(c: cmux) -> tuple:
    """Create a new workspace for test commands and return (workspace_id, surface_id).

    The test script's own terminal stays in the original workspace.
    We query the new workspace's surface list directly instead of relying
    on focus state, which may not have settled yet.
    """
    ws_id = c.new_workspace()
    # Wait for the new workspace's shell to initialize
    time.sleep(1.5)
    # Get surfaces belonging to this specific workspace
    surfaces = c.list_surfaces(workspace=ws_id)
    if not surfaces:
        raise cmuxError(f"No surfaces found in new workspace {ws_id}")
    # surfaces is list of (index, id, focused) tuples
    sid = surfaces[0][1]
    return ws_id, sid


def _wait_for_fold(c: cmux, surface: str, timeout_s: float = 8.0) -> bool:
    """Poll list_folds() on a specific surface until at least one fold exists."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        folds = c.list_folds(surface=surface)
        if folds:
            return True
        time.sleep(0.2)
    return False


def _wait_for_text(c: cmux, surface: str, marker: str, timeout_s: float = 8.0) -> bool:
    """Poll read_terminal_text() until marker appears in the surface."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        text = c.read_terminal_text(panel=surface)
        if marker in text:
            return True
        time.sleep(0.2)
    return False


def _reset_fold_settings(c: cmux):
    """Restore default fold settings."""
    c.set_fold_settings(threshold=20, head_lines=3, tail_lines=3)


def _visible_lines(c: cmux, surface: str) -> set:
    """Return the set of stripped non-empty lines visible in a surface's viewport."""
    text = c.read_terminal_text(panel=surface)
    return set(l.strip() for l in text.strip().split("\n") if l.strip())


def _send_and_wait_fold(c: cmux, surface: str, cmd: str = "seq 30\n",
                        timeout_s: float = 8.0) -> bool:
    """Send a command to a surface and wait for a fold to appear."""
    c.send_surface(surface, cmd)
    return _wait_for_fold(c, surface, timeout_s=timeout_s)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_settings_readable(c: cmux):
    """get_fold_settings returns expected defaults."""
    _reset_fold_settings(c)
    settings = c.get_fold_settings()
    check("settings_threshold", settings.get("threshold") == 20,
          f"expected 20, got {settings.get('threshold')}")
    check("settings_head_lines", settings.get("head_lines") == 3,
          f"expected 3, got {settings.get('head_lines')}")
    check("settings_tail_lines", settings.get("tail_lines") == 3,
          f"expected 3, got {settings.get('tail_lines')}")


def test_settings_writable(c: cmux):
    """set_fold_settings changes values, get_fold_settings reflects them."""
    c.set_fold_settings(threshold=10, head_lines=5, tail_lines=7)
    settings = c.get_fold_settings()
    check("writable_threshold", settings.get("threshold") == 10,
          f"expected 10, got {settings.get('threshold')}")
    check("writable_head_lines", settings.get("head_lines") == 5,
          f"expected 5, got {settings.get('head_lines')}")
    check("writable_tail_lines", settings.get("tail_lines") == 7,
          f"expected 7, got {settings.get('tail_lines')}")
    _reset_fold_settings(c)


def test_seq30_fold_created(c: cmux, surface: str):
    """Run `seq 30` in test surface, verify fold dimensions are consistent."""
    _reset_fold_settings(c)
    c.clear_folds(surface=surface)

    if not _send_and_wait_fold(c, surface):
        check("seq30_fold_created", False, "No fold created after seq 30")
        return

    folds = c.list_folds(surface=surface)
    check("seq30_fold_count", len(folds) == 1,
          f"expected 1 fold, got {len(folds)}")

    if folds:
        fold = folds[0]
        folded = fold.get("folded_lines", 0)
        total = fold.get("total_output_lines", 0)
        # Terminal counts more lines than just seq output (command echo,
        # prompt, etc.), so total_output_lines > 30. Verify consistency:
        # folded_lines == total_output_lines - head(3) - tail(3)
        expected_folded = total - 3 - 3
        check("seq30_folded_consistent",
              folded == expected_folded,
              f"folded_lines={folded}, expected total({total})-3-3={expected_folded}")
        check("seq30_folded_reasonable", folded >= 20,
              f"folded_lines={folded}, expected >= 20")


def test_seq30_visible_text(c: cmux, surface: str):
    """After fold, visible text contains early seq numbers and late ones, but not middle."""
    _reset_fold_settings(c)
    c.clear_folds(surface=surface)

    if not _send_and_wait_fold(c, surface):
        check("visible_text_fold", False, "No fold created")
        return

    time.sleep(0.3)
    line_set = _visible_lines(c, surface)

    # The first few seq numbers should be in the head (visible)
    check("visible_head_1", "1" in line_set,
          f"'1' not found in visible lines")
    check("visible_head_2", "2" in line_set,
          f"'2' not found in visible lines")

    # The last seq number should be in the tail (visible)
    check("visible_tail_30", "30" in line_set,
          f"'30' not found in visible lines")
    check("visible_tail_29", "29" in line_set,
          f"'29' not found in visible lines")

    # Verify a fold exists covering the middle lines (read_terminal_text
    # reads the underlying buffer, not the visual viewport, so we verify
    # hiding via the fold data model instead of text absence).
    folds = c.list_folds(surface=surface)
    check("visible_fold_exists", len(folds) == 1,
          f"expected 1 fold, got {len(folds)}")
    if folds:
        check("visible_fold_covers_middle", folds[0].get("folded_lines", 0) >= 20,
              f"fold should hide >=20 lines, got {folds[0].get('folded_lines')}")


def test_seq30_unfold_restores_text(c: cmux, surface: str):
    """Remove fold, visible text shows all 30 lines."""
    _reset_fold_settings(c)
    c.clear_folds(surface=surface)

    if not _send_and_wait_fold(c, surface):
        check("unfold_fold_exists", False, "No fold created")
        return

    # Now unfold
    c.clear_folds(surface=surface)
    time.sleep(0.3)

    line_set = _visible_lines(c, surface)

    # After unfolding, middle lines should be visible
    check("unfold_shows_10", "10" in line_set,
          f"'10' not found after unfold")
    check("unfold_shows_15", "15" in line_set,
          f"'15' not found after unfold")
    check("unfold_shows_20", "20" in line_set,
          f"'20' not found after unfold")


def test_tail_lines_respected(c: cmux, surface: str):
    """Set tail_lines=5, run seq 30. With more tail lines, more rows stay visible at end."""
    c.set_fold_settings(threshold=20, head_lines=3, tail_lines=5)
    c.clear_folds(surface=surface)

    if not _send_and_wait_fold(c, surface):
        check("tail5_fold_created", False, "No fold created")
        _reset_fold_settings(c)
        return

    folds = c.list_folds(surface=surface)
    if folds:
        fold = folds[0]
        folded = fold.get("folded_lines", 0)
        total = fold.get("total_output_lines", 0)
        expected = total - 3 - 5
        check("tail5_folded_consistent",
              folded == expected,
              f"folded_lines={folded}, expected total({total})-3-5={expected}")

    time.sleep(0.3)
    line_set = _visible_lines(c, surface)

    check("tail5_visible_30", "30" in line_set,
          f"'30' not found in visible lines")
    check("tail5_visible_29", "29" in line_set,
          f"'29' not found in visible lines")
    # Verify fold covers middle (buffer reads include folded text)
    folds = c.list_folds(surface=surface)
    if folds:
        check("tail5_fold_covers_middle", folds[0].get("folded_lines", 0) >= 18,
              f"fold should hide >=18 lines, got {folds[0].get('folded_lines')}")

    _reset_fold_settings(c)


def test_head_lines_respected(c: cmux, surface: str):
    """Set head_lines=5, run seq 30. With more head lines, more rows stay visible at start."""
    c.set_fold_settings(threshold=20, head_lines=5, tail_lines=3)
    c.clear_folds(surface=surface)

    if not _send_and_wait_fold(c, surface):
        check("head5_fold_created", False, "No fold created")
        _reset_fold_settings(c)
        return

    folds = c.list_folds(surface=surface)
    if folds:
        fold = folds[0]
        folded = fold.get("folded_lines", 0)
        total = fold.get("total_output_lines", 0)
        expected = total - 5 - 3
        check("head5_folded_consistent",
              folded == expected,
              f"folded_lines={folded}, expected total({total})-5-3={expected}")

    time.sleep(0.3)
    line_set = _visible_lines(c, surface)

    check("head5_visible_1", "1" in line_set,
          f"'1' not found in visible lines")
    check("head5_visible_2", "2" in line_set,
          f"'2' not found in visible lines")
    # Verify fold covers middle (buffer reads include folded text)
    folds = c.list_folds(surface=surface)
    if folds:
        check("head5_fold_covers_middle", folds[0].get("folded_lines", 0) >= 18,
              f"fold should hide >=18 lines, got {folds[0].get('folded_lines')}")

    _reset_fold_settings(c)


def test_fold_indicator_position(c: cmux, surface: str):
    """Fold region spans the middle of output, not the very end."""
    _reset_fold_settings(c)
    c.clear_folds(surface=surface)

    if not _send_and_wait_fold(c, surface):
        check("indicator_fold_exists", False, "No fold created")
        return

    time.sleep(0.3)
    folds = c.list_folds(surface=surface)
    if not folds:
        check("indicator_has_fold", False, "No folds found")
        return

    fold = folds[0]
    start_row = fold.get("start_row", 0)
    end_row = fold.get("end_row", 0)
    folded_lines = fold.get("folded_lines", 0)
    total = fold.get("total_output_lines", 0)

    check("indicator_has_range", folded_lines > 0,
          f"folded_lines={folded_lines}")
    check("indicator_start_before_end", start_row < end_row,
          f"start_row={start_row} should be < end_row={end_row}")

    expected = total - 3 - 3
    check("indicator_correct_span", folded_lines == expected,
          f"folded_lines={folded_lines}, expected total({total})-3-3={expected}")

    check("indicator_not_at_end", end_row - start_row < total,
          f"fold spans {end_row - start_row} rows but total output is {total}")


def test_changing_tail_changes_fold_size(c: cmux, surface: str):
    """Changing tail_lines from 3 to 5 results in a smaller fold (2 fewer folded rows)."""
    # First run with tail=3
    c.set_fold_settings(threshold=20, head_lines=3, tail_lines=3)
    c.clear_folds(surface=surface)

    if not _send_and_wait_fold(c, surface):
        check("compare_first_fold", False, "No fold created with tail=3")
        _reset_fold_settings(c)
        return
    folds_t3 = c.list_folds(surface=surface)
    folded_t3 = folds_t3[0].get("folded_lines", 0) if folds_t3 else 0

    # Second run with tail=5
    c.set_fold_settings(threshold=20, head_lines=3, tail_lines=5)
    c.clear_folds(surface=surface)

    if not _send_and_wait_fold(c, surface):
        check("compare_second_fold", False, "No fold created with tail=5")
        _reset_fold_settings(c)
        return
    folds_t5 = c.list_folds(surface=surface)
    folded_t5 = folds_t5[0].get("folded_lines", 0) if folds_t5 else 0

    # tail=5 should fold 2 fewer rows than tail=3
    check("tail_change_reduces_fold",
          folded_t3 - folded_t5 == 2,
          f"tail=3 folded {folded_t3}, tail=5 folded {folded_t5}, "
          f"diff={folded_t3 - folded_t5}, expected 2")

    _reset_fold_settings(c)


def main() -> int:
    global passed, failed

    with cmux(SOCKET_PATH) as c:
        assert c.ping(), "Failed to ping cmux"

        # --- Settings tests (no terminal interaction needed) ---
        print("test_settings_readable")
        test_settings_readable(c)

        print("\ntest_settings_writable")
        test_settings_writable(c)

        # --- Create a separate workspace for rendering tests ---
        # Commands must run in a different shell from the one executing
        # this script, otherwise keystrokes queue behind the Python process.
        print("\n--- Creating test workspace ---")
        test_ws, test_surface = _setup_test_workspace(c)
        print(f"  Test workspace: {test_ws}")
        print(f"  Test surface: {test_surface}")

        print("\ntest_seq30_fold_created")
        test_seq30_fold_created(c, test_surface)
        c.clear_folds(surface=test_surface)

        print("\ntest_seq30_visible_text")
        test_seq30_visible_text(c, test_surface)
        c.clear_folds(surface=test_surface)

        print("\ntest_seq30_unfold_restores_text")
        test_seq30_unfold_restores_text(c, test_surface)
        c.clear_folds(surface=test_surface)

        print("\ntest_tail_lines_respected")
        test_tail_lines_respected(c, test_surface)
        c.clear_folds(surface=test_surface)

        print("\ntest_head_lines_respected")
        test_head_lines_respected(c, test_surface)
        c.clear_folds(surface=test_surface)

        print("\ntest_fold_indicator_position")
        test_fold_indicator_position(c, test_surface)
        c.clear_folds(surface=test_surface)

        print("\ntest_changing_tail_changes_fold_size")
        test_changing_tail_changes_fold_size(c, test_surface)
        c.clear_folds(surface=test_surface)

        # Leave test workspace open so user can inspect the terminal visually
        _reset_fold_settings(c)
        print("\n--- Test workspace left open for inspection ---")
        print(f"  Switch to workspace '{test_ws}' to see fold results")

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        print("FAIL")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
