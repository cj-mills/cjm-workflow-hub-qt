"""The hub shell's jobs seam: graph stack + JobQueue behind a private asyncio
loop thread (DEC 61b46ae8 — the CorrectionShellSession recipe with the hub's
curation verbs).

The Textual hub opened the stack INSIDE the app "so the JobQueue lives on
Textual's event loop"; under Qt that loop is this session's daemon thread.
open_stack() bootstraps the capability stack and resolves the effective db
(2ce81638 resolution: explicit path wins, else the workspace-scoped persisted
config answers); every curation GESTURE composes the core commit call(s) with
a fresh load_hub_data into ONE coroutine submitted through run_serial — the
donor committed then reloaded inside one Textual action handler, and the
gesture lock restores exactly that run-to-completion semantics, so the HubData
a gesture resolves to always reflects its own commit. Deliberately Qt-free
(stdlib + spine imports only): testable headless, openers injectable."""

import asyncio
from concurrent.futures import Future
from typing import Any, Callable, Dict, List, Optional

from cjm_context_graph_layer.journal import sidecar_journal_path
from cjm_substrate_qt_kit.loopthread import LoopThreadSession
from cjm_transcription_core.curation import (confirm_collection, file_sources, refile_members,
                                             rename_collection, set_collection_order)
from cjm_workflow_hub_tui.spine import HubData, load_hub_data, open_stack


class HubShellSession(LoopThreadSession):
    """The loop-thread seat for the hub shell.

    start() spins the loop (kit LoopThreadSession); open_stack() bootstraps
    the graph capability + JobQueue, resolves the effective db, and derives
    the sidecar journal path every curation commit rides (ccbab9f5); load()
    and the curation verbs each resolve to a fresh HubData. close() runs
    on_close() on the loop (queue stop + capability unload — the donor's
    _teardown), then stops the thread. One instance per window."""

    thread_name = "hub-session"

    def __init__(self, manifests_dir: str,   # Capability manifests directory
                 *, graph_capability: str = "cjm-capability-graph-sqlite",
                 actor: str = "human",       # Curation actor stamped on every commit
                 timeout: float = 600.0,     # graph worker may cold-start
                 stack_opener: Callable[..., Any] = open_stack,
                 loader: Callable[..., Any] = load_hub_data):
        super().__init__(timeout=timeout)
        self.manifests_dir = manifests_dir
        self.graph_capability = graph_capability
        self.actor = actor
        self._stack_opener = stack_opener
        self._loader = loader
        self.manager: Optional[Any] = None   # the open stack (loop-owned)
        self.queue: Optional[Any] = None
        self.db: Optional[str] = None        # effective graph db path
        self.journal_path: Optional[str] = None
        self._gesture_lock: Optional[asyncio.Lock] = None  # minted on the loop

    # ---- gesture serialization ------------------------------------------

    def run_serial(self, coro) -> Future:
        """Submit one GESTURE coroutine, serialized to completion before the
        next runs. Bare submit() interleaves at await points (asyncio tasks),
        but the donor's Textual message queue ran each action handler to
        completion before dispatching the next key — the commit-then-reload
        consistency every gesture assumes. The lock restores exactly that."""
        return self.submit(self._serial(coro))

    async def _serial(self, coro):
        if self._gesture_lock is None:
            self._gesture_lock = asyncio.Lock()
        async with self._gesture_lock:
            return await coro

    # ---- the open ladder -------------------------------------------------

    def open_stack(self, graph_db_path: Optional[str]) -> Future:
        """Bootstrap the graph capability stack + JobQueue (2ce81638 db
        resolution). Resolves to {"db": effective_path}."""
        return self.submit(self._open_stack(graph_db_path))

    async def _open_stack(self, graph_db_path):
        try:
            self.manager, self.queue, db = await self._stack_opener(
                graph_db_path, manifests_dir=self.manifests_dir,
                graph_capability=self.graph_capability)
        except SystemExit as e:
            # load_capabilities exits on a missing capability, and a library
            # exit must resolve the Future, never kill the loop thread.
            raise RuntimeError(str(e) or "capability load failed") from e
        self.db = str(db)
        self.journal_path = sidecar_journal_path(self.db)
        return {"db": self.db}

    # ---- reload + the curation gestures ----------------------------------

    def load(self) -> Future:
        """One full hub reload off the graph — resolves to HubData."""
        return self.run_serial(self._load())

    async def _load(self) -> HubData:
        return await self._loader(self.queue, self.graph_capability)

    def confirm(self, coll_id: str) -> Future:
        """Confirm a ⚑-proposed collection, then reload (one gesture)."""
        return self.run_serial(self._confirm(coll_id))

    async def _confirm(self, coll_id):
        await confirm_collection(self.queue, self.graph_capability, coll_id,
                                 self.actor, journal_path=self.journal_path)
        return await self._load()

    def rename(self, coll_id: str, title: str) -> Future:
        """Rename a collection (merge when the title already exists), then
        reload (one gesture)."""
        return self.run_serial(self._rename(coll_id, title))

    async def _rename(self, coll_id, title):
        await rename_collection(self.queue, self.graph_capability, coll_id,
                                title, self.actor,
                                journal_path=self.journal_path)
        return await self._load()

    def file_targets(self, grouped: Dict[Optional[str], List[str]],
                     title: str) -> Future:
        """File/refile the picked sources into `title`, grouped by the
        collection they leave so each move is one journaled op (the donor's
        _commit_file contract; grouping = panes.group_targets_by_collection),
        then reload (one gesture)."""
        return self.run_serial(self._file_targets(grouped, title))

    async def _file_targets(self, grouped, title):
        for coll_id, ids in grouped.items():
            if coll_id:
                await refile_members(self.queue, self.graph_capability, ids,
                                     coll_id, title, self.actor,
                                     journal_path=self.journal_path)
            else:
                await file_sources(self.queue, self.graph_capability, title,
                                   ids, self.actor,
                                   journal_path=self.journal_path)
        return await self._load()

    def set_order(self, coll_id: str, order: List[str]) -> Future:
        """Commit an order-mode chain for one collection, then reload (one
        gesture)."""
        return self.run_serial(self._set_order(coll_id, order))

    async def _set_order(self, coll_id, order):
        await set_collection_order(self.queue, self.graph_capability, coll_id,
                                   order, self.actor,
                                   journal_path=self.journal_path)
        return await self._load()

    # ---- teardown --------------------------------------------------------

    async def on_close(self) -> None:
        """Kit close() hook: the donor's _teardown verbatim — stop the queue,
        unload the graph capability; failures never block exit."""
        if self.queue is not None:
            try:
                await self.queue.stop()
            except Exception:
                pass
        if self.manager is not None:
            try:
                self.manager.unload_capability(self.graph_capability)
            except Exception:
                pass
        self.queue = None
        self.manager = None
