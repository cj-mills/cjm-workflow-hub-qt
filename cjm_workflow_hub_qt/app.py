"""The Qt hub shell: the workspace front door under PySide6 (DEC 61b46ae8, a
direct port IN SPIRIT of cjm-workflow-hub-tui per amendment 2030586d). One
window, one list: the spine's grouped rows (collections with ⚑-flagged
proposals, stage-at-a-glance status per source), the curation vocabulary —
confirm (y), file/refile (f), rename-or-merge (r), order mode (g + J/K) —
riding the sidecar journal (ccbab9f5), and the launcher keys (1/2/3) which
now SPAWN the Qt stage apps as detached processes across their core envs:
the Textual suspend dance disappears, and a 2s poll reloads the hub when a
child exits (the donor's reload-on-resume semantics).

Shell-only by design: every stateful decision lives in the imported spine
(build_rows / stage_glance / HubData) or in HubShellSession, whose loop
thread owns the capability stack; this module materializes panes.py row
dicts into one QListWidget and forwards key gestures through a single
keyPressEvent dispatcher (the correction-qt idiom) with the donor's
mode/editing/busy gates. The transient editor stays an inline QLineEdit so
the d544e250 two-phase existing-title confirm can PAINT in the status line
under it and take the second enter — surfacing, never a gate."""

import getpass
from typing import Any, Dict, List, Optional

from cjm_substrate_qt_kit.style import apply_row_style
from cjm_transcript_graph_schema.schema import collection_node_id
from cjm_workflow_hub_tui.spine import build_rows, HubData
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
                               QVBoxLayout, QWidget)

from . import panes
from .launch import build_stage_cmd, resolve_stage_app, spawn_stage, STAGE_APPS
from .session import HubShellSession

_KEYNAMES = {Qt.Key_Up: "up", Qt.Key_Down: "down",
             Qt.Key_Escape: "escape", Qt.Key_Return: "enter",
             Qt.Key_Enter: "enter", Qt.Key_Space: "space"}


