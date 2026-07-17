import datetime as dt
import unittest

from scripts import atualizar_dashboard


class PayloadTests(unittest.TestCase):
    def test_payload_contract_and_phone_sanitization(self):
        data = [
            {
                "Data_iso": "2026-01-10",
                "Ano": 2026,
                "Categoria": "Botinas",
                "Qtde_num": 1,
            }
        ]
        stock = []
        open_tools = [
            {
                "Colaborador": "PESSOA TESTE",
                "TelefoneWhatsApp": "5511999999999",
                "QuantidadeEmAberto": 1,
            }
        ]

        payload = atualizar_dashboard.build_payload(
            data,
            stock,
            open_tools,
            dt.datetime(2026, 7, 10, 12, 0, 0),
        )

        self.assertEqual(payload["schemaVersion"], 2)
        self.assertEqual(payload["metadata"]["operatingYear"], 2026)
        self.assertEqual(
            payload["openTools"][0]["TelefoneWhatsApp"],
            "",
        )
        self.assertNotEqual(
            payload["openTools"][0]["Colaborador"],
            "PESSOA TESTE",
        )
        self.assertTrue(
            payload["openTools"][0]["Colaborador"].startswith(
                "Colaborador "
            )
        )
        self.assertFalse(
            payload["features"]["personalDataIncluded"]
        )

    def test_serialization_is_es_module(self):
        payload = {
            "schemaVersion": 2,
            "metadata": {},
            "features": {},
            "withdrawals": [],
            "stock": [],
            "openTools": [],
        }
        output = atualizar_dashboard.serialize_payload_js(payload)
        self.assertIn("export const dashboardData", output)
        self.assertNotIn("SUA_SENHA", output)

    def test_generation_time_alone_does_not_trigger_publication(self):
        previous = {
            "schemaVersion": 2,
            "metadata": {
                "generatedAt": "13/07/2026 13:03:01",
                "referenceDate": "2026-07-13",
            },
            "features": {"personalDataIncluded": False},
            "withdrawals": [{"Item": "1"}],
            "stock": [],
            "openTools": [],
        }
        current = {
            **previous,
            "metadata": {
                **previous["metadata"],
                "generatedAt": "13/07/2026 13:08:01",
            },
        }

        self.assertTrue(
            atualizar_dashboard._payloads_equivalent_for_publish(
                previous, current
            )
        )

    def test_reference_date_change_triggers_daily_publication(self):
        previous = {
            "metadata": {
                "generatedAt": "13/07/2026 23:59:00",
                "referenceDate": "2026-07-13",
            }
        }
        current = {
            "metadata": {
                "generatedAt": "14/07/2026 00:01:00",
                "referenceDate": "2026-07-14",
            }
        }

        self.assertFalse(
            atualizar_dashboard._payloads_equivalent_for_publish(
                previous, current
            )
        )


    def test_homologation_blocks_git_push(self):
        with self.assertRaises(RuntimeError):
            atualizar_dashboard.validate_security_profile(
                git_push=True,
                homologation_mode=True,
                include_personal_data=False,
                allow_public_personal_data=False,
                direct_whatsapp_enabled=False,
            )

    def test_publication_blocks_personal_data_without_override(self):
        with self.assertRaises(RuntimeError):
            atualizar_dashboard.validate_security_profile(
                git_push=True,
                homologation_mode=False,
                include_personal_data=True,
                allow_public_personal_data=False,
                direct_whatsapp_enabled=False,
            )

    def test_publication_allows_personal_data_with_explicit_override(self):
        atualizar_dashboard.validate_security_profile(
            git_push=True,
            homologation_mode=False,
            include_personal_data=True,
            allow_public_personal_data=True,
            direct_whatsapp_enabled=False,
        )

    def test_direct_whatsapp_requires_personal_data(self):
        with self.assertRaises(RuntimeError):
            atualizar_dashboard.validate_security_profile(
                git_push=False,
                homologation_mode=False,
                include_personal_data=False,
                allow_public_personal_data=False,
                direct_whatsapp_enabled=True,
            )

    def test_public_xlsx_rows_are_pseudonymized(self):
        rows = [
            {
                "Requisitante": "NOME REAL TESTE",
                "Nº Retirada": "12345",
                "Responsável pelo Registro": "OPERADOR REAL",
                "Observação": "DADO PRIVADO",
                "Data_iso": "2026-01-10",
                "Ano": 2026,
                "Categoria": "Sacolas",
                "Qtde_num": 1,
            }
        ]
        public_rows = atualizar_dashboard._public_withdrawals(rows)
        self.assertNotEqual(public_rows[0]["Requisitante"], "NOME REAL TESTE")
        self.assertTrue(public_rows[0]["Requisitante"].startswith("Colaborador "))
        self.assertNotEqual(public_rows[0]["Nº Retirada"], "12345")
        self.assertEqual(public_rows[0]["Responsável pelo Registro"], "")
        self.assertEqual(public_rows[0]["Observação"], "")


if __name__ == "__main__":
    unittest.main()
