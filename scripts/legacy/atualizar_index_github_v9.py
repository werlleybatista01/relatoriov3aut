# -*- coding: utf-8 -*-
"""
Atualizador V9 do dashboard interativo do almoxarifado.

Melhorias principais:
- Seleciona o backup pela data existente no nome do arquivo, não apenas pelo
  horário de modificação.
- Impede regressão para um backup ou uma última movimentação mais antiga.
- Aguarda o arquivo do Access ficar estável antes da leitura.
- Impede duas execuções simultâneas.
- Compara o conteúdo real de DATA e ESTOQUE antes de alterar o index.html.
- Evita commits a cada execução de 10 minutos quando nada mudou.
- Mantém uma atualização diária da DATA_REFERENCIA para as regras sazonais.
- Grava o index.html de forma atômica para reduzir risco de corrupção.
- Sincroniza o Git antes da alteração e trata push rejeitado.
- Mantém o layout e as regras de classificação já existentes.
- Usa 2026 em todos os indicadores operacionais.
- Mantém 2025 somente para comparações de sazonalidade.
- Gera a planilha para download somente com registros de 2026.
- Considera 1 unidade de sacola no Access como 1 pacote com 100 sacolas.
- Exibe sacolas como medida principal e pacotes como informação de apoio.
- Acrescenta uma explicação humana abaixo da projeção de estoque.
- Não informa uma quantidade recomendada de compra para sacolas.
- Separa botinas por modelo e tamanho, sem misturar produtos diferentes.
- Distingue botina de segurança, botina motorista e botas PVC.
- Distingue botas PVC brancas, pretas e sem cor informada.
- Sinaliza cadastros de botinas sem tamanho ou modelo identificável.
- Simplifica a decisão das botinas em verde, amarelo e vermelho.
- Não calcula quantidade automática de compra para botinas nesta etapa.
- Adiciona pesquisa por nome do requisitante na página Ferramentas.
- A pesquisa aceita nomes parciais e ignora acentos e maiúsculas.
- Permite limpar a pesquisa e restaurar todos os registros de 2026.
- Calcula ferramentas atualmente em aberto usando retiradas, devoluções e exclusões.
- Exibe somente saldos ainda com colaboradores; itens devolvidos ficam ocultos.
- Usa TBClientes para localizar o telefone do colaborador.
- Mostra um botão de WhatsApp somente quando existem itens atrasados.
- Solicita senha antes de abrir o WhatsApp e monta uma mensagem pronta.
- Consolida retiradas antes de descontar devoluções e exclusões.
- Evita aplicar a mesma devolução mais de uma vez em linhas duplicadas.
- Remove do log o total geral que misturava sacolas, pares e unidades.
- Classifica produtos por código em devolvível, uso permanente e consumo.
- Mantém itens não classificados fora da cobrança e gera lista local para revisão.
- Exclui ferramentas fixas e materiais de consumo da contagem e do WhatsApp.

O arquivo config.env atual continua compatível.
"""

# Sincronizado com o arquivo V9 enviado em 13/07/2026.
# Ajustes nesta cópia: BASE_DIR aponta para a raiz modular e nenhum
# segredo possui valor padrão utilizável.
from __future__ import annotations

import base64
import csv
import contextlib
import datetime as dt
import hashlib
import io
import json
import os
import re
import subprocess
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from access_parser import AccessParser  # type: ignore
except Exception:
    AccessParser = None

try:
    import pyodbc  # type: ignore
except Exception:
    pyodbc = None

from openpyxl import Workbook


# Na arquitetura modular, o config.env fica na raiz do projeto.
BASE_DIR = Path(__file__).resolve().parents[2]
TABELA_RETIRADAS = "TBRetiradas"
TABELA_DEVOLUCOES = "TBRetiradasDevolver"
TABELA_EXCLUSOES = "TBRetiradasExcluir"
TABELA_CLIENTES = "TBClientes"
TABELA_ESTOQUE = "TBEstoque"


def log(msg: str) -> None:
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def load_env(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def env_bool(name: str, default: bool = False) -> bool:
    value = CONFIG.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "sim", "yes", "on"}


def env_float(name: str, default: float) -> float:
    try:
        return float(CONFIG.get(name, str(default)).replace(",", "."))
    except Exception:
        return default


CONFIG = load_env(BASE_DIR / "config.env")

BACKUP_DIR = Path(CONFIG.get("BACKUP_DIR") or Path.home() / "Desktop")
BACKUP_PATTERNS = [
    p.strip()
    for p in CONFIG.get(
        "BACKUP_PATTERNS",
        "Backup*.mdb;Backup*.accdb;*.mdb;*.accdb",
    ).split(";")
    if p.strip()
]
ACCESS_PASSWORD = CONFIG.get("ACCESS_PASSWORD", "")
REPO_DIR = Path(CONFIG.get("REPO_DIR") or BASE_DIR)
INDEX_PATH = REPO_DIR / CONFIG.get("INDEX_FILE", "index.html")
GIT_PUSH = env_bool("GIT_PUSH", False)
OPERATING_YEAR = int(CONFIG.get("OPERATING_YEAR", "2026"))
SEASONAL_HISTORY_YEAR = int(
    CONFIG.get("SEASONAL_HISTORY_YEAR", "2025")
)
SACOLAS_POR_PACOTE = int(CONFIG.get("SACOLAS_POR_PACOTE", "100"))
WHATSAPP_PASSWORD = CONFIG.get("WHATSAPP_PASSWORD", "")
if SACOLAS_POR_PACOTE <= 0:
    raise ValueError("SACOLAS_POR_PACOTE precisa ser maior que zero")

STATE_PATH = Path(CONFIG.get("STATE_FILE") or BASE_DIR / "estado_atualizador_v2.json")
LOCK_PATH = Path(CONFIG.get("LOCK_FILE") or BASE_DIR / ".atualizador_v2.lock")
LOCK_STALE_MINUTES = env_float("LOCK_STALE_MINUTES", 120.0)
BACKUP_STABILITY_SECONDS = env_float("BACKUP_STABILITY_SECONDS", 2.0)
BACKUP_STABILITY_ATTEMPTS = max(
    2, int(env_float("BACKUP_STABILITY_ATTEMPTS", 4.0))
)
MAX_RECORD_DROP_PERCENT = env_float("MAX_RECORD_DROP_PERCENT", 15.0)
ALLOW_RECORD_DROP = env_bool("ALLOW_RECORD_DROP", False)
ALLOW_BACKUP_REGRESSION = env_bool("ALLOW_BACKUP_REGRESSION", False)

TOOL_CLASSIFICATION_PATH = Path(
    CONFIG.get("TOOL_CLASSIFICATION_FILE")
    or BASE_DIR / "classificacao_ferramentas.json"
)
TOOL_CLASSIFICATION_PENDING_PATH = Path(
    CONFIG.get("TOOL_CLASSIFICATION_PENDING_FILE")
    or BASE_DIR / "produtos_pendentes_classificacao.csv"
)
VALID_TOOL_CLASSIFICATIONS = {
    "devolvivel",
    "uso_permanente",
    "consumo",
    "ignorar",
    "nao_classificado",
}

# A ordem é importante: consumo explícito vem primeiro, depois equipamentos
# devolvíveis e, por último, ferramentas manuais de uso permanente. Assim,
# "disco para Makita" não vira máquina e "martelo demolidor" não vira martelo
# manual. Após a primeira identificação, a decisão fica persistida por código.
CONSUMABLE_PATTERNS = [
    r"\bfita isolante\b", r"\bfita veda rosca\b",
    r"\bfita crepe\b", r"\bfita adesiva\b",
    r"\bdisco(?:s)?\b", r"\bbroca(?:s)?\b", r"\blixa(?:s)?\b",
    r"\bparafuso(?:s)?\b", r"\bprego(?:s)?\b",
    r"\bporca(?:s)?\b", r"\barruela(?:s)?\b",
    r"\bbucha(?:s)?\b", r"\bcola\b", r"\bsilicone\b",
    r"\bselante\b", r"\babracadeira(?:s)?\b",
    r"\beletrodo(?:s)?\b", r"\barame\b",
    r"\blamina(?:s)?\b", r"\brefil\b", r"\btinta\b",
    r"\bsolvente\b", r"\bthinner\b", r"\boleo\b",
    r"\bgraxa\b", r"\bcombustivel\b", r"\bgasolina\b",
    r"\bquerosene\b", r"\bcordao\b", r"\blinha de nylon\b",
]

RETURNABLE_PATTERNS = [
    r"\bmartelete\b", r"\bmartelo demolidor\b",
    r"\bchave de impacto\b", r"\bfuradeira\b",
    r"\bparafusadeira\b", r"\bmotosserra\b",
    r"\bmoto serra\b", r"\brocadeira\b",
    r"\bserra marmore\b", r"\bserra circular\b",
    r"\bserra tico tico\b", r"\besmerilhadeira\b",
    r"\blixadeira\b", r"\bpolitriz\b",
    r"\bmaquina de solda\b", r"\binversora de solda\b",
    r"\bcompactador\b", r"\bbetoneira\b", r"\bgerador\b",
    r"\bcompressor\b", r"\blavadora\b",
    r"\bbomba d agua\b", r"\bsoprador\b", r"\bescada\b",
    r"\bandaime\b", r"\bextensao\b", r"\bsonda\b",
    r"\bmultimetro\b", r"\bnivel laser\b", r"\btalha\b",
    r"\bguincho\b", r"\bmacaco hidraulico\b",
    r"\bregua vibratoria\b", r"\bgdc\s*\d+\b",
    r"\bgws\s*\d+\b", r"\bga\s*\d+\b",
]

PERMANENT_PATTERNS = [
    r"\bcarrinho de mao\b", r"\bpicareta\b", r"\benxada\b",
    r"\btrena\b", r"\bregua\b", r"\bcolher de pedreiro\b",
    r"\bcolher pedreiro\b", r"\bmarreta\b", r"\bmartelo\b",
    r"\bchave\b", r"\balicate\b", r"\bpa\b",
    r"\bnivel de mao\b", r"\bnivel manual\b", r"\bfacao\b",
    r"\bcavadeira\b", r"\bpeneira\b", r"\bfoice\b",
    r"\bancinho\b", r"\brastelo\b", r"\bprumo\b",
    r"\bdesempenadeira\b", r"\besquadro\b", r"\bformao\b",
    r"\bserrote\b", r"\bpe de cabra\b",
]


def safe_text(value: Any) -> str:
    if value is None or value == "(Empty Date)" or isinstance(value, list):
        return ""
    return str(value).strip()


def normalize_code(value: Any) -> str:
    text = safe_text(value)
    if re.fullmatch(r"-?\d+\.0+", text):
        return text.split(".", 1)[0]
    return text


def norm(value: Any) -> str:
    text = unicodedata.normalize("NFKD", safe_text(value))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def to_float(value: Any) -> float:
    if (
        value is None
        or value == ""
        or value == "(Empty Date)"
        or isinstance(value, list)
    ):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    text = re.sub(r"[^0-9,.\-]", "", str(value).strip())
    if text.count(",") == 1 and text.rfind(",") > text.rfind("."):
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except Exception:
        return 0.0


def fmt_date(value: Any) -> str:
    text = safe_text(value)
    if not text:
        return ""
    if re.match(r"^\d{2}/\d{2}/\d{4}$", text):
        return text

    formats = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y  %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
    )
    for fmt in formats:
        try:
            return dt.datetime.strptime(text[:19], fmt).strftime("%d/%m/%Y")
        except Exception:
            pass
    return text


def iso_from_br(value: str) -> str:
    try:
        return dt.datetime.strptime(value, "%d/%m/%Y").strftime("%Y-%m-%d")
    except Exception:
        return ""


def record_year(row: Dict[str, Any]) -> Optional[int]:
    value = row.get("Ano")
    try:
        if value not in {None, ""}:
            return int(value)
    except Exception:
        pass

    date_iso = safe_text(row.get("Data_iso"))
    if re.match(r"^\\d{4}-\\d{2}-\\d{2}$", date_iso):
        return int(date_iso[:4])
    return None


