package tr.com.cmsrag.mcpswing.infrastructure.mcp;

import io.modelcontextprotocol.client.McpClient;
import io.modelcontextprotocol.client.McpSyncClient;
import io.modelcontextprotocol.client.transport.ServerParameters;
import io.modelcontextprotocol.client.transport.StdioClientTransport;
import io.modelcontextprotocol.json.McpJsonDefaults;
import io.modelcontextprotocol.spec.McpSchema;
import org.junit.jupiter.api.Test;
import java.nio.file.Path;
import java.net.ServerSocket;
import java.time.Duration;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** Gerçek STDIO JSON-RPC hattında araç keşfi, yazma, okuma ve doğrulamayı sınar. */
class McpProtocolIntegrationTest {
    @Test void exchangesTrackStateThroughRealMcpTransport() throws Exception {
        int port;
        try (ServerSocket socket = new ServerSocket(0)) { port = socket.getLocalPort(); }
        String javaExecutable = Path.of(System.getProperty("java.home"), "bin",
                System.getProperty("os.name").toLowerCase().contains("win") ? "java.exe" : "java").toString();
        ServerParameters server = ServerParameters.builder(javaExecutable)
                .args("-Djava.awt.headless=true", "-Dcms.track.port=" + port,
                        "-cp", System.getProperty("java.class.path"),
                        "tr.com.cmsrag.mcpswing.McpSwingApplication", "--server-only")
                .build();
        StdioClientTransport transport = new StdioClientTransport(server, McpJsonDefaults.getMapper());
        try (McpSyncClient client = McpClient.sync(transport)
                .requestTimeout(Duration.ofSeconds(10)).build()) {
            client.initialize();

            Set<String> toolNames = client.listTools().tools().stream()
                    .map(McpSchema.Tool::name).collect(Collectors.toSet());
            assertEquals(Set.of("get_application_status", "open_track_application", "close_track_application",
                    "get_track_state", "get_write_policy", "get_change_history",
                    "get_speed", "set_speed", "get_heading", "set_heading", "get_ship_type",
                    "set_ship_type", "set_track_state"), toolNames);

            McpSchema.CallToolResult missingStatus = client.callTool(McpSchema.CallToolRequest
                    .builder("get_application_status").arguments(Map.of()).build());
            @SuppressWarnings("unchecked")
            Map<String, Object> missing = (Map<String, Object>) missingStatus.structuredContent();
            assertEquals(false, missing.get("running"));

            McpSchema.CallToolResult written = client.callTool(McpSchema.CallToolRequest.builder("set_track_state")
                    .arguments(Map.of("speedKnots", 24.5, "headingDegrees", 270, "shipType", "FIRKATEYN"))
                    .build());
            assertFalse(written.isError());
            @SuppressWarnings("unchecked")
            Map<String, Object> writeResult = (Map<String, Object>) written.structuredContent();
            assertEquals(true, writeResult.get("applicationStarted"));
            assertEquals(true, writeResult.get("verified"));
            assertTrue(String.valueOf(writeResult.get("feedback")).contains("bulunamadı"));

            McpSchema.CallToolResult openedAgain = client.callTool(McpSchema.CallToolRequest
                    .builder("open_track_application").arguments(Map.of()).build());
            @SuppressWarnings("unchecked")
            Map<String, Object> openResult = (Map<String, Object>) openedAgain.structuredContent();
            assertEquals(true, openResult.get("alreadyRunning"));

            McpSchema.CallToolResult read = client.callTool(
                    McpSchema.CallToolRequest.builder("get_track_state").arguments(Map.of()).build());
            assertFalse(read.isError());
            @SuppressWarnings("unchecked")
            Map<String, Object> state = (Map<String, Object>) read.structuredContent();
            assertEquals(24.5, ((Number) state.get("speedKnots")).doubleValue());
            assertEquals(270, ((Number) state.get("headingDegrees")).intValue());
            assertEquals("FIRKATEYN", state.get("shipType"));

            McpSchema.CallToolResult historyResult = client.callTool(
                    McpSchema.CallToolRequest.builder("get_change_history").arguments(Map.of()).build());
            @SuppressWarnings("unchecked")
            Map<String, Object> history = (Map<String, Object>) historyResult.structuredContent();
            assertEquals(1, ((Number) history.get("count")).intValue());

            McpSchema.CallToolResult rejected = client.callTool(McpSchema.CallToolRequest.builder("set_heading")
                    .arguments(Map.of("headingDegrees", 361)).build());
            assertTrue(rejected.isError());

            McpSchema.CallToolResult closed = client.callTool(McpSchema.CallToolRequest
                    .builder("close_track_application").arguments(Map.of()).build());
            assertFalse(closed.isError());

            Map<String, Object> finalStatus = null;
            for (int attempt = 0; attempt < 30; attempt++) {
                Thread.sleep(100);
                McpSchema.CallToolResult status = client.callTool(McpSchema.CallToolRequest
                        .builder("get_application_status").arguments(Map.of()).build());
                @SuppressWarnings("unchecked")
                Map<String, Object> candidate = (Map<String, Object>) status.structuredContent();
                finalStatus = candidate;
                if (Boolean.FALSE.equals(candidate.get("running"))) break;
            }
            assertEquals(false, finalStatus.get("running"));
        }
    }
}
