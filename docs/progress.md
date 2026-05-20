# Progress Log

## 2026-05-20

- Read the smart-search-cli skill and confirmed local web research capability.
- Ran `smart-search doctor --format json` and confirmed the search stack is configured and healthy.
- Ran deep research planning for the decision-agent project.
- Researched decision theory and agent architecture:
  - expected utility and multi-criteria decision making
  - premortem and risk management
  - Bayesian evidence updating
  - Cynefin problem classification
  - agent runtimes, memory, tools, and guardrails
  - mobile client capabilities for RikkaHub and Cherry Studio
- Created project-local skill scaffold:
  - `E:\AIwork\real\.codex\skills\real-decision-agent-dev`
- Drafted the first version of the project skill for REAL decision-agent development.
- Created project documentation structure under `E:\AIwork\real\docs`.
- Created initial project docs:
  - `development-plan.md`
  - `progress.md`
  - `bug-feedback.md`
  - `research-notes.md`
- Validated `real-decision-agent-dev` skill with `quick_validate.py`; result: valid.

## Current Direction

- Primary product path: server-hosted web app optimized for mobile browsers.
- Companion path: optional RikkaHub or Cherry Studio integration when remote MCP and markdown skill workflows fit.
- Next implementation step: create the backend skeleton and the first case/session/journal models.

## 2026-05-20 Implementation Slice 1

- Added FastAPI application skeleton.
- Added SQLite schema for:
  - decision cases
  - conversation messages
  - decision options
  - evidence items
  - journal entries
- Added repository layer for case-scoped persistence.
- Added deterministic decision engine with:
  - basic problem classification
  - expected value calculation
  - MCDA weighted scoring
  - anti-ruin risk gate
  - four action outputs
- Added server-side `smart-search` wrapper.
- Added API endpoints for cases, messages, options, evidence, evaluation, and journal entries.
- Added mobile-first web UI at `/`.
- Added tests for case/message persistence and anti-ruin evaluation.
- Added `.gitignore`.
- Ran `pytest -q`; result: 2 passed.
- Started local dev server at `http://127.0.0.1:8000`.
- Browser-smoked the app on desktop and mobile-sized viewport.

## 2026-05-20 Implementation Slice 2

- Fixed SQLite request failures caused by FastAPI threadpool access by opening connections with `check_same_thread=False` and WAL mode.
- Added `.env` loading without an extra dependency.
- Added configurable OpenAI-compatible LLM settings:
  - `LLM_BASE_URL`
  - `LLM_API_KEY`
  - `LLM_MODEL`
  - `LLM_TIMEOUT_SECONDS`
- Added `.env.example` and local `.env` template.
- Added LLM status endpoint: `GET /api/llm/config`.
- Added first LLM-backed decision-agent endpoint: `POST /api/cases/{case_id}/agent/respond`.
- Added mobile UI control for `Agent 分析`.
- Replaced the visible work-change demo wording with a neutral workflow-improvement example.
- Updated existing local SQLite sample data so the app no longer opens with the old work-change case.
- Ran `pytest -q`; result: 3 passed.

## 2026-05-20 Implementation Slice 3

- Reworked the main UI from form-driven panels into a chat/CLI-style decision terminal.
- Removed visible manual `证据搜索` and `快速评估` panels from the primary workflow; the backend capabilities remain available for agent/tool use.
- Added single-message continuation endpoint: `POST /api/cases/{case_id}/agent/message`.
- Updated the agent prompt so it extracts goals, options, constraints, risks, and missing evidence from natural language before asking focused follow-up questions.
- Added lightweight automatic evidence lookup when the current message appears to require external facts and no evidence has been collected yet.
- Added client-side Markdown rendering for assistant messages.
- Added a `新决策` flow where the user starts with one natural-language description instead of filling title/goal/question fields.
- Ran `pytest -q`; result: 4 passed.
- Restarted local dev server at `http://127.0.0.1:8000`.

## 2026-05-20 Implementation Slice 4

