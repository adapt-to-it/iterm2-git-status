#!/usr/bin/env python3
"""
iTerm2 Status Bar: Git Status
==============================
Shows current git branch + change count in the status bar of every session.
Click the component to open an interactive popover with:
- Collapsible local/remote branch lists (double-click to checkout)
- Changed files grouped by status (double-click to open diff in VS Code)
- Quick action buttons: Commit, Push, Pull

Auto-refresh:
- Instantly on every `cd` (via iterm2.Reference("path?") — requires Shell Integration)
- Every 5 seconds to catch git commit/checkout/stash (polling via user variable)

Requirements:
- iTerm2 3.3+ with Python API enabled
- Shell Integration installed
- Python 3.8+
- VS Code (`code` CLI) in PATH for diff feature
- No external dependencies (only stdlib + iterm2)
"""

import asyncio
import html
import json
import subprocess
from typing import Dict, List, Optional, Tuple

import iterm2

# ---------------------------------------------------------------------------
# Popover CSS — dark theme matching iTerm2
# ---------------------------------------------------------------------------

POPOVER_CSS = """
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');

:root {
  --bg:         #0d1117;
  --bg-raised:  #161b22;
  --bg-hover:   #1c2128;
  --bg-active:  #21262d;
  --border:     #30363d;
  --border-dim: #21262d;
  --text:       #c9d1d9;
  --text-dim:   #6e7681;
  --text-muted: #484f58;
  --accent:     #00ff87;
  --accent-dim: #00cc6a;
  --blue:       #58a6ff;
  --orange:     #f0883e;
  --red:        #ff6b6b;
  --yellow:     #e3b341;
  --green:      #3fb950;
  --font:       'JetBrains Mono', 'Menlo', monospace;
  --radius:     5px;
  --radius-sm:  3px;
  --transition: 0.15s cubic-bezier(0.4, 0, 0.2, 1);
}

* { box-sizing: border-box; margin: 0; padding: 0; }

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-dim); }

body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font);
  font-size: 11px;
  line-height: 1.5;
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
}

/* ── Header ─────────────────────────────────────────────── */
.header {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 10px 12px 9px;
  border-bottom: 1px solid var(--border-dim);
  flex-shrink: 0;
  background: var(--bg-raised);
}
.header-icon {
  color: var(--accent);
  flex-shrink: 0;
  opacity: 0.9;
}
.header-branch {
  color: var(--accent);
  font-weight: 700;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  letter-spacing: 0.01em;
}
.header-badge {
  font-size: 10px;
  font-weight: 500;
  color: var(--text-dim);
  background: var(--bg-active);
  border: 1px solid var(--border);
  padding: 1px 7px;
  border-radius: 10px;
  white-space: nowrap;
  flex-shrink: 0;
}

/* ── Scroll area ─────────────────────────────────────────── */
.scroll-area {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  padding: 8px 12px;
}

/* ── Section divider ─────────────────────────────────────── */
.divider {
  height: 1px;
  background: var(--border-dim);
  margin: 8px 0;
}

/* ── Branch collapsible ──────────────────────────────────── */
.branch-section { margin-bottom: 5px; }

.branch-toggle { display: none; }

.branch-label {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding: 4px 7px;
  border-radius: var(--radius-sm);
  color: var(--text-dim);
  background: transparent;
  border: 1px solid transparent;
  user-select: none;
  transition: color var(--transition), background var(--transition), border-color var(--transition);
}
.branch-label:hover {
  color: var(--text);
  background: var(--bg-hover);
  border-color: var(--border-dim);
}
.branch-label .chevron {
  display: inline-flex;
  align-items: center;
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  color: var(--text-muted);
}
.branch-toggle:checked + .branch-label .chevron {
  transform: rotate(90deg);
}
.branch-toggle:checked + .branch-label {
  color: var(--blue);
}
.branch-toggle:checked + .branch-label .chevron {
  color: var(--blue);
}

.branch-list {
  display: none;
  max-height: 108px;
  overflow-y: auto;
  margin-top: 2px;
  margin-left: 8px;
  border-left: 1px solid var(--border-dim);
  padding-left: 6px;
  padding-bottom: 2px;
  animation: slideDown 0.15s ease;
}
.branch-toggle:checked + .branch-label + .branch-list { display: block; }

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}

.branch-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 11px;
  border-radius: var(--radius-sm);
  color: var(--text);
  transition: background var(--transition), color var(--transition);
  cursor: pointer;
  user-select: none;
  -webkit-user-select: none;
}
.branch-item:hover {
  background: var(--bg-hover);
  color: var(--blue);
}
.branch-item.current {
  color: var(--accent);
  font-weight: 500;
}
.branch-item .b-icon { flex-shrink: 0; opacity: 0.7; }
.branch-item.current .b-icon { opacity: 1; }
.branch-item .b-name {
  overflow: hidden;
  text-overflow: ellipsis;
}
.branch-none { font-size: 10px; color: var(--text-muted); padding: 3px 6px; font-style: italic; }

/* ── Section label ───────────────────────────────────────── */
.section { margin-bottom: 9px; }
.section-header {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-bottom: 3px;
}
.section-label {
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  padding: 2px 6px;
  border-radius: 10px;
}
.staged    .section-label { color: var(--green);  background: rgba(63,185,80,.12);  border: 1px solid rgba(63,185,80,.2);  }
.modified  .section-label { color: var(--orange); background: rgba(240,136,62,.12); border: 1px solid rgba(240,136,62,.2); }
.deleted   .section-label { color: var(--red);    background: rgba(255,107,107,.12);border: 1px solid rgba(255,107,107,.2);}
.untracked .section-label { color: var(--text-dim); background: rgba(110,118,129,.1); border: 1px solid rgba(110,118,129,.15);}
.other     .section-label { color: var(--yellow); background: rgba(227,179,65,.1);  border: 1px solid rgba(227,179,65,.15);}

/* ── File row ────────────────────────────────────────────── */
.file {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 6px;
  white-space: nowrap;
  overflow: hidden;
  font-size: 11px;
  border-radius: var(--radius-sm);
  color: var(--text);
  transition: background var(--transition), color var(--transition);
  cursor: pointer;
  user-select: none;
  -webkit-user-select: none;
}
.file:hover { background: var(--bg-hover); color: var(--blue); }
.file .f-icon { flex-shrink: 0; opacity: 0.6; }
.file:hover .f-icon { opacity: 1; }
.file .f-name { overflow: hidden; text-overflow: ellipsis; flex: 1; }
.file .diff-btn {
  flex-shrink: 0;
  display: none;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 3px;
  border: 1px solid var(--border);
  background: var(--bg-active);
  color: var(--text-dim);
  cursor: pointer;
  transition: all var(--transition);
  font-size: 9px;
  line-height: 1;
  user-select: none;
  -webkit-user-select: none;
}
.file:hover .diff-btn { display: inline-flex; }
.file .diff-btn:hover {
  background: rgba(88,166,255,.15);
  border-color: rgba(88,166,255,.5);
  color: var(--blue);
}

.staged    .file .f-icon { color: var(--green);  }
.modified  .file .f-icon { color: var(--orange); }
.deleted   .file .f-icon { color: var(--red);    }
.untracked .file .f-icon { color: var(--text-dim); }
.other     .file .f-icon { color: var(--yellow); }

.clean {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--green);
  font-style: italic;
  padding: 6px 2px;
  font-size: 11px;
}
.no-repo {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-dim);
  font-style: italic;
  padding: 12px 12px;
}

/* ── Action bar ──────────────────────────────────────────── */
.actions {
  display: flex;
  gap: 6px;
  padding: 8px 12px 7px;
  border-top: 1px solid var(--border-dim);
  flex-shrink: 0;
  background: var(--bg-raised);
}
.actions button {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 6px 0;
  background: var(--bg-active);
  color: var(--text-dim);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-family: var(--font);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  cursor: pointer;
  transition: all var(--transition);
  position: relative;
  overflow: hidden;
}
.actions button::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.04) 50%, transparent 60%);
  transform: translateX(-100%);
  transition: transform 0.4s ease;
}
.actions button:hover::after { transform: translateX(100%); }
.actions button:hover {
  transform: translateY(-1px);
  box-shadow: 0 3px 10px rgba(0,0,0,0.4);
}
.actions button:active { transform: translateY(0); box-shadow: none; }

.actions button.commit {
  color: var(--green);
  border-color: rgba(63,185,80,.3);
  background: rgba(63,185,80,.06);
}
.actions button.commit:hover {
  color: #5de56e;
  border-color: rgba(63,185,80,.6);
  background: rgba(63,185,80,.12);
  box-shadow: 0 3px 10px rgba(63,185,80,.15);
}
.actions button.push {
  color: var(--blue);
  border-color: rgba(88,166,255,.3);
  background: rgba(88,166,255,.06);
}
.actions button.push:hover {
  color: #7dbfff;
  border-color: rgba(88,166,255,.6);
  background: rgba(88,166,255,.12);
  box-shadow: 0 3px 10px rgba(88,166,255,.15);
}
.actions button.pull {
  color: var(--orange);
  border-color: rgba(240,136,62,.3);
  background: rgba(240,136,62,.06);
}
.actions button.pull:hover {
  color: #f5a060;
  border-color: rgba(240,136,62,.6);
  background: rgba(240,136,62,.12);
  box-shadow: 0 3px 10px rgba(240,136,62,.15);
}

/* ── Editor button ───────────────────────────────────────── */
.actions button.editor {
  color: var(--text-dim);
  border-color: var(--border);
  background: var(--bg-active);
  flex: 0 0 auto;
  padding: 6px 10px;
  font-size: 9px;
}
.actions button.editor:hover {
  color: var(--text);
  border-color: rgba(110,118,129,.5);
  background: var(--bg-hover);
  box-shadow: 0 3px 10px rgba(0,0,0,.3);
}

/* ── Status bar ──────────────────────────────────────────── */
.status-bar {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 12px 5px;
  min-height: 22px;
  flex-shrink: 0;
  border-top: 1px solid var(--border-dim);
  background: var(--bg);
}
.status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--text-muted);
  transition: background var(--transition);
}
.status-bar.ok   .status-dot { background: var(--accent); box-shadow: 0 0 5px var(--accent); }
.status-bar.err  .status-dot { background: var(--red);    box-shadow: 0 0 5px var(--red); }
.status-bar.loading .status-dot {
  background: var(--yellow);
  animation: pulse 1s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.3; }
}
.status-text {
  font-size: 10px;
  color: var(--text-dim);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.status-bar.ok  .status-text { color: var(--accent); }
.status-bar.err .status-text { color: var(--red); }
.status-bar.loading .status-text { color: var(--yellow); }
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
            timeout=10,
        )
        return r.stdout if r.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _run_git_result(args: List[str], cwd: str) -> Tuple[bool, str]:
    """Returns (success, output_or_stderr)."""
    try:
        r = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0:
            return True, (r.stdout or r.stderr or "OK").strip()
        return False, (r.stderr or r.stdout or "Error").strip()
    except FileNotFoundError:
        return False, "git not found"
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except OSError as e:
        return False, str(e)


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


def _git_branches(cwd: str) -> Dict[str, List[str]]:
    """Returns {"local": [...], "remote": [...], "current": branch_name}."""
    out = _run_git(["branch", "-a", "--no-color"], cwd)
    local: List[str] = []
    remote: List[str] = []
    current = ""
    if out:
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            is_current = line.startswith("* ")
            name = line.lstrip("* ").strip()
            # Skip HEAD pointer
            if "HEAD ->" in name or name.endswith("/HEAD"):
                continue
            if name.startswith("remotes/"):
                remote_name = name[len("remotes/"):]
                remote.append(remote_name)
            else:
                local.append(name)
                if is_current:
                    current = name
    return {"local": local, "remote": remote, "current": current}


def _git_checkout(cwd: str, branch: str) -> Tuple[bool, str]:
    return _run_git_result(["checkout", branch], cwd)


def _git_commit(cwd: str, message: str) -> Tuple[bool, str]:
    return _run_git_result(["commit", "-m", message], cwd)


def _git_push(cwd: str) -> Tuple[bool, str]:
    return _run_git_result(["push"], cwd)


def _git_pull(cwd: str) -> Tuple[bool, str]:
    return _run_git_result(["pull"], cwd)


import os as _os

_CONFIG_PATH = _os.path.expanduser(
    "~/Library/Application Support/iTerm2/Scripts/AutoLaunch/git_status_bar_config.json"
)


def _load_config() -> dict:
    try:
        with open(_CONFIG_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_config(data: dict) -> None:
    with open(_CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _get_saved_editor() -> Optional[str]:
    return _load_config().get("editor")


def _save_editor(editor_path: str) -> None:
    cfg = _load_config()
    cfg["editor"] = editor_path
    _save_config(cfg)


def _pick_editor_app() -> Optional[str]:
    """Open a native macOS file picker in /Applications and return the CLI path."""
    script = '''
tell application "Finder"
    activate
end tell
set appFile to choose file with prompt "Select your editor application:" default location POSIX file "/Applications"
return POSIX path of appFile
'''
    try:
        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=60,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return None
        app_path = r.stdout.strip()
        # Look for a CLI executable inside the .app bundle
        candidates = [
            # VS Code
            _os.path.join(app_path, "Contents/Resources/app/bin/code"),
            # Cursor
            _os.path.join(app_path, "Contents/Resources/app/bin/cursor"),
            # Sublime Text
            _os.path.join(app_path, "Contents/SharedSupport/bin/subl"),
            # Zed
            _os.path.join(app_path, "Contents/MacOS/cli"),
        ]
        for cli in candidates:
            if _os.path.isfile(cli) and _os.access(cli, _os.X_OK):
                return cli
        # Fallback: open the .app directly via `open -a`
        # Store the .app path itself — we'll call `open -a <app> <file>`
        if app_path.endswith(".app") and _os.path.isdir(app_path):
            return f"open_app:{app_path}"
        return None
    except (subprocess.TimeoutExpired, OSError):
        return None


def _app_path_for_cli(cli_path: str) -> Optional[str]:
    """Walk up from a CLI path inside a .app bundle to find the .app root."""
    parts = cli_path.split("/")
    for i, part in enumerate(parts):
        if part.endswith(".app"):
            return "/".join(parts[:i + 1])
    return None


def _open_editor_diff(cwd: str, filepath: str, editor_path: str) -> Tuple[bool, str]:
    """Open a two-pane diff: HEAD version vs working copy."""
    import tempfile
    abs_path = filepath if _os.path.isabs(filepath) else _os.path.join(cwd, filepath)

    # Get the CLI path (needed for --diff flag; open_app fallback uses git difftool)
    if editor_path.startswith("open_app:"):
        cli_path = None
        app_path = editor_path[len("open_app:"):]
    else:
        cli_path = editor_path
        app_path = _app_path_for_cli(editor_path)

    # Try to get HEAD version of the file
    head_content = _run_git(["show", f"HEAD:{filepath}"], cwd)

    if head_content is not None and cli_path:
        # Write HEAD content to a temp file and open --diff
        suffix = _os.path.splitext(filepath)[1] or ".txt"
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=suffix,
                prefix=f"HEAD_{_os.path.basename(filepath)}_",
                delete=False
            ) as tmp:
                tmp.write(head_content)
                tmp_path = tmp.name
            subprocess.Popen(
                [cli_path, "--diff", tmp_path, abs_path],
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True, f"Diff opened for {_os.path.basename(filepath)}"
        except OSError as e:
            return False, str(e)
    elif app_path:
        # Fallback: open the file normally (VS Code will show git gutter diff)
        try:
            subprocess.Popen(
                ["open", "-n", "-a", app_path, "--args", abs_path],
                cwd=cwd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True, f"Opened {_os.path.basename(filepath)} (no HEAD — new file)"
        except OSError as e:
            return False, str(e)
    else:
        return False, "No editor configured"


def _open_editor(cwd: str, filepath: str, editor_path: str) -> Tuple[bool, str]:
    abs_path = filepath if _os.path.isabs(filepath) else _os.path.join(cwd, filepath)
    try:
        if editor_path.startswith("open_app:"):
            app_path = editor_path[len("open_app:"):]
            cmd = ["open", "-n", "-a", app_path, "--args", abs_path]
        else:
            # Prefer `open -a <bundle>` over calling the CLI directly — much faster
            app_path = _app_path_for_cli(editor_path)
            if app_path:
                cmd = ["open", "-n", "-a", app_path, "--args", abs_path]
            else:
                cmd = [editor_path, "--new-window", abs_path]
        subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True, f"Opened {_os.path.basename(filepath)}"
    except OSError as e:
        return False, str(e)


def _summary_text(path: str) -> str:
    """Compact text for the status bar."""
    branch, groups = _git_info(path)
    if branch is None:
        return ""
    total = sum(len(v) for v in groups.values())
    if total == 0:
        return f"\u2387 {branch} \u2713"
    return f"\u2387 {branch}* {total} file{'s' if total != 1 else ''}"


def _popover_html(path: str, session_id: str) -> str:
    """Full interactive HTML for the click popover."""
    branch, groups = _git_info(path)
    safe_path = html.escape(path)

    # SVG icons (inline, no external deps)
    ICO_BRANCH = "<svg width='11' height='11' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><line x1='6' y1='3' x2='6' y2='15'/><circle cx='18' cy='6' r='3'/><circle cx='6' cy='18' r='3'/><path d='M18 9a9 9 0 0 1-9 9'/></svg>"
    ICO_REMOTE = "<svg width='11' height='11' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' cy='12' r='10'/><line x1='2' y1='12' x2='22' y2='12'/><path d='M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z'/></svg>"
    ICO_CHECK  = "<svg width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round'><polyline points='20 6 9 17 4 12'/></svg>"
    ICO_CLEAN  = "<svg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round'><path d='M22 11.08V12a10 10 0 1 1-5.93-9.14'/><polyline points='22 4 12 14.01 9 11.01'/></svg>"
    ICO_FILE   = "<svg width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'/><polyline points='14 2 14 8 20 8'/></svg>"
    ICO_COMMIT = "<svg width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round'><circle cx='12' cy='12' r='4'/><line x1='1.05' y1='12' x2='7' y2='12'/><line x1='17.01' y1='12' x2='22.96' y2='12'/></svg>"
    ICO_PUSH   = "<svg width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><line x1='12' y1='19' x2='12' y2='5'/><polyline points='5 12 12 5 19 12'/></svg>"
    ICO_PULL   = "<svg width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><line x1='12' y1='5' x2='12' y2='19'/><polyline points='19 12 12 19 5 12'/></svg>"
    ICO_EDITOR = "<svg width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polyline points='16 18 22 12 16 6'/><polyline points='8 6 2 12 8 18'/></svg>"
    ICO_DIFF   = "<svg width='10' height='10' viewBox='0 0 16 16' fill='currentColor' xmlns='http://www.w3.org/2000/svg'><path fill-rule='evenodd' d='M11.5 2a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zM9.05 3a2.5 2.5 0 0 1 4.9 0H16v1h-2.05a2.5 2.5 0 0 1-4.9 0H0V3h9.05zM4.5 11a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zm-2.45 1a2.5 2.5 0 0 1 4.9 0H16v1H6.95a2.5 2.5 0 0 1-4.9 0H0v-1h2.05zM8 7a1 1 0 0 0 0 2h5a1 1 0 0 0 0-2H8zM3 8a1 1 0 0 1 1-1h.5a1 1 0 0 1 0 2H4a1 1 0 0 1-1-1z'/></svg>"
    ICO_CHEVRON= "<svg width='9' height='9' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'><polyline points='9 18 15 12 9 6'/></svg>"
    ICO_NOREPO = "<svg width='13' height='13' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round'><circle cx='12' cy='12' r='10'/><line x1='4.93' y1='4.93' x2='19.07' y2='19.07'/></svg>"
    ICO_GIT    = "<svg width='13' height='13' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><circle cx='18' cy='18' r='3'/><circle cx='6' cy='6' r='3'/><path d='M13 6h3a2 2 0 0 1 2 2v7'/><line x1='6' y1='9' x2='6' y2='21'/></svg>"

    if branch is None:
        return (
            f"<html><head><meta charset='utf-8'><style>{POPOVER_CSS}</style></head><body>"
            f"<div class='header'>"
            f"<span class='header-icon'>{ICO_NOREPO}</span>"
            f"<span class='header-branch' style='color:var(--text-dim)'>{safe_path}</span>"
            f"</div>"
            f"<div class='scroll-area'>"
            f"<div class='no-repo'>{ICO_NOREPO} Not a git repository</div>"
            f"</div></body></html>"
        )

    safe_branch = html.escape(branch)
    total = sum(len(v) for v in groups.values())
    badge = f"{total} change{'s' if total != 1 else ''}" if total > 0 else "clean"

    # --- Branch lists ---
    branches = _git_branches(path)
    current = branches["current"]
    js_sid = session_id.replace('"', '\\"')

    def branch_items_html(branch_list: List[str], icon: str) -> str:
        if not branch_list:
            return f'<div class="branch-none">none</div>'
        items = []
        for b in branch_list:
            safe_b = html.escape(b)
            is_cur = (b == current)
            cls = "branch-item current" if is_cur else "branch-item"
            js_b = b.replace("\\", "\\\\").replace('"', '\\"')
            cur_icon = ICO_CHECK if is_cur else icon
            items.append(
                f'<div class="{cls}" title="{safe_b}" data-branch="{safe_b}">'
                f'<span class="b-icon">{cur_icon}</span>'
                f'<span class="b-name">{safe_b}</span>'
                f'</div>'
            )
        return "".join(items)

    local_items  = branch_items_html(branches["local"],  ICO_BRANCH)
    remote_items = branch_items_html(branches["remote"], ICO_REMOTE)
    local_count  = len(branches["local"])
    remote_count = len(branches["remote"])

    branches_html = f"""
