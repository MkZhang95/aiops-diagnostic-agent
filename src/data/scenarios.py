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

    # ============================================================
    # 场景 4: P2P 大盘带宽占比下降 — 手机分享比下降-有效覆盖度
    #   期望规则匹配: phone_sharing / phone_sharing_drop
    #   手机有效覆盖度 = 返回节点成功率 × 连接成功率 × 尝试订阅率 × 订阅成功率
    #   本 case 的瓶颈在 connect_success_rate（0.97 → 0.78）
    # ============================================================
    "phone_sharing_coverage_drop": {
        "alert": {
            "metric_name": "p2p_bandwidth_share",
            "description": "P2P 大盘带宽占比下降",
            "severity": "warning",
            "current_value": 40.0,
            "baseline_value": 45.0,
            "timestamp": 1705571400,
            "service": "p2p-cdn",
            "region": "all",
        },
        "metrics": {
            # ---- 主指标 ----
            "p2p_bandwidth_share": {
                "t1_value": 45.0,
                "t2_value": 40.0,
                "delta": -5.0,
                "delta_ratio": -11.1,
                "time_series": [
                    (0, 45.0), (300, 44.8), (600, 44.5), (900, 44.0),
                    (1200, 43.2), (1500, 42.4), (1800, 41.5), (2100, 40.8),
                    (2400, 40.3), (2700, 40.1), (3000, 40.0), (3600, 40.0),
                ],
            },
            # ---- 手机链路（均下降） ----
            "phone_bandwidth_share": {
                "t1_value": 28.0,
                "t2_value": 23.0,
                "delta": -5.0,
                "delta_ratio": -17.9,
                "time_series": [
                    (0, 28.0), (300, 27.8), (600, 27.3), (900, 26.6),
                    (1200, 25.7), (1500, 24.8), (1800, 24.0), (2100, 23.4),
                    (2400, 23.1), (2700, 23.0), (3000, 23.0), (3600, 23.0),
                ],
            },
            "phone_sharing_ratio": {
                "t1_value": 0.62,
                "t2_value": 0.52,
                "delta": -0.10,
                "delta_ratio": -16.1,
                "time_series": [
                    (0, 0.62), (300, 0.61), (600, 0.60), (900, 0.59),
                    (1200, 0.57), (1500, 0.55), (1800, 0.54), (2100, 0.53),
                    (2400, 0.52), (2700, 0.52), (3000, 0.52), (3600, 0.52),
                ],
            },
            "phone_effective_coverage": {
                "t1_value": 0.85,
                "t2_value": 0.72,
                "delta": -0.13,
                "delta_ratio": -15.3,
                "time_series": [
                    (0, 0.85), (300, 0.84), (600, 0.83), (900, 0.81),
                    (1200, 0.78), (1500, 0.76), (1800, 0.74), (2100, 0.73),
                    (2400, 0.72), (2700, 0.72), (3000, 0.72), (3600, 0.72),
                ],
            },
            # ---- 有效覆盖度漏斗（LMDI 公式子指标，连接成功率是瓶颈） ----
            "return_node_success_rate": {
                "t1_value": 0.98,
                "t2_value": 0.97,
                "delta": -0.01,
                "delta_ratio": -1.0,
                "time_series": [
                    (0, 0.98), (600, 0.98), (1200, 0.975), (1800, 0.97),
                    (2400, 0.97), (3000, 0.97), (3600, 0.97),
                ],
            },
            "connect_success_rate": {
                "t1_value": 0.97,
                "t2_value": 0.78,
                "delta": -0.19,
                "delta_ratio": -19.6,
                "time_series": [
                    (0, 0.97), (300, 0.96), (600, 0.94), (900, 0.90),
                    (1200, 0.86), (1500, 0.83), (1800, 0.80), (2100, 0.79),
                    (2400, 0.78), (2700, 0.78), (3000, 0.78), (3600, 0.78),
                ],
            },
            "subscribe_attempt_rate": {
                "t1_value": 0.95,
                "t2_value": 0.94,
                "delta": -0.01,
                "delta_ratio": -1.1,
                "time_series": [
                    (0, 0.95), (600, 0.95), (1200, 0.945), (1800, 0.94),
                    (2400, 0.94), (3000, 0.94), (3600, 0.94),
                ],
            },
            "subscribe_success_rate": {
                "t1_value": 0.96,
                "t2_value": 0.95,
                "delta": -0.01,
                "delta_ratio": -1.0,
                "time_series": [
                    (0, 0.96), (600, 0.96), (1200, 0.955), (1800, 0.95),
                    (2400, 0.95), (3000, 0.95), (3600, 0.95),
                ],
            },
            # ---- 盒子链路（基本无变化，场景 1 不会命中） ----
            "box_bandwidth_share": {
                "t1_value": 17.0,
                "t2_value": 17.0,
                "delta": 0.0,
                "delta_ratio": 0.0,
                "time_series": [
                    (0, 17.0), (600, 17.0), (1200, 17.1), (1800, 17.0),
                    (2400, 17.0), (3000, 17.0), (3600, 17.0),
                ],
            },
            "box_sharing_ratio": {
                "t1_value": 0.55,
                "t2_value": 0.55,
                "delta": 0.0,
                "delta_ratio": 0.0,
                "time_series": [
                    (0, 0.55), (600, 0.55), (1200, 0.55), (1800, 0.55),
                    (2400, 0.55), (3000, 0.55), (3600, 0.55),
                ],
            },
            # ---- RTM（基本无变化，场景 2 不会命中） ----
            "rtm_bandwidth_share": {
                "t1_value": 8.0,
                "t2_value": 8.1,
                "delta": 0.1,
                "delta_ratio": 1.25,
                "time_series": [
                    (0, 8.0), (600, 8.0), (1200, 8.05), (1800, 8.1),
                    (2400, 8.1), (3000, 8.1), (3600, 8.1),
                ],
            },
        },
        "drill_down": {
            # p2p_bandwidth_share 的下钻数据（simulator.drill_down 不区分 metric，
            # 此处数据对应主指标 p2p_bandwidth_share 的 -5 变化）
            "app": [
                {"dimension_value": "app_1", "t1_value": 18.0, "t2_value": 14.0, "delta": -4.0, "contribution_ratio": 80.0},
                {"dimension_value": "app_2", "t1_value": 15.0, "t2_value": 14.2, "delta": -0.8, "contribution_ratio": 16.0},
                {"dimension_value": "app_3", "t1_value": 12.0, "t2_value": 11.8, "delta": -0.2, "contribution_ratio": 4.0},
            ],
            "os": [
                {"dimension_value": "android", "t1_value": 28.0, "t2_value": 23.0, "delta": -5.0, "contribution_ratio": 96.0},
                {"dimension_value": "ios", "t1_value": 17.0, "t2_value": 17.0, "delta": 0.0, "contribution_ratio": 4.0},
            ],
            "cdn_vendor": [
                {"dimension_value": "vendor_a", "t1_value": 20.0, "t2_value": 17.8, "delta": -2.2, "contribution_ratio": 44.0},
                {"dimension_value": "vendor_b", "t1_value": 15.0, "t2_value": 13.5, "delta": -1.5, "contribution_ratio": 30.0},
                {"dimension_value": "vendor_c", "t1_value": 10.0, "t2_value": 8.7, "delta": -1.3, "contribution_ratio": 26.0},
            ],
            "release_point": [
                {"dimension_value": "release_hot", "t1_value": 22.0, "t2_value": 19.5, "delta": -2.5, "contribution_ratio": 50.0},
                {"dimension_value": "release_cold", "t1_value": 15.0, "t2_value": 13.5, "delta": -1.5, "contribution_ratio": 30.0},
                {"dimension_value": "release_live", "t1_value": 8.0, "t2_value": 7.0, "delta": -1.0, "contribution_ratio": 20.0},
            ],
        },
        "logs": [
            {"timestamp": 1705570800, "level": "WARN", "message": "Phone peer connect latency spike on Android: avg 220ms -> 520ms", "source": "p2p-client-metrics", "region": "all"},
            {"timestamp": 1705570900, "level": "ERROR", "message": "Phone P2P connect_success_rate dropped to 78% (baseline 97%) on app_1 android", "source": "p2p-dashboard", "region": "all"},
            {"timestamp": 1705571000, "level": "ERROR", "message": "NAT traversal failed for android peers: STUN binding timeout", "source": "p2p-signal", "region": "all"},
            {"timestamp": 1705571100, "level": "WARN", "message": "app_1 v8.12.0 connect timeout rate 18% vs baseline 2%", "source": "client-crash-report", "region": "all"},
            {"timestamp": 1705571300, "level": "ERROR", "message": "Phone effective coverage degraded: funnel bottleneck = connect_success_rate", "source": "p2p-dashboard", "region": "all"},
        ],
        "changes": [
            {"timestamp": 1705564800, "change_type": "deployment", "description": "app_1 v8.12.0 全量发版 (调整了 P2P 连接建立逻辑和超时策略)", "author": "mobile-team", "affected_services": ["app_1", "p2p-client"]},
            {"timestamp": 1705561200, "change_type": "config", "description": "P2P 调度灰度：Android 端新 NAT 穿透策略上线", "author": "p2p-sched", "affected_services": ["p2p-signal", "p2p-client"]},
        ],
        "expected_root_cause": "手机侧（主要 Android/app_1）连接成功率骤降导致手机有效覆盖度下跌，手机分享比和手机大盘占比随之下降，带动 P2P 大盘占比下降——典型的手机分享比下降-有效覆盖度场景",
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
