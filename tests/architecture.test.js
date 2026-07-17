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
    /<script[^>]*src="src\/main\.js\?v=[^"]+"[^>]*type="module"[^>]*>|<script[^>]*type="module"[^>]*src="src\/main\.js\?v=[^"]+"[^>]*>/
  );
});

test("main apenas inicializa a aplicação", async () => {
  const main = await readFile(new URL("../src/main.js", import.meta.url), "utf8");

  assert.match(main, /dataUrl\.searchParams\.set\("v", String\(Date\.now\(\)\)\)/);
  assert.match(main, /createDashboardApp\(dashboardData\)\.init\(\)/);
  assert.equal(main.includes("renderBotinas"), false);
  assert.equal(main.includes("TBRetiradas"), false);
});

test("template de recuperação é a mesma casca modular de produção", async () => {
  const [index, template] = await Promise.all([
    readFile(new URL("../index.html", import.meta.url), "utf8"),
    readFile(new URL("../templates/index.modular.html", import.meta.url), "utf8")
  ]);

  assert.equal(template, index);
});

test("grades de sacolas preservam cartões legíveis e responsivos", async () => {
  const css = await readFile(
    new URL("../assets/css/style.css", import.meta.url),
    "utf8"
  );

  assert.match(
    css,
    /\.season-grid\s*\{[^}]*repeat\(auto-fit,\s*minmax\(min\(100%,\s*230px\),\s*1fr\)\)/s
  );
  assert.match(css, /\.season-card\s*\{[^}]*display:\s*flex/s);
  assert.match(css, /\.season-card\s*\{[^}]*flex-direction:\s*column/s);
  assert.match(css, /\.bags-overview-grid\s*>\s*\*[^}]*min-width:\s*0/s);
});

test("payload público respeita o modo de dados pessoais configurado", async () => {
  const { dashboardData } = await import("../data/dashboard-data.js");

  assert.equal(dashboardData.features.directWhatsAppEnabled, false);
  assert.equal(dashboardData.features.homologationMode, false);

  if (dashboardData.features.personalDataIncluded) {
    return;
  }

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
