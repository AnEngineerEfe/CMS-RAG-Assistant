package tr.com.cmsrag.mcpswing.infrastructure.local;

import io.modelcontextprotocol.json.McpJsonDefaults;
import io.modelcontextprotocol.json.McpJsonMapper;
import io.modelcontextprotocol.json.TypeRef;
import tr.com.cmsrag.mcpswing.application.TrackApplicationCommands;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.file.Files;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Properties;

/** STDIO MCP sürecindeki komutları açık Swing host sürecine yönlendirir. */
public final class RemoteTrackCommands implements TrackApplicationCommands {
    private static final McpJsonMapper JSON = McpJsonDefaults.getMapper();
    private static final TypeRef<Map<String, Object>> MAP_TYPE = new TypeRef<>() { };
    private static final Duration REQUEST_TIMEOUT = Duration.ofSeconds(3);
    private static final Duration START_TIMEOUT = Duration.ofSeconds(8);
    private final TrackApplicationEndpoint endpoint;
    private final TrackApplicationLauncher launcher;
    private final HttpClient httpClient;

    public RemoteTrackCommands(TrackApplicationEndpoint endpoint, TrackApplicationLauncher launcher) {
        this(endpoint, launcher, HttpClient.newBuilder().connectTimeout(REQUEST_TIMEOUT).build());
    }

    RemoteTrackCommands(TrackApplicationEndpoint endpoint, TrackApplicationLauncher launcher, HttpClient client) {
        this.endpoint = endpoint;
        this.launcher = launcher;
        this.httpClient = client;
    }

    @Override public Map<String, Object> getApplicationStatus() {
        try {
            Map<String, Object> status = request("get_application_status", Map.of());
            Map<String, Object> result = new LinkedHashMap<>(status);
            result.put("running", true);
            return Map.copyOf(result);
        } catch (IllegalStateException exception) {
            return Map.of("running", false,
                    "message", "Çalışan Track/Swing uygulaması bulunamadı.");
        }
    }

    @Override public Map<String, Object> openApplication() {
        if (isRunning()) {
            return Map.of("running", true, "alreadyRunning", true,
                    "message", "Track/Swing uygulaması zaten açık; ikinci pencere oluşturulmadı.");
        }
        startAndAwait();
        Map<String, Object> status = new LinkedHashMap<>(request("get_application_status", Map.of()));
        status.put("running", true);
        status.put("alreadyRunning", false);
        status.put("started", true);
        status.put("message", "Track/Swing uygulaması açıldı ve bağlantı doğrulandı.");
        return Map.copyOf(status);
    }

    @Override public Map<String, Object> closeApplication() {
        requireRunning();
        return request("close_application", Map.of());
    }

    @Override public Map<String, Object> getTrackState() {
        requireRunning();
        return request("get_track_state", Map.of());
    }
    @Override public Map<String, Object> getWritePolicy() {
        requireRunning();
        return request("get_write_policy", Map.of());
    }
    @Override public Map<String, Object> getChangeHistory() {
        requireRunning();
        return request("get_change_history", Map.of());
    }
    @Override public Map<String, Object> setSpeed(Object value) {
        return write("set_speed", Map.of("speedKnots", value));
    }
    @Override public Map<String, Object> setHeading(Object value) {
        return write("set_heading", Map.of("headingDegrees", value));
    }
    @Override public Map<String, Object> setShipType(Object value) {
        return write("set_ship_type", Map.of("shipType", value));
    }
    @Override public Map<String, Object> setTrackState(Object speed, Object heading, Object type) {
        return write("set_track_state", Map.of(
                "speedKnots", speed, "headingDegrees", heading, "shipType", type));
    }

