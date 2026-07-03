# jira-tools installation prompt

This file is a **prompt for a Claude Code agent**, not documentation for a
human to read passively. Execute the steps below in order, with the user
sitting at the keyboard. Run every command from the root of the cloned
`jira-tools` repository (the user should already have cloned it before this
file is invoked) unless a step says otherwise.

General rules for every step:
- When a command fails, **surface its actual error output to the user and
  stop** — don't guess at a fix, don't retry blindly, and don't invent a
  cause the tool didn't report.
- Never print the contents of the config file or the API token anywhere in
  the conversation.
- These steps are safe to run again on a machine that's already fully set
  up — each step below detects existing state (uv already installed,
  `jira-tools` already on PATH, config file already present, `install.py`'s
  own idempotency) and skips or short-circuits accordingly rather than
  redoing work or asking redundant questions.

## Steps

### 1. Ensure `uv` is installed

Run:

```
uv --version
```

- **Succeeds** (prints a version) — continue to step 2.
- **Fails** (`uv` not found) — ask the user, via `AskUserQuestion`, to choose
  one of: **install uv automatically**, **I'll install it myself**, or
  **abort**.
  - *Install automatically*: fetch and follow the installation instructions
    at https://docs.astral.sh/uv/getting-started/installation/ for the
    user's OS (don't hard-code a single install command — the right one
    differs by platform). After running it, re-run `uv --version` to
    confirm. If it still fails, surface the error and stop.
  - *I'll install it myself*: stop here and tell the user to re-run this
    prompt once `uv` is installed.
  - *Abort*: stop the whole installation now.

### 2. Install the jira-tools CLI

Run, from the repo root:

```
uv tool install .
```

