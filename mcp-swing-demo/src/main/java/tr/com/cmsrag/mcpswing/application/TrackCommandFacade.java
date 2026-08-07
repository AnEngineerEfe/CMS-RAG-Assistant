package tr.com.cmsrag.mcpswing.application;

import tr.com.cmsrag.mcpswing.domain.ShipType;
import tr.com.cmsrag.mcpswing.domain.TrackState;
import java.util.LinkedHashMap;
import java.util.Map;

/** Protokolden bağımsız komut yüzeyi; MCP adaptörü yalnızca bu sınıfa erişir. */
public final class TrackCommandFacade {
    private final TrackStateService service;
    public TrackCommandFacade(TrackStateService service) { this.service = service; }
    public Map<String, Object> getTrackState() { return toMap(service.getState()); }
    public Map<String, Object> setSpeed(Object value) { return toMap(service.setSpeed(asDouble(value, "speedKnots"))); }
    public Map<String, Object> setHeading(Object value) { return toMap(service.setHeading(asInteger(value, "headingDegrees"))); }
    public Map<String, Object> setShipType(Object value) {
        return toMap(service.setShipType(ShipType.fromExternalValue(asText(value, "shipType"))));
    }
    public Map<String, Object> setTrackState(Object speed, Object heading, Object type) {
        return toMap(service.setState(asDouble(speed, "speedKnots"), asInteger(heading, "headingDegrees"),
                ShipType.fromExternalValue(asText(type, "shipType"))));
    }
    private static Map<String, Object> toMap(TrackState state) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("speedKnots", state.speedKnots());
        result.put("headingDegrees", state.headingDegrees());
        result.put("shipType", state.shipType().name());
        result.put("shipTypeLabel", state.shipType().displayName());
        return Map.copyOf(result);
    }
    private static double asDouble(Object value, String field) {
        if (!(value instanceof Number number)) throw new IllegalArgumentException(field + " sayısal olmalıdır.");
        return number.doubleValue();
    }
    private static int asInteger(Object value, String field) {
        if (!(value instanceof Number number)) throw new IllegalArgumentException(field + " tam sayı olmalıdır.");
        double decimal = number.doubleValue();
        if (!Double.isFinite(decimal) || decimal != Math.rint(decimal)) {
            throw new IllegalArgumentException(field + " tam sayı olmalıdır.");
        }
        return number.intValue();
    }
    private static String asText(Object value, String field) {
        if (!(value instanceof String text)) throw new IllegalArgumentException(field + " metin olmalıdır.");
        return text;
    }
}
