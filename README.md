# Text2SQL AI

Enterprise-grade Text-to-SQL platform built with FastAPI, React, PostgreSQL, SQLAlchemy, Groq, FAISS, and Sentence Transformers.

The project is being delivered incrementally. See [the delivery roadmap](docs/ROADMAP.md) and [the architecture blueprint](docs/architecture/ARCHITECTURE.md).

Current status: Phase 10 production hardening complete. Deployment and security runbooks are under `docs/operations/`.

## Backend verification

From `backend/` with Python 3.11 and project dependencies installed:

```shell
python -m unittest discover -s tests -v
```

Database configuration is environment-driven; copy `backend/.env.example` and use a
least-privilege PostgreSQL role for every target data source.
