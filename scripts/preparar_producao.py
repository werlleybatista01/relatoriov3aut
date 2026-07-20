# -*- coding: utf-8 -*-
"""Prepara a configuração local de produção sem expor credenciais."""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Dict, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OLD_AUTOMATION = Path.home() / "Desktop" / "automacao"

PRODUCTION_VALUES = {
    "DATA_FILE": "data/dashboard-data.js",
    "DOWNLOAD_FILE": "downloads/relatorio_almoxarifado_2026.xlsx",
    "HOMOLOGATION_MODE": "false",
    "GIT_PUSH": "true",
    "INCLUDE_PERSONAL_DATA": "true",
    "ALLOW_PUBLIC_PERSONAL_DATA": "true",
    "DIRECT_WHATSAPP_ENABLED": "false",
    "OPERATING_YEAR": "2026",
    "SEASONAL_HISTORY_YEAR": "2025",
    "SACOLAS_POR_PACOTE": "100",
    "TOOL_CLASSIFICATION_FILE": "classificacao_ferramentas.json",
    "TOOL_CLASSIFICATION_PENDING_FILE": (
        "produtos_pendentes_classificacao.csv"
    ),
    "STATE_FILE": "estado_atualizador_v2.json",
    "LOCK_FILE": ".atualizador_v2.lock",
    "LOCK_STALE_MINUTES": "120",
    "BACKUP_STABILITY_SECONDS": "2",
    "BACKUP_STABILITY_ATTEMPTS": "4",
    "MAX_RECORD_DROP_PERCENT": "15",
    "ALLOW_RECORD_DROP": "false",
    "ALLOW_BACKUP_REGRESSION": "false",
}

REQUIRED_NAMED_PUBLIC_VALUES = {
    "HOMOLOGATION_MODE": "false",
    "GIT_PUSH": "true",
    "INCLUDE_PERSONAL_DATA": "true",
    "ALLOW_PUBLIC_PERSONAL_DATA": "true",
}

ORDER = [
    "BACKUP_DIR",
    "BACKUP_PATTERNS",
    "ACCESS_PASSWORD",
    "REPO_DIR",
    "DATA_FILE",
    "DOWNLOAD_FILE",
    "HOMOLOGATION_MODE",
    "GIT_PUSH",
    "OPERATING_YEAR",
    "SEASONAL_HISTORY_YEAR",
    "SACOLAS_POR_PACOTE",
    "INCLUDE_PERSONAL_DATA",
    "ALLOW_PUBLIC_PERSONAL_DATA",
    "DIRECT_WHATSAPP_ENABLED",
    "TOOL_CLASSIFICATION_FILE",
    "TOOL_CLASSIFICATION_PENDING_FILE",
    "STATE_FILE",
    "LOCK_FILE",
    "LOCK_STALE_MINUTES",
    "BACKUP_STABILITY_SECONDS",
    "BACKUP_STABILITY_ATTEMPTS",
    "MAX_RECORD_DROP_PERCENT",
    "ALLOW_RECORD_DROP",
    "ALLOW_BACKUP_REGRESSION",
]


def read_env(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def write_env(path: Path, values: Dict[str, str]) -> None:
    lines = [
        "# Configuração local de produção. Não enviar ao GitHub.",
        "# Gerada por scripts/preparar_producao.py.",
    ]
    emitted = set()
    for key in ORDER:
        if key in values:
            lines.append(f"{key}={values[key]}")
            emitted.add(key)
    for key in sorted(values.keys() - emitted):
        lines.append(f"{key}={values[key]}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def first_existing(paths: Iterable[Path]) -> Path | None:
    return next((path for path in paths if path.exists()), None)


def validate_named_public_profile(values: Dict[str, str]) -> None:
    wrong = {
        key: values.get(key, "")
        for key, expected in REQUIRED_NAMED_PUBLIC_VALUES.items()
        if values.get(key, "").lower() != expected
    }
    if wrong:
        details = ", ".join(
            f"{key}={value or 'ausente'}" for key, value in sorted(wrong.items())
        )
        raise RuntimeError(
            "Perfil de produção nominal inválido. O dashboard público deve "
            "publicar nomes reais de colaboradores conforme autorizado. "
            f"Valores divergentes: {details}"
        )


def prepare_production(
    root: Path = ROOT,
    old_automation: Path = DEFAULT_OLD_AUTOMATION,
) -> Dict[str, str]:
    root = root.resolve()
    config_path = root / "config.env"
    old_config_path = old_automation / "config.env"

    current = read_env(config_path)
    legacy = read_env(old_config_path)
    values = {**legacy, **current}

    password = values.get("ACCESS_PASSWORD", "").strip()
    invalid_passwords = {
        "",
        "SUA_SENHA_AQUI",
        "PREENCHIDA_SOMENTE_NO_COMPUTADOR_LOCAL",
    }
    if password in invalid_passwords:
        raise RuntimeError(
            "ACCESS_PASSWORD não foi encontrada. Mantenha o config.env "
            "antigo em Desktop\\automacao ou preencha a senha somente "
            "neste computador."
        )

    values["BACKUP_DIR"] = values.get(
        "BACKUP_DIR",
        str(Path.home() / "Desktop" / "backup"),
    )
    values["BACKUP_PATTERNS"] = values.get(
        "BACKUP_PATTERNS",
        "Backup * - Banco de Dados 11.0.mdb;*.accdb",
    )
    values["REPO_DIR"] = str(root)
    values.update(PRODUCTION_VALUES)
    validate_named_public_profile(values)

    root.mkdir(parents=True, exist_ok=True)
    (root / "data").mkdir(exist_ok=True)
    (root / "downloads").mkdir(exist_ok=True)
    write_env(config_path, values)

    private_files = {
        "classificacao_ferramentas.json": "TOOL_CLASSIFICATION_FILE",
        "produtos_pendentes_classificacao.csv": (
            "TOOL_CLASSIFICATION_PENDING_FILE"
        ),
    }
    for name, config_key in private_files.items():
        target = root / name
        configured = Path(values.get(config_key, name))
        if not configured.is_absolute():
            configured = root / configured
        source = first_existing(
            [old_automation / name, configured]
        )
        if not target.exists() and source and source.is_file():
            shutil.copy2(source, target)

    return values


def main() -> int:
    try:
        values = prepare_production()
        backup_dir = Path(values["BACKUP_DIR"])
        if not backup_dir.exists():
            raise FileNotFoundError(
                f"Pasta de backups não encontrada: {backup_dir}"
            )
        print("Configuração de produção preparada com segurança.")
        print(f"Repositório: {values['REPO_DIR']}")
        print(f"Backups: {values['BACKUP_DIR']}")
        print("Credencial preservada localmente: sim")
        print("Publicação com nomes reais: sim")
        return 0
    except Exception as exc:
        print(f"ERRO: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
