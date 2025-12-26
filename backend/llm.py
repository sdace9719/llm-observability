import os
from ddtrace.llmobs import LLMObs
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.graph import END, StateGraph, START
from ddtrace import tracer
from ddtrace import patch_all
from ddtrace.llmobs.decorators import llm
patch_all(llm_providers=["langchain"])

from db_utils import get_latest_order_id_by_product, place_new_order, update_order_items_if_processing
from state import State
from critic import check_answer_relevance, check_rag_relevance, check_query_classification

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from rag import get_rag_chain, initialize_vector_store
from utils import  get_cost, get_db_conn, render_graph_image
from dotenv import load_dotenv

@llm(model_name="gemini-flash-latest", model_provider="google")
def generate_query(state: State) -> State:
    with open("support_schema.txt", "r") as f:
        schema = f.read()
    template = """
    Generate a Postgresql query to run against the customer support database and
    return the result as a string. Ensure the query is in a proper text that can be
    given as it is to the db query executor without any changes/formatting.
    Example: SELECT * FROM customers WHERE email = 'test@example.com';

    The user query is: {user_query}
    user identifier: {user_identifier}

    Detailes schema is below:

    {schema}

    The query executor uses the following piece of code to format the result:
        rows = cur.fetchall()
        column_names = [desc[0] for desc in cur.description]
        
        formatted_rows = []
        for row in rows:
            # Zip creates pairs like: [('unit_price', 549.00), ('name', 'Lift Desk')]
            # Result string: "unit_price: 549.00"
            row_parts = [f"{col}: {val}" for col, val in zip(column_names, row)]
            formatted_rows.append(", ".join(row_parts))
            
        result_text = "\n".join(formatted_rows)
        print(result_text)

    Ensure that the generated query results in a meaningful result containing enough information so that
    the result can be used by another LLM to query the answer without making up any information. Use joins if necessary.

    IMPORTANT JOIN RULES:
    1. Always join 'customers' and 'orders' on 'customer_id' (e.g. customers.customer_id = orders.customer_id).
    2. NEVER join on 'email' or names.
    3. To filter by email, use WHERE customers.email = '...'.
    4. Both the operands of the join should be from the same data type and the column name should be exactly the same in both the tables.

    If such a query is not possible then return the following query.
    empty result query: SELECT * FROM customers WHERE false;
    """
    prompt = ChatPromptTemplate.from_template(template).invoke({"user_query": state['query'],"col": "col", "val": "val", "user_identifier": state['user_identifier'], "schema": schema})
    query_generator = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0, api_key=os.getenv("GOOGLE_API_KEY"),transport="rest")
    res = query_generator.invoke(prompt)
    usage = res.usage_metadata
    cost = get_cost(usage.get("input_tokens", -1), usage.get("output_tokens", -1), "gemini-flash-latest")
    LLMObs.annotate(
    metrics={
        # LangChain normalizes these keys for you
        "input_tokens": usage.get("input_tokens", -1),
        "output_tokens": usage.get("output_tokens", -1),
        "total_tokens": usage.get("total_tokens", -1),
        "total_cost": cost,
        }
    )
    if isinstance(res, dict):
        query = res.get('content', '')
    elif isinstance(res.content, list):
    # Case A: Content is a list of blocks (common in Gemini/Claude)
    # Join all 'text' parts together
        query = "".join(
        block.__str__() if not isinstance(block, dict) else block.get("text", "") for block in res.content
        )
    else:
        query = res.content.strip()
    return {"messages": [res], "sql_query": query}


def execute_query(state: State) -> State:
    with get_db_conn() as conn, conn.cursor() as cur:
        print(state['sql_query'])
        cur.execute(state['sql_query'])
        rows = cur.fetchall()
        column_names = [desc[0] for desc in cur.description]
        
        formatted_rows = []
        for row in rows:
            # Zip creates pairs like: [('unit_price', 549.00), ('name', 'Lift Desk')]
            # Result string: "unit_price: 549.00"
            row_parts = [f"{col}: {val}" for col, val in zip(column_names, row)]
            formatted_rows.append(", ".join(row_parts))
            
        result_text = "\n".join(formatted_rows)
        return {"messages": [("system", result_text)], "context": result_text}




