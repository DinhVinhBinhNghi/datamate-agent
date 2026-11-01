import pytest

from datamate.planner.direct_revenue import classify_direct_revenue
from datamate.planner.heuristic import plan_heuristic
from datamate.planner.validate import PlannerFailure


@pytest.mark.parametrize(
    ("text", "period"),
    [
        ("Tổng doanh thu trong ngày hôm nay là bao nhiêu nhỉ?", "hôm nay"),
        ("Doanh thu hôm qua của cửa hàng là bao nhiêu?", "hôm qua"),
        ("tong doanh thu thang 9 nam 2025 la bao nhiu", "tháng 9/2025"),
        ("Cho hỏi tổng doanh thu quý 2/2026 là bao nhiêu?", "quý 2/2026"),
        ("7 ngày gần nhất doanh thu đc bao nhiêu?", "7 ngày gần nhất"),
        ("Xem giúp doanh thu từ đầu năm tới hết hôm nay là bao nhiêu?", "từ đầu năm"),
        ("Tuần này cửa hàng bán được bao nhiêu tiền?", "tuần này"),
        ("5/25 quan thu ve bao nhieu doanh thu?", "tháng 5/2025"),
        ("Th 12/25 doanh thu cua quan duoc bao nhieu vay?", "tháng 12/2025"),
    ],
)
def test_direct_revenue_classifier_resolves_one_period(text, period):
    result = classify_direct_revenue(text)
    assert (result.category, result.period_expression) == ("direct_revenue", period)


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("Doanh thu tháng 5/2026 tăng hay giảm bao nhiêu phần trăm?", "growth_or_comparison"),
        ("Trung bình mỗi đơn tháng 4/2026 mang về bao nhiêu doanh thu?", "average_order"),
        ("Ngày nào trong tháng 6/2025 doanh thu cao nhất?", "ranking_or_threshold"),
        ("Doanh thu của Bánh Chocopie trong tháng 6/2025?", "entity_specific"),
        ("Doanh thu 3 tháng liền nhau là bao nhiêu mỗi tháng?", "multi_period"),
    ],
)
def test_non_direct_revenue_categories_are_explicit(text, category):
    assert classify_direct_revenue(text).category == category


def test_train_monthly_planner_is_generic_across_verified_business_configs():
    for business_id in ("biz_102", "biz_103", "biz_104"):
        intent = plan_heuristic({
            "id": "fixture", "business_id": business_id,
            "question": "Cho tôi biết doanh thu tháng 4/2025.",
            "as_of_date": "2026-06-01",
        })
        assert intent.metric == "revenue"
        assert intent.period_expression == "tháng 4/2025"


def test_train_monthly_planner_fails_closed_for_average_order():
    with pytest.raises(PlannerFailure, match="average_order"):
        plan_heuristic({
            "id": "fixture", "business_id": "biz_102",
            "question": "Doanh thu trung bình mỗi đơn tháng 4/2025 là bao nhiêu?",
            "as_of_date": "2026-06-01",
        })


def test_public_direct_revenue_is_still_locked_in_group3():
    with pytest.raises(PlannerFailure):
        plan_heuristic({
            "id": "fixture", "business_id": "dev_002",
            "question": "Th 12/25 doanh thu cua quan duoc bao nhieu vay?",
            "as_of_date": "2026-05-24",
        })
