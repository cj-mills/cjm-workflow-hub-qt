"""Stage-app launch: resolve across core envs, spawn detached (DEC 61b46ae8).

The one place the port's mechanics necessarily differ from the donor
(amendment 2030586d): the Textual hub SUSPENDED into a stage TUI and blocked
until it exited; the Qt hub SPAWNS the stage app as a detached process and
stays interactive — the child outlives the hub, and the shell's poll timer
reloads when one exits (the donor's reload-on-resume semantics).

Resolution carries the resolve_stage_tui core-env ladder verbatim (env-truth
register: each stage app's console script lives only in its own core's conda
env; env name = core repo name) with the QT console-script map — the hub now
fronts the Qt lane. PATH first (an env that installs everything wins), then
the sibling env's bin with the envs root derived from the hub's own
interpreter (sys.prefix's parent — never a hardcoded dev-machine path,
6dfe00e9 discipline). None = the caller paints a loud error NAMING the
missing env, and never spawns."""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

STAGE_APPS = {
    "transcription": ("cjm-transcription-qt", "cjm-transcription-core"),
    "decomp": ("cjm-transcript-decomp-qt", "cjm-transcript-decomp-core"),
    "correction": ("cjm-transcript-correction-qt", "cjm-transcript-correction-core"),
}


def resolve_stage_app(
    which: str,                        # "transcription" | "decomp" | "correction"
    envs_root: Optional[str] = None,   # Conda envs dir override (tests; None = derive)
) -> Optional[str]:  # Absolute executable path, or None = not installed anywhere we know
    """Resolve a stage app's console script across the core-env pattern."""
    cmd, env_name = STAGE_APPS[which]
    found = shutil.which(cmd)
    if found:
        return found
    root = Path(envs_root) if envs_root else Path(sys.prefix).parent
    cand = root / env_name / "bin" / cmd
    return str(cand) if cand.exists() else None


def build_stage_cmd(
    exe: str,                          # Resolved stage-app executable
    which: str,                        # Stage name (correction gets --source)
    graph_db_path: Optional[str],      # The hub's effective db (None = workspace answers)
    source_id: Optional[str] = None,   # Focused source (required for correction)
) -> List[str]:  # The spawn argv
    """The donor's launch argv, verbatim: the explicit-db-path guardrail
    (027bbe56 — every launched stage app opens the SAME graph the hub shows,
    never a convenience re-resolve), and correction opens ON a source."""
    cmd = [exe]
    if graph_db_path:
        cmd += ["--graph-db-path", str(graph_db_path)]
    if which == "correction":
        cmd += ["--source", str(source_id)]
    return cmd


def spawn_stage(cmd: List[str]) -> subprocess.Popen:
    """Spawn one stage app, detached: its own session (no signal coupling to
    the hub's terminal), and it survives a hub quit — Popen, not QProcess,
    whose destructor kills a still-running child."""
    return subprocess.Popen(cmd, start_new_session=True)
