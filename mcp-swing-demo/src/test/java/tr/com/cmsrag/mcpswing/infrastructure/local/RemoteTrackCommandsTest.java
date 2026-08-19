package tr.com.cmsrag.mcpswing.infrastructure.local;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import tr.com.cmsrag.mcpswing.application.TrackStateService;
import tr.com.cmsrag.mcpswing.domain.ShipType;

import java.net.ServerSocket;
import java.nio.file.Path;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

class RemoteTrackCommandsTest {
    @TempDir Path temporaryDirectory;

    @Test void connectsToExistingHostWithoutLaunchingAnotherApplication() throws Exception {
        TrackApplicationEndpoint endpoint = endpoint();
        TrackStateService service = new TrackStateService();
        AtomicInteger launches = new AtomicInteger();
        try (TrackApplicationHost host = new TrackApplicationHost(service, endpoint, () -> { })) {
            host.start();
            RemoteTrackCommands commands = new RemoteTrackCommands(endpoint, launches::incrementAndGet);

            Map<String, Object> result = commands.setTrackState(24.5, 270, "FIRKATEYN");

            assertEquals(0, launches.get());
            assertEquals(24.5, service.getState().speedKnots());
            assertEquals(270, service.getState().headingDegrees());
            assertEquals(ShipType.FIRKATEYN, service.getState().shipType());
            assertFalse((Boolean) result.get("applicationStarted"));
            assertTrue((Boolean) result.get("verified"));
            assertTrue((Boolean) commands.openApplication().get("alreadyRunning"));
            @SuppressWarnings("unchecked")
            var changes = (java.util.List<Map<String, Object>>) commands.getChangeHistory().get("changes");
            assertEquals("MCP", changes.getFirst().get("source"));

            service.setMcpWritesEnabled(false);
            assertEquals("LOCKED_BY_OPERATOR", commands.getWritePolicy().get("policy"));
            assertEquals(24.5, commands.getTrackState().get("speedKnots"));
            assertThrows(IllegalStateException.class, () -> commands.setSpeed(40));
            assertEquals(24.5, service.getState().speedKnots());
        }
    }

    @Test void reportsMissingApplicationThenStartsAndAppliesOriginalWrite() throws Exception {
        TrackApplicationEndpoint endpoint = endpoint();
        TrackStateService service = new TrackStateService();
        AtomicInteger launches = new AtomicInteger();
        TrackApplicationHost[] host = new TrackApplicationHost[1];
        RemoteTrackCommands commands = new RemoteTrackCommands(endpoint, () -> {
            launches.incrementAndGet();
            host[0] = new TrackApplicationHost(service, endpoint, () -> { });
            host[0].start();
        });
        try {
            assertFalse((Boolean) commands.getApplicationStatus().get("running"));
            assertThrows(IllegalStateException.class, commands::getTrackState);

            Map<String, Object> result = commands.setShipType("KORVET");

            assertEquals(1, launches.get());
            assertEquals(ShipType.KORVET, service.getState().shipType());
            assertTrue((Boolean) result.get("applicationStarted"));
            assertTrue((Boolean) result.get("verified"));
            assertTrue(String.valueOf(result.get("feedback")).contains("bulunamadı"));
        } finally {
            if (host[0] != null) host[0].close();
        }
    }

    @Test void secondHostCannotOwnTheSameApplicationEndpoint() throws Exception {
        TrackApplicationEndpoint endpoint = endpoint();
        try (TrackApplicationHost first = new TrackApplicationHost(new TrackStateService(), endpoint, () -> { });
             TrackApplicationHost second = new TrackApplicationHost(new TrackStateService(), endpoint, () -> { })) {
            first.start();
            assertThrows(java.io.IOException.class, second::start);
        }
    }

    private TrackApplicationEndpoint endpoint() throws Exception {
        try (ServerSocket socket = new ServerSocket(0)) {
            return new TrackApplicationEndpoint(socket.getLocalPort(),
                    temporaryDirectory.resolve("track-endpoint.properties"));
        }
    }
}
