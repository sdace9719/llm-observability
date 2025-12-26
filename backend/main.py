from __future__ import annotations
import asyncio
import subprocess
from datadog.dogstatsd.base import statsd
from dotenv import load_dotenv
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from flask import Flask, jsonify, request, session
from typing import Any, Dict, Optional
from ddtrace import patch_all
from ddtrace import tracer
patch_all(llm_providers=["langchain"])
from llm import State, chatagent

import psycopg

from db_utils import get_db_conn, DB_SETTINGS

from utils import (
  create_session, 
  validate_session,
  increment_session_count
)

from llm_utils import set_emotion_tags


app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("FLASK_SECRET_KEY", "dev-secret-key")
JUDGE_PASSWORD = os.getenv("JUDGE_PASSWORD")

retriever = None

CORS_ORIGIN = os.getenv("CORS_ORIGIN", "http://localhost:5173")
SESSION_COOKIE_SECURE = bool(int(os.getenv('SESSION_COOKIE_SECURE', '0')))
SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
SESSION_COOKIE_MAX_AGE = int(os.getenv('SESSION_COOKIE_MAX_AGE_SECONDS', str(60 * 60 * 12)))
SESSION_MAX_AGE_SECONDS = int(os.getenv('SESSION_MAX_AGE_SECONDS', '300'))  # default 5 minutes

@app.after_request
def add_cors_headers(response):
  """Allow browser clients (e.g. the React frontend) to call this API."""
  origin = request.headers.get('Origin') or CORS_ORIGIN
  response.headers['Access-Control-Allow-Origin'] = origin
  response.headers['Vary'] = 'Origin'
  response.headers['Access-Control-Allow-Credentials'] = 'true'
  response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Session-Id'
  response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
  return response


@contextmanager
def get_db_conn():
  conn = psycopg.connect(**DB_SETTINGS)
  try:
    yield conn
  finally:
    conn.close()



@app.route('/api/login', methods=['POST'])
def login() -> Any:
  payload: Dict[str, Any] = request.get_json(silent=True) or {}
  user_code = payload.get("access_code")
  if user_code != JUDGE_PASSWORD:
    return jsonify({"error": "Invalid Code"}), 401
  session["is_authorized"] = True
  user_identifier = str(payload.get('email') or payload.get('user') or '').strip()
  if not user_identifier:
    return jsonify({'error': 'Missing user identifier (email or user)'}), 400

  try:
    session_id = create_session(user_identifier)
  except ValueError as exc:
    return jsonify({'error': str(exc)}), 400
  except Exception as exc:  # pragma: no cover - defensive
    return jsonify({'error': f'Unable to create session: {exc}'}), 500

  response = jsonify({'session_id': session_id})
  response.set_cookie(
      'session_id',
      session_id,
      httponly=True,
      secure=SESSION_COOKIE_SECURE,
      samesite=SESSION_COOKIE_SAMESITE,
      path='/',
      max_age=SESSION_COOKIE_MAX_AGE,
  )
  response.set_cookie(
    'user_identifier',
    user_identifier,
    httponly=True,
    secure=SESSION_COOKIE_SECURE,
    samesite=SESSION_COOKIE_SAMESITE,
    path='/',
    max_age=SESSION_COOKIE_MAX_AGE,
  )
  return response


@app.route('/health', methods=['GET'])
def health() -> Any:
  return jsonify({'status': 'ok', 'timestamp': datetime.now(timezone.utc).isoformat()})


@app.route('/api/chat', methods=['POST'])
async def chat() -> Any:
  
  if not session.get("is_authorized"):
    return jsonify({'error': 'Unauthorized. Please login first.'}), 401

  session_id = request.cookies.get('session_id')
  if not validate_session(session_id):
    return jsonify({'error': 'Session expired or invalid. Please login again.'}), 401

  increment_session_count(session_id)

  payload: Dict[str, Any] = request.get_json(silent=True) or {}
  query = str(payload.get('prompt', '')).strip()

  if not query:
    return jsonify({'error': 'Missing query'}), 400
  
   
  current_context = tracer.current_trace_context()
  asyncio.create_task(set_emotion_tags(query,current_context))
  
  state: State = {
    "messages": [],
    "query": query,
    "context": "",
    "rag_type": "",
    "rag_relevant": False,
    "answer": "",
    "is_question": True,
    "user_identifier": request.cookies.get('user_identifier') or "",
    "sql_query": "",
  }
  if not state["user_identifier"]:
    return jsonify({'error': 'Missing user identifier'}), 400

  response = await chatagent.ainvoke(state)

  return jsonify(
      {
          'prompt': query,
          'reply': response['answer'],
          'received_at': datetime.now(timezone.utc).isoformat()
      }
  )


@app.route('/api/logout', methods=['POST'])
def close_session() -> Any:
  session_id = request.cookies.get('session_id')
  user_identifier = request.cookies.get('user_identifier')
  if not session_id:
    return jsonify({'error': 'Missing session'}), 400

  with get_db_conn() as conn, conn.cursor() as cur:
    res = cur.execute("SELECT conversation_count FROM user_sessions WHERE user_identifier = %s ;", (user_identifier,))
    for chat_length in res:
        statsd.distribution(
            "chatbot.session.chat_length",
            chat_length[0],
            tags=[
                "session_id:{}".format(session_id)
            ]
        )
    cur.execute("DELETE FROM user_sessions WHERE session_id = %s;", (session_id,))
    conn.commit()

  response = jsonify({'status': 'closed'})
  response.delete_cookie('session_id', path='/')
  return response


@app.route('/api/sessions', methods=['DELETE'])
def close_all_sessions() -> Any:
  payload: Dict[str, Any] = request.get_json(silent=True) or {}
  user_identifier = payload.get('email') or payload.get('user')
  user_identifier = str(user_identifier).strip() if user_identifier else None

  if not user_identifier:
    return jsonify({'error': 'Missing user identifier'}), 400

  with get_db_conn() as conn, conn.cursor() as cur:
    res = cur.execute("SELECT session_id, conversation_count FROM user_sessions WHERE user_identifier = %s;", (user_identifier,))
    for session_id, chat_length in res:
        statsd.distribution(
            "chatbot.session.chat_length",
            chat_length,
            tags=[
                "session_id:{}".format(session_id)
            ]
        )
    cur.execute("DELETE FROM user_sessions WHERE user_identifier = %s;", (user_identifier,))
    conn.commit()

  resp = jsonify({'status': 'all sessions closed'})
  resp.delete_cookie('session_id', path='/')
  return resp


if __name__ == '__main__':
  # Initialize it once when the app starts
  load_dotenv()
  # vectorstore = initialize_vector_store()

  # # --- STEP 2: SETUP THE RETRIEVER & CHAIN ---

  # # Create a Retriever
  # # "k=3" means "Find the top 3 most relevant policy chunks"
  # retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
  app.run(host="0.0.0.0", port=int(os.getenv("PORT", "4000")), debug=True, use_reloader=False)

