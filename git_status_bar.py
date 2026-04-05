#!/usr/bin/env python3
"""
iTerm2 Status Bar: Git Status
==============================
Shows current git branch + change count in the status bar of every session.
Click the component to open a popover with the full list of changed files
grouped by status (Staged, Modified, Deleted, Untracked).

Auto-refresh:
- Instantly on every `cd` (via iterm2.Reference("path?") — requires Shell Integration)
- Every 5 seconds to catch git commit/checkout/stash (polling via user variable)

Requirements:
- iTerm2 3.3+ with Python API enabled
- Shell Integration installed
- Python 3.8+
- No external dependencies (only stdlib + iterm2)
"""

import asyncio
import html
import subprocess
from typing import Dict, List, Optional, Tuple

import iterm2

# ---------------------------------------------------------------------------
# Popover CSS — dark theme matching iTerm2
# ---------------------------------------------------------------------------

POPOVER_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: #1e1e1e;
  color: #d4d4d4;
  font-family: -apple-system, "Menlo", monospace;
  font-size: 12px;
  padding: 10px;
  line-height: 1.6;
}
.header {
  color: #9cdcfe;
  font-weight: 700;
  font-size: 12px;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #333;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.section { margin-bottom: 10px; }
.section-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 2px 5px;
  border-radius: 3px;
  margin-bottom: 4px;
  display: inline-block;
}
.staged    .section-label { color: #6a9955; background: #162016; }
.modified  .section-label { color: #ce9178; background: #2d2016; }
.deleted   .section-label { color: #f44747; background: #2d1616; }
.untracked .section-label { color: #808080; background: #252525; }
.other     .section-label { color: #dcdcaa; background: #252520; }
.file {
  padding: 1px 5px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 11px;
}
.clean { color: #6a9955; font-style: italic; padding: 4px 0; }
.no-repo { color: #808080; font-style: italic; padding: 4px 0; }
"""

# ---------------------------------------------------------------------------
# Git helpers — synchronous (called via run_in_executor)
# ---------------------------------------------------------------------------

def _run_git(args: List[str], cwd: str) -> Optional[str]:
    try:
        r = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=3,
        )
        return r.stdout if r.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _parse_porcelain(output: str) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    for line in output.splitlines():
        if len(line) < 3:
            continue
        xy, filepath = line[:2], line[3:]
        if xy == "??":
            bucket = "?"
        elif xy[0] == "R":
            bucket = "A"
            if " -> " in filepath:
                filepath = filepath.split(" -> ")[0]
        elif xy[0] not in (" ", "?"):
            bucket = xy[0]
        else:
            bucket = xy[1]
        groups.setdefault(bucket, []).append(filepath)
    return groups


def _git_info(path: str) -> Tuple[Optional[str], Optional[Dict[str, List[str]]]]:
    """Returns (branch, groups) or (None, None) if not a git repo."""
    branch_out = _run_git(["branch", "--show-current"], path)
    if branch_out is None:
        return None, None
    branch = branch_out.strip() or "HEAD detached"
    porcelain = _run_git(["status", "--porcelain"], path)
    if porcelain is None:
        return branch, {}
    return branch, _parse_porcelain(porcelain)


def _summary_text(path: str) -> str:
    """Compact text for the status bar."""
    branch, groups = _git_info(path)
    if branch is None:
        return ""
    total = sum(len(v) for v in groups.values())
    if total == 0:
        return f"\u239b {branch} \u2713"
    return f"\u239b {branch}* {total} file{'s' if total != 1 else ''}"


def _popover_html(path: str) -> str:
    """Full HTML for the click popover."""
    branch, groups = _git_info(path)
    safe_path = html.escape(path)

    if branch is None:
        return (f"<html><head><style>{POPOVER_CSS}</style></head><body>"
                f"<div class='header'>{safe_path}</div>"
                f"<div class='no-repo'>Not a git repository</div>"
                f"</body></html>")

    safe_branch = html.escape(branch)
    total = sum(len(v) for v in groups.values())
    header = f"\u239b {safe_branch}"
    if total > 0:
        header += f" &mdash; {total} change{'s' if total != 1 else ''}"

    canonical = [
        ("staged",    "A", "Staged"),
        ("modified",  "M", "Modified"),
        ("deleted",   "D", "Deleted"),
        ("untracked", "?", "Untracked"),
    ]
    sections = []
    seen = set()
    for css_class, key, label in canonical:
        files = groups.get(key, [])
        if not files:
            continue
        seen.add(key)
        rows = "".join(
            f'<div class="file" title="{html.escape(f)}">{html.escape(f)}</div>'
            for f in files
        )
        sections.append(
            f'<div class="section {css_class}">'
            f'<div class="section-label">{label} ({len(files)})</div>'
            f'{rows}</div>'
        )
    for key, files in groups.items():
        if key in seen or not files:
            continue
        rows = "".join(
            f'<div class="file" title="{html.escape(f)}">{html.escape(f)}</div>'
            for f in files
        )
        sections.append(
            f'<div class="section other">'
            f'<div class="section-label">{html.escape(key)} ({len(files)})</div>'
            f'{rows}</div>'
        )

    body = "".join(sections) if sections else '<div class="clean">Working tree clean</div>'

    return (f"<html><head><style>{POPOVER_CSS}</style></head><body>"
            f"<div class='header'>{header}</div>"
            f"{body}"
            f"</body></html>")

# ---------------------------------------------------------------------------
# iTerm2 main
# ---------------------------------------------------------------------------

async def main(connection: iterm2.Connection):
    app = await iterm2.async_get_app(connection)
    loop = asyncio.get_event_loop()

    component = iterm2.StatusBarComponent(
        short_description="Git Status",
        detailed_description=(
            "Shows current git branch and uncommitted file changes. "
            "Click to see the full file list grouped by status."
        ),
        knobs=[],
        exemplar="\u239b main* 3 files",
        update_cadence=None,
        identifier="com.iterm2.user.git-status-bar",
    )

    @iterm2.StatusBarRPC
    async def git_status_coro(
        knobs,
        path=iterm2.Reference("path?"),
        _tick=iterm2.Reference("user.gitstatus_tick?"),
    ):
        if not path:
            return ""
        return await loop.run_in_executor(None, _summary_text, path)

    @iterm2.RPC
    async def git_status_click(session_id):
        session = app.get_session_by_id(session_id)
        if session is None:
            return
        path = await session.async_get_variable("path")
        if not path:
            return
        popover = await loop.run_in_executor(None, _popover_html, path)
        await component.async_open_popover(
            session_id,
            popover,
            iterm2.util.Size(420, 460),
        )

    await git_status_click.async_register(connection)
    await component.async_register(connection, git_status_coro, onclick=git_status_click)

    async def poll_tick():
        tick = 0
        while True:
            await asyncio.sleep(5)
            tick += 1
            for window in app.terminal_windows:
                for tab in window.tabs:
                    for session in tab.sessions:
                        try:
                            await session.async_set_variable(
                                "user.gitstatus_tick", str(tick)
                            )
                        except Exception:
                            pass

    asyncio.ensure_future(poll_tick())


iterm2.run_forever(main)
