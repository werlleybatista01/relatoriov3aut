from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, List

import pyodbc

ACCESS_DRIVER = "Microsoft Access Driver (*.mdb, *.accdb)"

def require_access_db(path: Path) -> Path:
    if not path.is_file():
        raise RuntimeError(f"Banco Access principal indisponivel: {path}")
    return path

def read_tables_readonly(db_path: Path, table_names: Iterable[str], password: str = "") -> Dict[str, List[Dict[str, Any]]]:
    """Le tabelas permitidas em uma unica conexao Access somente leitura."""
    source = require_access_db(db_path)
    allowed = tuple(table_names)
    if not allowed or any(not name.isidentifier() for name in allowed):
        raise RuntimeError("Lista de tabelas Access invalida")
    connection_string = f"DRIVER={{{ACCESS_DRIVER}}};DBQ={source};READONLY=TRUE;"
    if password:
        connection_string += f"PWD={password};"
    connection = pyodbc.connect(connection_string, readonly=True, autocommit=True, timeout=20)
    try:
        result: Dict[str, List[Dict[str, Any]]] = {}
        cursor = connection.cursor()
        for table_name in allowed:
            cursor.execute(f"SELECT * FROM [{table_name}]")
            columns = [column[0] for column in cursor.description]
            result[table_name] = [{columns[index]: row[index] for index in range(len(columns))} for row in cursor.fetchall()]
        return result
    finally:
        connection.close()
