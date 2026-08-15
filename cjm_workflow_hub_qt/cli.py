"""Console-script driver for the Qt hub: the SAME argument surface and
resolution ladder as cjm-workflow-hub — build_parser and resolve_settings
imported from it (the correction-leg pattern, DEC 61b46ae8), so the two
front doors cannot drift on which stack the hub opens. CJM_WORKSPACE is
exported inside resolve_settings, so the graph capability AND every spawned
stage app resolve workspace-scoped paths. Only the window in the middle
differs; the hub never needs sources/paths on its argv."""

import sys

from cjm_workflow_hub_tui.cli import build_parser, resolve_settings
from PySide6.QtWidgets import QApplication

from .app import HubWindow


def main() -> int:  # Console-script entry point (cjm-workflow-hub-qt)
    """Resolve the shared launch surface, run the Qt hub window."""
    parser = build_parser()
    parser.prog = "cjm-workflow-hub-qt"
    args = parser.parse_args()
    s = resolve_settings(args)
    qapp = QApplication(sys.argv[:1])
    win = HubWindow(s["manifests_dir"], graph_db_path=args.graph_db_path,
                    graph_capability=args.graph_capability)
    win.show()
    qapp.exec()
    return 0
