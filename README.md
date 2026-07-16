#//backend commands

#cd backend
# $env:DEMO_DATABASE_URL="postgresql+psycopg://text2sql:text2sql@localhost:5432/text2sql"
# .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000


#granting databse commans
# GRANT CONNECT ON DATABASE text2sql TO text2sql;
# GRANT USAGE ON SCHEMA public TO text2sql;

# GRANT SELECT ON ALL TABLES IN SCHEMA public TO text2sql;
# GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO text2sql;

# ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
# GRANT SELECT ON TABLES TO text2sql;

# ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
# GRANT USAGE, SELECT ON SEQUENCES TO text2sql;







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
