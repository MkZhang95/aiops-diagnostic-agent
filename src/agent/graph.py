"""Agent Graph 定义 — Phase 2 版本

两阶段架构:
  Phase 1 (采集): init_plan → analyze_alert → agent_node → validate_tool_calls
                  ⇄ tool_node → update_checklist → verify_completeness
  Phase 2 (归因): match_scenarios → diagnose → END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from src.agent.nodes import (
    ROUTE_OK,
    make_agent_node,
    make_analyze_alert,
    make_diagnose,
    make_init_plan,
    make_match_scenarios,
    make_route_metric,
    update_checklist,
    validate_tool_calls,
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

    # ---- Phase 0: NL 路由（场景模式下自动 bypass） ----
    graph.add_node("route_metric", make_route_metric(llm, runbook_dir))

    # ---- Phase 1: 数据采集 ----
    graph.add_node("init_plan", make_init_plan(runbook_dir))
    graph.add_node("analyze_alert", make_analyze_alert(llm))
    graph.add_node("agent_node", make_agent_node(llm, tools))
    graph.add_node("validate_tool_calls", validate_tool_calls)
    graph.add_node("tool_node", ToolNode(tools))
    graph.add_node("update_checklist", update_checklist)
    graph.add_node("verify_completeness", verify_completeness)

    # ---- Phase 2: 归因判断 ----
    graph.add_node("match_scenarios", make_match_scenarios(runbook_dir))
    graph.add_node("diagnose", make_diagnose(llm))

    # ---- 连线 ----
    graph.set_entry_point("route_metric")

    # route_metric → init_plan（路由成功 / bypass）或 END（unknown）
    graph.add_conditional_edges(
        "route_metric",
        _route_after_router,
        {
            "init_plan": "init_plan",
            "end": END,
        },
    )
    graph.add_edge("init_plan", "analyze_alert")
    graph.add_edge("analyze_alert", "agent_node")

    # agent_node 之后：有工具调用 → validate_tool_calls，否则 → verify_completeness
    graph.add_conditional_edges(
        "agent_node",
        _route_after_agent,
        {
            "validate_tool_calls": "validate_tool_calls",
            "verify_completeness": "verify_completeness",
        },
    )

    # validate_tool_calls 之后：合法 → tool_node；非法 → 回 agent_node 重试
    graph.add_conditional_edges(
        "validate_tool_calls",
        _route_after_validate,
        {
            "tool_node": "tool_node",
            "agent_node": "agent_node",
        },
    )

    # tool_node 执行完 → update_checklist
    graph.add_edge("tool_node", "update_checklist")

    # update_checklist → 回到 agent_node 继续
    graph.add_edge("update_checklist", "agent_node")

    # verify_completeness 之后：三种去向
    graph.add_conditional_edges(
        "verify_completeness",
        _route_after_verify,
        {
            "agent_node": "agent_node",
            "match_scenarios": "match_scenarios",
        },
    )

    # Phase 2 线性流程
    graph.add_edge("match_scenarios", "diagnose")
    graph.add_edge("diagnose", END)

    return graph.compile()


# ============================================================
# 路由函数
# ============================================================


def _route_after_router(state: dict) -> str:
    """route_metric 之后：路由成功 / bypass 进 init_plan，未知则结束。"""
    status = state.get("route_status", ROUTE_OK)
    if status == "unknown":
        return "end"
    return "init_plan"


def _route_after_agent(state: dict) -> str:
    """agent_node 之后的路由

    - 如果最后一条 AI 消息包含 tool_calls → 先做 Runbook Gate 校验
    - 否则 → 进入完整性验证
    """
    messages = state.get("messages", [])
    if not messages:
        return "verify_completeness"

    last_msg = messages[-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "validate_tool_calls"

    return "verify_completeness"


def _route_after_validate(state: dict) -> str:
    """validate_tool_calls 之后的路由"""
    if state.get("tool_calls_valid", True):
        return "tool_node"
    return "agent_node"


def _route_after_verify(state: dict) -> str:
    """verify_completeness 之后的路由

    - phase == "diagnosing": 采集结束，进入场景匹配 + 归因
    - 其他: 有遗漏 must 步骤，回到 agent_node 继续
    """
    phase = state.get("phase", "collecting")
    if phase == "diagnosing":
        return "match_scenarios"
    return "agent_node"