@llm(model_name="gemini-flash-latest", model_provider="google")
def get_policy_context(state: State) -> State:
    '''
    Get the policy context from the policy documents of the company and based on the user query by 
    doing a vector embedding similarity search.
    Arguments:
    user_query: The user query to get the policy context for.
    Returns:
    The policy context as a string.
    '''
    template = """You are a Customer Support Agent. 
    Use the user query to determine the relevant context from policy documents that contains answer to the user's query.
    If the answer is not in the context, say "I don't have that information."
    Do not make up facts.

    Question: {question}
    """
    policy_fetcher = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0, api_key=os.getenv("GOOGLE_API_KEY"),transport="rest")
    prompt = ChatPromptTemplate.from_template(template)
    rag_chain = get_rag_chain(retriever, policy_fetcher, prompt)

    reply = rag_chain.invoke({"question": state['query']})
    usage = reply.usage_metadata
    cost = get_cost(usage.get("input_tokens", -1), usage.get("output_tokens", -1), "gemini-flash-latest")
    LLMObs.annotate(
    metrics={
        # LangChain normalizes these keys for you
        "input_tokens": usage.get("input_tokens", -1),
        "output_tokens": usage.get("output_tokens", -1),
        "total_tokens": usage.get("total_tokens", -1),
        "total_cost": cost,
        }
    )
    return {"messages": [reply], "context": reply.content}


@llm(model_name="gemini-pro-latest", model_provider="google")
def get_rag_type(State: State) -> State:
    template = """
    There are two types of RAG to use. One is the customer support database and the other is the policy documents of the company.
    Based on the user query, determine the type of RAG to use.
    The only two possible types are "policy" and "database".
    Do not make up any other types.
    query: {query}
    """
    prompt = ChatPromptTemplate.from_template(template).invoke({"query": State['query']})
    classifier = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0, api_key=os.getenv("GOOGLE_API_KEY"),transport="rest")
    result = classifier.invoke(prompt)
    usage = result.usage_metadata
    cost = get_cost(usage.get("input_tokens", -1), usage.get("output_tokens", -1), "gemini-flash-latest")
    LLMObs.annotate(
    metrics={
        # LangChain normalizes these keys for you
        "input_tokens": usage.get("input_tokens", -1),
        "output_tokens": usage.get("output_tokens", -1),
        "total_tokens": usage.get("total_tokens", -1),
        "total_cost": cost,
        }
    )
    tracer.current_span().set_tag("rag_type", result.content.strip())
    return {"messages": [result], "rag_type": result.content.strip()}

def route_rag_type(state: State) -> str:
    return state['rag_type']

