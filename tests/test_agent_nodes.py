"""Agent node unit tests."""

from langchain_core.messages import AIMessage

from src.agent.nodes import validate_tool_calls


def _state_with_call(tool_name: str, args: dict, checklist: list[dict]) -> dict:
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "name": tool_name,
                        "args": args,
                    }
                ],
            )
        ],
        "checklist": checklist,
    }


def test_validate_tool_calls_allows_ready_step():
    checklist = [
        {
            "id": "overall_trend",
            "name": "整体趋势",
            "priority": "must",
            "action": "query_metric",
            "params": {"metric": "play_success_rate"},
            "depends_on": [],
            "status": "pending",
        }
    ]
    state = _state_with_call(
        "query_metric",
        {"metric": "play_success_rate"},
        checklist,
    )

    result = validate_tool_calls(state)

    assert result["tool_calls_valid"] is True
    assert "messages" not in result


def test_validate_tool_calls_rejects_step_with_unmet_dependency():
    checklist = [
        {
            "id": "overall_trend",
            "name": "整体趋势",
            "priority": "must",
            "action": "query_metric",
            "params": {"metric": "play_success_rate"},
            "depends_on": [],
            "status": "pending",
        },
        {
            "id": "drill_isp",
            "name": "运营商下钻",
            "priority": "must",
            "action": "query_metric",
            "params": {"metric": "play_success_rate", "dimension": "isp"},
            "depends_on": ["overall_trend"],
            "status": "pending",
        },
    ]
    state = _state_with_call(
        "query_metric",
        {"metric": "play_success_rate", "dimension": "isp"},
        checklist,
    )

    result = validate_tool_calls(state)

    assert result["tool_calls_valid"] is False
    assert len(result["messages"]) == 2
    assert result["messages"][0].type == "tool"
    assert "依赖未完成" in result["messages"][1].content


def test_validate_tool_calls_rejects_param_mismatch():
    checklist = [
        {
            "id": "overall_trend",
            "name": "整体趋势",
            "priority": "must",
            "action": "query_metric",
            "params": {"metric": "play_success_rate"},
            "depends_on": [],
            "status": "pending",
        }
    ]
    state = _state_with_call(
        "query_metric",
        {"metric": "cdn_error_rate"},
        checklist,
    )

    result = validate_tool_calls(state)

    assert result["tool_calls_valid"] is False
    assert "参数不匹配" in result["messages"][1].content
