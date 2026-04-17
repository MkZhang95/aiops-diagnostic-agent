"""Tool Q1: 统一指标查询.

合并原 query_metrics / drill_down / compare_time_points 三个工具，通过参数区分查询模式:
  - 整体查询:   query_metric(metric="play_success_rate")
  - 维度下钻:   query_metric(metric="play_success_rate", dimension="isp")
  - 条件过滤:   query_metric(metric="play_success_rate", filters="region=cn-south")

返回同时给人类读的文本 + `===EVIDENCE===` JSON 证据块。
"""

import json

from langchain_core.tools import tool

from src.data.simulator import DataSimulator

_simulator: DataSimulator | None = None


def set_simulator(sim: DataSimulator):
    global _simulator
    _simulator = sim


def _evidence_block(payload: dict) -> str:
    return "\n\n===EVIDENCE===\n" + json.dumps(payload, ensure_ascii=False)


@tool
def query_metric(metric: str, dimension: str = "", filters: str = "") -> str:
    """查询指标数据，三种模式自动路由：

    1. 整体查询: query_metric(metric="play_success_rate")
       返回 t1/t2/delta/rate_of_change/trend
    2. 维度下钻: query_metric(metric="play_success_rate", dimension="isp")
       返回各维度值的 t1/t2/delta 以及 top1_contribution
    3. 条件过滤: query_metric(metric="play_success_rate", filters="region=cn-south")
       过滤到指定维度值下的数据

    输入:
        metric: 指标名（如 play_success_rate, cdn_error_rate）
        dimension: 可选，下钻维度（如 isp / region / app_version）
        filters: 可选，过滤条件，格式 "key=value"，多个用逗号分隔
    """
    if _simulator is None:
        return "错误：数据模拟器未初始化。" + _evidence_block({})

    if dimension:
        return _drill(metric, dimension)
    if filters:
        return _filter(metric, filters)
    return _overall(metric)


def _overall(metric: str) -> str:
    data = _simulator.query_metrics(metric, 0, 3600)
    if not data.data_points:
        payload = {"metric": metric, "found": False}
        return (
            f"未找到指标 {metric} 的数据。可用指标: {_simulator.get_available_metrics()}"
            + _evidence_block(payload)
        )

    rate_of_change = (data.delta / data.t1_value) if data.t1_value else 0.0
    trend_seq = [p.value for p in data.data_points]
    trend_str = " → ".join(f"{v}" for v in trend_seq[-6:])

    if len(trend_seq) >= 3:
        tail = trend_seq[-3:]
        if all(tail[i] <= tail[i - 1] for i in range(1, len(tail))):
            trend = "declining"
        elif all(tail[i] >= tail[i - 1] for i in range(1, len(tail))):
            trend = "increasing"
        else:
            trend = "fluctuating"
    else:
        trend = "unknown"

    direction = "下降" if data.delta < 0 else "上升"
    text = (
        f"指标 [{metric}] 整体查询:\n"
        f"  基线 t1 = {data.t1_value}\n"
        f"  当前 t2 = {data.t2_value}\n"
        f"  变化   = {data.delta:+.2f} ({direction}, 变化率 {data.delta_ratio:+.2f}%)\n"
        f"  走势   = {trend_str}\n"
        f"  趋势判断 = {trend}"
    )
    payload = {
        "metric": metric,
        "found": True,
        "t1_value": data.t1_value,
        "t2_value": data.t2_value,
        "delta": round(data.delta, 4),
        "rate_of_change": round(rate_of_change, 4),
        "delta_ratio_pct": round(data.delta_ratio, 2),
        "direction": "down" if data.delta < 0 else "up",
        "trend": trend,
    }
    return text + _evidence_block(payload)


def _drill(metric: str, dimension: str) -> str:
    results = _simulator.drill_down(metric, dimension, (0, 3600))
    if not results:
        payload = {
            "metric": metric,
            "dimension": dimension,
            "found": False,
            "available_dimensions": _simulator.get_available_dimensions(),
        }
        return (
            f"指标 {metric} 在维度 {dimension} 无下钻数据。"
            f"可用维度: {payload['available_dimensions']}"
            + _evidence_block(payload)
        )

    sorted_results = sorted(results, key=lambda x: abs(x.delta), reverse=True)
    lines = [f"指标 [{metric}] 按 [{dimension}] 下钻:"]
    breakdown = []
    for d in sorted_results:
        arrow = "↓" if d.delta < 0 else "↑"
        lines.append(
            f"  {d.dimension_value}: {d.t1_value} → {d.t2_value} "
            f"(Δ{d.delta:+.2f} {arrow}, 贡献 {d.contribution_ratio:.1f}%)"
        )
        breakdown.append({
            "name": d.dimension_value,
            "t1": d.t1_value,
            "t2": d.t2_value,
            "delta": round(d.delta, 4),
            "ratio_pct": round(d.contribution_ratio, 2),
        })

    top1 = breakdown[0]
    payload = {
        "metric": metric,
        "dimension": dimension,
        "found": True,
        "breakdown": breakdown,
        "top1_name": top1["name"],
        "top1_contribution": round(top1["ratio_pct"] / 100.0, 4),
        "dimension_count": len(breakdown),
    }
    return "\n".join(lines) + _evidence_block(payload)


def _filter(metric: str, filters: str) -> str:
    filter_dict = {}
    for token in filters.split(","):
        token = token.strip()
        if "=" in token:
            k, v = token.split("=", 1)
            filter_dict[k.strip()] = v.strip()

    if not filter_dict:
        return f"过滤条件格式错误: {filters}" + _evidence_block({"found": False})

    matches = []
    for dim_key, expected in filter_dict.items():
        for d in _simulator.drill_down(metric, dim_key, (0, 3600)):
            if d.dimension_value.lower() == expected.lower():
                matches.append({
                    "dimension": dim_key,
                    "value": d.dimension_value,
                    "t1": d.t1_value,
                    "t2": d.t2_value,
                    "delta": round(d.delta, 4),
                    "ratio_pct": round(d.contribution_ratio, 2),
                })

    if not matches:
        payload = {"metric": metric, "filters": filter_dict, "found": False}
        return (
            f"指标 {metric} 在过滤条件 {filters} 下无数据。"
            + _evidence_block(payload)
        )

    lines = [f"指标 [{metric}] 过滤查询 ({filters}):"]
    for m in matches:
        lines.append(
            f"  {m['dimension']}={m['value']}: "
            f"{m['t1']} → {m['t2']} (Δ{m['delta']:+.2f}, 贡献 {m['ratio_pct']:.1f}%)"
        )

    payload = {
        "metric": metric,
        "filters": filter_dict,
        "found": True,
        "results": matches,
    }
    return "\n".join(lines) + _evidence_block(payload)