@llm(model_name="gemini-flash-latest", model_provider="google")
def process_request(state: State) -> State:
    template = """
    You are acting as an order processing agent. You are only allowed to place new orders or
    change contents of an existing order only if the existing order is in 'processing' state.
    You will be provided a set of tools to process the request. However, ensure that you have
    the necessary information before calling the tools.
    If the user query is missing necessary information required to process the request with the tools,
    reply with 'missing information' and specify what is expected.
    query: {query}

    You can use the following user email to process the request.
    user email: {user_identifier}
    """

    prompt = template.format(
        query=state['query'], 
        user_identifier=state['user_identifier']
    )
    # 1. Setup the Model and Tools
    tools = [place_new_order, update_order_items_if_processing, get_latest_order_id_by_product]
    # Create a mapping to easily run functions by name later
    tool_map = {t.name: t for t in tools}

    processor = ChatGoogleGenerativeAI(
        model="gemini-flash-latest", # Recommendation: Use specific version for stability
        temperature=0, 
        api_key=os.getenv("GOOGLE_API_KEY")
    ).bind_tools(tools)

    # 2. Initialize Message History
    # We use a list of messages so we can append tool outputs
    messages = [
        ("system", prompt),
        ("human", state['query']),
    ]

    MAX_ITERATIONS = 5
    final_response = None

    # 3. The Execution Loop
    total_cost = 0
    total_input_tokens = 0
    total_output_tokens = 0
    for _ in range(MAX_ITERATIONS):
        # Call the LLM
        ai_msg = processor.invoke(messages)
        total_cost += get_cost(ai_msg.usage_metadata.get("input_tokens", -1), ai_msg.usage_metadata.get("output_tokens", -1), "gemini-flash-latest")
        total_input_tokens += ai_msg.usage_metadata.get("input_tokens", -1)
        total_output_tokens += ai_msg.usage_metadata.get("output_tokens", -1)
        # Append the AI's response (tool call or final text) to history
        messages.append(ai_msg)

        # CHECK: Did the LLM ask for a tool?
        if not ai_msg.tool_calls:
            # No tool calls -> This is the final answer
            if isinstance(ai_msg, dict):
                final_response = ai_msg.get('content', '')
            elif isinstance(ai_msg.content, list):
                final_response = "".join(
                block.__str__() if not isinstance(block, dict) else block.get("text", "") for block in ai_msg.content
                )
            else:
                final_response = ai_msg.content.strip()
            break

        # EXECUTE: Run the requested tools
        for tool_call in ai_msg.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            print(f"Tool name: {tool_name}, Tool args: {tool_args}")
            
            # Run the actual function
            if tool_name in tool_map:
                tool_output = tool_map[tool_name].invoke(tool_args)
            else:
                tool_output = f"Error: Tool {tool_name} not found."

            # Create a message representing the tool's result
            tool_msg = ToolMessage(
                content=str(tool_output),
                tool_call_id=tool_call["id"],
                name=tool_name
            )
            
            # Append result to history so LLM sees it in next loop
            messages.append(tool_msg)

    else:
        # This 'else' block executes only if the loop finishes normally (without break)
        # meaning we hit MAX_ITERATIONS without a final answer.
        #raise Exception(f"Max loop depth of {MAX_ITERATIONS} reached without final response.")
        response = AIMessage(
            content=f"I am unable to process the request at this time"
        )
        messages.append(response)
        final_response = response.content
    LLMObs.annotate(
    metrics={
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "total_tokens": total_input_tokens + total_output_tokens,
        "total_cost": total_cost,
        }
    )

    # 4. Return or Use the Result
    return {"messages": messages, "answer": final_response}

@llm(model_name="gemini-flash-latest", model_provider="google")
def classify_query(State: State) -> State:
    template = """
    Determine if the user query is a question.
    The only possible responses you should give are: "yes", "no", "request","Security Violation".
    Do not make up any other types.
    The user should not be able to access any information on other users or the system. Any information that is not related to their orders
    or billing information should be considered as unauthorized information. Generic information like type of products, price and stock is ok.
    In the event of any unauthorized requests, replywith 'Security Violation'.
    If the user makes a request that falls into below categories, reply with 'request':-
    - Place a neworder
    - Change contents of an existing order.
    query: {query}
    """
    prompt = ChatPromptTemplate.from_template(template).invoke({"query": State['query']})
    classifier = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0, api_key=os.getenv("GOOGLE_API_KEY"),transport="rest")
    res = classifier.invoke(prompt)
    usage = res.usage_metadata
    cost = get_cost(usage.get("input_tokens", -1), usage.get("output_tokens", -1), "gemini-flash-latest")
    #print(usage)
    LLMObs.annotate(
    metrics={
        # LangChain normalizes these keys for you
        "input_tokens": usage.get("input_tokens", -1),
        "output_tokens": usage.get("output_tokens", -1),
        "total_tokens": usage.get("total_tokens", -1),
        "total_cost": cost,
        }
    )
    if isinstance(res, dict):
        result = res.get('content', '')
    elif isinstance(res.content, list):
        result = "".join(
        block.__str__() if not isinstance(block, dict) else block.get("text", "") for block in res.content
        )
    else:
        result = res.content.strip()
    if result=="Security Violation":
        tracer.current_span().set_tag("Breach Detected","yes")
        return {"messages": [res], "is_question": result, "answer": "Security Violation"}
    return {"messages": [res], "is_question": result}

