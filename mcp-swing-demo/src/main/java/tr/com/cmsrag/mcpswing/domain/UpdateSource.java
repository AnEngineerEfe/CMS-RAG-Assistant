package tr.com.cmsrag.mcpswing.domain;

/** İz durumundaki bir değişikliğin güvenilir kaynağını belirtir. */
public enum UpdateSource {
    OPERATOR("Operatör"),
    MCP("MCP / Model");

    private final String displayName;

    UpdateSource(String displayName) {
        this.displayName = displayName;
    }

    public String displayName() {
        return displayName;
    }
}
