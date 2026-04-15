"""知识模块单元测试"""

import os
import tempfile
import pytest
import yaml

from src.knowledge.runbook_loader import RunbookLoader, ChecklistItem
from src.knowledge.rule_matcher import RuleMatcher, MatchedRule


# ============================================================
# RunbookLoader 测试
# ============================================================


@pytest.fixture
def temp_runbook_dir():
    """创建临时 runbook 目录结构"""
    with tempfile.TemporaryDirectory() as tmpdir:
        metric_dir = os.path.join(tmpdir, "test_metric")
        os.makedirs(metric_dir)

        # _meta.yaml
        meta = {
            "metric": "test_metric",
            "display_name": "测试指标",
            "description": "测试用指标",
            "related_metrics": ["metric_a", "metric_b"],
        }
        with open(os.path.join(metric_dir, "_meta.yaml"), "w") as f:
            yaml.dump(meta, f, allow_unicode=True)

        # analysis_plan.yaml
        plan = {
            "metric": "test_metric",
            "steps": [
                {
                    "id": "step_1",
                    "name": "步骤1",
                    "priority": "must",
                    "action": "query_metrics",
                    "params": {"metric": "test_metric"},
                    "depends_on": [],
                    "used_by": ["scenario_a"],
                    "description": "查询整体趋势",
                },
                {
                    "id": "step_2",
                    "name": "步骤2",
                    "priority": "must",
                    "action": "drill_down",
                    "params": {"metric": "test_metric", "dimension": "isp"},
                    "depends_on": ["step_1"],
                    "used_by": ["scenario_a", "scenario_b"],
                    "description": "运营商下钻",
                },
                {
                    "id": "step_3",
                    "name": "步骤3",
                    "priority": "should",
                    "action": "check_changes",
                    "params": {},
                    "depends_on": [],
                    "used_by": ["scenario_a"],
                    "description": "查询变更",
                },
            ],
        }
        with open(os.path.join(metric_dir, "analysis_plan.yaml"), "w") as f:
            yaml.dump(plan, f, allow_unicode=True)

        # rules_scenario_a.yaml
        rules_a = {
            "scenario": "scenario_a",
            "display_name": "场景A",
            "required_evidence": ["step_1", "step_2"],
            "rules": [
                {
                    "id": "rule_1",
                    "name": "规则1",
                    "conditions": [
                        {
                            "step": "step_1",
                            "field": "rate_of_change",
                            "op": ">",
                            "value": 0.2,
                            "description": "变化率>20%",
                        },
                        {
                            "step": "step_2",
                            "field": "gini",
                            "op": ">",
                            "value": 0.7,
                            "description": "GINI>0.7",
                        },
                    ],
                    "confidence": "high",
                    "conclusion": "场景A结论",
                    "suggested_action": "建议操作A",
                },
            ],
        }
        with open(os.path.join(metric_dir, "rules_scenario_a.yaml"), "w") as f:
            yaml.dump(rules_a, f, allow_unicode=True)

        yield tmpdir


class TestRunbookLoader:
    def test_load_meta(self, temp_runbook_dir):
        loader = RunbookLoader(temp_runbook_dir)
        meta = loader.load_meta("test_metric")
        assert meta is not None
        assert meta.metric == "test_metric"
        assert meta.display_name == "测试指标"
        assert "metric_a" in meta.related_metrics

    def test_load_meta_not_found(self, temp_runbook_dir):
        loader = RunbookLoader(temp_runbook_dir)
        meta = loader.load_meta("nonexistent")
        assert meta is None

    def test_load_analysis_plan(self, temp_runbook_dir):
        loader = RunbookLoader(temp_runbook_dir)
        checklist = loader.load_analysis_plan("test_metric")
        assert len(checklist) == 3
        assert checklist[0].id == "step_1"
        assert checklist[0].priority == "must"
        assert checklist[0].status == "pending"
        assert checklist[1].depends_on == ["step_1"]

    def test_load_plan_not_found(self, temp_runbook_dir):
        loader = RunbookLoader(temp_runbook_dir)
        checklist = loader.load_analysis_plan("nonexistent")
        assert checklist == []

    def test_get_available_metrics(self, temp_runbook_dir):
        loader = RunbookLoader(temp_runbook_dir)
        metrics = loader.get_available_metrics()
        assert "test_metric" in metrics

    def test_get_ready_steps(self, temp_runbook_dir):
        loader = RunbookLoader(temp_runbook_dir)
        checklist = loader.load_analysis_plan("test_metric")

        # 初始状态：step_1 和 step_3 无依赖，可执行
        ready = loader._get_ready_steps(checklist)
        ready_ids = [s.id for s in ready]
        assert "step_1" in ready_ids
        assert "step_3" in ready_ids
        assert "step_2" not in ready_ids  # 依赖 step_1

    def test_get_ready_steps_after_done(self, temp_runbook_dir):
        loader = RunbookLoader(temp_runbook_dir)
        checklist = loader.load_analysis_plan("test_metric")

        # step_1 完成后，step_2 应该可执行
        checklist[0].status = "done"
        ready = loader._get_ready_steps(checklist)
        ready_ids = [s.id for s in ready]
        assert "step_2" in ready_ids
        assert "step_3" in ready_ids

    def test_format_checklist_status(self, temp_runbook_dir):
        loader = RunbookLoader(temp_runbook_dir)
        checklist = loader.load_analysis_plan("test_metric")
        text = loader.format_checklist_status(checklist)
        assert "归因分析清单" in text
        assert "⬜" in text
        assert "MUST" in text

    def test_format_pending_must_reminder(self, temp_runbook_dir):
        loader = RunbookLoader(temp_runbook_dir)
        checklist = loader.load_analysis_plan("test_metric")
        reminder = loader.format_pending_must_reminder(checklist)
        assert "尚未完成" in reminder
        assert "步骤1" in reminder

    def test_no_reminder_when_all_must_done(self, temp_runbook_dir):
        loader = RunbookLoader(temp_runbook_dir)
        checklist = loader.load_analysis_plan("test_metric")
        for item in checklist:
            if item.priority == "must":
                item.status = "done"
        reminder = loader.format_pending_must_reminder(checklist)
        assert reminder == ""


