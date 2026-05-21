# R.E.A.L

R.E.A.L is a local-first decision-support agent for turning vague hesitation into safer, staged decisions.

The current prototype includes:

- FastAPI backend with SQLite persistence
- OpenAI-compatible LLM configuration through `.env`
- ChatGPT-like web interface
- streaming assistant responses
- case-scoped decision state
- deterministic decision brief, risk gates, action plans, and review journals
- optional `smart-search` integration for evidence gathering

## Local Run

```powershell
cd E:\AIwork\real
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

Copy `.env.example` to `.env` and fill in your OpenAI-compatible provider settings before using LLM-backed chat.

For phone access or any non-local deployment, set `REAL_ACCESS_TOKEN` in `.env`. When it is set, `/api/*` endpoints require `Authorization: Bearer <token>` except health, auth status, and LLM config. The web UI will prompt once and store the token in browser local storage.

## Tests

```powershell
pytest -q
node --check app\static\app.js
```

## Notes

Do not commit `.env` or local SQLite data. They are intentionally ignored.
