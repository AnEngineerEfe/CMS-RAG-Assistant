package tr.com.cmsrag.mcpswing.application;

import tr.com.cmsrag.mcpswing.domain.ShipType;
import tr.com.cmsrag.mcpswing.domain.TrackState;
import tr.com.cmsrag.mcpswing.domain.TrackStateChange;
import tr.com.cmsrag.mcpswing.domain.UpdateSource;
import java.time.Clock;
import java.util.Objects;
import java.util.List;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;
import java.util.function.Consumer;

/** MCP ve Swing kaynaklı değişiklikleri doğrulayıp atomik biçimde yayımlar. */
public final class TrackStateService {
    private static final int MAX_HISTORY_SIZE = 100;
    private final AtomicReference<TrackState> state;
    private final CopyOnWriteArrayList<TrackStateChange> history = new CopyOnWriteArrayList<>();
    private final CopyOnWriteArrayList<Consumer<TrackStateChange>> listeners = new CopyOnWriteArrayList<>();
    private final AtomicBoolean mcpWritesEnabled = new AtomicBoolean(true);
    private final AtomicLong sequence = new AtomicLong();
    private final Clock clock;

    public TrackStateService() { this(TrackState.initial(), Clock.systemUTC()); }
    public TrackStateService(TrackState initialState) { this(initialState, Clock.systemUTC()); }
    TrackStateService(TrackState initialState, Clock clock) {
        state = new AtomicReference<>(Objects.requireNonNull(initialState, "Başlangıç durumu zorunludur."));
        this.clock = Objects.requireNonNull(clock, "Saat zorunludur.");
    }
    public TrackState getState() { return state.get(); }
    public List<TrackStateChange> getHistory() { return List.copyOf(history); }
    public boolean isMcpWritesEnabled() { return mcpWritesEnabled.get(); }
    public void setMcpWritesEnabled(boolean enabled) { mcpWritesEnabled.set(enabled); }

    public TrackState setSpeed(double speed) { return setSpeed(speed, UpdateSource.OPERATOR); }
    public TrackState setSpeed(double speed, UpdateSource source) {
        return update(source, current -> new TrackState(speed, current.headingDegrees(), current.shipType()));
    }
    public TrackState setHeading(int heading) { return setHeading(heading, UpdateSource.OPERATOR); }
    public TrackState setHeading(int heading, UpdateSource source) {
        return update(source, current -> new TrackState(current.speedKnots(), heading, current.shipType()));
    }
    public TrackState setShipType(ShipType type) { return setShipType(type, UpdateSource.OPERATOR); }
    public TrackState setShipType(ShipType type, UpdateSource source) {
        return update(source, current -> new TrackState(current.speedKnots(), current.headingDegrees(), type));
    }
    public TrackState setState(double speed, int heading, ShipType type) {
        return setState(speed, heading, type, UpdateSource.OPERATOR);
    }
    public TrackState setState(double speed, int heading, ShipType type, UpdateSource source) {
        return update(source, current -> new TrackState(speed, heading, type));
    }
    public AutoCloseable addListener(Consumer<TrackStateChange> listener) {
        Consumer<TrackStateChange> required = Objects.requireNonNull(listener, "Dinleyici zorunludur.");
        listeners.add(required);
        return () -> listeners.remove(required);
    }

    private TrackState update(UpdateSource source, java.util.function.UnaryOperator<TrackState> operation) {
        UpdateSource requiredSource = Objects.requireNonNull(source, "Güncelleme kaynağı zorunludur.");
        if (requiredSource == UpdateSource.MCP && !mcpWritesEnabled.get()) {
            throw new IllegalStateException("MCP yazma işlemleri operatör tarafından kilitlendi.");
        }
        TrackState before;
        TrackState after;
        do {
            before = state.get();
            after = operation.apply(before);
        } while (!state.compareAndSet(before, after));

        TrackStateChange change = new TrackStateChange(
                sequence.incrementAndGet(), clock.instant(), requiredSource, before, after);
        history.add(change);
        while (history.size() > MAX_HISTORY_SIZE) history.removeFirst();
        notifyListeners(change);
        return after;
    }
    private void notifyListeners(TrackStateChange change) { listeners.forEach(listener -> listener.accept(change)); }
}
