# iterm2-git-status

> An interactive, per-session git status panel for iTerm2's status bar — branch switcher, file diff viewer, and quick Commit/Push/Pull actions, all from a single click.

![iTerm2 Git Status Bar](https://img.shields.io/badge/iTerm2-3.3%2B-blue?logo=apple-terminal) ![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python) ![License: MIT](https://img.shields.io/badge/License-MIT-green)

---

## What it does

Each iTerm2 session independently shows:

- **Status bar** — always visible: `⎇ main ✓` when clean, `⎇ main* 4 files` when dirty
- **Interactive popover on click** — a full dark-themed panel with:
  - Collapsible **local and remote branch lists** — double-click any branch to checkout, click the copy icon to copy the branch name to clipboard
  - **`+` button next to Local** — inline branch creator: enter a name in the commit input (switches to blue "branch mode") and press Enter to `git checkout -b`
  - **Changed files** grouped by status (Staged, Modified, Deleted, Untracked) — each row shows per-file `+added -deleted` line counts (omitted for untracked and shown as `bin` for binary files)
  - **Checkboxes** on every file and section header, with a global "Select all" / "Deselect all" toggle and a live `N / M selected` counter
  - **Inline commit input** that slides in above the action bar as soon as you select at least one file. Press Enter to commit only the selected files; press Esc to cancel the selection
  - **Single-click** on a filename copies the relative path to the clipboard, with a green flash animation on the row
  - **Right-click context menu** (themed, not the browser default) with: Select, Copy name, Copy relative path, Copy absolute path, Reveal in Finder — plus **Add to .gitignore** for untracked files (auto-creates or appends to `.gitignore` at the repo root, handles files vs folders, deduplicates existing entries)
  - **Live refresh** — after any mutating action (commit, push/pull, checkout, new branch, add-to-.gitignore) the popover re-renders in place while preserving scroll position; no need to close and reopen it
  - Quick action buttons: **Commit** (disabled until a file is selected and a message is typed), **Push**, **Pull**
  - **Editor picker** — select your preferred editor once via a native macOS file picker, saved for future use

Changes are reflected:
- **Instantly** when you `cd` to a different directory (uses iTerm2 Shell Integration)
- **Instantly** inside the popover after any action you trigger from it
- **Within 5 seconds** after an external `git commit`, `git checkout`, `git stash`, etc.

Every terminal session shows its **own** git state — completely independent, no shared global state.

---

## Screenshots

```
Status bar (clean):       ⎇ main ✓
Status bar (dirty):       ⎇ feature/auth* 3 files

Popover on click:
┌──────────────────────────────────────────────────┐
│ ⎇ feature/auth  —  3 changes                    │
├──────────────────────────────────────────────────┤
│ ▶ LOCAL (3)                                  [+] │
│   * main                                         │
│     feature/auth  ← current                      │
│     fix/login                                    │
│ ▶ REMOTE (5)                                     │
├──────────────────────────────────────────────────┤
│ [ Select all ]                  1 / 3 selected   │
│                                                  │
│ [✓] STAGED (1)                                   │
│   [✓] ● src/auth.py         +12 -3        [±]   │
│ [–] MODIFIED (1)                                 │
│   [ ] ● src/utils.py        +4  -1        [±]   │
│ [ ] UNTRACKED (1)                                │
│   [ ] ● tests/test_auth.py                [±]   │
├──────────────────────────────────────────────────┤
│ > Commit message…                                │
├──────────────────────────────────────────────────┤
│ [Commit (1)]   [Push]   [Pull]     [editor]      │
│ ● ready                                          │
└──────────────────────────────────────────────────┘
```

- The `[±]` diff icon appears on hover and opens a two-pane HEAD vs working copy diff in your editor.
- The `[+]` next to `LOCAL` opens inline branch creation — the commit input turns blue and accepts a branch name.
- The commit input row only appears when at least one file is checked.
- Right-click a file for Copy name / relative / absolute path, Reveal in Finder, and (for untracked) Add to .gitignore.

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

**Click the copy icon** (appears on hover) next to any branch to copy its name to the clipboard. A confirmation message is shown in the status bar.

**Click the `+` button** in the Local section header to create a new branch inline: the commit input row switches to "branch mode" (blue accent + branch icon). Type a name, press Enter to run `git checkout -b <name>`. Press Esc or click `+` again to cancel.

### File list

Changed files are grouped by status:

| Badge | Meaning |
|---|---|
| `Staged` | Files added to the index (`git add`) |
| `Modified` | Tracked files with unstaged changes |
| `Deleted` | Files removed from the working tree |
| `Untracked` | New files not yet tracked by git |

Each row shows:
- A **checkbox** on the left (click a section header's checkbox to select/deselect all its files; the toolbar at the top toggles the entire list)
- The colored status icon
- The filename
- The `+added -deleted` line count from `git diff --numstat` (staged + unstaged merged per file). Untracked files don't show stats. Binary files show `bin`.
- A diff button (appears on hover)

**Single-click** a filename to copy the relative path to the clipboard — the row flashes green.

**Double-click** anywhere else on the row to open the file in your configured editor.

**Hover** over a file to reveal the `⊞` diff icon on the right. **Click it** to open a two-pane HEAD vs working copy diff directly in your editor (uses `--diff` flag).

**Right-click** any file to open the themed context menu:

| Menu item | Action |
|---|---|
| **Add to .gitignore** | Only for untracked files (hidden when the file is `.gitignore` itself). Creates `.gitignore` at the repo root if missing, or appends the relative path (with a trailing `/` for folders). Deduplicates existing entries. |
| **Select** | Toggles the row's checkbox. |
| **Copy name** | Copies the basename. |
| **Copy relative path** | Copies the path relative to the repo root. |
| **Copy absolute path** | Copies the full filesystem path. |
| **Reveal in Finder** | Opens the file's enclosing folder in Finder with the file highlighted (`open -R`). |

### Selection and commit

The action bar's **Commit** button is disabled until you have at least one file selected and have typed a commit message. The inline commit input appears above the action bar as soon as a file is checked.

- Select files (individually, by section, or via the "Select all" toolbar button).
- Type a commit message. Press **Enter** to commit, or click **Commit**.
- The commit runs `git add -- <files>` followed by `git commit -m <msg> -- <files>`, so only the selected files are staged and committed — any pre-existing staging of unselected files is left untouched.
- Press **Esc** in the input to clear the selection.

### Live refresh

Any action triggered from the popover that mutates git state (commit, push, pull, checkout, new branch, add-to-.gitignore) causes the popover to re-render in place. Scroll position is preserved, the selection is reset, and listeners are re-attached. You don't need to close and reopen the popover to see the updated file list or branch state.

### Action buttons

| Button | Action |
|---|---|
| **Commit (N)** | Commits only the selected files with the message from the inline input. Disabled when no selection or empty message. |
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
