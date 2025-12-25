# Metrics Monitored (and Explained)

This system uses several key metrics for LLM application observability, as captured in the monitors (see `monitoring/monitors/`) and referenced by dashboards.

Below are the main metrics currently tracked:

---

## 1. Sensitive Data Detected

- **Metric Source:** `Sensitive_data.json`
- **Datadog Query:**  
  ```
  @event_type:span @ml_app:vertex-chat-bot sensitive_data:*
  ```
- **What it measures:**  
  Monitors the number of times sensitive data (such as PII, passwords, account numbers) is detected in LLM outputs or traces within a 5-minute window.
- **Why it's important:**  
  Tracking for leaks or attempted exfiltration of confidential or regulated information is essential for compliance and security.
- **Thresholds:**  
  - Critical: >50 occurrences in 5 minutes  
  - Warning: >10 occurrences in 5 minutes

---

## 2. Prompt Injection Detected

- **Metric Source:** `prompt_injection.json`
- **Datadog Query:**  
  ```
  @event_type:span @ml_app:vertex-chat-bot @evaluations.prompt_injection:"prompt injection"
  ```
- **What it measures:**  
  Counts occurrences where the system has determined a prompt injection attack (where malicious user input modifies an LLM's intended behavior).
- **Why it's important:**  
  Early detection of prompt injection can prevent undesired or insecure LLM outputs, and supports safer prompt engineering.
- **Thresholds:**  
  - Critical: >10 in last 5 minutes  
  - Warning: >5 in last 5 minutes

---

## 3. Tool Selection Incorrectness

- **Metric Source:** `Tool_Selection.json`
- **Datadog Query:**  
  ```
  @event_type:span @ml_app:vertex-chat-bot @evaluations.tool_selection:"tool selection incorrect"
  ```
- **What it measures:**  
  Counts cases where the LLM selects the wrong tool for a customer support intent (e.g., calling the wrong API, using an inappropriate function).
- **Why it's important:**  
  Ensures automation and agentic actions are correct and prevent chat failures due to mis-invocations.
- **Thresholds:**  
  - Critical: >10 in last 5 minutes  
  - Warning: >5 in last 5 minutes

---

## 4. Tool Argument Incorrectness

- **Metric Source:** `Tool_Argument_Correctness.json`
- **Datadog Query:**  
  ```
  @event_type:span @ml_app:vertex-chat-bot @evaluations.tool_argument_correctness:"tool arguments incorrect"
  ```
- **What it measures:**  
  Captures occasions where the arguments passed to tools (e.g., function-call parameters) by the LLM are detected as incorrect (wrong types, missing required values, etc).
- **Why it's important:**  
  Reduces user-facing errors, and is essential for debugging prompt/model issues that lead to “bad API calls.”
- **Thresholds:**  
  - Critical: >10 in last 5 minutes  
  - Warning: >5 in last 5 minutes

---

## 5. Answer Relevancy

- **Metric Source:** `Answer_Relevancy.json`
- **Datadog Query:**  
  ```
  trace-analytics("@answer_relevant:yes").index("trace-search", "djm-search").rollup("count").last("5m") < 50
  ```
- **What it measures:**  
  Counts traces where answers are marked relevant in the last 5 minutes.
- **Why it's important:**  
  A drop implies degraded answer quality or retrieval issues.
- **Thresholds:**  
  - Critical: < 50 in last 5 minutes  
  - Warning: < 75 in last 5 minutes

---

## 5. LLM Cost

- **Metric Source:** `LLM_cost.json`
- **Datadog Query:**  
  ```
  llm-observability("@event_type:span").rollup("sum", "@metrics.estimated_total_cost").last("5m") > 5000000000
  ```
- **What it measures:**  
  Sum of estimated LLM usage cost over the last 5 minutes.
- **Why it's important:**  
  Flags runaway usage, abuse, or unexpected traffic spikes that drive spend.
- **Thresholds:**  
  - Critical: > 5,000,000,000 in 5 minutes  
  - Warning: > 2,500,000,000 in 5 minutes

---

## 6. Session Length

- **Metric Source:** `session_length.json`
- **Datadog Query:**  
  ```
  avg(last_5m):avg:chatbot.session.chat_length{*} > 15
  ```
- **What it measures:**  
  Average user messages per session.
- **Why it's important:**  
  Longer sessions can indicate friction, looping, or unhelpful responses.
- **Thresholds:**  
  - Critical: > 15  
  - Warning: > 10

---

## 7. Confusion Score

- **Metric Source:** `confusion_score.json`
- **Datadog Query:**  
  ```
  avg(last_5m):avg:trace.background.confusion_score{*} > 0.8
  ```
- **What it measures:**  
  Average confusion score inferred from conversations.
- **Why it's important:**  
  Rising confusion signals degraded understanding or UX and warrants investigation.
- **Thresholds:**  
  - Critical: > 0.8  
  - Warning: > 0.6

---

## Cross-metric notes

- **Window:** All metrics above use a rolling 5-minute time window and alert if the count exceeds thresholds.
- **Use in dashboards:**  
  These metrics are typically visualized as time-series, count-over-time widgets in a Datadog dashboard to support ongoing monitoring and post-incident analysis.

---

**Summary**:  
The system tracks metrics for sensitive data leaks, prompt injection, incorrect tool selection/arguments, answer relevancy, LLM cost spikes, session length, and confusion score. Each monitor fires when an abnormal frequency or value is detected, helping teams respond quickly to security, reliability, cost, or UX degradations in the LLM-powered chatbot.

---

# Dashboard Metrics (from `monitoring/dashboard.json`)

The “GenAI Support Bot: Health & Safety” dashboard visualizes:

## Trace duration
- **Query:** `avg:ml_obs.trace.duration{service:vertex-chat-bot}`
- **What it measures:** Avg span duration for the chat service.
- **Why it matters:** Detects latency regressions impacting UX.

## Sensitive data detection
- **Query:** LLM observability count with `sensitive_data:*`
- **What it measures:** Current volume of spans flagged for sensitive data.
- **Why it matters:** Signals potential data leakage.

## Sentiment
- **Query:** Spans grouped by `@user.emotion`
- **What it measures:** Distribution of detected emotions across sessions.
- **Why it matters:** Gauges overall user experience tone.

## Input vs output tokens
- **Queries:** `ml_obs.span.llm.input.tokens` vs `ml_obs.span.llm.output.tokens` by `model_name`
- **What it measures:** Prompt vs completion token volumes.
- **Why it matters:** Tracks cost/performance balance and prompt bloat.

## RAG vs input tokens
- **Queries:** `@rag.context_size` (spans) vs prompt tokens
- **What it measures:** Retrieved context size relative to prompt size.
- **Why it matters:** Finds over-fetching or under-fetching in retrieval.

## Confusion score (query value)
- **Query:** Avg `@user.confusion_score`
- **What it measures:** Current confusion level.
- **Why it matters:** Rising confusion suggests degraded understanding.

## User messages per session
- **Query:** Avg `chatbot.session.chat_length`
- **What it measures:** Messages per session.
- **Why it matters:** Longer sessions can mean friction or looping.

## Was RAG Relevant
- **Query:** Counts by `@rag_relevant`
- **What it measures:** Relevance flags from retrieval.
- **Why it matters:** Validates RAG quality.

## Is a Query
- **Query:** Counts by `@critic_query_classification`
- **What it measures:** Classification of user input (question vs other).
- **Why it matters:** Monitors routing/intent detection quality.

## Answer relevancy
- **Query:** Ratio of `@answer_relevant:yes` over total answers
- **What it measures:** Share of answers marked relevant.
- **Why it matters:** Direct signal of response quality.

## Queries by RAG type
- **Query:** Counts by `@rag_type`
- **What it measures:** Distribution of RAG routing (policy, database, etc.).
- **Why it matters:** Observes routing trends/load.

## Confusion score by category
- **Query:** Avg `@user.confusion_score` grouped by `@user.topic`
- **What it measures:** Confusion per topic/category.
- **Why it matters:** Pinpoints content areas causing confusion.

## Request volume by topic
- **Query:** Counts by `@user.topic`
- **What it measures:** Volume distribution across topics.
- **Why it matters:** Shows demand hotspots and helps prioritize content fixes.



