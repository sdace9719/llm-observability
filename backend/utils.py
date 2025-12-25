from datetime import datetime, timedelta, timezone
import json
import os
from typing import Optional
import uuid
import psycopg
from transformers import pipeline
from datadog import statsd

from db_utils import get_db_conn

# 1. Load the Emotion Pipeline
# This model returns all 28 emotions. We will filter for "confusion".


SESSION_MAX_AGE_SECONDS = int(os.getenv('SESSION_MAX_AGE_SECONDS', '300'))

def render_graph_image(app):
    png_data = app.get_graph().draw_mermaid_png()
    with open("graph_visualization.png", "wb") as f:
        f.write(png_data)


def remove_expired_sessions(cur, user_identifier: Optional[str] = None) -> None:
    global SESSION_MAX_AGE_SECONDS
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=SESSION_MAX_AGE_SECONDS)
    if user_identifier:
        res = cur.execute("SELECT session_id, session_count FROM user_sessions WHERE user_identifier = %s AND created_at < %s;", (user_identifier, cutoff))
        for session_id, session_count in res:
            statsd.distribution(
                "chatbot.session.chat_length",
                session_count,
                tags=[
                    "session_id:{}".format(session_id)
                ]
            )
        cur.execute(
            "DELETE FROM user_sessions WHERE user_identifier = %s AND created_at < %s;",
            (user_identifier, cutoff),
        )
    else:
        res = cur.execute("SELECT session_id, session_count FROM user_sessions WHERE created_at < %s;", (cutoff,))
        for session_id, session_count in res:
            statsd.distribution(
                "chatbot.session.chat_length",
                session_count,
                tags=[
                    "session_id:{}".format(session_id)
                ]
            )
        cur.execute("DELETE FROM user_sessions WHERE created_at < %s;", (cutoff,))


def create_session(user_identifier: str) -> str:
  session_id = uuid.uuid4()
  with get_db_conn() as conn, conn.cursor() as cur:
    remove_expired_sessions(cur, user_identifier)
    cur.execute(
        "SELECT COUNT(*) FROM user_sessions WHERE user_identifier = %s;",
        (user_identifier,),
    )
    active_count = cur.fetchone()[0] or 0
    if active_count >= 3:
      raise ValueError("Maximum of 3 active sessions reached. Please close an existing session.")
    cur.execute(
        """
        INSERT INTO user_sessions (session_id, user_identifier)
        VALUES (%s, %s)
        ON CONFLICT (session_id) DO NOTHING;
        """,
        (session_id, user_identifier),
    )
    conn.commit()
  return str(session_id)


def validate_session(session_id: str) -> bool:
  if not session_id:
    return False
  #ensure_session_table_exists()
  with get_db_conn() as conn, conn.cursor() as cur:
    remove_expired_sessions(cur)
    cur.execute(
        "SELECT created_at FROM user_sessions WHERE session_id = %s LIMIT 1;",
        (session_id,),
    )
    row = cur.fetchone()
    if not row:
      conn.commit()
      return False
    created_at = row[0]
    if created_at < datetime.now(timezone.utc) - timedelta(seconds=SESSION_MAX_AGE_SECONDS):
      cur.execute("DELETE FROM user_sessions WHERE session_id = %s;", (session_id,))
      conn.commit()
      return False
    cur.execute(
        "UPDATE user_sessions SET last_seen = NOW() WHERE session_id = %s;",
        (session_id,),
    )
    conn.commit()
    return True


def increment_session_count(session_id: str) -> None:
  if not session_id:
    return
  with get_db_conn() as conn, conn.cursor() as cur:
    cur.execute(
        """
        UPDATE user_sessions
        SET conversation_count = conversation_count + 1
        WHERE session_id = %s;
        """,
        (session_id,),
    )
    conn.commit()

def get_cost(input_tokens: int, output_tokens: int, model_name: str) -> float:
  with open("cost-per-mil.json", "r") as f:
    cost_per_mil = json.load(f)
  cost = (cost_per_mil[model_name]["input"] * input_tokens / 1_000_000) + (cost_per_mil[model_name]["output"] * output_tokens / 1_000_000)
  #print(f"input_tokens: {input_tokens}, output_tokens: {output_tokens}, model_name: {model_name}, cost: {cost}")
  return cost

# # Test it
# user_input = "I don't understand how this billing works, it makes no sense."
# score = get_confusion_score(user_input)

# print(f"Confusion Score: {score:.4f}") 
# # Output might be: Confusion Score: 0.8523