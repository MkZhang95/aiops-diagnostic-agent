"""LangGraph StateGraph definition for the diagnostic agent."""

from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from .nodes import (
    make_agent_node,
    make_analyze_alert,
    make_evaluate_result,
    make_generate_report,
)
from .state import AgentState


def _should_continue_after_agent(state: AgentState) -> str:
    """Route after agent node: tool call or evaluate."""
    messages = state.get("messages", [])
    if not messages:
        return "evaluate_result"

    last_message = messages[-1]
    if isinstance(last_message, AIMessage) and getattr(last_message, "tool_calls", None):
        return "tool_node"

    return "evaluate_result"


def _should_continue_after_evaluate(state: AgentState) -> str:
    """Route after evaluate: continue or generate report."""
    status = state.get("status", "running")
    if status in ("completed", "max_steps_reached", "failed"):
        return "generate_report"
    return "agent_node"


def build_graph(llm, tools: list | None = None):
    """Build the diagnostic agent LangGraph.

    Args:
        llm: BaseLLM instance
        tools: List of LangChain tools. If None, builds a minimal graph without tool calling.

    Returns:
        Compiled LangGraph
    """
    chat_model = llm.get_chat_model()

    if tools:
        llm_with_tools = chat_model.bind_tools(tools)
        tool_node = ToolNode(tools)
    else:
        llm_with_tools = chat_model
        tool_node = None

    # Create node functions
    analyze_alert = make_analyze_alert(llm_with_tools)
    agent_node = make_agent_node(llm_with_tools)
    evaluate_result = make_evaluate_result()
    generate_report = make_generate_report(chat_model)  # report uses raw LLM, no tools

    # Build graph
    graph = StateGraph(AgentState)

    graph.add_node("analyze_alert", analyze_alert)
    graph.add_node("agent_node", agent_node)
    graph.add_node("evaluate_result", evaluate_result)
    graph.add_node("generate_report", generate_report)

    if tool_node:
        graph.add_node("tool_node", tool_node)

    # Edges
    graph.set_entry_point("analyze_alert")
    graph.add_edge("analyze_alert", "agent_node")

    if tool_node:
        graph.add_conditional_edges(
            "agent_node",
            _should_continue_after_agent,
            {"tool_node": "tool_node", "evaluate_result": "evaluate_result"},
        )
        graph.add_edge("tool_node", "agent_node")
    else:
        graph.add_edge("agent_node", "evaluate_result")

    graph.add_conditional_edges(
        "evaluate_result",
        _should_continue_after_evaluate,
        {"agent_node": "agent_node", "generate_report": "generate_report"},
    )
    graph.add_edge("generate_report", END)

    return graph.compile()
