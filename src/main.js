import { createDashboardApp } from "./app.js";

/**
 * Ponto de entrada da aplicação.
 * Nenhuma regra de negócio deve ser adicionada aqui.
 */
async function initializeDashboard() {
  const dataUrl = new URL("../data/dashboard-data.js", import.meta.url);
  dataUrl.searchParams.set("v", String(Date.now()));
  const { dashboardData } = await import(dataUrl.href);
  createDashboardApp(dashboardData).init();
}

initializeDashboard().catch((error) => {
  console.error("Não foi possível carregar os dados atualizados.", error);
  const root = document.getElementById("app") || document.body;
  root.insertAdjacentHTML(
    "afterbegin",
    '<div class="error">Não foi possível carregar os dados atualizados. Atualize a página.</div>'
  );
});