<div class="branch-section">
  <input type="checkbox" id="tl" class="branch-toggle" checked>
  <label for="tl" class="branch-label">
    <span class="chevron">{ICO_CHEVRON}</span>
    {ICO_BRANCH}&nbsp;Local
    <span style="margin-left:auto;font-size:9px;opacity:0.5">{local_count}</span>
  </label>
  <div class="branch-list">{local_items}</div>
</div>
<div class="branch-section">
  <input type="checkbox" id="tr" class="branch-toggle">
  <label for="tr" class="branch-label">
    <span class="chevron">{ICO_CHEVRON}</span>
    {ICO_REMOTE}&nbsp;Remote
    <span style="margin-left:auto;font-size:9px;opacity:0.5">{remote_count}</span>
  </label>
  <div class="branch-list">{remote_items}</div>
</div>
"""

    # --- File sections ---
    canonical = [
        ("staged",    "A", "Staged",    ICO_CHECK),
        ("modified",  "M", "Modified",  ICO_FILE),
        ("deleted",   "D", "Deleted",   ICO_FILE),
        ("untracked", "?", "Untracked", ICO_FILE),
    ]
    sections = []
    seen: set = set()

    def file_div(f: str, f_icon: str) -> str:
        safe_f = html.escape(f)
        return (
            f'<div class="file" title="{safe_f} (double-click to open)" data-file="{safe_f}">'
            f'<span class="f-icon">{f_icon}</span>'
            f'<span class="f-name">{safe_f}</span>'
            f'<span class="diff-btn" data-diff="{safe_f}" title="Open diff view">{ICO_DIFF}</span>'
            f'</div>'
        )

    for css_class, key, label, f_icon in canonical:
        files = groups.get(key, [])
        if not files:
            continue
        seen.add(key)
        rows = "".join(file_div(f, f_icon) for f in files)
        sections.append(
            f'<div class="section {css_class}">'
            f'<div class="section-header">'
            f'<span class="section-label">{label} ({len(files)})</span>'
            f'</div>'
            f'{rows}</div>'
        )
    for key, files in groups.items():
        if key in seen or not files:
            continue
        rows = "".join(file_div(f, ICO_FILE) for f in files)
        sections.append(
            f'<div class="section other">'
            f'<div class="section-header">'
            f'<span class="section-label">{html.escape(key)} ({len(files)})</span>'
            f'</div>'
            f'{rows}</div>'
        )

    files_body = (
        "".join(sections) if sections
        else f'<div class="clean">{ICO_CLEAN} Working tree clean</div>'
    )

    # Editor label for the button
    saved_editor = _get_saved_editor()
    if saved_editor:
        # Strip open_app: prefix and .app suffix for display
        _ed_display = saved_editor.replace("open_app:", "").rstrip("/")
        _ed_display = _os.path.basename(_ed_display).replace(".app", "")
        editor_label = _ed_display
    else:
        editor_label = "set editor"
    editor_title = html.escape(saved_editor or "not set")

    # --- JavaScript ---
    js = f"""
