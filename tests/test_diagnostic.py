import json
import tempfile
import unittest
from pathlib import Path

from scripts import diagnosticar_ambiente


class DiagnosticTests(unittest.TestCase):
    def test_report_does_not_expose_config_values(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "atualizar_index_github.py").write_text(
                '"""Atualizador V8"""\n',
                encoding="utf-8",
            )
            (folder / "atualizar_index_github_v9.py").write_text(
                '"""Atualizador V9"""\n',
                encoding="utf-8",
            )
            (folder / "config.env").write_text(
                "ACCESS_PASSWORD=SEGREDO\nGIT_PUSH=true\n",
                encoding="utf-8",
            )
            (folder / "estado_atualizador_v2.json").write_text(
                json.dumps({"version": 8}),
                encoding="utf-8",
            )

            report = diagnosticar_ambiente.build_report(folder)
            serialized = json.dumps(report, ensure_ascii=False)

            self.assertIn("ACCESS_PASSWORD", report["config_chaves"])
            self.assertNotIn("SEGREDO", serialized)
            self.assertEqual(report["script_ativo"]["versao"], "V8")
            self.assertTrue(report["avisos"])


if __name__ == "__main__":
    unittest.main()
