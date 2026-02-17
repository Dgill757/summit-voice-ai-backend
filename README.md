# Summit Voice AI Backend

FastAPI backend for 26-agent orchestration, analytics, and AI Builder.

## Run

```bash
python -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Key Endpoints
- `/api/v1/health`
- `/api/v1/agents`
- `/api/v1/builder/generate`
- `/api/v1/builder/deploy`
- `/api/v1/dashboard`

## Scheduler
Autonomous scheduler reads `agent_settings` and executes due agents.
