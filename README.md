# Peer Review Skills

This repository contains Codex skills for safe external software peer review.

Primary skill:

- `peer-review`: run independent Claude, Codex/GPT, and Grok Build CLI peer reviews by default, with Gemini opt-in, then have Codex reconcile and validate the findings.

Compatibility entry points:

- `claude-peer-review`: Claude-only preset for the unified runner.
- `gpt-peer-review`: Codex/GPT-only preset for the unified runner.
- `claude-gpt-peer-review`: Claude plus Codex/GPT preset for the unified runner.
- `chatgpt-pro-peer-review`: browser-backed ChatGPT GPT-5.5 Pro / Extended Pro review.

The core pattern is:

```text
curate safe repo context
  -> run independent CLI reviewers
  -> report exact participants, models, and efforts
  -> have Codex validate each finding
  -> accept, defer, reject, or implement deliberately
```

External reviewers propose candidates and critiques. Codex verifies them against the repository, applies changes when appropriate, and explains what was accepted, deferred, or rejected. The user keeps product judgment and final direction.

## Defaults

Humans do not need to specify `--intensity` when calling the skill. The skill infers the review intensity from the request, passes the matching flag to the runner, and reports what it selected. Default intensity is `gate` when the target is ambiguous or the runner is called directly without a selected intensity.

| Reviewer | CLI | Gate/Critical model | Gate/Critical effort |
| --- | --- | --- | --- |
| Claude | `claude` | Opus 4.8 via `opus` alias | `xhigh` |
| Codex/GPT | `codex` | `gpt-5.5` | `xhigh` |
| Grok Build | `grok` | `grok-composer-2.5-fast` | `max`; `reasoning_effort=high` |

Intensity presets:

| Intensity | Use For | Claude/Codex Effort |
| --- | --- | --- |
| `planning` | Queue discovery and task prioritization | `high` |
| `gate` | Pre-merge, readiness, and normal blocking reviews | `xhigh` |
| `critical` | Schema, security, deploy, live-data, API, provenance, point-in-time, or weak/conflicting verification | `xhigh` |

Gemini remains supported but is opt-in through `--reviewers gemini` or `--reviewers all-with-gemini`.

The runner does not silently downgrade. If a CLI, model, auth state, or effort setting is unavailable, the report says so clearly.

Reviewer CLIs run independently and in parallel by default, up to `--jobs 4` or `PEER_REVIEW_JOBS`. Use `--jobs 1` when debugging one reviewer at a time.

## Install

In Codex, install the primary skill:

```text
Install the Codex skill from https://github.com/imweihuang/claude-peer-review-skill/tree/main/peer-review
```

Optional compatibility installs:

```text
Install the Codex skill from https://github.com/imweihuang/claude-peer-review-skill/tree/main/claude-peer-review
Install the Codex skill from https://github.com/imweihuang/claude-peer-review-skill/tree/main/gpt-peer-review
Install the Codex skill from https://github.com/imweihuang/claude-peer-review-skill/tree/main/claude-gpt-peer-review
Install the Codex skill from https://github.com/imweihuang/claude-peer-review-skill/tree/main/chatgpt-pro-peer-review
```

Manual install:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R peer-review "${CODEX_HOME:-$HOME/.codex}/skills/"
cp -R claude-peer-review "${CODEX_HOME:-$HOME/.codex}/skills/"
cp -R gpt-peer-review "${CODEX_HOME:-$HOME/.codex}/skills/"
cp -R claude-gpt-peer-review "${CODEX_HOME:-$HOME/.codex}/skills/"
cp -R chatgpt-pro-peer-review "${CODEX_HOME:-$HOME/.codex}/skills/"
```

Restart Codex so the new skill metadata is discovered.

## Usage

Default all-reviewer council:

```text
Use $peer-review to run a production-readiness review of this repository.
```

Specific presets:

```text
Use $claude-peer-review to run Claude as a code-audit peer on this repo.
Use $gpt-peer-review to run GPT-5.5 as a code-audit peer on this repo.
Use $claude-gpt-peer-review to ask both Claude and GPT for independent production-readiness reviews.
Use $chatgpt-pro-peer-review to ask ChatGPT GPT-5.5 Pro / Extended Pro through the browser.
```

`chatgpt-pro-peer-review` waits up to 45 minutes for Extended Pro by default, using repeated browser polls. Override with `CHATGPT_PRO_BROWSER_TIMEOUT_SECONDS`.

Preflight local CLIs and requested settings:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/peer-review/scripts/run_peer_review.py" --preflight
```

Manually check/update reviewer CLIs and model-default evidence:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/peer-review/scripts/refresh_peer_review_clis.py"
```

Update CLIs explicitly:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/peer-review/scripts/refresh_peer_review_clis.py" --update
```

