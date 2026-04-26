"""route_metric 节点单测

用 Fake LLM 验证路由的确定性逻辑：
- bypass：场景模式 alert.metric_name 已设置
- routed：合法 metric 输出
- unknown：null / 非合法 metric / JSON 损坏
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from src.agent.nodes import (
    ROUTE_BYPASS,
    ROUTE_OK,
    ROUTE_UNKNOWN,
    make_route_metric,
)
from src.agent.state import AlertEvent


class _FakeChatModel:
    """最小可用的 ChatModel 替身：按构造时给定的字符串回包。"""

    def __init__(self, content: str):
        self._content = content

    def invoke(self, messages):
        return AIMessage(content=self._content)


class _FakeLLM:
    def __init__(self, content: str):
        self._content = content
        self.model_name = "fake"

    def get_chat_model(self):
        return _FakeChatModel(self._content)


def _state(metric: str = "", query: str = ""):
    return {
        "alert": AlertEvent(alert_id="t1", metric_name=metric),
        "user_query": query,
    }


def test_bypass_when_metric_already_set():
    """场景模式：alert.metric_name 已存在，直接 bypass，不走 LLM"""
    router = make_route_metric(_FakeLLM("should not be called"), "runbooks")
    out = router(_state(metric="play_success_rate"))
    assert out["route_status"] == ROUTE_BYPASS


def test_routed_to_play_success_rate():
    fake = _FakeLLM(
        '{"metric": "play_success_rate", "confidence": "high", "reason": "用户问起播失败"}'
    )
    router = make_route_metric(fake, "runbooks")
    out = router(_state(query="播放失败率最近涨了，帮我归因"))
    assert out["route_status"] == ROUTE_OK
    assert out["alert"].metric_name == "play_success_rate"
    assert out["alert"].description == "播放失败率最近涨了，帮我归因"


def test_routed_to_p2p():
    fake = _FakeLLM(
        '{"metric": "p2p_bandwidth_share", "confidence": "high", "reason": "P2P 带宽占比"}'
    )
    router = make_route_metric(fake, "runbooks")
    out = router(_state(query="P2P 大盘带宽占比掉了"))
    assert out["route_status"] == ROUTE_OK
    assert out["alert"].metric_name == "p2p_bandwidth_share"


def test_unknown_when_metric_null():
    fake = _FakeLLM('{"metric": null, "confidence": "low", "reason": "无匹配"}')
    router = make_route_metric(fake, "runbooks")
    out = router(_state(query="今天午饭吃什么"))
    assert out["route_status"] == ROUTE_UNKNOWN


def test_unknown_when_metric_not_in_allowed():
    """LLM 编造了不存在的 metric 名 → 必须被硬校验拦下来"""
    fake = _FakeLLM(
        '{"metric": "fake_metric_xyz", "confidence": "high", "reason": "..."}'
    )
    router = make_route_metric(fake, "runbooks")
    out = router(_state(query="随便问问"))
    assert out["route_status"] == ROUTE_UNKNOWN


def test_unknown_when_json_broken():
    fake = _FakeLLM("not a json at all")
    router = make_route_metric(fake, "runbooks")
    out = router(_state(query="随便问问"))
    assert out["route_status"] == ROUTE_UNKNOWN


def test_strip_markdown_code_fence():
    """LLM 偶尔会用 ```json ... ``` 包裹，需要容错"""
    fake = _FakeLLM(
        '```json\n{"metric": "play_success_rate", "confidence": "high", "reason": "ok"}\n```'
    )
    router = make_route_metric(fake, "runbooks")
    out = router(_state(query="播放成功率怎么了"))
    assert out["route_status"] == ROUTE_OK
    assert out["alert"].metric_name == "play_success_rate"


def test_unknown_when_missing_query_and_metric():
    router = make_route_metric(_FakeLLM(""), "runbooks")
    out = router(_state(metric="", query=""))
    assert out["route_status"] == ROUTE_UNKNOWN
