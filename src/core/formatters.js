/**
 * Funções puras de formatação e agrupamento.
 *
 * Elas não acessam DOM nem variáveis globais, o que permite testes isolados.
 */

/** Escapa texto antes de inseri-lo em HTML gerado. */
export function escapeHtml(value) {
  return String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      })[char]
  );
}

/** Converte valores indefinidos, vazios ou inválidos para zero. */
export function toNumber(value) {
  return Number(value || 0) || 0;
}

/** Formata números segundo o padrão brasileiro. */
export function formatNumber(value) {
  const number = Number(value || 0);
  return number.toLocaleString("pt-BR", {
    maximumFractionDigits: number % 1 ? 1 : 0
  });
}

/** Converte YYYY-MM-DD para DD/MM/YYYY. */
export function formatBrazilianDate(isoDate) {
  if (!isoDate) return "";
  const [year, month, day] = isoDate.split("-");
  return `${day}/${month}/${year}`;
}

/** Cria uma data local sem o deslocamento indesejado causado pelo UTC. */
export function parseIsoLocal(isoDate) {
  const [year, month, day] = String(isoDate).split("-").map(Number);
  return new Date(year, month - 1, day);
}

/** Soma dias a uma data ISO e retorna outra data ISO. */
export function addDays(isoDate, days) {
  const date = parseIsoLocal(isoDate);
  date.setDate(date.getDate() + days);
  return date.toISOString().slice(0, 10);
}

/** Gera rótulo de mês curto, por exemplo: jul/2026. */
export function monthLabel(key) {
  if (!key) return "Sem data";
  const [year, month] = key.split("-");
  const names = [
    "jan",
    "fev",
    "mar",
    "abr",
    "mai",
    "jun",
    "jul",
    "ago",
    "set",
    "out",
    "nov",
    "dez"
  ];
  return `${names[Number(month) - 1]}/${year}`;
}

/** Extrai o ano do registro, priorizando a propriedade Ano. */
export function recordYear(row) {
  return Number(row.Ano || String(row.Data_iso || "").slice(0, 4) || 0);
}

/** Conta valores únicos não vazios. */
export function countUnique(rows, key) {
  return new Set(rows.map((row) => row[key]).filter(Boolean)).size;
}

/** Soma o campo Qtde_num de uma coleção. */
export function sumQuantities(rows) {
  return rows.reduce((total, row) => total + toNumber(row.Qtde_num), 0);
}

/**
 * Agrupa registros por uma propriedade e acumula quantidade e ocorrências.
 */
export function groupBy(rows, key) {
  const groups = {};

  rows.forEach((row) => {
    const groupKey = row[key] || "Não informado";
    if (!groups[groupKey]) {
      groups[groupKey] = { k: groupKey, q: 0, n: 0, rows: [] };
    }
    groups[groupKey].q += toNumber(row.Qtde_num);
    groups[groupKey].n += 1;
    groups[groupKey].rows.push(row);
  });

  return Object.values(groups).sort((a, b) => b.q - a.q);
}

/** Agrupa por mês em ordem cronológica. */
export function groupByMonth(rows) {
  const groups = {};

  rows.forEach((row) => {
    const key = String(row.Data_iso || "").slice(0, 7) || "Sem data";
    if (!groups[key]) {
      groups[key] = { k: key, q: 0, n: 0, rows: [] };
    }
    groups[key].q += toNumber(row.Qtde_num);
    groups[key].n += 1;
    groups[key].rows.push(row);
  });

  return Object.values(groups).sort((a, b) => a.k.localeCompare(b.k));
}

/** Retorna todos os dias da semana, inclusive os sem movimentação. */
export function groupByWeekday(rows) {
  const order = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"];
  const groups = groupBy(rows, "DiaSemana");
  return order.map(
    (day) => groups.find((group) => group.k === day) || { k: day, q: 0, n: 0, rows: [] }
  );
}
