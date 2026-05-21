# REAL Decision Agent Development Plan

## Goal

Build a mobile-first decision-support agent that helps a hesitant user turn vague uncertainty into a concrete action choice.

The product should support:

- multi-turn decision conversations
- evidence-driven web research
- risk-aware recommendations
- long-lived decision history
- mobile use through a browser-first UI

## Product Shape

### Primary path

Deploy a server-hosted web app that is comfortable on mobile browsers.

Why this is the primary path:

- works immediately on phone without local app packaging
- easier to manage long-lived sessions, journals, and evidence
- easier to run deterministic scoring and search on the server
- easier to expose remote MCP later if needed

### Companion path

Support RikkaHub or Cherry Studio as optional companion clients.

Use them for:

- lightweight chat access
- markdown-based skill consumption
- remote MCP connection when convenient

Do not depend on mobile clients for core orchestration until their exact tool and memory behavior is proven for this project.

## Core Decision Workflow

1. Intake the problem.
2. Classify the problem type.
3. Detect whether external evidence is needed.
4. Search or fetch evidence when needed.
5. Build options and criteria.
6. Score EV / MCDA.
7. Enforce anti-ruin gates.
8. Run premortem.
9. Decide action type.
10. Save a decision journal entry.
11. Schedule a review if the decision is reversible or experimental.

## Decision Output Types

- Reject
- Observe
- Small experiment
- Stage-gated increase

## System Modules

### 1. Session and conversation manager

Responsibilities:

- create decision cases
- keep multiple cases separate
- maintain rolling summaries
- preserve last active case state
- support returning to a decision later

### 1a. LLM decision agent layer

Responsibilities:

- read provider settings from `.env`
- call an OpenAI-compatible chat completion endpoint
- use the case, recent messages, and evidence as scoped context
- produce structured REAL-style guidance instead of generic Q&A
- fail clearly when model credentials are missing

### 2. Evidence and search layer

Responsibilities:

- trigger `smart-search-cli`
- save commands and source URLs
- fetch pages before source-backed claims
- record evidence confidence and date
- plan evidence queries from the current case, open questions, and information gaps
- distinguish candidate search results from fetched, citeable evidence
- expose evidence status and source links in the decision panel

### 3. Decision engine

Responsibilities:

- transform raw inputs into structured criteria
- calculate weighted scores
- calculate expected value where applicable
- compare options
- generate sensitivity notes

### 4. Risk gate

Responsibilities:

- detect possible ruin conditions
- require a stop or downgrade when health, liberty, finance, trust, or legal safety are threatened
- prevent summary score from overriding hard limits

### 5. Premortem generator

Responsibilities:

- ask what failed
- identify early warning signs
- define stop-loss conditions
- generate small safe probes

### 5a. Decision brief

Responsibilities:

- produce a structured status brief from the rolling case state
- expose recommended action, confidence, risk flags, information gaps, premortem, stop conditions, and next steps
- provide a deterministic safety scaffold for the LLM
- preserve anti-ruin downgrades even when the conversational answer is optimistic

### 6. Journal and memory

Responsibilities:

- store each decision case
- store evidence and rationale
- store outcome after follow-up
- learn your recurring hesitation patterns

### 7. Action plan and review loop

Responsibilities:

- convert the current decision brief into a timeboxed action plan
- define success signals, failure signals, stop conditions, and review date
- persist the accepted plan as a journal entry
- support later outcome review and learning
- list due reviews and let the user record outcomes from the web UI
- feed completed outcomes back into later decision calibration

## Data Model

### DecisionCase

- id
- title
- status
- created_at
- updated_at
- user_goal
- current_question
- classification
- urgency
- stakes
- summary

### DecisionOption

- id
- case_id
- label
- description
- expected_value
- mcda_score
- risk_notes
- reversibility
- evidence_links

### EvidenceItem

- id
- case_id
- query
- url
- title
- source_type
- fetched_text
- confidence
- created_at

### DecisionJournalEntry

- id
- case_id
- final_action
- rationale
- stop_conditions
- follow_up_date
- outcome

## Deployment Plan

### Phase 1

- FastAPI backend
- SQLite storage
- simple mobile-friendly web UI
- manual case creation
- manual evidence search button
- `.env`-configured LLM provider
- first agent response endpoint
- structured final recommendation

### Phase 2

- multi-dialogue state
- automatic search trigger
- case summaries
- deterministic decision brief
- action plan from decision brief
- journal creation from decision brief
- premortem and review reminders
- outcome review and journal update flow
- bug/feedback workflow

### Phase 3

- user preference profile
- personal weighting defaults
- outcome learning
- optional remote MCP endpoint
- companion client integration
- remote deployment
- phone access optimization
- authentication

## Frontend Notes

- use a dense, utilitarian interface
- keep decisions scannable
- avoid decorative landing-page treatment
- make the current case obvious on the first screen
- show evidence, risk, and recommended action together
- primary input should be a single natural-language composer
- do not require users to fill criteria, probabilities, or search queries before the agent has guided them
- keep manual search/scoring controls out of the primary path; expose them later only as advanced inspection tools
- render assistant output as Markdown so extracted structure and recommendations are readable

## Engineering Principles

- deterministic code for scoring and state
- LLM for interpretation and explanation
- search when facts matter
- never all-in when downside threatens the base
- keep every decision reversible when possible
