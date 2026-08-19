package tr.com.cmsrag.mcpswing.application;

import java.util.Map;

/** MCP adaptörünün yerel veya süreçler-arası uygulayabildiği iz komut sözleşmesi. */
public interface TrackCommands {
    Map<String, Object> getTrackState();
    Map<String, Object> getWritePolicy();
    Map<String, Object> getChangeHistory();
    Map<String, Object> setSpeed(Object value);
    Map<String, Object> setHeading(Object value);
    Map<String, Object> setShipType(Object value);
    Map<String, Object> setTrackState(Object speed, Object heading, Object type);
}
