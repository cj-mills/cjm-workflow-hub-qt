"""Pure row/label builders for the Qt hub shell — the paint logic, Qt-free.

Each function mirrors a Textual `_paint_*` region of cjm-workflow-hub-tui's
app.py, re-expressed as row dicts ({"text", "style"}) the shell materializes
into one QListWidget (the transcription-qt panes discipline). No windowing
(visible_slice) — Qt lists scroll natively — and no cursor marker: the list's
native current-row highlight is the focus paint. Style words match the kit
vocabulary (STYLE_COLORS): a row carries ONE style set, so the donor's
per-span styling collapses onto the row's dominant span (the picked box, the
order position, the collection status) — the transcription-qt precedent."""

from typing import Any, Dict, List, Optional

from .spine import stage_glance

_COLL_STYLE = {"proposed": "bold yellow", "confirmed": "bold green",
               "none": "bold dim"}


def hub_rows(rows: List[Dict[str, Any]],        # build_rows output (spine)
             selected: set,                     # source ids picked with space
             mode: str,                         # "browse" | "order"
             order_coll: Optional[str],         # collection being reordered
             order_work: List[str],             # member ids in working order
             ) -> List[Dict[str, Any]]:  # [{"text", "style"}] 1:1 with rows
    """One list row per spine row — the donor's _paint_row, single-style.

    Collections: status-colored title, ⚑ when proposed, member count.
    Sources: the [x] pick box (green when picked), the order-mode position
    prefix (magenta) for members of the collection being reordered, the
    stage-at-a-glance suffix, and ·ordered for chain members."""
    out: List[Dict[str, Any]] = []
    for row in rows:
        if row["kind"] == "collection":
            text = row["title"]
            if row["status"] == "proposed":
                text += " ⚑ proposed"
            text += f"  ({row['count']})"
            out.append({"text": text, "style": _COLL_STYLE[row["status"]]})
            continue
        in_order = (mode == "order" and row.get("coll_id") == order_coll)
        if in_order:
            pos = order_work.index(row["id"]) if row["id"] in order_work else -1
            prefix = f"{pos + 1:>4}. "
            style = "magenta"
        else:
            picked = row["id"] in selected
            prefix = ("[x] " if picked else "[ ] ") + ("  " if row["coll_id"] else "")
            style = "green" if picked else ""
        text = prefix + row["title"]
        glance = stage_glance(row.get("counts") or {})
        if glance:
            text += f"  {glance}"
        if row.get("ordered"):
            text += "  ·ordered"
        out.append({"text": text, "style": style})
    return out


def status_text(*, error: Optional[str],        # sticky error, if any
                busy: Optional[str],            # in-flight note, if any
                pending_title: Optional[str],   # two-phase existing-title confirm
                pending_count: int,             # members of the existing collection
                editing: Optional[str],         # None | "file" | "rename"
                mode: str,                      # "browse" | "order"
                ) -> str:  # The one-line status text (donor _paint_status)
    """The donor's status ladder, verbatim precedence: error > busy > the
    two-phase existing-title confirm (d544e250: surface, never block) >
    editor hint > order-mode hint > the browse key legend."""
    if error:
        return f" {error} "
    if busy:
        return f" {busy} "
    if pending_title:
        return (f" '{pending_title}' attaches to EXISTING collection "
                f"({pending_count} members) — enter again to confirm ")
    if editing:
        return " enter title (empty cancels) · esc cancel "
    if mode == "order":
        return " ORDER MODE  ·  J/K move member · enter commit · esc cancel "
    return (" space select · f file/refile · r rename/merge · y confirm"
            " · g order · 1/2/3 launch t/d/c · R reload · q quit")


def group_targets_by_collection(
    rows: List[Dict[str, Any]],   # build_rows output (spine)
    targets: set,                 # source ids being filed
) -> Dict[Optional[str], List[str]]:  # coll_id (None = unfiled) -> member ids
    """Group the filed sources by the collection they LEAVE, so each move is
    one journaled op (the donor's _commit_file grouping, pure)."""
    by_coll: Dict[Optional[str], List[str]] = {}
    for r in rows:
        if r["kind"] == "source" and r["id"] in targets:
            by_coll.setdefault(r.get("coll_id"), []).append(r["id"])
    return by_coll


def status_readout(*, error: Optional[str], busy: Optional[str],
                   pending_title: Optional[str], pending_count: int) -> str:
    """The status ladder's RESULT half (DEC 2a42c028 adoption): error >
    busy > the two-phase existing-title confirm. Empty when quiet — the
    modal prompts moved to the context slot (context_text) and the browse
    key legend to the hint line/overlay."""
    if error:
        return error
    if busy:
        return busy
    if pending_title:
        return (f"'{pending_title}' attaches to EXISTING collection "
                f"({pending_count} members) — enter again to confirm")
    return ""


def context_text(*, editing: Optional[str], mode: str) -> str:
    """The status ladder's MODE-SCOPED half: the editor prompt and the
    order-mode guidance ride the strip's context slot, present exactly
    while their mode is."""
    if editing:
        return "enter title (empty cancels) · esc cancel"
    if mode == "order":
        return "ORDER MODE · J/K move member · enter commit · esc cancel"
    return ""


def hint_entries() -> List[Dict[str, str]]:
    """The hub's declarative hint model (DEC 2a42c028): keyPressEvent-idiom
    app, so the model is data — verbs name the action methods."""
    def e(verb: str, key: str, label: str, group: str) -> Dict[str, str]:
        return {"verb": verb, "key": key, "label": label, "group": group}
    return [e("move", "j/k", "walk rows", "Browse"),
            e("filter", "/", "filter rows", "Browse"),
            e("toggle_select", "space", "select", "Browse"),
            e("reload", "R", "reload", "Browse"),
            e("file", "f", "file/refile", "Collections"),
            e("rename", "r", "rename/merge", "Collections"),
            e("confirm", "y", "confirm", "Collections"),
            e("order_mode", "g", "order mode", "Collections"),
            e("launch_transcription", "1", "launch transcription", "Launch"),
            e("launch_decomp", "2", "launch decomp", "Launch"),
            e("launch_correction", "3", "launch correction", "Launch"),
            e("cancel", "esc", "cancel", "App"),
            e("quit", "q", "quit", "App")]


def default_pins() -> List[str]:
    """The hint line's default verbs before the user pins their own."""
    return ["move", "filter", "toggle_select", "launch_transcription"]
