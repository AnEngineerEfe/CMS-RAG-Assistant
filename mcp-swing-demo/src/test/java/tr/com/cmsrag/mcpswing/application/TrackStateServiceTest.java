package tr.com.cmsrag.mcpswing.application;

import org.junit.jupiter.api.Test;
import tr.com.cmsrag.mcpswing.domain.ShipType;
import tr.com.cmsrag.mcpswing.domain.TrackState;
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
        AtomicReference<TrackState> observed = new AtomicReference<>();
        AutoCloseable subscription = service.addListener(observed::set);
        TrackState expected = service.setShipType(ShipType.DENIZALTI);
        assertEquals(expected, observed.get());
        subscription.close();
        service.setHeading(180);
        assertEquals(expected, observed.get());
    }
}
