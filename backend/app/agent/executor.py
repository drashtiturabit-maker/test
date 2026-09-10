import json
import logging
import time
from typing import AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage

from app.agent.graph import build_cx_graph
from app.agent.runnables import build_system_vars

logger = logging.getLogger(__name__)


async def stream_agent_response(
    query: str,
    thread_id: str,
    client_key: str,
    agent_config: dict,
    pinecone_namespace: str,
    chat_history: list[dict] | None = None,
) -> AsyncGenerator[str, None]:
    graph = build_cx_graph()
    system_vars = build_system_vars(agent_config)

    messages = []
    for msg in chat_history or []:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=query))

    config = {
        "configurable": {
            "thread_id": thread_id,
            "client_key": client_key,
            "pinecone_namespace": pinecone_namespace,
            "system_vars": system_vars,
            "lead_generation_config": {
                "status": True,
                "lead_collection_category": "silent",
            },
        },
        "recursion_limit": 25,
    }

    input_state = {
        "messages": messages,
        "client_key": client_key,
        "session_id": thread_id,
        "assistant_name": agent_config.get("bot_name", "Assistant"),
        "bot_name": agent_config.get("bot_name", "Assistant"),
        "company_name": agent_config.get("company_name", ""),
        "tone_description": system_vars["tone_description"],
        "custom_instructions": system_vars["custom_instructions"],
        "fallback_message": system_vars["fallback_message"],
        "expense": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "meeting_info": {},
        "lead_generation_obj_mapper": {},
        "lead_collection_intents": [],
        "all_lead_fields_collected": False,
        "retrieved_sources": [],
        "user_query": [],
    }

    start = time.time()
    final_text = ""
    sources = []

    try:
        for event in graph.stream(input_state, config=config, stream_mode="updates"):
            for node_name, node_output in event.items():
                if node_name == "cx_node" and node_output.get("messages"):
                    last = node_output["messages"][-1]
                    if hasattr(last, "content") and last.content and not getattr(last, "tool_calls", None):
                        token = last.content
                        if token != final_text:
                            new_part = token[len(final_text):] if token.startswith(final_text) else token
                            final_text = token
                            yield json.dumps({"type": "token", "content": new_part}) + "\n"
                if node_output.get("retrieved_sources"):
                    sources = node_output["retrieved_sources"]

        latency = int((time.time() - start) * 1000)
        yield json.dumps({
            "type": "done",
            "sources": list(set(sources)),
            "latency_ms": latency,
            "session_id": thread_id,
        }) + "\n"
    except Exception as e:
        logger.exception("Agent error: %s", e)
        yield json.dumps({"type": "error", "message": str(e)}) + "\n"
