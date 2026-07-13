# -*- coding: utf-8 -*-
"""Diagnóstico seguro da pasta de automação legada.

O relatório mostra versões, chaves de configuração, contagens e riscos sem
imprimir senhas, tokens ou valores do config.env.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def script_version(path: Path) -> str:
    if not path.exists():
        return "ausente"
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"Atualizador V(\d+)", text)
    return f"V{match.group(1)}" if match else "não identificado"


def env_keys(path: Path) -> list[str]:
    if not path.exists():
        return []
    keys = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        keys.append(stripped.split("=", 1)[0].strip())
    return sorted(set(keys))


def classification_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"total": 0, "classes": {}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    products = payload.get("produtos", {})
    counts = Counter()
    for item in products.values():
        if isinstance(item, dict):
            counts[str(item.get("classificacao") or "vazio")] += 1
        else:
            counts[str(item)] += 1
    return {
        "total": len(products),
        "classes": dict(sorted(counts.items())),
        "atualizado_em": payload.get("atualizado_em"),
    }


def pending_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def lock_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"existe": False}
    result: dict[str, Any] = {"existe": True}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        result["pid"] = payload.get("pid")
        result["started_at"] = payload.get("started_at")
        started_at = payload.get("started_at")
        if started_at:
            started = dt.datetime.fromisoformat(str(started_at))
            age_seconds = (
                dt.datetime.now(started.tzinfo)
                - started
            ).total_seconds()
        else:
            age_seconds = (
                dt.datetime.now().timestamp()
                - path.stat().st_mtime
            )
        result["idade_horas"] = round(age_seconds / 3600, 2)
    except Exception:
        result["conteudo_valido"] = False
        result["idade_horas"] = round(
            (
                dt.datetime.now().timestamp()
                - path.stat().st_mtime
            ) / 3600,
            2,
        )
    return result


def build_report(folder: Path) -> dict[str, Any]:
    active = folder / "atualizar_index_github.py"
    v9 = folder / "atualizar_index_github_v9.py"
    state_path = folder / "estado_atualizador_v2.json"
    state: dict[str, Any] = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {"erro": "estado inválido"}

    active_version = script_version(active)
    v9_version = script_version(v9)
    warnings = []

    if active_version != "V9":
        warnings.append(
            "O arquivo chamado pelos BATs não corresponde à V9."
        )
    if state.get("version") not in {9, 10, 11}:
        warnings.append(
            "O estado registrado indica execução anterior à V9/modular."
        )

    lock = lock_status(folder / ".atualizador_v2.lock")
    if lock.get("existe") and lock.get("idade_horas", 0) > 2:
        warnings.append(
            "Existe lock legado com mais de 2 horas; verificar processo "
            "antes de removê-lo."
        )

    return {
        "pasta": str(folder.resolve()),
        "gerado_em": dt.datetime.now().isoformat(timespec="seconds"),
        "script_ativo": {
            "arquivo": active.name,
            "versao": active_version,
            "sha256": file_hash(active) if active.exists() else "",
        },
        "script_v9": {
            "arquivo": v9.name,
            "versao": v9_version,
            "sha256": file_hash(v9) if v9.exists() else "",
        },
        "estado": {
            "version": state.get("version"),
            "last_action": state.get("last_action"),
            "last_check_at": state.get("last_check_at"),
        },
        "config_chaves": env_keys(folder / "config.env"),
        "classificacao": classification_summary(
            folder / "classificacao_ferramentas.json"
        ),
        "pendentes_classificacao": pending_count(
            folder / "produtos_pendentes_classificacao.csv"
        ),
        "lock": lock,
        "avisos": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "pasta",
        nargs="?",
        default=".",
        help="Pasta da automação legada",
    )
    parser.add_argument(
        "--saida",
        default="diagnostico_ambiente.json",
    )
    args = parser.parse_args()

    report = build_report(Path(args.pasta))
    output = Path(args.saida)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nRelatório salvo em: {output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
