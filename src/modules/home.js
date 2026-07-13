import { CATEGORIES } from "../config.js";
import {
  countUnique,
  escapeHtml,
  formatNumber,
  sumQuantities
} from "../core/formatters.js";

/**
 * Tela inicial.
 *
 * Os cartões apenas apresentam um resumo e disparam uma ação declarativa.
 * Nenhuma função JavaScript é embutida no HTML.
 */
export function createHomeModule({ selectors, tools, documentRef = document }) {
  function render() {
    const container = documentRef.getElementById("homeCards");
    const toolMetrics = tools.getHomeMetrics();

    container.innerHTML = CATEGORIES.map(([category, icon, description]) => {
      if (category === "Ferramentas") {
        return `
          <div class="card" role="button" tabindex="0"
               data-action="open-category" data-category="Ferramentas">
            <span class="icon">${icon}</span>
            <h2>Ferramentas</h2>
            <p class="muted">
              Equipamentos devolvíveis que continuam com colaboradores.
            </p>
            <div class="chips">
              <span class="chip">${formatNumber(toolMetrics.quantity)} itens em aberto</span>
              <span class="chip">${formatNumber(toolMetrics.people)} colaboradores</span>
              <span class="chip">${formatNumber(toolMetrics.overdue)} atrasados</span>
            </div>
          </div>
        `;
      }

      const rows = selectors.byCategory(category);
      const quantity = sumQuantities(rows);
      const people = countUnique(rows, "Requisitante");
      const products = countUnique(rows, "Nome do Produto");

      return `
        <div class="card" role="button" tabindex="0"
             data-action="open-category"
             data-category="${escapeHtml(category)}">
          <span class="icon">${icon}</span>
          <h2>${escapeHtml(category)}</h2>
          <p class="muted">${escapeHtml(description)}</p>
          <div class="chips">
            <span class="chip">${formatNumber(quantity)} unidades</span>
            <span class="chip">${rows.length} retiradas</span>
            <span class="chip">${people} requisitantes</span>
            <span class="chip">${products} produtos</span>
          </div>
        </div>
      `;
    }).join("");
  }

  return Object.freeze({ render });
}
