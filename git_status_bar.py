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
.branch-section { margin-bottom: 5px; position: relative; }

.branch-toggle { display: none; }

.branch-count { margin-left: auto; font-size: 9px; opacity: 0.5; }
.local-section .branch-label { padding-right: 30px; }
.local-section .branch-count { margin-right: 4px; }

.new-branch-btn {
  position: absolute;
  top: 3px;
  right: 4px;
  width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  color: var(--text-dim);
  border: 1px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-family: var(--font);
  font-size: 13px;
  font-weight: 400;
  line-height: 1;
  padding: 0;
  transition: all var(--transition);
  z-index: 2;
}
.new-branch-btn:hover {
  color: var(--blue);
  border-color: rgba(88,166,255,.45);
  background: rgba(88,166,255,.08);
  transform: rotate(90deg);
}
.new-branch-btn:active { transform: rotate(90deg) scale(0.92); }
.new-branch-btn.active {
  color: var(--blue);
  border-color: var(--blue);
  background: rgba(88,166,255,.15);
  transform: rotate(45deg);
}

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
  flex: 1;
}
.branch-item .b-copy {
  flex-shrink: 0;
  opacity: 0;
  cursor: pointer;
  padding: 1px 3px;
  border-radius: var(--radius-sm);
  transition: opacity var(--transition), background var(--transition);
}
.branch-item:hover .b-copy { opacity: 0.6; }
.branch-item .b-copy:hover { opacity: 1; background: var(--bg-hover); }
.branch-none { font-size: 10px; color: var(--text-muted); padding: 3px 6px; font-style: italic; }

/* ── Checkbox ────────────────────────────────────────────── */
.cb {
  appearance: none;
  -webkit-appearance: none;
  width: 11px;
  height: 11px;
  border: 1px solid var(--border);
  border-radius: 2px;
  background: var(--bg);
  cursor: pointer;
  flex-shrink: 0;
  position: relative;
  transition: border-color var(--transition), background var(--transition);
  margin: 0;
  display: inline-block;
  vertical-align: middle;
}
.cb:hover {
  border-color: var(--text-dim);
  background: var(--bg-hover);
}
.cb:checked {
  background: var(--bg);
  border-color: var(--accent-dim);
}
.cb:checked::after {
  content: '';
  position: absolute;
  left: 2px;
  top: 0px;
  width: 3px;
  height: 7px;
  border: solid var(--accent);
  border-width: 0 1.5px 1.5px 0;
  transform: rotate(45deg);
}
.cb:checked:hover { border-color: var(--accent); }
.cb:indeterminate {
  background: var(--bg);
  border-color: var(--accent-dim);
}
.cb:indeterminate::after {
  content: '';
  position: absolute;
  left: 2px;
  top: 4px;
  width: 5px;
  height: 1.5px;
  background: var(--accent);
  border-radius: 1px;
}
.file-cb { margin-right: 1px; }
.section-cb { margin-right: 2px; }

/* ── Select-all toolbar ──────────────────────────────────── */
.sel-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 2px 9px;
  margin-bottom: 2px;
  border-bottom: 1px dashed var(--border-dim);
  font-size: 10px;
  color: var(--text-dim);
}
.sel-toolbar .sel-btn {
  background: transparent;
  color: var(--text-dim);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 3px 9px;
  font-family: var(--font);
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  cursor: pointer;
  transition: all var(--transition);
}
.sel-toolbar .sel-btn:hover {
  color: var(--accent);
  border-color: var(--accent-dim);
  background: rgba(0,255,135,0.06);
}
.sel-toolbar .sel-btn:active { transform: translateY(1px); }
.sel-count {
  margin-left: auto;
  font-size: 9px;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.04em;
  opacity: 0.75;
}
.sel-count.has-selection { color: var(--accent); opacity: 1; }

