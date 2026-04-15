"""AIOps Diagnostic Agent CLI entry point."""

import argparse
import json
import os
import time
from datetime import datetime

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from src.agent import build_graph
from src.data import DataSimulator, list_scenarios
from src.llm import get_llm
from src.tools import get_all_tools

console = Console()


def main():
    parser = argparse.ArgumentParser(description="AIOps Diagnostic Agent")
    parser.add_argument("--alert", type=str, help="告警 JSON 文件路径")
    parser.add_argument("--scenario", type=str, help="预置场景名称")
    parser.add_argument("--llm", type=str, default=None, help="LLM provider: claude / openai")
    parser.add_argument("--max-steps", type=int, default=15, help="最大推理步骤数")
    parser.add_argument("--verbose", action="store_true", help="详细模式")
    args = parser.parse_args()

    console.print(Panel("[bold]AIOps Diagnostic Agent v0.1.0[/bold]", style="blue"))

    # Determine scenario / alert
    if args.scenario:
        scenario_name = args.scenario
    elif args.alert:
        scenario_name = None
    else:
        # Interactive menu
        scenarios = list_scenarios()
        console.print("\n[bold]选择诊断场景:[/bold]")
        for i, name in enumerate(scenarios, 1):
            console.print(f"  {i}. {name}")
        choice = input("\n请输入编号 (默认 1): ").strip() or "1"
        scenario_name = scenarios[int(choice) - 1]

    # Load alert and simulator
    if scenario_name:
        simulator = DataSimulator(scenario_name)
        alert = simulator.alert
        console.print(f"  场景: [cyan]{scenario_name}[/cyan]")
    else:
        with open(args.alert) as f:
            alert = json.load(f)
        simulator = DataSimulator("play_success_rate_drop")  # fallback

    console.print(Panel(
        f"[bold red]告警: {alert.get('description', alert['metric_name'])}[/bold red]\n"
        f"指标: {alert['metric_name']}  "
        f"当前值: {alert.get('current_value', 'N/A')}  "
        f"基线值: {alert.get('baseline_value', 'N/A')}  "
        f"严重级别: {alert.get('severity', 'N/A')}",
        title="🚨 告警信息",
    ))

    # Build agent with tools
    llm = get_llm(provider=args.llm)
    console.print(f"  使用模型: [cyan]{llm.model_name}[/cyan]")

    tools = get_all_tools(simulator)
    console.print(f"  已加载工具: {len(tools)} 个")

    graph = build_graph(llm, tools=tools)

    # Run
    console.print("\n[bold]开始诊断...[/bold]\n")
    start_time = time.time()

    result = graph.invoke({
        "alert": alert,
        "messages": [],
        "current_step": 0,
        "max_steps": args.max_steps,
        "evidence": [],
        "root_causes": [],
        "report": "",
        "status": "running",
    })
    elapsed = time.time() - start_time

    # Output report
    report = result.get("report", "")
    if report:
        console.print("\n")
        console.print(Panel(Markdown(report), title="📊 归因诊断报告", border_style="green"))

        # Save report
        os.makedirs("output", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"output/report_{timestamp}.md"
        with open(report_path, "w") as f:
            f.write(report)
        console.print(f"\n  报告已保存: [cyan]{report_path}[/cyan]")

    console.print(
        f"\n[dim]总耗时: {elapsed:.1f}s | "
        f"步骤数: {result.get('current_step', 0)} | "
        f"状态: {result.get('status')}[/dim]"
    )


if __name__ == "__main__":
    main()
