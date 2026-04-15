"""场景规则匹配引擎 — 从 Evidence Pool 取数据，匹配结构化条件"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import yaml


@dataclass
class MatchedRule:
    """匹配到的规则"""

    scenario: str
    scenario_name: str
    rule_id: str
    rule_name: str
    confidence: str  # high / medium / low
    conclusion: str
    suggested_action: str
    match_score: float  # 0.0 ~ 1.0
    matched_conditions: list[str] = field(default_factory=list)
    unmatched_conditions: list[str] = field(default_factory=list)


class RuleMatcher:
    """场景规则匹配器

    从 Evidence Pool（dict[step_id, result]）中取数据，
    与 rules_*.yaml 中的结构化条件进行匹配。
    """

    # 置信度权重，用于排序
    CONFIDENCE_WEIGHT = {"high": 3, "medium": 2, "low": 1}

    def __init__(self, runbook_dir: str = "runbooks"):
        self.runbook_dir = runbook_dir

    def match_all_scenarios(
        self, metric: str, evidence_pool: dict[str, Any]
    ) -> list[MatchedRule]:
        """匹配指定指标下的所有场景规则

        Args:
            metric: 指标名称
            evidence_pool: 共享结果池，key 为 step_id，value 为工具返回结果

        Returns:
            匹配到的规则列表，按置信度降序排列
        """
        rule_files = self._get_rule_files(metric)
        all_matched: list[MatchedRule] = []

        for rule_file in rule_files:
            scenario_rules = self._load_rule_file(rule_file)
            if not scenario_rules:
                continue

            scenario_id = scenario_rules.get("scenario", "")
            scenario_name = scenario_rules.get("display_name", scenario_id)

            # 检查该场景所需的 evidence 是否已采集
            required = scenario_rules.get("required_evidence", [])
            missing = [eid for eid in required if eid not in evidence_pool]
            if missing:
                # 缺少必要数据，跳过该场景
                continue

            # 逐条匹配规则
            for rule in scenario_rules.get("rules", []):
                matched_rule = self._evaluate_rule(
                    rule, scenario_id, scenario_name, evidence_pool
                )
                if matched_rule and matched_rule.match_score > 0:
                    all_matched.append(matched_rule)

        # 按置信度降序 + 匹配分数降序排列
        all_matched.sort(
            key=lambda r: (
                self.CONFIDENCE_WEIGHT.get(r.confidence, 0),
                r.match_score,
            ),
            reverse=True,
        )
        return all_matched

    def _evaluate_rule(
        self,
        rule: dict,
        scenario_id: str,
        scenario_name: str,
        evidence_pool: dict[str, Any],
    ) -> MatchedRule | None:
        """评估单条规则是否匹配

        Args:
            rule: 规则定义（来自 YAML）
            scenario_id: 场景 ID
            scenario_name: 场景显示名
            evidence_pool: 共享结果池

        Returns:
            MatchedRule（即使部分匹配也返回），或 None
        """
        conditions = rule.get("conditions", [])
        if not conditions:
            return None

        matched_conditions: list[str] = []
        unmatched_conditions: list[str] = []

        for cond in conditions:
            desc = cond.get("description", "")
            if self._check_condition(cond, evidence_pool):
                matched_conditions.append(desc)
            else:
                unmatched_conditions.append(desc)

        total = len(conditions)
        score = len(matched_conditions) / total if total > 0 else 0

        # 只有全部条件满足才算真正匹配
        # 但部分匹配也返回，方便报告中展示"接近但未完全匹配"的场景
        return MatchedRule(
            scenario=scenario_id,
            scenario_name=scenario_name,
            rule_id=rule.get("id", ""),
            rule_name=rule.get("name", ""),
            confidence=rule.get("confidence", "low") if score == 1.0 else "low",
            conclusion=rule.get("conclusion", ""),
            suggested_action=rule.get("suggested_action", ""),
            match_score=score,
            matched_conditions=matched_conditions,
            unmatched_conditions=unmatched_conditions,
        )

    def _check_condition(
        self, condition: dict, evidence_pool: dict[str, Any]
    ) -> bool:
        """检查单个结构化条件是否满足

        条件格式:
            step: evidence_pool 中的 step_id
            field: 要检查的字段名
            op: 比较操作符 (>, <, >=, <=, ==, !=)
            value: 期望值
        """
        step_id = condition.get("step")
        field_name = condition.get("field")
        op = condition.get("op")
        expected_value = condition.get("value")

        if not all([step_id, field_name, op]):
            return False

        evidence = evidence_pool.get(step_id)
        if evidence is None:
            return False

        # 从 evidence 中提取字段值
        # evidence 结构: {"tool": ..., "args": ..., "result": ..., "parsed": {...}}
        actual_value = self._extract_field(evidence, field_name)
        if actual_value is None:
            return False

        return self._compare(actual_value, op, expected_value)

    def _extract_field(self, evidence: dict, field_name: str) -> Any:
        """从 evidence 记录中提取字段值

        支持从 parsed（解析后的结构化数据）或 result（原始结果）中提取。
        使用 dot notation 支持嵌套字段，如 "summary.gini"
        """
        # 优先从 parsed 字段取（结构化解析结果）
        parsed = evidence.get("parsed", {})
        value = self._get_nested(parsed, field_name)
        if value is not None:
            return value

        # 其次从 result 取
        result = evidence.get("result", {})
        if isinstance(result, dict):
            value = self._get_nested(result, field_name)
            if value is not None:
                return value

        return None

    @staticmethod
    def _get_nested(data: dict, key: str) -> Any:
        """支持 dot notation 的嵌套字典取值"""
        if not isinstance(data, dict):
            return None
        parts = key.split(".")
        current = data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    @staticmethod
    def _compare(actual: Any, op: str, expected: Any) -> bool:
        """比较操作"""
        try:
            # 尝试数值比较
            if isinstance(expected, (int, float)):
                actual = float(actual)
            elif isinstance(expected, bool):
                if isinstance(actual, str):
                    actual = actual.lower() in ("true", "1", "yes")
                else:
                    actual = bool(actual)

            if op == ">":
                return actual > expected
            elif op == "<":
                return actual < expected
            elif op == ">=":
                return actual >= expected
            elif op == "<=":
                return actual <= expected
            elif op == "==":
                return actual == expected
            elif op == "!=":
                return actual != expected
            else:
                return False
        except (ValueError, TypeError):
            return False

    def _get_rule_files(self, metric: str) -> list[str]:
        """获取指标下所有规则文件"""
        import glob

        metric_dir = os.path.join(self.runbook_dir, metric)
        if not os.path.exists(metric_dir):
            return []
        return sorted(glob.glob(os.path.join(metric_dir, "rules_*.yaml")))

    def _load_rule_file(self, path: str) -> dict | None:
        """加载规则 YAML 文件"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception:
            return None

    def format_match_results(self, matched: list[MatchedRule]) -> str:
        """将匹配结果格式化为报告文本"""
        if not matched:
            return "未匹配到任何已知场景，建议人工排查。"

        lines = ["## 场景匹配结果\n"]

        # 完全匹配的规则
        full_matches = [r for r in matched if r.match_score == 1.0]
        partial_matches = [r for r in matched if 0 < r.match_score < 1.0]

        if full_matches:
            lines.append("### ✅ 匹配到的故障场景\n")
            for r in full_matches:
                lines.append(f"**{r.scenario_name} — {r.rule_name}**")
                lines.append(f"- 置信度: {r.confidence}")
                lines.append(f"- 结论: {r.conclusion}")
                lines.append(f"- 建议操作: {r.suggested_action}")
                lines.append(f"- 匹配条件:")
                for c in r.matched_conditions:
                    lines.append(f"  - ✅ {c}")
                lines.append("")

        if partial_matches:
            lines.append("### ⚠️ 部分匹配的场景（供参考）\n")
            for r in partial_matches:
                lines.append(
                    f"**{r.scenario_name} — {r.rule_name}** "
                    f"(匹配度: {r.match_score:.0%})"
                )
                for c in r.matched_conditions:
                    lines.append(f"  - ✅ {c}")
                for c in r.unmatched_conditions:
                    lines.append(f"  - ❌ {c}")
                lines.append("")

        return "\n".join(lines)
