import json
from types import SimpleNamespace

from src.services.price_objection_service import price_objection_service


def _lead_with_price(lo=900_000, hi=1_100_000):
    return SimpleNamespace(
        extracted_data=json.dumps(
            {
                "quiz": {
                    "price": {
                        "lo": lo,
                        "hi": hi,
                        "label": "900 тыс. ₽ – 1,1 млн ₽",
                    }
                }
            },
            ensure_ascii=False,
        )
    )


def test_price_objection_without_budget_asks_for_budget_orientir():
    text = "Добрый день, стоимость не подходит, спасибо"

    assert price_objection_service.looks_like_price_objection(text)

    reply = price_objection_service.build_reply(lead=_lead_with_price(), text=text)

    assert reply.budget_fit == "unknown"
    assert "на какой ориентир" in reply.text
    assert "Всего доброго" not in reply.text


def test_price_objection_near_budget_returns_to_measurement():
    reply = price_objection_service.build_reply(
        lead=_lead_with_price(),
        text="Ориентир до миллиона рублей",
    )

    assert reply.client_budget_rub == 1_000_000
    assert reply.budget_fit == "inside_range"
    assert "как раз рядом" in reply.text
    assert "ни к чему не обязывает" in reply.text
    assert "замер" in reply.text.lower()
    assert "пару ближайших окон" in reply.text


def test_price_objection_low_budget_stays_honest():
    reply = price_objection_service.build_reply(
        lead=_lead_with_price(),
        text="У нас бюджет до 500 тыс",
    )

    assert reply.client_budget_rub == 500_000
    assert reply.budget_fit == "below_range"
    assert "можем не попасть" in reply.text
