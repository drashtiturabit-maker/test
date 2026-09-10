import logging

from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables.config import RunnableConfig

from app.agent.runnables import create_cx_agent
from app.agent.state import CXGraphState
from app.agent.tools import _TOOL_REGISTRY

logger = logging.getLogger(__name__)

_cx_runnable = None


def get_cx_runnable():
    global _cx_runnable
    if _cx_runnable is None:
        _cx_runnable = create_cx_agent()
    return _cx_runnable


def cx_node(state: CXGraphState, config: RunnableConfig):
    runnable = get_cx_runnable()
    system_vars = config.get("configurable", {}).get("system_vars", {})
    response = runnable.invoke(
        {"messages": state["messages"], **system_vars},
        config=config,
    )
    return {"messages": [response]}


def cx_tool_node(state: CXGraphState, config: RunnableConfig):
    tool_calls = state["messages"][-1].tool_calls
    messages = []
    state_updates = {}

    for tool_call in tool_calls:
        tool = _TOOL_REGISTRY.get(tool_call["name"])
        if not tool:
            content = f"Unknown tool: {tool_call['name']}"
            state_changes = {}
        else:
            tool_args = {**tool_call["args"], "state": state, "config": config}
            content, state_changes = tool.invoke(tool_args)
            state_updates.update(state_changes or {})

        messages.append(ToolMessage(content=str(content), tool_call_id=tool_call["id"]))

    return {"messages": messages, **state_updates}


def conditional_cx_node(state: CXGraphState):
    if state["messages"][-1].tool_calls:
        return "cx_tool_node"
    return "end"
