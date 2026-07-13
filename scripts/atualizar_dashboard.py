# -*- coding: utf-8 -*-
"""
Atualizador do dashboard modular — versão 2.0.0 de produção.

Responsabilidades deste arquivo:
1. Ler o backup Access por meio da lógica já validada na V9.
2. Aplicar as mesmas regras de negócio de retiradas, estoque e ferramentas.
3. Gerar somente os artefatos de dados:
   - data/dashboard-data.js
   - downloads/relatorio_almoxarifado_<ano>.xlsx
4. Publicar apenas esses artefatos no Git, quando habilitado.

O HTML, o CSS e os módulos JavaScript permanecem estáveis. Isso elimina a
substituição de blocos de código dentro do index.html.
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from scripts.legacy import atualizar_index_github_v9 as legacy


SCHEMA_VERSION = 2
DATA_FILE = legacy.REPO_DIR / legacy.CONFIG.get(
    "DATA_FILE",
    "data/dashboard-data.js",
)
DOWNLOAD_FILE = legacy.REPO_DIR / legacy.CONFIG.get(
    "DOWNLOAD_FILE",
    f"downloads/relatorio_almoxarifado_{legacy.OPERATING_YEAR}.xlsx",
)
DIRECT_WHATSAPP_ENABLED = legacy.env_bool(
    "DIRECT_WHATSAPP_ENABLED",
    False,
)
HOMOLOGATION_MODE = legacy.env_bool(
    "HOMOLOGATION_MODE",
    True,
)
INCLUDE_PERSONAL_DATA = legacy.env_bool(
    "INCLUDE_PERSONAL_DATA",
    False,
)
ALLOW_PUBLIC_PERSONAL_DATA = legacy.env_bool(
    "ALLOW_PUBLIC_PERSONAL_DATA",
    False,
)


def _relative_repo_path(path: Path) -> str:
    """Retorna o caminho relativo ao repositório ou interrompe a publicação."""
    try:
        return path.resolve().relative_to(legacy.REPO_DIR.resolve()).as_posix()
    except ValueError as exc:
        raise RuntimeError(
            f"O arquivo precisa estar dentro do repositório: {path}"
        ) from exc


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    """Grava bytes de forma atômica para evitar arquivos parcialmente escritos."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(content)
    os.replace(temp, path)


def _atomic_write_text(path: Path, content: str) -> None:
    """Grava texto UTF-8 de forma atômica."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(content, encoding="utf-8")
    os.replace(temp, path)


def _file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _date_range(rows: List[Dict[str, Any]]) -> Tuple[str, str]:
    dates = sorted(
        row["Data_iso"]
        for row in rows
        if row.get("Data_iso")
    )
    if not dates:
        return "", ""

    def to_br(value: str) -> str:
        return dt.datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%Y")

    return to_br(dates[0]), to_br(dates[-1])



def _stable_alias(value: Any, prefix: str = "Colaborador") -> str:
    """Cria um identificador estável sem revelar o nome original."""
    text = str(value or "").strip()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:8]
    return f"{prefix} {digest.upper()}"


def _public_withdrawals(
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Remove dados pessoais quando o perfil público está ativado.

    A aplicação continua conseguindo agrupar registros porque os apelidos são
    determinísticos. Para conferência nominal em homologação privada, use
    INCLUDE_PERSONAL_DATA=true mantendo GIT_PUSH=false.
    """
    if INCLUDE_PERSONAL_DATA:
        return rows

    sanitized: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        original_name = item.get("Requisitante")
        withdrawal_number = item.get("Nº Retirada")
        item["Requisitante"] = _stable_alias(original_name)
        item["Responsável pelo Registro"] = ""
        item["Observação"] = ""
        if withdrawal_number:
            item["Nº Retirada"] = _stable_alias(
                withdrawal_number,
                prefix="RET-",
            ).replace(" ", "")
        sanitized.append(item)
    return sanitized


