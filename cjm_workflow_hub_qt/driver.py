"""The hub's shared launch surface: the argument surface (build_parser) and
the resolution ladder (resolve_settings). Toolkit-neutral by construction —
no Qt imports (spine absorption 12f342f1, rider 2: core-shaped seams so a
future non-Qt front end lifts it with the spine). Absorbed from the Textual
hub's cli as a frozen copy-split (the correction-leg pattern, DEC 61b46ae8):
CJM_WORKSPACE is exported inside resolve_settings, so the graph capability
AND every spawned stage app resolve workspace-scoped paths."""

import argparse
import os

from cjm_substrate.core.workspace import resolve_workspace


def build_parser() -> argparse.ArgumentParser:  # Configured CLI parser
    """The hub driver's argument surface (everything else the workspace answers)."""
    p = argparse.ArgumentParser(
        prog="cjm-workflow-hub-qt",
        description="Workspace front door for the transcription workflow: "
                    "collection-grouped sources with stage-at-a-glance pipeline "
                    "status, launch into the stage apps, and the collection "
                    "curation surface (confirm/rename/refile/order/merge).")
    p.add_argument("--workspace", default=None,
                   help="Workspace root (5daadfc4; default: CJM_WORKSPACE env, else "
                        "upward walk from cwd). Exported so the graph capability and "
                        "every launched stage app resolve workspace-scoped paths")
    p.add_argument("--manifests-dir", default=None,
                   help="Capability manifests directory (default: the workspace's "
                        ".cjm/manifests when one is active, else .cjm/manifests under the cwd)")
    p.add_argument("--graph-db-path", default=None,
                   help="Explicit graph db (default: the graph capability's persisted "
                        "workspace-scoped config; none anywhere = loud refusal)")
    p.add_argument("--graph-capability", default="cjm-capability-graph-sqlite",
                   help="Graph-storage capability name")
    return p


def resolve_settings(args) -> dict:  # {"manifests_dir"} — the resolved launch surface
    """Resolve + export the workspace and default the manifests dir.

    The one launch ladder every hub shell shares (the correction-leg pattern)
    so front doors cannot drift on which stack the hub opens: CJM_WORKSPACE is
    exported here so the graph capability AND every spawned/launched stage app
    resolve workspace-scoped paths."""
    ws = resolve_workspace(explicit=args.workspace)
    if ws is not None:
        os.environ["CJM_WORKSPACE"] = str(ws.root)
    manifests_dir = args.manifests_dir or (
        str(ws.substrate_data_dir / "manifests") if ws is not None else ".cjm/manifests")
    return {"manifests_dir": manifests_dir}
