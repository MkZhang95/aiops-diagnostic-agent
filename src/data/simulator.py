"""Data simulator that provides mock data for agent tools.

Loads pre-built scenario data and exposes query interfaces
that mimic real monitoring system APIs.
"""

from .models import (
    ChangeEvent,
    DimensionBreakdown,
    LogEntry,
    MetricDataPoint,
    TimeSeriesData,
)
from .scenarios import get_scenario


class DataSimulator:
    """Simulates monitoring data sources for a given scenario."""

    def __init__(self, scenario_name: str):
        self._scenario = get_scenario(scenario_name)
        self._scenario_name = scenario_name

    @property
    def alert(self) -> dict:
        return self._scenario["alert"]

    def query_metrics(
        self,
        metric_name: str,
        start_time: int,
        end_time: int,
        filters: dict | None = None,
    ) -> TimeSeriesData:
        """Query metric time series data.

        Corresponds to original system's get_data_from_nvqos().
        """
        metrics = self._scenario.get("metrics", {})

        if metric_name not in metrics:
            available = list(metrics.keys())
            return TimeSeriesData(
                metric_name=metric_name,
                t1_value=0, t2_value=0, delta=0, delta_ratio=0,
                data_points=[],
            )

        m = metrics[metric_name]
        data_points = [
            MetricDataPoint(timestamp=start_time + ts, value=val, metric_name=metric_name)
            for ts, val in m.get("time_series", [])
        ]

        return TimeSeriesData(
            metric_name=metric_name,
            data_points=data_points,
            t1_value=m["t1_value"],
            t2_value=m["t2_value"],
            delta=m["delta"],
            delta_ratio=m["delta_ratio"],
        )

    def drill_down(
        self,
        metric_name: str,
        dimension: str,
        time_range: tuple[int, int],
    ) -> list[DimensionBreakdown]:
        """Drill down metric by dimension.

        Corresponds to original system's generate_nvqos_reqbody_for_dimension_analysis().
        """
        drill_data = self._scenario.get("drill_down", {})

        if dimension not in drill_data:
            return []

        return [
            DimensionBreakdown(
                dimension_name=dimension,
                dimension_value=d["dimension_value"],
                t1_value=d["t1_value"],
                t2_value=d["t2_value"],
                delta=d["delta"],
                contribution_ratio=d["contribution_ratio"],
            )
            for d in drill_data[dimension]
        ]

    def search_logs(
        self,
        keyword: str,
        start_time: int,
        end_time: int,
        severity: str = "ERROR",
    ) -> list[LogEntry]:
        """Search logs by keyword and severity.

        Corresponds to original system's Kibana log search.
        """
        logs = self._scenario.get("logs", [])
        keyword_lower = keyword.lower()

        results = []
        for log in logs:
            severity_match = severity == "ALL" or log["level"] == severity or (
                severity == "ERROR" and log["level"] in ("ERROR", "WARN")
            )
            keyword_match = (
                keyword_lower in log["message"].lower()
                or keyword_lower in log.get("source", "").lower()
                or keyword_lower in log.get("region", "").lower()
            )

            if severity_match and keyword_match:
                results.append(LogEntry(**log))

        # If no keyword match, return all logs matching severity
        if not results:
            results = [
                LogEntry(**log) for log in logs
                if severity == "ALL" or log["level"] == severity or (
                    severity == "ERROR" and log["level"] in ("ERROR", "WARN")
                )
            ]

        return results

    def get_changes(
        self,
        start_time: int,
        end_time: int,
        service_name: str | None = None,
    ) -> list[ChangeEvent]:
        """Get change events in time range.

        Corresponds to original system's change event analysis.
        """
        changes = self._scenario.get("changes", [])
        results = []

        for ch in changes:
            if service_name and service_name not in ch.get("affected_services", []):
                continue
            results.append(ChangeEvent(**ch))

        return results

    def get_available_metrics(self) -> list[str]:
        """List available metric names for this scenario."""
        return list(self._scenario.get("metrics", {}).keys())

    def get_available_dimensions(self) -> list[str]:
        """List available drill-down dimensions for this scenario."""
        return list(self._scenario.get("drill_down", {}).keys())
