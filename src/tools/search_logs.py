"""Tool: 日志搜索 — 对应原系统 Kibana 日志分析."""

from langchain_core.tools import tool

from src.data.simulator import DataSimulator

_simulator: DataSimulator | None = None


def set_simulator(sim: DataSimulator):
    global _simulator
    _simulator = sim


@tool
def search_logs(keyword: str, start_time: int = 0, end_time: int = 3600, severity: str = "ERROR") -> str:
    """搜索与告警相关的日志。当你需要寻找异常日志作为根因证据时使用。

    输入:
        keyword: 搜索关键词，如 timeout, error, failed, CDN 节点名等
        start_time: 起始时间戳
        end_time: 结束时间戳
        severity: 日志级别过滤，ERROR / WARN / INFO / ALL

    输出: 匹配的日志条目列表，包含时间、级别、消息、来源。
    """
    logs = _simulator.search_logs(keyword, start_time, end_time, severity)

    if not logs:
        return f"未找到包含关键词 '{keyword}' 的 {severity} 级别日志。"

    lines = [f"日志搜索结果 (关键词: '{keyword}', 级别: {severity}):"]
    for log in logs:
        lines.append(
            f"  [{log.level}] {log.message}\n"
            f"         来源: {log.source} | 区域: {log.region}"
        )

    lines.append(f"\n  共找到 {len(logs)} 条日志")
    return "\n".join(lines)
