import ast
import asyncio
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock


def _load_knowledge_service_class():
    module_path = Path(__file__).parent / "src" / "services" / "knowledge_service.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    class_nodes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "KnowledgeService"]
    module = ast.Module(body=class_nodes, type_ignores=[])
    ast.fix_missing_locations(module)

    namespace = {
        "List": list,
        "Optional": object,
        "AsyncSession": object,
        "KnowledgeItem": SimpleNamespace(
            id="id",
            org_id="org_id",
            lead_id="lead_id",
            category="category",
            embedding=SimpleNamespace(cosine_distance=lambda _embedding: 0),
            content="content",
        ),
        "openrouter_service": SimpleNamespace(generate_embeddings=AsyncMock()),
        "select": lambda *args, **kwargs: FakeStatement(),
        "and_": lambda *args, **kwargs: ("and", args),
        "func": SimpleNamespace(
            count=lambda _value: "count",
            websearch_to_tsquery=lambda *_args: "ts_query",
            to_tsvector=lambda *_args: SimpleNamespace(op=lambda _op: lambda _query: True),
            ts_rank=lambda *_args: SimpleNamespace(desc=lambda: "rank_desc"),
        ),
    }
    exec(compile(module, str(module_path), "exec"), namespace)
    return namespace["KnowledgeService"], namespace["openrouter_service"]


class FakeStatement:
    def where(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self


class FakeEmptyCountResult:
    def scalar_one(self):
        return 0


class FakeDb:
    def __init__(self):
        self.execute = AsyncMock(return_value=FakeEmptyCountResult())


def test_search_knowledge_skips_embedding_when_base_is_empty():
    KnowledgeService, openrouter_service = _load_knowledge_service_class()
    db = FakeDb()

    docs = asyncio.run(
        KnowledgeService.search_knowledge(
            db=db,
            org_id=uuid.uuid4(),
            query="есть портфолио?",
            limit=3,
        )
    )

    assert docs == []
    assert db.execute.await_count == 1
    assert openrouter_service.generate_embeddings.await_count == 0
