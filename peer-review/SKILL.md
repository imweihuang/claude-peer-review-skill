---
name: peer-review
description: Use when the user asks for peer review, external review, model council, second opinion, red-team feedback, code audit, architecture review, schema review, production-readiness review, API contract review, coverage audit, or candid feedback from Claude, GPT/Codex, Gemini, Grok, or multiple CLI reviewers.
---

# Peer Review

## Purpose

Use this skill to run independent external CLI reviewers and then have Codex validate the findings. Treat the reviewers as strong second, third, and fourth eyes, not authorities.

Default reviewer roster:

| Reviewer | CLI | Default model | Default effort |
| --- | --- | --- | --- |
| Claude | `claude` | Opus 4.8 via `opus` alias | `xhigh` |
| Codex/GPT | `codex` | `gpt-5.5` | `xhigh` |
| Gemini | `gemini` | `cli-default` | reported as `not-cli-exposed` unless the local CLI exposes a thinking flag |
| Grok Build | `grok` | `grok-build` | `max`; `reasoning_effort=high` |

If a CLI, model, auth state, or effort setting is unavailable, report it clearly. Do not silently downgrade or present Codex self-review as external peer review.

## Review Modes

Choose one focused mode before building context:

| Mode | Use For | Context Bias |
| --- | --- | --- |
| Strategy Review | Product direction, architecture, schema, roadmap, core tradeoffs | Docs, data models, core modules, representative tests |
| Data/Schema Review | Database design, extraction schemas, event/object semantics, versioning | Models, migrations, schemas, ingestion/extraction/analytics |
| Diff Critique | Recent code changes or PR-like review | `git diff`, touched files, related tests |
| Launch Readiness | Production or deployment readiness | Deployment docs, config templates, health/ops, auth boundaries, tests |
| Coverage Audit | Whether tests prove important behavior | Test files, coverage output if already available, high-risk modules |
| Deciding Vote | Compare plausible designs | Option summary, constraints, files that prove tradeoffs |

Prefer targeted subsystem reviews over one giant whole-repo prompt.

## Workflow

1. Define the review target.
   - Identify project goal, milestone, review mode, and focus areas.
   - If the user does not specify reviewers, use the default roster: Claude, Codex/GPT, Gemini, and Grok Build.
   - If the user requests a subset, pass it with `--reviewers claude`, `--reviewers gpt`, `--reviewers claude,gpt`, etc.

2. Curate context.
   - Include tracked docs, source files, configs, and tests that directly support the review.
   - Never include `.env`, credentials, private keys, tokens, runtime logs, local DBs, caches, build outputs, or unrelated user files.
   - Inspect selected files first when practical:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/peer-review/scripts/build_review_context.py" --list README.md docs src tests
```

   - If the helper reports `total byte limit reached`, first narrow the selected paths. For a targeted cross-file review, raise limits with `--max-total-bytes 1500000`, `--max-bytes-per-file 150000`, or `PEER_REVIEW_MAX_TOTAL_BYTES` / `PEER_REVIEW_MAX_BYTES_PER_FILE`.
   - Add `--allow-untracked` only for newly created non-secret docs/code that you have inspected.
   - The context helper fails closed outside git by default. Use `--allow-non-git-context` only after inspecting the selected paths.
   - The context helper aborts on common secret/token content patterns. Redact the value or use `--allow-secret-like-content` only after manual inspection.
   - If files are omitted by total byte limits, the helper now emits an in-band `CONTEXT OMITTED` marker that reviewers can see.

3. Preflight the local reviewer roster.

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/peer-review/scripts/run_peer_review.py" --preflight
```

   - The response must include all requested participants, CLI versions, requested models, requested efforts, effort-status caveats, and unavailable/auth-failed reviewers.
   - Grok may be installed but unauthenticated. Report that as unavailable for the run until `grok login` or supported xAI auth is configured.
   - Gemini CLI currently exposes `--model` but no clear thinking-effort flag in `gemini --help`; by default use the local CLI default model and report Gemini effort as `not-cli-exposed` unless the installed CLI proves otherwise.
   - Preflight proves local CLI/model metadata, not a full paid review. A run may still fail on provider-specific runtime requirements; report those failures plainly.

