package tr.com.cmsrag.mcpswing.domain;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/** Bir iz güncellemesinin önceki/sonraki değerlerini ve kaynağını değişmez biçimde taşır. */
public record TrackStateChange(
        long sequence,
        Instant occurredAt,
        UpdateSource source,
        TrackState before,
        TrackState after) {

    public TrackStateChange {
        if (sequence < 1) throw new IllegalArgumentException("Değişiklik sıra numarası pozitif olmalıdır.");
        if (occurredAt == null || source == null || before == null || after == null) {
            throw new IllegalArgumentException("Değişiklik kaydı alanları boş olamaz.");
        }
    }

    /** Ekran ve audit çıktısı için yalnız gerçekten değişen alanları özetler. */
    public String summary() {
        List<String> changes = new ArrayList<>();
        if (Double.compare(before.speedKnots(), after.speedKnots()) != 0) {
            changes.add("Hız: %s → %s knot".formatted(formatSpeed(before.speedKnots()), formatSpeed(after.speedKnots())));
        }
        if (before.headingDegrees() != after.headingDegrees()) {
            changes.add("Yön: %d° → %d°".formatted(before.headingDegrees(), after.headingDegrees()));
        }
        if (before.shipType() != after.shipType()) {
            changes.add("Tip: %s → %s".formatted(before.shipType().displayName(), after.shipType().displayName()));
        }
        return changes.isEmpty() ? "Değer değişmedi" : String.join(" · ", changes);
    }

    private static String formatSpeed(double value) {
        return value == Math.rint(value) ? Long.toString(Math.round(value)) : Double.toString(value);
    }
}
