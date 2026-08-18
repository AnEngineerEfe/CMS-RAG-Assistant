"""LangGraph checkpoint altyapısını güvenli ve değiştirilebilir biçimde kurar."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


class CheckpointConfigurationError(RuntimeError):
    """Yapılandırılmış kalıcı checkpoint altyapısı kurulamadığında üretilir."""


@dataclass
class CheckpointRuntime:
    """Checkpointer ile ona ait bağlantı yaşam döngüsünü birlikte taşır."""

    saver: Any
    backend: str
    persistent: bool
    _manager: AbstractContextManager[Any] | None = field(default=None, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def display_name(self) -> str:
        """Arayüze parola veya bağlantı ayrıntısı sızdırmayan durum adını verir."""

        return "PostgreSQL · kalıcı" if self.persistent else "Bellek içi · oturumluk"

    def close(self) -> None:
        """Varsa PostgreSQL bağlantı bağlamını yalnızca bir kez kapatır."""

        if self._closed:
            return
        self._closed = True
        if self._manager is not None:
            self._manager.__exit__(None, None, None)


def create_checkpoint_runtime(dsn: str | None = None) -> CheckpointRuntime:
    """DSN yoksa bellek, varsa kurulumunu doğruladığı PostgreSQL saver döndürür."""

    serializer = JsonPlusSerializer(allowed_msgpack_modules=[])
    normalized_dsn = (dsn or "").strip()
    if not normalized_dsn:
        return CheckpointRuntime(
            saver=InMemorySaver(serde=serializer),
            backend="memory",
            persistent=False,
        )

    postgres_saver = _load_postgres_saver()
    manager = None
    entered = False
    try:
        manager = postgres_saver.from_conn_string(normalized_dsn)
        saver = manager.__enter__()
        entered = True
        # 3.1.x sürümündeki `from_conn_string` serde parametresi kabul etmez.
        # Checkpoint yazılmadan önce güvenli serializer'ı açıkça bağlarız.
        saver.serde = serializer
        saver.setup()
    except Exception:
        try:
            if entered and manager is not None:
                manager.__exit__(None, None, None)
        finally:
            # Sürücü hataları bağlantı dizesini/parolayı içerebildiği için
            # asıl istisna metnini kullanıcı arayüzüne taşımıyoruz.
            raise CheckpointConfigurationError(
                "LangGraph PostgreSQL checkpoint bağlantısı kurulamadı. "
                "CMS_RAG_CHECKPOINT_DSN değerini, veritabanı erişimini ve yetkileri denetleyin."
            ) from None
    return CheckpointRuntime(
        saver=saver,
        backend="postgresql",
        persistent=True,
        _manager=manager,
    )


def _load_postgres_saver():
    """İsteğe bağlı PostgreSQL paketini yalnızca kalıcı mod seçilince yükler."""

    try:
        from langgraph.checkpoint.postgres import PostgresSaver
    except ImportError:
        raise CheckpointConfigurationError(
            "PostgreSQL checkpoint modu için langgraph-checkpoint-postgres paketi kurulu değil. "
            "Bağımlılıkları requirements.txt üzerinden yeniden kurun."
        ) from None
    return PostgresSaver
