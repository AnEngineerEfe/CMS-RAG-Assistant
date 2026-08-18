"""Kullanıcı isteğini güvenli ve açıklanabilir agentic alt akışa yönlendirir."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ...domain.query import CMSQueryProcessor
from ...domain.track_control import TrackIntent, parse_track_request


class AgentRoute(str, Enum):
    """Ana grafiğin desteklediği kontrollü çalışma yollarını belirtir."""

    KNOWLEDGE = "knowledge"
    TRACK_CONTROL = "track_control"
    SAFE_REJECT = "safe_reject"


@dataclass(frozen=True)
class RouteDecision:
    """Yönlendirme sonucunu kullanıcıya açıklanabilir gerekçesiyle birlikte taşır."""

    route: AgentRoute
    reason: str


def decide_route(question: str) -> RouteDecision:
    """LLM'e bırakılmaması gereken güvenlik ve MCP ayrımını deterministik çözümler."""

    if not question.strip():
        return RouteDecision(AgentRoute.SAFE_REJECT, "Boş istek işleme alınmadı.")
    track_request = parse_track_request(question)
    if track_request.intent != TrackIntent.NOT_TRACK:
        return RouteDecision(
            AgentRoute.TRACK_CONTROL,
            "Canlı iz okuma, netleştirme veya yazma isteği algılandı.",
        )
    if CMSQueryProcessor.requests_restricted_information(question):
        return RouteDecision(
            AgentRoute.SAFE_REJECT,
            "Kamuya açık bilgi tabanının dışında kalan hassas veri talebi algılandı.",
        )
    return RouteDecision(
        AgentRoute.KNOWLEDGE,
        "Soru çevrimdışı ve kaynak kontrollü bilgi akışına yönlendirildi.",
    )
