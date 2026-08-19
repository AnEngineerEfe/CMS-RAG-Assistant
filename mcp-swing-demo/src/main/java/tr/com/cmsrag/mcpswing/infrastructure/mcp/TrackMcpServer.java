package tr.com.cmsrag.mcpswing.infrastructure.mcp;

import io.modelcontextprotocol.json.McpJsonDefaults;
import io.modelcontextprotocol.server.McpServer;
import io.modelcontextprotocol.server.McpServerFeatures;
import io.modelcontextprotocol.server.McpSyncServer;
import io.modelcontextprotocol.server.transport.StdioServerTransportProvider;
import io.modelcontextprotocol.spec.McpSchema;
import tr.com.cmsrag.mcpswing.application.TrackApplicationCommands;
import tr.com.cmsrag.mcpswing.domain.ShipType;
import java.util.List;
import java.util.Map;
import java.util.function.Function;

/** İz durumunu resmî Java SDK üzerinden yalnızca izinli MCP araçlarıyla açar. */
public final class TrackMcpServer {
    private static final Map<String, Object> EMPTY_SCHEMA = Map.of(
            "type", "object", "properties", Map.of(), "additionalProperties", false);
    private final TrackApplicationCommands commands;
    public TrackMcpServer(TrackApplicationCommands commands) { this.commands = commands; }

    public McpSyncServer start() {
        StdioServerTransportProvider transport = new StdioServerTransportProvider(McpJsonDefaults.getMapper());
        McpSyncServer server = McpServer.sync(transport)
                .serverInfo("cms-track-swing-server", "1.0.0")
                .capabilities(McpSchema.ServerCapabilities.builder().tools(false).build())
                .tools(toolSpecifications())
                .build();
        System.err.println("CMS Track MCP Server hazır: STDIO, 13 araç");
        return server;
    }

    private List<McpServerFeatures.SyncToolSpecification> toolSpecifications() {
        return List.of(
                tool("get_application_status", "Açık Track/Swing uygulaması bulunup bulunmadığını kontrol eder.",
                        EMPTY_SCHEMA, arguments -> commands.getApplicationStatus()),
                tool("open_track_application", "Track/Swing uygulamasını yalnız açık değilse başlatır; ikinci pencere açmaz.",
                        EMPTY_SCHEMA, arguments -> commands.openApplication()),
                tool("close_track_application", "Açık Track/Swing uygulamasını kontrollü biçimde kapatır.",
                        EMPTY_SCHEMA, arguments -> commands.closeApplication()),
                tool("get_track_state", "Hız, yön ve gemi tipini birlikte okur.", EMPTY_SCHEMA,
                        arguments -> commands.getTrackState()),
                tool("get_write_policy", "Operatörün MCP yazma iznini açık veya kilitli olarak okur.", EMPTY_SCHEMA,
                        arguments -> commands.getWritePolicy()),
                tool("get_change_history", "Son iz değişikliklerini zaman, kaynak ve önce/sonra değerleriyle okur.",
                        EMPTY_SCHEMA, arguments -> commands.getChangeHistory()),
                tool("get_speed", "İzin mevcut hızını knot cinsinden okur.", EMPTY_SCHEMA,
                        arguments -> Map.of("speedKnots", commands.getTrackState().get("speedKnots"))),
                tool("set_speed", "İzin hızını 0 ile 100 knot arasında günceller. Uygulama kapalıysa açar ve ilk komutu sürdürür.",
                        numberSchema("speedKnots", 0, 100, false),
                        arguments -> commands.setSpeed(arguments.get("speedKnots"))),
                tool("get_heading", "İzin mevcut yönünü derece cinsinden okur.", EMPTY_SCHEMA,
                        arguments -> Map.of("headingDegrees", commands.getTrackState().get("headingDegrees"))),
                tool("set_heading", "İzin yönünü 0 ile 360 derece arasında günceller. Uygulama kapalıysa açar ve ilk komutu sürdürür.",
                        numberSchema("headingDegrees", 0, 360, true),
                        arguments -> commands.setHeading(arguments.get("headingDegrees"))),
                tool("get_ship_type", "İzin seçili gemi tipini okur.", EMPTY_SCHEMA,
                        arguments -> Map.of("shipType", commands.getTrackState().get("shipType"),
                                "shipTypeLabel", commands.getTrackState().get("shipTypeLabel"))),
                tool("set_ship_type", "İzin gemi tipini kontrollü listeden seçer. Uygulama kapalıysa açar ve ilk komutu sürdürür.", shipTypeSchema(),
                        arguments -> commands.setShipType(arguments.get("shipType"))),
                tool("set_track_state", "Hız, yön ve gemi tipini tek atomik işlemle günceller. Uygulama kapalıysa açar ve ilk komutu sürdürür.", fullStateSchema(),
                        arguments -> commands.setTrackState(arguments.get("speedKnots"),
                                arguments.get("headingDegrees"), arguments.get("shipType")))
        );
    }

    private static McpServerFeatures.SyncToolSpecification tool(String name, String description,
            Map<String, Object> schema, Function<Map<String, Object>, Map<String, Object>> action) {
        return McpServerFeatures.SyncToolSpecification.builder()
                .tool(McpSchema.Tool.builder(name, schema).description(description).build())
                .callHandler((exchange, request) -> execute(action, request.arguments()))
                .build();
    }

    private static McpSchema.CallToolResult execute(Function<Map<String, Object>, Map<String, Object>> action,
            Map<String, Object> arguments) {
        try {
            Map<String, Object> result = action.apply(arguments);
            return McpSchema.CallToolResult.builder()
                    .content(List.of(McpSchema.TextContent.builder(result.toString()).build()))
                    .structuredContent(result).build();
        } catch (IllegalArgumentException | IllegalStateException exception) {
            return McpSchema.CallToolResult.builder().isError(true)
                    .content(List.of(McpSchema.TextContent.builder(exception.getMessage()).build())).build();
        }
    }

    private static Map<String, Object> numberSchema(String field, Number min, Number max, boolean integer) {
        return Map.of("type", "object", "properties", Map.of(field, Map.of(
                "type", integer ? "integer" : "number", "minimum", min, "maximum", max)),
                "required", List.of(field), "additionalProperties", false);
    }
    private static Map<String, Object> shipTypeSchema() {
        return Map.of("type", "object", "properties", Map.of("shipType", Map.of(
                "type", "string", "enum", List.of(ShipType.values()).stream().map(Enum::name).toList())),
                "required", List.of("shipType"), "additionalProperties", false);
    }
    private static Map<String, Object> fullStateSchema() {
        return Map.of("type", "object", "properties", Map.of(
                "speedKnots", Map.of("type", "number", "minimum", 0, "maximum", 100),
                "headingDegrees", Map.of("type", "integer", "minimum", 0, "maximum", 360),
                "shipType", Map.of("type", "string",
                        "enum", List.of(ShipType.values()).stream().map(Enum::name).toList())),
                "required", List.of("speedKnots", "headingDegrees", "shipType"),
                "additionalProperties", false);
    }
}
