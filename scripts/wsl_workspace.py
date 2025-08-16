#!/usr/bin/env python3
"""Utilities for managing a persistent WSL workspace for smollm3-openwebui.

This script keeps a WSL distribution active in the repository directory and
exposes chat-oriented commands for common development tasks.  Phases 1 and 2
cover environment setup, while Phase 3 adds integrated Git operations and
helpers for linking GitHub issues/PRs or running arbitrary shell commands.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
from pathlib import Path

DEFAULT_DISTRO = "Ubuntu"
# Default resource limits for sandboxed sessions (Phase 8)
CPU_TIME_LIMIT = 3600  # seconds of CPU time
MEMORY_LIMIT = 1 * 1024 * 1024 * 1024  # 1 GiB in bytes
IDLE_TIMEOUT = 3600  # seconds before shell auto-exit


def _load_template(repo: str) -> dict:
    """Load template configuration from ``wsl_template.json`` if present."""

    template_path = Path(repo) / "wsl_template.json"
    if template_path.is_file():
        with template_path.open("r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSON in {template_path}: {exc}")
    return {}


def _to_wsl_path(path: str) -> str:
    """Convert a Windows path to its WSL equivalent.

    Paths already in POSIX form are returned unchanged.
    """

    p = Path(path)
    if p.drive:
        drive = p.drive.rstrip(":").lower()
        rest = "/".join(p.parts[1:])
        return f"/mnt/{drive}/{rest}"
    return str(p)


def _ensure_dev_env(distro: str, repo: str) -> None:
    """Install developer tooling inside the WSL distro if missing.

    Installation is cached per repository by creating a marker file inside the
    repo.  Subsequent calls for the same repo skip reinstalling dependencies.
    """

    packages = [
        "build-essential",
        "clang",
        "git",
        "python3",
        "python3-pip",
        "python3-venv",
        "cargo",
        "rustc",
        "flake8",
        "pytest",
        "tmux",
    ]
    pkg_str = " ".join(packages)
    wsl_repo = _to_wsl_path(repo)
    marker = f"{wsl_repo}/.wsl_deps_installed"
    setup_cmd = (
        f"if [ ! -f {marker} ]; then "
        "sudo apt-get update && "
        f"sudo apt-get install -y {pkg_str} && "
        f"touch {marker}; fi"
    )
    subprocess.run(["wsl", "-d", distro, "bash", "-lc", setup_cmd], check=True)


def _run_in_wsl(distro: str, repo: str, cmd: str, *, log: bool = True) -> None:
    """Execute a command inside the WSL distro rooted at the repo path.

    When ``log`` is true the command and its output are appended to
    ``wsl_session.log`` in the repository so collaborators can review the
    history or follow along in real time.
    """

    wsl_repo = _to_wsl_path(repo)
    if log:
        safe = cmd.replace("'", "'\"'\"'")
        full_cmd = (
            f"cd '{wsl_repo}' && "
            f"echo \"$(date -Iseconds) :: {safe}\" >> wsl_session.log && "
            f"({cmd}) 2>&1 | tee -a wsl_session.log"
        )
    else:
        full_cmd = f"cd '{wsl_repo}' && {cmd}"
    subprocess.run(["wsl", "-d", distro, "bash", "-lc", full_cmd], check=True)


def start_workspace(
    distro: str,
    repo: str,
    *,
    cpu_limit: int = CPU_TIME_LIMIT,
    memory_limit: int = MEMORY_LIMIT,
    idle_timeout: int = IDLE_TIMEOUT,
) -> None:
    """Open a sandboxed shell in the WSL distro rooted at the repo path."""

    _ensure_dev_env(distro, repo)
    template = _load_template(repo)
    env_exports = ""
    for key, value in template.get("env", {}).items():
        env_exports += f"export {key}='{value}' && "
    # Auto-logout idle shells
    env_exports += f"export TMOUT={idle_timeout} && "
    session_cmd = (
        f"{env_exports}unshare -n prlimit --cpu={cpu_limit} --as={memory_limit} -- tmux new-session -A -s smollm3 'script -f -q wsl_session.log bash'"
    )
    _run_in_wsl(distro, repo, session_cmd, log=False)


def suspend_workspace(distro: str) -> None:
    """Suspend the given WSL distro."""

    subprocess.run(["wsl", "--terminate", distro], check=True)


async def run_tests(distro: str, repo: str) -> None:
    """Run pytest inside the WSL distro streaming output as it executes."""

    _ensure_dev_env(distro, repo)
    wsl_repo = _to_wsl_path(repo)
    cmd = [
        "wsl",
        "-d",
        distro,
        "bash",
        "-lc",
        (
            f"cd '{wsl_repo}' && "
            "echo \"$(date -Iseconds) :: pytest -vv\" >> wsl_session.log && "
            "pytest -vv 2>&1 | tee -a wsl_session.log"
        ),
    ]
    # Stream logs line-by-line so failures appear in real time.
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    assert proc.stdout is not None
    async for raw_line in proc.stdout:
        line = raw_line.decode()
        if any(pat in line for pat in ("FAILED", "ERROR", "Traceback", "E   ")):
            # Highlight failure lines and stack traces in red.
            print(f"\033[91m{line.rstrip()}\033[0m")
        else:
            print(line, end="")
    returncode = await proc.wait()
    if returncode:
        raise subprocess.CalledProcessError(returncode, cmd)


def run_lint(distro: str, repo: str) -> None:
    """Run flake8 over the repository inside the WSL distro."""

    _ensure_dev_env(distro, repo)
    _run_in_wsl(distro, repo, "flake8 .")


def run_build(distro: str, repo: str) -> None:
    """Attempt to build the project using common conventions."""

    _ensure_dev_env(distro, repo)
    build_cmd = (
        "if [ -f Cargo.toml ]; then cargo build; "
        "elif [ -f Makefile ]; then make; "
        "elif [ -f setup.py ]; then python3 setup.py build; "
        "else echo 'No build step defined.'; fi"
    )
    _run_in_wsl(distro, repo, build_cmd)


def run_template_script(distro: str, repo: str, script: str) -> None:
    """Run a template-defined script inside the WSL distro."""

    template = _load_template(repo)
    scripts = template.get("scripts", {})
    cmd = scripts.get(script)
    if not cmd:
        raise SystemExit(f"Unknown action: {script}")
    _ensure_dev_env(distro, repo)
    _run_in_wsl(distro, repo, cmd)


def git_pull(distro: str, repo: str) -> None:
    """Run `git pull` inside the repository."""

    _ensure_dev_env(distro, repo)
    _run_in_wsl(distro, repo, "git pull --ff-only")


def git_status(distro: str, repo: str) -> None:
    """Show `git status` for the repository."""

    _ensure_dev_env(distro, repo)
    _run_in_wsl(distro, repo, "git status")


def _suggest_commit_message(distro: str, repo: str) -> str:
    """Generate a simple commit message based on changed files."""

    wsl_repo = _to_wsl_path(repo)
    result = subprocess.run(
        ["wsl", "-d", distro, "bash", "-lc", f"cd '{wsl_repo}' && git status --short"],
        capture_output=True,
        text=True,
        check=True,
    )
    files = [line.split(maxsplit=1)[-1] for line in result.stdout.strip().splitlines()]
    if not files:
        return "chore: update repository"
    if len(files) == 1:
        return f"chore: update {files[0]}"
    return f"chore: update {files[0]} and {len(files) - 1} other files"


def git_commit(distro: str, repo: str, message: str | None) -> None:
    """Commit tracked changes with diff preview and suggested message."""

    _ensure_dev_env(distro, repo)
    wsl_repo = _to_wsl_path(repo)
    subprocess.run(
        [
            "wsl",
            "-d",
            distro,
            "bash",
            "-lc",
            f"cd '{wsl_repo}' && git --no-pager status && git --no-pager diff",
        ],
        check=True,
    )
    if not message:
        message = _suggest_commit_message(distro, repo)
        print(f"Using commit message: {message}")
    _run_in_wsl(distro, repo, f"git commit -am \"{message}\"")


def git_push(distro: str, repo: str) -> None:
    """Run `git push` for the repository."""

    _ensure_dev_env(distro, repo)
    _run_in_wsl(distro, repo, "git push")


def _get_github_url(distro: str, repo: str) -> str:
    """Return the base HTTPS GitHub URL for the repository."""

    wsl_repo = _to_wsl_path(repo)
    result = subprocess.run(
        ["wsl", "-d", distro, "bash", "-lc", f"cd '{wsl_repo}' && git config --get remote.origin.url"],
        capture_output=True,
        text=True,
        check=True,
    )
    url = result.stdout.strip()
    if url.endswith(".git"):
        url = url[:-4]
    if url.startswith("git@github.com:"):
        url = url.replace("git@github.com:", "https://github.com/")
    return url


def _open_github_link(distro: str, url: str) -> None:
    """Open a GitHub URL using `wslview` if available."""

    subprocess.run(
        [
            "wsl",
            "-d",
            distro,
            "bash",
            "-lc",
            f"command -v wslview >/dev/null && wslview '{url}' || echo '{url}'",
        ],
        check=True,
    )


def open_issue(distro: str, repo: str, issue: str) -> None:
    """Open the GitHub issue corresponding to the given number."""

    base = _get_github_url(distro, repo)
    _open_github_link(distro, f"{base}/issues/{issue}")


def open_pr(distro: str, repo: str, pr: str) -> None:
    """Open the GitHub pull request corresponding to the given number."""

    base = _get_github_url(distro, repo)
    _open_github_link(distro, f"{base}/pull/{pr}")


def snapshot_workspace(distro: str, repo: str) -> None:
    """Create a tarball snapshot of the repository inside WSL."""

    _ensure_dev_env(distro, repo)
    wsl_repo = _to_wsl_path(repo)
    cmd = (
        f"cd '{wsl_repo}' && "
        "tar -czf .wsl_snapshot.tar.gz --exclude=.wsl_snapshot.tar.gz ."
    )
    subprocess.run(["wsl", "-d", distro, "bash", "-lc", cmd], check=True)


def rollback_workspace(distro: str, repo: str) -> None:
    """Restore the repository to the last snapshot if one exists."""

    _ensure_dev_env(distro, repo)
    wsl_repo = _to_wsl_path(repo)
    cmd = (
        f"cd '{wsl_repo}' && "
        "if [ -f .wsl_snapshot.tar.gz ]; then "
        "tar -xzf .wsl_snapshot.tar.gz; "
        "else echo 'No snapshot found.'; fi"
    )
    subprocess.run(["wsl", "-d", distro, "bash", "-lc", cmd], check=True)


def run_shell(distro: str, repo: str, command: str) -> None:
    """Run an arbitrary shell command in the repository."""

    _ensure_dev_env(distro, repo)
    _run_in_wsl(distro, repo, command)


def show_resources(distro: str, repo: str) -> None:
    """Display current CPU and memory usage."""

    _ensure_dev_env(distro, repo)
    wsl_repo = _to_wsl_path(repo)
    cmd = (
        f"cd '{wsl_repo}' && echo 'CPU/memory usage:' && top -b -n1 | head -n5 && echo && free -h"
    )
    subprocess.run(["wsl", "-d", distro, "bash", "-lc", cmd], check=True)


def follow_log(distro: str, repo: str) -> None:
    """Stream the shared session log in real time."""

    _ensure_dev_env(distro, repo)
    wsl_repo = _to_wsl_path(repo)
    subprocess.run(
        [
            "wsl",
            "-d",
            distro,
            "bash",
            "-lc",
            f"cd '{wsl_repo}' && tail -n +1 -f wsl_session.log",
        ],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage a persistent WSL workspace for smollm3-openwebui",
    )
    parser.add_argument(
        "action",
        help="Action to perform or template script name",
    )
    parser.add_argument(
        "--distro",
        default=DEFAULT_DISTRO,
        help="WSL distribution name (default: %(default)s)",
    )
    parser.add_argument(
        "--repo",
        default=os.getcwd(),
        help="Path to the repository on the Windows side",
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Issue/PR number for issue/pr actions",
    )
    parser.add_argument(
        "--message",
        help="Commit message for commit action",
    )
    parser.add_argument(
        "--cmd",
        help="Command to run for the '$' action",
    )

    args = parser.parse_args()
    template_scripts = _load_template(args.repo).get("scripts", {})

    if args.action in {"start", "resume"}:
        start_workspace(args.distro, args.repo)
    elif args.action == "suspend":
        suspend_workspace(args.distro)
    elif args.action == "test":
        asyncio.run(run_tests(args.distro, args.repo))
    elif args.action == "lint":
        run_lint(args.distro, args.repo)
    elif args.action == "build":
        run_build(args.distro, args.repo)
    elif args.action == "pull":
        git_pull(args.distro, args.repo)
    elif args.action == "status":
        git_status(args.distro, args.repo)
    elif args.action == "commit":
        git_commit(args.distro, args.repo, args.message)
    elif args.action == "push":
        git_push(args.distro, args.repo)
    elif args.action == "issue":
        if not args.target:
            raise SystemExit("issue action requires an issue number")
        open_issue(args.distro, args.repo, args.target)
    elif args.action == "pr":
        if not args.target:
            raise SystemExit("pr action requires a pull request number")
        open_pr(args.distro, args.repo, args.target)
    elif args.action == "snapshot":
        snapshot_workspace(args.distro, args.repo)
    elif args.action == "rollback":
        rollback_workspace(args.distro, args.repo)
    elif args.action == "follow":
        follow_log(args.distro, args.repo)
    elif args.action == "resources":
        show_resources(args.distro, args.repo)
    elif args.action == "$":
        if not args.cmd:
            raise SystemExit("$ action requires --cmd")
        run_shell(args.distro, args.repo, args.cmd)
    elif args.action in template_scripts:
        run_template_script(args.distro, args.repo, args.action)
    else:
        raise SystemExit(f"Unknown action: {args.action}")


if __name__ == "__main__":
    main()
