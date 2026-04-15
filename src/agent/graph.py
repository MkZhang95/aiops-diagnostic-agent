"""Agent Graph 定义 — Phase 2 版本

两阶段架构:
  Phase 1 (采集): init_plan → analyze_alert → agent_node ⇄ tool_node
                  → update_checklist → verify_completeness
  Phase 2 (匹配): match_scenarios → generate_report → END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from src.agent.nodes import (
    make_analyze_alert,
    make_agent_node,
    make_generate_report,
    make_init_plan,
    make_match_scenarios,
    update_checklist,
    verify_completeness,
)
from src.agent.state import AgentState


def build_graph(llm, tools, runbook_dir: str = "runbooks"):
    """构建 Agent 执行图

    Args:
        llm: LLM 实例（BaseLLM 子类）
        tools: 工具列表
        runbook_dir: Runbook 目录路径

    Returns:
        编译后的 LangGraph 图
    """
    graph = StateGraph(AgentState)

    # ---- Phase 1: 数据采集 ----
    graph.add_node("init_plan", make_init_plan(runbook_dir))
    graph.add_node("analyze_alert", make_analyze_alert(llm))
    graph.add_node("agent_node", make_agent_node(llm, tools))
    graph.add_node("tool_node", ToolNode(tools))
    graph.add_node("update_checklist", update_checklist)
    graph.add_node("verify_completeness", verify_completeness)

    # ---- Phase 2: 场景匹配 + 报告 ----
    graph.add_node("match_scenarios", make_match_scenarios(runbook_dir))
    graph.add_node("generate_report", make_generate_report(llm))

    # ---- 连线 ----
    graph.set_entry_point("init_plan")
    graph.add_edge("init_plan", "analyze_alert")
    graph.add_edge("analyze_alert", "agent_node")

    # agent_node 之后：有工具调用 → tool_node，否则 → verify_completeness
    graph.add_conditional_edges(
        "agent_node",
        _route_after_agent,
        {
            "tool_node": "tool_node",
            "verify_completeness": "verify_completeness",
        },
    )

    # tool_node 执行完 → update_checklist
    graph.add_edge("tool_node", "update_checklist")

    # update_checklist → 回到 agent_node 继续
    graph.add_edge("update_checklist", "agent_node")

    # verify_completeness 之后：有遗漏 → agent_node，完成 → match_scenarios
    graph.add_conditional_edges(
        "verify_completeness",
        _route_after_verify,
        {
            "agent_node": "agent_node",
            "match_scenarios": "match_scenarios",
        },
    )

    # Phase 2 线性流程
    graph.add_edge("match_scenarios", "generate_report")
    graph.add_edge("generate_report", END)

    return graph.compile()


# ============================================================
# 路由函数
# ============================================================


def _route_after_agent(state: dict) -> str:
    """agent_node 之后的路由

    - 如果最后一条 AI 消息包含 tool_calls → 执行工具
    - 否则 → 进入完整性验证
    """
    messages = state.get("messages", [])
    if not messages:
        return "verify_completeness"

    last_msg = messages[-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tool_node"

    return "verify_completeness"


def _route_after_verify(state: dict) -> str:
    """verify_completeness 之后的路由

    - iteration == -1: 全部完成，进入场景匹配
    - iteration >= 0: 有遗漏，回到 agent_node
    """
    iteration = state.get("iteration", 0)
    if iteration == -1:
        return "match_scenarios"
    return "agent_node"