The refresh command reports installed versions, package-manager latest versions, local model catalogs, and proposed default changes. It does not rewrite skill defaults automatically.

Run a targeted review:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/peer-review/scripts/run_peer_review.py" \
  --mode "Diff Critique" \
  --review-scope strict \
  --intensity gate \
  --milestone "current milestone" \
  --focus "correctness bugs and behavioral regressions" \
  --focus "missing tests and security boundaries" \
  README.md src tests
```

`--review-scope` controls evidence policy. Use `strict` for implementation, launch, schema, security, and diff reviews; `broad-repo` for internal architecture reviews needing wider curated context; `strategy-open` or `web-research` for open-ended/current-info questions where external source discovery may help. The runner's default `auto` fails closed to `strict`; the skill should pass an explicit scope after reading the user's request.

`--intensity` controls effort policy. Use `planning` for recursive queue discovery and task prioritization, `gate` for pre-merge/readiness checks, and `critical` for high-risk schema, security, deploy, live-data, API, provenance, point-in-time, or weak/conflicting verification decisions.

Humans do not need to specify tool flags. Tool policy is inferred from `--review-scope`: `strict`, `broad-repo`, and fallback `auto` use `context-only`; `strategy-open` and `web-research` use `web-allowed`. `context-only` means curated context only. `web-allowed` permits web/source research only where a reviewer runtime exposes a verified safe toggle. Reviewer local repo browsing and write/action tools are never allowed.

Run a subset:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/peer-review/scripts/run_peer_review.py" \
  --reviewers claude,gpt \
  README.md src tests
```

By default a run exits nonzero if any requested reviewer fails. Add `--allow-partial` only when a degraded council is acceptable.

Limit or disable parallelism for a run:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/peer-review/scripts/run_peer_review.py" \
  --jobs 1 \
  README.md src tests
```

## Requirements

- Codex with skills enabled
- `claude` CLI installed and authenticated for Claude reviews
- `codex` CLI installed and authenticated for GPT reviews
- `gemini` CLI installed and authenticated for Gemini reviews, if requested
- `grok` CLI installed and authenticated for Grok Build reviews
- Git installed for tracked-file context selection
- Chrome with the Codex Chrome Extension and a logged-in ChatGPT Pro session for `chatgpt-pro-peer-review`

If a required CLI is unavailable or unauthenticated, the skill reports that status rather than pretending an internal self-review is an external review.

## Safety Model

The bundled context helper only includes selected files and skips common unsafe paths:

- `.env` and `.env.*`
- private keys and credential files
- local databases
- logs
- caches
- build outputs
- binary media/archive files
- paths outside the repo root

It also fails closed outside git by default, rejects common secret/token content patterns, blocks symlink targets outside the root, and emits an in-band `CONTEXT OMITTED` marker when the total byte limit drops files.

Reviewer-side web/source research is disabled for strict and broad-repo scopes. In strategy-open and web-research scopes, it is allowed only where a reviewer runtime exposes a verified safe toggle; the manifest reports each reviewer’s actual web/tool status. Codex/GPT remains read-only even when external research is requested.

Inspect selected context before running reviewers:

```bash
python3 peer-review/scripts/build_review_context.py --list README.md docs src tests
```

Generate a context bundle:

```bash
python3 peer-review/scripts/build_review_context.py README.md docs src tests
```

The helper defaults to a 1 MB total bundle and 100 KB per file. If a targeted review needs more context, raise the limits for that run:

```bash
PEER_REVIEW_MAX_TOTAL_BYTES=1500000 \
PEER_REVIEW_MAX_BYTES_PER_FILE=150000 \
python3 peer-review/scripts/build_review_context.py README.md docs src tests
```

If the helper still reports `total byte limit reached`, split the review by subsystem instead of sending one giant prompt.

Use `--allow-untracked` only for new non-secret files that you have inspected.
Use `--allow-non-git-context` and `--allow-secret-like-content` only after manual inspection.

## Repository Structure

```text
peer-review/
  SKILL.md
  agents/openai.yaml
  references/prompt-template.md
  scripts/build_review_context.py
  scripts/refresh_peer_review_clis.py
  scripts/run_peer_review.py
tests/
  test_peer_review_scripts.py
claude-peer-review/
  SKILL.md
  agents/openai.yaml
gpt-peer-review/
  SKILL.md
  agents/openai.yaml
claude-gpt-peer-review/
  SKILL.md
  agents/openai.yaml
chatgpt-pro-peer-review/
  SKILL.md
  agents/openai.yaml
```

## License

MIT
