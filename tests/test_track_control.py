"""Doğal dil yönlendirme ve güvenli MCP işlem orkestrasyonu testleri."""

import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from src.cms_rag.application.track_control import TrackControlService
from src.cms_rag.domain.track_control import (
    TrackField,
    TrackIntent,
    TrackState,
    parse_confirmation,
    parse_track_correction,
    parse_track_request,
)
from src.cms_rag.infrastructure.mcp_audit import McpAuditStore


class FakeTrackGateway:
    """Uygulama servisini taşıma ayrıntılarından bağımsız sınayan bellek içi kapı."""

    def __init__(self) -> None:
        """Başlangıç durumu, yetki ve çağrı sayaçlarını hazırlar."""

        self.state = TrackState(10.0, 90, "KORVET", "Korvet")
        self.write_enabled = True
        self.write_count = 0

    def get_state(self) -> TrackState:
        """Mevcut bellek durumunu döndürür."""

        return self.state

    def get_write_policy(self) -> bool:
        """Operatör yazma politikasını döndürür."""

        return self.write_enabled

    def set_state(self, state: TrackState) -> TrackState:
        """Atomik yazmayı taklit edip çağrı sayısını artırır."""

        self.write_count += 1
        self.state = state
        return state


class TrackRequestTests(unittest.TestCase):
    """Yalnız açık uygulama komutlarının MCP kanalına yönelmesini doğrular."""

    def test_parses_full_turkish_write_command(self):
        """Virgüllü hız, yön ve gemi tipini tek istekten çıkarır."""

        request = parse_track_request(
            "İzin hızını 24,5 knot, yönünü 270 derece ve tipini fırkateyn yap."
        )
        self.assertEqual(request.intent, TrackIntent.WRITE)
        self.assertEqual(request.speed_knots, 24.5)
        self.assertEqual(request.heading_degrees, 270)
        self.assertEqual(request.ship_type, "FIRKATEYN")

    def test_routes_direct_live_read_but_not_general_cms_question(self):
        """Canlı değer sorusunu okur, kavramsal hız/yön sorusunu RAG'a bırakır."""

        self.assertEqual(
            parse_track_request("İz durumunu göster").intent,
            TrackIntent.READ,
        )
        self.assertEqual(
            parse_track_request("İz yönetiminde hız ve yön nasıl işlenir?").intent,
            TrackIntent.NOT_TRACK,
        )

    def test_rejects_write_without_an_explicit_value(self):
        """Belirsiz değiştirme isteğinin hiçbir araca dönüşmemesini sağlar."""

        request = parse_track_request("Uygulamadaki iz hızını değiştir")
        self.assertEqual(request.intent, TrackIntent.AMBIGUOUS)

    def test_generic_track_value_asks_which_field_instead_of_using_rag(self):
        """`izi 101 yap` ifadesini RAG'a bırakmadan alan netleştirmesi ister."""

        request = parse_track_request("Bu sefer izi 101 yap")
        self.assertEqual(request.intent, TrackIntent.AMBIGUOUS)
        self.assertIn("Hızı mı, yönü mü", request.reason)

    def test_filler_word_keeps_out_of_range_speed_visible(self):
        """Alanla sayı arasındaki `pardon` sözcüğüne rağmen gerçek değeri raporlar."""

        request = parse_track_request("Hızı pardon 101 yap")
        self.assertEqual(request.intent, TrackIntent.AMBIGUOUS)
        self.assertEqual(request.correction_target, TrackField.SPEED)
        self.assertIn("101 knot", request.reason)
        self.assertIn("0–100", request.reason)

    def test_short_numeric_follow_up_completes_pending_speed_correction(self):
        """Yalnız `100` yanıtını bekleyen hız düzeltmesine bağlar."""

        request = parse_track_correction("tamam 100 olsun", TrackField.SPEED)
        self.assertEqual(request.intent, TrackIntent.WRITE)
        self.assertEqual(request.speed_knots, 100)

    def test_heading_and_ship_type_use_the_same_follow_up_resolver(self):
        """Ortak düzeltme mekanizmasının yön ve gemi tipi alanlarında da çalıştığını doğrular."""

        heading = parse_track_correction("270 olsun", TrackField.HEADING)
        ship = parse_track_correction("korvet", TrackField.SHIP_TYPE)
        self.assertEqual(heading.intent, TrackIntent.WRITE)
        self.assertEqual(heading.heading_degrees, 270)
        self.assertEqual(ship.intent, TrackIntent.WRITE)
        self.assertEqual(ship.ship_type, "KORVET")

    def test_unspecified_track_value_can_be_bound_to_a_field_then_revalidated(self):
        """`izi 101 yap` ardından `hız` denince saklanan değeri güvenli aralıkta yeniden sınar."""

        ambiguous = parse_track_request("Bu sefer izi 101 yap")
        rebound = parse_track_correction(
            "hız",
            ambiguous.correction_target,
            ambiguous.correction_value,
        )
        self.assertEqual(ambiguous.correction_target, TrackField.UNSPECIFIED)
        self.assertEqual(ambiguous.correction_value, 101)
        self.assertEqual(rebound.intent, TrackIntent.AMBIGUOUS)
        self.assertEqual(rebound.correction_target, TrackField.SPEED)
        self.assertIn("101 knot", rebound.reason)

    def test_missing_ship_type_accepts_a_short_valid_type_follow_up(self):
        """Eksik gemi tipi komutunu izinli bir kısa değerle tamamlar."""

        missing = parse_track_request("Gemi tipini değiştir")
        corrected = parse_track_correction("denizaltı", missing.correction_target)
        self.assertEqual(missing.correction_target, TrackField.SHIP_TYPE)
        self.assertEqual(corrected.intent, TrackIntent.WRITE)
        self.assertEqual(corrected.ship_type, "DENIZALTI")

    def test_ship_type_follow_up_typo_moves_to_the_common_suggestion_flow(self):
        """Gemi tipi düzeltmesindeki yazım hatasını da güvenli öneriye dönüştürür."""

        request = parse_track_correction("firakteyn", TrackField.SHIP_TYPE)
        self.assertEqual(request.intent, TrackIntent.AMBIGUOUS)
        self.assertEqual(request.suggested_ship_type, "FIRKATEYN")
        self.assertIn("demek istemiş olabilir misiniz", request.reason)

    def test_separates_valid_fields_when_ship_type_is_unknown(self):
        """Tanınmayan tipi dışarıda bırakıp geçerli hız ve yönü ayrıca onaya sunar."""

        request = parse_track_request(
            "İzin hızını 100 knot, yönünü 270 derece ve tipini sancar yap"
        )
        self.assertEqual(request.intent, TrackIntent.PARTIAL_WRITE)
        self.assertEqual(request.speed_knots, 100)
        self.assertEqual(request.heading_degrees, 270)
        self.assertIsNone(request.ship_type)
        self.assertIn("sancar", " ".join(request.warnings))
        self.assertIn("Fırkateyn", " ".join(request.warnings))

    def test_reports_every_invalid_field_in_one_response(self):
        """Birleşik komuttaki hız ve gemi tipi hatalarını birlikte açıklar."""

        request = parse_track_request(
            "İzin hızını 300 knot, yönünü 270 derece ve tipini sancar yap"
        )
        self.assertEqual(request.intent, TrackIntent.PARTIAL_WRITE)
        self.assertIsNone(request.speed_knots)
        self.assertEqual(request.heading_degrees, 270)
        warnings = " ".join(request.warnings)
        self.assertIn("300 knot", warnings)
        self.assertIn("sancar", warnings)

    def test_individual_ship_type_update_is_supported(self):
        """Üç alanı birlikte yazma zorunluluğu olmadan yalnız gemi tipini çözümler."""

        request = parse_track_request("Gemi tipini fırkateyn yap")
        self.assertEqual(request.intent, TrackIntent.WRITE)
        self.assertIsNone(request.speed_knots)
        self.assertIsNone(request.heading_degrees)
        self.assertEqual(request.ship_type, "FIRKATEYN")

    def test_typo_suggests_nearest_ship_type_without_applying_it(self):
        """Yakın yazım hatasında kullanıcıya seçenek önerir fakat otomatik düzeltme yapmaz."""

        request = parse_track_request("Gemi tipini firakteyn yap")
        self.assertEqual(request.intent, TrackIntent.AMBIGUOUS)
        self.assertIn("Fırkateyn", request.reason)
        self.assertIn("demek istemiş olabilir misiniz", request.reason)
        self.assertEqual(request.suggested_ship_type, "FIRKATEYN")

    def test_known_ship_type_is_an_unambiguous_shorthand_command(self):
        """Alan adını tekrar yazmadan `muhrip yap` ifadesini gemi tipi komutu kabul eder."""

        request = parse_track_request("muhrip yap")
        self.assertEqual(request.intent, TrackIntent.WRITE)
        self.assertEqual(request.ship_type, "MUHRIP")

    def test_short_confirmation_answers_are_statefully_recognized(self):
        """Bekleyen öneri için doğal kısa onay ve ret sözcüklerini ayırır."""

        self.assertIs(parse_confirmation("evet"), True)
        self.assertIs(parse_confirmation("Evet doğru, onu demek istedim"), True)
        self.assertIs(parse_confirmation("Aynen ya, tam olarak buydu!"), True)
        self.assertIs(parse_confirmation("Heh işte, doğru bildin"), True)
        self.assertIs(parse_confirmation("Olabilir, devam et"), True)
        self.assertIs(parse_confirmation("hayır"), False)
        self.assertIs(parse_confirmation("Yok abi, o değil"), False)
        self.assertIsNone(parse_confirmation("Emin değilim"))
        self.assertIsNone(parse_confirmation("Doğru mu acaba?"))
        self.assertIsNone(parse_confirmation("ADVENT nedir?"))

    def test_heading_is_normalized_to_its_principal_angle(self):
        """Negatif ve bir turdan büyük yönleri eşdeğer 0–359 esas açısına dönüştürür."""

        negative = parse_track_request("Yönü -10 derece yap")
        overflow = parse_track_request("Yönü 725 derece yap")
        self.assertEqual(negative.intent, TrackIntent.WRITE)
        self.assertEqual(negative.heading_degrees, 350)
        self.assertIn("-10°", " ".join(negative.warnings))
        self.assertEqual(overflow.heading_degrees, 5)
        self.assertIn("725°", " ".join(overflow.warnings))

    def test_domain_rejects_values_outside_safe_ranges(self):
        """MCP çağrısından önce hız ve yön sınırlarını uygular."""

        with self.assertRaises(ValueError):
            TrackState(101.0, 0, "BELIRSIZ", "Belirsiz")
        with self.assertRaises(ValueError):
            TrackState(10.0, 361, "BELIRSIZ", "Belirsiz")


