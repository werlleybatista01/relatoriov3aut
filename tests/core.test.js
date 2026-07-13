import test from "node:test";
import assert from "node:assert/strict";

import {
  addDays,
  formatBrazilianDate,
  groupBy,
  groupByMonth,
  recordYear,
  sumQuantities
} from "../src/core/formatters.js";
import { createDataSelectors } from "../src/core/data-selectors.js";
import { demoDashboardData } from "../data/dashboard-data.demo.js";

test("formatadores mantêm datas e somas previsíveis", () => {
  assert.equal(formatBrazilianDate("2026-07-10"), "10/07/2026");
  assert.equal(addDays("2026-07-10", 2), "2026-07-12");
  assert.equal(addDays("2026-07-31", 1), "2026-08-01");
  assert.equal(recordYear({ Data_iso: "2025-03-01" }), 2025);
  assert.equal(sumQuantities([{ Qtde_num: 2 }, { Qtde_num: 3 }]), 5);
});

test("agrupamentos preservam quantidade e registros", () => {
  const rows = [
    { Requisitante: "A", Qtde_num: 2, Data_iso: "2026-01-10" },
    { Requisitante: "A", Qtde_num: 3, Data_iso: "2026-01-15" },
    { Requisitante: "B", Qtde_num: 1, Data_iso: "2026-02-01" }
  ];

  const people = groupBy(rows, "Requisitante");
  assert.equal(people[0].k, "A");
  assert.equal(people[0].q, 5);
  assert.equal(people[0].n, 2);

  const months = groupByMonth(rows);
  assert.deepEqual(
    months.map((month) => month.k),
    ["2026-01", "2026-02"]
  );
});

test("seletores separam operação e histórico sazonal", () => {
  const selectors = createDataSelectors(demoDashboardData);
  assert.equal(selectors.operationalRows().length, 2);
  assert.equal(selectors.byCategory("Botinas").length, 1);
  assert.equal(selectors.stockTotal("Sacolas"), 1200);
});

import { calculateBagMetrics } from "../src/modules/bags.js";

test("métricas de sacolas tratam 90 dias como ponto de reposição", () => {
  const metrics = calculateBagMetrics({
    rows: [
      { Data_iso: "2026-01-01", Qtde_num: 10 },
      { Data_iso: "2026-01-10", Qtde_num: 10 }
    ],
    stock: 200,
    referenceDate: "2026-01-10"
  });

  assert.equal(metrics.total, 20);
  assert.equal(metrics.days, 10);
  assert.equal(metrics.averageDaily, 2);
  assert.equal(metrics.coverageDays, 100);
  assert.equal(metrics.buyInDays, 10);
  assert.equal(metrics.status, "warning");
});

test("semáforo de sacolas usa verde acima de 120, amarelo até 120 e vermelho até 90", () => {
  const rows = [
    { Data_iso: "2026-01-01", Qtde_num: 10 },
    { Data_iso: "2026-01-10", Qtde_num: 10 }
  ];

  const safe = calculateBagMetrics({ rows, stock: 260, referenceDate: "2026-01-10" });
  const warning = calculateBagMetrics({
    rows,
    stock: 210,
    referenceDate: "2026-01-10"
  });
  const danger = calculateBagMetrics({ rows, stock: 132, referenceDate: "2026-01-10" });

  assert.equal(safe.coverageDays, 130);
  assert.equal(safe.status, "safe");
  assert.equal(warning.coverageDays, 105);
  assert.equal(warning.status, "warning");
  assert.equal(danger.coverageDays, 66);
  assert.equal(danger.status, "danger");
});
