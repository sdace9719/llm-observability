

from typing import Annotated, TypedDict
from langgraph.graph import add_messages


class State(TypedDict):
    messages: Annotated[list, add_messages]
    query: str
    context: str
    rag_type: str
    rag_relevant: bool
    answer: str
    is_question: bool
    user_identifier: str
    sql_query: str
