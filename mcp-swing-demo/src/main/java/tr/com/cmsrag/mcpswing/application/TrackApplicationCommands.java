package tr.com.cmsrag.mcpswing.application;

import java.util.Map;

/** İz komutlarına ek olarak Swing sürecinin açık yaşam döngüsünü yönetir. */
public interface TrackApplicationCommands extends TrackCommands {
    Map<String, Object> getApplicationStatus();
    Map<String, Object> openApplication();
    Map<String, Object> closeApplication();
}