def route_question(state: State) -> str:
    # Read the decision stored by the previous node
    return state['is_question']


@llm(model_name="gemini-flash-latest", model_provider="google")
def get_answer(state: State) -> State:
    template = """
    You are a customer support agent responsible for answering user queries
    You will be provided with the context of the user query.
    Use only the provided context to answer the question.
    If a relevant answer is not found within the context, reply with 'I don't have that information.'.
    If the user query is not a question, reply with 'your feedback has been recorded.'
    Do not make up facts.
    Context:
    {context}
    query: {query}
    """
    prompt = ChatPromptTemplate.from_template(template).invoke({"context": state['context'], "query": state['query']})
    actor = ChatGoogleGenerativeAI(model="gemini-flash-latest", temperature=0, api_key=os.getenv("GOOGLE_API_KEY"),transport="rest")
    result = actor.invoke(prompt)
    usage = result.usage_metadata   
    cost = get_cost(usage.get("input_tokens", -1), usage.get("output_tokens", -1), "gemini-flash-latest")
    LLMObs.annotate(
    metrics={
        # LangChain normalizes these keys for you
        "input_tokens": usage.get("input_tokens", -1),
        "output_tokens": usage.get("output_tokens", -1),
        "total_tokens": usage.get("total_tokens", -1),
        "total_cost": cost,
        }
    )
    if isinstance(result, dict):
        answer = result.get('content', '')
    else:
        answer = result.content
    return {"messages": [result], "answer": answer}

def route_check_answer_verification_needed(State: State) -> State:
    return State['is_question']


load_dotenv()
vectorstore = initialize_vector_store()
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})

chatbotapp = StateGraph(State)
chatbotapp.add_node("get_rag_type", get_rag_type)
#chatbotapp.add_node("route_rag_type", route_rag_type)
chatbotapp.add_node("classify_query", classify_query)
chatbotapp.add_node("process_request", process_request)
#chatbotapp.add_node("route_question", route_question)
chatbotapp.add_node("get_answer", get_answer)
chatbotapp.add_node("get_policy_context", get_policy_context)
chatbotapp.add_node("generate_query", generate_query)
chatbotapp.add_node("execute_query", execute_query)
chatbotapp.add_node("check_rag_relevance", check_rag_relevance)
chatbotapp.add_node("check_answer_relevance", check_answer_relevance)
chatbotapp.add_node("check_query_classification", check_query_classification)

chatbotapp.add_edge(START, "classify_query")
chatbotapp.add_edge("classify_query", "check_query_classification")
chatbotapp.add_conditional_edges(
    "classify_query",
    route_question,
    {
        "yes": "get_rag_type",
        "no": "get_answer",
        "request": "process_request",
        "Security Violation": END
    }
)
chatbotapp.add_conditional_edges(
    "get_rag_type",
    route_rag_type,
    {
        "policy": "get_policy_context",
        "database": "generate_query"
    }
)
chatbotapp.add_edge("get_policy_context", "check_rag_relevance")
chatbotapp.add_edge("get_policy_context", "get_answer")
chatbotapp.add_edge("generate_query", "execute_query")
chatbotapp.add_edge("execute_query", "check_rag_relevance")
chatbotapp.add_edge("execute_query", "get_answer")
chatbotapp.add_conditional_edges(
    "get_answer",
    route_check_answer_verification_needed,
    {
        "yes": "check_answer_relevance",
        "no": END,
        "request": END,
        "Security Violation": END
    }
)
# chatbotapp.add_edge("get_answer", "check_answer_relevance")
chatbotapp.add_edge("check_answer_relevance", END)
chatbotapp.add_edge("process_request", END)

chatagent = chatbotapp.compile()

if __name__ == "__main__":
    render_graph_image(chatagent)