- Reworked the visual direction away from the CLI/terminal metaphor toward a ChatGPT-like web chat layout:
  - left conversation sidebar
  - centered message stream
  - bottom composer
  - light neutral theme
- Added static asset cache-busting query strings so updated CSS/JS are picked up more reliably.
- Improved assistant Markdown rendering for:
  - headings
  - unordered and ordered lists
  - blockquotes
  - horizontal rules
  - tables
  - inline bold, emphasis, links, and code
- Changed user messages to render as plain text while assistant messages render as Markdown.
- Verified Markdown conversion with a local Node VM sample.
- Ran `pytest -q`; result: 4 passed.

## 2026-05-20 Implementation Slice 5

- Added concise/default + expandable/detail response UX for assistant messages.
- Updated the system prompt so future model replies use:
  - `## 简洁结论`
  - `## 详细分析`
- Frontend now detects `## 详细分析` and renders the detailed part inside a native collapsible `<details>` block.
- Kept Markdown rendering inside both the visible summary and hidden detail body.
- Added cache-busting static versions `v=5`.
- Verified the generated assistant HTML includes `<details>` and preserves Markdown tables inside the detail body.
- Ran `pytest -q`; result: 4 passed.
- Restarted local dev server at `http://127.0.0.1:8000`.

## 2026-05-20 Implementation Slice 6

- Added OpenAI-compatible streaming chat support in `app/services/llm.py`.
- Added SSE endpoints:
  - `POST /api/cases/{case_id}/agent/respond/stream`
  - `POST /api/cases/{case_id}/agent/message/stream`
- Streaming assistant responses are persisted to SQLite after completion.
- Updated the frontend composer to use streaming endpoints by default.
- User messages now appear immediately; assistant messages progressively render as chunks arrive.
- Markdown rendering continues during streaming, including the concise/default + expandable/detail structure.
- Added a subtle streaming pulse on the assistant avatar.
- Added tests covering SSE output and persisted assistant messages.
- Added static asset cache-busting version `v=6`.
- Ran `pytest -q`; result: 5 passed.
- Ran `node --check app.js`; result: passed.
- Restarted local dev server at `http://127.0.0.1:8000`.

## 2026-05-20 Implementation Slice 7

- Updated streaming assistant rendering so the `详细分析` block is forced open while tokens are streaming.
- Kept historical assistant messages collapsed by default.
- After a streamed response finishes, the just-generated detail block remains open and can be manually collapsed.
- Added static asset cache-busting version `v=7`.
- Verified `renderAssistantMessage(..., { detailOpen: true })` outputs `<details open>`.
- Ran `node --check app.js`; result: passed.
- Ran `pytest -q`; result: 5 passed.

## 2026-05-20 Implementation Slice 8

- Added a decision-memory layer for multi-turn state tracking.
- Added `DecisionState` response model with:
  - summary
  - current action type
  - concerns
  - open questions
  - candidate options
  - next steps
  - evidence count
  - message count
- Added `GET /api/cases/{case_id}/state`.
- The agent now includes a `当前决策状态快照` block in its prompt context.
- Assistant replies now refresh the case summary after they are saved, including streaming replies after completion.
- Added deterministic extraction for:
  - `当前动作类型`
  - user concerns
  - candidate option lines
  - assistant follow-up questions
  - suggested next steps
- Added tests for state extraction and state persistence after streaming.
- Ran `pytest -q`; result: 6 passed.
- Ran Python compile check; result: passed.
- Restarted local dev server at `http://127.0.0.1:8000`.
- Smoke-tested `GET /api/cases/{case_id}/state` against local data.

## 2026-05-20 Implementation Slice 9

- Added deterministic decision brief layer on top of the rolling decision state.
- Added `DecisionBrief` and `PremortemItem` response models.
- Added `GET /api/cases/{case_id}/brief`.
- Decision brief includes:
  - recommended action
  - confidence level
  - reality checks
  - risk flags
  - information gaps
  - premortem items
  - stop conditions
  - next steps
