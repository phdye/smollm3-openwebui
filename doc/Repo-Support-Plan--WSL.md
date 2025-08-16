# Repo-Support-Plan

This plan describes stepwise features to transform the interactive environment to support persistent, preconfigured, collaborative development sessions.

**Current status:** Phases&nbsp;1–6 are implemented in `scripts/wsl_workspace.py`.  Phases&nbsp;7 and 8 are still future work.

## Phase 1: Persistent Workspace
- [x] Set up connection to a WSL distro that remains active during chat session.
- [x] Maintain path to repo folder.
- [x] Provide command to suspend/resume environment.
- [x] Deliver minimal environment for baseline editing and script execution.

Implemented via `scripts/wsl_workspace.py`, which opens the selected WSL
distribution in the repository directory, installs basic tools (Python and
Git) if missing, and exposes `start`/`resume` and `suspend` actions.

## Phase 2: Preconfigured Tooling
- [x] Ensure that system has pre-installed at least these common languages :
  - C/C++, Rust, Python Development (compilers, linters, test runners)
  - Corresponding compilers, linters, test runners

- [x] Provide chat command wrappers (`!test`, `!lint`, `!build`).
- [x] Document default environment and configuration.

`scripts/wsl_workspace.py` now installs `build-essential`, `clang`, `rustc`
with `cargo`, and Python tooling (`pip`, `flake8`, `pytest`) so a fresh WSL
instance is ready to lint, test, or build.  New actions `test`, `lint`, and
`build` execute the corresponding commands inside the repository directory.

## Phase 3: Integrated Git Operations
- [x] Implement chat commands for `git pull`, `git status`, `git commit`, and `git push`.
- [x] Show diff previews and commit message suggestions.
- [x] Link to GitHub Issues and PRs.
- [x] Implement chat command runner '$' to run any shell commands in the repo.

`scripts/wsl_workspace.py` exposes `pull`, `status`, `commit`, and `push` actions
that execute within the repository and stream their output back to chat. The
`commit` action previews diffs and proposes commit messages derived from the
changed files.  Commands `issue <id>` and `pr <id>` open the corresponding
GitHub links, and the special `$` action runs arbitrary shell commands rooted
at the repo path.

## Phase 4: Incremental Environment Setup
- [x] Cache dependency installations per repo.
- [x] Provide snapshot/rollback features to revert to prior state.

`scripts/wsl_workspace.py` caches dependency installation by writing a marker
file in the repository after packages are installed.  New `snapshot` and
`rollback` actions create and restore tarball snapshots of the repository so
work can be reverted to the previous state.

## Phase 5: Real-time Testing & Feedback
- [x] Execute tests asynchronously and stream logs back to chat.
- [x] Highlight failing lines and stack traces in context.

`scripts/wsl_workspace.py` uses `asyncio` to stream `pytest` output in real
time and emphasizes failing lines and stack traces in red for immediate
context.

## Phase 6: Collaborative Features
- [x] Allow multiple users to attach to same environment.
- [x] Provide session log to track contributions.
- [x] Implement follow mode for real-time command/output sharing.

`start`/`resume` now launch or attach to a shared `tmux` session that logs all
activity to `wsl_session.log`.  A new `follow` action tails this log so other
users can watch commands and output in real time.

## Phase 7: Customizable Templates
- [ ] Provide repo-specific environment templates.
- [ ] Support starter scripts accessible via short chat commands (`!run-tests`, `!start-devserver`).

*Not yet implemented.*

## Phase 8: Security & Resource Controls
- [ ] Sandbox each session with limited network and compute quotas.
- [ ] Expose resource monitoring commands for CPU/memory.
- [ ] Implement auto-timeouts for idle sessions.

## Maintenance
- Keep base images updated with patches.
- Log usage and performance metrics to refine features.
