"""Unit tests for core algorithms: structural contribution and GINI concentration."""


from src.tools.decompose_formula import compute_lmdi
from src.tools.decompose_metric import compute_gini, compute_structural


class TestStructuralContribution:
    """Tests for structural contribution decomposition (结构贡献度拆解法).

    公式: ΔV_a = 0.5×(Pa1+Pa0)×(Va1-Va0) + [0.5×(Va1+Va0) - V0]×(Pa1-Pa0)
    """

    def test_contributions_sum_to_total_change(self):
        """所有维度贡献度之和应等于指标总变化量."""
        data = [
            {"name": "cn-south", "t1": 99.3, "t2": 96.1, "p0": 0.35, "p1": 0.38},
            {"name": "cn-north", "t1": 99.1, "t2": 99.0, "p0": 0.30, "p1": 0.28},
            {"name": "cn-east", "t1": 99.2, "t2": 99.25, "p0": 0.20, "p1": 0.20},
            {"name": "cn-west", "t1": 99.0, "t2": 98.95, "p0": 0.15, "p1": 0.14},
        ]
        # 总体基线: V0 = Σ(p0_i × t1_i)
        v0 = sum(d["p0"] * d["t1"] for d in data)
        # 总体当期: V1 = Σ(p1_i × t2_i)
        v1 = sum(d["p1"] * d["t2"] for d in data)
        expected_total = v1 - v0

        results = compute_structural(data, v0=v0)
        actual_total = sum(r["contribution"] for r in results)

        assert abs(actual_total - expected_total) < 0.01, (
            f"贡献度之和 {actual_total:.4f} != 总变化量 {expected_total:.4f}"
        )

    def test_top_contributor_identified(self):
        """cn-south 下降最多，应该是最大贡献者."""
        data = [
            {"name": "cn-south", "t1": 99.3, "t2": 96.1, "p0": 0.35, "p1": 0.35},
            {"name": "cn-north", "t1": 99.1, "t2": 99.0, "p0": 0.30, "p1": 0.30},
            {"name": "cn-east", "t1": 99.2, "t2": 99.25, "p0": 0.20, "p1": 0.20},
            {"name": "cn-west", "t1": 99.0, "t2": 98.95, "p0": 0.15, "p1": 0.15},
        ]
        results = compute_structural(data)
        assert results[0]["name"] == "cn-south"
        assert results[0]["ratio"] > 50

    def test_performance_and_structure_effects(self):
        """性能效应和结构效应之和应等于总贡献度."""
        data = [
            {"name": "A", "t1": 90.0, "t2": 85.0, "p0": 0.6, "p1": 0.5},
            {"name": "B", "t1": 95.0, "t2": 95.0, "p0": 0.4, "p1": 0.5},
        ]
        results = compute_structural(data)

        for r in results:
            total = r["performance_effect"] + r["structure_effect"]
            assert abs(total - r["contribution"]) < 1e-10

    def test_no_weight_change_means_no_structure_effect(self):
        """权重不变时，结构效应应为 0."""
        data = [
            {"name": "A", "t1": 100, "t2": 80, "p0": 0.5, "p1": 0.5},
            {"name": "B", "t1": 100, "t2": 100, "p0": 0.5, "p1": 0.5},
        ]
        results = compute_structural(data)

        for r in results:
            assert abs(r["structure_effect"]) < 1e-10

    def test_no_value_change_but_weight_shift(self):
        """指标值不变但流量迁移时，只有结构效应."""
        data = [
            {"name": "good", "t1": 99.0, "t2": 99.0, "p0": 0.5, "p1": 0.3},
            {"name": "bad", "t1": 95.0, "t2": 95.0, "p0": 0.5, "p1": 0.7},
        ]
        v0 = sum(d["p0"] * d["t1"] for d in data)
        results = compute_structural(data, v0=v0)

        for r in results:
            assert abs(r["performance_effect"]) < 1e-10
            # 流量从 good(99) 迁移到 bad(95)，总体应该变差
        total = sum(r["contribution"] for r in results)
        assert total < 0  # 总体变差

    def test_equal_weight_fallback(self):
        """不提供权重时等权分配，仍能正常计算."""
        data = [
            {"name": "A", "t1": 100, "t2": 80},
            {"name": "B", "t1": 100, "t2": 100},
            {"name": "C", "t1": 100, "t2": 100},
        ]
        results = compute_structural(data)

        # A 应该是最大贡献者
        a_result = next(r for r in results if r["name"] == "A")
        assert a_result["ratio"] > 90

    def test_empty_input(self):
        """空输入应返回空列表."""
        assert compute_structural([]) == []


class TestLMDI:
    """Tests for LMDI decomposition (乘法指标)."""

    def test_basic_decomposition(self):
        """LMDI 贡献度占比之和应为 100%."""
        data = [
            {"name": "A", "t1": 100, "t2": 80},
            {"name": "B", "t1": 100, "t2": 100},
            {"name": "C", "t1": 100, "t2": 100},
        ]
        results = compute_lmdi(data)
        total_ratio = sum(r["ratio"] for r in results)
        assert abs(total_ratio - 100.0) < 1.0

    def test_single_dimension_change(self):
        """只有一个维度变化时贡献接近 100%."""
        data = [
            {"name": "A", "t1": 100, "t2": 80},
            {"name": "B", "t1": 100, "t2": 100},
        ]
        results = compute_lmdi(data)
        a_result = next(r for r in results if r["name"] == "A")
        assert a_result["ratio"] > 90

    def test_empty_input(self):
        assert compute_lmdi([]) == []


class TestGINI:
    """Tests for GINI coefficient calculation."""

    def test_perfect_equality(self):
        """完全均匀分布 → GINI ≈ 0."""
        values = [25, 25, 25, 25]
        gini = compute_gini(values)
        assert gini < 0.1

    def test_high_concentration(self):
        """高度集中分布 → GINI 接近 1."""
        values = [0, 0, 0, 100]
        gini = compute_gini(values)
        assert gini > 0.7

    def test_moderate_concentration(self):
        """中等集中分布."""
        values = [10, 15, 25, 50]
        gini = compute_gini(values)
        assert 0.2 < gini < 0.7

    def test_two_values(self):
        """只有两个值时的边界情况."""
        gini = compute_gini([100, 0])
        assert gini > 0.4

    def test_single_value(self):
        assert compute_gini([100]) == 0.0

    def test_empty_input(self):
        assert compute_gini([]) == 0.0

    def test_all_zeros(self):
        assert compute_gini([0, 0, 0]) == 0.0

    def test_negative_values_handled(self):
        """负值应取绝对值处理."""
        gini = compute_gini([-10, -20, -70])
        assert 0 <= gini <= 1
