# Repo-Support-Plan

This plan describes stepwise features to transform the interactive environment to support persistent, preconfigured, collaborative development sessions.

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

`scripts/wsl_workspace.py` wraps common Git workflows (`pull`, `status`, `commit`,
and `push`) and surfaces diffs with commit message hints. The new `$` action runs
arbitrary shell commands within the repository, enabling quick links to
GitHub Issues and PRs or any other tooling.

## Phase 4: Incremental Environment Setup
- [x] Cache dependency installations per repo.
- [x] Provide snapshot/rollback features to revert to prior state.

`scripts/wsl_workspace.py` persists downloaded packages in a per-repository
cache so subsequent sessions reuse previously installed dependencies. The tool
also exposes `snapshot` and `rollback` actions to capture and restore the
workspace state, enabling quick resets between experimentation steps.

## Phase 5: Real-time Testing & Feedback
- [x] Execute tests asynchronously and stream logs back to chat.
- [x] Highlight failing lines and stack traces in context.

`scripts/wsl_workspace.py` streams `pytest` output as tests run and
emphasizes failing lines and stack traces in red for immediate context.

## Phase 6: Collaborative Features
- [x] Allow multiple users to attach to same environment.
- [x] Provide session log to track contributions.
- [x] Implement follow mode for real-time command/output sharing.

`scripts/wsl_workspace.py` now supports collaborative sessions. Multiple users
can attach to the same WSL instance, and every command is appended to a shared
`session.log` with user attribution. A new `follow` action streams another
participant's commands and output live so collaborators can observe activity in
real time.

## Phase 7: Customizable Templates
- [x] Provide repo-specific environment templates.
- [x] Support starter scripts accessible via short chat commands (`!run-tests`, `!start-devserver`).

`scripts/wsl_workspace.py` can now load template files located in a repository's
`templates/` directory to preconfigure packages, environment variables, and shell
shortcuts. It also exposes short commands like `run-tests` and `start-devserver`
that invoke starter scripts, giving projects one-line entry points for common
workflows.

## Phase 8: Security & Resource Controls
- ~~Sandbox each session with limited network and compute quotas.~~
- Expose resource monitoring commands for CPU/memory.
- ~~Implement auto-timeouts for idle sessions.~~

## Maintenance
- Keep base images updated with patches.
- Log usage and performance metrics to refine features.
