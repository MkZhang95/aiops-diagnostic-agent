"""Tool: 变更事件检查 — 对应原系统变更事件分析."""

from langchain_core.tools import tool

from src.data.simulator import DataSimulator

_simulator: DataSimulator | None = None


def set_simulator(sim: DataSimulator):
    global _simulator
    _simulator = sim


@tool
def check_changes(start_time: int = 0, end_time: int = 3600, service_name: str = "") -> str:
    """检查告警时间窗口内的变更事件（代码发布、配置变更、扩缩容等）。当你需要寻找与告警时间关联的变更操作时使用。

    输入:
        start_time: 起始时间戳
        end_time: 结束时间戳
        service_name: 可选，过滤特定服务的变更

    输出: 变更事件列表，包含变更类型、描述、影响服务。
    """
    svc = service_name if service_name else None
    changes = _simulator.get_changes(start_time, end_time, svc)

    if not changes:
        return f"在指定时间窗口内未发现变更事件。"

    lines = ["变更事件检查结果:"]
    for ch in changes:
        lines.append(
            f"  [{ch.change_type.upper()}] {ch.description}\n"
            f"         执行者: {ch.author} | 影响服务: {', '.join(ch.affected_services)}"
        )

    lines.append(f"\n  共发现 {len(changes)} 个变更事件")
    return "\n".join(lines)
