"""Tool Q2: 日志查询.

相比原 search_logs，增加 level 过滤（ERROR/WARN/ALL）和 source 过滤。
返回文本 + 证据 JSON，证据 JSON 中 `error_count` / `has_errors` 等字段可被规则引擎直接使用。
"""

import json
from collections import Counter

from langchain_core.tools import tool

from src.data.simulator import DataSimulator


def _evidence_block(payload: dict) -> str:
    return "\n\n===EVIDENCE===\n" + json.dumps(payload, ensure_ascii=False)


def make_query_logs_tool(simulator: DataSimulator):
    """Create a query_logs tool bound to one diagnostic data source."""

    @tool("query_logs")
    def query_logs(keyword: str = "", level: str = "ERROR", source: str = "") -> str:
        """查询日志。当你需要查看异常日志作为根因证据时使用。

        输入:
            keyword: 搜索关键词（如 timeout, error, CDN 节点名）；为空则不按关键词过滤
            level: 日志级别，ERROR / WARN / INFO / ALL（默认 ERROR）
            source: 可选，按来源模块过滤（如 cdn-gateway / client-crash-report）

        输出: 匹配日志列表 + 错误条数、来源分布等摘要。
        """
        # simulator.search_logs 当 keyword 空字符串时会回退到全量匹配，逻辑交给它
        logs = simulator.search_logs(keyword or "", 0, 3600, level)

        if source:
            logs = [log for log in logs if source.lower() in log.source.lower()]

        if not logs:
            payload = {
                "keyword": keyword,
                "level": level,
                "source": source,
                "count": 0,
                "error_count": 0,
                "has_errors": False,
            }
            hint = f"关键词='{keyword}'" if keyword else "无关键词"
            return f"未找到匹配日志 ({hint}, 级别={level})。" + _evidence_block(payload)

        lines = [f"日志查询结果 (关键词='{keyword or '*'}', 级别={level}):"]
        for log in logs:
            lines.append(
                f"  [{log.level}] {log.message}\n"
                f"         来源: {log.source} | 区域: {log.region}"
            )
        lines.append(f"\n  共 {len(logs)} 条")

        level_counter = Counter(log.level for log in logs)
        source_counter = Counter(log.source for log in logs)
        error_count = level_counter.get("ERROR", 0)

        payload = {
            "keyword": keyword,
            "level": level,
            "source": source,
            "count": len(logs),
            "error_count": error_count,
            "has_errors": error_count > 0,
            "levels": dict(level_counter),
            "sources": list(source_counter.keys()),
        }
        return "\n".join(lines) + _evidence_block(payload)

    return query_logs
