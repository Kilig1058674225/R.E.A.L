---
name: real-decision-agent-dev
description: Project-local development workflow for the REAL decision-support agent. Use when Codex is working inside E:\AIwork\real on product planning, architecture, implementation, documentation, bug tracking, progress updates, smart-search-cli integration, mobile/web/MCP deployment, conversation management, decision workflows, or any task related to building the REAL life decision agent.
---

# REAL Decision Agent Dev

## Startup Ritual

Before making changes in this project:

1. Read `E:\AIwork\real\docs\development-plan.md`.
2. Read `E:\AIwork\real\docs\progress.md`.
3. Check `E:\AIwork\real\docs\bug-feedback.md` for active issues.
4. If a decision depends on current product behavior, docs, policy, pricing, or external facts, use `smart-search-cli` and record the command/source in the relevant doc.

## Product North Star

Build a mobile-first decision-support agent for a hesitant user. The product should help transform vague hesitation into one of four action types:

- Reject
- Observe
- Small experiment
- Stage-gated increase

The agent must not act like a generic chatbot. It should run a structured decision workflow with evidence checks, risk gates, expected value, MCDA, premortem, information-value planning, and decision journaling.

## Architecture Bias

Prefer a server-hosted web app as the primary product path because it supports mobile browsers, persistent storage, multi-dialogue management, tool execution, smart-search-cli, and future remote MCP exposure.

Treat RikkaHub or Cherry Studio markdown skills as companion interfaces unless their current mobile capabilities are explicitly confirmed for the required tool execution and state management. RikkaHub remote MCP support can be useful later through a server-side MCP endpoint.

## Development Rules

- Keep docs updated when architecture, scope, or priorities change.
- Add a dated entry to `docs/progress.md` after meaningful work.
- Add bugs, uncertainties, and user feedback to `docs/bug-feedback.md`.
- Separate LLM judgment from deterministic computation:
  - LLM: clarify problem, generate hypotheses, propose criteria, explain tradeoffs.
  - Code: score EV/MCDA, enforce risk gates, store state, run search wrapper, validate schemas.
- Do not let aggregate score override anti-ruin gates.
- Preserve multi-dialogue context with explicit session/case state, rolling summaries, and evidence records.

## Smart Search Policy

Use the local `smart-search` CLI for external research. Prefer:

- `smart-search doctor --format json` when availability is uncertain.
- `smart-search search ... --validation balanced --extra-sources 1..3 --format json` for broad discovery.
- `smart-search exa-search ... --include-highlights --format json` for source discovery.
- `smart-search fetch <url> --format markdown` before making source-backed claims.

Store important evidence under `C:\tmp\smart-search-evidence\...` and cite commands/URLs in docs when they influence product decisions.

## Core Docs

- `E:\AIwork\real\docs\development-plan.md`: product and technical plan.
- `E:\AIwork\real\docs\progress.md`: dated work log.
- `E:\AIwork\real\docs\bug-feedback.md`: bugs, risks, feedback, unresolved questions.
- `E:\AIwork\real\docs\research-notes.md`: external research notes and source links.

## Expected First Implementation Shape

Start with:

- FastAPI backend
- SQLite database
- Pydantic schemas
- React or Next.js mobile-first frontend
- server-side `smart-search` wrapper
- decision case/session/journal data model

Defer native mobile app work until the web app workflow proves useful.
