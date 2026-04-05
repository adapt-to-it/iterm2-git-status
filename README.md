# iterm2-git-status

> A per-session git status indicator for iTerm2's status bar — shows your current branch, change count, and a click-to-expand file list grouped by status.

![iTerm2 Git Status Bar](https://img.shields.io/badge/iTerm2-3.3%2B-blue?logo=apple-terminal) ![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python) ![License: MIT](https://img.shields.io/badge/License-MIT-green)

---

## What it does

Each iTerm2 session independently shows:

- **Status bar** — always visible: `⎛ main* 4 files` or `⎛ main ✓` when clean
- **Popover on click** — full file list grouped by status (Staged, Modified, Deleted, Untracked), dark-themed HTML panel

Changes are reflected:
- **Instantly** when you `cd` to a different directory (uses iTerm2 Shell Integration)
- **Within 5 seconds** after a `git commit`, `git checkout`, `git stash`, etc.

Every terminal session shows its **own** git state — completely independent, no shared global state.

---

## Screenshots

```
Status bar (clean):       ⎛ main ✓
Status bar (dirty):       ⎛ feature/auth* 3 files

Popover on click:
┌─────────────────────────────┐
│ ⎛ feature/auth — 3 changes  │
├─────────────────────────────┤
│ STAGED (1)                  │
│   src/auth.py               │
│ MODIFIED (1)                │
│   src/utils.py              │
│ UNTRACKED (1)               │
│   tests/test_auth.py        │
└─────────────────────────────┘
```

---

## Requirements

| Requirement | Version |
|---|---|
| [iTerm2](https://iterm2.com) | 3.3 or later |
| macOS | 10.14 (Mojave) or later |
| Python | 3.8+ (via iTerm2 runtime) |
| [iTerm2 Shell Integration](https://iterm2.com/documentation-shell-integration.html) | Required |

**No external Python dependencies.** Uses only `stdlib` + the bundled `iterm2` package.

---

## Installation

### 1. Install iTerm2 Shell Integration

Shell Integration is required so that iTerm2 tracks the current working directory of each session.

```bash
curl -L https://iterm2.com/shell_integration/install_shell_integration.sh | bash
```

Then restart your shell (or open a new tab).

### 2. Enable the iTerm2 Python API

In iTerm2: **Settings → General → Magic → Enable Python API** ✓

### 3. Install the iTerm2 Python Runtime

In iTerm2: **Scripts → Manage → Install Python Runtime**

This is a one-time step. iTerm2 downloads a self-contained Python environment.

### 4. Install the script

Copy `git_status_bar.py` to the AutoLaunch folder:

```bash
mkdir -p ~/Library/Application\ Support/iTerm2/Scripts/AutoLaunch
cp git_status_bar.py ~/Library/Application\ Support/iTerm2/Scripts/AutoLaunch/
```

Or with curl directly:

```bash
mkdir -p ~/Library/Application\ Support/iTerm2/Scripts/AutoLaunch
curl -o ~/Library/Application\ Support/iTerm2/Scripts/AutoLaunch/git_status_bar.py \
  https://raw.githubusercontent.com/Nerjak/iterm2-git-status/main/git_status_bar.py
```

### 5. Restart iTerm2

The script starts automatically. You can also launch it manually:
**Scripts → AutoLaunch → git_status_bar**

### 6. Add the component to your status bar

1. Open **Settings → Profiles → (your profile) → Session**
2. Enable **Status bar** ✓
3. Click **Configure Status Bar**
4. Drag **"Git Status"** into the bar
5. Click **OK**

The component will now appear in the status bar of every session.

---

## How it works

```
┌─────────────────────────────────────────────────────────────┐
│  iTerm2 Session                                             │
│                                                             │
│  path variable ──► StatusBarRPC ──► git status ──► text    │
│  (changes on cd)   (per-session)    (subprocess)   in bar  │
│                                                             │
│  poll every 5s ──► set user.gitstatus_tick ──► re-trigger  │
│  (all sessions)    (per-session variable)    RPC           │
│                                                             │
│  click on bar ──► @iterm2.RPC ──► popover HTML             │
└─────────────────────────────────────────────────────────────┘
```

- **`iterm2.StatusBarComponent`** registers the component with iTerm2
- **`@iterm2.StatusBarRPC`** with `iterm2.Reference("path?")` makes the coroutine re-execute automatically whenever the session's working directory changes — per session, with zero polling overhead for `cd` events
- A background `poll_tick()` task increments `user.gitstatus_tick` every 5 seconds on every open session, which triggers the RPC to re-run and pick up changes from `git commit`, `git checkout`, etc.
- **`@iterm2.RPC`** handles clicks and calls `component.async_open_popover()` with a fully formatted HTML panel

---

## File structure

```
iterm2-git-status/
├── git_status_bar.py   # The AutoLaunch daemon script
└── README.md
```

---

## Troubleshooting

**Status bar shows nothing / stays empty**

- Verify Shell Integration is installed and active: the prompt should have a colored marker, and `echo $ITERM_SHELL_INTEGRATION_INSTALLED` should print `Yes`
- Make sure the Python API is enabled: Settings → General → Magic → Enable Python API
- Check the script console: Scripts → Manage → Open Script Console

**Component does not appear in the "Configure Status Bar" list**

- Open the Script Console (Scripts → Manage → Open Script Console) and look for errors
- Try stopping and re-running the script from Scripts → AutoLaunch → git_status_bar

**Popover does not open on click**

- This is a known iTerm2 quirk: click directly on the text of the component, not on empty space around it

**Works in local sessions but not on SSH**

- Shell Integration must be installed on the remote host too
- Follow the [remote installation guide](https://iterm2.com/documentation-shell-integration.html)

---

## Contributing

Pull requests are welcome. For significant changes, please open an issue first.

When submitting a PR:
- Keep the zero-external-dependencies constraint
- Test with at least two simultaneous iTerm2 sessions in different git repos
- Ensure Python 3.8 compatibility

---

## License

[MIT](LICENSE)

---

## Related projects

- [iTerm2 Python API documentation](https://iterm2.com/python-api/)
- [iTerm2 Status Bar documentation](https://iterm2.com/documentation-status-bar.html)
- [iTerm2 Shell Integration](https://iterm2.com/documentation-shell-integration.html)
