from src.services.ai_reply_quality_gate_service import ai_reply_quality_gate_service


def test_blocks_repeated_room_question_when_rooms_are_known():
    result = ai_reply_quality_gate_service.validate(
        text="Какие конкретно комнаты хотите ремонтировать?",
        client_text="Хотел бы ремонт санузла и детской",
        extracted_data={"renovation_zones": ["санузел", "детская"]},
        stage_next_action="direct_chat_qualification",
    )

    assert result.blocked is True
    assert "repeated_known_rooms" in result.issues
    assert "санузел и детская" in result.text
    assert "площад" in result.text.lower()


def test_blocks_fake_identity_before_client_sees_it():
    result = ai_reply_quality_gate_service.validate(
        text="Здравствуйте, я Александр. Какая площадь?",
        client_text="Нужен ремонт",
        extracted_data={},
        stage_next_action="direct_chat_qualification",
    )

    assert result.blocked is True
    assert "fake_identity" in result.issues
    assert "Александр" not in result.text


def test_blocks_multiple_questions_in_one_reply():
    result = ai_reply_quality_gate_service.validate(
        text="Какая площадь? Есть дизайн-проект? Когда старт?",
        client_text="Хочу ремонт",
        extracted_data={},
        stage_next_action="direct_chat_qualification",
    )

    assert result.blocked is True
    assert "too_many_questions" in result.issues
    assert result.text.count("?") == 1


def test_allows_good_contextual_reply():
    result = ai_reply_quality_gate_service.validate(
        text="По задаче понял: санузел и детская. Какая примерная площадь?",
        client_text="санузел и детская",
        extracted_data={"renovation_zones": ["санузел", "детская"]},
        stage_next_action="direct_chat_qualification",
    )

    assert result.blocked is False
    assert result.score == 100
