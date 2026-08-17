"""Python CMS istemcisi ile gerçek Java MCP sunucusu arasındaki sözleşme testi."""

from pathlib import Path
import shutil
import unittest

from src.cms_rag.domain.track_control import TrackState
from src.cms_rag.infrastructure.mcp_track_client import StdioMcpTrackClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MCP_JAR = PROJECT_ROOT / "mcp-swing-demo" / "target" / "mcp-swing-demo.jar"


@unittest.skipUnless(shutil.which("java") and MCP_JAR.is_file(), "Java MCP jar hazır değil")
class McpTrackClientIntegrationTests(unittest.TestCase):
    """Gerçek STDIO hattında başlatma, yazma, okuma ve geçmişi doğrular."""

    def test_round_trip_through_real_java_server(self):
        """Python'dan yapılan atomik güncellemeyi Java sunucusundan geri okur."""

        client = StdioMcpTrackClient(PROJECT_ROOT, server_only=True)
        try:
            initial = client.get_state()
            self.assertEqual(initial.speed_knots, 0.0)
            expected = TrackState(24.5, 270, "FIRKATEYN", "Fırkateyn")
            self.assertEqual(client.set_state(expected), expected)
            self.assertEqual(client.get_state(), expected)
            self.assertTrue(client.get_write_policy())
            self.assertEqual(client.get_history()["count"], 1)
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
