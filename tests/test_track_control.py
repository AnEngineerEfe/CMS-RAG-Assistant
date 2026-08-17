"""Doğal dil yönlendirme ve güvenli MCP işlem orkestrasyonu testleri."""

import unittest
from tempfile import TemporaryDirectory
from pathlib import Path

from src.cms_rag.application.track_control import TrackControlService
from src.cms_rag.domain.track_control import TrackIntent, TrackState, parse_track_request
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
