# Customer Support Chatbot (Full Stack)

This project is a lightweight customer-support assistant built with a React frontend, a Flask backend, and a Postgres datastore. It supports login-gated chat sessions, tracks session activity, and can generate SQL responses using LangGraph and Gemini-based RAG logic.

## What it does
- **Frontend (Vite + React)**: A light, responsive chat UI with login gating. Once logged in, messages are sent to the backend and responses are streamed back. Session cookies are handled automatically.
- **Backend (Flask + LangGraph)**: Provides `/api/login`, `/api/chat`, `/api/logout`, and session-management endpoints. It validates sessions, tracks conversation counts, and can answer from policy docs or the `supportdb` database via RAG/LLM.
- **Database (Postgres)**: Seeds customer, order, product, and inventory data. Includes a read-only role and a `user_sessions` table for session tracking.
- **Schema summary**: `backend/support_schema.txt` is generated via `backend/generate_schema_summary.py` to help LLMs craft safe SQL.

## Prerequisites
- Node 18+ for the frontend.
- Python 3.11+ and virtualenv for the backend.
- Postgres (Dockerfile provided under `backend/db/`).
- Access to a Gemini API key (set `GOOGLE_API_KEY`) for LLM features.

## Setup

### Backend
1. Create and activate a virtualenv:
   ```bash
   python -m venv datadog-venv
   source datadog-venv/bin/activate
   ```
2. Install deps:
   ```bash
   pip install -r backend/requirements.txt
   ```
3. Set environment variables:
   - `GOOGLE_API_KEY` (required for LLM)
   - DB connection (defaults are usually fine with the provided Dockerfile):
     - `DB_HOST=localhost`
     - `DB_PORT=5431`
     - `DB_NAME=supportdb`
     - `DB_USER=support_ro`
     - `DB_PASSWORD=support_ro`
4. Run Flask:
   ```bash
   export FLASK_APP=backend.main
   flask run --debug
   ```

### Database (Docker)
In `backend/db/`:
```bash
docker build -t support-db .
docker run --name support-db -p 5431:5432 support-db
```
The init script creates tables, seeds sample data, and grants `support_ro` read access plus write access on `user_sessions`.

### Frontend
In `frontend/`:
```bash
npm install
npm run dev
```
Set `VITE_API_URL` if your backend isn’t on the default `http://localhost:5000`.

## Testing the flow
- Automated test scripts:
  - `backend/test.py` runs multiple chat requests with proper session cookies.
  - `backend/single_req_test.py` runs a single login/chat/logout cycle.
  - Both rely on the session endpoints and assume the backend at `http://localhost:5000`.
- Manual:
  1) Start DB + backend + frontend.
  2) Open the frontend, enter an email to log in.
  3) Send messages; if idle for 5+ minutes or exceeding 3 active sessions, you’ll need to log in again.

## Helpful utilities
- `backend/generate_schema_summary.py`: produces `backend/support_schema.txt` describing all tables/columns/types for LLM prompting.
- `backend/db/init.sql`: full schema + seed data + role grants.

## Mutual TLS (mTLS)
- `backend/run.sh` will generate a self-signed CA and server/client certs into `backend/certs/` if missing.
- Flask serves HTTPS with client cert verification using `SERVER_CERT`, `SERVER_KEY`, and `CA_CERT` (exported in `run.sh`).
- Quick test:
  ```bash
  cd backend
  ./run.sh &
  curl -k --cert certs/client.crt --key certs/client.key --cacert certs/ca.crt https://localhost:5000/health
  ```
- Clients (frontend/tests) must supply the client cert/key and trust `ca.crt` when calling the API.

## Notes
- Session rules: max 3 active sessions per user; sessions expire after 5 minutes. `/api/sessions` (DELETE) will clear all sessions for a given user; `/api/logout` deletes the current session.
- CORS is set to allow cookies; frontend uses `credentials: 'include'`.
- The LLM graph uses Gemini + LangGraph. Set `GOOGLE_API_KEY` before running `/api/chat`.


