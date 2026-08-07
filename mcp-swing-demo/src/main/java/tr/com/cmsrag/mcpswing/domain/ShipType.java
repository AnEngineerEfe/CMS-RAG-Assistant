package tr.com.cmsrag.mcpswing.domain;

import java.util.Arrays;

/** Demonstrasyonda sınıflandırılabilen genel iz/gemi tipleri. */
public enum ShipType {
    BELIRSIZ("Belirsiz"), FIRKATEYN("Fırkateyn"), KORVET("Korvet"), MUHRIP("Muhrip"),
    DENIZALTI("Denizaltı"), HUCUMBOT("Hücumbot"), TICARI_GEMI("Ticari Gemi"),
    YARDIMCI_GEMI("Yardımcı Gemi");

    private final String displayName;

    ShipType(String displayName) { this.displayName = displayName; }
    public String displayName() { return displayName; }

    /** MCP girdilerinde enum kodunu ve kullanıcıya gösterilen Türkçe adı kabul eder. */
    public static ShipType fromExternalValue(String value) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException("Gemi tipi boş olamaz.");
        String normalized = value.trim();
        return Arrays.stream(values())
                .filter(type -> type.name().equalsIgnoreCase(normalized)
                        || type.displayName.equalsIgnoreCase(normalized))
                .findFirst()
                .orElseThrow(() -> new IllegalArgumentException(
                        "Geçersiz gemi tipi: " + value + ". İzin verilenler: " + allowedValues()));
    }

    public static String allowedValues() {
        return Arrays.stream(values()).map(ShipType::name).toList().toString();
    }

    @Override public String toString() { return displayName; }
}
