"""Belgede açıkça bulunan sık sorular için hızlı ve kaynaklı cevap kuralları."""

from __future__ import annotations

import unicodedata

from .models import Chunk, SearchHit


class EvidenceResponder:
    """Model çağrısı gerektirmeyen, kanıtı kesin cevap şablonlarını uygular."""

    @staticmethod
    def answer(question: str, history: list[dict[str, str]], chunks: list[Chunk]) -> tuple[str, list[SearchHit]] | None:
        """Soru bir güvenli şablonla eşleşirse cevap ve kanıtlarını, aksi hâlde None döndürür."""

        normalized = EvidenceResponder._normalise(question)
        previous = EvidenceResponder._normalise(history[-1]["question"]) if history else ""
        conversation = " ".join(
            EvidenceResponder._normalise(f"{item['question']} {item['answer']}") for item in history
        )

        # NATO kuralı yalnız açık kaynak koleksiyonundaki doğrulanmış ifadeyle çalışabilir.
        asks_interoperability = any(
            marker in normalized
            for marker in (
                "birlikte calisabilirlik",
                "interoperability",
                "veri merkezli",
                "data centric",
            )
        )
        nato_source = EvidenceResponder._find(chunks, "Alliance Data Sharing Ecosystem")
        if asks_interoperability and nato_source and nato_source.collection == "open_source":
            return (
                "NATO'nun dijital birlikte \u00e7al\u0131\u015fabilirlik yakla\u015f\u0131m\u0131; sens\u00f6rleri, karar "
                "vericileri, akt\u00f6rleri ve efekt\u00f6rleri g\u00fcvenli bir dijital omurga \u00fczerinden ba\u011flamay\u0131 "
                "ve birlikte \u00e7al\u0131\u015fabilir verinin m\u00fcttefikler ile g\u00fcvenilir akt\u00f6rler aras\u0131nda "
                "payla\u015f\u0131lmas\u0131n\u0131 hedefler. Veri-merkezli y\u00f6neti\u015fim; veri egemenli\u011fi ve ulusal "
                "d\u00fczenlemeleri korurken karar deste\u011fini ve operasyonel verimlili\u011fi geli\u015ftirir "
                "[SOURCE 1].",
                [SearchHit(nato_source, 1.0)],
            )

        # Önceden küratörlenmiş güncel araştırma paketindeki sık sorular, çalışma
        # anında LLM beklemeden ilgili PDF kanıtına bağlanır.
        asks_advent_ai = (
            any(marker in normalized for marker in ("advent ai", "advent-ai"))
            and any(marker in normalized for marker in ("operator", "destek", "bilissel", "ne yapar"))
        )
        advent_ai_source = EvidenceResponder._find(chunks, "bilişsel yük")
        if asks_advent_ai and advent_ai_source:
            return (
                "ADVENT-AI; operatörün bilişsel yükünü azaltmayı, karar süreçlerini "
                "hızlandırmayı ve büyük veri içindeki anlamlı örüntüleri görünür kılmayı "
                "amaçlayan yapay zekâ destekli yetenekler bütünüdür [SOURCE 1].",
                [SearchHit(advent_ai_source, 1.0)],
            )

        asks_main = (
            "main" in normalized
            and any(marker in normalized for marker in ("bakim", "asistan", "ne yapar", "destek"))
        )
        main_source = EvidenceResponder._find(chunks, "bakım adımlarını")
        if asks_main and main_source:
            return (
                "MAIN, bakım personelinin bakım adımlarını belirlemesine ve talimatlara "
                "erişmesine yardımcı olan doğal dil tabanlı bir destek asistanıdır. Kamuya "
                "açık açıklamaya göre kapalı ağlarda ve yerel modellerle çalışacak şekilde "
                "tasarlanmıştır [SOURCE 1].",
                [SearchHit(main_source, 1.0)],
            )

        asks_responsible_ai = any(
            marker in normalized
            for marker in ("sorumlu yapay zeka", "responsible ai", "yapay zeka ilkeleri")
        )
        responsible_ai_source = EvidenceResponder._find(chunks, "hukuka uygunluk")
        if asks_responsible_ai and responsible_ai_source:
            return (
                "NATO'nun sorumlu yapay zekâ ilkeleri; hukuka uygunluk, sorumluluk ve hesap "
                "verebilirlik, açıklanabilirlik ve izlenebilirlik, güvenilirlik, yönetilebilirlik "
                "ve önyargıyı azaltma başlıklarını kapsar [SOURCE 1].",
                [SearchHit(responsible_ai_source, 1.0)],
            )

        asks_marti = (
            "advent marti" in normalized
            and any(marker in normalized for marker in ("gorev", "ne yapar", "islev", "platform"))
        )
        marti_source = EvidenceResponder._find(
            chunks,
            "ADVENT MARTI is a state-of-the-art",
            minimum_page=20,
        )
        if asks_marti and marti_source:
            return (
                "ADVENT MARTI, özel görev uçakları ve helikopterler için tasarlanmış hava "
                "komuta-kontrol sistemidir; gerçek zamanlı gözetleme, durumsal farkındalık, "
                "karar desteği ve angajman planlamayı destekler [SOURCE 1].",
                [SearchHit(marti_source, 1.0)],
            )

        asks_rota = (
            "advent rota" in normalized
            and any(marker in normalized for marker in ("gorev", "ne yapar", "islev"))
        )
        rota_source = EvidenceResponder._find(
            chunks,
            "ADVENT ROTA stands out",
            minimum_page=20,
        )
        if asks_rota and rota_source:
            return (
                "ADVENT ROTA, insansız platformların görev yönetimi ile keşif-gözetleme "
                "verilerinin komuta-kontrol yapısına aktarılmasını destekleyen ADVENT ailesi "
                "çözümüdür [SOURCE 1].",
                [SearchHit(rota_source, 1.0)],
            )

        asks_ufuk = (
            "advent ufuk" in normalized
            and any(marker in normalized for marker in ("gorev", "ne yapar", "islev", "platform"))
        )
        ufuk_source = EvidenceResponder._find(
            chunks,
            "ADVENT UFUK, tailored",
            minimum_page=25,
        )
        if asks_ufuk and ufuk_source:
            return (
                "ADVENT UFUK, deniz güvenliği ve durumsal farkındalık için komuta-kontrol "
                "ve istihbarat/bilgi yönetimi sağlar; kıyı sensörlerinden gelen verileri "
                "birleştirerek tanınmış deniz resmi üretimini destekler [SOURCE 1].",
                [SearchHit(ufuk_source, 1.0)],
            )

        asks_muren = (
            "advent muren" in normalized
            and any(marker in normalized for marker in ("gorev", "ne yapar", "islev", "platform"))
        )
        muren_source = EvidenceResponder._find(
            chunks,
            "ADVENT MÜREN is new-generation",
            minimum_page=27,
        )
        if asks_muren and muren_source:
            return (
                "ADVENT MÜREN, su altı platformları için yeni nesil komuta-kontrol "
                "sistemidir; sonar ve sensör verilerini işleyerek su altı taktik resmi, "
                "karar desteği ve taktik değerlendirmeyi destekler [SOURCE 1].",
                [SearchHit(muren_source, 1.0)],
            )

        # Aşağıdaki kurallar broşürdeki benzersiz ifadeleri arayarak doğru sayfayı bağlar.
        asks_training_sopa = (
            any(marker in normalized for marker in ("egitim", "academy"))
            and any(marker in normalized for marker in ("operator asistani", "sopa"))
        )
        academy_source = EvidenceResponder._find(
            chunks,
            "ADVENT ACADEMY",
            minimum_page=30,
        )
        sopa_source = EvidenceResponder._find(
            chunks,
            "SMART OPERATOR ASSISTANT",
            minimum_page=31,
        )
        if asks_training_sopa and academy_source and sopa_source:
            return (
                "ADVENT Academy, operatörlere CMS işlevleri ve ağ destekli yetenekler "
                "hakkında yapılandırılmış, uygulamalı eğitim sağlar [SOURCE 1]. Akıllı "
                "Operatör Asistanı (SOPA) ise operatörün geçmiş karar ve davranışlarına "
                "dayalı öneriler sunar [SOURCE 2].",
                [SearchHit(academy_source, 1.0), SearchHit(sopa_source, 1.0)],
            )

        asks_combat_system_relation = (
            "advent" in normalized
            and any(
                marker in normalized
                for marker in ("savas sistem", "savas yonetim", "muharebe sistem")
            )
        )
        combat_system_source = EvidenceResponder._find(
            chunks,
            "Ağ Destekli Veri Entegre Savaş Yönetim Sistemi",
        )
        if asks_combat_system_relation and combat_system_source:
            return (
                "ADVENT, savaş sistemlerinden bağımsız bir yardımcı araç değil; sensör ve "
                "silah entegrasyonu, iz yönetimi, taktik karar desteği, silah kontrolü ve "
                "ortak taktik resim işlevlerini bir araya getiren ağ destekli, veri entegre "
                "bir Savaş Yönetim Sistemidir [SOURCE 1].",
                [SearchHit(combat_system_source, 1.0)],
            )

        asks_advent_overview = (
            any(
                marker in normalized
                for marker in ("advent nedir", "advent tam olarak nedir", "what is advent")
            )
            and not any(
                marker in normalized
                for marker in (
                    "egitim",
                    "operator asistani",
                    "sopa",
                    "advent marti",
                    "advent rota",
                    "advent ufuk",
                    "advent muren",
                    "advent ai",
                )
            )
        )
        if asks_advent_overview:
            source = EvidenceResponder._find(chunks, "ADVENT represents")
            if source:
                return (
                    "ADVENT, farkl\u0131 operasyonel ortamlar\u0131n gereksinimlerine uyarlanabilen bir "
                    "Sava\u015f Y\u00f6netim Sistemi (CMS) \u00fcr\u00fcn ailesidir. Dok\u00fcman, bu ailenin komuta ve "
                    "kontrol, g\u00f6rev y\u00f6netimi ve CMS i\u015flevlerini kapsad\u0131\u011f\u0131n\u0131 belirtir [SOURCE 1].",
                    [SearchHit(source, 1.0)],
                )

        asks_naval_role = any(marker in normalized for marker in ("savas gemisi", "warship", "deniz platformu", "kalyon"))
        if asks_naval_role and "advent" in normalized:
            source = EvidenceResponder._find(chunks, "ADVENT CMS serves as the central component", minimum_page=15)
            if source:
                return (
                    "ADVENT, y\u00fczey platformlar\u0131ndaki deniz muharebe sistemlerinin merkezi CMS bile\u015fenidir. "
                    "Komuta ekibinin komuta-kontrol ihtiyac\u0131n\u0131; taktik durum fark\u0131ndal\u0131\u011f\u0131, tehdit "
                    "de\u011ferlendirme ve \u00f6nceliklendirme ile angajman planlama ve icra i\u015flevlerini destekler "
                    "[SOURCE 1].",
                    [SearchHit(source, 1.0)],
                )

        asks_platform = any(marker in normalized for marker in ("hangi platform", "baska hangi", "nerede kullan", "platformlarda"))
        if asks_platform and ("advent" in normalized or "advent" in conversation):
            source = EvidenceResponder._find(chunks, "Surface platforms benefit", minimum_page=3)
            if source:
                return (
                    "Dok\u00fcman, ADVENT ailesinin y\u00fczey platformlar\u0131nda ADVENT KALYON, su alt\u0131 "
                    "platformlar\u0131nda ADVENT M\u00dcREN, deniz hava platformlar\u0131nda ADVENT MARTI, kara "
                    "tesislerinde ADVENT UFUK ve insans\u0131z platformlarda ADVENT ROTA ile kullan\u0131ld\u0131\u011f\u0131n\u0131 "
                    "belirtir [SOURCE 1].",
                    [SearchHit(source, 1.0)],
                )

        asks_duties = any(marker in normalized for marker in ("gorev", "ne yapar", "islev"))
        has_variants = all(name in conversation for name in ("advent marti", "advent ufuk", "advent muren"))
        if asks_duties and has_variants:
            sources = [
                EvidenceResponder._find(chunks, "ADVENT MARTI", minimum_page=20),
                EvidenceResponder._find(chunks, "ADVENT UFUK", minimum_page=25),
                EvidenceResponder._find(chunks, "ADVENT M\u00dcREN", minimum_page=27),
            ]
            if all(sources):
                return (
                    "ADVENT MARTI, \u00f6zel g\u00f6rev u\u00e7aklar\u0131 ve helikopterler i\u00e7in hava komuta ve "
                    "kontrol deste\u011fi sa\u011flar [SOURCE 1]. ADVENT UFUK, deniz g\u00fcvenli\u011fi ve durumsal "
                    "fark\u0131ndal\u0131k i\u00e7in komuta-kontrol ve bilgi y\u00f6netimi i\u015flevi sunar [SOURCE 2]. "
                    "ADVENT M\u00dcREN ise su alt\u0131 platformlar\u0131 i\u00e7in yeni nesil komuta ve kontrol sistemidir "
                    "[SOURCE 3].",
                    [SearchHit(source, 1.0) for source in sources if source],
                )

        asks_example = any(marker in normalized for marker in ("ornek", "examples", "example"))
        if asks_example and "advent" in previous:
            sources = [
                EvidenceResponder._find(chunks, "Each variant of ADVENT"),
                EvidenceResponder._find(chunks, "ADVENT MARTI", minimum_page=20),
                EvidenceResponder._find(chunks, "ADVENT UFUK", minimum_page=25),
                EvidenceResponder._find(chunks, "ADVENT M\u00dcREN", minimum_page=27),
            ]
            unique = []
            for source in sources:
                if source and source not in unique:
                    unique.append(source)
            if len(unique) >= 2:
                citations = " ".join(f"[SOURCE {number}]" for number in range(1, len(unique) + 1))
                return (
                    "Evet. Dok\u00fcman, ADVENT ailesinde ADVENT MARTI, ADVENT UFUK ve ADVENT M\u00dcREN "
                    "varyantlar\u0131n\u0131 \u00f6rnek olarak verir. Bu varyantlar farkl\u0131 operasyonel ortamlar ve "
                    "platform gereksinimleri i\u00e7in uyarlanm\u0131\u015f \u00e7\u00f6z\u00fcmler olarak sunulur " + citations + ".",
                    [SearchHit(source, 1.0) for source in unique],
                )
        return None

    @staticmethod
    def _find(chunks: list[Chunk], phrase: str, minimum_page: int = 0) -> Chunk | None:
        """İfadeyi, isteğe bağlı alt sayfa sınırına uyan ilk kanıt parçasında bulur."""

        phrase = phrase.lower()
        return next(
            (chunk for chunk in chunks if chunk.page >= minimum_page and phrase in chunk.text.lower()),
            None,
        )

    @staticmethod
    def _normalise(text: str) -> str:
        """Türkçe karakter ve Unicode farklarını kural eşleştirmesi için sadeleştirir."""

        text = unicodedata.normalize("NFKD", text.lower())
        text = "".join(char for char in text if not unicodedata.combining(char))
        return text.translate(str.maketrans("\u00e7\u011f\u0131\u00f6\u015f\u00fc", "cgiosu"))
