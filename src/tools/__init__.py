"""Tool registry and simulator injection.

工具按功能分两类：
  Query 类（数据查询）: query_metric / query_logs / query_events
  Compute 类（基于查询结果的计算）: decompose_metric / decompose_formula /
                                    analyze_correlation / match_events
"""

from langchain_core.tools import BaseTool

from src.data.simulator import DataSimulator

from . import (
    analyze_correlation,
    decompose_formula,
    decompose_metric,
    match_events,
    query_events,
    query_logs,
    query_metric,
)


def get_all_tools(simulator: DataSimulator) -> list[BaseTool]:
    """Get all tools with simulator injected."""
    for mod in (
        query_metric,
        query_logs,
        query_events,
        decompose_metric,
        decompose_formula,
        analyze_correlation,
        match_events,
    ):
        mod.set_simulator(simulator)

    return [
        query_metric.query_metric,
        query_logs.query_logs,
        query_events.query_events,
        decompose_metric.decompose_metric,
        decompose_formula.decompose_formula,
        analyze_correlation.analyze_correlation,
        match_events.match_events,
    ]
