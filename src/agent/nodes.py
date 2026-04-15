"""Agent graph node functions."""

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from rich.console import Console

from .prompts import REPORT_PROMPT, SYSTEM_PROMPT
from .state import AgentState

console = Console()

# Minimum number of tool calls before allowing conclusion
MIN_TOOL_CALLS = 3


def _count_tool_calls(messages: list) -> int:
    """Count how many tool calls have been made so far."""
    count = 0
    for msg in messages:
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            count += len(msg.tool_calls)
    return count


def make_analyze_alert(llm_with_tools):
    """Create the analyze_alert node with LLM bound."""

    def analyze_alert(state: AgentState) -> dict:
        """分析告警上下文，规划诊断方向."""
        alert = state["alert"]
        console.print("\n[bold yellow][Step 0] 🚨 分析告警信息[/bold yellow]")
        console.print(f"  告警: {alert.get('description', alert.get('metric_name', 'unknown'))}")

        alert_text = (
            f"收到一条告警事件，请立即开始诊断。\n\n"
            f"告警详情：\n"
            f"```json\n{json.dumps(alert, ensure_ascii=False, indent=2)}\n```\n\n"
            f"第一步：请调用 query_metrics 工具查询指标 {alert.get('metric_name', '')} 的数据。"
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=alert_text),
        ]

        response = llm_with_tools.invoke(messages)

        if hasattr(response, "tool_calls") and response.tool_calls:
            tool_name = response.tool_calls[0]["name"]
            console.print(f"  → 调用工具: [green]{tool_name}[/green]")

        return {
            "messages": [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=alert_text), response],
            "current_step": 1,
            "status": "running",
            "evidence": [],
            "root_causes": [],
        }

    return analyze_alert


def make_agent_node(llm_with_tools):
    """Create the agent node that decides tool calls."""

    def agent_node(state: AgentState) -> dict:
        """Agent 推理节点：根据当前状态决定调用工具或给出结论."""
        step = state.get("current_step", 0)
        console.print(f"\n[bold cyan][Step {step}] 🤔 Agent 推理中...[/bold cyan]")

        messages = list(state["messages"])

        # If too few tool calls, nudge the agent to keep investigating
        tool_count = _count_tool_calls(messages)
        if tool_count < MIN_TOOL_CALLS:
            nudge = (
                "你还没有收集到足够的证据。"
                "请继续调用工具进行分析（维度下钻、贡献度计算、日志搜索、变更事件检查等）。"
                "至少需要使用 3 个不同的工具才能得出可靠结论。"
            )
            messages.append(HumanMessage(content=nudge))

        response = llm_with_tools.invoke(messages)

        if hasattr(response, "tool_calls") and response.tool_calls:
            tool_name = response.tool_calls[0]["name"]
            console.print(f"  → 调用工具: [green]{tool_name}[/green]")
        else:
            console.print("  → Agent 认为已收集足够证据，准备总结")

        return {
            "messages": [response],
            "current_step": step + 1,
        }

    return agent_node


def make_evaluate_result():
    """Create the evaluate_result node."""

    def evaluate_result(state: AgentState) -> dict:
        """评估当前诊断进度，决定继续还是结束."""
        step = state.get("current_step", 0)
        max_steps = state.get("max_steps", 15)

        if step >= max_steps:
            console.print(f"\n[bold red]⚠ 达到最大步骤数 ({max_steps})，结束诊断[/bold red]")
            return {"status": "max_steps_reached"}

        # Check if enough tools have been called
        tool_count = _count_tool_calls(state.get("messages", []))
        if tool_count < MIN_TOOL_CALLS:
            console.print(f"  → 已调用 {tool_count} 个工具，继续收集证据...")
            return {"status": "running"}

        console.print(f"  → 已调用 {tool_count} 个工具，证据充分，准备生成报告")
        return {"status": "completed"}

    return evaluate_result


def make_generate_report(llm):
    """Create the generate_report node with raw LLM (no tools)."""

    def generate_report(state: AgentState) -> dict:
        """生成最终归因诊断报告."""
        console.print("\n[bold green]📋 生成归因诊断报告...[/bold green]")

        messages = state["messages"] + [HumanMessage(content=REPORT_PROMPT)]
        response = llm.invoke(messages)

        report = response.content
        console.print("\n[bold green]✅ 诊断完成[/bold green]")

        return {
            "report": report,
            "status": "completed",
        }

    return generate_report
