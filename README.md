# Peer Review Skills

This repository contains Codex skills for running safe external peer reviews of software projects:

- `claude-peer-review`: run Claude CLI as a peer reviewer.
- `gpt-peer-review`: run Codex CLI with GPT-5.5 as a peer reviewer.
- `claude-gpt-peer-review`: run independent Claude and GPT reviews, then have Codex reconcile and validate the findings.

They are useful for:

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
External model = outside reviewer + strategist + red-team peer
User = product owner + final decision-maker
```

The external reviewers propose candidates and critiques. Codex verifies them against the repository, applies changes when appropriate, and explains what was accepted, deferred, or rejected. The user keeps product judgment and final direction.

## Why This Skill Exists

Using another model as a peer reviewer can be valuable, but only if the workflow is controlled. These skills help Codex:

- avoid sending `.env`, keys, logs, local databases, caches, and build artifacts
- keep Claude's filesystem tools disabled by default
- keep GPT reviews in a temporary empty working directory by default
- ask for file-grounded findings
- separate must-fix items from strategic improvements
- validate external suggestions before changing code

External models are treated as advisors, not authorities.

## Install

In Codex, ask:

```text
Install the Codex skill from https://github.com/imweihuang/claude-peer-review-skill/tree/main/claude-peer-review
```

Or install the GPT and dual-review skills:

```text
Install the Codex skill from https://github.com/imweihuang/claude-peer-review-skill/tree/main/gpt-peer-review
Install the Codex skill from https://github.com/imweihuang/claude-peer-review-skill/tree/main/claude-gpt-peer-review
```

Then restart Codex so the new skill is discovered.

Manual install:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R claude-peer-review "${CODEX_HOME:-$HOME/.codex}/skills/"
cp -R gpt-peer-review "${CODEX_HOME:-$HOME/.codex}/skills/"
cp -R claude-gpt-peer-review "${CODEX_HOME:-$HOME/.codex}/skills/"
```

## Usage Examples

```text
Use $claude-peer-review to run Claude as a code-audit peer on this repo.
```

```text
Use $gpt-peer-review to run GPT-5.5 as a code-audit peer on this repo.
```

```text
Use $claude-gpt-peer-review to ask both Claude and GPT for independent production-readiness reviews.
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
- Codex CLI installed and authenticated for live GPT reviews
- Git installed for tracked-file context selection

If a required CLI is unavailable, the skills instruct Codex to say so rather than pretending an internal self-review is an external review.

Default reviewer models:

| Skill | Reviewer Defaults |
| --- | --- |
| `claude-peer-review` | `claude-opus-4-8`, xHigh effort, tools disabled, no session persistence, 3 USD default cap |
| `gpt-peer-review` | `gpt-5.5`, xHigh effort, temporary empty working directory, read-only sandbox |
| `claude-gpt-peer-review` | Claude `claude-opus-4-8` xHigh and GPT `gpt-5.5` xHigh |

Override a Claude-only request with:

```bash
CLAUDE_PEER_REVIEW_MODEL=claude-opus-4-8 \
CLAUDE_PEER_REVIEW_EFFORT=xhigh \
CLAUDE_PEER_REVIEW_MAX_BUDGET_USD=3
```

Override a GPT-only request with:

```bash
GPT_PEER_REVIEW_MODEL=gpt-5.5 \
GPT_PEER_REVIEW_EFFORT=xhigh
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

Do not enable edit/write tools for these skills. Enable `Bash` only when the user explicitly wants Claude to run verification commands; Codex still owns validation and final edits.

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
gpt-peer-review/
  SKILL.md
  agents/openai.yaml
  references/prompt-template.md
  scripts/build_review_context.py
claude-gpt-peer-review/
  SKILL.md
  agents/openai.yaml
  references/prompt-template.md
  scripts/build_review_context.py
```

## License

MIT
