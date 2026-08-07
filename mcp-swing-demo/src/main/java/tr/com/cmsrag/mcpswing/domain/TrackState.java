package tr.com.cmsrag.mcpswing.domain;

/** Swing ekranı ile MCP araçlarının paylaştığı tek ve değişmez iz durumu. */
public record TrackState(double speedKnots, int headingDegrees, ShipType shipType) {
    public static final double MIN_SPEED_KNOTS = 0.0;
    public static final double MAX_SPEED_KNOTS = 100.0;
    public static final int MIN_HEADING_DEGREES = 0;
    public static final int MAX_HEADING_DEGREES = 360;

    public TrackState {
        if (!Double.isFinite(speedKnots) || speedKnots < MIN_SPEED_KNOTS || speedKnots > MAX_SPEED_KNOTS) {
            throw new IllegalArgumentException("Hız 0 ile 100 knot arasında olmalıdır.");
        }
        if (headingDegrees < MIN_HEADING_DEGREES || headingDegrees > MAX_HEADING_DEGREES) {
            throw new IllegalArgumentException("Yön 0 ile 360 derece arasında olmalıdır.");
        }
        if (shipType == null) throw new IllegalArgumentException("Gemi tipi boş olamaz.");
    }

    public static TrackState initial() { return new TrackState(0.0, 0, ShipType.BELIRSIZ); }
}
