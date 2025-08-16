# Repo-Support-Plan

This plan describes stepwise features to transform the interactive environment to support persistent, preconfigured, collaborative development sessions.

**Current status:** only Phases&nbsp;1 and&nbsp;2 and the real‑time testing portions of Phase&nbsp;5 are implemented in `scripts/wsl_workspace.py`.  Phases&nbsp;3, 4, 6, 7, and 8 are still future work.

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
- [ ] Implement chat commands for `git pull`, `git status`, `git commit`, and `git push`.
- [ ] Show diff previews and commit message suggestions.
- [ ] Link to GitHub Issues and PRs.
- [ ] Implement chat command runner '$' to run any shell commands in the repo.

*Not yet implemented.*

## Phase 4: Incremental Environment Setup
- [ ] Cache dependency installations per repo.
- [ ] Provide snapshot/rollback features to revert to prior state.

*Not yet implemented.*

## Phase 5: Real-time Testing & Feedback
- [x] Execute tests asynchronously and stream logs back to chat.
- [x] Highlight failing lines and stack traces in context.

`scripts/wsl_workspace.py` streams `pytest` output as tests run and
emphasizes failing lines and stack traces in red for immediate context.

## Phase 6: Collaborative Features
- [ ] Allow multiple users to attach to same environment.
- [ ] Provide session log to track contributions.
- [ ] Implement follow mode for real-time command/output sharing.

*Not yet implemented.*

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
