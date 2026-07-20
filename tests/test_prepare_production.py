import tempfile
import unittest
from pathlib import Path

from scripts.preparar_producao import (
    prepare_production,
    read_env,
    validate_named_public_profile,
)


class PrepareProductionTests(unittest.TestCase):
    def test_preserves_password_and_applies_authorized_named_profile(self):
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
            self.assertEqual(values["INCLUDE_PERSONAL_DATA"], "true")
            self.assertEqual(values["ALLOW_PUBLIC_PERSONAL_DATA"], "true")
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

    def test_named_public_profile_rejects_anonymous_publication(self):
        values = {
            "HOMOLOGATION_MODE": "false",
            "GIT_PUSH": "true",
            "INCLUDE_PERSONAL_DATA": "false",
            "ALLOW_PUBLIC_PERSONAL_DATA": "true",
        }

        with self.assertRaises(RuntimeError):
            validate_named_public_profile(values)

    def test_named_public_profile_accepts_authorized_names(self):
        validate_named_public_profile(
            {
                "HOMOLOGATION_MODE": "false",
                "GIT_PUSH": "true",
                "INCLUDE_PERSONAL_DATA": "true",
                "ALLOW_PUBLIC_PERSONAL_DATA": "true",
            }
        )


if __name__ == "__main__":
    unittest.main()
