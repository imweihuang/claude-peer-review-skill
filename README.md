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

## Collaboration Model

This skill is built around a three-role workflow:

```text
Codex = implementer + repo operator
Claude = outside reviewer + strategist + red-team peer
User = product owner + final decision-maker
```

Claude proposes candidates and critiques. Codex verifies them against the repository, applies changes when appropriate, and explains what was accepted, deferred, or rejected. The user keeps product judgment and final direction.

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

By default, live reviews run Claude Code in print mode with tools disabled, `claude-opus-4-7`, xHigh effort, no session persistence, and a 3 USD budget cap. Override a single request with:

```bash
CLAUDE_PEER_REVIEW_MODEL=claude-opus-4-7 \
CLAUDE_PEER_REVIEW_EFFORT=xhigh \
CLAUDE_PEER_REVIEW_MAX_BUDGET_USD=3
```

## Optional Tools

The safest default is no Claude tools:

```bash
CLAUDE_PEER_REVIEW_TOOLS=""
```

Enable tools only for the current review when the user explicitly approves the need:

```bash
# Current external facts: competitors, latest docs, CVEs, pricing, vendor changes.
CLAUDE_PEER_REVIEW_TOOLS="WebSearch,WebFetch"

# Large read-only repo review when curated context is not enough.
CLAUDE_PEER_REVIEW_TOOLS="Read,Grep,Glob"

# Mixed current-info plus read-only repo exploration.
CLAUDE_PEER_REVIEW_TOOLS="Read,Grep,Glob,WebSearch,WebFetch"
```

Do not enable edit/write tools for this skill. Enable `Bash` only when the user explicitly wants Claude to run verification commands; Codex still owns validation and final edits.

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