4. Refresh reviewer CLIs and default-model evidence only when explicitly asked.

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/peer-review/scripts/refresh_peer_review_clis.py"
```

   - This is a manual maintenance command, not part of normal peer-review execution.
   - It checks installed CLI versions, package-manager latest versions where possible, local model catalogs, and current default effort evidence.
   - It prints proposed default changes but does not rewrite `SKILL.md` or `run_peer_review.py`.
   - Run `--update` only when the user explicitly asks to update CLIs. Add `--install-missing` only when the user explicitly asks to install missing supported CLIs.
   - Use `--no-online` when package registry/Homebrew checks are not wanted.

5. Run independent reviewers with one neutral prompt and one shared context bundle.

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/peer-review/scripts/run_peer_review.py" \
  --mode "Diff Critique" \
  --milestone "current milestone" \
  --focus "correctness bugs and behavioral regressions" \
  --focus "missing tests and security boundaries" \
  README.md src tests
```

   - The runner keeps outputs separate and does not show one model's answer to another.
   - The runner runs independent reviewers in parallel by default, up to `--jobs 4` or `PEER_REVIEW_JOBS`. Use `--jobs 1` for sequential debugging.
   - Claude runs with tools disabled and no session persistence.
   - Codex/GPT runs in a temporary empty cwd with read-only sandboxing and ephemeral mode.
   - Gemini runs with `--skip-trust`, plan approval mode, and a sandbox where supported.
   - Grok Build runs with subagents disabled, web search disabled, plan permission mode, no tool allowlist, an initialized empty temp git directory, and `PEER_REVIEW_GROK_MAX_TURNS` defaulting to `4`.
   - By default the run exits nonzero if any requested reviewer fails. Use `--allow-partial` only when a degraded council is acceptable.

6. Synthesize without outsourcing judgment.
   - Group findings into:
     - agreement across reviewers
     - Claude-only
     - Codex/GPT-only
     - Gemini-only
     - Grok-only
     - direct conflict
     - speculative or unverifiable
   - Validate major findings against the repo before acting.
   - Classify each important finding as `accept and fix`, `accept and defer`, `reject with reason`, or `needs user decision`.

7. Implement only the right scope.
   - If the user asked for review only, do not modify files unless the newest request permits it.
   - If the user asked to proceed, apply small, high-confidence fixes and document strategic deferrals.
   - Keep unrelated refactors out.

8. Report the outcome.
   - Include selected review mode, context selection, and the participant table from the runner.
   - Include what each model actually participated with: CLI version, model, effort, and effort-status caveat.
   - Include strongest agreement, strongest disagreement, accepted/deferred/rejected findings, edits made, and verification results.
   - Never paste secrets or raw `.env` values.

## Overrides

Use these env vars for one run:

```bash
PEER_REVIEW_REVIEWERS=claude,codex,gemini,grok
PEER_REVIEW_CLAUDE_MODEL=opus
PEER_REVIEW_CLAUDE_EFFORT=xhigh
PEER_REVIEW_CODEX_MODEL=gpt-5.5
PEER_REVIEW_CODEX_EFFORT=xhigh
PEER_REVIEW_GEMINI_MODEL=cli-default
PEER_REVIEW_GROK_MODEL=grok-build
PEER_REVIEW_GROK_EFFORT=max
PEER_REVIEW_GROK_REASONING_EFFORT=high
PEER_REVIEW_GROK_MAX_TURNS=4
PEER_REVIEW_JOBS=4
```

Set `PEER_REVIEW_CLAUDE_MAX_BUDGET_USD` only when a Claude run needs an explicit `--max-budget-usd` cap; there is no default budget cap.

Do not use a lower model or lower effort unless the user explicitly approves the fallback.

## Context Selection Guide

- Data/schema review: product docs, data model docs, migrations, ORM models, extraction schemas, ingestion/extraction/analytics services, representative tests.
- Architecture review: README, product docs, deployment docs, service entry points, config, dependency manifests, core modules, tests.
- Production readiness: deployment docs, compose/config files without secrets, health/ops endpoints, tests, CI files, security-sensitive code.
- Frontend/product review: product docs, frontend routes/components/styles, API client types, screenshots if available.
- Diff critique: use `git diff --stat`, `git diff --name-only`, relevant touched files, and tests. Do not blindly include generated files or lockfiles unless dependency behavior is under review.

Keep the bundle small enough for each reviewer to reason over. Split by subsystem when context selection becomes noisy.

## Decision Standard

Give the most weight to feedback that is independently raised, file-grounded, relevant to the milestone, reproducible or logically valid, and scoped to the user's goal. Reject speculative feedback, contradicted claims, and complexity that does not pay for itself.
