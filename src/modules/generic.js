import { formatNumber, groupBy, sumQuantities } from "../core/formatters.js";

/**
 * Relatório genérico para categorias sem módulo analítico próprio.
 */
export function createGenericModule({
  selectors,
  components,
  tools,
  documentRef = document
}) {
  const { renderBars, renderTable } = components;

  function render(category) {
    if (category === "Ferramentas") {
      tools.render();
      return;
    }

    const rows = selectors.byCategory(category);
    const products = groupBy(rows, "Nome do Produto");
    const people = groupBy(rows, "Requisitante");

    documentRef.getElementById("genericTitle").textContent = category;
    documentRef.getElementById("genericSub").textContent =
      "Relatório de retiradas por produto, requisitante e histórico.";

    documentRef.getElementById("genericContent").innerHTML = `
      <div class="panel">
        <div class="kpis">
          <div class="kpi">
            <span>Total retirado</span><br>
            <b>${formatNumber(sumQuantities(rows))}</b>
          </div>
          <div class="kpi">
            <span>Nº de registros</span><br>
            <b>${rows.length}</b>
          </div>
          <div class="kpi">
            <span>Requisitantes</span><br>
            <b>${people.length}</b>
          </div>
          <div class="kpi">
            <span>Produtos</span><br>
            <b>${products.length}</b>
          </div>
        </div>
      </div>
      <div class="two">
        <div class="panel">
          <h2>Produtos mais retirados</h2>
          ${renderBars(products, 15)}
        </div>
        <div class="panel">
          <h2>Quem mais retirou</h2>
          ${renderBars(people, 15)}
        </div>
      </div>
      <div class="panel">
        <h2>Histórico</h2>
        ${renderTable(rows)}
      </div>
    `;
  }

  return Object.freeze({ render });
}
