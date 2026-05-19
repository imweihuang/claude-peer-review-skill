# Claude Peer Review Skill

`claude-peer-review` is a Codex skill for running Claude CLI as a safe external peer reviewer for a software project.

It is useful for:

- code audits
- architecture reviews
- data/schema reviews
- production-readiness reviews
- API contract reviews
- product strategy and methodology reviews
- "give me honest feedback" second-opinion reviews

The core pattern is:

```text
curate safe repo context
  -> ask Claude for candid, ranked feedback
  -> have Codex validate each finding
  -> accept, defer, reject, or implement deliberately
```

## Why This Skill Exists

Using another model as a peer reviewer can be valuable, but only if the workflow is controlled. This skill helps Codex:

- avoid sending `.env`, keys, logs, local databases, caches, and build artifacts
- keep Claude's filesystem tools disabled by default
- ask for file-grounded findings
- separate must-fix items from strategic improvements
- validate Claude's suggestions before changing code

Claude is treated as an advisor, not an authority.

## Install

In Codex, ask:

```text
Install the Codex skill from https://github.com/imweihuang/claude-peer-review-skill/tree/main/claude-peer-review
```

Then restart Codex so the new skill is discovered.

Manual install:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R claude-peer-review "${CODEX_HOME:-$HOME/.codex}/skills/"
```

## Usage Examples

```text
Use $claude-peer-review to run Claude as a code-audit peer on this repo.
```

```text
Use $claude-peer-review to ask Claude for an honest schema and architecture review.
```

```text
Use $claude-peer-review to review production readiness before launch.
```

```text
Use $claude-peer-review to evaluate this PR-like diff for correctness bugs and missing tests.
```

## Requirements

- Codex with skills enabled
- Claude CLI installed and authenticated for live Claude reviews
- Git installed for tracked-file context selection

If Claude CLI is unavailable, the skill instructs Codex to say so rather than pretending an internal self-review is a Claude review.

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

You can inspect selected context before running Claude:

```bash
python3 claude-peer-review/scripts/build_review_context.py --list README.md docs src tests
```

Generate a context bundle:

```bash
python3 claude-peer-review/scripts/build_review_context.py README.md docs src tests
```

Use `--allow-untracked` only for new non-secret files that you have inspected.

## Repository Structure

```text
claude-peer-review/
  SKILL.md
  agents/openai.yaml
  references/prompt-template.md
  scripts/build_review_context.py
```

## License

MIT
