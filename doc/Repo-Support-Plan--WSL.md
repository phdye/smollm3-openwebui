# Repo-Support-Plan

This plan describes stepwise features to transform the interactive environment to support persistent, preconfigured, collaborative development sessions.

## Phase 1: Persistent Workspace
- Set up connection to a WSL distro that remains active during chat session.
- Maintain path to repo folder.
- Provide command to suspend/resume environment.
- Deliver minimal environment for baseline editing and script execution.

## Phase 2: Preconfigured Tooling
- Ensure that system has pre-installed at least these common languages :
  - C/C++, Rust, Python Development (compiles, linters, test runners)
  - Corresponding compilers, linters, test runners

- Provide chat command wrappers (`!test`, `!lint`, `!build`).
- Document default environment and configuration.

## Phase 3: Integrated Git Operations
- Implement chat commands for `git pull`, `git status`, `git commit`, and `git push`.
- Show diff previews and commit message suggestions.
- Link to GitHub Issues and PRs.
- Implement chat command runner '$' to run any shell commands in the repo

## Phase 4: Incremental Environment Setup
- Cache dependency installations per repo.
- Provide snapshot/rollback features to revert to prior state.

## Phase 5: Real-time Testing & Feedback
- Execute tests asynchronously and stream logs back to chat.
- Highlight failing lines and stack traces in context.

## Phase 6: Collaborative Features
- Allow multiple users to attach to same environment.
- Provide session log to track contributions.
- Implement follow mode for real-time command/output sharing.

## Phase 7: Customizable Templates
- Provide repo-specific environment templates.
- Support starter scripts accessible via short chat commands (`!run-tests`, `!start-devserver`).

## Phase 8: Security & Resource Controls
- ~~Sandbox each session with limited network and compute quotas.~~
- Expose resource monitoring commands for CPU/memory.
- ~~Implement auto-timeouts for idle sessions.~~

## Maintenance
- Keep base images updated with patches.
- Log usage and performance metrics to refine features.