- Added rule-based anti-ruin downgrades for legal, debt, freedom/control, and judgment risks.
- Added decision brief context into the agent prompt so the LLM sees the deterministic safety scaffold.
- Added tests for:
  - decision brief risk downgrade
  - small-experiment brief generation
  - agent prompt containing decision brief context
- Ran `pytest -q`; result: 8 passed.
- Ran Python compile check; result: passed.
- Restarted local dev server at `http://127.0.0.1:8000`.
- Smoke-tested `GET /api/cases/{case_id}/brief` against local data.

## 2026-05-20 Implementation Slice 10

- Added action-plan generation from the current decision brief.
- Added `DecisionActionPlan` response model with:
  - action
  - commitment level
  - timebox days
  - review date
  - success signals
  - failure signals
  - stop conditions
  - next steps
  - journal rationale
- Added `GET /api/cases/{case_id}/action-plan`.
- Added `POST /api/cases/{case_id}/journal/from-brief` to persist the current brief/action plan as a journal entry.
- Added tests for action plan generation and journal creation from the brief.
- Added filtering so action-plan next steps prefer concrete actions and fall back to deterministic defaults when extracted chat text is too generic.
- Ran `pytest -q`; result: 9 passed.
- Ran Python compile check; result: passed.
- Restarted local dev server at `http://127.0.0.1:8000`.
- Smoke-tested `GET /api/cases/{case_id}/action-plan` against local data.

## 2026-05-20 Implementation Slice 11

- Connected the backend decision-state stack to the frontend.
- Added a functional decision panel beside the chat stream showing:
  - current recommended action
  - summary
  - confidence
  - evidence count
  - review date
  - next steps
  - risk flags
  - stop conditions
  - information gaps
  - recent journal entries
- Added frontend calls for:
  - `GET /api/cases/{case_id}/state`
  - `GET /api/cases/{case_id}/brief`
  - `GET /api/cases/{case_id}/action-plan`
  - `GET /api/cases/{case_id}/journal`
- Added `记录当前计划` button wired to `POST /api/cases/{case_id}/journal/from-brief`.
- The decision panel refreshes after selecting a case and after streamed replies finish.
- Added static asset cache-busting version `v=8`.
- Ran `node --check app.js`; result: passed.
- Ran `pytest -q`; result: 9 passed.
- Restarted local dev server at `http://127.0.0.1:8000`.
- Smoke-tested state, brief, action-plan, and journal endpoints against local data.

## 2026-05-20 Implementation Slice 12

- Added journal outcome update support:
  - `PATCH /api/cases/{case_id}/journal/{journal_id}`
  - `JournalUpdate` request model
- Added deterministic review summaries:
  - overdue / due today / upcoming / completed / unscheduled status
  - review prompt by action type
  - simple learning summary from recorded outcomes
- Added review endpoints:
  - `GET /api/cases/{case_id}/reviews`
  - `GET /api/reviews/due`
- Updated the decision panel so journal entries can be reviewed in-place with an outcome note.
- Added due/overdue review status text to the action-plan panel.
- Added frontend cache-busting version `v=9`.
- Added tests for overdue review listing, outcome patching, completed review status, and learning summary.
- Ran `pytest -q`; result: 10 passed.
- Ran `node --check app.js`; result: passed.
- Ran Python compile check; result: passed.
- Restarted local dev server at `http://127.0.0.1:8000`.
- Smoke-tested:
  - `GET /api/health`
  - `GET /api/reviews/due`
  - `GET /api/cases/{case_id}/reviews`
  - `/` static page loading `app.js?v=9` and `styles.css?v=9`
- Browser plugin smoke test could not run because the local browser automation endpoint refused connection on `127.0.0.1:9224`; HTTP smoke tests passed.

## Current Boundary

- Functional local prototype now covers the planned pre-deployment workflow: chat, streaming, multi-case state, decision brief, action plan, journal creation, and review/outcome update.
- Stop here before the next stage requested by the user: remote deployment, phone access optimization, and authentication.

