import pytest

from datamate.planner.heuristic import plan_heuristic
from datamate.planner.validate import PlannerFailure
from datamate.wave1_group4_public import compare_to_baseline


@pytest.mark.parametrize(
    ("text", "period"),
    [
        ("Rieng ngay hom nay doanh thu quan la bao nhieu?", "hôm nay"),
        ("Hôm qua quán bán được nhiêu tiền rứa?", "hôm qua"),
        ("Doanh thu bữa qua của quán tổng cộng được bao nhiêu?", "hôm qua"),
        ("Doanh thu T1/2026 quán được bao nhiêu hỉ?", "tháng 1/2026"),
        ("Tổng doanh thu hôm qua quán được bao nhiêu?", "hôm qua"),
        ("5/25 quan thu ve bao nhieu doanh thu?", "tháng 5/2025"),
        ("Bữa nay quán bán được bao nhiêu tiền rồi?", "hôm nay"),
        ("Th 12/25 doanh thu cua quan duoc bao nhieu vay?", "tháng 12/2025"),
    ],
)
def test_eight_public_direct_revenue_phrasings(text, period):
    intent = plan_heuristic({
        "id": "fixture", "business_id": "dev_002", "question": text,
        "as_of_date": "2026-05-24",
    })
    assert (intent.family, intent.metric, intent.period_expression) == (
        "revenue", "revenue", period
    )


@pytest.mark.parametrize(
    "text",
    [
        "Doanh thu th8/2025 so voi thang lien truoc thay doi may %?",
        "6-2025 trung binh 1 don dem ve bao nhieu doanh thu?",
        "Thang 7 nam 2025 ngay nao ban dat nhat, tinh theo doanh thu?",
        "Tháng 10/2025 nhóm cà phê chiếm bao nhiêu % doanh thu?",
    ],
)
def test_public_revenue_excluded_families_stay_abstain(text):
    with pytest.raises(PlannerFailure):
        plan_heuristic({
            "id": "fixture", "business_id": "dev_002", "question": text,
            "as_of_date": "2026-05-24",
        })


def test_diff_accepts_only_expected_abstain_to_integer_number_changes():
    baseline = [
        {"id": "q1", "type": "abstain"},
        {"id": "q2", "type": "number", "answer": 2},
    ]
    candidate = [
        {"id": "q1", "type": "number", "answer": 10},
        {"id": "q2", "type": "number", "answer": 2},
    ]
    report = compare_to_baseline(baseline, candidate, {"q1"})
    assert report["actual_change_count"] == 1
    assert report["unexpected_changes"] == []
    assert report["missing_expected_changes"] == []
    assert report["all_changes_are_abstain_to_integer_number"] is True
    # Production acceptance additionally requires exactly eight expected changes.
    assert report["passed"] is False


def test_diff_rejects_change_outside_inventory():
    baseline = [{"id": "q1", "type": "abstain"}, {"id": "q2", "type": "abstain"}]
    candidate = [
        {"id": "q1", "type": "number", "answer": 1},
        {"id": "q2", "type": "number", "answer": 2},
    ]
    report = compare_to_baseline(baseline, candidate, {"q1"})
    assert report["passed"] is False
    assert [row["id"] for row in report["unexpected_changes"]] == ["q2"]
