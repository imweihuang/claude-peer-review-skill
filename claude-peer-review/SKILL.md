---
name: claude-peer-review
description: Run Claude CLI as a safe external peer reviewer for software projects, including strategy review, architecture review, data/schema review, production-readiness review, code audit, security-boundary review, API contract review, product-methodology review, coverage audit, or second-opinion/deciding-vote requests. Use when the user explicitly asks Codex to ask Claude for a candid review, peer review, strategist review, red-team review, honest feedback, or cross-model second opinion, and when Codex must validate findings rather than blindly accept them.
---

# Claude Peer Review

## Purpose

Use this skill to get a Claude peer review without losing control of scope, secrets, or decision quality. Treat Claude as a candid peer reviewer, not an authority.

Default roles:

- Codex: repo operator, implementer, and validator.
- Claude: strategist, code auditor, red-team reviewer, or architecture/schema reviewer.
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

Default Claude peer reviews to Opus 4.8 adaptive reasoning at xHigh effort when the installed Claude CLI and account allow it:

- Model: `claude-opus-4-8`
- Effort: `xhigh`
- Budget: `3` USD unless the task context or user request justifies a different cap

Use per-request environment overrides when needed:

- `CLAUDE_PEER_REVIEW_MODEL` for model ID or alias
- `CLAUDE_PEER_REVIEW_EFFORT` for `low`, `medium`, `high`, `xhigh`, or `max`
- `CLAUDE_PEER_REVIEW_MAX_BUDGET_USD` for print-mode spend cap
- `CLAUDE_PEER_REVIEW_TOOLS` for an explicit Claude CLI tool allowlist; defaults to empty, which disables tools

Do not silently downgrade to Sonnet or lower effort. If Opus 4.8 or xHigh effort is unavailable, report that external review could not run under the requested settings and ask before using a fallback.

## Tool Policy

Default peer reviews run with no Claude tools: `CLAUDE_PEER_REVIEW_TOOLS=""`. This keeps Claude limited to the curated context bundle and prevents accidental extra file reads, shell commands, edits, or secret exposure.

Enable tools only when the review genuinely needs them:

| Tool set | Use for | Notes |
| --- | --- | --- |
| empty string | Standard repo, code, architecture, launch-readiness, and coverage reviews | Default and safest |
| `WebSearch,WebFetch` | Current external facts: competitor research, latest docs, CVEs, pricing, vendor/platform changes | Do not include private project details in search terms unless the user approves |
| `Read,Grep,Glob` | Large read-only repo reviews where curated context is insufficient | Use only with explicit user approval and a trusted checkout |
| `Read,Grep,Glob,WebSearch,WebFetch` | Mixed repo plus current external research | Still read-only |

Do not enable `Edit`, write tools, or broad shell access for this skill. Enable `Bash` only when the user explicitly asks Claude to run verification commands, and keep Codex responsible for validating the results.

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
python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-peer-review/scripts/build_review_context.py" --list README.md docs backend/src backend/tests
```

   - Prefer the bundled context helper:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-peer-review/scripts/build_review_context.py" README.md docs backend/src backend/tests
```

   - Add `--allow-untracked` only for newly created non-secret docs/code that you have inspected.

3. Prepare the external-review prompt.
   - Read `references/prompt-template.md` when writing or adapting the prompt.
   - State the chosen review mode and current milestone.
   - State the Claude tool policy: no tools by default, or the exact approved tool allowlist.
   - Require file-grounded, ranked feedback.
   - Require "must fix now" versus "defer" separation.
   - Forbid secret inspection and file edits.

4. Run the external reviewer safely.
   - If Claude CLI is available and requested or appropriate, use print mode with tools disabled:

```bash
tmp_prompt="$(mktemp)"
tmp_context="$(mktemp)"
review_model="${CLAUDE_PEER_REVIEW_MODEL:-claude-opus-4-8}"
review_effort="${CLAUDE_PEER_REVIEW_EFFORT:-xhigh}"
review_budget="${CLAUDE_PEER_REVIEW_MAX_BUDGET_USD:-3}"
review_tools="${CLAUDE_PEER_REVIEW_TOOLS:-}"
cat > "$tmp_prompt" <<'PROMPT'
<prompt>
PROMPT
python3 "${CODEX_HOME:-$HOME/.codex}/skills/claude-peer-review/scripts/build_review_context.py" <files...> > "$tmp_context"
cat "$tmp_prompt" "$tmp_context" | \
  ANTHROPIC_MODEL="$review_model" CLAUDE_CODE_EFFORT_LEVEL="$review_effort" \
  claude -p \
    --tools "$review_tools" \
    --no-session-persistence \
    --model "$review_model" \
    --effort "$review_effort" \
    --max-budget-usd "$review_budget"
rm -f "$tmp_prompt" "$tmp_context"
```

   - Keep the review prompt and curated file context in the same stdin stream.
   - Keep `review_tools` empty unless the user explicitly approved an allowlist for the current review.
   - The default full model ID is intentional for reproducibility. Override it only when the user requests a different model or the account cannot run it.
   - The command sets `ANTHROPIC_MODEL` and `CLAUDE_CODE_EFFORT_LEVEL` for the child process so inherited lower-quality settings do not override the intended review settings.
   - Opus 4.8 uses adaptive reasoning; use `--effort` to control reasoning depth instead of legacy fixed thinking budget variables.
   - If Claude CLI is unavailable, tell the user external review is unavailable. Do not present a self-review as a Claude peer review.

5. Validate findings before acting.
   - Do not accept external feedback at face value.
   - For each major finding, inspect the referenced files, reproduce the issue when possible, and classify it as:
     - accept and fix
     - accept and document/defer
     - reject with reason
     - needs user decision

   Use this rule: Claude finds candidates; Codex proves or disproves them against the repo.

6. Implement only the right scope.
   - If the user asked for review only, do not modify files unless the newest request permits it.
   - If the user asked to proceed, apply small, high-confidence fixes and document strategic deferrals.
   - Keep unrelated refactors out.

7. Report the outcome.
   - Summarize Claude's strongest feedback.
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
- Do not run external tools with filesystem, shell, or web permissions unless the user explicitly asks and the review requires it.
- Prefer `--tools ""` for Claude CLI review.
- Use `WebSearch,WebFetch` only for current external facts such as competitor research, latest docs, CVEs, pricing, or vendor/platform changes.
- Use `Read,Grep,Glob` only for approved read-only repo exploration in a trusted checkout.
- Do not enable edit/write tools for this skill.
- Prefer `--no-session-persistence` for one-off external reviews.
- Prefer the default `claude-opus-4-8 --effort xhigh` settings for high-quality review. Use `max` only when the user explicitly asks for maximum available reasoning and cost/latency are acceptable.
- Do not use `--allow-untracked` until you personally inspect the untracked files.
- Remember that tracked does not mean secret-free; inspect the `--list` output and be cautious with config files.
- `--max-budget-usd 3` is only a default example. Adjust it for context size and user preference.
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
- Claude's strongest useful feedback,
- findings accepted, deferred, rejected, or needing user decision,
- edits made, if any,
- verification run and results.

Keep the summary concise. Put the external model's raw output in a file only if the user asks for an audit trail.
