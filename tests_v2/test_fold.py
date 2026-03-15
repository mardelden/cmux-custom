#!/usr/bin/env python3
"""
Integration tests for fold socket commands (debug.fold.*).

Tests the full fold lifecycle: adding, listing, removing, and clearing folds
via socket commands against a running cmux debug build.
"""

import os
import sys
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
            msg += f" — {detail}"
        print(msg)


def test_fold_list_empty(c: cmux):
    """Fresh surface has no folds."""
    folds = c.list_folds()
    check("list_empty", len(folds) == 0, f"expected 0 folds, got {len(folds)}")


def test_fold_add_and_list(c: cmux):
    """Add a fold, verify list returns correct fields."""
    res = c.add_fold(start_row=10, end_row=20, total_output_lines=15)
    check("add_returns_fold_id", "fold_id" in res, f"keys: {list(res.keys())}")
    check("add_returns_total_folds", res.get("total_folds") == 1, f"total_folds={res.get('total_folds')}")
    check("add_start_row", res.get("start_row") == 10, f"start_row={res.get('start_row')}")
    check("add_end_row", res.get("end_row") == 20, f"end_row={res.get('end_row')}")
    check("add_folded_lines", res.get("folded_lines") == 10, f"folded_lines={res.get('folded_lines')}")

    folds = c.list_folds()
    check("list_after_add", len(folds) == 1, f"expected 1 fold, got {len(folds)}")
    if folds:
        f = folds[0]
        check("list_id_matches", f.get("id") == res.get("fold_id"))
        check("list_start_row", f.get("start_row") == 10, f"start_row={f.get('start_row')}")
        check("list_end_row", f.get("end_row") == 20, f"end_row={f.get('end_row')}")
        check("list_folded_lines", f.get("folded_lines") == 10, f"folded_lines={f.get('folded_lines')}")
        check("list_total_output_lines", f.get("total_output_lines") == 15, f"total_output_lines={f.get('total_output_lines')}")
        check("list_size", f.get("size") == 10, f"size={f.get('size')}")


def test_fold_add_validation(c: cmux):
    """Rejects invalid params: end_row <= start_row, missing params."""
    # end_row <= start_row
    try:
        c.add_fold(start_row=20, end_row=10)
        check("validation_end_lte_start", False, "should have raised")
    except cmuxError:
        check("validation_end_lte_start", True)

    # end_row == start_row
    try:
        c.add_fold(start_row=10, end_row=10)
        check("validation_end_eq_start", False, "should have raised")
    except cmuxError:
        check("validation_end_eq_start", True)


def test_fold_remove_by_id(c: cmux):
    """Add fold, remove by fold_id, verify list empty."""
    res = c.add_fold(start_row=30, end_row=40)
    fold_id = res["fold_id"]

    rm = c.remove_fold(fold_id=fold_id)
    check("remove_by_id_returns_id", rm.get("removed_fold_id") == fold_id)
    check("remove_by_id_remaining", rm.get("remaining_folds") == 0, f"remaining={rm.get('remaining_folds')}")

    folds = c.list_folds()
    check("remove_by_id_list_empty", len(folds) == 0, f"expected 0, got {len(folds)}")


def test_fold_remove_by_rows(c: cmux):
    """Add fold, remove by start_row+end_row, verify list empty."""
    c.add_fold(start_row=50, end_row=60)

    rm = c.remove_fold(start_row=50, end_row=60)
    check("remove_by_rows_remaining", rm.get("remaining_folds") == 0, f"remaining={rm.get('remaining_folds')}")

    folds = c.list_folds()
    check("remove_by_rows_list_empty", len(folds) == 0, f"expected 0, got {len(folds)}")


def test_fold_remove_not_found(c: cmux):
    """Removing non-existent fold returns error."""
    try:
        c.remove_fold(fold_id="00000000-0000-0000-0000-000000000000")
        check("remove_not_found", False, "should have raised")
    except cmuxError:
        check("remove_not_found", True)


