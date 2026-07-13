import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

test("index é uma casca sem CSS ou JavaScript embutido", async () => {
  const html = await readFile(new URL("../index.html", import.meta.url), "utf8");

  assert.equal(/<style[\s>]/i.test(html), false);
  assert.equal(/<script(?![^>]*\bsrc=)[^>]*>/i.test(html), false);
  assert.equal(/\son(click|input|change|submit)=/i.test(html), false);
  assert.match(html, /assets\/css\/style\.css/);
  assert.match(
    html,
    /<script[^>]*src="src\/main\.js"[^>]*type="module"[^>]*>|<script[^>]*type="module"[^>]*src="src\/main\.js"[^>]*>/
  );
});

test("main apenas inicializa a aplicação", async () => {
  const main = await readFile(new URL("../src/main.js", import.meta.url), "utf8");

  assert.match(main, /createDashboardApp\(\)\.init\(\)/);
  assert.equal(main.includes("renderBotinas"), false);
  assert.equal(main.includes("TBRetiradas"), false);
});

test("payload público contém somente identificadores pseudonimizados", async () => {
  const { dashboardData } = await import("../data/dashboard-data.js");

  assert.equal(dashboardData.features.directWhatsAppEnabled, false);
  assert.equal(dashboardData.features.personalDataIncluded, false);
  assert.equal(dashboardData.features.homologationMode, false);

  for (const row of dashboardData.withdrawals) {
    assert.match(row.Requisitante, /^Colaborador [A-F0-9]{8}$/);
    assert.match(row["Nº Retirada"] || "", /^(|RET-[A-F0-9]{8})$/);
    assert.equal(row["Responsável pelo Registro"] || "", "");
    assert.equal(row["Observação"] || "", "");
  }

  for (const row of dashboardData.openTools) {
    assert.match(row.Colaborador, /^Colaborador [A-F0-9]{8}$/);
    assert.equal(row.TelefoneWhatsApp || "", "");
  }
});
