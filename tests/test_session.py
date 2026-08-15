"""HubShellSession contract tests — headless (the seam is Qt-free): the open
ladder, the SystemExit conversion, gesture serialization, and each curation
verb's commit-then-reload composition."""

import asyncio

import pytest

import cjm_workflow_hub_qt.session as session_mod
from cjm_workflow_hub_qt.session import HubShellSession


class FakeQueue:
    def __init__(self):
        self.stopped = False

    async def stop(self):
        self.stopped = True


class FakeManager:
    def __init__(self):
        self.unloaded = []

    def unload_capability(self, name):
        self.unloaded.append(name)


def make_session(calls, loaded="DATA", **kw):
    async def opener(db, *, manifests_dir, graph_capability):
        calls.append(("open", db, manifests_dir, graph_capability))
        return FakeManager(), FakeQueue(), db or "/resolved/g.db"

    async def loader(queue, graph_id):
        calls.append(("load", graph_id))
        return loaded

    s = HubShellSession(".cjm/manifests", actor="human:test",
                        stack_opener=opener, loader=loader, timeout=10.0, **kw)
    s.start()
    return s


def test_open_ladder_resolves_db_and_journal():
    calls = []
    s = make_session(calls)
    try:
        res = s.open_stack("/tmp/explicit.db").result(10)
        assert res == {"db": "/tmp/explicit.db"}
        assert s.db == "/tmp/explicit.db"
        assert s.journal_path       # sidecar derived from the effective db
        assert calls[0] == ("open", "/tmp/explicit.db", ".cjm/manifests",
                            "cjm-capability-graph-sqlite")
    finally:
        s.close()


def test_library_exit_resolves_as_runtime_error_never_kills_the_loop():
    async def exiting(db, *, manifests_dir, graph_capability):
        raise SystemExit("no such capability")

    s = HubShellSession(".cjm/manifests", stack_opener=exiting, timeout=10.0)
    s.start()
    try:
        with pytest.raises(RuntimeError, match="no such capability"):
            s.open_stack(None).result(10)
        assert s.running   # the loop survived the library exit
    finally:
        s.close()


def test_run_serial_runs_gestures_to_completion_in_submission_order():
    calls = []
    s = make_session(calls)
    order = []

    async def slow():
        order.append("slow-start")
        await asyncio.sleep(0.05)
        order.append("slow-end")

    async def fast():
        order.append("fast")

    try:
        f1 = s.run_serial(slow())
        f2 = s.run_serial(fast())
        f2.result(10)
        f1.result(10)
        assert order == ["slow-start", "slow-end", "fast"]
    finally:
        s.close()


def test_confirm_composes_commit_then_reload(monkeypatch):
    calls = []
    s = make_session(calls)

    async def fake_confirm(queue, graph_id, coll_id, actor, *, journal_path):
        calls.append(("confirm", coll_id, actor, journal_path))

    monkeypatch.setattr(session_mod, "confirm_collection", fake_confirm)
    try:
        s.open_stack("/tmp/g.db").result(10)
        assert s.confirm("coll-1").result(10) == "DATA"
        assert calls[-2] == ("confirm", "coll-1", "human:test", s.journal_path)
        assert calls[-1] == ("load", "cjm-capability-graph-sqlite")
    finally:
        s.close()


def test_file_targets_routes_refile_vs_file_per_group(monkeypatch):
    calls = []
    s = make_session(calls)

    async def fake_refile(queue, graph_id, ids, from_coll, title, actor, *,
                          journal_path):
        calls.append(("refile", tuple(ids), from_coll, title))

    async def fake_file(queue, graph_id, title, ids, actor, *, journal_path):
        calls.append(("file", tuple(ids), title))

    monkeypatch.setattr(session_mod, "refile_members", fake_refile)
    monkeypatch.setattr(session_mod, "file_sources", fake_file)
    try:
        s.open_stack("/tmp/g.db").result(10)
        grouped = {"c1": ["s1", "s2"], None: ["s3"]}
        assert s.file_targets(grouped, "New Title").result(10) == "DATA"
        assert ("refile", ("s1", "s2"), "c1", "New Title") in calls
        assert ("file", ("s3",), "New Title") in calls
        assert calls[-1][0] == "load"
    finally:
        s.close()


def test_rename_and_set_order_compose_commit_then_reload(monkeypatch):
    calls = []
    s = make_session(calls)

    async def fake_rename(queue, graph_id, coll_id, title, actor, *,
                          journal_path):
        calls.append(("rename", coll_id, title))

    async def fake_order(queue, graph_id, coll_id, order, actor, *,
                         journal_path):
        calls.append(("order", coll_id, tuple(order)))

    monkeypatch.setattr(session_mod, "rename_collection", fake_rename)
    monkeypatch.setattr(session_mod, "set_collection_order", fake_order)
    try:
        s.open_stack("/tmp/g.db").result(10)
        assert s.rename("c1", "Better").result(10) == "DATA"
        assert ("rename", "c1", "Better") in calls
        assert s.set_order("c1", ["s2", "s1"]).result(10) == "DATA"
        assert ("order", "c1", ("s2", "s1")) in calls
    finally:
        s.close()


def test_close_stops_queue_and_unloads_capability():
    calls = []
    s = make_session(calls)
    s.open_stack("/tmp/g.db").result(10)
    queue, manager = s.queue, s.manager
    s.close()
    assert queue.stopped
    assert manager.unloaded == ["cjm-capability-graph-sqlite"]
    assert not s.running
