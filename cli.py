"""AIOps Diagnostic Agent CLI entry point."""

import argparse
import time

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from src.agent import build_graph
from src.agent.state import AlertEvent
from src.data import DataSimulator, list_scenarios
from src.llm import get_llm
from src.report import save_report
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
        "tool_calls_valid": True,
    }

    # 流式输出 Agent 推理过程 + token 统计
    step_count = 0
    final_state = initial_state
    token_rounds: list[dict] = []  # 每次 LLM 调用的 token 明细
    agent_round = 0

    def _collect_usage(msg, stage: str):
        usage = getattr(msg, "usage_metadata", None) or {}
        if not usage:
            meta = getattr(msg, "response_metadata", {}) or {}
            usage = meta.get("token_usage") or meta.get("usage") or {}
        if not usage:
            return
        token_rounds.append({
            "stage": stage,
            "input": usage.get("input_tokens") or usage.get("prompt_tokens") or 0,
            "output": usage.get("output_tokens") or usage.get("completion_tokens") or 0,
            "total": usage.get("total_tokens") or 0,
        })

    for event in graph.stream(initial_state):
        for node_name, state_update in event.items():
            step_count += 1

            if node_name == "agent_node":
                agent_round += 1
                messages = state_update.get("messages", [])
                for msg in messages:
                    _collect_usage(msg, f"agent_round_{agent_round}")
                    console.print(
                        f"\n[bold cyan]── Agent 第 {agent_round} 轮 ──[/bold cyan]"
                    )
                    if hasattr(msg, "content") and msg.content:
                        console.print("[yellow]Thought:[/yellow]")
                        console.print(msg.content)
                    if hasattr(msg, "tool_calls") and msg.tool_calls:
                        console.print("[green]Action:[/green]")
                        for tc in msg.tool_calls:
                            args_str = str(tc.get("args", {}))
                            if len(args_str) > 300:
                                args_str = args_str[:300] + "..."
                            console.print(f"  → [bold]{tc['name']}[/bold]({args_str})")
                    usage = getattr(msg, "usage_metadata", None) or {}
                    if usage:
                        console.print(
                            f"  [dim]tokens: in={usage.get('input_tokens', 0)} "
                            f"out={usage.get('output_tokens', 0)} "
                            f"total={usage.get('total_tokens', 0)}[/dim]"
                        )

            elif node_name == "tool_node":
                messages = state_update.get("messages", [])
                console.print("[magenta]Observation:[/magenta]")
                for msg in messages:
                    tool_name = getattr(msg, "name", "tool")
                    if hasattr(msg, "content") and msg.content:
                        content = str(msg.content)
                        if "===EVIDENCE===" in content:
                            content = content.split("===EVIDENCE===")[0].rstrip()
                        if len(content) > 300:
                            content = content[:300] + "..."
                        console.print(f"  [dim]← {tool_name}: {content}[/dim]")

            elif node_name == "match_scenarios":
                matched = state_update.get("matched_scenarios", [])
                console.print(
                    f"\n[bold magenta]── 场景规则匹配 ──[/bold magenta] "
                    f"命中 {len(matched)} 条"
                )

            elif node_name == "diagnose":
                messages = state_update.get("messages", [])
                console.print("\n[bold green]── 归因判断（diagnose）──[/bold green]")
                for msg in messages:
                    _collect_usage(msg, "diagnose")
                    usage = getattr(msg, "usage_metadata", None) or {}
                    if usage:
                        console.print(
                            f"[dim]tokens: in={usage.get('input_tokens', 0)} "
                            f"out={usage.get('output_tokens', 0)} "
                            f"total={usage.get('total_tokens', 0)}[/dim]"
                        )
                    if hasattr(msg, "content") and msg.content:
                        report = msg.content

            final_state.update(state_update)

    # 汇总 token
    total_in = sum(r["input"] for r in token_rounds)
    total_out = sum(r["output"] for r in token_rounds)
    total_all = sum(r["total"] for r in token_rounds) or (total_in + total_out)
    final_state["_token_stats"] = {
        "rounds": token_rounds,
        "total_input": total_in,
        "total_output": total_out,
        "total": total_all,
        "model": llm.model_name,
    }

    elapsed = time.time() - start_time

    # 输出报告
    report = ""
    for msg in reversed(final_state.get("messages", [])):
        if hasattr(msg, "content") and msg.content and len(msg.content) > 200:
            report = msg.content
            break

    if report:
        console.print("\n")
        console.print(
            Panel(Markdown(report), title="LLM 归因段", border_style="green")
        )

    # 用 report 模块渲染结构化完整报告（告警+checklist+evidence+matched+diagnose）
    report_path = save_report(final_state, output_dir="output", scenario_name=scenario_name)
    console.print(f"\n  结构化报告已保存: [cyan]{report_path}[/cyan]")

    # 统计
    evidence_count = len(final_state.get("evidence_pool", {}))
    matched_count = len(final_state.get("matched_scenarios", []))
    stats = final_state.get("_token_stats", {})
    console.print(
        f"\n[dim]耗时: {elapsed:.1f}s | "
        f"Evidence: {evidence_count} 条 | "
        f"匹配场景: {matched_count} 个[/dim]"
    )
    console.print("\n[bold]── Token 消耗明细 ──[/bold]")
    console.print(f"  模型: [cyan]{stats.get('model', '-')}[/cyan]")
    for r in stats.get("rounds", []):
        console.print(
            f"  {r['stage']:<20} in={r['input']:>6}  out={r['output']:>5}  "
            f"total={r['total']:>6}"
        )
    console.print(
        f"  [bold]合计[/bold]:              "
        f"in={stats.get('total_input', 0):>6}  "
        f"out={stats.get('total_output', 0):>5}  "
        f"total={stats.get('total', 0):>6}"
    )


if __name__ == "__main__":
    main()
