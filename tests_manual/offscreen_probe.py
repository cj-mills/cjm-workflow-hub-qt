"""Offscreen paint probe: stand the hub window up over a stubbed graph stack
(no capability loads) and walk every gesture — boot ladder, browse paint,
select, confirm, the two-phase file/refile editor, order mode, spawn +
child-exit reload — the paint-path verification layer pytest cannot give
(67335f7d), Qt edition. Run from a NEUTRAL cwd:

    QT_QPA_PLATFORM=offscreen python offscreen_probe.py
"""

import os
import sys
import time
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from cjm_transcript_graph_schema.schema import collection_node_id  # noqa: E402
from cjm_workflow_hub_tui.spine import HubData  # noqa: E402

import cjm_workflow_hub_qt.app as app_mod  # noqa: E402
import cjm_workflow_hub_qt.session as sess_mod  # noqa: E402
from cjm_workflow_hub_qt.session import HubShellSession  # noqa: E402

C1 = collection_node_id("Alpha")
CALLS = []


class FakeQueue:
    async def stop(self):
        pass


def make_data():
    data = HubData()
    data.collections = [{"id": C1, "title": "Alpha", "status": "proposed"}]
    data.members = {C1: [("s1", "one"), ("s2", "two")]}
    data.order = {C1: ["s1"]}
    data.sources = [("s1", "one"), ("s2", "two"), ("s3", "loose")]
    data.status = {"s1": {"transcripts": 1, "fine_segs": 3}}
    return data


def install_stubs():
    async def stack_opener(path, *, manifests_dir, graph_capability):
        return SimpleNamespace(unload_capability=lambda name: None), \
            FakeQueue(), "/tmp/probe-graph.db"

    async def loader(queue, graph_id):
        CALLS.append(("load",))
        return make_data()

    class ProbeSession(HubShellSession):
        def __init__(self, manifests_dir, **kw):
            kw.pop("stack_opener", None)
            kw.pop("loader", None)
            super().__init__(manifests_dir, stack_opener=stack_opener,
                             loader=loader, **kw)

    async def fake_confirm(queue, graph_id, coll_id, actor, *, journal_path):
        CALLS.append(("confirm", coll_id, actor))

    async def fake_rename(queue, graph_id, coll_id, title, actor, *,
                          journal_path):
        CALLS.append(("rename", coll_id, title))

    async def fake_file(queue, graph_id, title, ids, actor, *, journal_path):
        CALLS.append(("file", title, tuple(ids)))

    async def fake_refile(queue, graph_id, ids, from_coll, title, actor, *,
                          journal_path):
        CALLS.append(("refile", tuple(ids), from_coll, title))

    async def fake_order(queue, graph_id, coll_id, order, actor, *,
                         journal_path):
        CALLS.append(("order", coll_id, tuple(order)))

    app_mod.HubShellSession = ProbeSession
    sess_mod.confirm_collection = fake_confirm
    sess_mod.rename_collection = fake_rename
    sess_mod.file_sources = fake_file
    sess_mod.refile_members = fake_refile
    sess_mod.set_collection_order = fake_order


class FakeProc:
    def __init__(self):
        self.pid = 4242
        self.rc = None
        self.returncode = None

    def poll(self):
        self.returncode = self.rc
        return self.rc


def pump(app, cond, what, timeout=8.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        app.processEvents()
        if cond():
            return
        time.sleep(0.01)
    raise AssertionError(f"timed out waiting for {what}")


def list_text(win):
    return "\n".join(win.list.item(i).text() for i in range(win.list.count()))


def main() -> int:
    install_stubs()
    app = QApplication(sys.argv[:1])
    win = app_mod.HubWindow("/tmp/probe-manifests")
    win.show()

    # boot ladder -> grouped rows painted, legend status, db in the header
    pump(app, lambda: win.rows, "the grouped rows")
    assert "/tmp/probe-graph.db" in win.header.text()
    assert "Alpha ⚑ proposed  (2)" in list_text(win)
    assert "TDc 3segs" in list_text(win)
    assert "Unfiled" in list_text(win)
    assert "space select" in win.status.text()

    # cursor walk + select toggle paints the pick box
    win.action_move(1)                 # onto s1 ("one")
    win.action_toggle_select()
    assert "[x]   one" in list_text(win)
    assert win.selected == {"s1"}
    win.action_toggle_select()
    assert win.selected == set()

    # y on the ⚑ collection -> confirm rides the REAL loop thread
    win.action_move(-1)                # back to the Alpha header
    win.action_confirm()
    pump(app, lambda: not win.busy, "the confirm gesture")
    assert ("confirm", C1, win.sess.actor) in CALLS

    # f files the focused source under a NEW title (editor round-trip)
    win.action_move(2)                 # onto s2 ("two")
    win.action_file()
    assert win.editing == "file" and win.editor.isVisible()
    win.editor.setText("Brand New")
    win._on_editor_submitted()
    pump(app, lambda: not win.busy, "the file gesture")
    assert ("refile", ("s2",), C1, "Brand New") in CALLS

    # f with an EXISTING title takes the two-phase confirm (d544e250)
    win.cursor = 4                     # the unfiled source ("loose")
    win.action_file()
    win.editor.setText("Alpha")
    win._on_editor_submitted()
    assert win.pending_title == "Alpha"
    assert "EXISTING collection (2 members)" in win.status.text()
    win._on_editor_submitted()         # the second enter commits
    pump(app, lambda: not win.busy, "the refile-into-existing gesture")
    assert ("file", "Alpha", ("s3",)) in CALLS

    # g order mode on Alpha: J moves the member down, enter commits the chain
    win.cursor = 0
    win.action_order_mode()
    assert win.mode == "order" and win.order_work == ["s1", "s2"]
    assert "ORDER MODE" in win.status.text()
    win.action_move(1)                 # onto the first member
    win.action_order_shift(1)
    assert win.order_work == ["s2", "s1"]
    win.action_commit()
    pump(app, lambda: win.mode == "browse" and not win.busy, "the order commit")
    assert ("order", C1, ("s2", "s1")) in CALLS

    # r renames the collection (merge-by-title vocabulary)
    win.cursor = 0
    win.action_rename()
    assert win.editor.text() == "Alpha"
    win.editor.setText("Omega")
    win._on_editor_submitted()
    pump(app, lambda: not win.busy, "the rename gesture")
    assert ("rename", C1, "Omega") in CALLS

    # spawn: unresolvable stage app -> loud error NAMING the env, no spawn
    app_mod.resolve_stage_app = lambda which: None
    win.action_launch("decomp")
    assert "cjm-transcript-decomp-core" in win.status.text()
    win.action_cancel()

    # spawn: resolved -> detached child tracked; its exit triggers a reload
    proc = FakeProc()
    app_mod.resolve_stage_app = lambda which: "/fake/bin/cjm-transcript-correction-qt"
    app_mod.spawn_stage = lambda cmd: (CALLS.append(("spawn", tuple(cmd))), proc)[1]
    win.cursor = 1                     # correction opens ON a source
    win.action_launch("correction")
    assert win.children == {proc: "correction"}
    assert "launched correction" in win.status.text()
    assert ("spawn", ("/fake/bin/cjm-transcript-correction-qt",
                      "--graph-db-path", "/tmp/probe-graph.db",
                      "--source", "s1")) in CALLS
    loads_before = CALLS.count(("load",))
    proc.rc = 0
    win._poll_children()
    pump(app, lambda: CALLS.count(("load",)) > loads_before and not win.busy,
         "the child-exit reload")
    assert win.children == {}

    win.close()
    app.processEvents()
    print("offscreen probe: all assertions passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