- **Fails** — surface the exact error and stop. Common causes: the user's
  Python is older than the required `>=3.12` (uv's error will say so; tell
  the user to install Python 3.12+, or run `uv python install 3.12` to let
  uv fetch one, then retry this step), or a build/dependency error (relay
  it verbatim; don't guess a fix).
- **Already installed** — uv will report that and no-op rather than
  silently reinstalling; that's fine, continue to the verification below.
  (If the user specifically wants to pick up local source changes, that
  needs `uv tool install . --force`, but that's not required for a normal
  install and shouldn't be run unless asked.)
- **Succeeds** — continue.

Then verify the tool is actually reachable. Run, from the home directory
(so you're testing the globally installed command, not something resolved
from the local project):

```
jira-tools version
```

- **Succeeds** (prints a version string) — installation of the CLI itself
  is done; continue to step 3.
- **Fails** (command not found, or any error) — surface the exact error and
  stop. If it's "command not found," the likely cause is that uv's tool bin
  directory isn't on `PATH` (commonly `~/.local/bin`); tell the user to
  check their `PATH` or open a new shell session, then retry this
  verification. Don't proceed to configuration until this passes.

### 3. Resolve the config file path

Before touching the filesystem, determine the exact path every later step
will use:

- If the environment variable `XDG_CONFIG_HOME` is set, the path is
  `$XDG_CONFIG_HOME/jira-tools/config.toml`.
- Otherwise, the path is `~/.config/jira-tools/config.toml`.

Call this the **resolved config path** — use it, not a hard-coded
`~/.config/...` path, in every step from here on.

### 4. Ensure the config directory exists

Check whether the parent directory of the resolved config path exists.

- **Exists** — continue.
- **Missing** — create it (e.g. `mkdir -p`) before continuing.

### 5. Handle an existing config file

Check whether a file already exists at the resolved config path.

- **Doesn't exist** — continue to step 6 to create it fresh.
- **Exists** — stop and ask the user, via `AskUserQuestion`, to choose
  exactly one of:
  - **Overwrite** — discard the existing file and go to step 6 to re-enter
    all three fields from scratch.
  - **Edit specific fields** — keep the file, ask which of `site_url` /
    `email` / `api_token` need changing, and update only those in step 6.
  - **Keep as-is** — leave the file untouched and skip straight to step 7.
  - **Abort** — stop the whole configuration step here, with no changes.

  Do not guess which of these the user wants; always ask explicitly. Never
  overwrite or modify an existing config file without the user choosing
  Overwrite or Edit specific fields.

### 6. Collect and write the config fields

For each field that needs to be set (all three, unless step 5 said to edit
only specific fields), ask the user one at a time:

- **`site_url`** — the Atlassian site URL, e.g. `https://acme.atlassian.net`.
- **`email`** — the email address on their Atlassian account.
- **`api_token`** — an API token. Tell the user to generate one at
  https://id.atlassian.com/manage-profile/security/api-tokens, and to click
  **"Create API token"** — not "Create API token with scopes".

Write (or update) the TOML file at the resolved config path with these
contents:

```toml
site_url = "..."
email = "..."
api_token = "..."
```

Immediately set the file's permissions to owner-only (`chmod 600 <resolved
path>`) so it never ends up group/other-readable in the first place.

- **Succeeds** — continue to step 7.
- **Fails to write** (e.g. permission denied) — surface the exact error and
  stop.

### 7. Verify credentials with `auth-check`

Run:

```
jira-tools auth-check
```

This may print a permission warning to stderr independently of whether the
check passes or fails, of the form:

    Warning: <path> is readable by group/other; run `chmod 600 <path>`.

If you see it:
- Tell the user the config file has looser permissions than recommended.
- Offer to run `chmod 600 <resolved config path>` for them, or let them run
  it themselves.
- This warning does not by itself mean the check failed — evaluate the
  PASS/FAIL result independently, below.

Now evaluate the result:

- **Prints a config error instead of PASS/FAIL lines** (e.g. "Config file
  ... is invalid" or "not found") — this can happen if step 5's "keep
  as-is" choice fed in a config file that's malformed or missing a field.
  Relay the exact error message and return to step 6 to fix the offending
  field(s), then re-run this step.
- **Both `Jira: PASS (...)` and `Confluence: PASS (...)`** — read the
  displayed name back to the user and ask them to confirm it's the correct
  account. 
  - Confirmed correct — configuration is done; continue to step 8.
  - User says it's the wrong account — treat this the same as a FAIL below.
- **Either line shows `FAIL (...)`** — relay the exact FAIL reason(s) to the
  user (never fabricate a cause beyond what was printed). Then ask, via
  `AskUserQuestion`, to choose one of:
  - **Let me help you fix it** — go back to step 6 for the specific
    field(s) that need correcting, then re-run this step.
  - **I'll fix it myself** — wait for the user to confirm they've made the
    change, then re-run this step.
  - **Abort setup** — stop the configuration step here. Tell the user
    steps 1–2 (uv and the CLI) are already done and don't need repeating;
    they can resume from step 3 by re-running this prompt whenever they're
    ready.

  Always offer the abort option on every FAIL, so the user is never forced
  into an unbounded retry loop.

### 8. Run the local installer

Run, from the repo root:

```
uv run python install.py
```

This copies the skill files into `~/.claude/skills/` and injects a
`jira-tools` usage block into `~/.claude/CLAUDE.md` between
`<!-- BEGIN jira-tools -->` / `<!-- END jira-tools -->` markers. It is
idempotent — safe to run again even on an already-set-up machine.

- **Succeeds** — it prints one `Installed skill: ...` line per skill and a
  final `Updated global memory: ~/.claude/CLAUDE.md` line. Installation is
  complete.
- **Fails** — this happens specifically when `~/.claude/CLAUDE.md` contains
  exactly one of the two sentinel markers (typically from manual editing).
  When it does:
  - Relay the exact stderr message to the user verbatim.
  - Do **not** attempt to edit `~/.claude/CLAUDE.md` yourself to fix the
    markers.
  - Tell the user they need to fix the marker pair by hand (remove the
    stray marker, or restore its missing partner) and then re-run
    `uv run python install.py`.
  - Note for context: the skill files under `~/.claude/skills/` are copied
    before this check runs, so they are already installed/updated even
    though this step reports failure — only the `CLAUDE.md` update needs a
    retry.

## Done

Installation is complete once: `jira-tools version` prints a version,
`jira-tools auth-check` shows `PASS` for both Jira and Confluence with a
name the user confirmed, and `uv run python install.py` has completed
successfully (skills installed, `~/.claude/CLAUDE.md` updated).
