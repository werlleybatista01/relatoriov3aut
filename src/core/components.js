import { escapeHtml, formatNumber, toNumber } from "./formatters.js";

/**
 * Cria componentes HTML sem registrar eventos globais.
 * A interação é descrita por data-action e tratada por delegação em app.js.
 */
export function createComponents({ bagsPerPackage }) {
  function packagesFromBags(value) {
    return toNumber(value) / Math.max(1, Number(bagsPerPackage || 100));
  }

  function renderTable(rows, limit = 9999) {
    const body = rows
      .slice(0, limit)
      .map((row) => {
        const quantity =
          row.Categoria === "Sacolas"
            ? `${formatNumber(row.Qtde_num)} sacolas<br>
           <small>${formatNumber(
             toNumber(row.Pacotes_num) || packagesFromBags(row.Qtde_num)
           )} pacote(s)</small>`
            : `<b>${formatNumber(row.Qtde_num)}</b>`;

        return `<tr>
        <td>${escapeHtml(row.Data_fmt)}</td>
        <td>${escapeHtml(row["Nº Retirada"])}</td>
        <td>${escapeHtml(row.Requisitante)}</td>
        <td>${escapeHtml(row["Nome do Produto"])}</td>
        <td>${quantity}</td>
        <td>${escapeHtml(row.Status)}</td>
      </tr>`;
      })
      .join("");

    return `<div class="tablewrap">
      <table>
        <thead>
          <tr>
            <th>Data</th><th>Nº</th><th>Requisitante</th>
            <th>Produto</th><th>Qtd</th><th>Status</th>
          </tr>
        </thead>
        <tbody>
          ${body || '<tr><td colspan="6">Sem registros no recorte.</td></tr>'}
        </tbody>
      </table>
    </div>`;
  }

  /**
   * Renderiza barras. Quando action é informado, o item recebe data-action
   * e data-value, sem JavaScript embutido no HTML.
   */
  function renderBars(items, limit = 12, action = null) {
    const max = Math.max(1, ...items.map((item) => item.q));

    return (
      items
        .slice(0, limit)
        .map((item) => {
          const attributes = action
            ? `role="button" tabindex="0" data-action="${escapeHtml(action)}"
           data-value="${encodeURIComponent(item.k)}"`
            : "";

          return `<div class="barrow ${action ? "clickable" : ""}" ${attributes}>
        <b>${escapeHtml(item.k)}</b>
        <div class="bar">
          <span style="width:${Math.max(4, (item.q / max) * 100)}%"></span>
        </div>
        <span>${formatNumber(item.q)}</span>
      </div>`;
        })
        .join("") || '<p class="muted">Sem dados.</p>'
    );
  }

  return Object.freeze({ renderTable, renderBars, packagesFromBags });
}