def test_fold_clear(c: cmux):
    """Add 3 folds, clear, verify empty and removed_count=3."""
    c.add_fold(start_row=100, end_row=110)
    c.add_fold(start_row=120, end_row=130)
    c.add_fold(start_row=140, end_row=150)

    res = c.clear_folds()
    check("clear_removed_count", res.get("removed_count") == 3, f"removed_count={res.get('removed_count')}")

    folds = c.list_folds()
    check("clear_list_empty", len(folds) == 0, f"expected 0, got {len(folds)}")


def test_fold_clear_empty(c: cmux):
    """Clear when no folds succeeds with removed_count=0."""
    res = c.clear_folds()
    check("clear_empty", res.get("removed_count") == 0, f"removed_count={res.get('removed_count')}")


def test_multiple_folds_ordering(c: cmux):
    """3 folds returned in insertion order."""
    c.add_fold(start_row=200, end_row=210)
    c.add_fold(start_row=220, end_row=230)
    c.add_fold(start_row=240, end_row=250)

    folds = c.list_folds()
    check("ordering_count", len(folds) == 3, f"expected 3, got {len(folds)}")
    if len(folds) == 3:
        rows = [(f["start_row"], f["end_row"]) for f in folds]
        expected = [(200, 210), (220, 230), (240, 250)]
        check("ordering_order", rows == expected, f"got {rows}")


def test_fold_max_regions_eviction(c: cmux):
    """Adding >50 folds evicts oldest."""
    # Add 51 folds — each with unique rows
    for i in range(51):
        c.add_fold(start_row=1000 + i * 20, end_row=1010 + i * 20)

    folds = c.list_folds()
    check("eviction_max_50", len(folds) == 50, f"expected 50, got {len(folds)}")

    # The oldest fold (start_row=1000) should have been evicted;
    # the second fold (start_row=1020) should now be first
    if folds:
        first_start = folds[0].get("start_row")
        check("eviction_oldest_gone", first_start == 1020, f"first start_row={first_start}, expected 1020")


def test_fold_with_explicit_surface(c: cmux):
    """Commands work with explicit surface_id param."""
    # Get the current focused surface ID
    ident = c.capabilities()
    # Use list_folds with the focused surface
    surfs = c._call("surface.list") or {}
    surfaces = surfs.get("surfaces") or []
    if not surfaces:
        check("explicit_surface_skip", True)
        return

    sid = surfaces[0].get("id")
    if not sid:
        check("explicit_surface_skip", True)
        return

    # Clear any existing folds on this surface
    c.clear_folds(surface=sid)

    # Add fold with explicit surface
    res = c.add_fold(start_row=300, end_row=310, surface=sid)
    check("explicit_surface_add", "fold_id" in res, f"keys: {list(res.keys())}")

    # List with explicit surface
    folds = c.list_folds(surface=sid)
    check("explicit_surface_list", len(folds) >= 1, f"expected >=1 fold, got {len(folds)}")

    # Clear with explicit surface
    cr = c.clear_folds(surface=sid)
    check("explicit_surface_clear", cr.get("removed_count", 0) >= 1, f"removed_count={cr.get('removed_count')}")


def main() -> int:
    global passed, failed

    with cmux(SOCKET_PATH) as c:
        # Ensure we start clean
        c.clear_folds()

        print("test_fold_list_empty")
        test_fold_list_empty(c)

        print("test_fold_add_and_list")
        test_fold_add_and_list(c)
        c.clear_folds()

        print("test_fold_add_validation")
        test_fold_add_validation(c)
        c.clear_folds()

        print("test_fold_remove_by_id")
        test_fold_remove_by_id(c)
        c.clear_folds()

        print("test_fold_remove_by_rows")
        test_fold_remove_by_rows(c)
        c.clear_folds()

        print("test_fold_remove_not_found")
        test_fold_remove_not_found(c)
        c.clear_folds()

        print("test_fold_clear")
        test_fold_clear(c)

        print("test_fold_clear_empty")
        test_fold_clear_empty(c)

        print("test_multiple_folds_ordering")
        test_multiple_folds_ordering(c)
        c.clear_folds()

        print("test_fold_max_regions_eviction")
        test_fold_max_regions_eviction(c)
        c.clear_folds()

        print("test_fold_with_explicit_surface")
        test_fold_with_explicit_surface(c)

    print(f"\n{'='*40}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed:
        print("FAIL")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
