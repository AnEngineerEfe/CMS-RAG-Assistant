package tr.com.cmsrag.mcpswing.application;

import org.junit.jupiter.api.Test;
import tr.com.cmsrag.mcpswing.domain.ShipType;
import tr.com.cmsrag.mcpswing.domain.TrackState;
import tr.com.cmsrag.mcpswing.domain.TrackStateChange;
import tr.com.cmsrag.mcpswing.domain.UpdateSource;
import java.util.concurrent.atomic.AtomicReference;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class TrackStateServiceTest {
    @Test void updatesEveryFieldAtomically() {
        TrackStateService service = new TrackStateService();
        TrackState updated = service.setState(22.5, 270, ShipType.FIRKATEYN);
        assertEquals(new TrackState(22.5, 270, ShipType.FIRKATEYN), updated);
        assertEquals(updated, service.getState());
    }
    @Test void rejectsOutOfRangeValuesWithoutChangingState() {
        TrackState initial = new TrackState(12, 90, ShipType.KORVET);
        TrackStateService service = new TrackStateService(initial);
        assertThrows(IllegalArgumentException.class, () -> service.setSpeed(101));
        assertThrows(IllegalArgumentException.class, () -> service.setHeading(-1));
        assertEquals(initial, service.getState());
    }
    @Test void publishesUpdatesToRegisteredListeners() throws Exception {
        TrackStateService service = new TrackStateService();
        AtomicReference<TrackStateChange> observed = new AtomicReference<>();
        AutoCloseable subscription = service.addListener(observed::set);
        TrackState expected = service.setShipType(ShipType.DENIZALTI);
        assertEquals(expected, observed.get().after());
        assertEquals(UpdateSource.OPERATOR, observed.get().source());
        subscription.close();
        service.setHeading(180);
        assertEquals(expected, observed.get().after());
    }

    @Test void recordsMcpSourceAndLetsOperatorLockModelWrites() {
        TrackStateService service = new TrackStateService();

        service.setSpeed(18.5, UpdateSource.MCP);
        assertEquals(1, service.getHistory().size());
        assertEquals(UpdateSource.MCP, service.getHistory().getFirst().source());
        service.setMcpWritesEnabled(false);

        assertThrows(IllegalStateException.class, () -> service.setHeading(90, UpdateSource.MCP));
        assertEquals(0, service.getState().headingDegrees());
        assertEquals(1, service.getHistory().size());
        assertEquals(180, service.setHeading(180, UpdateSource.OPERATOR).headingDegrees());
    }
}
