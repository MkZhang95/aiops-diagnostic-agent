"""Golden case evals for deterministic, non-LLM diagnostic behavior."""

import json
from pathlib import Path
from typing import Any

import yaml

from src.data import DataSimulator
from src.knowledge.rule_matcher import RuleMatcher
from src.tools import get_all_tools

EVIDENCE_MARKER = "===EVIDENCE==="
GOLDEN_CASES_PATH = Path("evals/golden_cases.yaml")


def _parse_evidence(text: str) -> dict:
    if EVIDENCE_MARKER not in text:
        return {}
    try:
        return json.loads(text.split(EVIDENCE_MARKER, 1)[1].strip())
    except json.JSONDecodeError:
        return {}


def _get_nested(data: dict, path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _run_plan(scenario_name: str, metric: str) -> tuple[dict, list]:
    simulator = DataSimulator(scenario_name)
    tools = {tool.name: tool for tool in get_all_tools(simulator)}

    with open(f"runbooks/{metric}/analysis_plan.yaml", encoding="utf-8") as f:
        plan = yaml.safe_load(f)

    evidence_pool = {}
    for step in plan["steps"]:
        tool = tools[step["action"]]
        result = tool.invoke(step.get("params", {}))
        evidence_pool[step["id"]] = {
            "tool": step["action"],
            "args": step.get("params", {}),
            "result": result,
            "parsed": _parse_evidence(result),
        }

    matched = RuleMatcher("runbooks").match_all_scenarios(metric, evidence_pool)
    return evidence_pool, matched


def _load_cases() -> list[dict]:
    with GOLDEN_CASES_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)["cases"]


def test_golden_cases_pass_expected_deterministic_checks():
    for case in _load_cases():
        expected = case["expected"]
        evidence_pool, matched = _run_plan(case["scenario"], case["metric"])

        for step_id in expected.get("required_evidence", []):
            assert step_id in evidence_pool, f"{case['id']} missing evidence {step_id}"
            assert evidence_pool[step_id]["parsed"], (
                f"{case['id']} evidence {step_id} has no parsed payload"
            )

        full_match = expected.get("full_match")
        if full_match:
            assert any(
                item.scenario == full_match["scenario"]
                and item.rule_id == full_match["rule_id"]
                and item.match_score == 1.0
                for item in matched
            ), f"{case['id']} did not fully match {full_match}"

        partial_match = expected.get("partial_match")
        if partial_match:
            assert any(
                item.scenario == partial_match["scenario"]
                and item.match_score >= partial_match["min_score"]
                for item in matched
            ), f"{case['id']} did not partially match {partial_match}"

        for dotted_path, expected_value in expected.get("parsed", {}).items():
            step_id, field_path = dotted_path.split(".", 1)
            actual = _get_nested(evidence_pool[step_id]["parsed"], field_path)
            if isinstance(expected_value, float):
                assert abs(actual - expected_value) < 1e-6, (
                    f"{case['id']} {dotted_path}: {actual} != {expected_value}"
                )
            else:
                assert actual == expected_value, (
                    f"{case['id']} {dotted_path}: {actual} != {expected_value}"
                )
