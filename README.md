# Peer Review Skills

This repository contains Codex skills for safe external software peer review.

Primary skill:

- `peer-review`: run independent Claude, Codex/GPT, Gemini, and Grok Build CLI peer reviews, then have Codex reconcile and validate the findings.

Compatibility entry points:

- `claude-peer-review`: Claude-only preset for the unified runner.
- `gpt-peer-review`: Codex/GPT-only preset for the unified runner.
- `claude-gpt-peer-review`: Claude plus Codex/GPT preset for the unified runner.

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

| Reviewer | CLI | Default model | Default effort |
| --- | --- | --- | --- |
| Claude | `claude` | `claude-opus-4-8` | `max` |
| Codex/GPT | `codex` | `gpt-5.5` | `xhigh` |
| Gemini | `gemini` | `gemini-3.1-pro` | reported as `not-cli-exposed` unless the local CLI exposes a thinking flag |
| Grok Build | `grok` | `grok-build` | `max`; `reasoning_effort=high` |

The runner does not silently downgrade. If a CLI, model, auth state, or effort setting is unavailable, the report says so clearly.

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
```

Manual install:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R peer-review "${CODEX_HOME:-$HOME/.codex}/skills/"
cp -R claude-peer-review "${CODEX_HOME:-$HOME/.codex}/skills/"
cp -R gpt-peer-review "${CODEX_HOME:-$HOME/.codex}/skills/"
cp -R claude-gpt-peer-review "${CODEX_HOME:-$HOME/.codex}/skills/"
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
```

Preflight local CLIs and requested settings:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/peer-review/scripts/run_peer_review.py" --preflight
```

Run a targeted review:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/peer-review/scripts/run_peer_review.py" \
  --mode "Diff Critique" \
  --milestone "current milestone" \
  --focus "correctness bugs and behavioral regressions" \
  --focus "missing tests and security boundaries" \
  README.md src tests
```

Run a subset:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/peer-review/scripts/run_peer_review.py" \
  --reviewers claude,gpt \
  README.md src tests
```

## Requirements

- Codex with skills enabled
- `claude` CLI installed and authenticated for Claude reviews
- `codex` CLI installed and authenticated for GPT reviews
- `gemini` CLI installed and authenticated for Gemini reviews
- `grok` CLI installed and authenticated for Grok Build reviews
- Git installed for tracked-file context selection

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

## Repository Structure

```text
peer-review/
  SKILL.md
  agents/openai.yaml
  references/prompt-template.md
  scripts/build_review_context.py
  scripts/run_peer_review.py
claude-peer-review/
  SKILL.md
  agents/openai.yaml
gpt-peer-review/
  SKILL.md
  agents/openai.yaml
claude-gpt-peer-review/
  SKILL.md
  agents/openai.yaml
```

## License

MIT
