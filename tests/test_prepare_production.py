import tempfile
import unittest
from pathlib import Path

from scripts.preparar_producao import prepare_production, read_env


class PrepareProductionTests(unittest.TestCase):
    def test_preserves_password_and_applies_safe_public_profile(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "repo"
            old = base / "automacao"
            root.mkdir()
            old.mkdir()
            (old / "config.env").write_text(
                "BACKUP_DIR=C:\\\\backup\n"
                "ACCESS_PASSWORD=SEGREDO_LOCAL\n"
                "GIT_PUSH=false\n",
                encoding="utf-8",
            )
            (old / "classificacao_ferramentas.json").write_text(
                "{}", encoding="utf-8"
            )

            prepare_production(root, old)
            values = read_env(root / "config.env")

            self.assertEqual(values["ACCESS_PASSWORD"], "SEGREDO_LOCAL")
            self.assertEqual(values["HOMOLOGATION_MODE"], "false")
            self.assertEqual(values["GIT_PUSH"], "true")
            self.assertEqual(values["INCLUDE_PERSONAL_DATA"], "false")
            self.assertEqual(values["DIRECT_WHATSAPP_ENABLED"], "false")
            self.assertTrue(
                (root / "classificacao_ferramentas.json").exists()
            )

    def test_rejects_missing_password(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "repo"
            old = base / "automacao"
            root.mkdir()
            old.mkdir()
            with self.assertRaises(RuntimeError):
                prepare_production(root, old)


if __name__ == "__main__":
    unittest.main()
