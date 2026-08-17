"""Sohbet içindeki güvenli MCP okuma, onay ve yazma deneyimini yönetir."""

from __future__ import annotations

from typing import Any

import streamlit as st

from ..application.track_control import PendingTrackAction
from ..domain.track_control import TrackIntent, TrackState, parse_track_request
from ..infrastructure.mcp_track_client import McpTrackError
from .services import get_track_control_service


PENDING_ACTION_KEY = "pending_track_action"


def handle_track_question(question: str) -> bool:
    """İz kontrol iletisini RAG'dan ayırır; okur veya onay bekleyen plana dönüştürür."""

    request = parse_track_request(question)
    if request.intent == TrackIntent.NOT_TRACK:
        return False
    if request.intent == TrackIntent.AMBIGUOUS:
        _append_assistant(
            request.reason
            + " Geçerli örnekler: “Hızı 24,5 knot yap”, “Yönü 270 derece yap” "
            "veya “Gemi tipini fırkateyn yap” şeklindedir.",
            "MCP · KOMUT DOĞRULAMA",
        )
        return True
    try:
        service = get_track_control_service()
        if request.intent == TrackIntent.READ:
            state = service.read_state()
            _append_assistant(_state_text(state), "MCP · CANLI DURUM")
        else:
            st.session_state[PENDING_ACTION_KEY] = service.prepare(request)
    except ValueError as exception:
        _append_assistant(_safe_error(exception), "MCP · GEÇERSİZ DEĞER")
    except (McpTrackError, OSError) as exception:
        _append_assistant(_safe_error(exception), "MCP · BAĞLANTI HATASI")
    except RuntimeError as exception:
        _append_assistant(_safe_error(exception), "MCP · İŞLEM HATASI")
    return True


def render_pending_track_action() -> bool:
    """Bekleyen yazmayı önce/sonra özetiyle gösterir ve açık onay veya iptal ister."""

    action = st.session_state.get(PENDING_ACTION_KEY)
    if not isinstance(action, PendingTrackAction):
        return False
    with st.container(border=True):
        st.markdown("<div class='answer-label'>MCP · İŞLEM ONAYI</div>", unsafe_allow_html=True)
        st.markdown(f"**Planlanan değişiklik:** {action.summary()}")
        st.caption(
            "Henüz hiçbir değer değiştirilmedi. Onay sırasında yazma izni ve mevcut "
            "durum yeniden kontrol edilecektir."
        )
        approve, cancel, remainder = st.columns([1, 1, 3])
        with approve:
            if st.button("Onayla ve uygula", type="primary", use_container_width=True):
                _execute(action)
        with cancel:
            if st.button("İptal et", use_container_width=True):
                get_track_control_service().cancel(action)
                del st.session_state[PENDING_ACTION_KEY]
                _append_assistant("İşlem iptal edildi; hiçbir değer değiştirilmedi.", "MCP · İPTAL")
                st.rerun()
        with remainder:
            st.caption("Operatör onayı olmadan `set_*` aracı çağrılmaz.")
    return True


def _execute(action: PendingTrackAction) -> None:
    """Onaylı işlemi uygular, geri-okuma sonucunu konuşma geçmişine ekler."""

    try:
        verified = get_track_control_service().execute(action)
        content = (
            "İşlem uygulandı ve MCP üzerinden geri okunarak doğrulandı.\n\n"
            + _state_text(verified)
        )
        label = "MCP · DOĞRULANMIŞ İŞLEM"
    except PermissionError as exception:
        content = f"İşlem uygulanmadı: {exception}"
        label = "MCP · YETKİ REDDİ"
    except (McpTrackError, OSError, ValueError, RuntimeError) as exception:
        content = f"İşlem güvenli biçimde durduruldu: {_safe_error(exception)}"
        label = "MCP · İŞLEM HATASI"
    del st.session_state[PENDING_ACTION_KEY]
    _append_assistant(content, label)
    st.rerun()


def _state_text(state: TrackState) -> str:
    """Canlı durum nesnesini kısa ve sunuma uygun bir cevap olarak biçimlendirir."""

    return (
        f"**Hız:** {state.speed_knots:g} knot  \n"
        f"**Yön:** {state.heading_degrees}°  \n"
        f"**İz / gemi tipi:** {state.ship_type_label} (`{state.ship_type}`)"
    )


def _append_assistant(content: str, label: str) -> None:
    """MCP cevabını RAG kanıtı gibi göstermeden ortak sohbet geçmişine ekler."""

    message: dict[str, Any] = {
        "role": "assistant",
        "content": content,
        "sources": [],
        "label": label,
        "channel": "mcp",
    }
    st.session_state.messages.append(message)


def _safe_error(exception: Exception) -> str:
    """Teknik hatayı gizlemeden fakat gereksiz yığın izi vermeden kullanıcıya aktarır."""

    return str(exception).strip() or exception.__class__.__name__