    private Map<String, Object> write(String operation, Map<String, Object> arguments) {
        boolean applicationWasMissing = !isRunning();
        if (applicationWasMissing) startAndAwait();
        Map<String, Object> result = new LinkedHashMap<>(request(operation, arguments));
        result.put("applicationStarted", applicationWasMissing);
        if (applicationWasMissing) {
            result.put("feedback", "Çalışan Track/Swing uygulaması bulunamadı; yeni uygulama açıldı, "
                    + "ilk komut bu örneğe uygulandı ve sonuç geri okundu.");
        }
        Map<String, Object> readBack = request("get_track_state", Map.of());
        result.put("verified", stateFieldsEqual(result, readBack));
        return Map.copyOf(result);
    }

    private boolean isRunning() {
        try { return Boolean.TRUE.equals(request("get_application_status", Map.of()).get("running")); }
        catch (IllegalStateException exception) { return false; }
    }

    private void requireRunning() {
        if (!isRunning()) throw new IllegalStateException("Çalışan Track/Swing uygulaması bulunamadı. "
                + "Önce open_track_application aracını kullanın.");
    }

    private void startAndAwait() {
        try {
            launcher.launch();
        } catch (Exception exception) {
            throw new IllegalStateException("Track/Swing uygulaması başlatılamadı: " + exception.getMessage(), exception);
        }
        long deadline = System.nanoTime() + START_TIMEOUT.toNanos();
        while (System.nanoTime() < deadline) {
            if (isRunning()) return;
            try { Thread.sleep(100); }
            catch (InterruptedException exception) {
                Thread.currentThread().interrupt();
                throw new IllegalStateException("Track/Swing uygulaması beklenirken işlem kesildi.", exception);
            }
        }
        throw new IllegalStateException("Track/Swing uygulaması açıldı ancak yerel bağlantı "
                + START_TIMEOUT.toSeconds() + " saniyede kurulamadı.");
    }

    private Map<String, Object> request(String operation, Map<String, Object> arguments) {
        Properties descriptor = readDescriptor();
        String token = descriptor.getProperty("token");
        int port;
        try { port = Integer.parseInt(descriptor.getProperty("port")); }
        catch (RuntimeException exception) { throw unavailable(exception); }
        try {
            byte[] body = JSON.writeValueAsBytes(Map.of("operation", operation, "arguments", arguments));
            HttpRequest request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:" + port + "/track"))
                    .timeout(REQUEST_TIMEOUT).header("Content-Type", "application/json")
                    .header(TrackApplicationHost.TOKEN_HEADER, token).POST(HttpRequest.BodyPublishers.ofByteArray(body))
                    .build();
            HttpResponse<byte[]> response = httpClient.send(request, HttpResponse.BodyHandlers.ofByteArray());
            Map<String, Object> envelope = JSON.readValue(response.body(), MAP_TYPE);
            if (!Boolean.TRUE.equals(envelope.get("success"))) {
                throw new IllegalStateException(String.valueOf(envelope.get("error")));
            }
            @SuppressWarnings("unchecked")
            Map<String, Object> result = (Map<String, Object>) envelope.get("result");
            return Map.copyOf(result);
        } catch (IOException | InterruptedException exception) {
            if (exception instanceof InterruptedException) Thread.currentThread().interrupt();
            throw unavailable(exception);
        }
    }

    private Properties readDescriptor() {
        Properties properties = new Properties();
        try (var input = Files.newInputStream(endpoint.descriptorPath())) { properties.load(input); }
        catch (IOException exception) { throw unavailable(exception); }
        if (properties.getProperty("token") == null || properties.getProperty("port") == null) {
            throw unavailable(null);
        }
        return properties;
    }

    private IllegalStateException unavailable(Throwable cause) {
        return new IllegalStateException("Çalışan Track/Swing uygulaması bulunamadı.", cause);
    }

    private static boolean stateFieldsEqual(Map<String, Object> expected, Map<String, Object> actual) {
        return expected.get("speedKnots").equals(actual.get("speedKnots"))
                && expected.get("headingDegrees").equals(actual.get("headingDegrees"))
                && expected.get("shipType").equals(actual.get("shipType"));
    }
}
