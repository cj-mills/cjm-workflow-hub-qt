"""panes.py contract: the donor's _paint_row/_paint_status semantics as pure
row/status builders (single-style rows, the transcription-qt discipline)."""

from cjm_workflow_hub_qt import panes

ROWS = [
    {"kind": "collection", "id": "c1", "title": "Alpha", "status": "proposed",
     "count": 2},
    {"kind": "source", "id": "s1", "title": "one", "coll_id": "c1",
     "ordered": True, "counts": {"transcripts": 1, "fine_segs": 3}},
    {"kind": "source", "id": "s2", "title": "two", "coll_id": "c1",
     "ordered": False, "counts": {}},
    {"kind": "collection", "id": None, "title": "Unfiled", "status": "none",
     "count": 1},
    {"kind": "source", "id": "s3", "title": "loose", "coll_id": None,
     "ordered": False, "counts": {}},
]


def test_collection_rows_carry_status_style_and_flag():
    out = panes.hub_rows(ROWS, set(), "browse", None, [])
    assert out[0]["text"] == "Alpha ⚑ proposed  (2)"
    assert out[0]["style"] == "bold yellow"
    assert out[3]["text"] == "Unfiled  (1)"
    assert out[3]["style"] == "bold dim"


def test_source_rows_pick_box_indent_glance_and_ordered():
    out = panes.hub_rows(ROWS, {"s1"}, "browse", None, [])
    assert out[1]["text"] == "[x]   one  TDc 3segs  ·ordered"
    assert out[1]["style"] == "green"
    assert out[2]["text"] == "[ ]   two  tdc"
    assert out[2]["style"] == ""
    # unfiled sources have no membership indent
    assert out[4]["text"] == "[ ] loose  tdc"


def test_order_mode_rows_show_positions_for_the_ordered_collection_only():
    out = panes.hub_rows(ROWS, set(), "order", "c1", ["s2", "s1"])
    assert out[1]["text"].startswith("   2. one")
    assert out[1]["style"] == "magenta"
    assert out[2]["text"].startswith("   1. two")
    # the unfiled source keeps its browse paint
    assert out[4]["text"].startswith("[ ] ")


def test_status_ladder_precedence():
    kw = dict(error=None, busy=None, pending_title=None, pending_count=0,
              editing=None, mode="browse")
    assert "space select" in panes.status_text(**kw)
    assert panes.status_text(**{**kw, "mode": "order"}).strip().startswith("ORDER MODE")
    assert "enter title" in panes.status_text(**{**kw, "editing": "file"})
    two = panes.status_text(**{**kw, "editing": "file",
                               "pending_title": "Alpha", "pending_count": 2})
    assert "EXISTING collection (2 members)" in two
    assert "curating" in panes.status_text(**{**kw, "busy": "curating…"})
    assert panes.status_text(**{**kw, "error": "boom", "busy": "x"}).strip() == "boom"


def test_group_targets_by_collection_matches_the_donor_grouping():
    grouped = panes.group_targets_by_collection(ROWS, {"s1", "s2", "s3"})
    assert grouped == {"c1": ["s1", "s2"], None: ["s3"]}
    assert panes.group_targets_by_collection(ROWS, {"s2"}) == {"c1": ["s2"]}
