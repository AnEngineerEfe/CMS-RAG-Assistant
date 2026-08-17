"""MCP iz okumalarını ve onaylı yazma işlemlerini uygulama düzeyinde orkestre eder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..domain.track_control import TrackRequest, TrackState


class TrackGateway(Protocol):
    """Uygulama katmanının MCP taşımasına bağımlı olmadan kullandığı kapıdır."""

    def get_state(self) -> TrackState:
        """Canlı iz durumunu döndürür."""

    def get_write_policy(self) -> bool:
        """Operatörün MCP yazma iznini döndürür."""

    def set_state(self, state: TrackState) -> TrackState:
        """Üç alanı tek bir atomik araç çağrısıyla günceller."""


class TrackAudit(Protocol):
    """İşlem metnini saklamadan MCP sonucunu kalıcılaştıran kayıt kapısıdır."""

    def record(
        self,
        *,
        outcome: str,
        before: TrackState,
        after: TrackState,
        detail: str = "",
    ) -> None:
        """İşlemin sonucu ile önce/sonra durumunu kaydeder."""


@dataclass(frozen=True)
class PendingTrackAction:
    """Kullanıcı onayı bekleyen, mevcut ve hedef durumu sabitleyen işlem planıdır."""

    before: TrackState
    after: TrackState

    def summary(self) -> str:
        """Arayüzde açıkça gösterilecek değişiklik özetini üretir."""

        changes: list[str] = []
        if self.before.speed_knots != self.after.speed_knots:
            changes.append(f"Hız: {self.before.speed_knots:g} → {self.after.speed_knots:g} knot")
        if self.before.heading_degrees != self.after.heading_degrees:
            changes.append(
                f"Yön: {self.before.heading_degrees}° → {self.after.heading_degrees}°"
            )
        if self.before.ship_type != self.after.ship_type:
            changes.append(
                f"Gemi tipi: {self.before.ship_type_label} → {self.after.ship_type_label}"
            )
        return " · ".join(changes) or "Değerlerde değişiklik yok."


class TrackControlService:
    """Okuma, planlama, operatör izni ve geri-okuma doğrulamasını tek yerde uygular."""

    def __init__(self, gateway: TrackGateway, audit: TrackAudit | None = None) -> None:
        """Taşıma ayrıntılarını kapı arayüzünün arkasında tutar."""

        self.gateway = gateway
        self.audit = audit

    def read_state(self) -> TrackState:
        """MCP üzerinden canlı durumu salt okunur biçimde alır."""

        return self.gateway.get_state()

    def prepare(self, request: TrackRequest) -> PendingTrackAction:
        """Kısmi kullanıcı girdisini mevcut durumla birleştirip atomik işlem planı üretir."""

        before = self.gateway.get_state()
        after = TrackState(
            speed_knots=before.speed_knots if request.speed_knots is None else request.speed_knots,
            heading_degrees=(
                before.heading_degrees
                if request.heading_degrees is None
                else request.heading_degrees
            ),
            ship_type=before.ship_type if request.ship_type is None else request.ship_type,
            ship_type_label=(
                before.ship_type_label
                if request.ship_type is None
                else _ship_label(request.ship_type)
            ),
        )
        if before == after:
            raise ValueError("İstenen değerler zaten uygulanmış durumda.")
        return PendingTrackAction(before, after)

    def execute(self, action: PendingTrackAction) -> TrackState:
        """Onaylı planı izin kontrolüyle uygular ve geri okuyarak sonucunu doğrular."""

        if not self.gateway.get_write_policy():
            self._record("permission_denied", action)
            raise PermissionError("MCP/model yazma izni operatör tarafından kilitli.")
        current = self.gateway.get_state()
        if current != action.before:
            self._record("stale_confirmation", action)
            raise RuntimeError(
                "İz değerleri onay beklerken değişti; güvenlik için işlem iptal edildi."
            )
        written = self.gateway.set_state(action.after)
        verified = self.gateway.get_state()
        if written != action.after or verified != action.after:
            self._record("verification_failed", action)
            raise RuntimeError("MCP güncellemesi geri-okuma doğrulamasını geçemedi.")
        self._record("verified", action)
        return verified

    def cancel(self, action: PendingTrackAction) -> None:
        """Kullanıcı tarafından iptal edilen planı yazma yapmadan audit kaydına geçirir."""

        self._record("cancelled", action)

    def _record(self, outcome: str, action: PendingTrackAction) -> None:
        """Audit depolama hatasının kontrol işlemini bozmasına izin vermeden kayıt oluşturur."""

        if self.audit is None:
            return
        try:
            self.audit.record(outcome=outcome, before=action.before, after=action.after)
        except OSError:
            return


def _ship_label(ship_type: str) -> str:
    """Alan enum değerini kullanıcıya gösterilen Türkçe etikete dönüştürür."""

    from ..domain.track_control import SHIP_TYPE_LABELS

    return SHIP_TYPE_LABELS[ship_type]
