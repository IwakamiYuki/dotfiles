---
name: sequential-thinking
description: "Break complex problems into manageable sequential steps with structured reasoning. Use when: (1) Problems require multi-step analysis, (2) Multiple hypotheses need validation, (3) Design/architecture decisions need systematic evaluation, (4) Root cause analysis requires progressive investigation, (5) Ambiguous requirements need clarification through staged exploration."
---

# Sequential Thinking

## Overview

Enable systematic problem-solving by breaking complex tasks into discrete thinking steps, with support for revisions and branching when new information emerges.

## Core Format

Each thinking step follows this structure:

```markdown
## [Thought N/M]

**Focus:** [What this step addresses]

**Analysis:** [Detailed reasoning]

**Next:** Continue? [Yes/No] - [If yes, what to explore]
```

- **N/M**: Current step / Estimated total (adjust M as understanding evolves)
- Keep steps focused on single aspect
- Make reasoning explicit and traceable

## Revisions

When previous understanding was incorrect:

```markdown
## [Revision: Thought 2]

**Why:** [Reason for revision]

**Updated understanding:** [Corrected analysis]
```

## Branching

To explore alternative directions:

```markdown
## [Branch A: from Thought 4]

**Why branch:** [Reason to explore alternative]

**Direction:** [What this branch investigates]
```

## Examples

### Debug Analysis

```markdown
## [Thought 1/4]

**Focus:** Identify error scope from message

**Analysis:** "undefined is not a function" suggests calling non-existent method.
Stack trace points to API response handler.

**Next:** Yes - Examine API response structure and handler expectations

## [Thought 2/4]

**Focus:** Compare expected vs actual API response

**Analysis:** Handler expects `data.items.map()` but API returns `data.results`.
Field name mismatch between API contract and code.

**Next:** Yes - Check if API changed or code has wrong assumption
```

### Architecture Design

```markdown
## [Thought 1/5]

**Focus:** Clarify requirements and constraints

**Analysis:**
- Real-time updates needed
- 10k concurrent users
- <100ms latency requirement

**Next:** Yes - Evaluate technology options against constraints

## [Thought 2/5]

**Focus:** Compare WebSocket vs SSE vs Polling

**Analysis:**
- WebSocket: Bidirectional, low latency, scaling complexity
- SSE: Unidirectional, simpler, HTTP/2 efficient
- Polling: High latency, avoid

**Next:** Yes - Deep dive WebSocket scaling approaches

## [Branch A: from Thought 2]

**Why branch:** SSE might be sufficient if updates are one-way

**Direction:** Investigate SSE + Redis Pub/Sub scalability
```

## When to Use

- Problem needs 3+ distinct analysis steps
- Multiple hypotheses require systematic validation
- Design requires comparing trade-offs
- Incremental information gathering needed

## When NOT to Use

- Simple factual questions
- Single-file code modifications
- Well-defined procedural tasks

## Principles

1. **Transparency**: Make reasoning explicit at each step
2. **Flexibility**: Revise plan as new information emerges
3. **Traceability**: Maintain clear logical progression
4. **Focus**: One clear objective per thought step