class TrackControlServiceTests(unittest.TestCase):
    """Onay öncesi planlama, yetki ve yarış durumu güvenliğini sınar."""

    def setUp(self):
        """Her test için temiz kapı ve uygulama servisi oluşturur."""

        self.gateway = FakeTrackGateway()
        self.service = TrackControlService(self.gateway)

    def test_prepare_does_not_write_and_execute_verifies_result(self):
        """Planlamada yan etki olmadığını, onaydan sonra tek atomik yazma yapıldığını kanıtlar."""

        request = parse_track_request("Hızı 24,5 knot yap")
        action = self.service.prepare(request)
        self.assertEqual(self.gateway.write_count, 0)
        self.assertEqual(action.after.speed_knots, 24.5)

        verified = self.service.execute(action)
        self.assertEqual(self.gateway.write_count, 1)
        self.assertEqual(verified.speed_knots, 24.5)

    def test_operator_lock_rejects_write_but_read_stays_available(self):
        """Yazma kilidinin okumayı etkilemeden işlemi reddetmesini sağlar."""

        action = self.service.prepare(parse_track_request("Yönü 180 derece yap"))
        self.gateway.write_enabled = False
        self.assertEqual(self.service.read_state(), self.gateway.state)
        with self.assertRaises(PermissionError):
            self.service.execute(action)
        self.assertEqual(self.gateway.write_count, 0)

    def test_stale_confirmation_is_cancelled(self):
        """Onay beklerken operatör değişikliği olmuşsa eski planın uygulanmasını engeller."""

        action = self.service.prepare(parse_track_request("Yönü 180 derece yap"))
        self.gateway.state = TrackState(12.0, 90, "KORVET", "Korvet")
        with self.assertRaises(RuntimeError):
            self.service.execute(action)
        self.assertEqual(self.gateway.write_count, 0)

    def test_audit_stores_outcome_without_user_prompt(self):
        """Kalıcı MCP kaydında sonuç ve durum bulunurken serbest komut metni bulunmaz."""

        with TemporaryDirectory() as directory:
            audit = McpAuditStore(Path(directory))
            service = TrackControlService(self.gateway, audit)
            action = service.prepare(parse_track_request("Hızı 25 knot yap"))
            service.execute(action)
            event = audit.recent(1)[0]

        self.assertEqual(event["outcome"], "verified")
        self.assertEqual(event["after"]["speedKnots"], 25.0)
        self.assertNotIn("prompt", event)
        self.assertNotIn("question", event)


if __name__ == "__main__":
    unittest.main()
