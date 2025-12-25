# About This Project

## Inspiration
- Build a customer-support assistant that is safe, observable, and grounded in real data.
- Demonstrate full-stack LLM patterns: retrieval, tool use, and guardrails with practical monitoring.

## What it does
- Provides a login-gated chat UI where users can ask for help, track orders, or get product info.
- Uses RAG and tool calls to query policy docs and a Postgres-backed catalog/orders DB.
- Enforces session limits/expiry and records conversation metrics for observability.
- Surfaces health/safety signals in Datadog (prompt injection, sensitive data, cost, confusion, relevancy).

## How we built it
- Frontend: Vite + React chat with soft styling, quick actions, and session cookies.
- Backend: Flask API with session tables, LangGraph + Gemini agent, RAG pipeline, and tracing.
- Database: Postgres seeded for customers/orders/inventory; role-based access and session tracking.
- Tools: LangChain tools for orders/status/updates/product lookup; fuzzy name-to-SKU resolution; schema exporter for LLM context.
- Monitoring: Datadog monitors (JSON in `monitoring/monitors/`), dashboards (`monitoring/dashboard.json`), and docs (`monitoring/metrics.md`).

## Challenges we ran into
- Session integrity: short TTL, 3-session cap, cookie/CORS handling, and cleanup in tests.
- LLM correctness: avoiding wrong tools/arguments, handling ambiguous product names, keeping RAG relevant.
- Safety and cost: detecting sensitive data/prompt injection, capping session length, and cost alerts.
- Observability alignment: ensuring metrics/monitors matched real signals (latency, confusion, relevancy, tokens).

## Accomplishments that we're proud of
- End-to-end LLM stack with guardrails, RAG, and tool use tied to real data.
- Robust session handling with enforcement and metrics.
- Fuzzy product resolution that tolerates user phrasing while preventing wrong SKU choices.
- Comprehensive monitoring coverage with clear documentation.

## What we learned
- Practical LangGraph/LangChain patterns for tool orchestration and RAG.
- Designing session policies for UX and safety (expiry, caps, validation).
- Importance of observability in LLM apps: detecting prompt injection, sensitive data, cost spikes, and confusion.
- Handling messy user input with fuzzy matching and validation loops.

## What's next for First Project
- Add evals and automated regression checks for tool calls and RAG relevance.
- Expand product/order domain coverage and add human handoff.
- Introduce streaming responses and retry/fallback strategies for LLM calls.
- Harden LLM security and rate limits for production use.

