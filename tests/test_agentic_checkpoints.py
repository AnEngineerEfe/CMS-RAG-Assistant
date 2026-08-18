"""Bellek içi ve PostgreSQL LangGraph checkpoint kurulumunun birim testleri."""

import unittest
from unittest.mock import patch

from langgraph.checkpoint.memory import InMemorySaver

from src.cms_rag.application.agentic.checkpoints import (
    CheckpointConfigurationError,
    create_checkpoint_runtime,
)


class _FakeSaver:
    """PostgreSQL saver kurulum çağrısını ağsız izler."""

    def __init__(self, *, fail_setup: bool = False) -> None:
        self.fail_setup = fail_setup
        self.setup_calls = 0

    def setup(self) -> None:
        self.setup_calls += 1
        if self.fail_setup:
            raise RuntimeError("postgresql://admin:super-secret@localhost/cms")


class _FakeManager:
    """PostgresSaver context manager yaşam döngüsünü taklit eder."""

    def __init__(self, saver: _FakeSaver) -> None:
        self.saver = saver
        self.enter_calls = 0
        self.exit_calls = 0

    def __enter__(self):
        self.enter_calls += 1
        return self.saver

    def __exit__(self, exc_type, exc, traceback):
        del exc_type, exc, traceback
        self.exit_calls += 1


class _FakePostgresSaver:
    """Factory parametrelerini ve üretilen manager'ı testten erişilebilir tutar."""

    manager: _FakeManager
    received_dsn = ""

    @classmethod
    def from_conn_string(cls, dsn):
        cls.received_dsn = dsn
        return cls.manager


class AgenticCheckpointTests(unittest.TestCase):
    """Checkpoint seçimi, migration ve gizli bilgi sınırını doğrular."""

    def test_empty_dsn_uses_session_only_memory(self):
        runtime = create_checkpoint_runtime("  ")
        self.assertIsInstance(runtime.saver, InMemorySaver)
        self.assertFalse(runtime.persistent)
        self.assertEqual(runtime.backend, "memory")
        self.assertIn("oturumluk", runtime.display_name)

    def test_postgres_runtime_runs_setup_and_closes_once(self):
        saver = _FakeSaver()
        manager = _FakeManager(saver)
        _FakePostgresSaver.manager = manager
        with patch(
            "src.cms_rag.application.agentic.checkpoints._load_postgres_saver",
            return_value=_FakePostgresSaver,
        ):
            runtime = create_checkpoint_runtime("postgresql://localhost/cms")

        self.assertTrue(runtime.persistent)
        self.assertEqual(runtime.backend, "postgresql")
        self.assertEqual(saver.setup_calls, 1)
        self.assertEqual(manager.enter_calls, 1)
        self.assertIsNotNone(saver.serde)
        runtime.close()
        runtime.close()
        self.assertEqual(manager.exit_calls, 1)

    def test_connection_error_does_not_expose_password(self):
        saver = _FakeSaver(fail_setup=True)
        manager = _FakeManager(saver)
        _FakePostgresSaver.manager = manager
        with patch(
            "src.cms_rag.application.agentic.checkpoints._load_postgres_saver",
            return_value=_FakePostgresSaver,
        ):
            with self.assertRaises(CheckpointConfigurationError) as raised:
                create_checkpoint_runtime(
                    "postgresql://admin:super-secret@localhost/cms"
                )

        self.assertNotIn("super-secret", str(raised.exception))
        self.assertIn("CMS_RAG_CHECKPOINT_DSN", str(raised.exception))
        self.assertEqual(manager.exit_calls, 1)


if __name__ == "__main__":
    unittest.main()
