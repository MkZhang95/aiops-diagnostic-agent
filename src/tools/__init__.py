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
    """Create tools bound to one diagnostic data source.

    Each call returns fresh tool instances that close over the provided simulator,
    avoiding module-level global state across concurrent diagnostic runs.
    """
    return [
        query_metric.make_query_metric_tool(simulator),
        query_logs.make_query_logs_tool(simulator),
        query_events.make_query_events_tool(simulator),
        decompose_metric.make_decompose_metric_tool(simulator),
        decompose_formula.make_decompose_formula_tool(simulator),
        analyze_correlation.make_analyze_correlation_tool(simulator),
        match_events.make_match_events_tool(simulator),
    ]
