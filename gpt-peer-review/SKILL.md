---
name: gpt-peer-review
description: Run Codex CLI with GPT-5.5 as a safe external peer reviewer for software projects, including code audit, architecture review, data/schema review, production-readiness review, API contract review, coverage audit, strategy review, or candid second-opinion requests. Use when the user explicitly asks Codex to ask GPT, GPT-5.5, OpenAI, or another Codex/GPT reviewer for peer review, red-team feedback, honest feedback, or a cross-model second opinion.
---

# GPT Peer Review

## Purpose

Use this skill to get a GPT-5.5 peer review without losing control of scope, secrets, or decision quality. Treat the external GPT reviewer as a candid peer reviewer, not an authority.

Default roles:

- Codex: repo operator, implementer, and validator.
- GPT-5.5: strategist, code auditor, red-team reviewer, or architecture/schema reviewer.
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

Default GPT peer reviews to GPT-5.5 at xHigh reasoning when the installed Codex CLI and account allow it:

- Model: `gpt-5.5`
- Effort: `xhigh`

Use per-request environment overrides when needed:

- `GPT_PEER_REVIEW_MODEL` for model ID or alias
- `GPT_PEER_REVIEW_EFFORT` for `low`, `medium`, `high`, or `xhigh`

Do not silently downgrade to an older GPT model or lower effort. If GPT-5.5 or xHigh effort is unavailable, report that external review could not run under the requested settings and ask before using a fallback.

## Workflow

1. Define the review target.
   - Identify the project goal, current milestone, and the specific area under review.
   - Prefer focused reviews: data schema, architecture, API contract, production readiness, product methodology, security, or UX.
   - If the user asks to "go ahead", proceed with conservative defaults.

2. Curate context.
   - Include tracked docs, source files, configs, and tests that directly support the review.
   - Never include `.env`, credentials, private keys, tokens, runtime logs, local DBs, caches, build outputs, or unrelated user files.
   - When possible, inspect the context manifest first:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/gpt-peer-review/scripts/build_review_context.py" --list README.md docs backend/src backend/tests
```

   - Prefer the bundled context helper:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/gpt-peer-review/scripts/build_review_context.py" README.md docs backend/src backend/tests
```

   - Add `--allow-untracked` only for newly created non-secret docs/code that you have inspected.

3. Prepare the external-review prompt.
   - Read `references/prompt-template.md` when writing or adapting the prompt.
   - State the chosen review mode and current milestone.
   - Require file-grounded, ranked feedback.
   - Require "must fix now" versus "defer" separation.
   - Forbid secret inspection and file edits.
   - Instruct the reviewer to use only the supplied context unless the user explicitly approved live search or repo exploration.

4. Run the external reviewer safely.
   - If Codex CLI is available and requested or appropriate, run GPT-5.5 in a temporary empty working directory with read-only sandboxing:

```bash
tmp_prompt="$(mktemp)"
tmp_context="$(mktemp)"
tmp_cwd="$(mktemp -d)"
review_model="${GPT_PEER_REVIEW_MODEL:-gpt-5.5}"
review_effort="${GPT_PEER_REVIEW_EFFORT:-xhigh}"
cat > "$tmp_prompt" <<'PROMPT'
<prompt>
PROMPT
python3 "${CODEX_HOME:-$HOME/.codex}/skills/gpt-peer-review/scripts/build_review_context.py" <files...> > "$tmp_context"
cat "$tmp_prompt" "$tmp_context" | \
  codex --ask-for-approval never exec \
    --model "$review_model" \
    --config "model_reasoning_effort=\"$review_effort\"" \
    --sandbox read-only \
    --skip-git-repo-check \
    --ephemeral \
    --ignore-rules \
    --cd "$tmp_cwd" \
    -
rm -f "$tmp_prompt" "$tmp_context"
rmdir "$tmp_cwd"
```

   - Keep the review prompt and curated file context in the same stdin stream.
   - The command uses `--model` and `model_reasoning_effort` so inherited lower-quality settings do not override the intended review settings.
   - The temporary `--cd` directory keeps the external reviewer away from the repository filesystem; it should reason from the curated context, not scan arbitrary files.
   - If Codex CLI is unavailable, tell the user external GPT review is unavailable. Do not present a self-review as a GPT peer review.

5. Validate findings before acting.
   - Do not accept external feedback at face value.
   - For each major finding, inspect the referenced files, reproduce the issue when possible, and classify it as:
     - accept and fix
     - accept and document/defer
     - reject with reason
     - needs user decision

   Use this rule: GPT finds candidates; Codex proves or disproves them against the repo.

6. Implement only the right scope.
   - If the user asked for review only, do not modify files unless the newest request permits it.
   - If the user asked to proceed, apply small, high-confidence fixes and document strategic deferrals.
   - Keep unrelated refactors out.

7. Report the outcome.
   - Summarize GPT's strongest feedback.
   - Explain what you accepted, deferred, or rejected.
   - List verification commands and results.
   - Never paste secrets or raw `.env` values.

## Context Selection Guide

Use targeted context bundles:

- Data/schema review: product docs, data model docs, migrations, ORM models, extraction schemas, ingestion/extraction/analytics services, representative tests.
- Architecture review: README, product docs, deployment docs, service entry points, config, dependency manifests, core modules, tests.
- Production readiness: deployment docs, compose/config files without secrets, health/ops endpoints, tests, CI files, security-sensitive code.
- Frontend/product review: product docs, frontend routes/components/styles, API client types, screenshots if available.
- Diff critique: use `git diff --stat`, `git diff --name-only`, relevant touched files, and tests. Do not blindly include generated files or lockfiles unless dependency behavior is under review.

Keep the bundle small enough for the external reviewer to reason over. A sharper 10-file review usually beats a noisy whole-repo dump.

## Safety Rules

- Do not send `.env`, `.env.*`, secret stores, key files, local databases, logs, caches, or build artifacts to an external model.
- Do not run the external reviewer in the repo root unless the user explicitly asks and the review requires it.
- Prefer the temporary empty `--cd` directory and `--sandbox read-only` for one-off external reviews.
- Prefer `--ephemeral` so the external review does not persist a normal Codex session.
- Prefer the default `gpt-5.5` with `model_reasoning_effort="xhigh"` settings.
- Do not use `gpt-5.55` unless the local Codex model catalog explicitly exposes that exact model ID.
- Do not use `--allow-untracked` until you personally inspect the untracked files.
- Remember that tracked does not mean secret-free; inspect the `--list` output and be cautious with config files.
- Keep the external model's output as advice. Codex owns verification and final edits.

## Decision Standard

Accept external feedback when it is:

- grounded in provided files,
- relevant to the user's goal,
- reproducible or logically valid,
- appropriately scoped for the current milestone.

Defer feedback when it is strategically useful but not required for the current milestone. Reject feedback when it is speculative, contradicted by the repo, or would add complexity without a clear payoff.

## Output Shape

When reporting back to the user, include:

- the selected review mode,
- how context was curated,
- GPT's strongest useful feedback,
- findings accepted, deferred, rejected, or needing user decision,
- edits made, if any,
- verification run and results.

Keep the summary concise. Put the external model's raw output in a file only if the user asks for an audit trail.