## 2026-05-20 Bugfix Pass 1

- Re-ran health checks:
  - `pytest -q`; result: 10 passed.
  - `node --check app.js`; result: passed.
  - `GET /api/health`; result: ok.
- Added a static DOM id consistency check for frontend script references; result: no missing ids.
- Found and fixed duplicate journal creation:
  - repeated `POST /api/cases/{case_id}/journal/from-brief` now returns the existing unreviewed plan when action and review date match.
  - added test coverage to assert repeated saves keep journal count at 1.
- Restarted local dev server at `http://127.0.0.1:8000`.
- Smoke-tested repeated journal save on local data; the first and second call returned the same journal id and did not increase count.

## 2026-05-20 UI Management Pass 1

- Added backend deletion support:
  - `DELETE /api/cases/{case_id}` removes a decision case and cascaded child records.
  - `DELETE /api/cases/{case_id}/journal/{journal_id}` removes one Journal entry.
- Added tests for case rename, case deletion, and Journal deletion.
- Updated the conversation sidebar:
  - each conversation row now has icon-only rename and delete controls.
  - controls use `title` and `aria-label` so hover shows `重命名` / `删除`.
  - mobile keeps the icon controls visible because hover is unavailable.
- Updated the Journal panel:
  - each Journal card now has an icon-only delete button with hover title `删除`.
- Updated static cache version to `v=10`.
- Ran `pytest -q`; result: 11 passed.
- Ran `node --check app.js`; result: passed.
- Ran frontend DOM id consistency check; result: no missing ids.
- Restarted local server on `http://127.0.0.1:8000`.
- Smoke-tested static asset version and DELETE case endpoint.
- Browser automation still could not connect to `127.0.0.1:9224`; HTTP and static checks passed.

## 2026-05-20 Decision Panel Clarity Pass 1

- Fixed decision summary extraction so greetings, model questions, and `当前动作类型` lines are not treated as the user's goal.
- Stripped `Goal:` / `Question:` prefixes from initial case messages before panel summarization.
- Changed panel summary wording from raw `目标：...` to `正在判断：...；当前建议：...`.
- Converted action labels in the summary to Chinese (`小试`, `观察`, etc.) instead of internal enum values.
- Filtered question-like assistant lines out of action-plan next steps so questions stay under `需要你补充`.
- Updated right panel copy:
  - `行动计划` is now `现在先做`.
  - `待澄清` is now `需要你补充`.
  - added short hints explaining what can be answered now and what is for later review.
  - confidence values now render in Chinese.
- Updated static cache version to `v=11`.
- Added regression test for the `你好 -> 你是什么模型 -> 我想做副业赚钱` path.
- Ran `pytest -q`; result: 12 passed.
- Ran `node --check app.js`; result: passed.
- Smoke-tested local state/brief endpoints; summary now reads like `正在判断：我想做副业赚钱...；当前建议：小试`.

## 2026-05-20 Repository And Automation Setup

- Initialized `E:\AIwork\real` as a Git repository.
- Added `README.md` with local run and test instructions.
- Expanded `.gitignore` so `.env`, SQLite database files, WAL/SHM files, logs, caches, and bytecode are not committed.
- Verified no obvious secrets were staged.
- Ran checks before initial commit:
  - `pytest -q`; result: 12 passed.
  - `node --check app.js`; result: passed.
- Created initial commit: `Initial REAL decision agent prototype`.
- Added GitHub remote: `https://github.com/Kilig1058674225/R.E.A.L.git`.
- Pushed `main` to GitHub.
- Ran `smart-search doctor --format json`; result: ok, search/docs/fetch capabilities available.
- Created active Codex cron automation `REAL Autonomous Iteration`:
  - schedule: every 6 hours
  - workspace: `E:\AIwork\real`
  - behavior: read project docs, research comparable products with smart-search when useful, implement one high-impact iteration, run checks, update docs, commit, and push when tests pass.
