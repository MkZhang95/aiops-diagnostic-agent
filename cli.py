"""AIOps Diagnostic Agent CLI entry point."""

import argparse
import os
import time
from datetime import datetime

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from src.agent import build_graph
from src.agent.state import AlertEvent
from src.data import DataSimulator, list_scenarios
from src.llm import get_llm
from src.tools import get_all_tools

console = Console()


def _make_alert_event(alert_dict: dict) -> AlertEvent:
    """将场景数据中的 alert dict 转为 AlertEvent 对象"""
    return AlertEvent(
        alert_id=alert_dict.get("alert_id", f"alert_{int(time.time())}"),
        metric_name=alert_dict["metric_name"],
        severity=alert_dict.get("severity", "warning"),
        description=alert_dict.get("description", ""),
        timestamp=str(alert_dict.get("timestamp", "")),
        current_value=alert_dict.get("current_value", 0),
        baseline_value=alert_dict.get("baseline_value", 0),
        tags=alert_dict.get("tags", {}),
    )


def main():
    parser = argparse.ArgumentParser(description="AIOps Diagnostic Agent")
    parser.add_argument("--scenario", type=str, help="预置场景名称")
    parser.add_argument("--llm", type=str, default=None, help="LLM: claude/openai/zhipu")
    parser.add_argument("--verbose", action="store_true", help="详细模式")
    args = parser.parse_args()

    console.print(Panel("[bold]AIOps Diagnostic Agent v0.2.0[/bold]", style="blue"))

    # 选择场景
    if args.scenario:
        scenario_name = args.scenario
    else:
        scenarios = list_scenarios()
        console.print("\n[bold]选择诊断场景:[/bold]")
        for i, name in enumerate(scenarios, 1):
            console.print(f"  {i}. {name}")
        choice = input("\n请输入编号 (默认 1): ").strip() or "1"
        scenario_name = scenarios[int(choice) - 1]

    # 加载场景数据
    simulator = DataSimulator(scenario_name)
    alert_event = _make_alert_event(simulator.alert)
    console.print(f"  场景: [cyan]{scenario_name}[/cyan]")

    console.print(Panel(
        f"[bold red]{alert_event.description}[/bold red]\n"
        f"指标: {alert_event.metric_name}  "
        f"当前值: {alert_event.current_value}  "
        f"基线值: {alert_event.baseline_value}  "
        f"级别: {alert_event.severity}",
        title="告警信息",
    ))

    # 构建 Agent
    llm = get_llm(provider=args.llm)
    console.print(f"  模型: [cyan]{llm.model_name}[/cyan]")

    tools = get_all_tools(simulator)
    console.print(f"  工具: {len(tools)} 个\n")

    graph = build_graph(llm, tools=tools)

    # 执行
    console.print("[bold]开始诊断...[/bold]\n")
    start_time = time.time()

    initial_state = {
        "messages": [],
        "alert": alert_event,
        "phase": "collecting",
        "checklist": [],
        "evidence_pool": {},
        "matched_scenarios": [],
        "evidences": [],
        "root_causes": [],
        "iteration": 0,
    }

    # 流式输出 Agent 推理过程
    step_count = 0
    final_state = initial_state
    for event in graph.stream(initial_state):
        for node_name, state_update in event.items():
            step_count += 1

            if node_name == "agent_node":
                # 提取 AI 的 Thought 和工具调用
                messages = state_update.get("messages", [])
                for msg in messages:
                    if hasattr(msg, "content") and msg.content:
                        console.print("\n[bold cyan]Agent[/bold cyan]:")
                        console.print(msg.content)
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        for tc in msg.tool_calls:
                            console.print(
                                f"  [dim]-> 调用工具: {tc['name']}({tc.get('args', {})})[/dim]"
                            )

            elif node_name == "tool_node":
                messages = state_update.get("messages", [])
                for msg in messages:
                    if hasattr(msg, "content") and msg.content:
                        content = str(msg.content)
                        if len(content) > 200:
                            content = content[:200] + "..."
                        console.print(f"  [dim]<- {content}[/dim]")

            elif node_name == "diagnose":
                messages = state_update.get("messages", [])
                for msg in messages:
                    if hasattr(msg, "content") and msg.content:
                        report = msg.content

            final_state.update(state_update)

    elapsed = time.time() - start_time

    # 输出报告
    report = ""
    for msg in reversed(final_state.get("messages", [])):
        if hasattr(msg, "content") and msg.content and len(msg.content) > 200:
            report = msg.content
            break

    if report:
        console.print("\n")
        console.print(Panel(Markdown(report), title="归因诊断报告", border_style="green"))

        os.makedirs("output", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"output/report_{scenario_name}_{timestamp}.md"
        with open(report_path, "w") as f:
            f.write(report)
        console.print(f"\n  报告已保存: [cyan]{report_path}[/cyan]")

    # 统计
    evidence_count = len(final_state.get("evidence_pool", {}))
    matched_count = len(final_state.get("matched_scenarios", []))
    console.print(
        f"\n[dim]耗时: {elapsed:.1f}s | "
        f"Evidence: {evidence_count} 条 | "
        f"匹配场景: {matched_count} 个[/dim]"
    )


if __name__ == "__main__":
    main()
