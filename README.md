# iterm2-git-status

> An interactive, per-session git status panel for iTerm2's status bar — branch switcher, file diff viewer, and quick Commit/Push/Pull actions, all from a single click.

![iTerm2 Git Status Bar](https://img.shields.io/badge/iTerm2-3.3%2B-blue?logo=apple-terminal) ![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python) ![License: MIT](https://img.shields.io/badge/License-MIT-green)

---

## What it does

Each iTerm2 session independently shows:

- **Status bar** — always visible: `⎇ main ✓` when clean, `⎇ main* 4 files` when dirty
- **Interactive popover on click** — a full dark-themed panel with:
  - Collapsible **local and remote branch lists** — double-click any branch to checkout
  - **Changed files** grouped by status (Staged, Modified, Deleted, Untracked) — double-click to open in editor, click the diff icon to open a two-pane HEAD vs working copy diff
  - Quick action buttons: **Commit**, **Push**, **Pull**
  - **Editor picker** — select your preferred editor once via a native macOS file picker, saved for future use

Changes are reflected:
- **Instantly** when you `cd` to a different directory (uses iTerm2 Shell Integration)
- **Within 5 seconds** after a `git commit`, `git checkout`, `git stash`, etc.

Every terminal session shows its **own** git state — completely independent, no shared global state.

---

## Screenshots

```
Status bar (clean):       ⎇ main ✓
Status bar (dirty):       ⎇ feature/auth* 3 files

Popover on click:
┌────────────────────────────────────────┐
│ ⎇ feature/auth  —  3 changes          │
├────────────────────────────────────────┤
│ ▶ LOCAL (3)          ▶ REMOTE (5)      │
│   * main                               │
│     feature/auth  ← current            │
│     fix/login                          │
├────────────────────────────────────────┤
│ STAGED (1)                             │
│   ● src/auth.py                  [±]   │
│ MODIFIED (1)                           │
│   ● src/utils.py                 [±]   │
│ UNTRACKED (1)                          │
│   ● tests/test_auth.py           [±]   │
├────────────────────────────────────────┤
│ [Commit]   [Push]   [Pull]  [editor]   │
│ ● ready                                │
└────────────────────────────────────────┘
```

The `[±]` diff icon appears on hover next to each file and opens the two-pane diff view in your editor.

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

## Usage

### Status bar

| Display | Meaning |
|---|---|
| `⎇ main ✓` | On branch `main`, working tree clean |
| `⎇ main* 3 files` | On branch `main`, 3 uncommitted changes |

Click the component to open the interactive popover.

### Branch panel

The popover shows two collapsible sections — **Local** and **Remote** — with branch counts. Click the header to expand/collapse. The current branch is highlighted with a `✓` marker.

**Double-click** any branch to checkout. A native macOS confirmation dialog will appear before switching.

### File list

Changed files are grouped by status:

| Badge | Meaning |
|---|---|
| `Staged` | Files added to the index (`git add`) |
| `Modified` | Tracked files with unstaged changes |
| `Deleted` | Files removed from the working tree |
| `Untracked` | New files not yet tracked by git |

**Double-click** a file to open it in your configured editor.

**Hover** over a file to reveal the `⊞` diff icon on the right. **Click it** to open a two-pane HEAD vs working copy diff directly in your editor (uses `--diff` flag).

### Action buttons

| Button | Action |
|---|---|
| **Commit** | Opens a native text input dialog for the commit message, then runs `git commit -m "..."` |
| **Push** | Confirms, then runs `git push` |
| **Pull** | Confirms, then runs `git pull` |
| **editor name** | Opens a native macOS file picker in `/Applications` to select or change your preferred editor |

All actions show a status indicator at the bottom of the popover (green dot = success, red = error, pulsing yellow = in progress).

### Editor configuration

On first use of any file-opening action, a native macOS file picker opens in `/Applications`. Select your editor app (VS Code, Cursor, Sublime Text, etc.).

The script automatically resolves the internal CLI path from the `.app` bundle. The selection is saved to:

```
~/Library/Application Support/iTerm2/Scripts/AutoLaunch/git_status_bar_config.json
```

To change the editor later, click the editor name button in the action bar.

---

## How it works

```
┌─────────────────────────────────────────────────────────────────┐
│  iTerm2 Session                                                  │
│                                                                  │
│  path variable ──► StatusBarRPC ──► git status ──► ⎇ text       │
│  (changes on cd)   (per-session)    (subprocess)   in bar       │
│                                                                  │
│  poll every 5s ──► set user.gitstatus_tick ──► re-trigger RPC   │
│                                                                  │
│  click on bar ──► git_status_click RPC ──► popover HTML         │
│                                                                  │
│  JS in popover ──► iterm2Invoke() ──► git_status_bar_action RPC │
│                    (WebKit bridge)     checkout / commit /       │
│                                        push / pull / diff        │
└─────────────────────────────────────────────────────────────────┘
```

- **`iterm2.StatusBarComponent`** registers the component with iTerm2
- **`@iterm2.StatusBarRPC`** with `iterm2.Reference("path?")` re-executes on every `cd`
- **`poll_tick()`** increments `user.gitstatus_tick` every 5 seconds on every session, catching `git commit`, `git checkout`, etc.
- **`@iterm2.RPC git_status_click`** generates and opens the popover HTML on click
- **`@iterm2.RPC git_status_bar_action`** handles all interactive actions from the popover via the iTerm2 JavaScript bridge (`iterm2Invoke()`)
- **`iterm2.Alert` / `iterm2.TextInputAlert`** provide native macOS confirmation and input dialogs
- **`osascript`** drives the native file picker for editor selection
- Diff view uses `code --diff <tmp_HEAD_file> <working_copy>` to show a two-pane comparison

---

## File structure

```
iterm2-git-status/
├── git_status_bar.py                  # The AutoLaunch daemon script
└── README.md

# Auto-created at runtime:
~/Library/Application Support/iTerm2/Scripts/AutoLaunch/
└── git_status_bar_config.json         # Saved editor preference
```

---

## Troubleshooting

**Status bar shows nothing / stays empty**

- Verify Shell Integration is installed: `echo $ITERM_SHELL_INTEGRATION_INSTALLED` should print `Yes`
- Make sure the Python API is enabled: Settings → General → Magic → Enable Python API
- Check the script console: Scripts → Manage → Open Script Console

**Component does not appear in the "Configure Status Bar" list**

- Open the Script Console and look for errors
- Try stopping and re-running: Scripts → AutoLaunch → git_status_bar

**Popover does not open on click**

- Click directly on the text of the component, not on empty space around it

**Double-click on branch/file does nothing**

- Make sure the script is running (check Script Console for errors)
- The `iterm2Invoke` JavaScript bridge requires iTerm2 3.3+

**Diff view opens without differences**

- The file may be untracked (no HEAD version exists) — the file will open normally instead
- Ensure the file has been modified since the last commit

**Editor picker doesn't appear / wrong editor opens**

- Click the editor name button in the action bar to re-select
- The config is stored in `~/Library/Application Support/iTerm2/Scripts/AutoLaunch/git_status_bar_config.json` — delete it to reset

**Works in local sessions but not on SSH**

- Shell Integration must be installed on the remote host too

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
