"""Tool: 指标查询 — 对应原系统 get_data_from_nvqos()."""

from langchain_core.tools import tool

from src.data.simulator import DataSimulator

_simulator: DataSimulator | None = None


def set_simulator(sim: DataSimulator):
    global _simulator
    _simulator = sim


@tool
def query_metrics(metric_name: str, start_time: int = 0, end_time: int = 3600) -> str:
    """查询指标时间序列数据。当你需要了解某个指标的整体变化趋势时使用。

    输入:
        metric_name: 指标名称，如 play_success_rate, buffering_rate, first_frame_latency_p95
        start_time: 查询起始时间戳
        end_time: 查询结束时间戳

    输出: 指标的基线值、当前值、变化量、变化率，以及时间序列走势。
    """
    data = _simulator.query_metrics(metric_name, start_time, end_time)

    if not data.data_points:
        return f"未找到指标 {metric_name} 的数据。可用指标: {_simulator.get_available_metrics()}"

    direction = "下降" if data.delta < 0 else "上升"
    trend = " → ".join(f"{p.value}" for p in data.data_points[-4:])

    return (
        f"指标查询结果 [{metric_name}]:\n"
        f"  基线值 (t1): {data.t1_value}\n"
        f"  当前值 (t2): {data.t2_value}\n"
        f"  变化量: {data.delta:+.2f} ({direction})\n"
        f"  变化率: {data.delta_ratio:+.1f}%\n"
        f"  近期走势: {trend}\n"
        f"  数据点数: {len(data.data_points)}"
    )
