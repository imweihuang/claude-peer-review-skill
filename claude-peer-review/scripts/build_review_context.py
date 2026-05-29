#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


BLOCKED_PARTS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    ".next",
    "dist",
    "build",
    "coverage",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "var",
    "logs",
    "__pycache__",
}

BLOCKED_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.prod",
    ".env.development",
    ".envrc",
    ".vault-token",
    ".npmrc",
    ".pypirc",
    ".netrc",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "known_hosts",
    "terraform.tfvars",
    "terraform.tfstate",
    "terraform.tfstate.backup",
}

BLOCKED_SUFFIXES = {
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".sqlite",
    ".sqlite3",
    ".db",
    ".log",
    ".pyc",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".tgz",
    ".tfvars",
    ".tfstate",
}


def positive_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    normalized = raw.strip().replace("_", "")
    try:
        value = int(normalized)
    except ValueError:
        print(f"[context-builder] invalid {name}={raw!r}; using default {default}", file=sys.stderr)
        return default
    if value <= 0:
        print(f"[context-builder] invalid {name}={raw!r}; using default {default}", file=sys.stderr)
        return default
    return value


def main() -> int:
    default_max_bytes_per_file = positive_int_env("PEER_REVIEW_MAX_BYTES_PER_FILE", 100_000)
    default_max_total_bytes = positive_int_env("PEER_REVIEW_MAX_TOTAL_BYTES", 1_000_000)

    parser = argparse.ArgumentParser(
        description="Build a safe text context bundle for external peer review.",
    )
    parser.add_argument("paths", nargs="+", help="Files or directories to include.")
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--allow-untracked", action="store_true", help="Allow explicitly selected untracked files.")
    parser.add_argument("--list", action="store_true", help="List selected files instead of printing file contents.")
    parser.add_argument("--max-bytes-per-file", type=int, default=default_max_bytes_per_file)
    parser.add_argument("--max-total-bytes", type=int, default=default_max_total_bytes)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    tracked = git_tracked_files(root)
    if tracked is None:
        print(
            "[context-builder] WARNING: git ls-files unavailable; include only paths you have inspected.",
            file=sys.stderr,
        )
    candidates = collect_candidates(root, args.paths, tracked, args.allow_untracked)

    if args.list:
        for path in candidates:
            if not is_blocked(path, root):
                print(display_path(path, root))
        return 0

    written = 0
    for path in candidates:
        if written >= args.max_total_bytes:
            print(
                "[context-builder] total byte limit reached at "
                f"{args.max_total_bytes}; narrow the selected paths or raise "
                "--max-total-bytes / PEER_REVIEW_MAX_TOTAL_BYTES for a targeted review",
                file=sys.stderr,
            )
            break
        if is_blocked(path, root):
            print(f"[context-builder] skipped blocked path: {display_path(path, root)}", file=sys.stderr)
            continue
        try:
            data = path.read_bytes()
        except OSError as exc:
            print(f"[context-builder] skipped unreadable path {display_path(path, root)}: {exc}", file=sys.stderr)
            continue
        if b"\x00" in data:
            print(f"[context-builder] skipped binary path: {display_path(path, root)}", file=sys.stderr)
            continue

        truncated = len(data) > args.max_bytes_per_file
        if truncated:
            data = data[: args.max_bytes_per_file]

        remaining = args.max_total_bytes - written
        if len(data) > remaining:
            data = data[:remaining]
            truncated = True

        rel = display_path(path, root)
        sys.stdout.write(f"\n===== {rel} =====\n")
        sys.stdout.write(data.decode("utf-8", errors="replace"))
        if truncated:
            sys.stdout.write("\n[TRUNCATED]\n")
        if not data.endswith(b"\n"):
            sys.stdout.write("\n")
        written += len(data)

    return 0


def git_tracked_files(root: Path) -> set[Path] | None:
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return {root / item.decode("utf-8") for item in result.stdout.split(b"\0") if item}


def collect_candidates(root: Path, raw_paths: list[str], tracked: set[Path] | None, allow_untracked: bool) -> list[Path]:
    selected: list[Path] = []
    seen: set[Path] = set()

    for raw in raw_paths:
        path = (root / raw).resolve()
        if not is_relative_to(path, root):
            print(f"[context-builder] skipped outside-root path: {raw}", file=sys.stderr)
            continue
        if not path.exists():
            print(f"[context-builder] skipped missing path: {raw}", file=sys.stderr)
            continue
        for candidate in expand_path(root, path, tracked):
            if tracked is not None and candidate not in tracked and not allow_untracked:
                print(f"[context-builder] skipped untracked path: {display_path(candidate, root)}", file=sys.stderr)
                continue
            if tracked is not None and candidate not in tracked and allow_untracked:
                print(
                    f"[context-builder] WARNING: including untracked file: {display_path(candidate, root)}",
                    file=sys.stderr,
                )
            if candidate not in seen:
                selected.append(candidate)
                seen.add(candidate)

    return selected


def expand_path(root: Path, path: Path, tracked: set[Path] | None) -> list[Path]:
    if path.is_file():
        return [path]
    if tracked is not None:
        return sorted(item for item in tracked if is_relative_to(item, path) and item.is_file())
    return sorted(item for item in path.rglob("*") if item.is_file() and not is_blocked(item, root))


def is_blocked(path: Path, root: Path) -> bool:
    rel_parts = path.resolve().relative_to(root).parts
    name = path.name
    lower_name = name.lower()
    return (
        any(part in BLOCKED_PARTS for part in rel_parts)
        or lower_name in BLOCKED_NAMES
        or lower_name.startswith(".env.")
        or path.suffix.lower() in BLOCKED_SUFFIXES
    )


def display_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path)


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
