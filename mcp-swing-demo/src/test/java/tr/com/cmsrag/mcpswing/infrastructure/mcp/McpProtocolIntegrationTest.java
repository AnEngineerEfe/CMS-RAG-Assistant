package tr.com.cmsrag.mcpswing.infrastructure.mcp;

import io.modelcontextprotocol.client.McpClient;
import io.modelcontextprotocol.client.McpSyncClient;
import io.modelcontextprotocol.client.transport.ServerParameters;
import io.modelcontextprotocol.client.transport.StdioClientTransport;
import io.modelcontextprotocol.json.McpJsonDefaults;
import io.modelcontextprotocol.spec.McpSchema;
import org.junit.jupiter.api.Test;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** Gerçek STDIO JSON-RPC hattında araç keşfi, yazma, okuma ve doğrulamayı sınar. */
class McpProtocolIntegrationTest {
    @Test void exchangesTrackStateThroughRealMcpTransport() {
        String javaExecutable = Path.of(System.getProperty("java.home"), "bin",
                System.getProperty("os.name").toLowerCase().contains("win") ? "java.exe" : "java").toString();
        ServerParameters server = ServerParameters.builder(javaExecutable)
                .args("-Djava.awt.headless=true", "-cp", System.getProperty("java.class.path"),
                        "tr.com.cmsrag.mcpswing.McpSwingApplication", "--server-only")
                .build();
        StdioClientTransport transport = new StdioClientTransport(server, McpJsonDefaults.getMapper());
        try (McpSyncClient client = McpClient.sync(transport)
                .requestTimeout(Duration.ofSeconds(10)).build()) {
            client.initialize();

            Set<String> toolNames = client.listTools().tools().stream()
                    .map(McpSchema.Tool::name).collect(Collectors.toSet());
            assertEquals(Set.of("get_track_state", "get_speed", "set_speed", "get_heading",
                    "set_heading", "get_ship_type", "set_ship_type", "set_track_state"), toolNames);

            McpSchema.CallToolResult written = client.callTool(McpSchema.CallToolRequest.builder("set_track_state")
                    .arguments(Map.of("speedKnots", 24.5, "headingDegrees", 270, "shipType", "FIRKATEYN"))
                    .build());
            assertFalse(written.isError());

            McpSchema.CallToolResult read = client.callTool(
                    McpSchema.CallToolRequest.builder("get_track_state").arguments(Map.of()).build());
            assertFalse(read.isError());
            @SuppressWarnings("unchecked")
            Map<String, Object> state = (Map<String, Object>) read.structuredContent();
            assertEquals(24.5, ((Number) state.get("speedKnots")).doubleValue());
            assertEquals(270, ((Number) state.get("headingDegrees")).intValue());
            assertEquals("FIRKATEYN", state.get("shipType"));

            McpSchema.CallToolResult rejected = client.callTool(McpSchema.CallToolRequest.builder("set_heading")
                    .arguments(Map.of("headingDegrees", 361)).build());
            assertTrue(rejected.isError());
        }
    }
}
