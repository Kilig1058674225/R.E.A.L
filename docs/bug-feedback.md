# Bug / Feedback Log

## Open Questions

- Exact mobile client parity for skill loading, MCP orchestration, and multi-turn state on RikkaHub and Cherry Studio mobile still needs validation before making either client a first-class path.
- Final model/provider choice for the backend is not locked yet.
- Need to confirm the best storage strategy for long-lived session summaries if the project grows beyond SQLite.
- Final production auth shape is not locked; `REAL_ACCESS_TOKEN` is a simple deployment guard, not user accounts or multi-user authorization.
- This automation run could not execute full `pytest -q` because the sandboxed shell lacks a working Python/Pytest environment with project dependencies.

## Known Risks

- A pure chat experience will drift back toward generic Q&A unless the workflow stays explicit.
- If search is not gated carefully, the agent may over-search and slow down simple decisions.
- If anti-ruin rules are not coded as hard gates, the scoring layer can give false confidence.
- If conversation state is not case-scoped, multiple decisions will bleed into each other.
- The first LLM endpoint depends on an OpenAI-compatible `/chat/completions` provider; provider-specific quirks may require adapters later.
- The first decision-state extractor is deterministic and keyword-based; it will be useful for scaffolding but may miss nuanced options or concerns until a stronger extraction pass is added.
- The first decision brief is rule-based; it is intentionally conservative around anti-ruin risks but will need calibration as real cases accumulate.
- The first outcome-learning pass uses simple keyword heuristics; real calibration later needs richer extraction and user-specific preference memory.

## Feedback Ideas

- Make the current decision case visible at all times.
- Keep one-tap access to evidence and follow-up review.
- Prefer short, structured prompts over long conversational back-and-forth.
- Show the final recommendation as one of four actions, not as a vague paragraph.
- Primary interaction should feel like a CLI/chat box, not a form that asks the user to pre-structure the decision.
- Manual probability, risk, and search fields should be agent-internal or advanced-only, because the user may not know those values upfront.
- Assistant messages should render Markdown for readability.
- The primary visual style should be closer to ChatGPT web than to a CLI/terminal.
- Assistant replies should default to a concise conclusion, with detailed reasoning available through expand/collapse.
- Assistant replies should stream progressively rather than waiting for the whole response.

## Resolved

- The project should start as a server-hosted web app.
- The skill and docs live in `E:\AIwork\real` so the project can carry its own development workflow.
- First implementation slice now has a running FastAPI app, SQLite persistence, mobile web shell, and basic anti-ruin scoring.
- Fixed the `Request failed: 500` issue caused by SQLite connection thread ownership.
- Replaced the visible `要不要换工作` sample with a neutral workflow-improvement example for safer use in the workplace.
- Replaced the main form-heavy UI with a single-input decision terminal and Markdown-rendered assistant responses.
- Replaced the terminal-like UI with a ChatGPT-like layout and fixed Markdown rendering for richer response structures.
- Added collapsed detailed analysis for assistant messages so the default view stays concise.
- Added streaming response support through SSE and frontend incremental rendering.
- During streaming, the detailed analysis block now stays open so detailed content is visible as it arrives.
- Added a case-scoped decision state endpoint and rolling summary refresh so multi-turn context is no longer only implicit in raw chat messages.
- Added a decision brief endpoint with premortem, information gaps, stop conditions, and deterministic anti-ruin downgrades.
- Added action-plan generation and journal creation from the current decision brief, closing the first version of the decide-review loop.
- Connected state, brief, action plan, and journal data to a first frontend decision panel.
- Added journal outcome update, case review summaries, due review listing, and in-panel result recording.
- Fixed duplicate journal creation when `记录当前计划` / `journal/from-brief` is triggered repeatedly for the same active plan.
- Added icon-only rename/delete controls for conversation records and icon-only delete controls for Journal entries.
- Fixed current-suggestion summary incorrectly treating greetings, model questions, and raw first messages as the decision goal.
- Clarified the right decision panel labels so action steps, questions to answer, and review journal timing are easier to distinguish.
- Added optional `REAL_ACCESS_TOKEN` API protection and frontend token prompting for phone/non-local deployment readiness.

## New Implementation Notes

- The first classifier missed "换工作/跳槽"; this was caught by tests and fixed by adding career-change terms.
- FastAPI startup was moved to lifespan to avoid deprecated startup-event usage.
- Browser smoke found the mobile layout usable at a 390px-wide viewport.
- LLM configuration is now read from `.env`; the local `.env` template intentionally has an empty API key until the user fills it in.
- Manual evidence search and quick evaluation endpoints still exist, but are no longer exposed as primary UI controls.
