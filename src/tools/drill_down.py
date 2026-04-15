"""Tool: 维度下钻 — 对应原系统 generate_nvqos_reqbody_for_dimension_analysis()."""

from langchain_core.tools import tool

from src.data.simulator import DataSimulator

_simulator: DataSimulator | None = None


def set_simulator(sim: DataSimulator):
    global _simulator
    _simulator = sim


@tool
def drill_down(metric_name: str, dimension: str, start_time: int = 0, end_time: int = 3600) -> str:
    """按维度下钻分析指标变化来源。当你需要找出哪个维度值贡献了主要变化时使用。

    输入:
        metric_name: 指标名称
        dimension: 下钻维度，如 region(地区)、isp(运营商)、resolution(分辨率)、codec(编码器)、cdn_node(CDN节点)、phase(耗时阶段)
        start_time: 起始时间戳
        end_time: 结束时间戳

    输出: 各维度值在 t1/t2 时刻的值、变化量和贡献占比。
    """
    results = _simulator.drill_down(metric_name, dimension, (start_time, end_time))

    if not results:
        dims = _simulator.get_available_dimensions()
        return f"维度 {dimension} 无数据。可用维度: {dims}"

    lines = [f"按 [{dimension}] 维度下钻分析 [{metric_name}]:"]
    for d in sorted(results, key=lambda x: abs(x.delta), reverse=True):
        direction = "↓" if d.delta < 0 else "↑"
        lines.append(
            f"  {d.dimension_value}: "
            f"t1={d.t1_value} → t2={d.t2_value}, "
            f"变化={d.delta:+.2f} {direction}, "
            f"贡献占比={d.contribution_ratio:.1f}%"
        )

    return "\n".join(lines)
