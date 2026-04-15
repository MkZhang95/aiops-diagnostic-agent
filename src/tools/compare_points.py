"""Tool: 两点对比 — 对应原系统 query_data_for_two_points()."""

from langchain_core.tools import tool

from src.data.simulator import DataSimulator

_simulator: DataSimulator | None = None


def set_simulator(sim: DataSimulator):
    global _simulator
    _simulator = sim


@tool
def compare_time_points(metric_name: str, t1: int = 0, t2: int = 3600, dimensions: str = "") -> str:
    """对比两个时间点的指标数据并按维度拆解。当你需要综合对比指标在不同时间点的表现时使用。

    输入:
        metric_name: 指标名称
        t1: 基线时间点
        t2: 当前时间点
        dimensions: 需要拆解的维度列表（逗号分隔），如 "region,isp"

    输出: 指标总体变化 + 各维度的变化对比。
    """
    # 总体指标
    metrics = _simulator.query_metrics(metric_name, t1, t2)
    lines = [
        f"两点对比分析 [{metric_name}]:",
        f"  总体: t1={metrics.t1_value} → t2={metrics.t2_value}, "
        f"变化={metrics.delta:+.2f} ({metrics.delta_ratio:+.1f}%)",
    ]

    # 按维度拆解
    dim_list = [d.strip() for d in dimensions.split(",") if d.strip()] if dimensions else []

    if not dim_list:
        dim_list = _simulator.get_available_dimensions()
        lines.append(f"\n  自动选择可用维度: {dim_list}")

    for dim in dim_list:
        breakdowns = _simulator.drill_down(metric_name, dim, (t1, t2))
        if breakdowns:
            lines.append(f"\n  [{dim}] 维度拆解:")
            for b in sorted(breakdowns, key=lambda x: abs(x.delta), reverse=True):
                lines.append(
                    f"    {b.dimension_value}: {b.t1_value} → {b.t2_value} "
                    f"(Δ{b.delta:+.2f}, 贡献{b.contribution_ratio:.1f}%)"
                )

    return "\n".join(lines)
