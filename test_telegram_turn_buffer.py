from src.services.telegram_turn_buffer import TelegramTurnBuffer


class FakeTask:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


def test_turn_buffer_batches_items_and_cancels_previous_task():
    buffer = TelegramTurnBuffer()
    tasks: list[FakeTask] = []

    def make_task() -> FakeTask:
        task = FakeTask()
        tasks.append(task)
        return task

    buffer.add("lead-1", item={"content": "[Фото]"}, message="first", task_factory=make_task)
    buffer.add("lead-1", item={"content": "[Фото]", "is_voice": True}, message="second", task_factory=make_task)
    buffer.add("lead-1", item={"content": "в таком стиле"}, message="third", task_factory=make_task)

    turn = buffer.pop("lead-1")

    assert turn is not None
    assert [item["content"] for item in turn.items] == ["[Фото]", "[Фото]", "в таком стиле"]
    assert turn.message == "first"
    assert turn.has_voice is True
    assert tasks[0].cancelled is True
    assert tasks[1].cancelled is True
    assert tasks[2].cancelled is False
    assert "lead-1" not in buffer
