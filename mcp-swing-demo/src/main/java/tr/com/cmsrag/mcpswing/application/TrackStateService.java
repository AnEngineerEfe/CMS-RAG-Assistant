package tr.com.cmsrag.mcpswing.application;

import tr.com.cmsrag.mcpswing.domain.ShipType;
import tr.com.cmsrag.mcpswing.domain.TrackState;
import java.util.Objects;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Consumer;

/** MCP ve Swing kaynaklı değişiklikleri doğrulayıp atomik biçimde yayımlar. */
public final class TrackStateService {
    private final AtomicReference<TrackState> state;
    private final CopyOnWriteArrayList<Consumer<TrackState>> listeners = new CopyOnWriteArrayList<>();

    public TrackStateService() { this(TrackState.initial()); }
    public TrackStateService(TrackState initialState) {
        state = new AtomicReference<>(Objects.requireNonNull(initialState, "Başlangıç durumu zorunludur."));
    }
    public TrackState getState() { return state.get(); }
    public TrackState setSpeed(double speed) {
        return update(current -> new TrackState(speed, current.headingDegrees(), current.shipType()));
    }
    public TrackState setHeading(int heading) {
        return update(current -> new TrackState(current.speedKnots(), heading, current.shipType()));
    }
    public TrackState setShipType(ShipType type) {
        return update(current -> new TrackState(current.speedKnots(), current.headingDegrees(), type));
    }
    public TrackState setState(double speed, int heading, ShipType type) {
        TrackState updated = new TrackState(speed, heading, type);
        state.set(updated);
        notifyListeners(updated);
        return updated;
    }
    public AutoCloseable addListener(Consumer<TrackState> listener) {
        Consumer<TrackState> required = Objects.requireNonNull(listener, "Dinleyici zorunludur.");
        listeners.add(required);
        return () -> listeners.remove(required);
    }
    private TrackState update(java.util.function.UnaryOperator<TrackState> operation) {
        TrackState updated = state.updateAndGet(operation);
        notifyListeners(updated);
        return updated;
    }
    private void notifyListeners(TrackState updated) { listeners.forEach(listener -> listener.accept(updated)); }
}
