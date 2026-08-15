# cjm-workflow-hub-qt

<!-- generated from the context graph by `cjm-context-graph readme` — do not edit by hand; edit the graph (the urge to hand-edit = move it on-graph) -->

Qt front door for cjm-substrate workflows — the last migration on the PySide6 lane (DEC 61b46ae8, per amendment 2030586d: a direct port IN SPIRIT). The same collection-grouped source browse with stage-at-a-glance pipeline status and the same curation vocabulary (confirm / file / refile / rename-or-merge / order) as cjm-workflow-hub-tui, whose pure spine and CLI ladder it imports verbatim; the graph stack + JobQueue run behind a private asyncio loop thread with a gesture lock serializing each commit-then-reload. The hub is a launcher, so where the Textual donor suspended into the stage TUIs, this window SPAWNS the Qt stage apps as detached processes resolved across their core envs (PATH first, then the sibling env's bin) — children outlive the hub, and a 2s poll reloads the browse when one exits.

## Modules

- **`cjm_workflow_hub_qt`** — Qt front door for cjm-substrate workflows — a DIRECT PORT IN SPIRIT of
- **`cjm_workflow_hub_qt.app`** — The Qt hub shell: the workspace front door under PySide6 (DEC 61b46ae8, a
- **`cjm_workflow_hub_qt.cli`** — Console-script driver for the Qt hub: the SAME argument surface and
- **`cjm_workflow_hub_qt.launch`** — Stage-app launch: resolve across core envs, spawn detached (DEC 61b46ae8).
- **`cjm_workflow_hub_qt.panes`** — Pure row/label builders for the Qt hub shell — the paint logic, Qt-free.
- **`cjm_workflow_hub_qt.session`** — The hub shell's jobs seam: graph stack + JobQueue behind a private asyncio

## API

### `cjm_workflow_hub_qt.app`

- `HubWindow` _class_ — The hub surface under Qt — grouped browse + curation + stage spawn.

### `cjm_workflow_hub_qt.cli`

- `main` _function_ — Resolve the shared launch surface, run the Qt hub window.

### `cjm_workflow_hub_qt.launch`

- `build_stage_cmd` _function_ — The donor's launch argv, verbatim: the explicit-db-path guardrail
- `resolve_stage_app` _function_ — Resolve a stage app's console script across the core-env pattern.
- `spawn_stage` _function_ — Spawn one stage app, detached: its own session (no signal coupling to

### `cjm_workflow_hub_qt.panes`

- `group_targets_by_collection` _function_ — Group the filed sources by the collection they LEAVE, so each move is
- `hub_rows` _function_ — One list row per spine row — the donor's _paint_row, single-style.
- `status_text` _function_ — The donor's status ladder, verbatim precedence: error > busy > the

### `cjm_workflow_hub_qt.session`

- `HubShellSession` _class_ — The loop-thread seat for the hub shell.

## Dependencies

**Depends on:** `PySide6`, `cjm-context-graph-layer`, `cjm-substrate`, `cjm-substrate-qt-kit`, `cjm-transcription-core`, `cjm-workflow-hub-tui`
