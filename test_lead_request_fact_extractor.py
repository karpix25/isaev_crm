from src.services.lead_request_fact_extractor import lead_request_fact_extractor


def test_extracts_renovation_zones_from_free_text_request():
    facts = lead_request_fact_extractor.extract(
        "Хотел бы поинтересоваться ремонтом санузла и детской комнаты. Что-то в таком стиле."
    )

    assert facts["renovation_zones"] == ["санузел", "детская"]
    assert facts["rooms_description"] == "санузел, детская"
    assert facts["design_reference_provided"] is True
    assert "санузел, детская" in facts["client_request_summary"]


def test_merges_new_zones_without_losing_existing_context():
    merged = lead_request_fact_extractor.merge(
        {"renovation_zones": ["санузел"], "telegram_business_chat": {"chat_id": 123}},
        {"renovation_zones": ["детская"], "design_reference_provided": True},
    )

    assert merged["renovation_zones"] == ["санузел", "детская"]
    assert merged["rooms_description"] == "санузел, детская"
    assert merged["telegram_business_chat"] == {"chat_id": 123}
    assert merged["design_reference_provided"] is True
