"""Pre-built diagnostic scenarios with simulated data.

Each scenario contains a complete set of simulated data that forms
a self-consistent evidence chain leading to a known root cause.
"""

SCENARIOS = {
    # ============================================================
    # 场景 1: 播放成功率下降 — CDN 华南节点配置变更
    # ============================================================
    "play_success_rate_drop": {
        "alert": {
            "metric_name": "play_success_rate",
            "description": "播放成功率下降",
            "severity": "critical",
            "current_value": 97.8,
            "baseline_value": 99.2,
            "timestamp": 1705312200,
            "service": "video-cdn",
            "region": "all",
        },
        "metrics": {
            "play_success_rate": {
                "t1_value": 99.2,
                "t2_value": 97.8,
                "delta": -1.4,
                "delta_ratio": -1.41,
                "time_series": [
                    (0, 99.2), (300, 99.1), (600, 99.2), (900, 99.0),
                    (1200, 98.8), (1500, 98.2), (1800, 97.8), (2100, 97.9),
                    (2400, 97.8), (2700, 97.7), (3000, 97.8), (3600, 97.8),
                ],
            },
        },
        "drill_down": {
            "region": [
                {"dimension_value": "cn-south", "t1_value": 99.3, "t2_value": 96.1, "delta": -3.2, "contribution_ratio": 82.3},
                {"dimension_value": "cn-north", "t1_value": 99.1, "t2_value": 99.0, "delta": -0.1, "contribution_ratio": 11.2},
                {"dimension_value": "cn-east", "t1_value": 99.2, "t2_value": 99.25, "delta": 0.05, "contribution_ratio": 3.5},
                {"dimension_value": "cn-west", "t1_value": 99.0, "t2_value": 98.95, "delta": -0.05, "contribution_ratio": 3.0},
            ],
            "isp": [
                {"dimension_value": "china-telecom", "t1_value": 99.1, "t2_value": 98.2, "delta": -0.9, "contribution_ratio": 45.0},
                {"dimension_value": "china-unicom", "t1_value": 99.3, "t2_value": 98.5, "delta": -0.8, "contribution_ratio": 35.0},
                {"dimension_value": "china-mobile", "t1_value": 99.2, "t2_value": 98.9, "delta": -0.3, "contribution_ratio": 15.0},
                {"dimension_value": "other", "t1_value": 99.0, "t2_value": 98.9, "delta": -0.1, "contribution_ratio": 5.0},
            ],
            "cdn_node": [
                {"dimension_value": "cdn-gz-01", "t1_value": 99.4, "t2_value": 95.2, "delta": -4.2, "contribution_ratio": 72.0},
                {"dimension_value": "cdn-gz-02", "t1_value": 99.2, "t2_value": 97.5, "delta": -1.7, "contribution_ratio": 15.0},
                {"dimension_value": "cdn-sh-01", "t1_value": 99.3, "t2_value": 99.2, "delta": -0.1, "contribution_ratio": 5.0},
                {"dimension_value": "cdn-bj-01", "t1_value": 99.1, "t2_value": 99.0, "delta": -0.1, "contribution_ratio": 5.0},
                {"dimension_value": "cdn-cd-01", "t1_value": 99.0, "t2_value": 99.0, "delta": 0.0, "contribution_ratio": 3.0},
            ],
        },
        "logs": [
            {"timestamp": 1705311600, "level": "WARN", "message": "CDN node cdn-gz-01 health check latency increased to 250ms", "source": "cdn-monitor", "region": "cn-south"},
            {"timestamp": 1705311900, "level": "ERROR", "message": "Connection timeout to cdn-gz-01, retry count: 3", "source": "video-player", "region": "cn-south"},
            {"timestamp": 1705312000, "level": "ERROR", "message": "cdn-gz-01 upstream connection failed: connection refused", "source": "cdn-gateway", "region": "cn-south"},
            {"timestamp": 1705312100, "level": "ERROR", "message": "Playback failed: CDN resource unavailable, node=cdn-gz-01", "source": "video-player", "region": "cn-south"},
            {"timestamp": 1705312200, "level": "ERROR", "message": "Timeout errors spike detected: cdn-gz-01 error_rate=12.3%", "source": "alert-engine", "region": "cn-south"},
            {"timestamp": 1705312300, "level": "WARN", "message": "Fallback to cdn-gz-02 triggered for cn-south traffic", "source": "cdn-lb", "region": "cn-south"},
        ],
        "changes": [
            {"timestamp": 1705311600, "change_type": "config", "description": "CDN 节点 cdn-gz-01 配置更新: 修改连接池参数 max_connections 从 1000 调整为 200", "author": "ops-bot", "affected_services": ["video-cdn", "cdn-gz-01"]},
            {"timestamp": 1705296000, "change_type": "deployment", "description": "video-player SDK v2.3.1 发布 (常规更新)", "author": "ci-pipeline", "affected_services": ["video-player"]},
        ],
        "expected_root_cause": "CDN 华南节点 cdn-gz-01 配置变更（连接池参数缩减）导致播放成功率下降",
    },

    # ============================================================
    # 场景 2: 卡顿率上升 — 转码配置调整
    # ============================================================
    "buffering_rate_rise": {
        "alert": {
            "metric_name": "buffering_rate",
            "description": "卡顿率上升",
            "severity": "warning",
            "current_value": 5.1,
            "baseline_value": 3.2,
            "timestamp": 1705398600,
            "service": "video-transcode",
            "region": "all",
        },
        "metrics": {
            "buffering_rate": {
                "t1_value": 3.2,
                "t2_value": 5.1,
                "delta": 1.9,
                "delta_ratio": 59.4,
                "time_series": [
                    (0, 3.2), (300, 3.3), (600, 3.5), (900, 3.8),
                    (1200, 4.2), (1500, 4.6), (1800, 5.0), (2100, 5.1),
                    (2400, 5.1), (2700, 5.0), (3000, 5.1), (3600, 5.1),
                ],
            },
            "bitrate": {
                "t1_value": 2500,
                "t2_value": 2200,
                "delta": -300,
                "delta_ratio": -12.0,
                "time_series": [
                    (0, 2500), (300, 2480), (600, 2420), (900, 2380),
                    (1200, 2320), (1500, 2280), (1800, 2220), (2100, 2200),
                    (2400, 2200), (2700, 2200), (3000, 2200), (3600, 2200),
                ],
            },
        },
        "drill_down": {
            "resolution": [
                {"dimension_value": "1080p", "t1_value": 4.0, "t2_value": 7.2, "delta": 3.2, "contribution_ratio": 65.0},
                {"dimension_value": "720p", "t1_value": 2.8, "t2_value": 3.5, "delta": 0.7, "contribution_ratio": 18.0},
                {"dimension_value": "480p", "t1_value": 2.0, "t2_value": 2.3, "delta": 0.3, "contribution_ratio": 10.0},
                {"dimension_value": "360p", "t1_value": 1.5, "t2_value": 1.7, "delta": 0.2, "contribution_ratio": 7.0},
            ],
            "codec": [
                {"dimension_value": "h265", "t1_value": 3.0, "t2_value": 5.8, "delta": 2.8, "contribution_ratio": 62.0},
                {"dimension_value": "h264", "t1_value": 3.3, "t2_value": 4.2, "delta": 0.9, "contribution_ratio": 25.0},
                {"dimension_value": "av1", "t1_value": 3.5, "t2_value": 3.8, "delta": 0.3, "contribution_ratio": 13.0},
            ],
            "region": [
                {"dimension_value": "cn-south", "t1_value": 3.3, "t2_value": 5.3, "delta": 2.0, "contribution_ratio": 35.0},
                {"dimension_value": "cn-north", "t1_value": 3.1, "t2_value": 5.0, "delta": 1.9, "contribution_ratio": 33.0},
                {"dimension_value": "cn-east", "t1_value": 3.2, "t2_value": 4.9, "delta": 1.7, "contribution_ratio": 22.0},
                {"dimension_value": "cn-west", "t1_value": 3.0, "t2_value": 3.5, "delta": 0.5, "contribution_ratio": 10.0},
            ],
        },
        "logs": [
            {"timestamp": 1705398000, "level": "INFO", "message": "Transcoding profile updated: h265 CRF changed from 23 to 28", "source": "transcode-service", "region": "all"},
            {"timestamp": 1705398300, "level": "WARN", "message": "Video quality score dropped for 1080p h265 streams: VMAF 85 -> 72", "source": "quality-monitor", "region": "all"},
            {"timestamp": 1705398600, "level": "WARN", "message": "Buffering events increased 60% for 1080p content", "source": "player-analytics", "region": "all"},
        ],
        "changes": [
            {"timestamp": 1705397400, "change_type": "config", "description": "转码配置更新: H265 编码 CRF 参数从 23 调整为 28 以降低带宽成本", "author": "transcode-team", "affected_services": ["video-transcode", "video-cdn"]},
            {"timestamp": 1705380000, "change_type": "scaling", "description": "转码集群扩容: GPU 节点从 50 增加到 60 (常规扩容)", "author": "k8s-autoscaler", "affected_services": ["video-transcode"]},
        ],
        "expected_root_cause": "转码配置更新（H265 CRF 参数调大）导致视频质量下降，引起 1080p 内容卡顿率上升",
    },

    # ============================================================
    # 场景 3: 首帧耗时劣化 — DNS 解析异常 + 运营商链路
    # ============================================================
    "first_frame_latency_degradation": {
        "alert": {
            "metric_name": "first_frame_latency_p95",
            "description": "首帧耗时 P95 劣化",
            "severity": "warning",
            "current_value": 1200,
            "baseline_value": 800,
            "timestamp": 1705485000,
            "service": "video-player",
            "region": "all",
        },
        "metrics": {
            "first_frame_latency_p95": {
                "t1_value": 800,
                "t2_value": 1200,
                "delta": 400,
                "delta_ratio": 50.0,
                "time_series": [
                    (0, 800), (300, 820), (600, 870), (900, 950),
                    (1200, 1050), (1500, 1120), (1800, 1180), (2100, 1200),
                    (2400, 1200), (2700, 1190), (3000, 1200), (3600, 1200),
                ],
            },
            "dns_resolve_time_p95": {
                "t1_value": 50,
                "t2_value": 280,
                "delta": 230,
                "delta_ratio": 460.0,
                "time_series": [
                    (0, 50), (300, 55), (600, 80), (900, 150),
                    (1200, 220), (1500, 260), (1800, 270), (2100, 280),
                    (2400, 280), (2700, 275), (3000, 280), (3600, 280),
                ],
            },
            "tcp_connect_time_p95": {
                "t1_value": 120,
                "t2_value": 180,
                "delta": 60,
                "delta_ratio": 50.0,
                "time_series": [
                    (0, 120), (300, 125), (600, 135), (900, 150),
                    (1200, 165), (1500, 175), (1800, 178), (2100, 180),
                    (2400, 180), (2700, 180), (3000, 180), (3600, 180),
                ],
            },
        },
        "drill_down": {
            "isp": [
                {"dimension_value": "china-telecom", "t1_value": 780, "t2_value": 1350, "delta": 570, "contribution_ratio": 55.0},
                {"dimension_value": "china-unicom", "t1_value": 800, "t2_value": 1100, "delta": 300, "contribution_ratio": 25.0},
                {"dimension_value": "china-mobile", "t1_value": 820, "t2_value": 950, "delta": 130, "contribution_ratio": 12.0},
                {"dimension_value": "other", "t1_value": 750, "t2_value": 850, "delta": 100, "contribution_ratio": 8.0},
            ],
            "region": [
                {"dimension_value": "cn-east", "t1_value": 790, "t2_value": 1280, "delta": 490, "contribution_ratio": 42.0},
                {"dimension_value": "cn-south", "t1_value": 810, "t2_value": 1250, "delta": 440, "contribution_ratio": 35.0},
                {"dimension_value": "cn-north", "t1_value": 780, "t2_value": 980, "delta": 200, "contribution_ratio": 15.0},
                {"dimension_value": "cn-west", "t1_value": 820, "t2_value": 900, "delta": 80, "contribution_ratio": 8.0},
            ],
            "phase": [
                {"dimension_value": "dns_resolve", "t1_value": 50, "t2_value": 280, "delta": 230, "contribution_ratio": 57.5},
                {"dimension_value": "tcp_connect", "t1_value": 120, "t2_value": 180, "delta": 60, "contribution_ratio": 15.0},
                {"dimension_value": "ssl_handshake", "t1_value": 80, "t2_value": 100, "delta": 20, "contribution_ratio": 5.0},
                {"dimension_value": "server_response", "t1_value": 200, "t2_value": 250, "delta": 50, "contribution_ratio": 12.5},
                {"dimension_value": "content_download", "t1_value": 350, "t2_value": 390, "delta": 40, "contribution_ratio": 10.0},
            ],
        },
        "logs": [
            {"timestamp": 1705484400, "level": "WARN", "message": "DNS resolution timeout for video-cdn.example.com via china-telecom resolver", "source": "dns-monitor", "region": "cn-east"},
            {"timestamp": 1705484700, "level": "ERROR", "message": "DNS query latency exceeded 200ms, resolver=ct-dns-sh-01", "source": "dns-monitor", "region": "cn-east"},
            {"timestamp": 1705484800, "level": "WARN", "message": "TCP connection latency increased for china-telecom backbone", "source": "network-monitor", "region": "cn-east"},
            {"timestamp": 1705485000, "level": "ERROR", "message": "First frame timeout rate increased to 3.2% (baseline: 0.8%)", "source": "player-analytics", "region": "cn-east"},
            {"timestamp": 1705485100, "level": "INFO", "message": "DNS failover triggered: switching to backup resolver for ct-dns-sh-01", "source": "dns-manager", "region": "cn-east"},
        ],
        "changes": [
            {"timestamp": 1705484100, "change_type": "config", "description": "DNS 服务商中国电信侧 DNS 节点 ct-dns-sh-01 维护升级", "author": "external-isp", "affected_services": ["dns-resolve"]},
            {"timestamp": 1705470000, "change_type": "deployment", "description": "video-player SDK v2.3.2 热修复 (不影响首帧逻辑)", "author": "ci-pipeline", "affected_services": ["video-player"]},
        ],
        "expected_root_cause": "中国电信 DNS 节点维护导致 DNS 解析延迟激增，叠加电信骨干网链路质量下降，造成首帧耗时劣化",
    },
}


def get_scenario(name: str) -> dict:
    """Get a scenario by name."""
    if name not in SCENARIOS:
        available = ", ".join(SCENARIOS.keys())
        raise ValueError(f"Unknown scenario: {name}. Available: {available}")
    return SCENARIOS[name]


def list_scenarios() -> list[str]:
    """List available scenario names."""
    return list(SCENARIOS.keys())
