import logging

from langgraph.graph import END, START, StateGraph

from app.agent.nodes import conditional_cx_node, cx_node, cx_tool_node
from app.agent.state import CXGraphState

logger = logging.getLogger(__name__)

_graph = None


def build_cx_graph():
    global _graph
    if _graph is not None:
        return _graph

    workflow = StateGraph(CXGraphState)
    workflow.add_node("cx_node", cx_node)
    workflow.add_node("cx_tool_node", cx_tool_node)
    workflow.add_conditional_edges("cx_node", conditional_cx_node, {"cx_tool_node": "cx_tool_node", "end": END})
    workflow.add_edge("cx_tool_node", "cx_node")
    workflow.add_edge(START, "cx_node")

    _graph = workflow.compile()
    logger.info("CX agent graph compiled")
    return _graph
