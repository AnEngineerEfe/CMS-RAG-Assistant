package tr.com.cmsrag.mcpswing.application;

import org.junit.jupiter.api.Test;
import tr.com.cmsrag.mcpswing.domain.ShipType;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class TrackCommandFacadeTest {
    @Test void translatesMcpStyleArgumentsIntoDomainState() {
        TrackCommandFacade facade = new TrackCommandFacade(new TrackStateService());
        Map<String, Object> result = facade.setTrackState(18.75, 315, "FIRKATEYN");
        assertEquals(18.75, result.get("speedKnots"));
        assertEquals(315, result.get("headingDegrees"));
        assertEquals(ShipType.FIRKATEYN.name(), result.get("shipType"));
        assertEquals("Fırkateyn", result.get("shipTypeLabel"));
    }
    @Test void acceptsTurkishDisplayNameForDirectCalls() {
        TrackCommandFacade facade = new TrackCommandFacade(new TrackStateService());
        assertEquals("DENIZALTI", facade.setShipType("Denizaltı").get("shipType"));
    }
    @Test void rejectsFractionalHeadingAndUnknownShipType() {
        TrackCommandFacade facade = new TrackCommandFacade(new TrackStateService());
        assertThrows(IllegalArgumentException.class, () -> facade.setHeading(45.5));
        assertThrows(IllegalArgumentException.class, () -> facade.setShipType("Uzay gemisi"));
    }

    @Test void exposesMcpAuditHistoryAndOperatorWritePolicy() {
        TrackStateService service = new TrackStateService();
        TrackCommandFacade facade = new TrackCommandFacade(service);

        facade.setSpeed(12.5);
        assertEquals(1, facade.getChangeHistory().get("count"));
        assertEquals("ENABLED", facade.getWritePolicy().get("policy"));
        service.setMcpWritesEnabled(false);

        assertEquals("LOCKED_BY_OPERATOR", facade.getWritePolicy().get("policy"));
        assertThrows(IllegalStateException.class, () -> facade.setHeading(45));
    }
}
