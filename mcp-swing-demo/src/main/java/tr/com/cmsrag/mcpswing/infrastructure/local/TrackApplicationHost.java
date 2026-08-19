package tr.com.cmsrag.mcpswing.infrastructure.local;

import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import io.modelcontextprotocol.json.McpJsonDefaults;
import io.modelcontextprotocol.json.McpJsonMapper;
import io.modelcontextprotocol.json.TypeRef;
import tr.com.cmsrag.mcpswing.application.TrackCommandFacade;
import tr.com.cmsrag.mcpswing.application.TrackStateService;

import java.io.IOException;
import java.net.InetAddress;
import java.net.InetSocketAddress;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.security.SecureRandom;
import java.util.Base64;
import java.util.Map;
import java.util.Properties;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

/** Açık Swing sürecini yerel loopback üzerinde tek otorite olarak yayımlar. */
public final class TrackApplicationHost implements AutoCloseable {
    static final String TOKEN_HEADER = "X-CMS-Track-Token";
    private static final McpJsonMapper JSON = McpJsonDefaults.getMapper();
    private static final TypeRef<Map<String, Object>> MAP_TYPE = new TypeRef<>() { };
    private final TrackApplicationEndpoint endpoint;
    private final TrackCommandFacade commands;
    private final Runnable shutdownAction;
    private final String token = createToken();
    private final AtomicBoolean closed = new AtomicBoolean();
    private HttpServer server;

    public TrackApplicationHost(TrackStateService service, TrackApplicationEndpoint endpoint,
            Runnable shutdownAction) {
        this.commands = new TrackCommandFacade(service);
        this.endpoint = endpoint;
        this.shutdownAction = shutdownAction;
    }

    public void start() throws IOException {
        server = HttpServer.create(new InetSocketAddress(InetAddress.getByName("127.0.0.1"), endpoint.port()), 0);
        server.createContext("/track", this::handle);
        server.setExecutor(Executors.newCachedThreadPool(task -> {
            Thread thread = new Thread(task, "track-local-ipc");
            thread.setDaemon(true);
            return thread;
        }));
        server.start();
        try {
            writeDescriptor();
        } catch (IOException exception) {
            server.stop(0);
            throw exception;
        }
    }

    private void handle(HttpExchange exchange) throws IOException {
        if (!"POST".equals(exchange.getRequestMethod())) {
            respond(exchange, 405, Map.of("success", false, "error", "Yalnız POST desteklenir."));
            return;
        }
        if (!token.equals(exchange.getRequestHeaders().getFirst(TOKEN_HEADER))) {
            respond(exchange, 403, Map.of("success", false, "error", "Yerel uygulama kimliği doğrulanamadı."));
            return;
        }
        try {
            Map<String, Object> request = JSON.readValue(exchange.getRequestBody().readAllBytes(), MAP_TYPE);
            String operation = String.valueOf(request.get("operation"));
            @SuppressWarnings("unchecked")
            Map<String, Object> arguments = request.get("arguments") instanceof Map<?, ?> map
                    ? (Map<String, Object>) map : Map.of();
            Map<String, Object> result = dispatch(operation, arguments);
            respond(exchange, 200, Map.of("success", true, "result", result));
            if ("close_application".equals(operation)) {
                Thread.ofPlatform().name("track-application-close").start(() -> {
                    close();
                    shutdownAction.run();
                });
            }
        } catch (IllegalArgumentException | IllegalStateException exception) {
            respond(exchange, 400, Map.of("success", false, "error", exception.getMessage()));
        } catch (Exception exception) {
            respond(exchange, 500, Map.of("success", false,
                    "error", "Yerel Track uygulaması isteği işleyemedi: " + exception.getMessage()));
        }
    }

    private Map<String, Object> dispatch(String operation, Map<String, Object> arguments) {
        return switch (operation) {
            case "get_application_status" -> Map.of("running", true,
                    "pid", ProcessHandle.current().pid(), "port", endpoint.port());
            case "open_application" -> Map.of("running", true, "alreadyRunning", true,
                    "pid", ProcessHandle.current().pid());
            case "close_application" -> Map.of("running", false, "closing", true);
            case "get_track_state" -> commands.getTrackState();
            case "get_write_policy" -> commands.getWritePolicy();
            case "get_change_history" -> commands.getChangeHistory();
            case "set_speed" -> commands.setSpeed(arguments.get("speedKnots"));
            case "set_heading" -> commands.setHeading(arguments.get("headingDegrees"));
            case "set_ship_type" -> commands.setShipType(arguments.get("shipType"));
            case "set_track_state" -> commands.setTrackState(arguments.get("speedKnots"),
                    arguments.get("headingDegrees"), arguments.get("shipType"));
            default -> throw new IllegalArgumentException("Bilinmeyen yerel işlem: " + operation);
        };
    }

    private void respond(HttpExchange exchange, int status, Map<String, Object> body) throws IOException {
        byte[] payload = JSON.writeValueAsBytes(body);
        exchange.getResponseHeaders().set("Content-Type", "application/json; charset=utf-8");
        exchange.sendResponseHeaders(status, payload.length);
        try (var output = exchange.getResponseBody()) { output.write(payload); }
    }

    private void writeDescriptor() throws IOException {
        Files.createDirectories(endpoint.descriptorPath().getParent());
        Properties properties = new Properties();
        properties.setProperty("port", Integer.toString(endpoint.port()));
        properties.setProperty("token", token);
        properties.setProperty("pid", Long.toString(ProcessHandle.current().pid()));
        var temporary = endpoint.descriptorPath().resolveSibling(endpoint.descriptorPath().getFileName() + ".tmp");
        try (var output = Files.newOutputStream(temporary, StandardOpenOption.CREATE,
                StandardOpenOption.TRUNCATE_EXISTING, StandardOpenOption.WRITE)) {
            properties.store(output, "CMS Track Swing local endpoint");
        }
        try {
            Files.move(temporary, endpoint.descriptorPath(), StandardCopyOption.REPLACE_EXISTING,
                    StandardCopyOption.ATOMIC_MOVE);
        } catch (java.nio.file.AtomicMoveNotSupportedException ignored) {
            Files.move(temporary, endpoint.descriptorPath(), StandardCopyOption.REPLACE_EXISTING);
        }
    }

    @Override public void close() {
        if (!closed.compareAndSet(false, true)) return;
        if (server != null) server.stop(0);
        try {
            Properties current = new Properties();
            if (Files.exists(endpoint.descriptorPath())) {
                try (var input = Files.newInputStream(endpoint.descriptorPath())) { current.load(input); }
                if (token.equals(current.getProperty("token"))) Files.deleteIfExists(endpoint.descriptorPath());
            }
        } catch (IOException exception) {
            System.err.println("Track keşif kaydı temizlenemedi: " + exception.getMessage());
        }
    }

    private static String createToken() {
        byte[] bytes = new byte[32];
        new SecureRandom().nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }
}
