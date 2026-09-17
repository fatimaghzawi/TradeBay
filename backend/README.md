# TradeBay Backend

FastAPI modular monolith. Business logic lives in domain services, not route handlers.

## Local run

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -e ".[dev]"
copy ..\.env.example ..\.env  # fill secrets
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs

## Quality

```bash
ruff check .
ruff format .
mypy app
pytest
```
