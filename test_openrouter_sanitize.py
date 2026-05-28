import importlib.util
import sys
import types
from pathlib import Path


langfuse_stub = types.ModuleType("langfuse")
langfuse_stub.Langfuse = object
sys.modules.setdefault("langfuse", langfuse_stub)

module_path = Path(__file__).parent / "src" / "services" / "openrouter_service.py"
spec = importlib.util.spec_from_file_location("openrouter_service_for_test", module_path)
openrouter_module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(openrouter_module)
OpenRouterService = openrouter_module.OpenRouterService


def test_sanitize_lead_message_unescapes_newlines():
    service = OpenRouterService()

    text = service._sanitize_lead_message("Цена 4,0 – 4,9 млн рублей.\\n\\nЧтобы составить точную смету, нужен замер.")

    assert "\\n" not in text
    assert "\n\n" in text
