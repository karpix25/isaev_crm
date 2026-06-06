from src.services.quiz_hot_lead_service import quiz_hot_lead_service


def test_quiz_hot_lead_requires_value_area_budget_and_near_deadline():
    decision = quiz_hot_lead_service.evaluate(
        {
            "area": "sm",
            "budget": "b2",
            "deadline": "soon",
            "type": "apt",
        }
    )

    assert decision.is_hot is True
    assert "40–70" in decision.reason
    assert "1–2" in decision.reason


def test_quiz_hot_lead_accepts_strong_area_and_budget_without_near_deadline():
    decision = quiz_hot_lead_service.evaluate(
        {
            "area": "lg",
            "budget": "b4",
            "deadline": "later",
            "type": "house",
        }
    )

    assert decision.is_hot is True
    assert "крупный объект" in decision.reason


def test_quiz_hot_lead_keeps_small_low_budget_lead_cold():
    decision = quiz_hot_lead_service.evaluate(
        {
            "area": "xs",
            "budget": "b1",
            "deadline": "later",
            "type": "apt",
        }
    )

    assert decision.is_hot is False
