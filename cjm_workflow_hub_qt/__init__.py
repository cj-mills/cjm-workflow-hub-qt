"""Qt front door for cjm-substrate workflows — a DIRECT PORT IN SPIRIT of
cjm-workflow-hub-tui's grouped browse + curation surface onto PySide6 (DEC
61b46ae8, the c4b0d6e5 lane's last migration): the same collection-grouped
rows with stage-at-a-glance pipeline status, the same curation vocabulary
(confirm / file / refile / rename-or-merge / order), whose pure spine it
imports verbatim; the graph stack + JobQueue live behind a private asyncio
loop thread. The hub is a launcher, so where the Textual donor suspended into
the stage TUIs, this window SPAWNS the Qt stage apps as detached processes
resolved across their core envs — the one place the mechanics necessarily
differ (amendment 2030586d). Born on-graph."""

__version__ = "0.0.3"
