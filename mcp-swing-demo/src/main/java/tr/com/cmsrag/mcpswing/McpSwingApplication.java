package tr.com.cmsrag.mcpswing;

import io.modelcontextprotocol.server.McpSyncServer;
import tr.com.cmsrag.mcpswing.application.TrackStateService;
import tr.com.cmsrag.mcpswing.infrastructure.mcp.TrackMcpServer;
import tr.com.cmsrag.mcpswing.infrastructure.local.RemoteTrackCommands;
import tr.com.cmsrag.mcpswing.infrastructure.local.TrackApplicationEndpoint;
import tr.com.cmsrag.mcpswing.infrastructure.local.TrackApplicationHost;
import tr.com.cmsrag.mcpswing.infrastructure.local.TrackApplicationLauncher;
import tr.com.cmsrag.mcpswing.presentation.TrackControlFrame;
import javax.swing.SwingUtilities;
import javax.swing.UIManager;
import java.awt.GraphicsEnvironment;
import java.util.Arrays;

/** STDIO MCP köprüsünü veya tek otoriteli Swing uygulama sürecini başlatır. */
public final class McpSwingApplication {
    private McpSwingApplication() { }
    public static void main(String[] args) {
        boolean uiOnly = Arrays.asList(args).contains("--ui-only");
        boolean serverOnly = Arrays.asList(args).contains("--server-only");
        if (uiOnly && serverOnly) throw new IllegalArgumentException("Çalışma kipleri birlikte kullanılamaz.");
        TrackApplicationEndpoint endpoint = TrackApplicationEndpoint.configured();
        if (!uiOnly) {
            RemoteTrackCommands commands = new RemoteTrackCommands(
                    endpoint, TrackApplicationLauncher.currentRuntime(endpoint));
            McpSyncServer server = new TrackMcpServer(commands).start();
            Runtime.getRuntime().addShutdownHook(new Thread(server::closeGracefully, "mcp-shutdown"));
        }
        if (uiOnly) startSwingHost(endpoint);
    }

    private static void startSwingHost(TrackApplicationEndpoint endpoint) {
        RemoteTrackCommands probe = new RemoteTrackCommands(endpoint, () -> { });
        if (Boolean.TRUE.equals(probe.getApplicationStatus().get("running"))) {
            System.err.println("Track/Swing uygulaması zaten açık; ikinci pencere oluşturulmadı.");
            return;
        }
        TrackStateService service = new TrackStateService();
        try {
            TrackApplicationHost host = new TrackApplicationHost(service, endpoint, () -> System.exit(0));
            host.start();
            Runtime.getRuntime().addShutdownHook(new Thread(host::close, "track-host-shutdown"));
            if (!GraphicsEnvironment.isHeadless()) openFrame(service);
            System.err.println("Track/Swing uygulama hostu hazır: 127.0.0.1:" + endpoint.port());
        } catch (java.io.IOException exception) {
            throw new IllegalStateException("Track/Swing yerel bağlantısı başlatılamadı: " + exception.getMessage(), exception);
        }
    }

    private static void openFrame(TrackStateService service) {
            SwingUtilities.invokeLater(() -> {
                useSystemLookAndFeel();
                new TrackControlFrame(service).setVisible(true);
            });
    }
    private static void useSystemLookAndFeel() {
        try { UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName()); }
        catch (Exception exception) {
            System.err.println("Sistem görünümü uygulanamadı; Java varsayılanı kullanılacak: " + exception.getMessage());
        }
    }
}