def operational_data(
    data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return [
        row
        for row in data
        if record_year(row) == OPERATING_YEAR
    ]


def guess_category(product: Any) -> str:
    text = safe_text(product).upper()
    if "BOTINA" in text or re.search(r"\bBOTA\b", text):
        return "Botinas"
    if (
        "SACOLA" in text
        or "SACO DE LIXO" in text
        or re.search(r"\bSACO\b", text)
    ):
        return "Sacolas"
    if "ENXADA" in text:
        return "Enxadas"
    if any(
        word in text
        for word in [
            "CAMISA",
            "CAMISETA",
            "CALÇA",
            "CALCA",
            "UNIFORME",
            "JALECO",
            "BONÉ",
            "BONE",
            "COLETE",
            "BERMUDA",
            "MEIA",
            "CAPA DE CHUVA",
        ]
    ):
        return "Uniformes"
    return "Ferramentas"



def matches_any_pattern(text: str, patterns: List[str]) -> Optional[str]:
    for pattern in patterns:
        if re.search(pattern, text):
            return pattern
    return None


def infer_tool_classification(product: Any) -> Tuple[str, str]:
    """Sugere a classe inicial pelo nome; a decisão é persistida por código.

    O nome é usado somente para criar a classificação inicial. Nas execuções
    seguintes, o código do produto é a chave autoritativa do cadastro local.
    """
    product_text = norm(product)
    if not product_text:
        return "nao_classificado", "nome_vazio"

    category = guess_category(product)
    if category in {"Uniformes", "Botinas", "Sacolas"}:
        return "ignorar", f"categoria_{norm(category)}"

    pattern = matches_any_pattern(product_text, CONSUMABLE_PATTERNS)
    if pattern:
        return "consumo", f"regra_consumo:{pattern}"

    pattern = matches_any_pattern(product_text, RETURNABLE_PATTERNS)
    if pattern:
        return "devolvivel", f"regra_devolvivel:{pattern}"

    pattern = matches_any_pattern(product_text, PERMANENT_PATTERNS)
    if pattern:
        return "uso_permanente", f"regra_permanente:{pattern}"

    return "nao_classificado", "revisao_manual"


def load_tool_classification_registry() -> Dict[str, Any]:
    if not TOOL_CLASSIFICATION_PATH.exists():
        return {
            "versao": 1,
            "descricao": (
                "Classificação local por código: devolvivel, "
                "uso_permanente, consumo, ignorar ou nao_classificado."
            ),
            "produtos": {},
        }

    try:
        payload = json.loads(
            TOOL_CLASSIFICATION_PATH.read_text(encoding="utf-8")
        )
    except Exception as exc:
        raise RuntimeError(
            "Não foi possível ler o arquivo de classificação "
            f"{TOOL_CLASSIFICATION_PATH}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise RuntimeError(
            "O arquivo classificacao_ferramentas.json precisa conter um "
            "objeto JSON."
        )
    products = payload.get("produtos")
    if not isinstance(products, dict):
        payload["produtos"] = {}
    payload.setdefault("versao", 1)
    payload.setdefault(
        "descricao",
        "Classificação local por código de produto.",
    )
    return payload


def write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        json.loads(temporary.read_text(encoding="utf-8"))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def prepare_tool_classifications(
    withdrawals: List[Dict[str, Any]],
    stock_rows: List[Dict[str, Any]],
) -> Tuple[Dict[str, str], Dict[str, Any], List[Dict[str, Any]]]:
    """Cria/atualiza o cadastro local e devolve o mapa por código.

    Uma classificação já existente é preservada. Produtos novos recebem uma
    sugestão inicial pelo nome. Os não reconhecidos ficam fora da cobrança e
    são gravados em CSV para revisão.
    """
    registry = load_tool_classification_registry()
    products: Dict[str, Any] = registry.setdefault("produtos", {})

    candidates: Dict[str, Dict[str, Any]] = {}

    for row in stock_rows:
        code = normalize_code(row.get("IDCodigo"))
        name = safe_text(row.get("NomeProduto"))
        if not code or not name:
            continue
        candidates.setdefault(
            code,
            {
                "codigo": code,
                "nome": name,
                "origem_nome": "TBEstoque",
                "movimentacoes": 0,
            },
        )

    for row in withdrawals:
        code = normalize_code(row.get("CodigoProduto"))
        name = safe_text(row.get("NomeProduto"))
        if not name:
            continue
        if not code:
            code = "SEM_CODIGO:" + norm(name)
        item = candidates.setdefault(
            code,
            {
                "codigo": code,
                "nome": name,
                "origem_nome": "TBRetiradas",
                "movimentacoes": 0,
            },
        )
        item["movimentacoes"] = int(item.get("movimentacoes") or 0) + 1
        if item.get("origem_nome") != "TBEstoque":
            item["nome"] = name

    changed = False
    classifications: Dict[str, str] = {}
    pending: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {
        "devolvivel": 0,
        "uso_permanente": 0,
        "consumo": 0,
        "ignorar": 0,
        "nao_classificado": 0,
        "novos": 0,
        "alterados": 0,
    }

    for code, candidate in sorted(candidates.items()):
        name = safe_text(candidate.get("nome"))
        existing = products.get(code)
        if isinstance(existing, str):
            existing = {
                "nome": name,
                "classificacao": existing,
                "origem": "manual",
            }
        if not isinstance(existing, dict):
            existing = None

        classification = ""
        if existing:
            classification = norm(existing.get("classificacao")).replace(
                " ", "_"
            )
            if classification not in VALID_TOOL_CLASSIFICATIONS:
                classification = ""

        if not classification:
            classification, rule = infer_tool_classification(name)
            existing = {
                "nome": name,
                "classificacao": classification,
                "origem": "automatica",
                "regra": rule,
            }
            products[code] = existing
            counts["novos"] += 1
            changed = True
        else:
            assert existing is not None
            # Reavalia somente itens ainda pendentes que foram criados
            # automaticamente. Classificações conhecidas ou editadas pelo
            # usuário permanecem estáveis por código.
            if (
                classification == "nao_classificado"
                and safe_text(existing.get("origem")) == "automatica"
            ):
                inferred, rule = infer_tool_classification(name)
                if inferred != classification:
                    classification = inferred
                    existing["classificacao"] = inferred
                    existing["regra"] = rule
                    counts["alterados"] += 1
                    changed = True

            if safe_text(existing.get("nome")) != name:
                existing["nome"] = name
                changed = True
            products[code] = existing

        classifications[code] = classification
        counts[classification] = counts.get(classification, 0) + 1

        if classification == "nao_classificado":
            pending.append(
                {
                    "CodigoProduto": code,
                    "NomeProduto": name,
                    "MovimentacoesEncontradas": int(
                        candidate.get("movimentacoes") or 0
                    ),
                    "ClassificacaoSugerida": "",
                    "OpcoesValidas": (
                        "devolvivel | uso_permanente | consumo | ignorar"
                    ),
                }
            )

    registry["produtos"] = products
    registry["atualizado_em"] = dt.datetime.now().isoformat(
        timespec="seconds"
    )
    if changed or not TOOL_CLASSIFICATION_PATH.exists():
        write_json_atomic(TOOL_CLASSIFICATION_PATH, registry)

    write_pending_classifications_csv(pending)
    counts["arquivo_alterado"] = int(changed)
    counts["total_produtos"] = len(candidates)
    counts["pendentes"] = len(pending)
    return classifications, counts, pending


def write_pending_classifications_csv(
    pending: List[Dict[str, Any]],
) -> None:
    TOOL_CLASSIFICATION_PENDING_PATH.parent.mkdir(
        parents=True, exist_ok=True
    )
    if not pending:
        TOOL_CLASSIFICATION_PENDING_PATH.unlink(missing_ok=True)
        return

    temporary = TOOL_CLASSIFICATION_PENDING_PATH.with_name(
        TOOL_CLASSIFICATION_PENDING_PATH.name + ".tmp"
    )
    fieldnames = [
        "CodigoProduto",
        "NomeProduto",
        "MovimentacoesEncontradas",
        "ClassificacaoSugerida",
        "OpcoesValidas",
    ]
    try:
        with temporary.open(
            "w", encoding="utf-8-sig", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(pending)
        os.replace(temporary, TOOL_CLASSIFICATION_PENDING_PATH)
    finally:
        temporary.unlink(missing_ok=True)


def classification_for_product(
    code: Any,
    product: Any,
    classifications: Dict[str, str],
) -> str:
    normalized_code = normalize_code(code)
    if not normalized_code:
        normalized_code = "SEM_CODIGO:" + norm(product)
    classification = classifications.get(
        normalized_code,
        "nao_classificado",
    )
    if classification not in VALID_TOOL_CLASSIFICATIONS:
        return "nao_classificado"
    return classification


def extract_size(text: Any) -> str:
    value = safe_text(text)
    match = re.search(r"\((\d{2})\)", value)
    if match:
        return match.group(1)
    match = re.search(r"\b(3[3-9]|4[0-9]|5[0-2])\b", value)
    return match.group(1) if match else ""


def botina_model(product: Any) -> str:
    """Normaliza o modelo usando o nome cadastrado no Access."""
    text = norm(product)
    if not text:
        return "Modelo não identificado"
    if "motorista" in text:
        return "Botina motorista"
    if "pvc" in text or "borracha" in text:
        if "branca" in text or "branco" in text:
            return "Bota PVC branca"
        if "preta" in text or "preto" in text:
            return "Bota PVC preta"
        return "Bota PVC"
    if "botina" in text or "seguranca" in text:
        return "Botina de segurança"
    return "Modelo não identificado"


def extract_backup_date(path: Path) -> Optional[dt.date]:
    name = path.stem

    match = re.search(
        r"(?<!\d)(\d{2})[-_. ](\d{2})[-_. ](\d{4})(?!\d)",
        name,
    )
    if match:
        day, month, year = map(int, match.groups())
        try:
            return dt.date(year, month, day)
        except ValueError:
            pass

    match = re.search(
        r"(?<!\d)(\d{4})[-_. ](\d{2})[-_. ](\d{2})(?!\d)",
        name,
    )
    if match:
        year, month, day = map(int, match.groups())
        try:
            return dt.date(year, month, day)
        except ValueError:
            pass

    return None


def list_backup_candidates() -> List[Path]:
    if not BACKUP_DIR.exists():
        raise FileNotFoundError(
            f"Pasta de backup não encontrada: {BACKUP_DIR}"
        )

    unique: Dict[str, Path] = {}
    for pattern in BACKUP_PATTERNS:
        for path in BACKUP_DIR.glob(pattern):
            if path.is_file() and not path.name.startswith("~$"):
                unique[str(path.resolve()).lower()] = path

    files = list(unique.values())
    if not files:
        raise FileNotFoundError(
            f"Nenhum backup Access encontrado em {BACKUP_DIR}"
        )
    return files


def backup_sort_key(path: Path) -> Tuple[int, dt.date, int]:
    parsed_date = extract_backup_date(path)
    has_date = 1 if parsed_date else 0
    fallback_date = dt.datetime.fromtimestamp(path.stat().st_mtime).date()
    effective_date = parsed_date or fallback_date
    return has_date, effective_date, path.stat().st_mtime_ns


def find_latest_backup() -> Tuple[Path, dt.date, bool]:
    files = list_backup_candidates()
    selected = max(files, key=backup_sort_key)
    parsed_date = extract_backup_date(selected)
    used_filename_date = parsed_date is not None
    effective_date = (
        parsed_date
        or dt.datetime.fromtimestamp(selected.stat().st_mtime).date()
    )

    if not used_filename_date:
        log(
            "AVISO: não foi possível extrair a data do nome do backup. "
            "Foi usada a data de modificação como fallback."
        )

    return selected, effective_date, used_filename_date


def wait_until_file_is_stable(path: Path) -> None:
    previous: Optional[Tuple[int, int]] = None

    for attempt in range(1, BACKUP_STABILITY_ATTEMPTS + 1):
        stat = path.stat()
        current = (stat.st_size, stat.st_mtime_ns)

        if previous == current:
            log(
                f"Backup estável: {path.name} "
                f"({stat.st_size:,} bytes)."
            )
            return

        previous = current
        if attempt < BACKUP_STABILITY_ATTEMPTS:
            time.sleep(BACKUP_STABILITY_SECONDS)

    raise RuntimeError(
        "O backup continua sendo alterado por outro processo. "
        "A execução foi cancelada para evitar leitura incompleta."
    )


def read_table_access_parser(
    db_path: Path, table_name: str
) -> List[Dict[str, Any]]:
    if AccessParser is None:
        raise RuntimeError("access-parser não instalado")

    database = AccessParser(str(db_path))
    if table_name not in database.catalog:
        raise RuntimeError(f"Tabela {table_name} não encontrada")

    table = database.get_table(table_name)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        table.parse()

    data = table.parsed_table
    keys = list(data.keys())
    count = max((len(values) for values in data.values()), default=0)

    return [
        {
            key: data[key][index] if index < len(data[key]) else None
            for key in keys
        }
        for index in range(count)
    ]


def read_table_odbc(
    db_path: Path, table_name: str
) -> List[Dict[str, Any]]:
    if pyodbc is None:
        raise RuntimeError("pyodbc não instalado")

    connection_string = (
        r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
        f"DBQ={db_path};"
    )
    if ACCESS_PASSWORD:
        connection_string += f"PWD={ACCESS_PASSWORD};"

    connection = pyodbc.connect(connection_string, autocommit=True)
    try:
        cursor = connection.cursor()
        cursor.execute(f"SELECT * FROM [{table_name}]")
        columns = [column[0] for column in cursor.description]
        return [
            {
                columns[index]: row[index]
                for index in range(len(columns))
            }
            for row in cursor.fetchall()
        ]
    finally:
        connection.close()


def read_table(
    db_path: Path, table_name: str
) -> Tuple[List[Dict[str, Any]], str]:
    try:
        return read_table_access_parser(db_path, table_name), "access_parser"
    except Exception as exc:
        log(
            f"access_parser falhou na tabela {table_name}: {exc}. "
            "Tentando pyodbc."
        )
        return read_table_odbc(db_path, table_name), "pyodbc"



def parse_date_value(value: Any) -> Optional[dt.date]:
    text = safe_text(value)
    if not text:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
    ):
        try:
            return dt.datetime.strptime(text[:19], fmt).date()
        except Exception:
            pass
    return None


def tool_balance_key(row: Dict[str, Any]) -> Tuple[str, str, str]:
    return (
        normalize_code(row.get("NumeroRetirada")),
        normalize_code(row.get("CodigoProduto")),
        normalize_code(row.get("CodigoCliente")),
    )


def normalize_phone_br(value: Any) -> str:
    digits = re.sub(r"\D+", "", safe_text(value))
    if not digits:
        return ""
    if digits.startswith("55") and len(digits) in {12, 13}:
        return digits
    if len(digits) in {10, 11}:
        return "55" + digits
    return digits


def normalize_open_tools(
    withdrawals: List[Dict[str, Any]],
    returns: List[Dict[str, Any]],
    exclusions: List[Dict[str, Any]],
    clients: List[Dict[str, Any]],
    stock_rows: List[Dict[str, Any]],
    tool_classifications: Dict[str, str],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Monta somente os itens devolvíveis que ainda estão em aberto.

    Regra principal:
    1. Soma todas as linhas da retirada pela chave
       (número da retirada, produto e colaborador).
    2. Soma todas as devoluções da mesma chave.
    3. Soma todas as exclusões da mesma chave.
    4. Calcula o saldo uma única vez.

    Isso evita descontar a mesma devolução repetidamente quando a retirada
    original possui mais de uma linha para o mesmo produto.

    Devoluções e exclusões ficam invisíveis no dashboard. Elas servem apenas
    para reduzir o saldo. Itens totalmente devolvidos ou excluídos não entram
    no resultado.
    """
    diagnostics: Dict[str, Any] = {
        "withdrawal_groups": 0,
        "duplicate_withdrawal_groups": 0,
        "adjusted_by_return_groups": 0,
        "adjusted_by_exclusion_groups": 0,
        "fully_closed_groups": 0,
        "open_groups": 0,
        "negative_balance_groups": 0,
        "positive_return_rows": 0,
        "positive_exclusion_rows": 0,
        "devolvable_groups": 0,
        "devolvable_quantity": 0.0,
        "permanent_groups": 0,
        "permanent_quantity": 0.0,
        "consumption_groups": 0,
        "consumption_quantity": 0.0,
        "ignored_groups": 0,
        "ignored_quantity": 0.0,
        "unclassified_groups": 0,
        "unclassified_quantity": 0.0,
    }

    returned: Dict[Tuple[str, str, str], float] = {}
    excluded: Dict[Tuple[str, str, str], float] = {}

    for row in returns:
        key = tool_balance_key(row)
        raw_qty = to_float(row.get("QtdeRetirada"))
        if raw_qty > 0:
            diagnostics["positive_return_rows"] += 1
        # A tabela de devoluções representa redução do saldo.
        returned[key] = returned.get(key, 0.0) - abs(raw_qty)

    for row in exclusions:
        key = tool_balance_key(row)
        raw_qty = to_float(row.get("QtdeRetirada"))
        if raw_qty > 0:
            diagnostics["positive_exclusion_rows"] += 1
        # A tabela de exclusões também representa redução do saldo.
        excluded[key] = excluded.get(key, 0.0) - abs(raw_qty)

    client_map: Dict[str, Dict[str, Any]] = {}
    for row in clients:
        code = normalize_code(row.get("IDCodigoCli"))
        if code:
            client_map[code] = row

    stock_map: Dict[str, Dict[str, Any]] = {}
    for row in stock_rows:
        code = normalize_code(row.get("IDCodigo"))
        if code:
            stock_map[code] = row

    # Consolida primeiro todas as linhas da retirada.
    withdrawal_groups: Dict[
        Tuple[str, str, str],
        Dict[str, Any],
    ] = {}

    for row in withdrawals:
        due_date = parse_date_value(row.get("DataDevolucao"))

        product = safe_text(row.get("NomeProduto"))
        if not product:
            continue

        # Evita misturar as páginas próprias de uniformes, botinas e sacolas.
        category_guess = guess_category(product)
        if category_guess in {"Uniformes", "Botinas", "Sacolas"}:
            continue

        key = tool_balance_key(row)
        source_qty = abs(to_float(row.get("QtdeRetirada")))
        if source_qty <= 0:
            continue

        item = withdrawal_groups.setdefault(
            key,
            {
                "rows": [],
                "withdrawn": 0.0,
                "withdrawal_dates": [],
                "due_dates": [],
            },
        )
        item["rows"].append(row)
        item["withdrawn"] += source_qty

        withdrawal_date = parse_date_value(row.get("DataRetirada"))
        if withdrawal_date:
            item["withdrawal_dates"].append(withdrawal_date)
        if due_date:
            item["due_dates"].append(due_date)

    diagnostics["withdrawal_groups"] = len(withdrawal_groups)
    diagnostics["duplicate_withdrawal_groups"] = sum(
        1 for group in withdrawal_groups.values()
        if len(group["rows"]) > 1
    )
    result: List[Dict[str, Any]] = []
    today = dt.date.today()

    for key, group in withdrawal_groups.items():
        withdrawn_qty = float(group["withdrawn"])
        returned_qty = abs(float(returned.get(key, 0.0)))
        excluded_qty = abs(float(excluded.get(key, 0.0)))
        if returned_qty > 0:
            diagnostics["adjusted_by_return_groups"] += 1
        if excluded_qty > 0:
            diagnostics["adjusted_by_exclusion_groups"] += 1
        balance = withdrawn_qty - returned_qty - excluded_qty

        if balance < -0.000001:
            diagnostics["negative_balance_groups"] += 1
            # Saldo negativo significa baixa maior que a retirada.
            # O dashboard não deve mostrar quantidade negativa.
            continue

        if balance <= 0.000001:
            diagnostics["fully_closed_groups"] += 1
            continue

        rows = group["rows"]
        row = rows[0]

        product_code = normalize_code(row.get("CodigoProduto"))
        client_code = normalize_code(row.get("CodigoCliente"))
        client = client_map.get(client_code, {})
        stock = stock_map.get(product_code, {})
        product_name = (
            safe_text(row.get("NomeProduto"))
            or safe_text(stock.get("NomeProduto"))
        )
        classification = classification_for_product(
            product_code,
            product_name,
            tool_classifications,
        )

        if classification == "uso_permanente":
            diagnostics["permanent_groups"] += 1
            diagnostics["permanent_quantity"] += balance
            continue
        if classification == "consumo":
            diagnostics["consumption_groups"] += 1
            diagnostics["consumption_quantity"] += balance
            continue
        if classification == "ignorar":
            diagnostics["ignored_groups"] += 1
            diagnostics["ignored_quantity"] += balance
            continue
        if classification != "devolvivel":
            diagnostics["unclassified_groups"] += 1
            diagnostics["unclassified_quantity"] += balance
            continue

        diagnostics["devolvable_groups"] += 1
        diagnostics["devolvable_quantity"] += balance
        diagnostics["open_groups"] += 1

        withdrawal_dates: List[dt.date] = group["withdrawal_dates"]
        due_dates: List[dt.date] = group["due_dates"]

        # Usa a retirada mais antiga e o prazo mais próximo para não
        # esconder um atraso quando a mesma chave possui linhas divergentes.
        withdrawal_date = (
            min(withdrawal_dates) if withdrawal_dates else None
        )
        due_date = min(due_dates) if due_dates else None

        days_out = (
            max(0, (today - withdrawal_date).days)
            if withdrawal_date
            else 0
        )
        if due_date is None:
            overdue_days = 0
            status = "Sem prazo"
            status_class = "ok"
            status_text = "Sem prazo de devolução cadastrado"
        else:
            overdue_days = max(0, (today - due_date).days)
            days_until_due = (due_date - today).days

            if overdue_days > 0:
                status = "Atrasado"
                status_class = "danger"
                status_text = f"Atrasado há {overdue_days} dia(s)"
            elif days_until_due <= 3:
                status = "Vence em breve"
                status_class = "warn"
                status_text = (
                    "Vence hoje"
                    if days_until_due == 0
                    else f"Vence em {days_until_due} dia(s)"
                )
            else:
                status = "No prazo"
                status_class = "ok"
                status_text = f"Vence em {days_until_due} dia(s)"

        product_names = [
            safe_text(source.get("NomeProduto"))
            for source in rows
            if safe_text(source.get("NomeProduto"))
        ]
        client_names = [
            safe_text(source.get("NomeCliente"))
            for source in rows
            if safe_text(source.get("NomeCliente"))
        ]
        observations = [
            safe_text(source.get("Observacao"))
            for source in rows
            if safe_text(source.get("Observacao"))
        ]

        result.append(
            {
                "NumeroRetirada": key[0],
                "CodigoProduto": product_code,
                "CodigoCliente": client_code,
                "Colaborador": (
                    safe_text(client.get("Cliente"))
                    or (client_names[0] if client_names else "")
                    or "Não informado"
                ),
                "Produto": (
                    product_names[0]
                    if product_names
                    else safe_text(stock.get("NomeProduto"))
                    or "Produto não informado"
                ),
                "CategoriaEstoque": safe_text(stock.get("Categoria")),
                "QuantidadeEmAberto": round(balance, 6),
                "DataRetirada": (
                    withdrawal_date.strftime("%d/%m/%Y")
                    if withdrawal_date
                    else fmt_date(row.get("DataRetirada"))
                ),
                "DataRetiradaISO": (
                    withdrawal_date.isoformat() if withdrawal_date else ""
                ),
                "PrazoDevolucao": (
                    due_date.strftime("%d/%m/%Y") if due_date else ""
                ),
                "PrazoDevolucaoISO": (
                    due_date.isoformat() if due_date else ""
                ),
                "DiasFora": days_out,
                "DiasAtraso": overdue_days,
                "Status": status,
                "StatusClasse": status_class,
                "StatusTexto": status_text,
                "TelefoneWhatsApp": normalize_phone_br(
                    client.get("TelCelular")
                ),
                "Setor": safe_text(row.get("Setor")),
                "Departamento": safe_text(row.get("Departamento")),
                "Observacao": observations[0] if observations else "",
            }
        )

    result.sort(
        key=lambda item: (
            0 if item["StatusClasse"] == "danger" else
            1 if item["StatusClasse"] == "warn" else 2,
            item.get("PrazoDevolucaoISO") or "9999-12-31",
            norm(item.get("Colaborador")),
            norm(item.get("Produto")),
        )
    )
    return result, diagnostics


def normalize_retiradas(
    raw: List[Dict[str, Any]],
    tool_classifications: Dict[str, str],
) -> Tuple[List[Dict[str, Any]], int]:
    output: List[Dict[str, Any]] = []
    removed = 0
    weekdays = [
        "Segunda",
        "Terça",
        "Quarta",
        "Quinta",
        "Sexta",
        "Sábado",
        "Domingo",
    ]

    for index, row in enumerate(raw, 1):
        product = safe_text(row.get("NomeProduto"))
        number = safe_text(row.get("NumeroRetirada"))
        date_br = fmt_date(row.get("DataRetirada"))

        if not product or not number or not date_br:
            continue

        # A interpretação de valores negativos permanece igual à versão
        # anterior nesta etapa. Para sacolas, cada unidade registrada no
        # Access representa um pacote fechado com SACOLAS_POR_PACOTE sacolas.
        source_quantity = abs(to_float(row.get("QtdeRetirada")))
        category = guess_category(product)
        package_quantity = (
            source_quantity if category == "Sacolas" else 0.0
        )
        quantity = (
            source_quantity * SACOLAS_POR_PACOTE
            if category == "Sacolas"
            else source_quantity
        )

        if category in {"Ferramentas", "Enxadas"}:
            classification = classification_for_product(
                row.get("CodigoProduto"),
                product,
                tool_classifications,
            )
            if classification != "devolvivel":
                removed += 1
                continue

        date_iso = iso_from_br(date_br)
        weekday = ""
        if date_iso:
            weekday = weekdays[
                dt.datetime.strptime(date_iso, "%Y-%m-%d").weekday()
            ]

        output.append(
            {
                "Item": safe_text(row.get("IDCodigo")) or str(index),
                "Nome do Produto": product,
                "Qtde": (
                    str(int(quantity))
                    if float(quantity).is_integer()
                    else str(quantity).replace(".", ",")
                ),
                "Unidade Medida": (
                    "sacolas"
                    if category == "Sacolas"
                    else safe_text(row.get("UnidadeMedida"))
                ),
                "Pacotes": (
                    str(int(package_quantity))
                    if category == "Sacolas"
                    and float(package_quantity).is_integer()
                    else (
                        str(package_quantity).replace(".", ",")
                        if category == "Sacolas"
                        else ""
                    )
                ),
                "Sacolas por pacote": (
                    SACOLAS_POR_PACOTE
                    if category == "Sacolas"
                    else ""
                ),
                "Requisitante": safe_text(row.get("NomeCliente")),
                "Data_fmt": date_br,
                "Data_iso": date_iso,
                "Ano": int(date_iso[:4]) if date_iso else None,
                "Mes": date_iso[:7] if date_iso else "",
                "DiaSemana": weekday,
                "Status": safe_text(row.get("StatusDevolucao")),
                "Observação": safe_text(row.get("Observacao")),
                "Nº Retirada": number,
                "Responsável pelo Registro": safe_text(
                    row.get("ResposavelRegistro")
                ),
                "Categoria": category,
                "Modelo": (
                    botina_model(product) if category == "Botinas" else ""
                ),
                "Tamanho": (
                    extract_size(product) if category == "Botinas" else ""
                ),
                "Qtde_num": quantity,
                "Pacotes_num": package_quantity,
            }
        )

    output.sort(
        key=lambda item: (
            item["Data_iso"],
            item["Nº Retirada"],
            item["Nome do Produto"],
        )
    )
    return output, removed


def normalize_estoque(
    raw: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    grouped: Dict[Tuple[str, str, str], Dict[str, Any]] = {}

    for row in raw:
        product = safe_text(row.get("NomeProduto"))
        if not product:
            continue
        category = guess_category(product)
        if category not in {"Botinas", "Sacolas"}:
            continue

        if category == "Botinas":
            model = botina_model(product)
            size = extract_size(product)
            display_name = (
                f"{model} - tamanho {size}" if size else f"{model} - sem tamanho"
            )
            key = (category, model, size or "Sem tamanho")
        else:
            model = ""
            size = ""
            display_name = product
            key = (category, "", product)

        item = grouped.setdefault(
            key,
            {
                "Categoria": category,
                "Modelo": model,
                "Tamanho": size,
                "Nome do Produto": display_name,
                "QtdeEstoque": 0.0,
                "EstoqueMin": 0.0,
                "PacotesEstoque": 0.0,
                "PacotesMin": 0.0,
                "SacolasPorPacote": SACOLAS_POR_PACOTE if category == "Sacolas" else 0,
                "ProdutosOrigem": [],
            },
        )
        raw_stock = to_float(row.get("QtdeEstoque"))
        raw_minimum = to_float(row.get("EstoqueMin"))
        if category == "Sacolas":
            item["PacotesEstoque"] += raw_stock
            item["PacotesMin"] += raw_minimum
            item["QtdeEstoque"] += raw_stock * SACOLAS_POR_PACOTE
            item["EstoqueMin"] += raw_minimum * SACOLAS_POR_PACOTE
        else:
            item["QtdeEstoque"] += raw_stock
            item["EstoqueMin"] += raw_minimum
        if product not in item["ProdutosOrigem"]:
            item["ProdutosOrigem"].append(product)

    return sorted(
        grouped.values(),
        key=lambda item: (
            item["Categoria"],
            item.get("Modelo") or item["Nome do Produto"],
            int(item["Tamanho"]) if str(item.get("Tamanho", "")).isdigit() else 999,
        ),
    )



def make_xlsx_b64(data: List[Dict[str, Any]]) -> str:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Retiradas"

    headers = [
        "Item",
        "Nome do Produto",
        "Qtde",
        "Unidade Medida",
        "Pacotes",
        "Sacolas por pacote",
        "Requisitante",
        "Data_fmt",
        "Status",
        "Observação",
        "Nº Retirada",
        "Responsável pelo Registro",
        "Categoria",
        "Modelo",
        "Tamanho",
    ]
    worksheet.append(headers)

    for row in data:
        worksheet.append([row.get(header, "") for header in headers])

    for column in worksheet.columns:
        letter = column[0].column_letter
        max_length = max(len(str(cell.value or "")) for cell in column)
        worksheet.column_dimensions[letter].width = min(
            max(12, max_length + 2),
            50,
        )

    buffer = io.BytesIO()
    workbook.save(buffer)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def find_js_const_bounds(html: str, name: str) -> Tuple[int, int, int]:
    match = re.search(
        rf"\bconst\s+{re.escape(name)}\s*=",
        html,
    )
    if not match:
        raise RuntimeError(
            f"Não encontrei const {name} no index.html"
        )

    value_start = match.end()
    quote: Optional[str] = None
    escaped = False
    depth = 0

    for index in range(value_start, len(html)):
        char = html[index]

        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue

        if char in {'"', "'", "`"}:
            quote = char
        elif char in "[{(":
            depth += 1
        elif char in "]})":
            depth = max(0, depth - 1)
        elif char == ";" and depth == 0:
            return match.start(), value_start, index + 1

    raise RuntimeError(
        f"A declaração const {name} não possui fechamento válido."
    )


def extract_js_const_raw(html: str, name: str) -> str:
    _, value_start, end = find_js_const_bounds(html, name)
    return html[value_start : end - 1].strip()


def replace_js_const(
    html: str,
    name: str,
    value: Any,
    quote: bool = False,
) -> str:
    start, _, end = find_js_const_bounds(html, name)
    encoded = (
        json.dumps(str(value), ensure_ascii=False)
        if quote
        else str(value)
    )
    replacement = f"const {name}={encoded};"
    return html[:start] + replacement + html[end:]


def payload_hash(
    data: List[Dict[str, Any]],
    stock: List[Dict[str, Any]],
    open_tools: List[Dict[str, Any]],
) -> str:
    serialized = json.dumps(
        {
            "data": data,
            "estoque": stock,
            "ferramentas_abertas": open_tools,
            "senha_whatsapp": WHATSAPP_PASSWORD,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def current_html_payload_hash(html: str) -> Optional[str]:
    try:
        current_data = json.loads(extract_js_const_raw(html, "DATA"))
        current_stock = json.loads(extract_js_const_raw(html, "ESTOQUE"))
        current_tools = json.loads(
            extract_js_const_raw(html, "FERRAMENTAS_ABERTAS")
        )
        return payload_hash(current_data, current_stock, current_tools)
    except Exception as exc:
        log(
            "AVISO: não foi possível calcular o hash dos dados atuais do "
            f"HTML: {exc}"
        )
        return None


def current_html_reference_date(html: str) -> str:
    try:
        return str(
            json.loads(
                extract_js_const_raw(html, "DATA_REFERENCIA")
            )
        )
    except Exception:
        return ""


def atomic_write_text(path: Path, content: str) -> None:
    temp_path = path.with_name(path.name + ".tmp")
    try:
        temp_path.write_text(content, encoding="utf-8")
        # Validação mínima antes de substituir o arquivo verdadeiro.
        validation = temp_path.read_text(encoding="utf-8")
        for name in [
            "DATA",
            "ESTOQUE",
            "FERRAMENTAS_ABERTAS",
            "SENHA_WHATSAPP",
            "XLSX_B64",
            "GERADO_EM",
            "DATA_REFERENCIA",
        ]:
            find_js_const_bounds(validation, name)
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def replace_required(
    html: str,
    pattern: str,
    replacement: str,
    description: str,
    *,
    flags: int = 0,
) -> str:
    updated, count = re.subn(
        pattern,
        lambda _match: replacement,
        html,
        count=1,
        flags=flags,
    )
    if count != 1:
        raise RuntimeError(
            "Não foi possível aplicar a regra de 2026 em "
            f"{description}. O index.html pode ter mudado de estrutura."
        )
    return updated


def ensure_operational_frontend(html: str) -> str:
    """
    Separa os dois usos dos dados no navegador:

    - Indicadores, médias, rankings, cobertura e compra: somente 2026.
    - Calendário e comparação sazonal: 2025 e 2026.

    A função é idempotente: pode ser executada em todas as atualizações.
    """
    if re.search(r"\bconst\s+ANO_OPERACIONAL\s*=", html):
        html = replace_js_const(
            html,
            "ANO_OPERACIONAL",
            OPERATING_YEAR,
        )
    else:
        match = re.search(
            r"\bconst\s+DATA_REFERENCIA\s*=\s*[^;]+;",
            html,
        )
        if not match:
            raise RuntimeError(
                "Não encontrei DATA_REFERENCIA para inserir "
                "ANO_OPERACIONAL no index.html."
            )
        html = (
            html[: match.end()]
            + f"\nconst ANO_OPERACIONAL={OPERATING_YEAR};"
            + f"\nconst ANO_HISTORICO_SAZONAL={SEASONAL_HISTORY_YEAR};"
            + html[match.end() :]
        )

    if re.search(r"\bconst\s+ANO_HISTORICO_SAZONAL\s*=", html):
        html = replace_js_const(
            html,
            "ANO_HISTORICO_SAZONAL",
            SEASONAL_HISTORY_YEAR,
        )

    if "function dadosOperacionais()" not in html:
        html = replace_required(
            html,
            (
                r"function byCat\(cat\)\{return DATA\.filter"
                r"\(r=>r\.Categoria===cat\)\}\s*"
                r"function sum\(arr\)"
            ),
            (
                "function anoRegistro(r){return Number("
                "r.Ano||String(r.Data_iso||'').slice(0,4)||0)} "
                "function dadosOperacionais(){return DATA.filter("
                "r=>anoRegistro(r)===ANO_OPERACIONAL)} "
                "function dadosSazonais(){return DATA.filter("
                "r=>anoRegistro(r)===ANO_HISTORICO_SAZONAL||"
                "anoRegistro(r)===ANO_OPERACIONAL)} "
                "function byCat(cat){return dadosOperacionais().filter("
                "r=>r.Categoria===cat)} "
                "function byCatSazonal(cat){return dadosSazonais().filter("
                "r=>r.Categoria===cat)} "
                "function sum(arr)"
            ),
            "separação dos dados operacionais e sazonais",
        )

    old_sacola_arr = (
        "function sacolaArr(){let arr=byCat('Sacolas'); "
        "if(sacolaFiltro==='todos')return arr; "
        "return arr.filter(r=>String(r.Ano)===String(sacolaFiltro))}"
    )
    new_sacola_arr = (
        "function sacolaArr(){return byCat('Sacolas')}"
    )
    if old_sacola_arr in html:
        html = html.replace(
            old_sacola_arr,
            new_sacola_arr,
            1,
        )
    elif new_sacola_arr not in html:
        raise RuntimeError(
            "Não foi possível ajustar sacolaArr para o ano operacional."
        )

    old_event_rows = (
        "function eventRows(ev,year){let d=eventDates(ev,year);"
        "return byCat('Sacolas').filter(r=>r.Data_iso>=d.weekStart"
        "&&r.Data_iso<=d.weekEnd)}"
    )
    new_event_rows = (
        "function eventRows(ev,year){let d=eventDates(ev,year);"
        "return byCatSazonal('Sacolas').filter(r=>anoRegistro(r)===year"
        "&&r.Data_iso>=d.weekStart&&r.Data_iso<=d.weekEnd)}"
    )
    if old_event_rows in html:
        html = html.replace(
            old_event_rows,
            new_event_rows,
            1,
        )
    elif new_event_rows not in html:
        raise RuntimeError(
            "Não foi possível ajustar eventRows para a sazonalidade."
        )

    html = re.sub(
        r"let sacolaFiltro=(?:'todos'|String\(ANO_OPERACIONAL\));",
        "let sacolaFiltro=String(ANO_OPERACIONAL);",
        html,
        count=1,
    )

    old_pills = (
        '<div class="pillbar"><button class="pill '
        "${sacolaFiltro==='todos'?'active':''}\" "
        'onclick="sacolaFiltro=\'todos\';renderSacolas()">'
        'Todo período</button>${getYearsSacolas().map(y=>'
        '`<button class="pill '
        "${String(sacolaFiltro)===String(y)?'active':''}\" "
        "onclick=\"sacolaFiltro='${y}';renderSacolas()\">"
        "${y}</button>`).join('')}</div>"
    )
    new_pills = (
        '<div class="pillbar">'
        '<span class="pill active">Indicadores operacionais: '
        '${ANO_OPERACIONAL}</span>'
        '<span class="pill">Histórico de '
        '${ANO_HISTORICO_SAZONAL} usado somente na sazonalidade</span>'
        '</div>'
    )
    if old_pills in html:
        html = html.replace(old_pills, new_pills, 1)
    elif "Indicadores operacionais: ${ANO_OPERACIONAL}" not in html:
        raise RuntimeError(
            "Não foi possível substituir os filtros de ano das sacolas."
        )

    html = html.replace(
        "O cálculo usa a média mensal do período selecionado.",
        "O cálculo usa exclusivamente as retiradas de "
        "${ANO_OPERACIONAL}.",
        1,
    )
    html = html.replace(
        "No recorte selecionado, foram retiradas",
        "Em ${ANO_OPERACIONAL}, foram retiradas",
        1,
    )

    new_event_cards = r"""function renderEventCards(){let y=ANO_OPERACIONAL;return EVENTOS.map(ev=>{let future=eventoFuturo(ev,y);let cls=ev.forca==='alta'?'high':'medium';let d=eventDates(ev,y);return `<div class="season-card ${cls}" onclick="openEvento('${ev.id}')"><span>${brDate(d.start)}${d.start!==d.end?' a '+brDate(d.end):''}</span><b>${ev.nome}</b><small>${ev.desc}</small><em class="tag ${future?'future':'done'}">${future?'Previsto':'Realizado'}</em></div>`}).join('')+`<div class="season-card leaves"><span>mar.–jun.</span><b>Outono / folhas</b><small>Período de atenção para limpeza urbana e folhas.</small><em class="tag">Alerta complementar</em></div>`}"""
    html = replace_required(
        html,
        (
            r"function renderEventCards\(\)\{.*?\}"
            r"\nfunction openPessoaSacolas"
        ),
        new_event_cards + "\nfunction openPessoaSacolas",
        "cartões do calendário sazonal",
        flags=re.S,
    )

    new_open_event = r"""function openEvento(id){let ev=EVENTOS.find(e=>e.id===id),years=[ANO_HISTORICO_SAZONAL,ANO_OPERACIONAL];let html=years.map(y=>{let d=eventDates(ev,y),rows=eventRows(ev,y),future=eventoFuturo(ev,y),anoRows=byCatSazonal('Sacolas').filter(r=>anoRegistro(r)===y),avg=mediaSemanal(anoRows),total=sum(rows),ratio=avg?total/avg:0;if(future){let hist=eventRows(ev,ANO_HISTORICO_SAZONAL),histTotal=sum(hist);return `<div class="panel"><h3>${ev.nome} · ${y} · previsto</h3><p class="muted">Evento ainda não realizado. Semana que será analisada: <b>${brDate(d.weekStart)} a ${brDate(d.weekEnd)}</b>.</p><div class="note">Referência sazonal de ${ANO_HISTORICO_SAZONAL}: <b>${fmt(histTotal)}</b> unidades na semana seguinte ao evento. Margem sugerida: <b>+${Math.round(ev.margem*100)}%</b>.</div></div>`}return `<div class="panel"><h3>${ev.nome} · ${y} · realizado</h3><p class="muted">Semana seguinte analisada: <b>${brDate(d.weekStart)} a ${brDate(d.weekEnd)}</b>. Este resultado é usado somente para sazonalidade.</p><div class="kpis"><div class="kpi"><span>Total da semana</span><br><b>${fmt(total)}</b></div><div class="kpi"><span>Registros</span><br><b>${rows.length}</b></div><div class="kpi"><span>Média semanal de ${y}</span><br><b>${fmt(avg)}</b></div><div class="kpi"><span>Vezes acima da média</span><br><b>${fmt(ratio)}×</b></div></div>${table(rows)}</div>`}).join('');openModal(ev.nome,`Comparação sazonal: ${ANO_HISTORICO_SAZONAL} e ${ANO_OPERACIONAL}`,html)}"""
    html = replace_required(
        html,
        r"function openEvento\(id\)\{.*?\}\nfunction openModal",
        new_open_event + "\nfunction openModal",
        "comparação dos eventos sazonais",
        flags=re.S,
    )

    html = re.sub(
        (
            r"function getYearsSacolas\(\)\{.*?\}"
            r"\nlet sacolaFiltro="
        ),
        (
            "function getYearsSacolas(){return "
            "[ANO_HISTORICO_SAZONAL,ANO_OPERACIONAL]}\n"
            "let sacolaFiltro="
        ),
        html,
        count=1,
        flags=re.S,
    )

    html = html.replace(
        "Escolha uma categoria para consultar retiradas, consumo, "
        "estoque e alertas.",
        f"Indicadores operacionais de {OPERATING_YEAR}. "
        f"O histórico de {SEASONAL_HISTORY_YEAR} é usado somente "
        "na análise sazonal.",
        1,
    )
    html = html.replace(
        "relatorio_almoxarifado_retiradas.xlsx",
        f"relatorio_almoxarifado_{OPERATING_YEAR}.xlsx",
        1,
    )
    return html


def ensure_sacola_package_frontend(html: str) -> str:
    """Aplica a leitura de sacolas em unidades individuais, com pacotes
    apenas como apoio, e acrescenta interpretação simples da projeção.

    A função substitui blocos completos e é idempotente.
    """
    if re.search(r"\bconst\s+SACOLAS_POR_PACOTE\s*=", html):
        html = replace_js_const(
            html,
            "SACOLAS_POR_PACOTE",
            SACOLAS_POR_PACOTE,
        )
    else:
        match = re.search(
            r"\bconst\s+ANO_HISTORICO_SAZONAL\s*=\s*[^;]+;",
            html,
        )
        if not match:
            raise RuntimeError(
                "Não encontrei ANO_HISTORICO_SAZONAL para inserir "
                "SACOLAS_POR_PACOTE."
            )
        html = (
            html[: match.end()]
            + f"\nconst SACOLAS_POR_PACOTE={SACOLAS_POR_PACOTE};"
            + html[match.end() :]
        )

    helpers = r'''function pacotesDeSacolas(v){return n(v)/SACOLAS_POR_PACOTE}
function dataEsgotamento(estoque,media){if(!media||estoque<=0)return null;let dias=Math.max(0,Math.round((estoque/media)*30.4375));let d=parseISO(DATA_REFERENCIA);d.setDate(d.getDate()+dias);return d.toLocaleDateString('pt-BR',{day:'2-digit',month:'long',year:'numeric'})}
function leituraSituacaoSacolas(estoque,media,min3,minSaz){if(estoque<=media)return {cor:'vermelho',titulo:'Situação crítica',texto:'O estoque cobre aproximadamente um mês ou menos. A reposição precisa ser tratada como prioridade.'};if(estoque<min3)return {cor:'amarelo',titulo:'Abaixo do mínimo operacional',texto:'O estoque ainda existe, mas não alcança a meta de três meses de cobertura. É necessário planejar a reposição.'};if(estoque<minSaz)return {cor:'amarelo',titulo:'Estoque operacional, com pouca folga sazonal',texto:'A meta normal de três meses está atendida, porém o estoque está abaixo da margem prevista para períodos de maior consumo.'};return {cor:'verde',titulo:'Estoque confortável',texto:'O estoque está acima da meta operacional e da margem sazonal calculada para o período.'}}
'''
    if "function pacotesDeSacolas(v)" not in html:
        html = replace_required(
            html,
            r"function monthLabel\(key\)",
            helpers + "function monthLabel(key)",
            "funções de apoio das sacolas",
        )
    else:
        html = replace_required(
            html,
            r"function pacotesDeSacolas\(v\)\{.*?\}\nfunction monthLabel\(key\)",
            helpers + "function monthLabel(key)",
            "funções de apoio das sacolas",
            flags=re.S,
        )

    new_table = r'''function table(arr,limit=9999){let rows=arr.slice(0,limit).map(r=>{let qtd=r.Categoria==='Sacolas'?`${fmt(r.Qtde_num)} sacolas<br><small>${fmt(n(r.Pacotes_num)||pacotesDeSacolas(r.Qtde_num))} pacote(s)</small>`:`<b>${fmt(r.Qtde_num)}</b>`;return `<tr><td>${esc(r.Data_fmt)}</td><td>${esc(r['Nº Retirada'])}</td><td>${esc(r.Requisitante)}</td><td>${esc(r['Nome do Produto'])}</td><td>${qtd}</td><td>${esc(r.Status)}</td></tr>`}).join('');return `<div class="tablewrap"><table><thead><tr><th>Data</th><th>Nº</th><th>Requisitante</th><th>Produto</th><th>Qtd</th><th>Status</th></tr></thead><tbody>${rows||'<tr><td colspan="6">Sem registros no recorte.</td></tr>'}</tbody></table></div>`}'''
    html = replace_required(
        html,
        r"function table\(arr,limit=9999\)\{.*?\}\nfunction bars",
        new_table + "\nfunction bars",
        "tabela com sacolas e pacotes",
        flags=re.S,
    )

    new_home = r'''function homeCards(){let el=document.getElementById('homeCards');el.innerHTML=CATS.map(c=>{let arr=byCat(c[0]);let qtd=sum(arr),req=unique(arr,'Requisitante'),prod=unique(arr,'Nome do Produto');let quantidade=c[0]==='Sacolas'?`<span class="chip">${fmt(qtd)} sacolas</span><span class="chip">${fmt(pacotesDeSacolas(qtd))} pacotes</span>`:`<span class="chip">${fmt(qtd)} unidades</span>`;return `<div class="card" onclick="openCat('${c[0]}')"><span class="icon">${c[1]}</span><h2>${c[0]}</h2><p class="muted">${c[2]}</p><div class="chips">${quantidade}<span class="chip">${arr.length} retiradas</span><span class="chip">${req} requisitantes</span><span class="chip">${prod} produtos</span></div></div>`}).join('')}'''
    html = replace_required(
        html,
        r"function homeCards\(\)\{.*?\}\nfunction show",
        new_home + "\nfunction show",
        "cartões da página inicial",
        flags=re.S,
    )

    new_stock_rows = r'''function stockRows(cat){let rows=stockByCat(cat).map(e=>{let atual=cat==='Sacolas'?`${fmt(e.QtdeEstoque)} sacolas<br><small>${fmt(n(e.PacotesEstoque)||pacotesDeSacolas(e.QtdeEstoque))} pacotes</small>`:`<b>${fmt(e.QtdeEstoque)}</b>`;let minimo=cat==='Sacolas'?`${fmt(e.EstoqueMin)} sacolas<br><small>${fmt(n(e.PacotesMin)||pacotesDeSacolas(e.EstoqueMin))} pacotes</small>`:fmt(e.EstoqueMin);return `<tr><td>${esc(e.Tamanho?('Tam. '+e.Tamanho):e['Nome do Produto'])}</td><td>${atual}</td><td>${minimo}</td><td>${n(e.QtdeEstoque)<=n(e.EstoqueMin)?'Atenção':'Normal'}</td></tr>`}).join('');return `<div class="tablewrap"><table><thead><tr><th>Item</th><th>Estoque atual</th><th>Mínimo Access</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table></div>`}'''
    html = replace_required(
        html,
        (
            r"function stockRows\(cat\)\{.*?\}"
            r"(?=\n(?:\n)?function (?:extrairTamanho|renderBotinas))"
        ),
        new_stock_rows,
        "estoque de sacolas",
        flags=re.S,
    )

    new_projection_and_sacolas = r'''function renderProjection(estoque,media,min3,minSaz){let after30=Math.max(0,estoque-media),after60=Math.max(0,estoque-media*2),after90=Math.max(0,estoque-media*3),scale=Math.max(estoque,minSaz,min3,media,1);function y(v){return 285-(v/scale)*220}let pts=`100,${y(estoque)} 360,${y(after30)} 620,${y(after60)} 890,${y(after90)}`,yMin3=y(min3),ySaz=y(minSaz),yCrit=y(media);return `<div class="projection"><div class="topbar"><div><h3>Projeção do estoque de sacolas</h3><p class="muted">A linha azul mostra a redução estimada do estoque se o ritmo médio de consumo de ${ANO_OPERACIONAL} continuar.</p></div></div><svg viewBox="0 0 1000 360"><rect x="70" y="35" width="860" height="260" rx="18" fill="#fff" stroke="#d8e6f3"/><rect x="70" y="${yMin3}" width="860" height="${Math.max(0,295-yMin3)}" fill="#fff8df" opacity=".6"/><rect x="70" y="${yCrit}" width="860" height="${Math.max(0,295-yCrit)}" fill="#fff0ed" opacity=".65"/><g stroke="#e2edf7"><line x1="70" y1="85" x2="930" y2="85"/><line x1="70" y1="145" x2="930" y2="145"/><line x1="70" y1="205" x2="930" y2="205"/><line x1="70" y1="265" x2="930" y2="265"/></g><line x1="70" y1="${ySaz}" x2="930" y2="${ySaz}" stroke="#6aa9e8" stroke-width="4" stroke-dasharray="10 8"/><line x1="70" y1="${yMin3}" x2="930" y2="${yMin3}" stroke="#b77900" stroke-width="4" stroke-dasharray="10 8"/><line x1="70" y1="${yCrit}" x2="930" y2="${yCrit}" stroke="#b42318" stroke-width="3" stroke-dasharray="8 8"/><polyline points="${pts}" fill="none" stroke="#076eb0" stroke-width="7" stroke-linecap="round"/><circle cx="100" cy="${y(estoque)}" r="9" fill="#16813a"/><circle cx="360" cy="${y(after30)}" r="7" fill="#076eb0"/><circle cx="620" cy="${y(after60)}" r="7" fill="#076eb0"/><circle cx="890" cy="${y(after90)}" r="7" fill="#076eb0"/><text x="85" y="${Math.max(20,y(estoque)-15)}" font-size="15" font-weight="900" fill="#003b71">Atual: ${fmt(estoque)}</text><text x="755" y="${Math.max(20,y(after90)-15)}" font-size="15" font-weight="900" fill="#003b71">90 dias: ${fmt(after90)}</text><text x="690" y="${yMin3-8}" font-size="13" font-weight="900" fill="#7a5a00">Mínimo de 3 meses: ${fmt(min3)}</text><text x="690" y="${ySaz-8}" font-size="13" font-weight="900" fill="#0f5f99">Margem sazonal: ${fmt(minSaz)}</text><text x="690" y="${yCrit-8}" font-size="13" font-weight="900" fill="#8a1f17">Ponto crítico: ${fmt(media)}</text><g fill="#63738a" font-size="13" font-weight="800"><text x="75" y="330">Estoque atual</text><text x="325" y="330">Após 30 dias</text><text x="585" y="330">Após 60 dias</text><text x="845" y="330">Após 90 dias</text></g></svg><div class="legend"><span><i class="dot"></i> saldo projetado</span><span><i class="dot warn"></i> mínimo de 3 meses</span><span><i class="dot info"></i> margem sazonal</span><span><i class="dot danger"></i> ponto crítico de 1 mês</span></div></div>`}
function renderProjectionExplanation(estoque,media,min3,minSaz){let after30=Math.max(0,estoque-media),after60=Math.max(0,estoque-media*2),after90=Math.max(0,estoque-media*3),cobertura=media?estoque/media:0,fim=dataEsgotamento(estoque,media),sit=leituraSituacaoSacolas(estoque,media,min3,minSaz);return `<div class="panel"><h2>Como interpretar este gráfico</h2><div class="note"><b>${sit.titulo}</b><br>${sit.texto}</div><p class="leitura">O estoque atual possui <b>${fmt(estoque)} sacolas</b>, equivalentes a <b>${fmt(pacotesDeSacolas(estoque))} pacotes</b> de ${SACOLAS_POR_PACOTE}. Com a média atual de <b>${fmt(media)} sacolas por mês</b> (${fmt(pacotesDeSacolas(media))} pacotes), a cobertura estimada é de <b>${fmt(cobertura)} meses</b>${fim?` e a previsão aproximada de término é <b>${fim}</b>`:''}.</p><div class="kpis"><div class="kpi"><span>Após 30 dias</span><br><b>${fmt(after30)}</b><small> sacolas</small></div><div class="kpi"><span>Após 60 dias</span><br><b>${fmt(after60)}</b><small> sacolas</small></div><div class="kpi"><span>Após 90 dias</span><br><b>${fmt(after90)}</b><small> sacolas</small></div><div class="kpi"><span>Situação</span><br><b>${sit.cor}</b><small> decisão visual</small></div></div><div class="rule-matrix" style="margin-top:14px"><div class="matrix-card danger"><b>Vermelho</b><span>Até 1 mês de cobertura. Prioridade imediata.</span></div><div class="matrix-card warn"><b>Amarelo</b><span>Abaixo de 3 meses ou da margem sazonal. Planejar reposição.</span></div><div class="matrix-card ok"><b>Verde</b><span>Acima da meta de 3 meses e da margem sazonal.</span></div><div class="matrix-card info"><b>Regra do sistema</b><span>1 pacote representa ${SACOLAS_POR_PACOTE} sacolas.</span></div></div><p class="leitura"><b>Linhas do gráfico:</b> o ponto crítico representa um mês de consumo; o mínimo operacional representa três meses; e a margem sazonal acrescenta proteção para festas, feriados e épocas de maior utilização.</p></div>`}
function renderSacolas(){let arr=sacolaArr(),estoque=stockTotal('Sacolas'),media=mediaMensal(arr),min3=media*3,margem=bestSeasonMargin(),minSaz=min3*(1+margem),cobertura=media?estoque/media:0,st=statusEstoque(estoque,min3,minSaz,media),total=sum(arr),docs=unique(arr,'Nº Retirada'),reqs=group(arr,'Requisitante'),meses=groupMonth(arr),dias=groupWeekday(arr),prods=group(arr,'Nome do Produto'),avgWeek=mediaSemanal(arr),fim=dataEsgotamento(estoque,media);document.getElementById('sacolasContent').innerHTML=`<div class="pillbar"><span class="pill active">Indicadores operacionais: ${ANO_OPERACIONAL}</span><span class="pill">${SACOLAS_POR_PACOTE} sacolas por pacote</span><span class="pill">Histórico de ${ANO_HISTORICO_SAZONAL} usado somente na sazonalidade</span></div><div class="decision"><div class="decision-main status-${st.cls}"><div class="eyebrow">Decisão automática · Sacolas</div><div class="decision-title">${st.txt}</div><p class="decision-text">A regra operacional usa somente as retiradas de ${ANO_OPERACIONAL}. Cada unidade cadastrada no Access representa um pacote fechado com <b>${SACOLAS_POR_PACOTE} sacolas</b>. O objetivo é manter pelo menos três meses de cobertura, considerando também os períodos sazonais.</p><div class="mini-grid"><div class="mini"><span>Estoque atual</span><b>${fmt(estoque)}</b><small>sacolas · ${fmt(pacotesDeSacolas(estoque))} pacotes</small></div><div class="mini"><span>Consumo médio mensal</span><b>${fmt(media)}</b><small>sacolas · ${fmt(pacotesDeSacolas(media))} pacotes/mês</small></div><div class="mini"><span>Mínimo de 3 meses</span><b>${fmt(min3)}</b><small>sacolas · ${fmt(pacotesDeSacolas(min3))} pacotes</small></div><div class="mini"><span>Margem sazonal</span><b>${fmt(minSaz)}</b><small>sacolas · ${fmt(pacotesDeSacolas(minSaz))} pacotes</small></div></div></div><aside class="decision-side status-${st.cls}"><span class="recommend-badge ${st.cls==='danger'?'danger':st.cls==='warn'?'warn':''}">${st.badge}</span><h3>Leitura rápida</h3><p class="muted">Cobertura estimada: <b>${fmt(cobertura)} meses</b>.</p>${fim?`<p class="muted">Previsão aproximada de término, mantendo o ritmo atual: <b>${fim}</b>.</p>`:''}<div class="risk-box ${st.cls==='danger'?'danger':''}"><b>Como decidir:</b> verde significa estoque confortável; amarelo indica necessidade de planejamento; vermelho indica prioridade imediata.</div></aside></div><div class="panel"><h2>Resumo executivo de ${ANO_OPERACIONAL}</h2><div class="kpis"><div class="kpi"><span>Total retirado</span><br><b>${fmt(total)}</b><small> sacolas</small></div><div class="kpi"><span>Pacotes utilizados</span><br><b>${fmt(pacotesDeSacolas(total))}</b></div><div class="kpi"><span>Média semanal</span><br><b>${fmt(avgWeek)}</b><small> sacolas</small></div><div class="kpi"><span>Cobertura atual</span><br><b>${fmt(cobertura)}</b><small> meses</small></div></div><p class="leitura">Em ${ANO_OPERACIONAL}, foram utilizadas <b>${fmt(total)} sacolas</b>, equivalentes a <b>${fmt(pacotesDeSacolas(total))} pacotes</b>, em <b>${fmt(docs)} retiradas</b>. Todos os cálculos operacionais estão apresentados em sacolas; a quantidade de pacotes aparece somente como apoio para facilitar a conferência com o Access.</p></div><div class="panel"><h2>Régua simples de decisão</h2><div class="rule-matrix"><div class="matrix-card danger"><b>Vermelho</b><span>Estoque igual ou abaixo de um mês de consumo.</span></div><div class="matrix-card warn"><b>Amarelo</b><span>Estoque abaixo de três meses ou da margem sazonal.</span></div><div class="matrix-card ok"><b>Verde</b><span>Estoque acima da meta operacional e sazonal.</span></div><div class="matrix-card info"><b>Conversão</b><span>1 pacote = ${SACOLAS_POR_PACOTE} sacolas.</span></div></div><div class="ruler"><div class="ruler-track"><span class="ruler-pin" style="left:${Math.min(96,Math.max(4,estoque/Math.max(minSaz,1)*80))}%">Atual: ${fmt(estoque)} sacolas</span></div><div class="ruler-labels"><span>Crítico: ${fmt(media)}</span><span>3 meses: ${fmt(min3)}</span><span>Sazonal: ${fmt(minSaz)}</span><span>Confortável</span></div></div></div>${renderProjection(estoque,media,min3,minSaz)}${renderProjectionExplanation(estoque,media,min3,minSaz)}<div class="panel"><h2>Calendário sazonal municipal</h2><p class="muted">Clique em um evento para comparar a semana seguinte em ${ANO_HISTORICO_SAZONAL} e ${ANO_OPERACIONAL}. O histórico antigo não entra na média operacional.</p><div class="season-grid">${renderEventCards()}</div></div><div class="two"><div class="panel"><h2>Consumo mensal em sacolas</h2>${bars(meses.map(x=>({...x,k:monthLabel(x.k)})),24)}</div><div class="panel"><h2>Consumo por dia da semana</h2>${bars(dias,7)}</div></div><div class="two"><div class="panel"><h2>Retiradas por colaborador</h2><p class="muted">Clique no nome para ver datas e retiradas.</p>${bars(reqs,15,'openPessoaSacolas')}</div><div class="panel"><h2>Tipos de sacola</h2>${bars(prods,12)}</div></div><div class="panel"><h2>Histórico de sacolas de ${ANO_OPERACIONAL}</h2>${table(arr)}</div>`}'''
    html = replace_required(
        html,
        r"function renderProjection\(estoque,media,min3,minSaz\)\{.*?\}\nfunction renderEventCards",
        new_projection_and_sacolas + "\nfunction renderEventCards",
        "gráfico e painel de sacolas",
        flags=re.S,
    )

    html = html.replace(
        "Retiradas da semana seguinte ao evento",
        "Sacolas utilizadas na semana seguinte ao evento",
    )
    return html


def ensure_botina_model_frontend(html: str) -> str:
    """Separa o painel de botinas por modelo e tamanho.

    O painel operacional continua usando somente OPERATING_YEAR. A função
    substitui o bloco completo das botinas e pode ser executada novamente
    sem duplicar funções.
    """
    new_botina_block = r'''function extrairTamanho(txt){let m=String(txt||'').match(/(?:^|[^0-9])([3-5][0-9])(?:[^0-9]|$)/);return m?m[1]:''}
function normalizarModeloBotinaTexto(txt){let t=String(txt||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toUpperCase();if(t.includes('MOTORISTA'))return 'Botina motorista';if(t.includes('PVC')||t.includes('BORRACHA')){if(t.includes('BRANCA')||t.includes('BRANCO'))return 'Bota PVC branca';if(t.includes('PRETA')||t.includes('PRETO'))return 'Bota PVC preta';return 'Bota PVC'}if(t.includes('BOTINA')||t.includes('SEGURANCA'))return 'Botina de segurança';return 'Modelo não identificado'}
function modeloBotina(r){return r.Modelo||normalizarModeloBotinaTexto(r['Nome do Produto'])}
function chaveBotina(modelo,tam){return `${modelo}|||${tam}`}
function rotuloBotina(modelo,tam){return `${modelo} · ${tam==='Sem tamanho'?'sem tamanho':'tam. '+tam}`}
let botinaModeloFiltro='todos';
function botinaStockByKey(){let m={};stockByCat('Botinas').forEach(e=>{let modelo=modeloBotina(e),tam=String(e.Tamanho||extrairTamanho(e['Nome do Produto'])||'Sem tamanho'),k=chaveBotina(modelo,tam);if(!m[k])m[k]={estoque:0,minimo:0,modelo,tam,origens:[]};m[k].estoque+=n(e.QtdeEstoque);m[k].minimo+=n(e.EstoqueMin);m[k].origens.push(...(e.ProdutosOrigem||[]))});return m}
function mesesCompletosBotina(arr){let atual=DATA_REFERENCIA.slice(0,7),keys=[...new Set(arr.map(r=>(r.Data_iso||'').slice(0,7)).filter(Boolean).filter(k=>k!==atual))];if(!keys.length)keys=[...new Set(arr.map(r=>(r.Data_iso||'').slice(0,7)).filter(Boolean))];return Math.max(1,keys.length)}
function botinaStats(){let arr=byCat('Botinas'),st=botinaStockByKey(),meses=mesesCompletosBotina(arr),m={};arr.forEach(r=>{let modelo=modeloBotina(r),tam=String(r.Tamanho||extrairTamanho(r['Nome do Produto'])||'Sem tamanho'),k=chaveBotina(modelo,tam);if(!m[k])m[k]={k,modelo,tam,q:0,n:0,rows:[],estoque:0,minimo:0,media:0,cobertura:999,status:'Normal',cls:'ok'};m[k].q+=n(r.Qtde_num);m[k].n++;m[k].rows.push(r)});Object.entries(st).forEach(([k,s])=>{if(!m[k])m[k]={k,modelo:s.modelo,tam:s.tam,q:0,n:0,rows:[],estoque:0,minimo:0,media:0,cobertura:999,status:'Normal',cls:'ok'};m[k].estoque=s.estoque;m[k].minimo=s.minimo;m[k].origens=s.origens});let rank={danger:0,warn:1,ok:2};return Object.values(m).map(x=>{x.media=x.q/meses;x.cobertura=x.media?x.estoque/x.media:999;let cadastroRuim=x.tam==='Sem tamanho'||x.modelo==='Modelo não identificado';if(cadastroRuim){x.status='Revisar cadastro';x.cls='warn'}else if(x.estoque<=0&&x.q>0){x.status='Sem estoque';x.cls='danger'}else if(x.media>0&&x.cobertura<=1){x.status='Crítico';x.cls='danger'}else if(x.media>0&&x.cobertura<4){x.status='Abaixo da meta';x.cls='warn'}else{x.status='Normal';x.cls='ok'}return x}).sort((a,b)=>(rank[a.cls]-rank[b.cls])||(b.q-a.q)||a.modelo.localeCompare(b.modelo)||Number(a.tam)-Number(b.tam))}
function botinaStatsFiltrados(stats){return botinaModeloFiltro==='todos'?stats:stats.filter(s=>s.modelo===botinaModeloFiltro)}
function botinaRowsFiltradas(arr){return botinaModeloFiltro==='todos'?arr:arr.filter(r=>modeloBotina(r)===botinaModeloFiltro)}
function renderBotinaPills(stats){let modelos=[...new Set(stats.map(s=>s.modelo))].sort();return `<div class="pillbar"><button class="pill ${botinaModeloFiltro==='todos'?'active':''}" onclick="botinaModeloFiltro='todos';renderBotinas()">Todos os modelos</button>${modelos.map(m=>`<button class="pill ${botinaModeloFiltro===m?'active':''}" onclick="botinaModeloFiltro=decodeURIComponent('${encodeURIComponent(m)}');renderBotinas()">${esc(m)}</button>`).join('')}</div>`}
function botinaColaboradores(arr){let g=group(arr,'Requisitante');return g.map(x=>{let itens=group(x.rows.map(r=>({...r,ItemBotina:rotuloBotina(modeloBotina(r),String(r.Tamanho||extrairTamanho(r['Nome do Produto'])||'Sem tamanho'))})),'ItemBotina');let dates=x.rows.map(r=>r.Data_iso).filter(Boolean).sort();let gaps=[];for(let i=1;i<dates.length;i++)gaps.push(Math.round((parseISO(dates[i])-parseISO(dates[i-1]))/86400000));let mediaTroca=gaps.length?Math.round(gaps.reduce((a,b)=>a+b,0)/gaps.length):null;return {...x,principal:itens[0]?.k||'-',mediaTroca}})}
function openItemBotina(keyEnc){let key=decodeURIComponent(keyEnc),[modelo,tam]=key.split('|||'),arr=byCat('Botinas').filter(r=>modeloBotina(r)===modelo&&String(r.Tamanho||extrairTamanho(r['Nome do Produto'])||'Sem tamanho')===tam),pessoas=group(arr,'Requisitante'),st=botinaStats().find(s=>s.k===key);openModal(rotuloBotina(modelo,tam),`${fmt(sum(arr))} par(es) retirado(s) em ${ANO_OPERACIONAL} · estoque ${fmt(st?.estoque||0)}`,`<div class="two"><div class="panel"><h3>Quem retirou</h3>${bars(pessoas,30,'openPessoaBotina')}</div><div class="panel"><h3>Histórico do item</h3>${table(arr)}</div></div>`)}
function openPessoaBotina(nomeEnc){let nome=decodeURIComponent(nomeEnc),arr=byCat('Botinas').filter(r=>(r.Requisitante||'Não informado')===nome),porItem=group(arr.map(r=>({...r,ItemBotina:rotuloBotina(modeloBotina(r),String(r.Tamanho||extrairTamanho(r['Nome do Produto'])||'Sem tamanho'))})),'ItemBotina');openModal('Retiradas de botinas · '+nome,`${fmt(sum(arr))} par(es) em ${fmt(arr.length)} registro(s) de ${ANO_OPERACIONAL}`,`<div class="two"><div class="panel"><h3>Modelos e tamanhos</h3>${bars(porItem,20)}</div><div class="panel"><h3>Datas e produtos</h3>${table(arr)}</div></div>`)}
function botinaStatusGeral(stats){let crit=stats.filter(s=>s.cls==='danger'),warn=stats.filter(s=>s.cls==='warn'),cad=stats.filter(s=>s.status==='Revisar cadastro');if(crit.length)return {cls:'danger',badge:'🚨 Prioridade imediata',txt:'Existem botinas em situação crítica',desc:`${crit.length} combinação(ões) de modelo e tamanho estão sem estoque ou com até um mês de cobertura.`};if(warn.length)return {cls:'warn',badge:'⚠️ Planejar reposição',txt:'Existem botinas abaixo da meta',desc:`${warn.length} combinação(ões) precisam de atenção${cad.length?`, incluindo ${cad.length} cadastro(s) incompleto(s)`:''}.`};return {cls:'ok',badge:'✅ Estoque confortável',txt:'Estoque de botinas dentro da meta',desc:'As combinações com consumo possuem cobertura igual ou superior a quatro meses.'}}
function renderBotinaPrioridades(stats){let rows=stats.map(s=>`<tr onclick="openItemBotina('${encodeURIComponent(s.k)}')" style="cursor:pointer"><td><b>${esc(s.modelo)}</b></td><td>${esc(s.tam)}</td><td>${fmt(s.estoque)}</td><td>${fmt(s.q)}</td><td>${fmt(s.media)}</td><td>${s.media?fmt(s.cobertura)+' mês(es)':'Sem consumo'}</td><td><span class="recommend-badge ${s.cls==='danger'?'danger':s.cls==='warn'?'warn':''}">${s.status}</span></td></tr>`).join('');return `<div class="tablewrap"><table><thead><tr><th>Modelo</th><th>Tamanho</th><th>Estoque</th><th>Saídas ${ANO_OPERACIONAL}</th><th>Média/mês</th><th>Cobertura</th><th>Status</th></tr></thead><tbody>${rows||'<tr><td colspan="7">Sem dados no filtro.</td></tr>'}</tbody></table></div>`}
function renderBotinaEstoqueConsumo(stats){let max=Math.max(1,...stats.map(s=>Math.max(s.estoque,s.q)));return stats.map(s=>`<div class="prod" onclick="openItemBotina('${encodeURIComponent(s.k)}')"><b>${esc(rotuloBotina(s.modelo,s.tam))}</b><div class="bar" title="Estoque atual" style="margin-top:9px"><span style="width:${Math.max(3,s.estoque/max*100)}%;background:linear-gradient(90deg,#076eb0,#16813a)"></span></div><div class="bar" title="Saídas em ${ANO_OPERACIONAL}" style="margin-top:5px"><span style="width:${Math.max(3,s.q/max*100)}%;background:linear-gradient(90deg,#f6c431,#b77900)"></span></div><small>Estoque ${fmt(s.estoque)} · saídas ${fmt(s.q)} · ${s.status}</small></div>`).join('')||'<p class="muted">Sem dados no filtro.</p>'}
function renderBotinas(){let arrTodos=byCat('Botinas'),allStats=botinaStats(),stats=botinaStatsFiltrados(allStats),arr=botinaRowsFiltradas(arrTodos),st=botinaStatusGeral(allStats),total=sum(arrTodos),estoque=stockTotal('Botinas'),mediaTotal=allStats.reduce((a,s)=>a+s.media,0),crit=allStats.filter(s=>s.cls!=='ok'),reqs=botinaColaboradores(arr),meses=groupMonth(arr),modelos=group(arrTodos.map(r=>({...r,ModeloAgrupado:modeloBotina(r)})),'ModeloAgrupado'),cadastro=allStats.filter(s=>s.tam==='Sem tamanho'||s.modelo==='Modelo não identificado'),top=allStats.filter(s=>s.cls!=='ok').slice(0,5);document.getElementById('botinasContent').innerHTML=`${renderBotinaPills(allStats)}<div class="decision"><div class="decision-main status-${st.cls}"><div class="eyebrow">Decisão automática · Botinas · ${ANO_OPERACIONAL}</div><div class="decision-title">${st.txt}</div><p class="decision-text">A análise agora cruza <b>modelo + tamanho</b>. Botina de segurança, botina motorista e bota PVC não são mais somadas como se fossem o mesmo produto. A meta operacional é manter aproximadamente <b>4 meses de cobertura</b> para cada combinação com consumo.</p><div class="mini-grid"><div class="mini"><span>Estoque total</span><b>${fmt(estoque)}</b><small>pares em todos os modelos</small></div><div class="mini"><span>Saídas em ${ANO_OPERACIONAL}</span><b>${fmt(total)}</b><small>pares retirados</small></div><div class="mini"><span>Média mensal</span><b>${fmt(mediaTotal)}</b><small>pares/mês</small></div><div class="mini"><span>Itens com atenção</span><b>${fmt(crit.length)}</b><small>modelo + tamanho</small></div></div></div><aside class="decision-side status-${st.cls}"><span class="recommend-badge ${st.cls==='danger'?'danger':st.cls==='warn'?'warn':''}">${st.badge}</span><h3>Leitura rápida</h3><p class="muted">${st.desc}</p>${top.length?`<div class="risk-box ${st.cls==='danger'?'danger':''}"><b>Prioridades para conferir:</b><br>${top.map(s=>`${esc(rotuloBotina(s.modelo,s.tam))} — ${s.status}`).join('<br>')}</div>`:'<div class="risk-box"><b>Sem prioridade imediata:</b> manter o acompanhamento mensal.</div>'}</aside></div>${cadastro.length?`<div class="note"><b>Atenção ao cadastro:</b> existem ${cadastro.length} item(ns) sem tamanho ou modelo plenamente identificado. Eles aparecem separadamente e não são somados a outros tamanhos.</div>`:''}<div class="panel"><h2>Prioridades por modelo e tamanho</h2><p class="muted">Vermelho: sem estoque ou até 1 mês. Amarelo: menos de 4 meses ou cadastro incompleto. Verde: cobertura adequada. Clique em uma linha para ver quem retirou e as datas.</p>${renderBotinaPrioridades(stats)}</div><div class="two"><div class="panel"><h2>Estoque x saídas</h2><p class="muted">Barra superior: estoque. Barra inferior: saídas de ${ANO_OPERACIONAL}.</p><div class="prodgrid">${renderBotinaEstoqueConsumo(stats)}</div></div><div class="panel"><h2>Itens que exigem atenção</h2>${renderBotinaPrioridades((stats.filter(s=>s.cls!=='ok').length?stats.filter(s=>s.cls!=='ok'):stats.slice(0,6)))}</div></div><div class="two"><div class="panel"><h2>Consumo mensal</h2>${bars(meses.map(x=>({...x,k:monthLabel(x.k)})),24)}</div><div class="panel"><h2>Consumo por modelo</h2>${bars(modelos,10)}</div></div><div class="two"><div class="panel"><h2>Colaboradores e trocas</h2><p class="muted">Clique no colaborador para ver modelos, tamanhos e datas.</p><div class="tablewrap"><table><thead><tr><th>Colaborador</th><th>Qtd</th><th>Item principal</th><th>Média entre retiradas</th></tr></thead><tbody>${reqs.slice(0,25).map(r=>`<tr onclick="openPessoaBotina('${encodeURIComponent(r.k)}')" style="cursor:pointer"><td><b>${esc(r.k)}</b></td><td>${fmt(r.q)}</td><td>${esc(r.principal)}</td><td>${r.mediaTroca?fmt(r.mediaTroca)+' dias':'—'}</td></tr>`).join('')}</tbody></table></div></div><div class="panel"><h2>Quem mais retirou</h2>${bars(reqs,15,'openPessoaBotina')}</div></div><div class="panel"><h2>Investigação por modelo e tamanho</h2><p class="muted">Cada cartão representa um item operacional distinto.</p><div class="prodgrid">${stats.map(s=>`<div class="prod" onclick="openItemBotina('${encodeURIComponent(s.k)}')"><b>🥾 ${esc(rotuloBotina(s.modelo,s.tam))}</b><br>Estoque ${fmt(s.estoque)} · saídas ${fmt(s.q)}<br><small>${s.status}</small></div>`).join('')}</div></div>`}'''
    starts = [
        position
        for position in (
            html.find("\nfunction extrairTamanho"),
            html.find("\nfunction renderBotinas"),
        )
        if position >= 0
    ]
    if not starts:
        raise RuntimeError(
            "Não encontrei o início do painel de botinas no index.html."
        )
    start = min(starts) + 1
    end = html.find("\nfunction getYearsSacolas", start)
    if end < 0:
        raise RuntimeError(
            "Não encontrei o final do painel de botinas no index.html."
        )
    return html[:start] + new_botina_block + html[end:]



def ensure_ferramentas_abertas_frontend(html: str) -> str:
    """Exibe somente saldos atuais em aberto, agrupados por colaborador.

    Devoluções e exclusões são usadas no Python, mas não aparecem na tela.
    O WhatsApp é exibido apenas para colaboradores com atraso e exige senha
    antes de abrir uma mensagem pronta.
    """
    tools_block = r"""function normalizarPesquisaFerramentas(txt){return String(txt||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\s+/g,' ').trim()}
let ferramentasBusca='';
function ferramentasAbertasFiltradas(){let termo=normalizarPesquisaFerramentas(ferramentasBusca);if(!termo)return FERRAMENTAS_ABERTAS;return FERRAMENTAS_ABERTAS.filter(r=>normalizarPesquisaFerramentas((r.Colaborador||'')+' '+(r.Produto||'')).includes(termo))}
function agruparFerramentasPorPessoa(arr){let m={};arr.forEach(r=>{let k=r.CodigoCliente||r.Colaborador||'Não informado';if(!m[k])m[k]={codigo:k,nome:r.Colaborador||'Não informado',telefone:r.TelefoneWhatsApp||'',itens:[],qtd:0,atrasados:0,maisAntiga:'',maisAntigaISO:'',pior:'ok'};let p=m[k];p.itens.push(r);p.qtd+=n(r.QuantidadeEmAberto);if(r.StatusClasse==='danger'){p.atrasados+=n(r.QuantidadeEmAberto);p.pior='danger'}else if(r.StatusClasse==='warn'&&p.pior!=='danger')p.pior='warn';if(!p.maisAntigaISO||String(r.DataRetiradaISO||'')<p.maisAntigaISO){p.maisAntigaISO=r.DataRetiradaISO||'';p.maisAntiga=r.DataRetirada||''}if(!p.telefone&&r.TelefoneWhatsApp)p.telefone=r.TelefoneWhatsApp});return Object.values(m).sort((a,b)=>(b.atrasados-a.atrasados)||(a.maisAntigaISO||'9999').localeCompare(b.maisAntigaISO||'9999')||a.nome.localeCompare(b.nome))}
function statusFerramentaBadge(cls,txt){return `<span class="recommend-badge ${cls==='danger'?'danger':cls==='warn'?'warn':''}">${esc(txt)}</span>`}
function tabelaFerramentasAbertas(arr){let rows=arr.map(r=>`<tr><td>${esc(r.Produto)}</td><td><b>${fmt(r.QuantidadeEmAberto)}</b></td><td>${esc(r.DataRetirada)}</td><td>${esc(r.PrazoDevolucao)}</td><td>${fmt(r.DiasFora)} dias</td><td>${statusFerramentaBadge(r.StatusClasse,r.StatusTexto)}</td><td>${esc(r.NumeroRetirada)}</td></tr>`).join('');return `<div class="tablewrap"><table><thead><tr><th>Ferramenta</th><th>Qtd. com a pessoa</th><th>Retirada</th><th>Prazo</th><th>Dias fora</th><th>Situação</th><th>Nº retirada</th></tr></thead><tbody>${rows||'<tr><td colspan="7">Nenhum item em aberto.</td></tr>'}</tbody></table></div>`}
function abrirItensPessoaFerramentas(codigoEnc){let codigo=decodeURIComponent(codigoEnc),p=agruparFerramentasPorPessoa(FERRAMENTAS_ABERTAS).find(x=>String(x.codigo)===codigo);if(!p)return;let atrasados=p.itens.filter(r=>r.StatusClasse==='danger');openModal('Ferramentas com '+p.nome,`${fmt(p.qtd)} item(ns) em aberto · ${fmt(atrasados.reduce((a,r)=>a+n(r.QuantidadeEmAberto),0))} atrasado(s)`,tabelaFerramentasAbertas(p.itens))}
function mensagemWhatsAppFerramentas(p){let atrasados=p.itens.filter(r=>r.StatusClasse==='danger');let linhas=atrasados.slice(0,8).map(r=>`• ${r.Produto} — qtd. ${fmt(r.QuantidadeEmAberto)}, prazo ${r.PrazoDevolucao}`);if(atrasados.length>8)linhas.push(`• e mais ${atrasados.length-8} item(ns)`);let primeiro=String(p.nome||'').trim().split(/\s+/)[0]||'';return `Olá, ${primeiro}. Consta no almoxarifado que os seguintes itens estão com prazo de devolução vencido:\n\n${linhas.join('\n')}\n\nPoderia verificar, por favor?`}
function abrirWhatsAppFerramentas(codigoEnc,event){if(event){event.preventDefault();event.stopPropagation()}let codigo=decodeURIComponent(codigoEnc),p=agruparFerramentasPorPessoa(FERRAMENTAS_ABERTAS).find(x=>String(x.codigo)===codigo);if(!p||!p.atrasados)return;if(!p.telefone){alert('Telefone não cadastrado para este colaborador.');return}let senha=prompt('Digite a senha para abrir o WhatsApp:');if(senha!==SENHA_WHATSAPP){alert('Senha incorreta.');return}let url='https://wa.me/'+encodeURIComponent(p.telefone)+'?text='+encodeURIComponent(mensagemWhatsAppFerramentas(p));window.open(url,'_blank','noopener')}
function cartaoPessoaFerramentas(p){let temAtraso=p.atrasados>0,acao=temAtraso?(p.telefone?`<button class="btn green" type="button" onclick="abrirWhatsAppFerramentas('${encodeURIComponent(p.codigo)}',event)">WhatsApp</button>`:`<button class="btn ghost" type="button" disabled title="Telefone não cadastrado">Sem telefone</button>`):'';return `<div class="panel" style="border-left:6px solid ${p.pior==='danger'?'var(--critico)':p.pior==='warn'?'var(--alerta)':'var(--ok)'};margin-bottom:12px"><div class="topbar" style="margin-bottom:8px"><div><h3>${esc(p.nome)}</h3><p class="muted">${fmt(p.itens.length)} tipo(s) de item · ${fmt(p.qtd)} unidade(s) em aberto${p.maisAntiga?` · retirada mais antiga: ${esc(p.maisAntiga)}`:''}</p></div><div class="actions">${temAtraso?statusFerramentaBadge('danger',fmt(p.atrasados)+' atrasado(s)'):statusFerramentaBadge(p.pior,p.pior==='warn'?'Vence em breve':'No prazo')}<button class="btn ghost" type="button" onclick="abrirItensPessoaFerramentas('${encodeURIComponent(p.codigo)}')">Ver itens</button>${acao}</div></div></div>`}
function atualizarPesquisaFerramentas(){let input=document.getElementById('ferramentasBuscaNome');if(input)ferramentasBusca=input.value;let arr=ferramentasAbertasFiltradas(),pessoas=agruparFerramentasPorPessoa(arr),box=document.getElementById('ferramentasResultados');if(!box)return;let total=arr.reduce((a,r)=>a+n(r.QuantidadeEmAberto),0),atrasados=arr.filter(r=>r.StatusClasse==='danger').reduce((a,r)=>a+n(r.QuantidadeEmAberto),0),semTelefone=pessoas.filter(p=>p.atrasados>0&&!p.telefone).length;box.innerHTML=`<div class="panel"><p class="leitura">Mostrando somente itens que continuam com colaboradores. O sistema soma as linhas da mesma retirada, desconta devoluções e cancelamentos e exibe apenas o saldo restante.</p><div class="kpis"><div class="kpi"><span>Pessoas com itens</span><br><b>${fmt(pessoas.length)}</b></div><div class="kpi"><span>Itens em aberto</span><br><b>${fmt(total)}</b></div><div class="kpi"><span>Itens atrasados</span><br><b>${fmt(atrasados)}</b></div><div class="kpi"><span>Sem telefone</span><br><b>${fmt(semTelefone)}</b></div></div></div>${pessoas.length?pessoas.map(cartaoPessoaFerramentas).join(''):`<div class="panel"><h2>Nenhum item encontrado</h2><p class="muted">Não há saldo em aberto para a pesquisa informada.</p></div>`}`}
function limparPesquisaFerramentas(){ferramentasBusca='';let input=document.getElementById('ferramentasBuscaNome');if(input){input.value='';input.focus()}atualizarPesquisaFerramentas()}
function renderFerramentas(){document.getElementById('genericTitle').textContent='Equipamentos devolvíveis com colaboradores';document.getElementById('genericSub').textContent='Mostra apenas equipamentos que precisam retornar. Ferramentas fixas e materiais de consumo ficam fora da contagem.';document.getElementById('genericContent').innerHTML=`<div class="panel"><h2>Pesquisar colaborador ou ferramenta</h2><p class="muted">Digite parte do nome da pessoa ou do equipamento. Itens devolvidos, ferramentas fixas e materiais de consumo não aparecem.</p><div class="searchbar" style="grid-template-columns:minmax(0,1fr) auto"><input id="ferramentasBuscaNome" type="search" autocomplete="off" placeholder="Ex.: Nilton, martelete, escada..." value="${esc(ferramentasBusca)}" oninput="atualizarPesquisaFerramentas()"><button class="btn ghost" type="button" onclick="limparPesquisaFerramentas()">Limpar pesquisa</button></div></div><div id="ferramentasResultados"></div>`;atualizarPesquisaFerramentas()}
function renderGeneric(cat){if(cat==='Ferramentas'){renderFerramentas();return}let arr=byCat(cat),prods=group(arr,'Nome do Produto'),reqs=group(arr,'Requisitante');document.getElementById('genericTitle').textContent=cat;document.getElementById('genericSub').textContent='Relatório de retiradas por produto, requisitante e histórico.';document.getElementById('genericContent').innerHTML=`<div class="panel"><div class="kpis"><div class="kpi"><span>Total retirado</span><br><b>${fmt(sum(arr))}</b></div><div class="kpi"><span>Nº de registros</span><br><b>${arr.length}</b></div><div class="kpi"><span>Requisitantes</span><br><b>${reqs.length}</b></div><div class="kpi"><span>Produtos</span><br><b>${prods.length}</b></div></div></div><div class="two"><div class="panel"><h2>Produtos mais retirados</h2>${bars(prods,15)}</div><div class="panel"><h2>Quem mais retirou</h2>${bars(reqs,15)}</div></div><div class="panel"><h2>Histórico</h2>${table(arr)}</div>`}"""

    starts = [
        position
        for position in (
            html.find("function normalizarPesquisaFerramentas"),
            html.find("function renderGeneric(cat)"),
        )
        if position >= 0
    ]
    if not starts:
        raise RuntimeError(
            "Não encontrei o painel genérico para inserir Ferramentas."
        )
    start = min(starts)
    end = html.find("\nfunction stockByCat", start)
    if end < 0:
        raise RuntimeError(
            "Não encontrei o final do painel genérico no index.html."
        )
    html = html[:start] + tools_block + html[end:]

    # Ajusta o card inicial de Ferramentas para representar o saldo atual.
    home_pattern = r"function homeCards\(\)\{.*?\}\nfunction show"
    home_block = r"""function homeCards(){let el=document.getElementById('homeCards');el.innerHTML=CATS.map(c=>{if(c[0]==='Ferramentas'){let arr=FERRAMENTAS_ABERTAS,pessoas=agruparFerramentasPorPessoa(arr),qtd=arr.reduce((a,r)=>a+n(r.QuantidadeEmAberto),0),atrasados=arr.filter(r=>r.StatusClasse==='danger').reduce((a,r)=>a+n(r.QuantidadeEmAberto),0);return `<div class="card" onclick="openCat('Ferramentas')"><span class="icon">${c[1]}</span><h2>Ferramentas</h2><p class="muted">Equipamentos devolvíveis que continuam com colaboradores.</p><div class="chips"><span class="chip">${fmt(qtd)} itens em aberto</span><span class="chip">${fmt(pessoas.length)} colaboradores</span><span class="chip">${fmt(atrasados)} atrasados</span></div></div>`}let arr=byCat(c[0]),qtd=sum(arr),req=unique(arr,'Requisitante'),prod=unique(arr,'Nome do Produto');return `<div class="card" onclick="openCat('${c[0]}')"><span class="icon">${c[1]}</span><h2>${c[0]}</h2><p class="muted">${c[2]}</p><div class="chips"><span class="chip">${fmt(qtd)} unidades</span><span class="chip">${arr.length} retiradas</span><span class="chip">${req} requisitantes</span><span class="chip">${prod} produtos</span></div></div>`}).join('')}
function show"""
    updated, count = re.subn(
        home_pattern,
        home_block,
        html,
        count=1,
        flags=re.S,
    )
    if count != 1:
        raise RuntimeError(
            "Não foi possível ajustar o card inicial de Ferramentas."
        )

    marker = "const FERRAMENTAS_SALDO_VERSAO=9;"
    marker_pattern = r"const\s+FERRAMENTAS_SALDO_VERSAO\s*=\s*\d+\s*;"
    if re.search(marker_pattern, updated):
        updated = re.sub(
            marker_pattern,
            marker,
            updated,
            count=1,
        )
    else:
        insert_at = updated.find("function normalizarPesquisaFerramentas")
        if insert_at < 0:
            raise RuntimeError(
                "Não encontrei o ponto para inserir a versão do saldo."
            )
        updated = updated[:insert_at] + marker + "\n" + updated[insert_at:]

    return updated


def build_updated_html(
    original_html: str,
    data: List[Dict[str, Any]],
    stock: List[Dict[str, Any]],
    open_tools: List[Dict[str, Any]],
) -> Tuple[str, str, str]:
    now = dt.datetime.now()
    generated_at = now.strftime("%d/%m/%Y %H:%M:%S")
    reference_date = now.strftime("%Y-%m-%d")
    operating_rows = operational_data(data)

    if not operating_rows:
        raise RuntimeError(
            f"Nenhuma retirada de {OPERATING_YEAR} foi encontrada. "
            "A publicação foi bloqueada para evitar um painel vazio."
        )

    # DATA mantém 2025 e 2026 porque 2025 é necessário para a sazonalidade.
    # Todos os cálculos operacionais do navegador usam somente 2026.
    html = original_html
    html = replace_js_const(
        html,
        "DATA",
        json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    )
    html = replace_js_const(
        html,
        "ESTOQUE",
        json.dumps(
            stock,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    )
    tools_json = json.dumps(
        open_tools,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    if re.search(r"\bconst\s+FERRAMENTAS_ABERTAS\s*=", html):
        html = replace_js_const(
            html,
            "FERRAMENTAS_ABERTAS",
            tools_json,
        )
    else:
        estoque_match = re.search(
            r"\bconst\s+ESTOQUE\s*=.*?;",
            html,
            flags=re.S,
        )
        if not estoque_match:
            raise RuntimeError(
                "Não encontrei ESTOQUE para inserir FERRAMENTAS_ABERTAS."
            )
        html = (
            html[:estoque_match.end()]
            + "\nconst FERRAMENTAS_ABERTAS=" + tools_json + ";"
            + html[estoque_match.end():]
        )

    if re.search(r"\bconst\s+SENHA_WHATSAPP\s*=", html):
        html = replace_js_const(
            html,
            "SENHA_WHATSAPP",
            WHATSAPP_PASSWORD,
            quote=True,
        )
    else:
        tools_match = re.search(
            r"\bconst\s+FERRAMENTAS_ABERTAS\s*=.*?;",
            html,
            flags=re.S,
        )
        if not tools_match:
            raise RuntimeError(
                "Não encontrei FERRAMENTAS_ABERTAS para inserir senha."
            )
        html = (
            html[:tools_match.end()]
            + "\nconst SENHA_WHATSAPP="
            + json.dumps(WHATSAPP_PASSWORD, ensure_ascii=False)
            + ";"
            + html[tools_match.end():]
        )
    # A planilha baixada é operacional e, portanto, contém somente 2026.
    html = replace_js_const(
        html,
        "XLSX_B64",
        make_xlsx_b64(operating_rows),
        quote=True,
    )
    html = replace_js_const(
        html,
        "GERADO_EM",
        generated_at,
        quote=True,
    )
    html = replace_js_const(
        html,
        "DATA_REFERENCIA",
        reference_date,
        quote=True,
    )
    html = ensure_operational_frontend(html)
    html = ensure_sacola_package_frontend(html)
    html = ensure_botina_model_frontend(html)
    html = ensure_ferramentas_abertas_frontend(html)

    dates = [
        row["Data_iso"]
        for row in operating_rows
        if row.get("Data_iso")
    ]
    if dates:
        start = dt.datetime.strptime(
            min(dates), "%Y-%m-%d"
        ).strftime("%d/%m/%Y")
        end = dt.datetime.strptime(
            max(dates), "%Y-%m-%d"
        ).strftime("%d/%m/%Y")

        html = re.sub(
            r'<span id="periodoHeader">.*?</span>',
            (
                f'<span id="periodoHeader">{start} a {end} '
                f'· operacional {OPERATING_YEAR}</span>'
            ),
            html,
            count=1,
            flags=re.S,
        )
        html = re.sub(
            r'<span id="geradoHeader">.*?</span>',
            f'<span id="geradoHeader">{generated_at}</span>',
            html,
            count=1,
            flags=re.S,
        )

    return html, generated_at, reference_date


def load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    try:
        value = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception as exc:
        log(f"AVISO: estado anterior inválido: {exc}")
        return {}


def save_state(state: Dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = STATE_PATH.with_name(STATE_PATH.name + ".tmp")
    try:
        temp_path.write_text(
            json.dumps(
                state,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        os.replace(temp_path, STATE_PATH)
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


def parse_iso_date(value: Any) -> Optional[dt.date]:
    try:
        return dt.date.fromisoformat(str(value))
    except Exception:
        return None


def validate_regression(
    state: Dict[str, Any],
    backup_date: dt.date,
    last_data_date: str,
    record_count: int,
) -> None:
    previous_backup_date = parse_iso_date(state.get("backup_date"))
    if (
        previous_backup_date
        and backup_date < previous_backup_date
        and not ALLOW_BACKUP_REGRESSION
    ):
        raise RuntimeError(
            "REGRESSÃO BLOQUEADA: o backup selecionado é de "
            f"{backup_date:%d/%m/%Y}, mas o último processado era de "
            f"{previous_backup_date:%d/%m/%Y}."
        )

    previous_data_date = parse_iso_date(state.get("last_data_date"))
    current_data_date = parse_iso_date(last_data_date)
    if (
        previous_data_date
        and current_data_date
        and current_data_date < previous_data_date
        and not ALLOW_BACKUP_REGRESSION
    ):
        raise RuntimeError(
            "REGRESSÃO BLOQUEADA: a última movimentação do banco atual é "
            f"{current_data_date:%d/%m/%Y}, mas o dashboard já havia "
            f"processado movimentações até {previous_data_date:%d/%m/%Y}."
        )

    try:
        previous_count = int(state.get("record_count") or 0)
    except Exception:
        previous_count = 0

    if previous_count > 0 and record_count < previous_count:
        drop = (previous_count - record_count) / previous_count * 100
        if drop > MAX_RECORD_DROP_PERCENT and not ALLOW_RECORD_DROP:
            raise RuntimeError(
                "QUEDA DE DADOS BLOQUEADA: os registros caíram de "
                f"{previous_count} para {record_count} "
                f"({drop:.1f}%). Para autorizar conscientemente, use "
                "ALLOW_RECORD_DROP=true no config.env."
            )
        log(
            "AVISO: a quantidade de registros caiu de "
            f"{previous_count} para {record_count} ({drop:.1f}%)."
        )


def run_git(
    args: List[str],
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_DIR,
        text=True,
        capture_output=True,
    )
    if check and result.returncode != 0:
        detail = (result.stdout + "\n" + result.stderr).strip()
        raise RuntimeError(
            f"Falha no comando git {' '.join(args)}:\n{detail}"
        )
    return result


def sync_repository() -> None:
    if not GIT_PUSH:
        return
    if not (REPO_DIR / ".git").exists():
        raise FileNotFoundError(
            f"Repositório Git não encontrado: {REPO_DIR}"
        )

    log("Sincronizando o repositório com o GitHub...")
    run_git(["pull", "--rebase", "--autostash"])
    log("Repositório sincronizado.")


def publish_git() -> bool:
    if not GIT_PUSH:
        log("GIT_PUSH=false. Envio automático desativado.")
        return False

    run_git(["add", INDEX_PATH.name])

    staged = run_git(
        ["diff", "--cached", "--quiet"],
        check=False,
    )
    if staged.returncode == 0:
        log("Sem alterações no index.html. Nada para enviar.")
        return False
    if staged.returncode not in {0, 1}:
        raise RuntimeError(
            "Não foi possível verificar as alterações preparadas no Git."
        )

    message = (
        "Atualização automática do dashboard - "
        f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}"
    )
    run_git(["commit", "-m", message])

    first_push = run_git(["push"], check=False)
    if first_push.returncode != 0:
        detail = (first_push.stdout + "\n" + first_push.stderr).lower()
        log(
            "Primeiro push não foi aceito. Tentando sincronizar e "
            "reenviar."
        )
        run_git(["pull", "--rebase", "--autostash"])
        run_git(["push"])
        if "non-fast-forward" not in detail:
            log("Push recuperado após nova sincronização.")

    log("GitHub atualizado com sucesso.")
    return True


class ExecutionLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.acquired = False

    def __enter__(self) -> "ExecutionLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)

        if self.path.exists():
            age_minutes = (
                time.time() - self.path.stat().st_mtime
            ) / 60
            if age_minutes > LOCK_STALE_MINUTES:
                log(
                    "AVISO: bloqueio antigo encontrado e removido "
                    f"({age_minutes:.1f} minutos)."
                )
                self.path.unlink(missing_ok=True)

        try:
            descriptor = os.open(
                self.path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError as exc:
            raise RuntimeError(
                "Já existe outra execução do atualizador em andamento. "
                "Esta execução foi encerrada sem alterar arquivos."
            ) from exc

        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "started_at": dt.datetime.now().isoformat(
                            timespec="seconds"
                        ),
                    },
                    ensure_ascii=False,
                )
            )
        self.acquired = True
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)


def main() -> int:
    try:
        with ExecutionLock(LOCK_PATH):
            sync_repository()

            backup, backup_date, used_name_date = find_latest_backup()
            log(
                f"Backup selecionado: {backup} "
                f"(data considerada: {backup_date:%d/%m/%Y}; "
                f"origem: {'nome do arquivo' if used_name_date else 'modificação'})"
            )
            wait_until_file_is_stable(backup)

            raw, method = read_table(backup, TABELA_RETIRADAS)
            log(
                f"Tabela {TABELA_RETIRADAS} lida via {method}: "
                f"{len(raw)} linhas brutas"
            )

            raw_stock, stock_method = read_table(
                backup,
                TABELA_ESTOQUE,
            )
            log(
                f"Tabela {TABELA_ESTOQUE} lida via {stock_method}: "
                f"{len(raw_stock)} linhas brutas"
            )

            raw_returns, returns_method = read_table(
                backup,
                TABELA_DEVOLUCOES,
            )
            log(
                f"Tabela {TABELA_DEVOLUCOES} lida via {returns_method}: "
                f"{len(raw_returns)} linhas brutas"
            )
            raw_exclusions, exclusions_method = read_table(
                backup,
                TABELA_EXCLUSOES,
            )
            log(
                f"Tabela {TABELA_EXCLUSOES} lida via {exclusions_method}: "
                f"{len(raw_exclusions)} linhas brutas"
            )
            raw_clients, clients_method = read_table(
                backup,
                TABELA_CLIENTES,
            )
            log(
                f"Tabela {TABELA_CLIENTES} lida via {clients_method}: "
                f"{len(raw_clients)} cadastros"
            )

            tool_classifications, classification_stats, pending_products = (
                prepare_tool_classifications(raw, raw_stock)
            )
            data, removed = normalize_retiradas(
                raw,
                tool_classifications,
            )
            stock = normalize_estoque(raw_stock)
            open_tools, tool_diagnostics = normalize_open_tools(
                raw,
                raw_returns,
                raw_exclusions,
                raw_clients,
                raw_stock,
                tool_classifications,
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

            state = load_state()
            validate_regression(
                state,
                backup_date,
                last_data_date,
                len(data),
            )

            unique_withdrawals = len(
                {
                    row["Nº Retirada"]
                    for row in data
                    if row.get("Nº Retirada")
                }
            )
            units = sum(
                float(row.get("Qtde_num") or 0)
                for row in data
            )
            operating_rows = operational_data(data)
            operating_unique_withdrawals = len(
                {
                    row["Nº Retirada"]
                    for row in operating_rows
                    if row.get("Nº Retirada")
                }
            )
            operating_units = sum(
                float(row.get("Qtde_num") or 0)
                for row in operating_rows
            )
            botina_stock = sum(
                float(item.get("QtdeEstoque") or 0)
                for item in stock
                if item.get("Categoria") == "Botinas"
            )
            sacola_stock = sum(
                float(item.get("QtdeEstoque") or 0)
                for item in stock
                if item.get("Categoria") == "Sacolas"
            )
            sacola_stock_packages = sum(
                float(item.get("PacotesEstoque") or 0)
                for item in stock
                if item.get("Categoria") == "Sacolas"
            )

            log(f"Registros históricos preservados: {len(data)}")
            log(
                f"Registros operacionais de {OPERATING_YEAR}: "
                f"{len(operating_rows)}"
            )
            log(
                f"Retiradas únicas de {OPERATING_YEAR}: "
                f"{operating_unique_withdrawals}"
            )
            category_totals: Dict[str, float] = {}
            for row in operating_rows:
                category = safe_text(row.get("Categoria")) or "Sem categoria"
                category_totals[category] = (
                    category_totals.get(category, 0.0)
                    + float(row.get("Qtde_num") or 0)
                )
            category_parts = []
            for category in sorted(category_totals):
                unit_label = (
                    "sacolas"
                    if category == "Sacolas"
                    else "pares"
                    if category == "Botinas"
                    else "unidades"
                )
                category_parts.append(
                    f"{category}={category_totals[category]} {unit_label}"
                )
            log(
                "Totais operacionais por categoria "
                "(não somados entre si): "
                + "; ".join(category_parts)
            )
            log(
                f"Histórico sazonal disponível: "
                f"{SEASONAL_HISTORY_YEAR} e {OPERATING_YEAR}"
            )
            log(
                "Linhas de ferramentas fixas, consumo, ignoradas ou "
                f"não classificadas removidas da visão operacional: {removed}"
            )
            log(
                "Classificação por código: "
                f"{classification_stats.get('devolvivel', 0)} devolvível(is); "
                f"{classification_stats.get('uso_permanente', 0)} de uso permanente; "
                f"{classification_stats.get('consumo', 0)} de consumo; "
                f"{classification_stats.get('nao_classificado', 0)} pendente(s) de revisão."
            )
            if pending_products:
                log(
                    "AVISO: produtos ainda não classificados: "
                    f"{len(pending_products)}. Lista gerada em "
                    f"{TOOL_CLASSIFICATION_PENDING_PATH}. Esses itens não "
                    "entram na contagem nem geram WhatsApp."
                )
            botina_models = sorted({
                str(item.get("Modelo") or "Modelo não identificado")
                for item in stock
                if item.get("Categoria") == "Botinas"
            })
            botina_without_size = sum(
                1 for item in stock
                if item.get("Categoria") == "Botinas"
                and not safe_text(item.get("Tamanho"))
            )
            log(f"Estoque Botinas: {botina_stock}")
            log("Modelos de botinas identificados: " + ", ".join(botina_models))
            if botina_without_size:
                log(f"AVISO: itens de botinas sem tamanho: {botina_without_size}")
            log(
                f"Estoque Sacolas: {sacola_stock} sacolas "
                f"({sacola_stock_packages} pacotes de "
                f"{SACOLAS_POR_PACOTE})"
            )
            tool_people = len({
                item.get("CodigoCliente") or item.get("Colaborador")
                for item in open_tools
            })
            tool_open_qty = sum(
                float(item.get("QuantidadeEmAberto") or 0)
                for item in open_tools
            )
            tool_overdue_qty = sum(
                float(item.get("QuantidadeEmAberto") or 0)
                for item in open_tools
                if item.get("StatusClasse") == "danger"
            )
            tool_missing_phone = len({
                item.get("CodigoCliente") or item.get("Colaborador")
                for item in open_tools
                if item.get("StatusClasse") == "danger"
                and not item.get("TelefoneWhatsApp")
            })
            log(
                "Ferramentas em aberto: "
                f"{tool_open_qty} unidade(s), {tool_people} colaborador(es)"
            )
            log(
                "Ferramentas atrasadas: "
                f"{tool_overdue_qty} unidade(s)"
            )
            if tool_missing_phone:
                log(
                    "AVISO: colaboradores atrasados sem telefone: "
                    f"{tool_missing_phone}"
                )
            log(
                "Conferência de saldos: "
                f"{tool_diagnostics['withdrawal_groups']} grupo(s) analisado(s); "
                f"{tool_diagnostics['duplicate_withdrawal_groups']} com "
                "linhas repetidas; "
                f"{tool_diagnostics['adjusted_by_return_groups']} ajustado(s) "
                "por devolução; "
                f"{tool_diagnostics['adjusted_by_exclusion_groups']} "
                "ajustado(s) por exclusão; "
                f"{tool_diagnostics['fully_closed_groups']} encerrado(s)."
            )
            log(
                "Filtro de ferramentas abertas: "
                f"{tool_diagnostics['devolvable_groups']} grupo(s) devolvível(is) "
                f"({tool_diagnostics['devolvable_quantity']} unidade(s)); "
                f"{tool_diagnostics['permanent_groups']} de uso permanente "
                f"({tool_diagnostics['permanent_quantity']} unidade(s)) ignorado(s); "
                f"{tool_diagnostics['consumption_groups']} de consumo "
                f"({tool_diagnostics['consumption_quantity']} unidade(s)) ignorado(s); "
                f"{tool_diagnostics['unclassified_groups']} não classificado(s) "
                f"({tool_diagnostics['unclassified_quantity']} unidade(s)) fora da cobrança."
            )
            if tool_diagnostics["negative_balance_groups"]:
                log(
                    "AVISO: baixas maiores que retiradas em "
                    f"{tool_diagnostics['negative_balance_groups']} grupo(s). "
                    "Esses saldos não foram publicados."
                )
            log(
                "Última movimentação encontrada: "
                f"{last_data_date or 'não identificada'}"
            )

            if not INDEX_PATH.exists():
                raise FileNotFoundError(
                    f"index.html não encontrado: {INDEX_PATH}"
                )

            original_html = INDEX_PATH.read_text(encoding="utf-8")
            new_hash = payload_hash(data, stock, open_tools)
            old_hash = current_html_payload_hash(original_html)
            today = dt.date.today().isoformat()
            current_reference = current_html_reference_date(
                original_html
            )
            preview_html = ensure_ferramentas_abertas_frontend(
                ensure_botina_model_frontend(
                    ensure_sacola_package_frontend(
                        ensure_operational_frontend(original_html)
                    )
                )
            )

            data_changed = old_hash != new_hash
            reference_changed = current_reference != today
            rules_changed = preview_html != original_html

            if (
                not data_changed
                and not reference_changed
                and not rules_changed
            ):
                log(
                    "Dados, regras de sacolas, botinas, classificação por código, saldos de ferramentas e data de referência não mudaram. "
                    "Nenhum arquivo ou commit foi criado."
                )
                save_state(
                    {
                        "version": 9,
                        "backup_file": str(backup),
                        "backup_date": backup_date.isoformat(),
                        "last_data_date": last_data_date,
                        "record_count": len(data),
                        "unique_withdrawals": unique_withdrawals,
                        "units": units,
                        "operating_year": OPERATING_YEAR,
                        "operating_record_count": len(operating_rows),
                        "operating_unique_withdrawals": operating_unique_withdrawals,
                        "operating_units": operating_units,
                        "sacolas_por_pacote": SACOLAS_POR_PACOTE,
                        "open_tool_rows": len(open_tools),
                        "open_tool_quantity": tool_open_qty,
                        "overdue_tool_quantity": tool_overdue_qty,
                        "tool_balance_diagnostics": tool_diagnostics,
                        "tool_classification_stats": classification_stats,
                        "tool_classification_file": str(TOOL_CLASSIFICATION_PATH),
                        "pending_tool_classifications": len(pending_products),
                        "totals_by_category": category_totals,
                        "payload_hash": new_hash,
                        "last_check_at": dt.datetime.now().isoformat(
                            timespec="seconds"
                        ),
                        "last_action": "sem_alteracao",
                    }
                )
                return 0

            if rules_changed:
                log(
                    "Nova regra aplicada: Ferramentas classifica cada produto "
                    "pelo código em devolvível, uso permanente ou consumo; "
                    "itens fixos e consumíveis ficam fora da contagem e do "
                    "WhatsApp; itens novos não classificados ficam em revisão; "
                    "saldos devolvíveis continuam descontando devoluções e exclusões; "
                    "botinas separadas por modelo e tamanho; "
                    "indicadores operacionais de "
                    f"{OPERATING_YEAR}; {SEASONAL_HISTORY_YEAR} somente na "
                    f"sazonalidade; 1 pacote = {SACOLAS_POR_PACOTE} sacolas."
                )
            if data_changed:
                log("Mudança real nos dados detectada.")
            elif reference_changed:
                log(
                    "Dados iguais; atualização diária da "
                    "DATA_REFERENCIA detectada."
                )

            updated_html, generated_at, reference_date = (
                build_updated_html(
                    original_html,
                    data,
                    stock,
                    open_tools,
                )
            )
            atomic_write_text(INDEX_PATH, updated_html)
            log(f"index.html atualizado com segurança: {INDEX_PATH}")

            published = publish_git()

            save_state(
                {
                    "version": 9,
                    "backup_file": str(backup),
                    "backup_date": backup_date.isoformat(),
                    "last_data_date": last_data_date,
                    "record_count": len(data),
                    "unique_withdrawals": unique_withdrawals,
                    "units": units,
                    "operating_year": OPERATING_YEAR,
                    "operating_record_count": len(operating_rows),
                    "operating_unique_withdrawals": operating_unique_withdrawals,
                    "operating_units": operating_units,
                    "botina_stock": botina_stock,
                    "sacola_stock": sacola_stock,
                    "sacola_stock_packages": sacola_stock_packages,
                    "sacolas_por_pacote": SACOLAS_POR_PACOTE,
                    "open_tool_rows": len(open_tools),
                    "open_tool_quantity": tool_open_qty,
                    "overdue_tool_quantity": tool_overdue_qty,
                    "tool_balance_diagnostics": tool_diagnostics,
                    "tool_classification_stats": classification_stats,
                    "tool_classification_file": str(TOOL_CLASSIFICATION_PATH),
                    "pending_tool_classifications": len(pending_products),
                    "totals_by_category": category_totals,
                    "payload_hash": new_hash,
                    "generated_at": generated_at,
                    "reference_date": reference_date,
                    "last_check_at": dt.datetime.now().isoformat(
                        timespec="seconds"
                    ),
                    "last_action": (
                        "publicado"
                        if published
                        else "atualizado_localmente"
                    ),
                }
            )
            return 0

    except Exception as exc:
        log(f"ERRO: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
