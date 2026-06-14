from src.services.direct_qualification_service import build_next_prompt


def test_first_direct_qualification_prompt_does_not_introduce_fake_manager_name():
    prompt = build_next_prompt({}, company_name="ISAEV GROUP")

    assert prompt
    assert "Александр" not in prompt.text
    assert "Я менеджер" not in prompt.text
    assert prompt.text.startswith("Чтобы дать нормальную вилку")
