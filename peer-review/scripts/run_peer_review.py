#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_REVIEWERS = ("claude", "codex", "gemini", "grok")
REVIEWER_ALIASES = {
    "all": DEFAULT_REVIEWERS,
    "gpt": ("codex",),
    "openai": ("codex",),
    "grok-build": ("grok",),
    "claude-gpt": ("claude", "codex"),
    "claude-codex": ("claude", "codex"),
}


@dataclass
class Participant:
    key: str
    label: str
    cli: str
    cli_path: str | None
    cli_version: str | None
    requested_model: str
    requested_effort: str
    effort_status: str
    status: str
    command: str | None = None
    output_file: str | None = None
    stderr_file: str | None = None
    notes: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None


ParticipantRunner = Callable[[Participant, str, Path, int], Participant]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run independent CLI peer reviews and report exact reviewer metadata.",
    )
    parser.add_argument("paths", nargs="*", help="Files or directories to include in the curated context.")
    parser.add_argument("--root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument(
        "--reviewers",
        default=os.environ.get("PEER_REVIEW_REVIEWERS", "all"),
        help="Comma-separated reviewers: all, claude, codex/gpt, gemini, grok.",
    )
    parser.add_argument("--mode", default="Architecture Review", help="Review mode label.")
    parser.add_argument("--project", default=None, help="Project name for the review prompt.")
    parser.add_argument("--milestone", default="current milestone", help="Milestone or launch gate under review.")
    parser.add_argument("--focus", action="append", default=[], help="Focus area. May be repeated.")
    parser.add_argument("--prompt-file", help="Optional extra instructions to place before the context bundle.")
    parser.add_argument("--allow-untracked", action="store_true", help="Allow explicitly selected untracked files.")
    parser.add_argument(
        "--allow-non-git-context",
        action="store_true",
        help="Allow context building outside a git repository after manual path inspection.",
    )
    parser.add_argument(
        "--allow-secret-like-content",
        action="store_true",
        help="Allow selected files whose contents match common secret/token patterns after manual inspection.",
    )
    parser.add_argument("--max-bytes-per-file", type=int, default=None)
    parser.add_argument("--max-total-bytes", type=int, default=None)
    parser.add_argument("--output-dir", help="Directory for manifest and raw reviewer outputs.")
    parser.add_argument("--timeout-seconds", type=int, default=int(os.environ.get("PEER_REVIEW_TIMEOUT_SECONDS", "1800")))
    parser.add_argument("--preflight", action="store_true", help="Check local CLIs and requested settings without running reviews.")
    parser.add_argument("--dry-run", action="store_true", help="Print local reviewer metadata without invoking reviewers.")
    parser.add_argument("--allow-partial", action="store_true", help="Exit 0 when at least one requested reviewer ran.")
    parser.add_argument(
        "--jobs",
        type=positive_int,
        default=positive_int_env("PEER_REVIEW_JOBS", 4),
        help="Maximum reviewer CLIs to run at once. Defaults to PEER_REVIEW_JOBS or 4. Use --jobs 1 for sequential debugging.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    reviewers = parse_reviewers(args.reviewers)
    participants = [preflight_participant(key) for key in reviewers]

    if args.preflight or args.dry_run:
        print_summary(participants, output_dir=None, dry_run=True)
        return 0 if all(p.status == "ready" for p in participants) else 2

    if not args.paths:
        parser.error("paths are required unless --preflight or --dry-run is used")

    output_dir = Path(args.output_dir).resolve() if args.output_dir else Path(tempfile.mkdtemp(prefix="peer-review-"))
    output_dir.mkdir(parents=True, exist_ok=True)

    prompt = build_prompt(args, root)
    context = build_context(args, root)
    review_input = f"{prompt}\n\n# Selected Repository Context\n{context}"

    results = run_participants(participants, review_input, output_dir, args.timeout_seconds, jobs=args.jobs)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "mode": args.mode,
        "project": args.project or root.name,
        "milestone": args.milestone,
        "reviewers_requested": reviewers,
        "reviewer_jobs": args.jobs,
        "context_paths": args.paths,
        "context_bytes": len(context.encode("utf-8", errors="replace")),
        "participants": [asdict(item) for item in results],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print_summary(results, output_dir=output_dir, dry_run=False)
    return run_exit_code(results, args.allow_partial)


def parse_reviewers(raw: str) -> list[str]:
    selected: list[str] = []
    for item in raw.replace("+", ",").split(","):
        key = item.strip().lower()
        if not key:
            continue
        expanded = REVIEWER_ALIASES.get(key, (key,))
        for reviewer in expanded:
            if reviewer not in DEFAULT_REVIEWERS:
                raise SystemExit(f"unknown reviewer {reviewer!r}; expected one of {', '.join(DEFAULT_REVIEWERS)}")
            if reviewer not in selected:
                selected.append(reviewer)
    return selected or list(DEFAULT_REVIEWERS)


def positive_int(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {raw!r}") from exc
    if value < 1:
        raise argparse.ArgumentTypeError(f"expected a positive integer, got {raw!r}")
    return value


def positive_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return positive_int(raw)
    except argparse.ArgumentTypeError as exc:
        raise SystemExit(f"{name}: {exc}") from exc


def preflight_participant(key: str) -> Participant:
    if key == "claude":
        return make_participant(
            key=key,
            label="Claude",
            cli="claude",
            model=os.environ.get("PEER_REVIEW_CLAUDE_MODEL", "claude-opus-4-8"),
            effort=os.environ.get("PEER_REVIEW_CLAUDE_EFFORT", "max"),
            effort_status="requested with --effort",
        )
    if key == "codex":
        participant = make_participant(
            key=key,
            label="Codex/GPT",
            cli="codex",
            model=os.environ.get("PEER_REVIEW_CODEX_MODEL", os.environ.get("PEER_REVIEW_GPT_MODEL", "gpt-5.5")),
            effort=os.environ.get("PEER_REVIEW_CODEX_EFFORT", os.environ.get("PEER_REVIEW_GPT_EFFORT", "xhigh")),
            effort_status="requested with model_reasoning_effort",
        )
        if participant.status == "ready" and not codex_model_supports(participant.requested_model, participant.requested_effort):
            participant.status = "model_unavailable"
            participant.notes = "requested model/effort was not found in `codex debug models`; not downgrading"
        return participant
    if key == "gemini":
        return make_participant(
            key=key,
            label="Gemini",
            cli="gemini",
            model=os.environ.get("PEER_REVIEW_GEMINI_MODEL", "cli-default"),
            effort=os.environ.get("PEER_REVIEW_GEMINI_EFFORT", "not-cli-exposed"),
            effort_status="Gemini CLI default model; no thinking-effort flag in --help",
        )
    if key == "grok":
        effort = os.environ.get("PEER_REVIEW_GROK_EFFORT", "max")
        reasoning = os.environ.get("PEER_REVIEW_GROK_REASONING_EFFORT", "high")
        participant = make_participant(
            key=key,
            label="Grok Build",
            cli="grok",
            model=os.environ.get("PEER_REVIEW_GROK_MODEL", "grok-build"),
            effort=f"{effort}; reasoning_effort={reasoning}",
            effort_status="requested with --effort and --reasoning-effort",
        )
        if participant.status == "ready":
            model_status = grok_model_status(participant.requested_model)
            if model_status == "auth_required":
                participant.status = "auth_required"
                participant.notes = "`grok models` could not confirm authentication"
            elif model_status == "model_unavailable":
                participant.status = "model_unavailable"
                participant.notes = f"requested model {participant.requested_model!r} was not listed by `grok models`; not downgrading"
        return participant
    raise AssertionError(key)


def make_participant(key: str, label: str, cli: str, model: str, effort: str, effort_status: str) -> Participant:
    cli_path = shutil.which(cli)
    version = get_version(cli) if cli_path else None
    return Participant(
        key=key,
        label=label,
        cli=cli,
        cli_path=cli_path,
        cli_version=version,
        requested_model=model,
        requested_effort=effort,
        effort_status=effort_status,
        status="ready" if cli_path else "missing_cli",
        notes=None if cli_path else f"`{cli}` is not on PATH",
    )


def get_version(cli: str) -> str | None:
    try:
        result = subprocess.run(
            [cli, "--version"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return " ".join(result.stdout.strip().split()) or None


def codex_model_supports(model: str, effort: str) -> bool:
    try:
        result = subprocess.run(
            ["codex", "debug", "models"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return True
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return True
    for item in data.get("models", []):
        if item.get("slug") != model:
            continue
        efforts = {entry.get("effort") for entry in item.get("supported_reasoning_levels", [])}
        return effort in efforts
    return False


def grok_model_status(model: str) -> str:
    try:
        result = subprocess.run(
            ["grok", "models"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    combined = f"{result.stdout}\n{result.stderr}"
    if is_auth_prompt(combined) or "you are logged in" not in combined.lower():
        return "auth_required"
    listed_models = set()
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("* "):
            listed_models.add(stripped[2:].split()[0])
    if listed_models and model not in listed_models:
        return "model_unavailable"
    return "ready"


def build_prompt(args: argparse.Namespace, root: Path) -> str:
    focus = args.focus or ["highest-risk correctness, architecture, security, data, test, and launch-readiness issues"]
    focus_lines = "\n".join(f"{index}. {item}" for index, item in enumerate(focus, start=1))
    extra = ""
    if args.prompt_file:
        extra = Path(args.prompt_file).read_text(encoding="utf-8")
    return textwrap.dedent(
        f"""
        You are acting as a candid strategist and senior peer reviewer for {args.project or root.name}.

        Project goal:
        Review the selected repository context for the user's requested software work.

        Current milestone:
        {args.milestone}

        Review mode:
        {args.mode}

        Your task:
        Review the selected repository context below, especially:
        {focus_lines}

        Constraints:
        - Use only the supplied context unless explicitly told otherwise.
        - Do not inspect or request .env, secrets, credentials, private keys, runtime logs, untracked files, or unrelated user files.
        - Do not edit files.
        - Ground findings in the provided code/docs.
        - Separate must-fix issues from strategic improvements.
        - Treat the current milestone seriously; do not demand future-scale work unless it blocks this milestone.
        - Do not give generic advice; tie recommendations to the provided context.
        - Prefer concise output and prioritize the highest-risk findings.

        Output format:
        1. What is strong
        2. What is fragile
        3. Must fix before {args.milestone}
        4. Defer / later
        5. Recommended repo changes, ranked by strategic importance
        6. Findings that are speculative or need verification
        7. Any product/schema/architecture insight that changes your view of the project
        """
    ).strip() + ("\n\nAdditional user instructions:\n" + extra.strip() if extra.strip() else "")


def build_context(args: argparse.Namespace, root: Path) -> str:
    helper = Path(__file__).with_name("build_review_context.py")
    cmd = [sys.executable, str(helper), "--root", str(root)]
    if args.allow_untracked:
        cmd.append("--allow-untracked")
    if args.allow_non_git_context:
        cmd.append("--allow-non-git-context")
    if args.allow_secret_like_content:
        cmd.append("--allow-secret-like-content")
    if args.max_bytes_per_file is not None:
        cmd += ["--max-bytes-per-file", str(args.max_bytes_per_file)]
    if args.max_total_bytes is not None:
        cmd += ["--max-total-bytes", str(args.max_total_bytes)]
    cmd += args.paths
    result = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.returncode != 0:
        raise SystemExit(f"context builder failed with exit code {result.returncode}")
    if not result.stdout.strip():
        raise SystemExit("context builder produced empty context; refusing to run external reviewers")
    return result.stdout


def run_participants(
    participants: list[Participant],
    review_input: str,
    output_dir: Path,
    timeout_seconds: int,
    jobs: int,
    runner: ParticipantRunner | None = None,
) -> list[Participant]:
    participant_runner = runner or run_participant
    results = list(participants)
    ready = [(index, participant) for index, participant in enumerate(participants) if participant.status == "ready"]
    if not ready:
        return results

    if jobs == 1 or len(ready) == 1:
        for index, participant in ready:
            results[index] = participant_runner(participant, review_input, output_dir, timeout_seconds)
        return results

    max_workers = min(jobs, len(ready))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(participant_runner, participant, review_input, output_dir, timeout_seconds): index
            for index, participant in ready
        }
        for future in concurrent.futures.as_completed(future_to_index):
            index = future_to_index[future]
            try:
                results[index] = future.result()
            except Exception as exc:  # pragma: no cover - defensive boundary around external runners.
                participant = participants[index]
                participant.status = "error"
                participant.notes = f"unexpected runner failure: {exc}"
                results[index] = participant
    return results


def run_participant(participant: Participant, review_input: str, output_dir: Path, timeout_seconds: int) -> Participant:
    started_monotonic = time.monotonic()
    participant.started_at = datetime.now(timezone.utc).isoformat()
    cwd = Path(tempfile.mkdtemp(prefix=f"peer-review-{participant.key}-"))
    out_file = output_dir / f"{participant.key}-review.md"
    err_file = output_dir / f"{participant.key}-stderr.txt"

    try:
        cmd, stdin_text = command_for(participant, review_input, cwd)
        participant.command = shell_join(cmd)
        participant.output_file = str(out_file)
        participant.stderr_file = str(err_file)
        result = subprocess.run(
            cmd,
            input=stdin_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        participant.status = "timeout"
        participant.notes = f"timed out after {timeout_seconds}s"
        out_file.write_text(exc.stdout or "", encoding="utf-8")
        err_file.write_text(exc.stderr or "", encoding="utf-8")
        return finish_participant_timing(participant, started_monotonic)
    except OSError as exc:
        participant.status = "error"
        participant.notes = str(exc)
        return finish_participant_timing(participant, started_monotonic)
    finally:
        shutil.rmtree(cwd, ignore_errors=True)

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    out_file.write_text(stdout, encoding="utf-8")
    err_file.write_text(stderr, encoding="utf-8")

    combined = f"{stdout}\n{stderr}"
    if result.returncode != 0:
        if is_model_unavailable(combined):
            participant.status = "model_unavailable"
        else:
            participant.status = "auth_required" if is_auth_prompt(combined) else "error"
        participant.notes = short_note(combined) or f"exit code {result.returncode}"
    elif not stdout.strip():
        participant.status = "empty_output"
        participant.notes = "reviewer exited successfully but produced no stdout"
    else:
        participant.status = "ran"
    return finish_participant_timing(participant, started_monotonic)


def finish_participant_timing(participant: Participant, started_monotonic: float) -> Participant:
    participant.completed_at = datetime.now(timezone.utc).isoformat()
    participant.duration_seconds = round(time.monotonic() - started_monotonic, 3)
    return participant


def command_for(participant: Participant, review_input: str, cwd: Path) -> tuple[list[str], str | None]:
    if participant.key == "claude":
        budget = os.environ.get("PEER_REVIEW_CLAUDE_MAX_BUDGET_USD", "3")
        tools = os.environ.get("PEER_REVIEW_CLAUDE_TOOLS", "")
        return (
            [
                "claude",
                "-p",
                "--tools",
                tools,
                "--no-session-persistence",
                "--model",
                participant.requested_model,
                "--effort",
                participant.requested_effort,
                "--max-budget-usd",
                budget,
            ],
            review_input,
        )
    if participant.key == "codex":
        return (
            [
                "codex",
                "--ask-for-approval",
                "never",
                "exec",
                "--model",
                participant.requested_model,
                "--config",
                f"model_reasoning_effort=\"{participant.requested_effort}\"",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--ephemeral",
                "--ignore-rules",
                "--cd",
                str(cwd),
                "-",
            ],
            review_input,
        )
    if participant.key == "gemini":
        cmd = ["gemini"]
        if participant.requested_model not in {"", "cli-default", "default"}:
            cmd += ["--model", participant.requested_model]
        cmd += [
            "--skip-trust",
            "--approval-mode",
            "plan",
            "--sandbox",
            "--output-format",
            "text",
            "--prompt",
            "Use the complete review instructions and repository context from stdin. Do not edit files.",
        ]
        return (
            cmd,
            review_input,
        )
    if participant.key == "grok":
        prompt_file = cwd / "prompt-and-context.md"
        prompt_file.write_text(review_input, encoding="utf-8")
        effort = os.environ.get("PEER_REVIEW_GROK_EFFORT", "max")
        reasoning = os.environ.get("PEER_REVIEW_GROK_REASONING_EFFORT", "high")
        max_turns = os.environ.get("PEER_REVIEW_GROK_MAX_TURNS", "4")
        subprocess.run(["git", "init"], cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return (
            [
                "grok",
                "--model",
                participant.requested_model,
                "--effort",
                effort,
                "--reasoning-effort",
                reasoning,
                "--max-turns",
                max_turns,
                "--no-subagents",
                "--disable-web-search",
                "--tools",
                "",
                "--permission-mode",
                "plan",
                "--no-alt-screen",
                "--output-format",
                "plain",
                "--prompt-file",
                str(prompt_file),
            ],
            None,
        )
    raise AssertionError(participant.key)


def is_auth_prompt(text: str) -> bool:
    lowered = text.lower()
    needles = [
        "signing in",
        "open this url to sign in",
        "no auth credentials",
        "authentication",
        "not logged in",
        "login",
    ]
    return any(needle in lowered for needle in needles)


def is_model_unavailable(text: str) -> bool:
    lowered = text.lower()
    return "modelnotfound" in lowered or "requested entity was not found" in lowered


def short_note(text: str) -> str | None:
    lines = [" ".join(line.strip().split()) for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    return lines[0][:240]


def shell_join(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def print_summary(participants: list[Participant], output_dir: Path | None, dry_run: bool) -> None:
    title = "Peer Review Dry Run" if dry_run else "Peer Review Run"
    print(f"# {title}")
    if output_dir:
        print(f"Output dir: {output_dir}")
        print(f"Manifest: {output_dir / 'manifest.json'}")
    print()
    print("| Reviewer | CLI version | Requested model | Requested effort | Effort status | Status |")
    print("| --- | --- | --- | --- | --- | --- |")
    for item in participants:
        print(
            "| "
            + " | ".join(
                [
                    item.label,
                    item.cli_version or "unavailable",
                    f"`{item.requested_model}`",
                    f"`{item.requested_effort}`",
                    item.effort_status,
                    item.status,
                ]
            )
            + " |"
        )
    notes = [item for item in participants if item.notes]
    if notes:
        print("\n## Notes")
        for item in notes:
            print(f"- {item.label}: {item.notes}")
    commands = [item for item in participants if item.command]
    if commands:
        print("\n## Commands")
        for item in commands:
            print(f"- {item.label}: `{item.command}`")


def run_exit_code(participants: list[Participant], allow_partial: bool) -> int:
    ran_count = sum(1 for item in participants if item.status == "ran")
    if ran_count == len(participants) and participants:
        return 0
    if allow_partial and ran_count > 0:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