def _public_open_tools(
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Sanitiza saldos em aberto antes de gerar o arquivo público.

    Telefone só pode ser exportado quando o modo direto estiver explicitamente
    habilitado. Nomes e códigos são pseudonimizados quando dados pessoais estão
    desativados.
    """
    sanitized: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)

        if not INCLUDE_PERSONAL_DATA:
            original_name = item.get("Colaborador")
            original_code = item.get("CodigoCliente")
            withdrawal_number = item.get("NumeroRetirada")
            item["Colaborador"] = _stable_alias(original_name)
            item["CodigoCliente"] = _stable_alias(
                original_code or original_name,
                prefix="COL-",
            ).replace(" ", "")
            if withdrawal_number:
                item["NumeroRetirada"] = _stable_alias(
                    withdrawal_number,
                    prefix="RET-",
                ).replace(" ", "")

        if not DIRECT_WHATSAPP_ENABLED:
            item["TelefoneWhatsApp"] = ""

        sanitized.append(item)
    return sanitized


def validate_security_profile(
    *,
    git_push: bool | None = None,
    homologation_mode: bool | None = None,
    include_personal_data: bool | None = None,
    allow_public_personal_data: bool | None = None,
    direct_whatsapp_enabled: bool | None = None,
) -> None:
    """Bloqueia combinações de configuração inseguras."""
    git_push = legacy.GIT_PUSH if git_push is None else git_push
    homologation_mode = (
        HOMOLOGATION_MODE
        if homologation_mode is None
        else homologation_mode
    )
    include_personal_data = (
        INCLUDE_PERSONAL_DATA
        if include_personal_data is None
        else include_personal_data
    )
    allow_public_personal_data = (
        ALLOW_PUBLIC_PERSONAL_DATA
        if allow_public_personal_data is None
        else allow_public_personal_data
    )
    direct_whatsapp_enabled = (
        DIRECT_WHATSAPP_ENABLED
        if direct_whatsapp_enabled is None
        else direct_whatsapp_enabled
    )

    if homologation_mode and git_push:
        raise RuntimeError(
            "HOMOLOGATION_MODE=true exige GIT_PUSH=false."
        )

    if (
        git_push
        and include_personal_data
        and not allow_public_personal_data
    ):
        raise RuntimeError(
            "Publicação bloqueada: dados pessoais estão habilitados. "
            "Mantenha INCLUDE_PERSONAL_DATA=false ou autorize de forma "
            "explícita e documentada."
        )

    if direct_whatsapp_enabled and not include_personal_data:
        raise RuntimeError(
            "DIRECT_WHATSAPP_ENABLED=true exige "
            "INCLUDE_PERSONAL_DATA=true."
        )

def build_payload(
    data: List[Dict[str, Any]],
    stock: List[Dict[str, Any]],
    open_tools: List[Dict[str, Any]],
    generated_at: dt.datetime,
) -> Dict[str, Any]:
    """Monta o contrato único consumido pelo frontend."""
    operating_rows = legacy.operational_data(data)
    if not operating_rows:
        raise RuntimeError(
            f"Nenhuma retirada de {legacy.OPERATING_YEAR} foi encontrada."
        )

    period_start, period_end = _date_range(operating_rows)
    relative_download = _relative_repo_path(DOWNLOAD_FILE)

    return {
        "schemaVersion": SCHEMA_VERSION,
        "metadata": {
            "generatedAt": generated_at.strftime("%d/%m/%Y %H:%M:%S"),
            "referenceDate": generated_at.strftime("%Y-%m-%d"),
            "periodStart": period_start,
            "periodEnd": period_end,
            "operatingYear": legacy.OPERATING_YEAR,
            "seasonalHistoryYear": legacy.SEASONAL_HISTORY_YEAR,
            "bagsPerPackage": legacy.SACOLAS_POR_PACOTE,
            "downloadUrl": relative_download,
        },
        "features": {
            "directWhatsAppEnabled": DIRECT_WHATSAPP_ENABLED,
            "personalDataIncluded": INCLUDE_PERSONAL_DATA,
            "homologationMode": HOMOLOGATION_MODE,
        },
        "withdrawals": _public_withdrawals(data),
        "stock": stock,
        "openTools": _public_open_tools(open_tools),
    }


def serialize_payload_js(payload: Dict[str, Any]) -> str:
    """
    Serializa o payload como ES Module.

    JSON é usado dentro do JavaScript para manter o arquivo determinístico e
    simples de validar. O cabeçalho deixa claro que o arquivo é gerado.
    """
    body = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        "/**\n"
        " * Arquivo gerado automaticamente.\n"
        " * Não edite manualmente em produção.\n"
        " */\n"
        f"export const dashboardData = Object.freeze({body});\n"
    )


def _load_existing_payload(path: Path) -> Dict[str, Any] | None:
    """Lê o payload JSON do módulo gerado anteriormente, quando disponível."""
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8")
        match = re.search(
            r"Object\.freeze\((\{.*\})\);\s*$",
            content,
            flags=re.DOTALL,
        )
        if not match:
            return None
        payload = json.loads(match.group(1))
        return payload if isinstance(payload, dict) else None
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None


def _payloads_equivalent_for_publish(
    previous: Dict[str, Any],
    current: Dict[str, Any],
) -> bool:
    """Ignora somente o relógio; mudanças reais e a nova data continuam válidas."""
    previous_copy = json.loads(json.dumps(previous, ensure_ascii=False))
    current_copy = json.loads(json.dumps(current, ensure_ascii=False))
    previous_copy.get("metadata", {}).pop("generatedAt", None)
    current_copy.get("metadata", {}).pop("generatedAt", None)
    return previous_copy == current_copy


def write_artifacts(
    payload: Dict[str, Any],
    operating_rows: List[Dict[str, Any]],
) -> bool:
    """
    Gera o módulo de dados e a planilha.

    Retorna True somente quando pelo menos um artefato mudou.
    """
    previous_payload = _load_existing_payload(DATA_FILE)
    if (
        previous_payload is not None
        and DOWNLOAD_FILE.exists()
        and _payloads_equivalent_for_publish(previous_payload, payload)
    ):
        legacy.log(
            "Dados operacionais sem alteração. Artefatos preservados."
        )
        return False

    before = {
        DATA_FILE: _file_hash(DATA_FILE),
        DOWNLOAD_FILE: _file_hash(DOWNLOAD_FILE),
    }

    _atomic_write_text(DATA_FILE, serialize_payload_js(payload))
    workbook_bytes = base64.b64decode(
        legacy.make_xlsx_b64(operating_rows)
    )
    _atomic_write_bytes(DOWNLOAD_FILE, workbook_bytes)

    after = {
        DATA_FILE: _file_hash(DATA_FILE),
        DOWNLOAD_FILE: _file_hash(DOWNLOAD_FILE),
    }
    return before != after


def publish_git() -> bool:
    """Publica somente dados e planilha; o código visual não é reescrito."""
    if not legacy.GIT_PUSH:
        legacy.log("GIT_PUSH=false. Envio automático desativado.")
        return False

    files = [
        _relative_repo_path(DATA_FILE),
        _relative_repo_path(DOWNLOAD_FILE),
    ]
    legacy.run_git(["add", *files])

    staged = legacy.run_git(
        ["diff", "--cached", "--quiet"],
        check=False,
    )
    if staged.returncode == 0:
        legacy.log("Sem alterações nos artefatos. Nada para enviar.")
        return False
    if staged.returncode != 1:
        raise RuntimeError(
            "Não foi possível verificar as alterações preparadas no Git."
        )

    message = (
        "Atualização automática dos dados do dashboard - "
        f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}"
    )
    legacy.run_git(["commit", "-m", message])

    push = legacy.run_git(["push"], check=False)
    if push.returncode != 0:
        legacy.log("Push rejeitado. Sincronizando e tentando novamente.")
        legacy.run_git(["pull", "--rebase", "--autostash"])
        legacy.run_git(["push"])

    legacy.log("Dados do dashboard publicados com sucesso.")
    return True


def main() -> int:
    try:
        validate_security_profile()
        with legacy.ExecutionLock(legacy.LOCK_PATH):
            legacy.sync_repository()

            backup, backup_date, used_name_date = legacy.find_latest_backup()
            legacy.log(
                f"Backup selecionado: {backup} "
                f"(data: {backup_date:%d/%m/%Y}; "
                f"origem: {'nome' if used_name_date else 'modificação'})"
            )
            legacy.wait_until_file_is_stable(backup)

            raw, method = legacy.read_table(
                backup,
                legacy.TABELA_RETIRADAS,
            )
            raw_stock, stock_method = legacy.read_table(
                backup,
                legacy.TABELA_ESTOQUE,
            )
            raw_returns, returns_method = legacy.read_table(
                backup,
                legacy.TABELA_DEVOLUCOES,
            )
            raw_exclusions, exclusions_method = legacy.read_table(
                backup,
                legacy.TABELA_EXCLUSOES,
            )
            raw_clients, clients_method = legacy.read_table(
                backup,
                legacy.TABELA_CLIENTES,
            )

            legacy.log(
                "Tabelas lidas: "
                f"retiradas={len(raw)} ({method}), "
                f"estoque={len(raw_stock)} ({stock_method}), "
                f"devoluções={len(raw_returns)} ({returns_method}), "
                f"exclusões={len(raw_exclusions)} ({exclusions_method}), "
                f"clientes={len(raw_clients)} ({clients_method})"
            )

            classifications, classification_stats, pending = (
                legacy.prepare_tool_classifications(raw, raw_stock)
            )
            data, removed = legacy.normalize_retiradas(
                raw,
                classifications,
            )
            stock = legacy.normalize_estoque(raw_stock)
            open_tools, tool_diagnostics = legacy.normalize_open_tools(
                raw,
                raw_returns,
                raw_exclusions,
                raw_clients,
                raw_stock,
                classifications,
            )

            if not data:
                raise RuntimeError(
                    "Nenhum registro válido foi encontrado em TBRetiradas."
                )

            dates = [
                row["Data_iso"]
                for row in data
                if row.get("Data_iso")
            ]
            last_data_date = max(dates) if dates else ""

            state = legacy.load_state()
            legacy.validate_regression(
                state,
                backup_date,
                last_data_date,
                len(data),
            )

            generated_at = dt.datetime.now()
            operating_rows = legacy.operational_data(data)
            payload = build_payload(
                data,
                stock,
                open_tools,
                generated_at,
            )
            public_operating_rows = _public_withdrawals(operating_rows)
            changed = write_artifacts(payload, public_operating_rows)
            published = publish_git() if changed else False

            legacy.log(
                f"Registros operacionais: {len(operating_rows)}; "
                f"ferramentas abertas: {len(open_tools)}; "
                f"não classificados pendentes: {len(pending)}; "
                f"linhas removidas da visão de consumo: {removed}"
            )

            legacy.save_state(
                {
                    "version": 11,
                    "architecture": "modular-data-file-v2.0.0",
                    "backup_file": str(backup),
                    "backup_date": backup_date.isoformat(),
                    "last_data_date": last_data_date,
                    "records": len(data),
                    "operating_records": len(operating_rows),
                    "open_tool_rows": len(open_tools),
                    "tool_balance_diagnostics": tool_diagnostics,
                    "tool_classification_stats": classification_stats,
                    "pending_tool_classifications": len(pending),
                    "data_file": str(DATA_FILE),
                    "download_file": str(DOWNLOAD_FILE),
                    "generated_at": generated_at.isoformat(
                        timespec="seconds"
                    ),
                    "last_action": (
                        "publicado"
                        if published
                        else "atualizado_localmente"
                        if changed
                        else "sem_alteracao"
                    ),
                }
            )
            return 0

    except Exception as exc:
        legacy.log(f"ERRO: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
