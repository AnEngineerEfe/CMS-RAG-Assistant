package tr.com.cmsrag.mcpswing.infrastructure.local;

import java.nio.file.Path;

/** Swing uygulamasının yalnız yerel makinede kullandığı keşif adresini tanımlar. */
public record TrackApplicationEndpoint(int port, Path descriptorPath) {
    public static final int DEFAULT_PORT = 43117;

    public static TrackApplicationEndpoint configured() {
        int port = Integer.getInteger("cms.track.port", DEFAULT_PORT);
        String customDescriptor = System.getProperty("cms.track.descriptor");
        Path descriptor = customDescriptor == null || customDescriptor.isBlank()
                ? Path.of(System.getProperty("java.io.tmpdir"), "cms-track-swing-" + port + ".properties")
                : Path.of(customDescriptor);
        return new TrackApplicationEndpoint(port, descriptor.toAbsolutePath().normalize());
    }
}