<script>
var SESSION_ID = "{js_sid}";

function setStatus(msg, cls) {{
  var bar = document.getElementById('status-bar');
  var txt = document.getElementById('status-text');
  bar.className = 'status-bar ' + cls;
  txt.textContent = msg;
}}

function onResult(resultJson) {{
  try {{
    var r = JSON.parse(resultJson);
    setStatus(r.message || (r.ok ? 'Done' : 'Failed'), r.ok ? 'ok' : 'err');
  }} catch(e) {{
    setStatus(String(resultJson), 'err');
  }}
}}

function doCheckout(branch) {{
  setStatus('Switching to ' + branch + '\u2026', 'loading');
  iterm2Invoke(
    'git_status_bar_action(session_id: "' + SESSION_ID + '", action: "checkout", arg: "' + branch + '")',
    'onResult'
  );
}}

function doDiff(filepath) {{
  setStatus('Opening\u2026', 'loading');
  iterm2Invoke(
    'git_status_bar_action(session_id: "' + SESSION_ID + '", action: "diff", arg: "' + filepath + '")',
    'onResult'
  );
}}

function doDiffView(filepath) {{
  setStatus('Opening diff view\u2026', 'loading');
  iterm2Invoke(
    'git_status_bar_action(session_id: "' + SESSION_ID + '", action: "diff_view", arg: "' + filepath + '")',
    'onResult'
  );
}}

