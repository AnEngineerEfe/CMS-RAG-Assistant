package tr.com.cmsrag.mcpswing;

import io.modelcontextprotocol.server.McpSyncServer;
import tr.com.cmsrag.mcpswing.application.TrackStateService;
import tr.com.cmsrag.mcpswing.infrastructure.mcp.TrackMcpServer;
import tr.com.cmsrag.mcpswing.presentation.TrackControlFrame;
import javax.swing.SwingUtilities;
import javax.swing.UIManager;
import java.awt.GraphicsEnvironment;
import java.util.Arrays;

/** Swing demonstrasyonunu ve STDIO MCP sunucusunu aynı süreçte başlatır. */
public final class McpSwingApplication {
    private McpSwingApplication() { }
    public static void main(String[] args) {
        boolean uiOnly = Arrays.asList(args).contains("--ui-only");
        boolean serverOnly = Arrays.asList(args).contains("--server-only");
        if (uiOnly && serverOnly) throw new IllegalArgumentException("Çalışma kipleri birlikte kullanılamaz.");
        TrackStateService service = new TrackStateService();
        if (!uiOnly) {
            McpSyncServer server = new TrackMcpServer(service).start();
            Runtime.getRuntime().addShutdownHook(new Thread(server::closeGracefully, "mcp-shutdown"));
        }
        if (!serverOnly && !GraphicsEnvironment.isHeadless()) {
            SwingUtilities.invokeLater(() -> {
                useSystemLookAndFeel();
                new TrackControlFrame(service).setVisible(true);
            });
        }
    }
    private static void useSystemLookAndFeel() {
        try { UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName()); }
        catch (Exception exception) {
            System.err.println("Sistem görünümü uygulanamadı; Java varsayılanı kullanılacak: " + exception.getMessage());
        }
    }
}
