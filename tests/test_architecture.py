"""Katman sınırlarının ve kaynak kod belgelemesinin gerilemesini önleyen testler."""

import ast
from pathlib import Path
import unittest


SOURCE_ROOT = Path("src/cms_rag")


class ArchitectureGuardTests(unittest.TestCase):
    """Modüler mimarinin dosya taşıma sonrası korunacağını doğrular."""

    def test_streamlit_entrypoint_stays_thin(self):
        """Kök giriş dosyasının iş mantığı barındırmadan sunum katmanını çağırmasını ister."""

        entrypoint = Path("app.py").read_text(encoding="utf-8")
        self.assertLessEqual(len(entrypoint.splitlines()), 10)
        self.assertIn("from src.cms_rag.presentation.app import run", entrypoint)

    def test_layers_do_not_depend_in_the_wrong_direction(self):
        """Domain ve altyapı katmanlarının üst seviye uygulama/UI bağımlılığını reddeder."""

        forbidden_by_layer = {
            "domain": ("application", "infrastructure", "presentation", "streamlit"),
            "infrastructure": ("application", "presentation", "streamlit"),
            "application": ("presentation", "streamlit"),
        }
        violations: list[str] = []
        for layer, forbidden_names in forbidden_by_layer.items():
            for path in (SOURCE_ROOT / layer).glob("*.py"):
                content = path.read_text(encoding="utf-8")
                for forbidden in forbidden_names:
                    if f"cms_rag.{forbidden}" in content or f"..{forbidden}" in content:
                        violations.append(f"{path}: {forbidden}")
        self.assertEqual(violations, [])

    def test_every_source_class_and_function_is_documented(self):
        """Her sınıf ve fonksiyonun bakım amacını açıklayan bir docstring taşımasını ister."""

        missing: list[str] = []
        for path in SOURCE_ROOT.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    if not ast.get_docstring(node):
                        missing.append(f"{path}:{node.lineno}:{node.name}")
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
