import { EVENTS } from "../config.js";
import {
  addDays,
  countUnique,
  escapeHtml,
  formatBrazilianDate,
  formatNumber,
  groupBy,
  groupByMonth,
  groupByWeekday,
  monthLabel,
  parseIsoLocal,
  recordYear,
  sumQuantities,
  toNumber
} from "../core/formatters.js";

const DAY_NAMES = [
  "Segunda",
  "Terça",
  "Quarta",
  "Quinta",
  "Sexta",
  "Sábado",
  "Domingo"
];

const SECTOR_KEYS = [
  "Setor",
  "Secretaria",
  "Departamento",
  "Lotação",
  "Lotacao",
  "Unidade Administrativa",
  "Unidade"
];

const HOUR_BANDS = [
  { label: "06h–08h", start: 6, end: 8 },
  { label: "08h–10h", start: 8, end: 10 },
  { label: "10h–12h", start: 10, end: 12 },
  { label: "12h–14h", start: 12, end: 14 },
  { label: "14h–16h", start: 14, end: 16 },
  { label: "16h–18h", start: 16, end: 18 },
  { label: "18h–20h", start: 18, end: 20 }
];

const REORDER_POINT_DAYS = 90;
const ATTENTION_START_DAYS = 120;

const CHART_COLORS = ["#1473e6", "#18a67a", "#7c4dff", "#f59e0b", "#e85d3f", "#52627a"];

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function isoDate(row) {
  return String(row.Data_iso || "").slice(0, 10);
}

function safeDate(iso) {
  if (!iso) return null;
  const value = parseIsoLocal(iso);
  return Number.isNaN(value.getTime()) ? null : value;
}

function daysBetween(startIso, endIso) {
  const start = safeDate(startIso);
  const end = safeDate(endIso);
  if (!start || !end || end < start) return 0;
  return Math.floor((end - start) / 86_400_000) + 1;
}

function dateBounds(rows) {
  const dates = rows.map(isoDate).filter(Boolean).sort();
  return {
    start: dates[0] || "",
    end: dates.at(-1) || ""
  };
}

function rowSector(row) {
  for (const key of SECTOR_KEYS) {
    const value = String(row[key] || "").trim();
    if (value) return value;
  }
  return "";
}

function rowHour(row) {
  const directValues = [
    row.Hora,
    row.HoraRetirada,
    row["Hora Retirada"],
    row.DataHora,
    row.DataHora_iso,
    row.Data_fmt
  ];

  for (const value of directValues) {
    const match = String(value || "").match(/(?:^|\s|T)([01]?\d|2[0-3]):[0-5]\d/);
    if (match) return Number(match[1]);
  }

  return null;
}

function hourBandIndex(hour) {
  if (hour === null) return -1;
  return HOUR_BANDS.findIndex((band) => hour >= band.start && hour < band.end);
}

