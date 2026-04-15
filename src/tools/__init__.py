"""Tool registry and simulator injection."""

from langchain_core.tools import BaseTool

from src.data.simulator import DataSimulator

from . import check_changes, compare_points, drill_down, query_metrics, search_logs
from .concentration import check_concentration
from .contribution import compute_contribution


def get_all_tools(simulator: DataSimulator) -> list[BaseTool]:
    """Get all tools with simulator injected.

    Args:
        simulator: DataSimulator instance providing mock data.

    Returns:
        List of LangChain tools ready for agent use.
    """
    # Inject simulator into tools that need it
    query_metrics.set_simulator(simulator)
    drill_down.set_simulator(simulator)
    search_logs.set_simulator(simulator)
    check_changes.set_simulator(simulator)
    compare_points.set_simulator(simulator)

    return [
        query_metrics.query_metrics,
        drill_down.drill_down,
        compute_contribution,
        check_concentration,
        search_logs.search_logs,
        check_changes.check_changes,
        compare_points.compare_time_points,
    ]
