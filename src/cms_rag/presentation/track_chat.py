"""Sohbet içindeki güvenli MCP okuma, onay ve yazma deneyimini yönetir."""

from __future__ import annotations

from typing import Any

import streamlit as st

from ..application.track_control import PendingTrackAction
from ..domain.track_control import (
    SHIP_TYPE_LABELS,
    TrackField,
    TrackIntent,
    TrackRequest,
    TrackState,
    parse_confirmation,
    parse_track_correction,
    parse_track_request,
)
from ..infrastructure.mcp_track_client import McpTrackError
from .services import get_agentic_workflow, get_track_control_service


PENDING_ACTION_KEY = "pending_track_action"
PENDING_SUGGESTION_KEY = "pending_track_suggestion"
PENDING_CORRECTION_KEY = "pending_track_correction"
PENDING_AGENTIC_THREAD_KEY = "pending_track_agentic_thread"
PENDING_AGENTIC_COMPLETION_KEY = "pending_track_agentic_completion"


def handle_track_question(question: str) -> bool:
    """İz kontrol iletisini RAG'dan ayırır; okur veya onay bekleyen plana dönüştürür."""

    pending_correction = st.session_state.get(PENDING_CORRECTION_KEY)
    correction_target: TrackField | None = None
    correction_value: float | None = None
    if isinstance(pending_correction, tuple) and len(pending_correction) == 2:
        correction_target, correction_value = pending_correction
    elif isinstance(pending_correction, TrackField):
        correction_target = pending_correction
    request: TrackRequest | None = None
    if isinstance(correction_target, TrackField):
        fresh_request = parse_track_request(question)
        if fresh_request.intent != TrackIntent.NOT_TRACK:
            st.session_state.pop(PENDING_CORRECTION_KEY, None)
            request = fresh_request
        elif parse_confirmation(question) is False:
            st.session_state.pop(PENDING_CORRECTION_KEY, None)
            _append_assistant(
                "Sayısal değer düzeltmesi iptal edildi; hiçbir değer değiştirilmedi.",
                "MCP · DÜZELTME İPTALİ",
            )
            return True
        elif "?" in question or len(question.split()) > 7:
            st.session_state.pop(PENDING_CORRECTION_KEY, None)
            return False
        else:
            request = parse_track_correction(question, correction_target, correction_value)
            if request.intent != TrackIntent.AMBIGUOUS or request.suggested_ship_type:
                st.session_state.pop(PENDING_CORRECTION_KEY, None)

    suggested_type = st.session_state.get(PENDING_SUGGESTION_KEY)
    confirmation = parse_confirmation(question) if isinstance(suggested_type, str) else None
    if request is not None:
        pass
    elif confirmation is True:
        st.session_state.pop(PENDING_SUGGESTION_KEY, None)
        request = TrackRequest(TrackIntent.WRITE, ship_type=suggested_type)
    elif confirmation is False:
        st.session_state.pop(PENDING_SUGGESTION_KEY, None)
        _append_assistant(
            "Gemi tipi önerisi iptal edildi; hiçbir değer değiştirilmedi.",
            "MCP · ÖNERİ İPTALİ",
        )
        return True
    else:
        request = parse_track_request(question)
        if isinstance(suggested_type, str) and request.intent == TrackIntent.NOT_TRACK:
            # Kısa fakat tanınmayan bir cevapta öneriyi kaybetmeyiz. Açık yeni bir soru
            # ise kullanıcı konuyu değiştirmiş kabul edip normal RAG akışına bırakırız.
            if len(question.split()) <= 6 and "?" not in question:
                _append_assistant(
                    f"Yanıtınızı kesin onay veya ret olarak anlayamadım. "
                    f"{SHIP_TYPE_LABELS[suggested_type]} önerisini kabul ediyorsanız "
                    "örneğin “evet doğru”, “aynen” veya “kastettiğim buydu”; "
                    "reddediyorsanız “hayır” ya da “o değil” diyebilirsiniz.",
                    "MCP · ÖNERİ NETLEŞTİRME",
                )
                return True
            st.session_state.pop(PENDING_SUGGESTION_KEY, None)
        elif isinstance(suggested_type, str):
            # Kullanıcı önceki öneriye cevap vermek yerine yeni ve açık bir MCP komutu verdi.
            st.session_state.pop(PENDING_SUGGESTION_KEY, None)
    if request.intent == TrackIntent.NOT_TRACK:
        return False
    if request.intent == TrackIntent.AMBIGUOUS:
        suggestion_note = ""
        if request.suggested_ship_type:
            st.session_state[PENDING_SUGGESTION_KEY] = request.suggested_ship_type
            suggestion_note = (
                f" **Evet doğru**, **aynen** veya **kastettiğim buydu** gibi bir onay verirseniz "
                f"{SHIP_TYPE_LABELS[request.suggested_ship_type]} için onay planı hazırlanır; "
                "değer doğrudan değiştirilmez."
            )
        correction_note = ""
        if request.correction_target:
            st.session_state[PENDING_CORRECTION_KEY] = (
                request.correction_target,
                request.correction_value,
            )
            if request.correction_target == TrackField.UNSPECIFIED:
                correction_note = " Takip mesajında yalnızca `hız`, `yön` veya `gemi tipi` diyebilirsiniz."
            elif request.correction_target == TrackField.SHIP_TYPE:
                correction_note = " Yeni gemi tipini kısa bir takip mesajıyla yazabilirsiniz."
            else:
                field_name = "hız" if request.correction_target == TrackField.SPEED else "yön"
                correction_note = (
                    f" Yeni {field_name} değerini `100` veya `{field_name} 100 olsun` "
                    "gibi kısa bir takip mesajıyla yazabilirsiniz."
                )
        _append_assistant(
            request.reason
            + suggestion_note
            + correction_note
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

    completion = st.session_state.get(PENDING_AGENTIC_COMPLETION_KEY)
    if isinstance(completion, dict):
        with st.container(border=True):
            st.markdown(
                "<div class='answer-label'>AGENTIC · CHECKPOINT KURTARMA</div>",
                unsafe_allow_html=True,
            )
            st.warning(
                "MCP sonucu alındı fakat graph checkpoint'i tamamlanamadı. MCP işlemi "
                "tekrar uygulanmadan yalnızca kayıt devam ettirilecektir."
            )
            if st.button("Checkpoint devamını yeniden dene", type="primary"):
                if _resume_agentic_interrupt(
                    str(completion.get("decision", "failed")),
                    str(completion.get("answer", "")),
                ):
                    _append_assistant(
                        "Bekleyen agent checkpoint'i güvenli biçimde tamamlandı.",
                        "AGENTIC · CHECKPOINT KURTARILDI",
                    )
                st.rerun()
        return True

    action = st.session_state.get(PENDING_ACTION_KEY)
    if not isinstance(action, PendingTrackAction):
        return False
    with st.container(border=True):
        st.markdown("<div class='answer-label'>MCP · İŞLEM ONAYI</div>", unsafe_allow_html=True)
        st.markdown(f"**Planlanan değişiklik:** {action.summary()}")
        for warning in action.warnings:
            st.warning(warning)
        st.caption(
            "Henüz hiçbir değer değiştirilmedi. Onay sırasında yazma izni ve mevcut "
            "durum yeniden kontrol edilecektir."
        )
        approve, cancel, remainder = st.columns([1, 1, 3])
        with approve:
            approve_label = (
                "Geçerli değişiklikleri uygula"
                if action.partial
                else "Onayla ve uygula"
            )
            if st.button(approve_label, type="primary", use_container_width=True):
                _execute(action)
        with cancel:
            if st.button("İptal et", use_container_width=True):
                get_track_control_service().cancel(action)
                del st.session_state[PENDING_ACTION_KEY]
                content = "İşlem iptal edildi; hiçbir değer değiştirilmedi."
                _resume_agentic_interrupt("rejected", content)
                _append_assistant(content, "MCP · İPTAL")
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
        if action.warnings:
            notes = "\n".join(f"- {warning}" for warning in action.warnings)
            content += f"\n\n**İşlem notları:**\n{notes}"
        label = "MCP · DOĞRULANMIŞ İŞLEM"
        decision = "approved"
    except PermissionError as exception:
        content = f"İşlem uygulanmadı: {exception}"
        label = "MCP · YETKİ REDDİ"
        decision = "failed"
    except (McpTrackError, OSError, ValueError, RuntimeError) as exception:
        content = f"İşlem güvenli biçimde durduruldu: {_safe_error(exception)}"
        label = "MCP · İŞLEM HATASI"
        decision = "failed"
    del st.session_state[PENDING_ACTION_KEY]
    _resume_agentic_interrupt(decision, content)
    _append_assistant(content, label)
    st.rerun()


def _resume_agentic_interrupt(decision: str, answer: str) -> bool:
    """Varsa bekleyen LangGraph MCP turunu aynı thread üzerinde sonuçlandırır."""

    thread_id = st.session_state.get(PENDING_AGENTIC_THREAD_KEY)
    if not isinstance(thread_id, str) or not thread_id.strip():
        return True
    try:
        get_agentic_workflow().resume(
            thread_id,
            {"decision": decision, "answer": answer},
        )
    except Exception:  # Sunum sınırı; sürücü hatasının DSN/parola metni kullanıcıya taşınmaz.
        st.session_state[PENDING_AGENTIC_COMPLETION_KEY] = {
            "decision": decision,
            "answer": answer,
        }
        _append_assistant(
            "İşlem sonucu alındı ancak agent checkpoint'i tamamlanamadı. Veritabanı "
            "erişimini denetleyip ekrandaki güvenli yeniden deneme düğmesini kullanın.",
            "AGENTIC · CHECKPOINT UYARISI",
        )
        return False
    st.session_state.pop(PENDING_AGENTIC_THREAD_KEY, None)
    st.session_state.pop(PENDING_AGENTIC_COMPLETION_KEY, None)
    return True


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