function doAction(action) {{
  setStatus(action.charAt(0).toUpperCase() + action.slice(1) + '\u2026', 'loading');
  iterm2Invoke(
    'git_status_bar_action(session_id: "' + SESSION_ID + '", action: "' + action + '", arg: "")',
    'onResult'
  );
}}

document.addEventListener('DOMContentLoaded', function() {{
  // Branch double-click
  document.querySelectorAll('.branch-item').forEach(function(el) {{
    el.addEventListener('mousedown', function(e) {{ e.preventDefault(); }});
    el.addEventListener('dblclick', function(e) {{
      e.preventDefault();
      var branch = el.getAttribute('data-branch');
      if (branch) doCheckout(branch);
    }});
  }});

  // File double-click → open file
  document.querySelectorAll('.file').forEach(function(el) {{
    el.addEventListener('mousedown', function(e) {{ e.preventDefault(); }});
    el.addEventListener('dblclick', function(e) {{
      e.preventDefault();
      var filepath = el.getAttribute('data-file');
      if (filepath) doDiff(filepath);
    }});
  }});

  // Diff button click → open diff view
  document.querySelectorAll('.diff-btn').forEach(function(btn) {{
    btn.addEventListener('mousedown', function(e) {{ e.stopPropagation(); e.preventDefault(); }});
    btn.addEventListener('click', function(e) {{
      e.stopPropagation();
      e.preventDefault();
      var filepath = btn.getAttribute('data-diff');
      if (filepath) doDiffView(filepath);
    }});
  }});
}});
</script>
"""

    return (
        f"<html><head><meta charset='utf-8'><style>{POPOVER_CSS}</style></head><body>"
        # Header
        f"<div class='header'>"
        f"<span class='header-icon'>{ICO_GIT}</span>"
        f"<span class='header-branch'>{safe_branch}</span>"
        f"<span class='header-badge'>{badge}</span>"
        f"</div>"
        # Scroll area: branches + divider + files
        f"<div class='scroll-area'>"
        f"{branches_html}"
        f"<div class='divider'></div>"
        f"{files_body}"
        f"</div>"
        # Action buttons
        f"<div class='actions'>"
        f"<button class='commit' onclick='doAction(\"commit\")'>{ICO_COMMIT}&nbsp;Commit</button>"
        f"<button class='push'   onclick='doAction(\"push\")'  >{ICO_PUSH}&nbsp;Push</button>"
        f"<button class='pull'   onclick='doAction(\"pull\")'  >{ICO_PULL}&nbsp;Pull</button>"
        f"<button class='editor' onclick='doAction(\"set_editor\")' title='Editor: {editor_title}'>"
        f"{ICO_EDITOR}&nbsp;{html.escape(editor_label)}</button>"
        f"</div>"
        # Status bar
        f"<div id='status-bar' class='status-bar'>"
        f"<span class='status-dot'></span>"
        f"<span id='status-text' class='status-text'>double-click branch to checkout &middot; double-click file to diff</span>"
        f"</div>"
        f"{js}"
        f"</body></html>"
    )


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
            "Click to see an interactive panel with branch list, file changes, "
            "and quick Commit/Push/Pull buttons."
        ),
        knobs=[],
        exemplar="\u2387 main* 3 files",
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
        popover = await loop.run_in_executor(None, _popover_html, path, session_id)
        await component.async_open_popover(
            session_id,
            popover,
            iterm2.util.Size(450, 650),
        )

    @iterm2.RPC
    async def git_status_bar_action(session_id, action, arg):
        session = app.get_session_by_id(session_id)
        if session is None:
            return json.dumps({"ok": False, "message": "Session not found"})
        path = await session.async_get_variable("path")
        if not path:
            return json.dumps({"ok": False, "message": "No path"})

        if action == "checkout":
            alert = iterm2.Alert(
                "Checkout Branch",
                f"Switch to branch '{arg}'?",
            )
            alert.add_button("Checkout")
            alert.add_button("Cancel")
            result = await alert.async_run(connection)
            if result == 1000:
                ok, msg = await loop.run_in_executor(None, _git_checkout, path, arg)
                return json.dumps({"ok": ok, "message": msg})
            return json.dumps({"ok": False, "message": "Cancelled"})

        elif action == "commit":
            text_alert = iterm2.TextInputAlert(
                "Git Commit",
                "Enter commit message:",
                "Commit message...",
                "",
            )
            message = await text_alert.async_run(connection)
            if message and message.strip():
                ok, msg = await loop.run_in_executor(
                    None, _git_commit, path, message.strip()
                )
                return json.dumps({"ok": ok, "message": msg})
            return json.dumps({"ok": False, "message": "Cancelled"})

        elif action == "push":
            alert = iterm2.Alert("Git Push", "Push to remote?")
            alert.add_button("Push")
            alert.add_button("Cancel")
            result = await alert.async_run(connection)
            if result == 1000:
                ok, msg = await loop.run_in_executor(None, _git_push, path)
                return json.dumps({"ok": ok, "message": msg})
            return json.dumps({"ok": False, "message": "Cancelled"})

        elif action == "pull":
            alert = iterm2.Alert("Git Pull", "Pull from remote?")
            alert.add_button("Pull")
            alert.add_button("Cancel")
            result = await alert.async_run(connection)
            if result == 1000:
                ok, msg = await loop.run_in_executor(None, _git_pull, path)
                return json.dumps({"ok": ok, "message": msg})
            return json.dumps({"ok": False, "message": "Cancelled"})

        elif action == "diff":
            editor = await loop.run_in_executor(None, _get_saved_editor)
            if not editor:
                selected = await loop.run_in_executor(None, _pick_editor_app)
                if not selected:
                    return json.dumps({"ok": False, "message": "No editor selected"})
                await loop.run_in_executor(None, _save_editor, selected)
                editor = selected
            ok, msg = await loop.run_in_executor(None, _open_editor, path, arg, editor)
            return json.dumps({"ok": ok, "message": msg})

        elif action == "diff_view":
            editor = await loop.run_in_executor(None, _get_saved_editor)
            if not editor:
                selected = await loop.run_in_executor(None, _pick_editor_app)
                if not selected:
                    return json.dumps({"ok": False, "message": "No editor selected"})
                await loop.run_in_executor(None, _save_editor, selected)
                editor = selected
            ok, msg = await loop.run_in_executor(None, _open_editor_diff, path, arg, editor)
            return json.dumps({"ok": ok, "message": msg})

        elif action == "set_editor":
            selected = await loop.run_in_executor(None, _pick_editor_app)
            if not selected:
                return json.dumps({"ok": False, "message": "Cancelled"})
            await loop.run_in_executor(None, _save_editor, selected)
            name = _os.path.basename(selected.replace("open_app:", "").rstrip("/"))
            return json.dumps({"ok": True, "message": f"Editor set: {name}"})

        return json.dumps({"ok": False, "message": f"Unknown action: {action}"})

    await git_status_bar_action.async_register(connection)
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