function average(values) {
  if (!values.length) return 0;
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function linearRegression(values) {
  if (values.length < 2) return values.slice();
  const n = values.length;
  const sumX = ((n - 1) * n) / 2;
  const sumXX = ((n - 1) * n * (2 * n - 1)) / 6;
  const sumY = values.reduce((total, value) => total + value, 0);
  const sumXY = values.reduce((total, value, index) => total + index * value, 0);
  const denominator = n * sumXX - sumX * sumX;
  const slope = denominator ? (n * sumXY - sumX * sumY) / denominator : 0;
  const intercept = (sumY - slope * sumX) / n;
  return values.map((_value, index) => Math.max(0, intercept + slope * index));
}

function nextMonthKey(key, offset = 1) {
  const [year, month] = key.split("-").map(Number);
  const date = new Date(year, month - 1 + offset, 1);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function monthlySeries(rows) {
  const grouped = groupByMonth(rows).filter((item) => item.k !== "Sem data");
  if (!grouped.length) return [];

  const byKey = new Map(grouped.map((item) => [item.k, item.q]));
  const first = grouped[0].k;
  const last = grouped.at(-1).k;
  const result = [];
  let key = first;

  while (key <= last && result.length < 36) {
    result.push({ key, value: byKey.get(key) || 0, projected: false });
    key = nextMonthKey(key);
  }

  return result;
}

function trendPercent(series, periodEnd) {
  if (series.length < 2) return { value: null, projected: false };
  const latest = series.at(-1);
  const previous = series.at(-2).value;
  if (!previous) {
    return { value: latest.value ? 100 : 0, projected: false };
  }

  let comparableCurrent = latest.value;
  let projected = false;
  const end = safeDate(periodEnd);

  if (end && latest.key === periodEnd.slice(0, 7)) {
    const daysInMonth = new Date(end.getFullYear(), end.getMonth() + 1, 0).getDate();
    const elapsedDays = end.getDate();
    if (elapsedDays < daysInMonth && elapsedDays > 0) {
      comparableCurrent = (latest.value / elapsedDays) * daysInMonth;
      projected = true;
    }
  }

  return {
    value: ((comparableCurrent - previous) / previous) * 100,
    projected
  };
}

function formatPercent(value) {
  if (value === null || !Number.isFinite(value)) return "—";
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${Math.round(value)}%`;
}

function exhaustionDate(referenceDate, coverageDays) {
  if (!Number.isFinite(coverageDays) || coverageDays < 0) return "";
  const date = safeDate(referenceDate);
  if (!date) return "";
  date.setDate(date.getDate() + Math.round(coverageDays));
  return date.toLocaleDateString("pt-BR", {
    day: "2-digit",
    month: "long",
    year: "numeric"
  });
}

export function calculateBagMetrics({ rows, stock, referenceDate }) {
  const total = sumQuantities(rows);
  const bounds = dateBounds(rows);
  const days = Math.max(1, daysBetween(bounds.start, bounds.end));
  const averageDaily = total / days;
  const coverageDays = averageDaily > 0 ? stock / averageDaily : Infinity;
  const ideal90Days = averageDaily * REORDER_POINT_DAYS;
  const deficit90Days = Math.max(0, ideal90Days - stock);
  const buyInDays = Number.isFinite(coverageDays)
    ? Math.max(0, Math.floor(coverageDays - REORDER_POINT_DAYS))
    : null;
  const series = monthlySeries(rows);
  const trendResult = trendPercent(series, bounds.end || referenceDate);
  const latestMonth = series.at(-1) || null;

  let status = "safe";
  let statusTitle = "Situação segura";
  let statusDetail = `Cobertura acima de ${ATTENTION_START_DAYS} dias, distante do ponto de reposição.`;

  if (!rows.length || averageDaily <= 0) {
    status = "neutral";
    statusTitle = "Sem consumo suficiente";
    statusDetail = "Não há dados suficientes no filtro para projetar a reposição.";
  } else if (coverageDays <= 30) {
    status = "critical";
    statusTitle = "Compra crítica";
    statusDetail = `O ponto de reposição de ${REORDER_POINT_DAYS} dias já foi ultrapassado e a cobertura está em 30 dias ou menos.`;
  } else if (coverageDays <= REORDER_POINT_DAYS) {
    status = "danger";
    statusTitle = "Providenciar compra agora";
    statusDetail = `O estoque atingiu ou ultrapassou o ponto de reposição de ${REORDER_POINT_DAYS} dias.`;
  } else if (coverageDays <= ATTENTION_START_DAYS) {
    status = "warning";
    statusTitle = "Atenção ao ponto de reposição";
    statusDetail = `Faltam aproximadamente ${buyInDays} dias para atingir o ponto de reposição de ${REORDER_POINT_DAYS} dias.`;
  }

  return {
    total,
    days,
    averageDaily,
    coverageDays,
    ideal90Days,
    deficit90Days,
    buyInDays,
    series,
    trend: trendResult.value,
    trendProjected: trendResult.projected,
    latestMonth,
    exhaustion: exhaustionDate(referenceDate, coverageDays),
    status,
    statusTitle,
    statusDetail
  };
}

function renderSelectOptions(values, selected, allLabel) {
  const unique = Array.from(new Set(values.filter(Boolean))).sort((a, b) =>
    String(a).localeCompare(String(b), "pt-BR")
  );
  return [
    `<option value="todos">${escapeHtml(allLabel)}</option>`,
    ...unique.map(
      (value) =>
        `<option value="${escapeHtml(value)}"${value === selected ? " selected" : ""}>${escapeHtml(value)}</option>`
    )
  ].join("");
}

function renderBarsList(groups, action = "", maxItems = 10) {
  const items = groups.slice(0, maxItems);
  const maximum = Math.max(1, ...items.map((item) => item.q));
  if (!items.length) {
    return '<div class="bags-empty">Nenhum dado disponível para o filtro.</div>';
  }

  return `<div class="bags-ranking">${items
    .map((item, index) => {
      const attributes = action
        ? ` role="button" tabindex="0" data-action="${action}" data-value="${encodeURIComponent(item.k)}"`
        : "";
      return `<div class="bags-rank-row"${attributes}>
        <span class="bags-rank-number">${index + 1}</span>
        <span class="bags-rank-name" title="${escapeHtml(item.k)}">${escapeHtml(item.k)}</span>
        <span class="bags-rank-track"><i style="width:${clamp((item.q / maximum) * 100, 2, 100)}%"></i></span>
        <b>${formatNumber(item.q)}</b>
      </div>`;
    })
    .join("")}</div>`;
}

function renderDonut(groups, title) {
  const normalized = groups.filter((item) => item.q > 0);
  const top = normalized.slice(0, 5);
  const remaining = normalized.slice(5).reduce((total, item) => total + item.q, 0);
  if (remaining > 0) top.push({ k: "Outros", q: remaining });
  const total = top.reduce((sum, item) => sum + item.q, 0);

  if (!total) {
    return `<div class="bags-empty">${escapeHtml(title)} indisponível para o filtro.</div>`;
  }

  let cursor = 0;
  const segments = top.map((item, index) => {
    const start = cursor;
    cursor += (item.q / total) * 100;
    return `${CHART_COLORS[index % CHART_COLORS.length]} ${start}% ${cursor}%`;
  });

  return `<div class="bags-donut-layout">
    <div class="bags-donut" style="background:conic-gradient(${segments.join(",")})">
      <div><b>${formatNumber(total)}</b><span>sacolas</span></div>
    </div>
    <div class="bags-donut-legend">
      ${top
        .map(
          (item, index) => `<div>
            <i style="background:${CHART_COLORS[index % CHART_COLORS.length]}"></i>
            <span>${escapeHtml(item.k)}</span>
            <b>${Math.round((item.q / total) * 100)}%</b>
          </div>`
        )
        .join("")}
    </div>
  </div>`;
}

function renderConsumptionChart(series) {
  if (!series.length) {
    return '<div class="bags-empty">Não existem meses com consumo no filtro selecionado.</div>';
  }

  const actualValues = series.map((item) => item.value);
  const trendValues = linearRegression(actualValues);
  const recentAverage = average(actualValues.slice(-3));
  const lastKey = series.at(-1).key;
  const projected = [1, 2, 3].map((offset) => ({
    key: nextMonthKey(lastKey, offset),
    value: Math.max(0, recentAverage),
    projected: true
  }));
  const all = [...series, ...projected];
  const valuesForScale = [
    ...actualValues,
    ...trendValues,
    ...projected.map((item) => item.value),
    1
  ];
  const maximum = Math.max(...valuesForScale) * 1.18;
  const width = 980;
  const height = 330;
  const left = 62;
  const right = 24;
  const top = 26;
  const bottom = 58;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const x = (index) =>
    left + (all.length === 1 ? plotWidth / 2 : (index / (all.length - 1)) * plotWidth);
  const y = (value) => top + plotHeight - (value / maximum) * plotHeight;
  const actualPoints = series
    .map((item, index) => `${x(index)},${y(item.value)}`)
    .join(" ");
  const trendPoints = trendValues
    .map((value, index) => `${x(index)},${y(value)}`)
    .join(" ");
  const projectionStart = series.length - 1;
  const projectionPoints = [
    `${x(projectionStart)},${y(series.at(-1).value)}`,
    ...projected.map((item, index) => `${x(series.length + index)},${y(item.value)}`)
  ].join(" ");
  const areaPoints = `${x(0)},${top + plotHeight} ${actualPoints} ${x(series.length - 1)},${top + plotHeight}`;
  const projectionX = x(projectionStart) + 8;
  const gridValues = [0, 0.25, 0.5, 0.75, 1].map((ratio) => maximum * ratio);

  return `<div class="bags-line-chart">
    <div class="bags-chart-legend">
      <span><i class="real"></i>Consumo real</span>
      <span><i class="trend"></i>Tendência</span>
      <span><i class="projection"></i>Projeção por média móvel</span>
    </div>
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Consumo mensal de sacolas e projeção">
      <rect x="${projectionX}" y="${top}" width="${Math.max(0, width - right - projectionX)}" height="${plotHeight}" fill="#f3f8ff" rx="12"></rect>
      ${gridValues
        .map((value) => {
          const lineY = y(value);
          return `<line x1="${left}" y1="${lineY}" x2="${width - right}" y2="${lineY}" stroke="#dfe8f2"></line>
          <text x="${left - 10}" y="${lineY + 4}" text-anchor="end">${formatNumber(value)}</text>`;
        })
        .join("")}
      <polygon points="${areaPoints}" fill="rgba(20,115,230,.10)"></polygon>
      <polyline points="${actualPoints}" fill="none" stroke="#1473e6" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"></polyline>
      <polyline points="${trendPoints}" fill="none" stroke="#1473e6" stroke-width="2.5" stroke-dasharray="9 7"></polyline>
      <polyline points="${projectionPoints}" fill="none" stroke="#60a5fa" stroke-width="4" stroke-dasharray="5 7"></polyline>
      <line x1="${projectionX}" y1="${top}" x2="${projectionX}" y2="${top + plotHeight}" stroke="#9db4cb" stroke-dasharray="6 6"></line>
      <text x="${projectionX + 12}" y="${top + 18}" class="projection-label">Projeção</text>
      ${series
        .map(
          (item, index) =>
            `<circle cx="${x(index)}" cy="${y(item.value)}" r="5" fill="#1473e6"><title>${monthLabel(item.key)}: ${formatNumber(item.value)} sacolas</title></circle>`
        )
        .join("")}
      ${all
        .map((item, index) => {
          const show = all.length <= 10 || index % 2 === 0 || index === all.length - 1;
          return show
            ? `<text x="${x(index)}" y="${height - 24}" text-anchor="middle">${monthLabel(item.key)}</text>`
            : "";
        })
        .join("")}
    </svg>
  </div>`;
}

function renderHeatmap(rows) {
  const hoursPresent = rows.some((row) => rowHour(row) !== null);
  if (!hoursPresent) {
    const weekdays = groupByWeekday(rows);
    const maximum = Math.max(1, ...weekdays.map((item) => item.q));
    return `<div class="bags-weekday-map">
      ${weekdays
        .map(
          (item) => `<div style="--intensity:${clamp(item.q / maximum, 0.08, 1)}">
            <span>${escapeHtml(item.k.slice(0, 3))}</span>
            <b>${formatNumber(item.q)}</b>
          </div>`
        )
        .join("")}
      <p>O banco não trouxe horário confiável. O mapa mostra somente os dias da semana.</p>
    </div>`;
  }

  const matrix = HOUR_BANDS.map(() => DAY_NAMES.map(() => 0));
  rows.forEach((row) => {
    const day = DAY_NAMES.indexOf(row.DiaSemana);
    const band = hourBandIndex(rowHour(row));
    if (day >= 0 && band >= 0) matrix[band][day] += toNumber(row.Qtde_num);
  });
  const maximum = Math.max(1, ...matrix.flat());

  return `<div class="bags-heatmap">
    <div></div>${DAY_NAMES.map((day) => `<b>${day.slice(0, 3)}</b>`).join("")}
    ${matrix
      .map(
        (row, bandIndex) =>
          `<span>${HOUR_BANDS[bandIndex].label}</span>${row
            .map(
              (value) =>
                `<i style="--intensity:${clamp(value / maximum, 0.05, 1)}" title="${formatNumber(value)} sacolas"><em>${value ? formatNumber(value) : ""}</em></i>`
            )
            .join("")}`
      )
      .join("")}
  </div>`;
}

function eventDates(event, year) {
  const start = `${year}-${event.inicio}`;
  const end = `${year}-${event.fim}`;
  return {
    start,
    end,
    weekStart: addDays(end, 1),
    weekEnd: addDays(end, 7)
  };
}

/**
 * Dashboard inteligente de sacolas.
 *
 * O módulo usa somente regras matemáticas auditáveis. Nenhum insight depende
 * de IA externa, de tokens ou de envio de dados para terceiros.
 */
export function createBagsModule({
  selectors,
  components,
  modal,
  documentRef = document
}) {
  const { renderTable } = components;
  const { operatingYear, seasonalHistoryYear, referenceDate, bagsPerPackage } =
    selectors.metadata;
  const allRows = selectors.seasonalByCategory("Sacolas");
  const stockRows = selectors.stockByCategory("Sacolas");
  const years = Array.from(new Set(allRows.map(recordYear).filter(Boolean))).sort();
  const availableSectors = allRows.map(rowSector).filter(Boolean);
  const hasSectorData = availableSectors.length > 0;

  const VIEW_META = Object.freeze({
    overview: {
      icon: "⌂",
      label: "Visão geral",
      title: "Centro de decisão",
      description:
        "Somente os indicadores essenciais para decidir compra, acompanhar consumo e evitar ruptura."
    },
    stock: {
      icon: "▣",
      label: "Estoque",
      title: "Estoque e reposição",
      description:
        "Cobertura, estoque mínimo, prazo de compra e simulação de novas entradas."
    },
    seasonality: {
      icon: "◫",
      label: "Sazonalidade",
      title: "Sazonalidade e eventos",
      description: "Meses, dias da semana e impacto dos eventos municipais no consumo."
    },
    collaborators: {
      icon: "♙",
      label: "Colaboradores",
      title: "Colaboradores e histórico",
      description:
        "Ranking, participação, frequência e detalhamento das retiradas por pessoa."
    },
    comparisons: {
      icon: "↗",
      label: "Comparações",
      title: "Comparação entre períodos",
      description:
        "Mês contra mês, ritmo projetado e evolução histórica sem comparar períodos incompletos de forma incorreta."
    },
    reports: {
      icon: "▤",
      label: "Relatórios",
      title: "Relatórios e dados",
      description:
        "Downloads, filtros completos e histórico detalhado das retiradas de sacolas."
    }
  });

  const state = {
    view: "overview",
    year: String(operatingYear),
    start: "",
    end: "",
    person: "todos",
    product: "todos",
    sector: "todos",
    simulatedPackages: 0
  };

  function baseRowsForYear() {
    if (state.year === "geral") return allRows;
    return allRows.filter((row) => recordYear(row) === Number(state.year));
  }

  function resetPeriod() {
    const bounds = dateBounds(baseRowsForYear());
    state.start = bounds.start;
    state.end = bounds.end;
  }

  resetPeriod();

  function filteredRows({ ignoreDates = false } = {}) {
    return baseRowsForYear().filter((row) => {
      const date = isoDate(row);
      if (!ignoreDates && state.start && date && date < state.start) return false;
      if (!ignoreDates && state.end && date && date > state.end) return false;
      if (state.person !== "todos" && row.Requisitante !== state.person) return false;
      if (state.product !== "todos" && row["Nome do Produto"] !== state.product)
        return false;
      if (state.sector !== "todos" && rowSector(row) !== state.sector) return false;
      return true;
    });
  }

  function stockForCurrentFilter() {
    if (state.product === "todos") {
      return stockRows.reduce((total, row) => total + toNumber(row.QtdeEstoque), 0);
    }

    return stockRows
      .filter((row) => {
        const mainName = String(row["Nome do Produto"] || "").trim();
        const origins = Array.isArray(row.ProdutosOrigem) ? row.ProdutosOrigem : [];
        return mainName === state.product || origins.includes(state.product);
      })
      .reduce((total, row) => total + toNumber(row.QtdeEstoque), 0);
  }

  function packages(value) {
    return bagsPerPackage ? toNumber(value) / bagsPerPackage : 0;
  }

  function roundedToPackages(value) {
    if (!bagsPerPackage) return Math.ceil(value);
    return Math.ceil(value / bagsPerPackage) * bagsPerPackage;
  }

  function statusIcon(status) {
    return {
      critical: "!",
      danger: "!",
      warning: "⏳",
      safe: "✓",
      neutral: "i"
    }[status];
  }

  function buildInsights(rows, metrics, people, sectors, products, weekdays) {
    const insights = [];
    const total = Math.max(1, metrics.total);
    const topPerson = people[0];
    const topSector = sectors[0];
    const topProduct = products[0];
    const topDay = [...weekdays].sort((a, b) => b.q - a.q)[0];

    if (metrics.trend !== null) {
      const direction = metrics.trend >= 0 ? "aumentou" : "caiu";
      insights.push({
        icon: "↗",
        tone: metrics.trend > 10 ? "warning" : "info",
        text: `O consumo mensal ${direction} ${Math.abs(Math.round(metrics.trend))}% em relação ao mês anterior.`
      });
    }

    if (hasSectorData && topSector) {
      insights.push({
        icon: "◔",
        tone: "success",
        text: `O setor ${topSector.k} concentra ${Math.round((topSector.q / total) * 100)}% das retiradas filtradas.`
      });
    } else if (topProduct) {
      insights.push({
        icon: "▣",
        tone: "success",
        text: `${topProduct.k} representa ${Math.round((topProduct.q / total) * 100)}% do consumo no período.`
      });
    }

    if (topPerson) {
      insights.push({
        icon: "♙",
        tone: "info",
        text: `${topPerson.k} lidera o consumo com ${formatNumber(topPerson.q)} sacolas.`
      });
    }

    if (topDay?.q) {
      insights.push({
        icon: "◫",
        tone: "info",
        text: `${topDay.k} é o dia de maior saída, com ${formatNumber(topDay.q)} sacolas.`
      });
    }

    if (Number.isFinite(metrics.coverageDays)) {
      const coverageTone =
        metrics.coverageDays <= REORDER_POINT_DAYS
          ? "danger"
          : metrics.coverageDays <= ATTENTION_START_DAYS
            ? "warning"
            : "success";
      insights.push({
        icon: metrics.coverageDays <= REORDER_POINT_DAYS ? "!" : "▣",
        tone: coverageTone,
        text: metrics.exhaustion
          ? `A cobertura estimada é de ${Math.round(metrics.coverageDays)} dias. O ponto de reposição é ${REORDER_POINT_DAYS} dias e o possível esgotamento é ${metrics.exhaustion}.`
          : `A cobertura estimada é de ${Math.round(metrics.coverageDays)} dias, considerando ponto de reposição em ${REORDER_POINT_DAYS} dias.`
      });
    }

    return insights.slice(0, 5);
  }

  function renderRail() {
    const buttons = Object.entries(VIEW_META)
      .map(
        ([
          key,
          item
        ]) => `<button type="button" class="bags-nav-button${state.view === key ? " active" : ""}" data-bags-view="${key}" aria-label="${escapeHtml(item.label)}" title="${escapeHtml(item.label)}">
        <span class="bags-nav-icon">${item.icon}</span><span class="bags-nav-label">${escapeHtml(item.label)}</span>
      </button>`
      )
      .join("");

    return `<aside class="bags-side-nav" aria-label="Navegação do dashboard de sacolas">
      <div class="bags-nav-brand"><span>🛍️</span><b>Sacolas</b></div>
      <nav>${buttons}</nav>
      <button type="button" class="bags-nav-button back" data-action="navigate-home" aria-label="Voltar às categorias" title="Voltar às categorias"><span class="bags-nav-icon">←</span><span class="bags-nav-label">Categorias</span></button>
    </aside>`;
  }

  function renderViewHeader() {
    const meta = VIEW_META[state.view];
    return `<header class="bags-view-header">
      <div><span class="bags-eyebrow">Decisão automática · Sacolas</span><h2>${escapeHtml(meta.title)}</h2><p>${escapeHtml(meta.description)}</p></div>
      <span class="bags-mode-badge">Regras auditáveis</span>
    </header>`;
  }

  function renderYearButtons() {
    return [...years.map(String), "geral"]
      .map(
        (year) =>
          `<button type="button" class="bags-year-button${state.year === year ? " active" : ""}" data-bags-year="${year}">${year === "geral" ? "Geral" : year}</button>`
      )
      .join("");
  }

  function renderFilters(
    rows,
    {
      showPerson = false,
      showSector = false,
      showDownload = false,
      compact = false
    } = {}
  ) {
    const sectorOptions = hasSectorData
      ? renderSelectOptions(allRows.map(rowSector), state.sector, "Todos")
      : '<option value="todos">Sem cadastro de setor</option>';

    return `<div class="bags-filterbar${compact ? " compact" : ""}">
      <label class="bags-date-filter"><span>Período</span><div><input id="bagsStart" type="date" value="${state.start}"><b>até</b><input id="bagsEnd" type="date" value="${state.end}"></div></label>
      <div class="bags-year-switch" aria-label="Ano do relatório">${renderYearButtons()}</div>
      ${showSector ? `<label><span>Setor</span><select id="bagsSector"${hasSectorData ? "" : " disabled"}>${sectorOptions}</select></label>` : ""}
      ${
        showPerson
          ? `<label><span>Colaborador</span><select id="bagsPerson">${renderSelectOptions(
              rows.map((row) => row.Requisitante || "Não informado"),
              state.person,
              "Todos"
            )}</select></label>`
          : ""
      }
      <label><span>Tipo de sacola</span><select id="bagsProduct">${renderSelectOptions(
        rows.map((row) => row["Nome do Produto"] || "Não informado"),
        state.product,
        "Todos"
      )}</select></label>
      ${showDownload ? '<button class="btn green bags-download" type="button" data-action="download-report">📥 Planilha completa</button>' : ""}
    </div>`;
  }

  function renderExecutiveKpis(metrics) {
    const latestMonthLabel = metrics.latestMonth
      ? monthLabel(metrics.latestMonth.key)
      : "Sem mês";
    const coverage = Number.isFinite(metrics.coverageDays)
      ? `${formatNumber(metrics.coverageDays)} dias`
      : "—";
    const exhaustion = metrics.exhaustion || "Sem previsão";

    return `<div class="bags-executive-kpis">
      <article class="bags-kpi-card consumption"><i>◫</i><div><span>Consumo no mês</span><b>${formatNumber(metrics.latestMonth?.value || 0)}</b><small>${latestMonthLabel}</small></div></article>
      <article class="bags-kpi-card coverage"><i>⌛</i><div><span>Cobertura</span><b>${coverage}</b><small>ritmo atual</small></div></article>
      <article class="bags-kpi-card exhaustion"><i>◷</i><div><span>Previsão de esgotamento</span><b>${escapeHtml(exhaustion)}</b><small>estimativa por média diária</small></div></article>
      <article class="bags-kpi-card trend"><i>↗</i><div><span>Tendência</span><b>${formatPercent(metrics.trend)}</b><small>${metrics.trendProjected ? "mensalizada vs. mês anterior" : "vs. mês anterior"}</small></div></article>
    </div>`;
  }

  function renderOverviewStockCard(metrics, currentStock) {
    const decision = decisionDetails(metrics);
    const coverage = Number.isFinite(metrics.coverageDays)
      ? `${formatNumber(metrics.coverageDays)} dias`
      : "Sem projeção";
    const stockPackages = packages(currentStock);

    return `<article class="bags-overview-stock-card ${decision.tone}">
      <div class="bags-overview-stock-head">
        <div><span class="bags-eyebrow">Estoque atual</span><h3>Disponibilidade imediata</h3></div>
        <span class="bags-stock-status">${escapeHtml(decision.badge)}</span>
      </div>
      <div class="bags-overview-stock-value"><i>▣</i><div><b>${formatNumber(currentStock)}</b><span>sacolas</span><small>${formatNumber(stockPackages)} pacotes</small></div></div>
      <div class="bags-overview-stock-metrics">
        <div><span>Cobertura estimada</span><b>${escapeHtml(coverage)}</b></div>
        <div><span>Possível esgotamento</span><b>${escapeHtml(metrics.exhaustion || "—")}</b></div>
      </div>
      <button type="button" class="bags-text-link" data-bags-view="stock">Abrir estoque e reposição →</button>
    </article>`;
  }

  function renderOverviewInsights(insights) {
    const items = insights.slice(0, 4);
    return `<article class="bags-overview-insights-card">
      <div class="bags-overview-card-title"><div><span class="bags-eyebrow">Leitura automática</span><h3>Insights importantes</h3></div><span class="bags-insights-count">${items.length}</span></div>
      <div class="bags-overview-insight-list">
        ${items.map((insight) => `<div class="${insight.tone}"><i>${insight.icon}</i><p>${escapeHtml(insight.text)}</p></div>`).join("") || '<div class="info"><i>i</i><p>Não há dados suficientes para gerar insights confiáveis.</p></div>'}
      </div>
    </article>`;
  }

  function renderOverviewDecision(metrics) {
    const decision = decisionDetails(metrics);
    return `<article class="bags-overview-decision ${decision.tone}">
      <div><span class="bags-decision-icon">${statusIcon(metrics.status)}</span><span class="bags-decision-badge">${escapeHtml(decision.badge)}</span></div>
      <h3>${escapeHtml(decision.title)}</h3>
      <p>${escapeHtml(decision.text)}</p>
    </article>`;
  }

  function decisionDetails(metrics) {
    if (!metrics.total || !Number.isFinite(metrics.coverageDays)) {
      return {
        tone: "neutral",
        title: "Acompanhar dados",
        badge: "Sem base suficiente",
        text: "Ainda não há consumo suficiente para estimar uma decisão de compra confiável."
      };
    }

    const coverage = Math.round(metrics.coverageDays);
    const daysToReorder = Math.max(
      0,
      Math.floor(metrics.coverageDays - REORDER_POINT_DAYS)
    );
    const daysPastReorder = Math.max(
      0,
      Math.ceil(REORDER_POINT_DAYS - metrics.coverageDays)
    );

    if (metrics.coverageDays <= 30) {
      return {
        tone: "danger",
        title: "Compra em situação crítica",
        badge: "Compra necessária",
        text: `A cobertura está em ${coverage} dias. O ponto de reposição de ${REORDER_POINT_DAYS} dias foi ultrapassado em aproximadamente ${daysPastReorder} dias. A compra deve ser tratada como prioridade.`
      };
    }

    if (metrics.coverageDays <= REORDER_POINT_DAYS) {
      return {
        tone: "danger",
        title: "Providenciar compra agora",
        badge: "Compra necessária",
        text: `A cobertura está em ${coverage} dias. O estoque atingiu ou já passou do ponto de reposição de ${REORDER_POINT_DAYS} dias, criado para dar tempo ao processo de compra e entrega.`
      };
    }

    if (metrics.coverageDays <= ATTENTION_START_DAYS) {
      return {
        tone: "warning",
        title: "Acompanhar e preparar a compra",
        badge: "Atenção",
        text: `A cobertura está em ${coverage} dias. Faltam aproximadamente ${daysToReorder} dias para atingir o ponto de reposição de ${REORDER_POINT_DAYS} dias.`
      };
    }

    return {
      tone: "safe",
      title: "Estoque sob controle",
      badge: "Situação segura",
      text: `A cobertura está em ${coverage} dias, acima da faixa de atenção. O ponto de reposição continua definido em ${REORDER_POINT_DAYS} dias.`
    };
  }

  function renderCompactInsights(insights) {
    return `<div class="bags-executive-insights">${
      insights
        .slice(0, 3)
        .map(
          (insight) =>
            `<article class="${insight.tone}"><i>${insight.icon}</i><p>${escapeHtml(insight.text)}</p></article>`
        )
        .join("") ||
      '<article class="info"><i>i</i><p>Não há dados suficientes para gerar alertas executivos.</p></article>'
    }</div>`;
  }

  function renderStockPanel(metrics, currentStock) {
    const ideal = metrics.ideal90Days;
    const deficit = roundedToPackages(metrics.deficit90Days);
    const progress = ideal > 0 ? clamp((currentStock / ideal) * 100, 0, 100) : 0;
    const gaugeColor =
      metrics.status === "safe"
        ? "#16a34a"
        : metrics.status === "warning"
          ? "#f59e0b"
          : "#ef4444";

    const stockBandLabel =
      metrics.coverageDays <= REORDER_POINT_DAYS
        ? "Compra necessária"
        : metrics.coverageDays <= ATTENTION_START_DAYS
          ? "Atenção"
          : "Faixa segura";

    return `<article class="bags-stock-panel">
      <h3>Estoque × ponto de reposição</h3>
      <div class="bags-stock-content">
        <div class="bags-gauge" style="--gauge:${progress}%;--gauge-color:${gaugeColor}"><div><b>${formatNumber(currentStock)}</b><span>sacolas</span><small>${stockBandLabel}</small></div></div>
        <div class="bags-stock-numbers"><span>Estoque no ponto de reposição</span><b>${formatNumber(ideal)} sacolas</b><small>${formatNumber(packages(ideal))} pacotes</small><hr><span>Falta para retornar ao ponto de reposição</span><b class="${deficit > 0 ? "danger-text" : "success-text"}">${formatNumber(deficit)} sacolas</b><small>${formatNumber(packages(deficit))} pacotes fechados</small></div>
      </div>
      <p class="bags-formula">Fórmula: média diária do filtro × ${REORDER_POINT_DAYS} dias − estoque atual. Esse valor indica o ponto de reposição, não o estoque final desejado após a compra. O valor é arredondado para pacote fechado de ${bagsPerPackage} sacolas.</p>
    </article>`;
  }

  function renderRecommendation(metrics, isDrilldown) {
    if (!metrics.total || !Number.isFinite(metrics.coverageDays)) {
      return '<article class="bags-recommendation neutral"><i>i</i><div><h3>Sem recomendação automática</h3><p>O filtro não possui consumo suficiente para calcular o ponto de reposição.</p></div></article>';
    }

    const decision = decisionDetails(metrics);
    const deficit = roundedToPackages(metrics.deficit90Days);
    const drilldownNote = isDrilldown
      ? " Este cenário usa apenas a demanda do filtro atual; volte para Todos antes da decisão geral."
      : "";

    if (decision.tone === "danger") {
      const deficitText =
        deficit > 0
          ? ` Para retornar ao ponto de reposição de ${REORDER_POINT_DAYS} dias, faltam ao menos <b>${formatNumber(deficit)} sacolas</b> (${formatNumber(packages(deficit))} pacotes).`
          : "";
      return `<article class="bags-recommendation danger"><i>🛒</i><div><h3>${escapeHtml(decision.title)}</h3><p>${escapeHtml(decision.text)}${deficitText}${escapeHtml(drilldownNote)}</p></div></article>`;
    }

    if (decision.tone === "warning") {
      return `<article class="bags-recommendation warning"><i>!</i><div><h3>${escapeHtml(decision.title)}</h3><p>${escapeHtml(decision.text)}${escapeHtml(drilldownNote)}</p></div></article>`;
    }

    return `<article class="bags-recommendation safe"><i>✓</i><div><h3>${escapeHtml(decision.title)}</h3><p>${escapeHtml(decision.text)}${escapeHtml(drilldownNote)}</p></div></article>`;
  }

  function renderEventCards() {
    const selectedYear = state.year === "geral" ? operatingYear : Number(state.year);
    return EVENTS.map((event) => {
      const dates = eventDates(event, selectedYear);
      const future = dates.weekEnd > referenceDate;
      return `<button type="button" class="season-card ${event.forca === "alta" ? "high" : "medium"}" data-action="bags-event" data-event-id="${escapeHtml(event.id)}"><span>${formatBrazilianDate(dates.start)}${dates.start !== dates.end ? ` a ${formatBrazilianDate(dates.end)}` : ""}</span><b>${escapeHtml(event.nome)}</b><small>${escapeHtml(event.desc)}</small><em class="tag ${future ? "future" : "done"}">${future ? "Previsto" : "Realizado"}</em></button>`;
    }).join("");
  }

  function comparisonSnapshot(rows) {
    const bounds = dateBounds(rows);
    const reference = safeDate(state.end || bounds.end || referenceDate);
    if (!reference) return null;
    const currentKey = `${reference.getFullYear()}-${String(reference.getMonth() + 1).padStart(2, "0")}`;
    const previousDate = new Date(reference.getFullYear(), reference.getMonth() - 1, 1);
    const previousKey = `${previousDate.getFullYear()}-${String(previousDate.getMonth() + 1).padStart(2, "0")}`;
    const elapsed = reference.getDate();
    const daysCurrent = new Date(
      reference.getFullYear(),
      reference.getMonth() + 1,
      0
    ).getDate();
    const daysPrevious = new Date(
      previousDate.getFullYear(),
      previousDate.getMonth() + 1,
      0
    ).getDate();
    const compareDay = Math.min(elapsed, daysPrevious);
    const current = rows.filter(
      (row) =>
        isoDate(row).startsWith(currentKey) &&
        Number(isoDate(row).slice(8, 10)) <= elapsed
    );
    const previousComparable = rows.filter(
      (row) =>
        isoDate(row).startsWith(previousKey) &&
        Number(isoDate(row).slice(8, 10)) <= compareDay
    );
    const previousFull = rows.filter((row) => isoDate(row).startsWith(previousKey));
    const currentTotal = sumQuantities(current);
    const previousComparableTotal = sumQuantities(previousComparable);
    const previousFullTotal = sumQuantities(previousFull);
    const projected = elapsed ? (currentTotal / elapsed) * daysCurrent : currentTotal;
    const variation = previousComparableTotal
      ? ((currentTotal - previousComparableTotal) / previousComparableTotal) * 100
      : null;
    return {
      currentKey,
      previousKey,
      elapsed,
      currentTotal,
      previousComparableTotal,
      previousFullTotal,
      projected,
      variation
    };
  }

  function renderComparisonBars(series) {
    const values = series.slice(-8);
    if (!values.length)
      return '<div class="bags-empty">Sem meses disponíveis para comparação.</div>';
    const maximum = Math.max(...values.map((item) => item.value), 1);
    return `<div class="bags-month-bars">${values.map((item) => `<div><span>${escapeHtml(monthLabel(item.key))}</span><i><b style="width:${clamp((item.value / maximum) * 100, 2, 100)}%"></b></i><strong>${formatNumber(item.value)}</strong></div>`).join("")}</div>`;
  }

  function renderSimulator(metrics, currentStock) {
    const added = Math.max(0, state.simulatedPackages) * bagsPerPackage;
    const simulatedStock = currentStock + added;
    const coverage =
      metrics.averageDaily > 0 ? simulatedStock / metrics.averageDaily : null;
    return `<article class="bags-simulator"><div><span class="bags-eyebrow">Simulador</span><h3>Simular nova entrada</h3><p>Informe quantos pacotes pretende receber. O cálculo não altera o estoque real.</p></div><label><span>Pacotes adicionados</span><input id="bagsSimulatedPackages" type="number" min="0" step="1" value="${state.simulatedPackages}"></label><div class="bags-simulator-result"><span>Novo estoque</span><b>${formatNumber(simulatedStock)} sacolas</b><small>${formatNumber(packages(simulatedStock))} pacotes</small></div><div class="bags-simulator-result"><span>Nova cobertura</span><b>${coverage === null ? "—" : `${formatNumber(coverage)} dias`}</b><small>com o ritmo atual</small></div></article>`;
  }

  function renderOverview(context) {
    const { rows, metrics, currentStock, insights, sourceCount } = context;
    const period = dateBounds(rows);
    const updatedAt = period.end || state.end || referenceDate;
    return `<div class="bags-overview-period"><span>Dados operacionais de ${operatingYear}</span><b>Atualizado até ${formatBrazilianDate(updatedAt)}</b></div>
      ${renderExecutiveKpis(metrics)}
      <div class="bags-overview-grid">
        <article class="bags-chart-panel"><div class="bags-panel-heading"><div><h3>Consumo e projeção</h3><p>Leitura principal para acompanhar ritmo e mudança de demanda.</p></div><span>${formatNumber(metrics.total)} sacolas · ${formatNumber(sourceCount)} retiradas</span></div>${renderConsumptionChart(metrics.series)}</article>
        <aside class="bags-overview-sidebar">${renderOverviewStockCard(metrics, currentStock)}${renderOverviewInsights(insights)}${renderOverviewDecision(metrics)}</aside>
      </div>`;
  }

  function renderStockView(context) {
    const { baseRows, metrics, currentStock, isDrilldown } = context;
    return `${renderFilters(baseRows, { compact: true })}<div class="bags-stock-view-grid">${renderStockPanel(metrics, currentStock)}<div class="bags-stock-side">${renderRecommendation(metrics, isDrilldown)}${renderSimulator(metrics, currentStock)}</div></div>`;
  }

  function renderSeasonalityView(context) {
    const { baseRows, rows, metrics, insights } = context;
    return `${renderFilters(baseRows, { compact: true })}<div class="bags-section-grid two-col"><article class="bags-chart-panel"><div class="bags-panel-heading"><div><h3>Evolução mensal</h3><p>Histórico real e projeção para localizar picos e padrões recorrentes.</p></div></div>${renderConsumptionChart(metrics.series)}</article><article class="bags-analysis-card"><h3>Dias de maior saída</h3>${renderHeatmap(rows)}</article></div><article class="panel bags-season-panel"><h2>Calendário sazonal municipal</h2><p class="muted">Clique em um evento para comparar a semana seguinte em ${seasonalHistoryYear} e ${operatingYear}.</p><div class="season-grid">${renderEventCards()}<div class="season-card leaves"><span>mar.–jun.</span><b>Outono / folhas</b><small>Período de atenção para limpeza urbana e folhas.</small><em class="tag">Alerta complementar</em></div></div></article>${renderCompactInsights(insights.filter((item) => item.icon !== "♙"))}`;
  }

  function renderCollaboratorsView(context) {
    const { baseRows, rows, people, participation, participationTitle, sourceCount } =
      context;
    return `${renderFilters(baseRows, { showPerson: true, showSector: true })}<div class="bags-collaborator-summary"><article><span>Pessoas no período</span><b>${formatNumber(people.length)}</b></article><article><span>Retiradas</span><b>${formatNumber(sourceCount)}</b></article><article><span>Sacolas retiradas</span><b>${formatNumber(sumQuantities(rows))}</b></article><article><span>Média por pessoa</span><b>${people.length ? formatNumber(sumQuantities(rows) / people.length) : "0"}</b></article></div><div class="bags-section-grid two-col"><article class="bags-analysis-card"><div class="bags-panel-heading"><div><h3>Ranking de colaboradores</h3><p>Clique em uma pessoa para abrir o histórico detalhado.</p></div></div>${renderBarsList(people, "bags-person", 20)}</article><article class="bags-analysis-card"><h3>${participationTitle}</h3>${renderDonut(participation, participationTitle)}</article></div><details class="bags-history"><summary>Ver retiradas do filtro atual (${formatNumber(rows.length)} registros)</summary><div class="panel">${renderTable(rows)}</div></details>`;
  }

  function renderComparisonsView(context) {
    const { baseRows, metrics } = context;
    const comparisonRows = filteredRows({ ignoreDates: true });
    const snapshot = comparisonSnapshot(comparisonRows);
    const cards = snapshot
      ? `<div class="bags-comparison-kpis"><article><span>${escapeHtml(monthLabel(snapshot.currentKey))} até o dia ${snapshot.elapsed}</span><b>${formatNumber(snapshot.currentTotal)}</b><small>sacolas</small></article><article><span>${escapeHtml(monthLabel(snapshot.previousKey))} até o mesmo dia</span><b>${formatNumber(snapshot.previousComparableTotal)}</b><small>comparação justa</small></article><article><span>Variação comparável</span><b class="${(snapshot.variation || 0) > 0 ? "danger-text" : "success-text"}">${formatPercent(snapshot.variation)}</b><small>mesmo número de dias</small></article><article><span>Projeção do mês atual</span><b>${formatNumber(snapshot.projected)}</b><small>ritmo mensalizado</small></article></div>`
      : '<div class="bags-empty">Sem dados suficientes para comparar meses.</div>';
    return `${renderFilters(baseRows, { compact: true })}${cards}<div class="bags-section-grid two-col"><article class="bags-chart-panel"><div class="bags-panel-heading"><div><h3>Linha histórica</h3><p>Consumo mensal, tendência e projeção.</p></div></div>${renderConsumptionChart(metrics.series)}</article><article class="bags-analysis-card"><h3>Últimos meses</h3>${renderComparisonBars(metrics.series)}</article></div><div class="bags-comparison-note"><b>Regra de comparação:</b> o mês atual é comparado ao mesmo número de dias do mês anterior. A projeção mensal aparece separadamente para não misturar dado realizado com estimativa.</div>`;
  }

  function renderReportsView(context) {
    const { baseRows, rows, people, products, sourceCount } = context;
    return `${renderFilters(baseRows, { showPerson: true, showSector: true, showDownload: true })}<div class="bags-report-actions"><article><i>▤</i><div><h3>Planilha completa</h3><p>Arquivo XLSX gerado pelo atualizador com os dados do relatório.</p></div><button type="button" class="btn green" data-action="download-report">Baixar XLSX</button></article><article><i>⇩</i><div><h3>Sacolas filtradas</h3><p>Baixa somente as linhas exibidas nesta tela, em CSV.</p></div><button type="button" class="btn ghost" id="bagsDownloadCsv">Baixar CSV</button></article></div><div class="bags-collaborator-summary"><article><span>Registros filtrados</span><b>${formatNumber(rows.length)}</b></article><article><span>Retiradas únicas</span><b>${formatNumber(sourceCount)}</b></article><article><span>Colaboradores</span><b>${formatNumber(people.length)}</b></article><article><span>Tipos de sacola</span><b>${formatNumber(products.length)}</b></article></div><div class="bags-history open"><div class="panel">${renderTable(rows)}</div></div>`;
  }

  function renderDashboard() {
    const baseRows = baseRowsForYear();
    const rows = filteredRows();
    const currentStock = stockForCurrentFilter();
    const metrics = calculateBagMetrics({
      rows,
      stock: currentStock,
      referenceDate: state.end || referenceDate
    });
    const people = groupBy(rows, "Requisitante");
    const products = groupBy(rows, "Nome do Produto");
    const sectors = hasSectorData
      ? groupBy(
          rows.map((row) => ({ ...row, SetorCalculado: rowSector(row) })),
          "SetorCalculado"
        )
      : [];
    const weekdays = groupByWeekday(rows);
    const participation = hasSectorData ? sectors : products;
    const participationTitle = hasSectorData
      ? "Participação por setor"
      : "Participação por tipo";
    const insights = buildInsights(rows, metrics, people, sectors, products, weekdays);
    const sourceCount = countUnique(rows, "Nº Retirada");
    const isDrilldown =
      state.person !== "todos" || state.sector !== "todos" || state.product !== "todos";
    const context = {
      baseRows,
      rows,
      metrics,
      currentStock,
      people,
      products,
      sectors,
      weekdays,
      participation,
      participationTitle,
      insights,
      sourceCount,
      isDrilldown
    };

    const views = {
      overview: renderOverview,
      stock: renderStockView,
      seasonality: renderSeasonalityView,
      collaborators: renderCollaboratorsView,
      comparisons: renderComparisonsView,
      reports: renderReportsView
    };

    const content = documentRef.getElementById("sacolasContent");
    if (!content) return;
    content.innerHTML = `<div class="bags-dashboard bags-shell">${renderRail()}<main class="bags-workspace">${renderViewHeader()}<div class="bags-view-content">${views[state.view](context)}</div></main></div>`;
    bindControls();
  }

  function setYear(year) {
    state.year = year;
    state.person = "todos";
    state.product = "todos";
    state.sector = "todos";
    resetPeriod();
    renderDashboard();
  }

  function setView(view) {
    if (!VIEW_META[view]) return;
    state.view = view;
    if (view === "overview") {
      state.year = String(operatingYear);
      state.person = "todos";
      state.product = "todos";
      state.sector = "todos";
      resetPeriod();
    } else if (view === "stock" || view === "seasonality" || view === "comparisons") {
      state.person = "todos";
      state.sector = "todos";
    }
    renderDashboard();
  }

  function bindControls() {
    documentRef
      .querySelectorAll("[data-bags-view]")
      .forEach((button) =>
        button.addEventListener("click", () => setView(button.dataset.bagsView))
      );
    documentRef
      .querySelectorAll("[data-bags-year]")
      .forEach((button) =>
        button.addEventListener("click", () => setYear(button.dataset.bagsYear))
      );

    const start = documentRef.getElementById("bagsStart");
    const end = documentRef.getElementById("bagsEnd");
    const person = documentRef.getElementById("bagsPerson");
    const product = documentRef.getElementById("bagsProduct");
    const sector = documentRef.getElementById("bagsSector");
    const simulator = documentRef.getElementById("bagsSimulatedPackages");
    const csvButton = documentRef.getElementById("bagsDownloadCsv");

    start?.addEventListener("change", () => {
      state.start = start.value;
      if (state.end && state.start > state.end) state.end = state.start;
      renderDashboard();
    });
    end?.addEventListener("change", () => {
      state.end = end.value;
      if (state.start && state.end < state.start) state.start = state.end;
      renderDashboard();
    });
    person?.addEventListener("change", () => {
      state.person = person.value;
      renderDashboard();
    });
    product?.addEventListener("change", () => {
      state.product = product.value;
      renderDashboard();
    });
    sector?.addEventListener("change", () => {
      state.sector = sector.value;
      renderDashboard();
    });
    simulator?.addEventListener("input", () => {
      state.simulatedPackages = Math.max(0, toNumber(simulator.value));
      renderDashboard();
    });
    csvButton?.addEventListener("click", () => downloadFilteredCsv(filteredRows()));
  }

  function downloadFilteredCsv(rows) {
    const headers = [
      "Data",
      "Nº Retirada",
      "Requisitante",
      "Produto",
      "Quantidade",
      "Setor"
    ];
    const quote = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const lines = [headers.map(quote).join(";")];
    rows.forEach((row) =>
      lines.push(
        [
          row.Data_fmt || formatBrazilianDate(isoDate(row)),
          row["Nº Retirada"] || "",
          row.Requisitante || "",
          row["Nome do Produto"] || "",
          row.Qtde_num || 0,
          rowSector(row)
        ]
          .map(quote)
          .join(";")
      )
    );
    const blob = new Blob(["\ufeff", lines.join("\r\n")], {
      type: "text/csv;charset=utf-8"
    });
    const url = URL.createObjectURL(blob);
    const anchor = documentRef.createElement ? documentRef.createElement("a") : null;
    if (!anchor) return;
    anchor.href = url;
    anchor.download = `sacolas_${state.start || "inicio"}_${state.end || "fim"}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  function openPerson(encodedName) {
    const name = decodeURIComponent(encodedName);
    const rows = filteredRows().filter(
      (row) => (row.Requisitante || "Não informado") === name
    );
    modal.open(
      `Retiradas de ${name}`,
      `${formatNumber(sumQuantities(rows))} sacolas em ${rows.length} registros`,
      renderTable(rows)
    );
  }

  function eventRows(event, year) {
    const dates = eventDates(event, year);
    return allRows.filter(
      (row) =>
        recordYear(row) === year &&
        isoDate(row) >= dates.weekStart &&
        isoDate(row) <= dates.weekEnd
    );
  }

  function openEvent(id) {
    const event = EVENTS.find((item) => item.id === id);
    if (!event) return;
    const html = [seasonalHistoryYear, operatingYear]
      .map((year) => {
        const dates = eventDates(event, year);
        const rows = eventRows(event, year);
        const yearRows = allRows.filter((row) => recordYear(row) === year);
        const yearBounds = dateBounds(yearRows);
        const yearWeeks = Math.max(
          1,
          daysBetween(yearBounds.start, yearBounds.end) / 7
        );
        const weeklyAverage = sumQuantities(yearRows) / yearWeeks;
        const total = sumQuantities(rows);
        const ratio = weeklyAverage ? total / weeklyAverage : 0;
        const future = dates.weekEnd > referenceDate;
        if (future)
          return `<div class="panel"><h3>${escapeHtml(event.nome)} · ${year} · previsto</h3><p class="muted">Semana que será analisada: <b>${formatBrazilianDate(dates.weekStart)} a ${formatBrazilianDate(dates.weekEnd)}</b>.</p><div class="note">Margem sazonal cadastrada: <b>+${Math.round(event.margem * 100)}%</b>.</div></div>`;
        return `<div class="panel"><h3>${escapeHtml(event.nome)} · ${year}</h3><p class="muted">Semana seguinte: <b>${formatBrazilianDate(dates.weekStart)} a ${formatBrazilianDate(dates.weekEnd)}</b>.</p><div class="kpis"><div class="kpi"><span>Total da semana</span><br><b>${formatNumber(total)}</b></div><div class="kpi"><span>Registros</span><br><b>${rows.length}</b></div><div class="kpi"><span>Média semanal</span><br><b>${formatNumber(weeklyAverage)}</b></div><div class="kpi"><span>Relação com a média</span><br><b>${formatNumber(ratio)}×</b></div></div>${renderTable(rows)}</div>`;
      })
      .join("");
    modal.open(
      event.nome,
      `Comparação sazonal: ${seasonalHistoryYear} e ${operatingYear}`,
      html
    );
  }

  return Object.freeze({ render: renderDashboard, openPerson, openEvent });
}
