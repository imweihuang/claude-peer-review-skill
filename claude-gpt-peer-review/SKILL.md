---
name: claude-gpt-peer-review
description: Run independent Claude Opus and GPT-5.5 peer reviews for software projects, then have Codex reconcile and validate the findings. Use when the user asks for both Claude and GPT, dual-model peer review, cross-model review, deciding vote, model council, red-team review, honest feedback from both models, or a higher-confidence second opinion on strategy, architecture, schema, production readiness, code quality, tests, or API contracts.
---

# Claude + GPT Peer Review

## Purpose

Use this skill to get two independent external peer reviews without losing control of scope, secrets, or decision quality. Treat both models as candid peer reviewers, not authorities.

Default roles:

- Codex: repo operator, context curator, validator, and final synthesizer.
- Claude: outside strategist, code auditor, red-team reviewer, or architecture/schema reviewer.
- GPT-5.5: independent OpenAI reviewer with the same curated context.
- User: product owner and final decision-maker.

## Review Modes

Choose one mode before building context:

| Mode | Use For | Context Bias |
| --- | --- | --- |
| Strategy Review | Product direction, architecture, schema, roadmap, core tradeoffs | Docs, data models, core modules, representative tests |
| Data/Schema Review | Database design, extraction schemas, event/object semantics, versioning | Models, migrations, schemas, ingestion/extraction/analytics |
| Diff Critique | Recent code changes or PR-like review | `git diff`, touched files, related tests |
| Launch Readiness | Internal production or deployment readiness | Deployment docs, config templates, health/ops, auth boundaries, tests |
| Coverage Audit | Whether tests prove the important behavior | Test files, coverage output if already available, high-risk modules |
| Deciding Vote | Compare two plausible designs | Short option summary, constraints, files that prove tradeoffs |

Prefer one focused mode. Combine modes only when the user explicitly asks for a broad review.

## Model and Effort Defaults

Default dual peer reviews to these settings when the installed CLIs and accounts allow them:

| Reviewer | Model | Effort | Budget |
| --- | --- | --- | --- |
| Claude | `claude-opus-4-8` | `xhigh` | `3` USD default cap |
| GPT | `gpt-5.5` | `xhigh` | Codex CLI account default |

Use per-request environment overrides when needed:

- `CLAUDE_GPT_REVIEW_CLAUDE_MODEL` for Claude model ID or alias
- `CLAUDE_GPT_REVIEW_CLAUDE_EFFORT` for `low`, `medium`, `high`, `xhigh`, or `max`
- `CLAUDE_GPT_REVIEW_CLAUDE_MAX_BUDGET_USD` for Claude print-mode spend cap
- `CLAUDE_GPT_REVIEW_GPT_MODEL` for GPT model ID or alias
- `CLAUDE_GPT_REVIEW_GPT_EFFORT` for `low`, `medium`, `high`, or `xhigh`

Do not silently downgrade either reviewer. If Claude Opus 4.8, GPT-5.5, or xHigh effort is unavailable, report the limitation and ask before using a fallback.

## Workflow

1. Define the review target.
   - Identify the project goal, current milestone, and the specific area under review.
   - Prefer focused reviews: data schema, architecture, API contract, production readiness, product methodology, security, or UX.
   - If the user asks to "go ahead", proceed with conservative defaults.

2. Curate context once.
   - Include tracked docs, source files, configs, and tests that directly support the review.
   - Never include `.env`, credentials, private keys, tokens, runtime logs, local DBs, caches, build outputs, or unrelated user files.
   - Inspect the context manifest first when practical:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-gpt-peer-review/scripts/build_review_context.py" --list README.md docs backend/src backend/tests
```

   - Build the same context for both reviewers:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-gpt-peer-review/scripts/build_review_context.py" README.md docs backend/src backend/tests
```

   - Add `--allow-untracked` only for newly created non-secret docs/code that you have inspected.

3. Prepare one neutral external-review prompt.
   - Read `references/prompt-template.md` when writing or adapting the prompt.
   - State the chosen review mode and current milestone.
   - Require file-grounded, ranked feedback.
   - Require "must fix now" versus "defer" separation.
   - Forbid secret inspection and file edits.
   - Do not mention one model's likely answer to the other model.

4. Run reviewers independently.
   - Do not show Claude's output to GPT or GPT's output to Claude before both reviews complete.
   - Use the same prompt and same curated context for both reviewers.
   - Sequential runs are simpler to monitor; parallel runs are acceptable only when you can keep outputs separate.

Claude run:

```bash
tmp_dir="$(mktemp -d)"
tmp_prompt="$tmp_dir/prompt.md"
tmp_context="$tmp_dir/context.md"
claude_out="$tmp_dir/claude-review.md"
gpt_out="$tmp_dir/gpt-review.md"
gpt_cwd="$tmp_dir/gpt-cwd"
mkdir "$gpt_cwd"
claude_model="${CLAUDE_GPT_REVIEW_CLAUDE_MODEL:-claude-opus-4-8}"
claude_effort="${CLAUDE_GPT_REVIEW_CLAUDE_EFFORT:-xhigh}"
claude_budget="${CLAUDE_GPT_REVIEW_CLAUDE_MAX_BUDGET_USD:-3}"
gpt_model="${CLAUDE_GPT_REVIEW_GPT_MODEL:-gpt-5.5}"
gpt_effort="${CLAUDE_GPT_REVIEW_GPT_EFFORT:-xhigh}"
cat > "$tmp_prompt" <<'PROMPT'
<prompt>
PROMPT
python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-gpt-peer-review/scripts/build_review_context.py" <files...> > "$tmp_context"
cat "$tmp_prompt" "$tmp_context" | \
  ANTHROPIC_MODEL="$claude_model" CLAUDE_CODE_EFFORT_LEVEL="$claude_effort" \
  claude -p \
    --tools "" \
    --no-session-persistence \
    --model "$claude_model" \
    --effort "$claude_effort" \
    --max-budget-usd "$claude_budget" > "$claude_out"
```

GPT run:

```bash
cat "$tmp_prompt" "$tmp_context" | \
  codex --ask-for-approval never exec \
    --model "$gpt_model" \
    --config "model_reasoning_effort=\"$gpt_effort\"" \
    --sandbox read-only \
    --skip-git-repo-check \
    --ephemeral \
    --ignore-rules \
    --cd "$gpt_cwd" \
    - > "$gpt_out"
```

After both complete, read `"$claude_out"` and `"$gpt_out"` for synthesis. Remove `"$tmp_dir"` unless the user asks for an audit trail.

5. Synthesize without outsourcing judgment.
   - Group findings into:
     - both reviewers agree
     - Claude-only
     - GPT-only
     - direct conflict
     - speculative or unverifiable
   - Validate major findings against the repo before acting.
   - For conflicts, inspect the referenced files and decide using the repo, tests, product goal, and current milestone.

6. Implement only the right scope.
   - If the user asked for review only, do not modify files unless the newest request permits it.
   - If the user asked to proceed, apply small, high-confidence fixes and document strategic deferrals.
   - Keep unrelated refactors out.

7. Report the outcome.
   - Summarize strongest agreement and strongest disagreement.
   - Explain what Codex accepted, deferred, rejected, or needs user decision.
   - List verification commands and results.
   - Never paste secrets or raw `.env` values.

## Context Selection Guide

Use targeted context bundles:

- Data/schema review: product docs, data model docs, migrations, ORM models, extraction schemas, ingestion/extraction/analytics services, representative tests.
- Architecture review: README, product docs, deployment docs, service entry points, config, dependency manifests, core modules, tests.
- Production readiness: deployment docs, compose/config files without secrets, health/ops endpoints, tests, CI files, security-sensitive code.
- Frontend/product review: product docs, frontend routes/components/styles, API client types, screenshots if available.
- Diff critique: use `git diff --stat`, `git diff --name-only`, relevant touched files, and tests. Do not blindly include generated files or lockfiles unless dependency behavior is under review.

Keep the bundle small enough for both reviewers to reason over. A sharper 10-file review usually beats a noisy whole-repo dump.

## Safety Rules

- Do not send `.env`, `.env.*`, secret stores, key files, local databases, logs, caches, or build artifacts to either external model.
- Do not let either reviewer edit files.
- Prefer `--tools ""` and `--no-session-persistence` for Claude.
- Prefer a temporary empty `--cd` directory, `--sandbox read-only`, and `--ephemeral` for GPT.
- Prefer the default `claude-opus-4-8 --effort xhigh` and `gpt-5.5` with `model_reasoning_effort="xhigh"` settings.
- Do not use `gpt-5.55` unless the local Codex model catalog explicitly exposes that exact model ID.
- Do not use `--allow-untracked` until you personally inspect the untracked files.
- Remember that tracked does not mean secret-free; inspect the `--list` output and be cautious with config files.
- Keep both models' outputs as advice. Codex owns verification and final edits.

## Decision Standard

Give the most weight to feedback that is:

- independently raised by both reviewers,
- grounded in provided files,
- relevant to the user's goal,
- reproducible or logically valid,
- appropriately scoped for the current milestone.

Defer feedback when it is strategically useful but not required for the current milestone. Reject feedback when it is speculative, contradicted by the repo, or would add complexity without a clear payoff.

## Output Shape

When reporting back to the user, include:

- the selected review mode,
- how context was curated,
- strongest Claude/GPT agreement,
- strongest disagreement or model-specific concern,
- findings accepted, deferred, rejected, or needing user decision,
- edits made, if any,
- verification run and results.

Keep the summary concise. Put raw model outputs in files only if the user asks for an audit trail.