/* ── Section label ───────────────────────────────────────── */
.section { margin-bottom: 9px; }
.section-header {
  display: flex;
  align-items: center;
  gap: 6px;
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
.file.copied {
  animation: copyFlash 0.65s cubic-bezier(0.4, 0, 0.2, 1);
}
@keyframes copyFlash {
  0%   { background: rgba(0,255,135,0.28); box-shadow: inset 2px 0 0 var(--accent); }
  60%  { background: rgba(0,255,135,0.10); box-shadow: inset 2px 0 0 var(--accent-dim); }
  100% { background: transparent;          box-shadow: inset 2px 0 0 transparent; }
}
.file .f-icon { flex-shrink: 0; opacity: 0.6; }
.file:hover .f-icon { opacity: 1; }
.file .f-name {
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  cursor: pointer;
  transition: color var(--transition);
  min-width: 0;
}
.file.copied .f-name { color: var(--accent); }
.file .f-stat {
  flex-shrink: 0;
  font-size: 9.5px;
  font-family: var(--font);
  font-variant-numeric: tabular-nums;
  color: var(--text-muted);
  padding: 0 5px 0 6px;
  margin-left: 2px;
  border-left: 1px solid var(--border-dim);
  letter-spacing: -0.02em;
  white-space: nowrap;
  opacity: 0.85;
  transition: opacity var(--transition);
}
.file:hover .f-stat { opacity: 1; }
.file .f-stat .add { color: var(--green); font-weight: 600; }
.file .f-stat .del { color: var(--red);   font-weight: 600; margin-left: 2px; }
.file .f-stat .bin { color: var(--yellow); font-style: italic; }
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

/* ── Commit input (inline, above actions) ─────────────────── */
.commit-input-wrap {
  flex-shrink: 0;
  max-height: 0;
  overflow: hidden;
  opacity: 0;
  padding: 0 12px;
  background: var(--bg-raised);
  border-top: 1px solid var(--border-dim);
  transition: max-height 0.2s cubic-bezier(0.4, 0, 0.2, 1),
              opacity 0.2s ease,
              padding 0.2s ease;
  position: relative;
}
.commit-input-wrap.show {
  max-height: 60px;
  opacity: 1;
  padding: 9px 12px 2px;
}
.commit-input-wrap::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  width: 2px;
  height: 100%;
  background: linear-gradient(180deg, var(--accent) 0%, var(--accent-dim) 100%);
  opacity: 0;
  transition: opacity 0.2s ease;
}
.commit-input-wrap.show::before { opacity: 0.85; }
.commit-input-wrap.mode-branch::before {
  background: linear-gradient(180deg, var(--blue) 0%, #4a8fdd 100%);
}
.commit-input-wrap.mode-branch .commit-input {
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='11' height='11' viewBox='0 0 24 24' fill='none' stroke='%2358a6ff' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><line x1='6' y1='3' x2='6' y2='15'/><circle cx='18' cy='6' r='3'/><circle cx='6' cy='18' r='3'/><path d='M18 9a9 9 0 0 1-9 9'/></svg>");
  background-position: 7px center;
}
.commit-input-wrap.mode-branch .commit-input:focus {
  border-color: rgba(88,166,255,.6);
  box-shadow: 0 0 0 2px rgba(88,166,255,.14);
}
.commit-input {
  width: 100%;
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 6px 10px 6px 22px;
  font-family: var(--font);
  font-size: 11px;
  outline: none;
  transition: border-color var(--transition), box-shadow var(--transition);
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%2300cc6a' stroke-width='2.5' stroke-linecap='round'><polyline points='9 18 15 12 9 6'/></svg>");
  background-repeat: no-repeat;
  background-position: 8px center;
}
.commit-input::placeholder {
  color: var(--text-dim);
  opacity: 0.6;
  font-style: italic;
}
.commit-input:focus {
  border-color: var(--accent-dim);
  box-shadow: 0 0 0 2px rgba(0,255,135,0.14);
}

/* ── Disabled button ─────────────────────────────────────── */
.actions button:disabled,
.actions button.disabled {
  color: var(--text-muted) !important;
  border-color: var(--border-dim) !important;
  background: var(--bg-active) !important;
  cursor: not-allowed;
  transform: none !important;
  box-shadow: none !important;
  opacity: 0.75;
}
.actions button:disabled:hover::after,
.actions button.disabled:hover::after { transform: translateX(-100%); }
.actions button:disabled:hover,
.actions button.disabled:hover {
  color: var(--text-muted) !important;
  border-color: var(--border-dim) !important;
  background: var(--bg-active) !important;
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

/* ── Context menu ────────────────────────────────────────── */
.ctx-menu {
  position: fixed;
  z-index: 9999;
  min-width: 180px;
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 4px;
  box-shadow:
    0 8px 28px rgba(0,0,0,0.55),
    0 2px 6px rgba(0,0,0,0.35),
    inset 0 1px 0 rgba(255,255,255,0.03);
  font-family: var(--font);
  font-size: 11px;
  color: var(--text);
  opacity: 0;
  transform: translateY(-4px) scale(0.98);
  transform-origin: top left;
  pointer-events: none;
  transition: opacity 0.12s ease, transform 0.12s cubic-bezier(0.4, 0, 0.2, 1);
}
.ctx-menu.show {
  opacity: 1;
  transform: translateY(0) scale(1);
  pointer-events: auto;
}
.ctx-menu::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 2px;
  background: linear-gradient(180deg, var(--accent) 0%, var(--accent-dim) 100%);
  border-radius: var(--radius) 0 0 var(--radius);
  opacity: 0.5;
}
.ctx-header {
  padding: 5px 10px 6px 12px;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-dim);
  border-bottom: 1px solid var(--border-dim);
  margin-bottom: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 260px;
}
.ctx-item {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 5px 12px 5px 12px;
  cursor: pointer;
  border-radius: var(--radius-sm);
  color: var(--text);
  transition: background var(--transition), color var(--transition);
  user-select: none;
  -webkit-user-select: none;
  white-space: nowrap;
}
.ctx-item:hover {
  background: var(--bg-hover);
  color: var(--accent);
}
.ctx-item:hover .ctx-icon { color: var(--accent); opacity: 1; }
.ctx-icon {
  flex-shrink: 0;
  width: 12px;
  height: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--text-dim);
  opacity: 0.8;
  transition: color var(--transition), opacity var(--transition);
}
.ctx-label { flex: 1; }
.ctx-kbd {
  font-size: 9px;
  color: var(--text-muted);
  letter-spacing: 0.04em;
  padding-left: 10px;
}
.ctx-sep {
  height: 1px;
  background: var(--border-dim);
  margin: 3px 4px;
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


def _git_info_full(path: str):
    branch, groups = _git_info(path)
    stats = _git_numstat(path) if groups else {}
    return branch, groups, stats


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


def _git_new_branch(cwd: str, name: str) -> Tuple[bool, str]:
    import re as _re
    if not name or not _re.match(r"^[A-Za-z0-9._/\-]+$", name):
        return False, "Invalid branch name"
    ok, msg = _run_git_result(["checkout", "-b", name], cwd)
    if ok:
        return True, f"Created and switched to '{name}'"
    return False, msg


def _git_commit(cwd: str, message: str, files: Optional[List[str]] = None) -> Tuple[bool, str]:
    if files:
        ok, msg = _run_git_result(["add", "--"] + files, cwd)
        if not ok:
            return False, msg
        return _run_git_result(["commit", "-m", message, "--"] + files, cwd)
    return _run_git_result(["commit", "-m", message], cwd)


def _git_numstat(cwd: str) -> Dict[str, Tuple[int, int, bool]]:
    """Returns {filepath: (added, deleted, is_binary)} merging staged + unstaged."""
    result: Dict[str, Tuple[int, int, bool]] = {}
    for args in (["diff", "--numstat"], ["diff", "--cached", "--numstat"]):
        out = _run_git(args, cwd)
        if not out:
            continue
        for line in out.splitlines():
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue
            a_str, d_str, path = parts
            if " => " in path:
                # rename: "old => new" or "dir/{old => new}/file"
                if "{" in path and "}" in path:
                    pre, rest = path.split("{", 1)
                    mid, post = rest.split("}", 1)
                    _, new = mid.split(" => ", 1)
                    path = pre + new + post
                else:
                    path = path.split(" => ", 1)[1]
            is_binary = a_str == "-" or d_str == "-"
            added = 0 if is_binary else int(a_str)
            deleted = 0 if is_binary else int(d_str)
            if path in result:
                pa, pd, pb = result[path]
                result[path] = (pa + added, pd + deleted, pb or is_binary)
            else:
                result[path] = (added, deleted, is_binary)
    return result


def _git_push(cwd: str) -> Tuple[bool, str]:
    return _run_git_result(["push"], cwd)


def _git_pull(cwd: str) -> Tuple[bool, str]:
    return _run_git_result(["pull"], cwd)


def _git_toplevel(cwd: str) -> Optional[str]:
    out = _run_git(["rev-parse", "--show-toplevel"], cwd)
    return out.strip() if out else None


def _add_to_gitignore(cwd: str, filepath: str) -> Tuple[bool, str]:
    import os as _os2
    root = _git_toplevel(cwd)
    if not root:
        return False, "Not a git repo"

    abs_path = filepath if _os2.path.isabs(filepath) else _os2.path.join(cwd, filepath)
    try:
        rel = _os2.path.relpath(abs_path, root)
    except ValueError:
        return False, "Path outside repo"
    if rel.startswith(".."):
        return False, "Path outside repo"

    is_dir = _os2.path.isdir(abs_path)
    entry = rel.replace(_os2.sep, "/")
    if is_dir and not entry.endswith("/"):
        entry = entry + "/"

    gi_path = _os2.path.join(root, ".gitignore")
    existing_lines: List[str] = []
    had_trailing_newline = True
    if _os2.path.exists(gi_path):
        try:
            with open(gi_path, "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError as e:
            return False, f"Read error: {e}"
        had_trailing_newline = content.endswith("\n") if content else True
        existing_lines = content.splitlines()
        for line in existing_lines:
            stripped = line.strip()
            if stripped == entry or stripped == entry.rstrip("/"):
                return True, f"Already in .gitignore: {entry}"

    try:
        with open(gi_path, "a", encoding="utf-8") as fh:
            if existing_lines and not had_trailing_newline:
                fh.write("\n")
            fh.write(entry + "\n")
    except OSError as e:
        return False, f"Write error: {e}"

    kind = "folder" if is_dir else "file"
    return True, f"Added {kind} to .gitignore: {entry}"


def _reveal_in_finder(cwd: str, filepath: str) -> Tuple[bool, str]:
    import os as _os2
    abs_path = filepath if _os2.path.isabs(filepath) else _os2.path.join(cwd, filepath)
    if not _os2.path.exists(abs_path):
        return False, f"Not found: {filepath}"
    try:
        subprocess.run(["open", "-R", abs_path], check=True, timeout=5)
        return True, f"Revealed: {_os2.path.basename(abs_path)}"
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return False, str(e)


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
    branch, groups, stats = _git_info_full(path)
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
    ICO_COPY   = "<svg width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><rect x='9' y='9' width='13' height='13' rx='2' ry='2'/><path d='M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1'/></svg>"
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
                f'<span class="b-copy" data-branch="{safe_b}" title="Copy branch name">{ICO_COPY}</span>'
                f'</div>'
            )
        return "".join(items)

    local_items  = branch_items_html(branches["local"],  ICO_BRANCH)
    remote_items = branch_items_html(branches["remote"], ICO_REMOTE)
    local_count  = len(branches["local"])
    remote_count = len(branches["remote"])

    branches_html = f"""
<div class="branch-section local-section">
  <input type="checkbox" id="tl" class="branch-toggle" checked>
  <label for="tl" class="branch-label">
    <span class="chevron">{ICO_CHEVRON}</span>
    {ICO_BRANCH}&nbsp;Local
    <span class="branch-count">{local_count}</span>
  </label>
  <button type="button" id="new-branch-btn" class="new-branch-btn" title="Create new branch">+</button>
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

    def stat_html(f: str, key: str) -> str:
        if key == "?":
            return ""
        s = stats.get(f)
        if not s:
            return ""
        added, deleted, is_bin = s
        if is_bin:
            return "<span class='f-stat'><span class='bin'>bin</span></span>"
        return (
            "<span class='f-stat'>"
            f"<span class='add'>+{added}</span> "
            f"<span class='del'>-{deleted}</span>"
            "</span>"
        )

    def file_div(f: str, f_icon: str, key: str) -> str:
        safe_f = html.escape(f)
        safe_k = html.escape(key)
        return (
            f'<div class="file" title="{safe_f}" data-file="{safe_f}" data-status="{safe_k}">'
            f'<input type="checkbox" class="cb file-cb" data-file="{safe_f}">'
            f'<span class="f-icon">{f_icon}</span>'
            f'<span class="f-name" data-file="{safe_f}">{safe_f}</span>'
            f'{stat_html(f, key)}'
            f'<span class="diff-btn" data-diff="{safe_f}" title="Open diff view">{ICO_DIFF}</span>'
            f'</div>'
        )

    total_files = 0
    for css_class, key, label, f_icon in canonical:
        files = groups.get(key, [])
        if not files:
            continue
        seen.add(key)
        total_files += len(files)
        safe_section = html.escape(css_class)
        rows = "".join(file_div(f, f_icon, key) for f in files)
        sections.append(
            f'<div class="section {css_class}" data-section="{safe_section}">'
            f'<div class="section-header">'
            f'<input type="checkbox" class="cb section-cb" data-section="{safe_section}">'
            f'<span class="section-label">{label} ({len(files)})</span>'
            f'</div>'
            f'{rows}</div>'
        )
    for key, files in groups.items():
        if key in seen or not files:
            continue
        total_files += len(files)
        safe_section = "other_" + html.escape(key)
        rows = "".join(file_div(f, ICO_FILE, key) for f in files)
        sections.append(
            f'<div class="section other" data-section="{safe_section}">'
            f'<div class="section-header">'
            f'<input type="checkbox" class="cb section-cb" data-section="{safe_section}">'
            f'<span class="section-label">{html.escape(key)} ({len(files)})</span>'
            f'</div>'
            f'{rows}</div>'
        )

    if sections:
        toolbar = (
            f'<div class="sel-toolbar">'
            f'<button type="button" class="sel-btn" id="sel-all-btn">Select all</button>'
            f'<span class="sel-count" id="sel-count">0 / {total_files} selected</span>'
            f'</div>'
        )
        files_body = toolbar + "".join(sections)
    else:
        files_body = f'<div class="clean">{ICO_CLEAN} Working tree clean</div>'

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
var REPO_PATH = {json.dumps(path)};

function setStatus(msg, cls) {{
  var bar = document.getElementById('status-bar');
  var txt = document.getElementById('status-text');
  bar.className = 'status-bar ' + cls;
  txt.textContent = msg;
}}

function copyBranch(name) {{
  if (navigator.clipboard) {{
    navigator.clipboard.writeText(name).then(function() {{
      setStatus('Copied: ' + name, 'ok');
    }});
  }} else {{
    var ta = document.createElement('textarea');
    ta.value = name;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    setStatus('Copied: ' + name, 'ok');
  }}
}}

function onResult(resultJson) {{
  try {{
    var r = JSON.parse(resultJson);
    setStatus(r.message || (r.ok ? 'Done' : 'Failed'), r.ok ? 'ok' : 'err');
  }} catch(e) {{
    setStatus(String(resultJson), 'err');
  }}
}}

function onMutatingResult(resultJson) {{
  try {{
    var r = JSON.parse(resultJson);
    setStatus(r.message || (r.ok ? 'Done' : 'Failed'), r.ok ? 'ok' : 'err');
    if (r.ok) refreshContent();
  }} catch(e) {{
    setStatus(String(resultJson), 'err');
  }}
}}

function doCheckout(branch) {{
  setStatus('Switching to ' + branch + '\u2026', 'loading');
  iterm2Invoke(
    'git_status_bar_action(session_id: "' + SESSION_ID + '", action: "checkout", arg: "' + escArg(branch) + '")',
    'onMutatingResult'
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

function escArg(s) {{
  return String(s).replace(/\\\\/g, '\\\\\\\\').replace(/"/g, '\\\\"');
}}

var MUTATING_ACTIONS = {{commit:1, push:1, pull:1, checkout:1, new_branch:1, gitignore:1}};

function doAction(action, argStr) {{
  setStatus(action.charAt(0).toUpperCase() + action.slice(1) + '\u2026', 'loading');
  var a = argStr == null ? "" : escArg(argStr);
  var cb = MUTATING_ACTIONS[action] ? 'onMutatingResult' : 'onResult';
  iterm2Invoke(
    'git_status_bar_action(session_id: "' + SESSION_ID + '", action: "' + action + '", arg: "' + a + '")',
    cb
  );
}}

function getSelectedFiles() {{
  var out = [];
  document.querySelectorAll('.file-cb:checked').forEach(function(cb) {{
    out.push(cb.getAttribute('data-file'));
  }});
  return out;
}}

function updateSelectionUI() {{
  var allFileCbs = document.querySelectorAll('.file-cb');
  var total = allFileCbs.length;
  var selected = getSelectedFiles();
  var count = selected.length;

  var countEl = document.getElementById('sel-count');
  if (countEl) {{
    countEl.textContent = count + ' / ' + total + ' selected';
    countEl.classList.toggle('has-selection', count > 0);
  }}

  var selAllBtn = document.getElementById('sel-all-btn');
  if (selAllBtn) {{
    selAllBtn.textContent = (count === total && total > 0) ? 'Deselect all' : 'Select all';
  }}

  document.querySelectorAll('.section').forEach(function(sec) {{
    var cbs = sec.querySelectorAll('.file-cb');
    var checked = sec.querySelectorAll('.file-cb:checked').length;
    var secCb = sec.querySelector('.section-cb');
    if (!secCb) return;
    if (checked === 0) {{
      secCb.checked = false;
      secCb.indeterminate = false;
    }} else if (checked === cbs.length) {{
      secCb.checked = true;
      secCb.indeterminate = false;
    }} else {{
      secCb.checked = false;
      secCb.indeterminate = true;
    }}
  }});

  updateCommitUI();
}}

var INPUT_MODE = 'commit'; // 'commit' | 'branch'

function setInputMode(mode) {{
  INPUT_MODE = mode;
  var wrap = document.getElementById('commit-input-wrap');
  var input = document.getElementById('commit-input');
  var newBtn = document.getElementById('new-branch-btn');
  if (wrap) wrap.classList.toggle('mode-branch', mode === 'branch');
  if (newBtn) newBtn.classList.toggle('active', mode === 'branch');
  if (input) {{
    input.placeholder = (mode === 'branch')
      ? 'Branch name\u2026 (press Enter to create)'
      : 'Commit message\u2026';
  }}
  updateCommitUI();
}}

function updateCommitUI() {{
  var selected = getSelectedFiles();
  var wrap = document.getElementById('commit-input-wrap');
  var input = document.getElementById('commit-input');
  var btn = document.getElementById('commit-btn');
  var hasSel = selected.length > 0;
  var isBranch = (INPUT_MODE === 'branch');

  if (wrap) {{
    if (hasSel || isBranch) wrap.classList.add('show');
    else {{
      wrap.classList.remove('show');
      if (input) input.value = '';
    }}
  }}
  if (btn) {{
    var msg = input ? input.value.trim() : '';
    var enabled = !isBranch && hasSel && msg.length > 0;
    btn.disabled = !enabled;
    btn.classList.toggle('disabled', !enabled);
    btn.querySelector('.commit-label').textContent =
      hasSel ? ('Commit (' + selected.length + ')') : 'Commit';
  }}
}}

function doCommit() {{
  var input = document.getElementById('commit-input');
  var msg = input ? input.value.trim() : '';
  var files = getSelectedFiles();
  if (!msg || files.length === 0) return;
  var payload = JSON.stringify({{message: msg, files: files}});
  setStatus('Committing\u2026', 'loading');
  iterm2Invoke(
    'git_status_bar_action(session_id: "' + SESSION_ID + '", action: "commit", arg: "' + escArg(payload) + '")',
    'onMutatingResult'
  );
}}

function doCreateBranch() {{
  var input = document.getElementById('commit-input');
  var name = input ? input.value.trim() : '';
  if (!name) return;
  // basic client-side validation
  if (!/^[A-Za-z0-9._\\/\\-]+$/.test(name)) {{
    setStatus('Invalid branch name', 'err');
    return;
  }}
  setStatus('Creating branch\u2026', 'loading');
  iterm2Invoke(
    'git_status_bar_action(session_id: "' + SESSION_ID + '", action: "new_branch", arg: "' + escArg(name) + '")',
    'onMutatingResult'
  );
  if (input) input.value = '';
  setInputMode('commit');
}}

function joinPath(base, rel) {{
  if (!base) return rel;
  if (rel.charAt(0) === '/') return rel;
  var b = base.replace(/\\/+$/, '');
  return b + '/' + rel;
}}

function basename(p) {{
  var parts = String(p).split('/');
  return parts[parts.length - 1] || p;
}}

function copyToClipboard(text, label, rowEl) {{
  var done = function() {{
    setStatus((label ? label + ': ' : 'Copied: ') + text, 'ok');
    if (rowEl) {{
      rowEl.classList.remove('copied');
      void rowEl.offsetWidth;
      rowEl.classList.add('copied');
      setTimeout(function() {{ rowEl.classList.remove('copied'); }}, 750);
    }}
  }};
  if (navigator.clipboard) {{
    navigator.clipboard.writeText(text).then(done, done);
  }} else {{
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try {{ document.execCommand('copy'); }} catch(e) {{}}
    document.body.removeChild(ta);
    done();
  }}
}}

var CTX_ICONS = {{
  check:  "<svg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'><polyline points='20 6 9 17 4 12'/></svg>",
  copy:   "<svg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><rect x='9' y='9' width='13' height='13' rx='2' ry='2'/><path d='M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1'/></svg>",
  rel:    "<svg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><polyline points='10 17 15 12 10 7'/><line x1='4' y1='12' x2='15' y2='12'/></svg>",
  abs:    "<svg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><line x1='3' y1='12' x2='21' y2='12'/><polyline points='16 7 21 12 16 17'/><line x1='21' y1='4' x2='21' y2='20'/></svg>",
  finder: "<svg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><path d='M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z'/></svg>",
  ignore: "<svg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><circle cx='12' cy='12' r='9'/><line x1='5.6' y1='5.6' x2='18.4' y2='18.4'/></svg>"
}};

function hideContextMenu() {{
  var m = document.getElementById('ctx-menu');
  if (!m) return;
  m.classList.remove('show');
  setTimeout(function() {{ if (m && !m.classList.contains('show')) m.remove(); }}, 140);
}}

function showContextMenu(x, y, filepath, rowEl) {{
  hideContextMenu();

  var absPath = joinPath(REPO_PATH, filepath);
  var fname = basename(filepath);
  var status = rowEl ? rowEl.getAttribute('data-status') : '';
  var isUntracked = (status === '?');
  var canIgnore = isUntracked && fname !== '.gitignore';

  var menu = document.createElement('div');
  menu.id = 'ctx-menu';
  menu.className = 'ctx-menu';

  var header = document.createElement('div');
  header.className = 'ctx-header';
  header.textContent = fname;
  menu.appendChild(header);

  var items = [];
  if (canIgnore) {{
    items.push({{ icon: CTX_ICONS.ignore, label: 'Add to .gitignore', action: function() {{
        doAction('gitignore', filepath);
    }}}});
    items.push({{ sep: true }});
  }}
  items = items.concat([
    {{ icon: CTX_ICONS.check,  label: 'Select',              action: function() {{
        var cb = rowEl ? rowEl.querySelector('.file-cb') : null;
        if (cb) {{ cb.checked = !cb.checked; updateSelectionUI(); }}
    }}}},
    {{ sep: true }},
    {{ icon: CTX_ICONS.copy,   label: 'Copy name',           action: function() {{
        copyToClipboard(fname, 'Name copied', rowEl);
    }}}},
    {{ icon: CTX_ICONS.rel,    label: 'Copy relative path',  action: function() {{
        copyToClipboard(filepath, 'Relative copied', rowEl);
    }}}},
    {{ icon: CTX_ICONS.abs,    label: 'Copy absolute path',  action: function() {{
        copyToClipboard(absPath, 'Absolute copied', rowEl);
    }}}},
    {{ sep: true }},
    {{ icon: CTX_ICONS.finder, label: 'Reveal in Finder',    action: function() {{
        doAction('reveal', filepath);
    }}}}
  ]);

  items.forEach(function(it) {{
    if (it.sep) {{
      var s = document.createElement('div');
      s.className = 'ctx-sep';
      menu.appendChild(s);
      return;
    }}
    var row = document.createElement('div');
    row.className = 'ctx-item';
    row.innerHTML =
      '<span class="ctx-icon">' + it.icon + '</span>' +
      '<span class="ctx-label">' + it.label + '</span>';
    row.addEventListener('mousedown', function(e) {{ e.preventDefault(); }});
    row.addEventListener('click', function(e) {{
      e.preventDefault();
      e.stopPropagation();
      hideContextMenu();
      it.action();
    }});
    menu.appendChild(row);
  }});

  document.body.appendChild(menu);

  // Position with edge-clamp
  var vw = window.innerWidth, vh = window.innerHeight;
  menu.style.left = '0px';
  menu.style.top = '0px';
  var rect = menu.getBoundingClientRect();
  var mw = rect.width, mh = rect.height;
  var posX = x, posY = y;
  if (posX + mw + 6 > vw) posX = Math.max(4, vw - mw - 6);
  if (posY + mh + 6 > vh) posY = Math.max(4, y - mh);
  if (posY < 4) posY = 4;
  menu.style.left = posX + 'px';
  menu.style.top = posY + 'px';

  requestAnimationFrame(function() {{ menu.classList.add('show'); }});
}}

function copyFilename(filepath, nameEl) {{
  var rowEl = nameEl ? nameEl.closest('.file') : null;
  var done = function() {{
    setStatus('Copied: ' + filepath, 'ok');
    if (rowEl) {{
      rowEl.classList.remove('copied');
      void rowEl.offsetWidth;
      rowEl.classList.add('copied');
      setTimeout(function() {{ rowEl.classList.remove('copied'); }}, 750);
    }}
  }};
  if (navigator.clipboard) {{
    navigator.clipboard.writeText(filepath).then(done, done);
  }} else {{
    var ta = document.createElement('textarea');
    ta.value = filepath;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    try {{ document.execCommand('copy'); }} catch(e) {{}}
    document.body.removeChild(ta);
    done();
  }}
}}

function refreshContent(afterMsg) {{
  var onRefresh = 'onRefreshResult';
  window[onRefresh] = function(resultJson) {{
    try {{
      var r = JSON.parse(resultJson);
      if (!r || !r.ok || !r.html) return;
      var doc = new DOMParser().parseFromString(r.html, 'text/html');
      var newScroll = doc.querySelector('.scroll-area');
      var curScroll = document.querySelector('.scroll-area');
      if (newScroll && curScroll) {{
        // preserve scroll position
        var scrollTop = curScroll.scrollTop;
        curScroll.innerHTML = newScroll.innerHTML;
        curScroll.scrollTop = scrollTop;
      }}
      var newBadge = doc.querySelector('.header-badge');
      var curBadge = document.querySelector('.header-badge');
      if (newBadge && curBadge) curBadge.textContent = newBadge.textContent;
      var newBranch = doc.querySelector('.header-branch');
      var curBranch = document.querySelector('.header-branch');
      if (newBranch && curBranch) curBranch.textContent = newBranch.textContent;
      // reset selection state & input mode
      INPUT_MODE = 'commit';
      attachFileListeners();
      updateSelectionUI();
      if (afterMsg) setStatus(afterMsg, 'ok');
    }} catch (e) {{}}
  }};
  iterm2Invoke(
    'git_status_bar_action(session_id: "' + SESSION_ID + '", action: "refresh", arg: "")',
    onRefresh
  );
}}

function attachFileListeners() {{
  // File rows
  document.querySelectorAll('.file').forEach(function(el) {{
    if (el.dataset.bound) return;
    el.dataset.bound = '1';
    el.addEventListener('dblclick', function(e) {{
      var t = e.target;
      if (t.classList && (t.classList.contains('cb') || t.classList.contains('diff-btn'))) return;
      if (t.closest && t.closest('.diff-btn')) return;
      e.preventDefault();
      var filepath = el.getAttribute('data-file');
      if (filepath) doDiff(filepath);
    }});
    el.addEventListener('contextmenu', function(e) {{
      var t = e.target;
      if (t.classList && (t.classList.contains('cb') || t.classList.contains('diff-btn'))) return;
      if (t.closest && t.closest('.diff-btn')) return;
      e.preventDefault();
      e.stopPropagation();
      var filepath = el.getAttribute('data-file');
      if (filepath) showContextMenu(e.clientX, e.clientY, filepath, el);
    }});
  }});

  // Filename single-click → copy
  document.querySelectorAll('.file .f-name').forEach(function(nameEl) {{
    if (nameEl.dataset.bound) return;
    nameEl.dataset.bound = '1';
    var clickTimer = null;
    nameEl.addEventListener('mousedown', function(e) {{ e.preventDefault(); }});
    nameEl.addEventListener('click', function(e) {{
      e.stopPropagation();
      e.preventDefault();
      if (clickTimer) return;
      clickTimer = setTimeout(function() {{
        clickTimer = null;
        var filepath = nameEl.getAttribute('data-file');
        if (filepath) copyFilename(filepath, nameEl);
      }}, 220);
    }});
    nameEl.addEventListener('dblclick', function(e) {{
      if (clickTimer) {{ clearTimeout(clickTimer); clickTimer = null; }}
    }});
  }});

  // Diff buttons
  document.querySelectorAll('.diff-btn').forEach(function(btn) {{
    if (btn.dataset.bound) return;
    btn.dataset.bound = '1';
    btn.addEventListener('mousedown', function(e) {{ e.stopPropagation(); e.preventDefault(); }});
    btn.addEventListener('click', function(e) {{
      e.stopPropagation();
      e.preventDefault();
      var filepath = btn.getAttribute('data-diff');
      if (filepath) doDiffView(filepath);
    }});
  }});

  // File checkboxes
  document.querySelectorAll('.file-cb').forEach(function(cb) {{
    if (cb.dataset.bound) return;
    cb.dataset.bound = '1';
    cb.addEventListener('click', function(e) {{ e.stopPropagation(); }});
    cb.addEventListener('change', function() {{ updateSelectionUI(); }});
  }});

  // Section checkboxes
  document.querySelectorAll('.section-cb').forEach(function(cb) {{
    if (cb.dataset.bound) return;
    cb.dataset.bound = '1';
    cb.addEventListener('click', function(e) {{ e.stopPropagation(); }});
    cb.addEventListener('change', function() {{
      var sec = cb.closest('.section');
      if (!sec) return;
      var checked = cb.checked;
      sec.querySelectorAll('.file-cb').forEach(function(fcb) {{ fcb.checked = checked; }});
      updateSelectionUI();
    }});
  }});

  // Select all
  var selAllBtn = document.getElementById('sel-all-btn');
  if (selAllBtn && !selAllBtn.dataset.bound) {{
    selAllBtn.dataset.bound = '1';
    selAllBtn.addEventListener('click', function(e) {{
      e.preventDefault();
      var all = document.querySelectorAll('.file-cb');
      var total = all.length;
      var checked = document.querySelectorAll('.file-cb:checked').length;
      var newState = !(checked === total && total > 0);
      all.forEach(function(cb) {{ cb.checked = newState; }});
      updateSelectionUI();
    }});
  }}

  // Branch rows (double-click checkout, copy button)
  document.querySelectorAll('.branch-item').forEach(function(el) {{
    if (el.dataset.bound) return;
    el.dataset.bound = '1';
    el.addEventListener('mousedown', function(e) {{ e.preventDefault(); }});
    el.addEventListener('dblclick', function(e) {{
      e.preventDefault();
      var branch = el.getAttribute('data-branch');
      if (branch) doCheckout(branch);
    }});
  }});
  document.querySelectorAll('.b-copy').forEach(function(el) {{
    if (el.dataset.bound) return;
    el.dataset.bound = '1';
    el.addEventListener('click', function(e) {{
      e.stopPropagation();
      e.preventDefault();
      var branch = el.getAttribute('data-branch');
      if (branch) copyBranch(branch);
    }});
  }});

  // New branch button
  var newBtn = document.getElementById('new-branch-btn');
  if (newBtn && !newBtn.dataset.bound) {{
    newBtn.dataset.bound = '1';
    newBtn.addEventListener('click', function(e) {{
      e.preventDefault();
      e.stopPropagation();
      var input = document.getElementById('commit-input');
      if (INPUT_MODE === 'branch') {{
        if (input) input.value = '';
        setInputMode('commit');
      }} else {{
        setInputMode('branch');
        if (input) {{
          input.value = '';
          setTimeout(function() {{ input.focus(); }}, 30);
        }}
      }}
    }});
  }}
}}

document.addEventListener('DOMContentLoaded', function() {{
  attachFileListeners();

  // Dismiss context menu
  document.addEventListener('mousedown', function(e) {{
    var m = document.getElementById('ctx-menu');
    if (m && !m.contains(e.target)) hideContextMenu();
  }});
  document.addEventListener('keydown', function(e) {{
    if (e.key === 'Escape') hideContextMenu();
  }});
  var scrollArea = document.querySelector('.scroll-area');
  if (scrollArea) scrollArea.addEventListener('scroll', hideContextMenu);
  window.addEventListener('blur', hideContextMenu);
  window.addEventListener('resize', hideContextMenu);
  document.addEventListener('contextmenu', function(e) {{
    // Suppress default browser context menu anywhere outside file rows
    if (!e.target.closest('.file')) e.preventDefault();
  }});

  // Commit / branch input
  var input = document.getElementById('commit-input');
  if (input) {{
    input.addEventListener('input', updateCommitUI);
    input.addEventListener('keydown', function(e) {{
      if (e.key === 'Enter') {{
        e.preventDefault();
        if (INPUT_MODE === 'branch') doCreateBranch();
        else doCommit();
      }} else if (e.key === 'Escape') {{
        e.preventDefault();
        if (INPUT_MODE === 'branch') {{
          input.value = '';
          setInputMode('commit');
        }} else {{
          document.querySelectorAll('.file-cb').forEach(function(cb) {{ cb.checked = false; }});
          updateSelectionUI();
        }}
      }}
    }});
  }}

  // Commit button
  var commitBtn = document.getElementById('commit-btn');
  if (commitBtn) {{
    commitBtn.addEventListener('click', function(e) {{
      e.preventDefault();
      if (commitBtn.disabled) return;
      doCommit();
    }});
  }}

  updateSelectionUI();
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
        # Inline commit input (shown when files selected)
        f"<div id='commit-input-wrap' class='commit-input-wrap'>"
        f"<input id='commit-input' class='commit-input' type='text' "
        f"placeholder='Commit message\u2026' autocomplete='off' spellcheck='false'>"
        f"</div>"
        # Action buttons
        f"<div class='actions'>"
        f"<button id='commit-btn' class='commit disabled' disabled>"
        f"{ICO_COMMIT}&nbsp;<span class='commit-label'>Commit</span></button>"
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
            try:
                payload = json.loads(arg) if arg else {}
            except (ValueError, TypeError):
                return json.dumps({"ok": False, "message": "Invalid commit payload"})
            message = (payload.get("message") or "").strip()
            files = payload.get("files") or []
            if not message:
                return json.dumps({"ok": False, "message": "Empty commit message"})
            if not files:
                return json.dumps({"ok": False, "message": "No files selected"})
            ok, msg = await loop.run_in_executor(
                None, _git_commit, path, message, files
            )
            return json.dumps({"ok": ok, "message": msg})

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

        elif action == "reveal":
            ok, msg = await loop.run_in_executor(None, _reveal_in_finder, path, arg)
            return json.dumps({"ok": ok, "message": msg})

        elif action == "gitignore":
            ok, msg = await loop.run_in_executor(None, _add_to_gitignore, path, arg)
            return json.dumps({"ok": ok, "message": msg})

        elif action == "refresh":
            html_str = await loop.run_in_executor(None, _popover_html, path, session_id)
            return json.dumps({"ok": True, "message": "", "html": html_str})

        elif action == "new_branch":
            ok, msg = await loop.run_in_executor(None, _git_new_branch, path, arg)
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