class HubWindow(QMainWindow):
    """The hub surface under Qt — grouped browse + curation + stage spawn."""

    stack_opened = Signal(object)   # loop-thread Future -> Qt thread (queued)
    data_loaded = Signal(object)    # every load/gesture resolves through here

    def __init__(self, manifests_dir: str,               # Capability manifests directory
                 *, graph_db_path: Optional[str] = None,  # Explicit db (None = workspace answers)
                 graph_capability: str = "cjm-capability-graph-sqlite"):
        super().__init__()
        self.setWindowTitle("cjm workflow hub (qt)")
        self.resize(900, 640)
        self.graph_db_path = graph_db_path
        self.data = HubData()
        self.rows: List[Dict[str, Any]] = []
        self.cursor = 0
        self.selected: set = set()           # source ids picked for f (space)
        self.mode = "browse"                 # "browse" | "order"
        self.order_coll: Optional[str] = None
        self.order_work: List[str] = []      # member ids being reordered
        self.editing: Optional[str] = None   # None | "file" | "rename"
        self.pending_title: Optional[str] = None  # two-phase existing-title confirm
        self.busy: Optional[str] = None
        self.error: Optional[str] = None
        self.children: Dict[Any, str] = {}   # live Popen -> stage name
        self._clear_selected_on_ok = False   # a file/refile gesture is in flight
        self._refresh_after_error = False    # gesture failed -> one plain reload
        self._reload_pending = False         # child exited while a gate held
        self._build_widgets()
        self._build_key_table()
        self._poll = QTimer(self)
        self._poll.setInterval(2000)
        self._poll.timeout.connect(self._poll_children)
        self._poll.start()
        self.stack_opened.connect(self._on_stack_opened)
        self.data_loaded.connect(self._on_data_loaded)
        self.sess = HubShellSession(manifests_dir,
                                    graph_capability=graph_capability,
                                    actor=f"human:{getpass.getuser()}")
        self.sess.start()
        self.busy = "opening workspace graph…"
        self._paint()
        fut = self.sess.open_stack(graph_db_path)
        fut.add_done_callback(self.stack_opened.emit)

    # ---- widgets ---------------------------------------------------------

    def _build_widgets(self) -> None:
        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)
        self.header = QLabel(" WORKSPACE HUB ")
        self.header.setTextFormat(Qt.PlainText)
        self.list = QListWidget()
        self.list.setFocusPolicy(Qt.NoFocus)   # keys land in keyPressEvent
        self.list.setSelectionMode(QListWidget.SingleSelection)
        self.list.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.list.itemClicked.connect(self._on_item_clicked)
        self.editor = QLineEdit()
        self.editor.setVisible(False)
        self.editor.returnPressed.connect(self._on_editor_submitted)
        self.status = QLabel("")
        self.status.setTextFormat(Qt.PlainText)
        self.status.setWordWrap(True)
        lay.addWidget(self.header)
        lay.addWidget(self.list, 1)
        lay.addWidget(self.editor)
        lay.addWidget(self.status)
        self.setCentralWidget(central)

    # ---- painting --------------------------------------------------------

    def _paint(self) -> None:
        db = self.graph_db_path or ""
        self.header.setText(f" WORKSPACE HUB  {db}")
        self.list.setUpdatesEnabled(False)
        self.list.clear()
        if self.rows:
            for spec in panes.hub_rows(self.rows, self.selected, self.mode,
                                       self.order_coll, self.order_work):
                item = QListWidgetItem(spec["text"])
                apply_row_style(item, spec["style"])
                self.list.addItem(item)
            self.cursor = max(0, min(self.cursor, len(self.rows) - 1))
            self.list.setCurrentRow(self.cursor)
            self.list.scrollToItem(self.list.currentItem())
        else:
            placeholder = QListWidgetItem("   (no sources on the graph yet — "
                                          "1 launches the transcription app)")
            apply_row_style(placeholder, "dim")
            self.list.addItem(placeholder)
        self.list.setUpdatesEnabled(True)
        self._paint_status()

    def _paint_status(self) -> None:
        n = 0
        if self.pending_title:
            existing = self._existing_by_title(self.pending_title)
            n = len(self.data.members.get(existing, [])) if existing else 0
        self.status.setText(panes.status_text(
            error=self.error, busy=self.busy, pending_title=self.pending_title,
            pending_count=n, editing=self.editing, mode=self.mode))

    # ---- key dispatch ----------------------------------------------------

    def _build_key_table(self) -> None:
        t: Dict[str, Any] = {}
        for k in ("j", "down"):
            t[k] = lambda: self.action_move(1)
        for k in ("k", "up"):
            t[k] = lambda: self.action_move(-1)
        t["space"] = self.action_toggle_select
        t["y"] = self.action_confirm
        t["f"] = self.action_file
        t["r"] = self.action_rename
        t["g"] = self.action_order_mode
        t["J"] = lambda: self.action_order_shift(1)
        t["K"] = lambda: self.action_order_shift(-1)
        t["enter"] = self.action_commit
        t["1"] = lambda: self.action_launch("transcription")
        t["2"] = lambda: self.action_launch("decomp")
        t["3"] = lambda: self.action_launch("correction")
        t["R"] = self.action_reload
        t["escape"] = self.action_cancel
        t["q"] = self.close
        self._key_table = t

    def keyPressEvent(self, event) -> None:
        name = _KEYNAMES.get(event.key())
        if name is None:
            text = event.text()
            name = text if text and text.isprintable() and text != " " else None
        fn = self._key_table.get(name) if name else None
        if fn is None:
            super().keyPressEvent(event)
            return
        fn()

    # ---- boot + reload plumbing ------------------------------------------

    def _on_stack_opened(self, fut) -> None:
        try:
            res = fut.result()
        except Exception as e:
            self.busy = None
            self.error = str(e)
            self._paint()
            return
        self.graph_db_path = res["db"]
        self._submit_load("loading…")

    def _submit_load(self, note: str) -> None:
        self.busy = note
        self._paint()
        self.sess.load().add_done_callback(self.data_loaded.emit)

    def _submit_gesture(self, fut) -> None:
        """One curation gesture (commit + reload composed loop-side): the
        resolved HubData lands in _on_data_loaded; a failure paints and then
        refreshes once, the donor's error-then-reload contract."""
        self._refresh_after_error = True
        fut.add_done_callback(self.data_loaded.emit)

    def _on_data_loaded(self, fut) -> None:
        try:
            data = fut.result()
        except Exception as e:
            self.busy = None
            refresh = self._refresh_after_error
            self._refresh_after_error = False
            self._clear_selected_on_ok = False
            if refresh:
                self.error = str(e)
                self._submit_load("loading…")
            else:
                self.error = f"reload failed: {e} (R retries)"
                self._paint()
            return
        self._refresh_after_error = False
        self.data = data
        self.rows = build_rows(data)
        self.cursor = max(0, min(self.cursor, len(self.rows) - 1))
        self.selected &= {r["id"] for r in self.rows if r["kind"] == "source"}
        if self._clear_selected_on_ok:
            self.selected.clear()
            self._clear_selected_on_ok = False
        self.busy = None
        self._paint()

    # ---- gestures --------------------------------------------------------

    def _focused(self) -> Optional[Dict[str, Any]]:
        return self.rows[self.cursor] if self.rows else None

    def _existing_by_title(self, title: str) -> Optional[str]:
        cid = collection_node_id(title)
        return cid if any(c["id"] == cid for c in self.data.collections) else None

    def _on_item_clicked(self, item) -> None:
        if self.editing:
            return
        self.cursor = self.list.row(item)

    def action_move(self, delta: int) -> None:
        if not self.rows or self.editing:
            return
        self.cursor = max(0, min(self.cursor + delta, len(self.rows) - 1))
        self.list.setCurrentRow(self.cursor)
        self.list.scrollToItem(self.list.currentItem())

    def action_toggle_select(self) -> None:
        row = self._focused()
        if self.mode != "browse" or self.editing or not row or row["kind"] != "source":
            return
        if row["id"] in self.selected:
            self.selected.discard(row["id"])
        else:
            self.selected.add(row["id"])
        self._paint()

    def action_confirm(self) -> None:
        row = self._focused()
        if (self.mode != "browse" or self.editing or self.busy or not row
                or row["kind"] != "collection" or not row["id"]
                or row["status"] != "proposed"):
            return
        self.busy = "curating…"
        self._paint()
        self._submit_gesture(self.sess.confirm(row["id"]))

    def action_file(self) -> None:
        row = self._focused()
        if self.mode != "browse" or self.editing or self.busy or not row:
            return
        targets = self.selected or ({row["id"]} if row["kind"] == "source" else set())
        if not targets:
            self.error = "select sources (space) or focus one before f"
            self._paint()
            return
        self._open_editor("file")

    def action_rename(self) -> None:
        row = self._focused()
        if (self.mode != "browse" or self.editing or self.busy or not row
                or row["kind"] != "collection" or not row["id"]):
            return
        self._open_editor("rename", prefill=row["title"])

    def _open_editor(self, kind: str, prefill: str = "") -> None:
        self.editor.setText(prefill)
        self.editor.setVisible(True)
        self.editor.setFocus()
        self.editing = kind
        self.pending_title = None
        self.error = None
        self._paint_status()

    def _close_editor(self) -> None:
        self.editor.setVisible(False)
        self.editor.clearFocus()
        self.setFocus(Qt.OtherFocusReason)   # keys land in keyPressEvent again
        self.editing = None
        self.pending_title = None

    def _on_editor_submitted(self) -> None:
        if not self.editing:
            return
        title = self.editor.text().strip()
        if not title:
            self._close_editor()
            self._paint()
            return
        # d544e250: an existing title surfaces before it commits (two-phase)
        if self._existing_by_title(title) and self.pending_title != title:
            self.pending_title = title
            self._paint_status()
            return
        kind = self.editing
        row = self._focused()
        self._close_editor()
        self.busy = "curating…"
        self.error = None
        self._paint()
        self._clear_selected_on_ok = True   # donor: selected.clear() on success, BOTH branches
        if kind == "rename":
            self._submit_gesture(self.sess.rename(row["id"], title))
            return
        targets = self.selected or ({row["id"]} if row and row["kind"] == "source" else set())
        grouped = panes.group_targets_by_collection(self.rows, targets)
        self._submit_gesture(self.sess.file_targets(grouped, title))

    def action_order_mode(self) -> None:
        row = self._focused()
        if (self.mode != "browse" or self.editing or self.busy or not row
                or row["kind"] != "collection" or not row["id"]):
            return
        members = [r["id"] for r in self.rows
                   if r["kind"] == "source" and r.get("coll_id") == row["id"]]
        if len(members) < 2:
            self.error = "order mode needs at least two members"
            self._paint()
            return
        self.mode = "order"
        self.order_coll = row["id"]
        self.order_work = members
        self._paint()

    def action_order_shift(self, delta: int) -> None:
        row = self._focused()
        if (self.mode != "order" or not row or row["kind"] != "source"
                or row.get("coll_id") != self.order_coll):
            return
        i = self.order_work.index(row["id"])
        j = i + delta
        if not (0 <= j < len(self.order_work)):
            return
        self.order_work[i], self.order_work[j] = self.order_work[j], self.order_work[i]
        self._paint()

    def action_commit(self) -> None:
        if self.mode != "order" or self.busy:
            return
        coll, order = self.order_coll, list(self.order_work)
        self.mode, self.order_coll, self.order_work = "browse", None, []
        self.busy = "ordering…"
        self._paint()
        self._submit_gesture(self.sess.set_order(coll, order))

    def action_launch(self, which: str) -> None:
        """Spawn a stage app (1/2/3) — resolved across the core envs, then
        Popen-detached: the hub stays interactive and the child outlives it;
        the poll timer reloads when it exits (spawn-not-suspend, 61b46ae8)."""
        row = self._focused()
        if self.mode != "browse" or self.editing or self.busy:
            return
        exe = resolve_stage_app(which)
        if exe is None:
            cmd, env_name = STAGE_APPS[which]
            self.error = (f"{cmd} not found on PATH or in the {env_name} env "
                          f"(pip install it there; see resolve_stage_app)")
            self._paint()
            return
        source_id = None
        if which == "correction":
            if not row or row["kind"] != "source":
                self.error = "focus a source row to open it in the correction app"
                self._paint()
                return
            source_id = row["id"]
        try:
            proc = spawn_stage(build_stage_cmd(exe, which, self.graph_db_path,
                                               source_id))
        except BaseException as e:
            # The donor's hardened launch contract (the 2026-07-22 wedge):
            # NOTHING about a failed launch may escape unpainted — here that
            # means a Popen raise (exec-format, non-executable resolve, fork
            # failure) paints instead of escaping keyPressEvent.
            self.error = f"launch failed: {e}"
            self._paint()
            return
        self.children[proc] = which
        self._paint()
        if not self.error:   # donor fidelity: launching never clears a sticky error
            self.status.setText(f" launched {which} (pid {proc.pid}) ")

    def _poll_children(self) -> None:
        """The reload-on-resume replacement: when a spawned stage app exits,
        reload the hub (its session likely changed the graph). Reloads defer
        while a gate holds (editing / order mode / busy) and fire on the next
        quiet poll."""
        exited = [p for p in self.children if p.poll() is not None]
        for proc in exited:
            which = self.children.pop(proc)
            if proc.returncode:
                self.error = f"{which} app exited with rc={proc.returncode}"
            self._reload_pending = True
        if (self._reload_pending and self.mode == "browse"
                and not self.editing and not self.busy):
            self._reload_pending = False
            self._submit_load("loading…")

    def action_cancel(self) -> None:
        if self.editing:
            self._close_editor()
        elif self.mode == "order":
            self.mode, self.order_coll, self.order_work = "browse", None, []
        self.error = None
        self._paint()

    def action_reload(self) -> None:
        if self.mode == "browse" and not self.editing and not self.busy:
            self._submit_load("loading…")

    def closeEvent(self, event) -> None:
        """Quit = teardown (queue stop + capability unload on the loop, then
        the loop itself); spawned stage apps live on — they are processes,
        not children of the window."""
        self._poll.stop()
        self.sess.close()
        super().closeEvent(event)
