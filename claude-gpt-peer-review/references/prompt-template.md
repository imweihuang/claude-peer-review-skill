# Claude + GPT Peer Review Prompt Template

Use this template when asking Claude and GPT to independently review the same repo context. Send the same prompt and context to both reviewers before reading either model's answer.

```text
You are acting as a candid strategist and senior peer reviewer for <PROJECT>.

Project goal:
<One or two sentences explaining what the project is trying to achieve.>

Current milestone:
<Internal MVP, production pilot, public launch prep, refactor, etc. Include scope limits.>

Review mode:
<Strategy Review | Data/Schema Review | Diff Critique | Launch Readiness | Coverage Audit | Deciding Vote>

Your task:
Review the selected repository context below, especially:
1. <focus area>
2. <focus area>
3. <focus area>

Constraints:
- Use only the supplied context unless explicitly told otherwise.
- Do not inspect or request .env, secrets, credentials, private keys, runtime logs, untracked files, or unrelated user files.
- Do not edit files.
- Ground findings in the provided code/docs.
- Separate must-fix issues from strategic improvements.
- Be honest, critical, and practical.
- Treat the current milestone seriously; do not demand future-scale work unless it blocks this milestone.
- Do not give generic advice; tie recommendations to the provided context.
- Prefer concise output. Prioritize the highest-risk findings over exhaustive commentary.

Output format:
1. What is strong
2. What is fragile
3. Must fix before <milestone>
4. Defer / later
5. Recommended repo changes, ranked by strategic importance
6. Findings that are speculative or need verification
7. Any product/schema/architecture insight that changes your view of the project
```

## Synthesis Prompt Shape

After both external reviews complete, Codex should synthesize them without treating either model as authoritative:

```text
Compare the two reviews against the repository evidence.

Group findings by:
1. Both reviewers agree
2. Claude-only
3. GPT-only
4. Direct conflict
5. Speculative or unverifiable

For each important finding, decide:
- accept and fix
- accept and document/defer
- reject with reason
- needs user decision
```

## Common Focus Areas

Data/schema review:

```text
data schema, raw-to-structured pipeline, future source generality, event/object semantics, auditability, versioning, migration strategy, tests
```

Market intelligence or AI extraction review:

```text
source normalization, extraction schema, prompt/output contract, quote/repost/reply/media handling, mindshare versus predictions, confidence/review workflow, quantification/scoring
```

Production readiness review:

```text
configuration, secrets handling, deployment path, migrations, health checks, observability, data recovery, auth boundaries, operational runbooks, tests
```

Architecture review:

```text
module boundaries, provider abstractions, data flow, extensibility, failure modes, coupling, test strategy, complexity budget
```

Diff critique:

```text
behavioral regressions, edge cases, security/auth boundaries, missing tests, migration risk, changed public contracts, generated-file noise
```

Deciding vote:

```text
compare option A versus option B against current constraints, operational risk, future extensibility, implementation cost, and reversibility
```