# ============================================================
# RuleMatcher 测试
# ============================================================


class TestRuleMatcher:
    def test_full_match(self, temp_runbook_dir):
        matcher = RuleMatcher(temp_runbook_dir)
        evidence_pool = {
            "step_1": {
                "result": {},
                "parsed": {"rate_of_change": 0.3},
            },
            "step_2": {
                "result": {},
                "parsed": {"gini": 0.85},
            },
        }
        matched = matcher.match_all_scenarios("test_metric", evidence_pool)
        assert len(matched) > 0
        assert matched[0].match_score == 1.0
        assert matched[0].confidence == "high"
        assert matched[0].scenario == "scenario_a"

    def test_partial_match(self, temp_runbook_dir):
        matcher = RuleMatcher(temp_runbook_dir)
        evidence_pool = {
            "step_1": {
                "result": {},
                "parsed": {"rate_of_change": 0.3},  # 满足
            },
            "step_2": {
                "result": {},
                "parsed": {"gini": 0.5},  # 不满足 > 0.7
            },
        }
        matched = matcher.match_all_scenarios("test_metric", evidence_pool)
        assert len(matched) > 0
        assert matched[0].match_score == 0.5
        assert matched[0].confidence == "low"  # 部分匹配降级为 low

    def test_no_match_missing_evidence(self, temp_runbook_dir):
        matcher = RuleMatcher(temp_runbook_dir)
        evidence_pool = {
            "step_1": {"result": {}, "parsed": {"rate_of_change": 0.3}},
            # step_2 缺失
        }
        matched = matcher.match_all_scenarios("test_metric", evidence_pool)
        assert len(matched) == 0  # required_evidence 不满足

    def test_compare_operators(self):
        assert RuleMatcher._compare(0.8, ">", 0.7) is True
        assert RuleMatcher._compare(0.6, ">", 0.7) is False
        assert RuleMatcher._compare(0.5, "<", 0.7) is True
        assert RuleMatcher._compare(0.7, ">=", 0.7) is True
        assert RuleMatcher._compare(0.7, "<=", 0.7) is True
        assert RuleMatcher._compare(True, "==", True) is True
        assert RuleMatcher._compare(1, "!=", 2) is True

    def test_get_nested(self):
        data = {"a": {"b": {"c": 42}}}
        assert RuleMatcher._get_nested(data, "a.b.c") == 42
        assert RuleMatcher._get_nested(data, "a.b") == {"c": 42}
        assert RuleMatcher._get_nested(data, "x.y") is None

    def test_format_match_results_empty(self, temp_runbook_dir):
        matcher = RuleMatcher(temp_runbook_dir)
        text = matcher.format_match_results([])
        assert "未匹配" in text

    def test_format_match_results_with_matches(self, temp_runbook_dir):
        matcher = RuleMatcher(temp_runbook_dir)
        matched = [
            MatchedRule(
                scenario="test",
                scenario_name="测试场景",
                rule_id="r1",
                rule_name="规则1",
                confidence="high",
                conclusion="测试结论",
                suggested_action="测试建议",
                match_score=1.0,
                matched_conditions=["条件1", "条件2"],
                unmatched_conditions=[],
            )
        ]
        text = matcher.format_match_results(matched)
        assert "测试场景" in text
        assert "测试结论" in text
        assert "✅" in text
