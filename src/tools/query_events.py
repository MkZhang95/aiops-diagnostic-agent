"""Tool Q3: 事件/变更查询.

相比原 check_changes，增加 event_type 过滤（deployment/config/scaling），
并在证据 JSON 中拆分 has_release / has_config_change / has_deployment 等布尔位，便于规则直接使用。
"""

import json
from collections import Counter

from langchain_core.tools import tool

from src.data.simulator import DataSimulator


def _evidence_block(payload: dict) -> str:
    return "\n\n===EVIDENCE===\n" + json.dumps(payload, ensure_ascii=False)


_RELEASE_KEYWORDS = ("发版", "release", "deploy", "上线", "灰度", "发布")


def make_query_events_tool(simulator: DataSimulator):
    """Create a query_events tool bound to one diagnostic data source."""

    @tool("query_events")
    def query_events(event_type: str = "", service: str = "") -> str:
        """查询告警时间窗口内的变更事件（代码发布、配置变更、扩缩容等）。

        输入:
            event_type: 可选，按事件类型过滤（deployment / config / scaling）
            service: 可选，按服务名过滤

        输出: 事件列表 + 类型分布、是否包含发版/配置变更等。
        """
        changes = simulator.get_changes(0, 3600, service or None)
        if event_type:
            changes = [ch for ch in changes if ch.change_type == event_type]

        if not changes:
            payload = {
                "event_type_filter": event_type,
                "service_filter": service,
                "count": 0,
                "has_changes": False,
                "has_config_change": False,
                "has_deployment": False,
                "has_release": False,
            }
            return "指定条件下未发现变更事件。" + _evidence_block(payload)

        lines = ["变更事件查询结果:"]
        for ch in changes:
            lines.append(
                f"  [{ch.change_type.upper()}] {ch.description}\n"
                f"         执行者: {ch.author} | 影响服务: {', '.join(ch.affected_services)}"
            )
        lines.append(f"\n  共 {len(changes)} 个事件")

        type_counter = Counter(ch.change_type for ch in changes)
        has_deployment = type_counter.get("deployment", 0) > 0
        has_release = has_deployment or any(
            any(kw in ch.description.lower() for kw in _RELEASE_KEYWORDS)
            for ch in changes
        )

        payload = {
            "event_type_filter": event_type,
            "service_filter": service,
            "count": len(changes),
            "has_changes": True,
            "change_types": dict(type_counter),
            "has_config_change": type_counter.get("config", 0) > 0,
            "has_deployment": has_deployment,
            "has_release": has_release,
        }
        return "\n".join(lines) + _evidence_block(payload)

    return query_events
