package tr.com.cmsrag.mcpswing.infrastructure.local;

import tr.com.cmsrag.mcpswing.McpSwingApplication;

import java.net.URISyntaxException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/** MCP köprüsünden gerektiğinde tek Swing host sürecini başlatır. */
@FunctionalInterface
public interface TrackApplicationLauncher {
    void launch() throws Exception;

    static TrackApplicationLauncher currentRuntime(TrackApplicationEndpoint endpoint) {
        return () -> {
            String javaExecutable = Path.of(System.getProperty("java.home"), "bin",
                    System.getProperty("os.name").toLowerCase().contains("win") ? "java.exe" : "java").toString();
            List<String> command = new ArrayList<>();
            command.add(javaExecutable);
            command.add("-Dcms.track.port=" + endpoint.port());
            command.add("-Dcms.track.descriptor=" + endpoint.descriptorPath());
            command.add("-Djava.awt.headless=" + System.getProperty("java.awt.headless", "false"));
            Path location = runtimeLocation();
            if (location.toString().toLowerCase().endsWith(".jar")) {
                command.add("-jar");
                command.add(location.toString());
            } else {
                command.add("-cp");
                command.add(System.getProperty("java.class.path"));
                command.add(McpSwingApplication.class.getName());
            }
            command.add("--ui-only");
            new ProcessBuilder(command)
                    .redirectInput(ProcessBuilder.Redirect.PIPE)
                    .redirectOutput(ProcessBuilder.Redirect.DISCARD)
                    .redirectError(ProcessBuilder.Redirect.DISCARD)
                    .start();
        };
    }

    private static Path runtimeLocation() throws URISyntaxException {
        return Path.of(McpSwingApplication.class.getProtectionDomain().getCodeSource().getLocation().toURI())
                .toAbsolutePath().normalize();
    }
}
