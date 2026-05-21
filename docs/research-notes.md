# Research Notes

## 2026-05-21 Evidence Tool Layer

Command:

```powershell
smart-search search "AI agent evidence retrieval source citation fetch before claim design patterns RAG fact checking" --validation balanced --extra-sources 2 --format json --output C:\tmp\smart-search-evidence\real-decision-agent\evidence-layer-patterns.json
```

Relevant product/architecture takeaway:

- The evidence layer should follow a retrieve/fetch-before-claim pattern.
- Search results are discovery candidates, not final proof.
- Fetched page text with URL/title metadata should be stored separately as citeable evidence.
- Agent prompts should receive fetched evidence summaries and abstain or ask for more evidence when sources are insufficient.
- The implementation should keep retrieval, verification/fetching, and answer synthesis as separate modules.

## Sources Used

- [OpenAI Agents SDK](https://platform.openai.com/docs/guides/agents)
- [AWS LLM workflows](https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-patterns/llm-workflows.html)
- [Microsoft Agent Framework: From LLMs to Agents](https://learn.microsoft.com/en-us/agent-framework/journey/from-llms-to-agents)
- [OpenSearch plan-execute-reflect agents](https://docs.opensearch.org/3.4/ml-commons-plugin/agents-tools/agents/plan-execute-reflect/)
- [PMI decision analysis article](https://www.pmi.org/learning/library/decision-analysis-projects-utlity-multi-criteria-10379)
- [Government Analysis Function MCDA guide](https://analysisfunction.civilservice.gov.uk/policy-store/an-introductory-guide-to-mcda/)
- [NIST SP 800-30 Rev. 1 PDF](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=912091)
- [HBR premortem](https://hbr.org/2007/09/performing-a-project-premortem)
- [Stanford Encyclopedia of Philosophy: Bayesian Epistemology](https://plato.stanford.edu/entries/epistemology-bayesian/)
- [HBR Cynefin framework](https://www.hbr.org/2007/11/a-leaders-framework-for-decision-making)
- [RikkaHub MCP docs](https://docs.rikka-ai.com/docs/assistants/mcp)
- [RikkaHub repository](https://github.com/rikkahub/rikkahub)
- [Cherry Studio repository](https://github.com/CherryHQ/cherry-studio)

## Key Findings

### Decision theory

- Expected utility and multi-criteria decision analysis are appropriate foundations for a structured decision agent.
- Risk aversion matters when downside can dominate the outcome.
- Sensitivity analysis is important because the agent will often work with incomplete or subjective estimates.

### Risk and bias

- Premortem is useful for surfacing failure modes before commitment.
- Bayesian updating is a good mental model for evidence-driven revisions.
- Cynefin supports classifying the problem before choosing a decision method.

### Agent architecture

- A raw LLM is not enough for this project.
- The system needs tools, memory, state, and guardrails.
- The server should own orchestration so mobile clients stay lightweight.

### Mobile path

- RikkaHub supports remote MCP server connections through SSE and StreamableHttp.
- RikkaHub has strong markdown rendering and assistant-level MCP configuration.
- Cherry Studio is primarily desktop-first; mobile support exists but should not be assumed to have full parity.

## Implications

- Use the web app as the canonical workflow.
- Treat mobile clients as adapters, not as the system of record.
- Keep search, scoring, and state in the server.
- Keep Markdown skill files small and task-oriented.
