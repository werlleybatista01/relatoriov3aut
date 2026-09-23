import { escapeHtml, formatNumber, groupBy, sumQuantities, toNumber } from "../core/formatters.js";

export function createBootsHubModule({ selectors, modal, documentRef = document }) {
  const esc = escapeHtml;
  const fmt = formatNumber;
  const n = toNumber;
  const { operatingYear, referenceDate } = selectors.metadata;
  let filter = "todos";

  function size(row) {
    const value = row.Tamanho || String(row["Nome do Produto"] || "").match(/(?:^|[^0-9])([3-5][0-9])(?:[^0-9]|$)/)?.[1];
    return String(value || "Sem tamanho");
  }

  function model(row) {
    if (row.Modelo) return row.Modelo;
    const text = String(row["Nome do Produto"] || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toUpperCase();
    if (text.includes("MOTORISTA")) return "Botina motorista";
    if (text.includes("PVC") || text.includes("BORRACHA")) return text.includes("BRAN") ? "Bota PVC branca" : text.includes("PRET") ? "Bota PVC preta" : "Bota PVC";
    if (text.includes("BOTINA") || text.includes("SEGURANCA")) return "Botina de segurança";
    return "Modelo não identificado";
  }

  function key(row) { return model(row) + "|||" + size(row); }

  function stockMap() {
    const map = {};
    selectors.stockByCategory("Botinas").forEach(row => {
      const k = key(row);
      if (!map[k]) map[k] = { estoque: 0, minimo: 0, modelo: model(row), tamanho: size(row) };
      map[k].estoque += n(row.QtdeEstoque);
      map[k].minimo += n(row.EstoqueMin);
    });
    return map;
  }

  function stats() {
    const rows = selectors.byCategory("Botinas");
    const stocks = stockMap();
    const months = Math.max(1, new Set(rows.map(r => String(r.Data_iso || "").slice(0, 7)).filter(Boolean).filter(m => m !== String(referenceDate).slice(0, 7))).size);
    const map = {};
    rows.forEach(row => {
      const k = key(row);
      if (!map[k]) map[k] = { k, modelo: model(row), tamanho: size(row), saidas: 0, rows: [] };
      map[k].saidas += n(row.Qtde_num);
      map[k].rows.push(row);
    });
    Object.entries(stocks).forEach(([k, s]) => {
      if (!map[k]) map[k] = { k, modelo: s.modelo, tamanho: s.tamanho, saidas: 0, rows: [] };
      Object.assign(map[k], s);
    });
    return Object.values(map).map(x => {
      x.estoque ??= 0; x.minimo ??= 0; x.media = x.saidas / months;
      x.cobertura = x.media ? x.estoque / x.media : 999;
      x.status = x.estoque <= 0 && x.saidas > 0 ? "Sem estoque" : x.media && x.cobertura <= 1 ? "Crítico" : x.minimo > 0 && x.estoque < x.minimo ? "Abaixo do mínimo" : x.media && x.cobertura < 4 ? "Atenção" : "Normal";
      x.cls = ["Sem estoque", "Crítico"].includes(x.status) ? "danger" : ["Abaixo do mínimo", "Atenção"].includes(x.status) ? "warn" : "ok";
      return x;
    }).sort((a,b) => ({danger:0,warn:1,ok:2}[a.cls] - ({danger:0,warn:1,ok:2}[b.cls]) || b.saidas - a.saidas || a.modelo.localeCompare(b.modelo) || Number(a.tamanho) - Number(b.tamanho));
  }

  function filtered(rows) { return filter === "todos" ? rows : rows.filter(x => x.modelo === filter); }

  function pills(rows) {
    const models = [...new Set(rows.map(x => x.modelo))].sort();
    return `<div class="boots-pills"><button class="boots-pill ${filter==="todos"?"active":""}" data-action="boots-filter" data-model="todos">Todos</button>${models.map(m => `<button class="boots-pill ${filter===m?"active":""}" data-action="boots-filter" data-model="${encodeURIComponent(m)}">${esc(m)}</button>`).join("")}</div>`;
  }

  function openItem(k) {
    const s = stats().find(x => x.k === decodeURIComponent(k));
    if (!s) return;
    const rows = s.rows;
    const people = groupBy(rows, "Requisitante");
    modal.open(`${s.modelo} · tamanho ${esc(s.tamanho)}`, `${fmt(s.estoque)} em estoque · ${fmt(s.saidas)} saídas em ${operatingYear}`, `
      <div class="boots-modal-grid">
        <div class="panel"><h3>Quem retirou</h3>${people.map(p => `<div class="boots-person-row"><b>${esc(p.k)}</b><span>${fmt(p.q)} par(es)</span></div>`).join("") || "<p class='muted'>Sem retiradas.</p>"}</div>
        <div class="panel"><h3>Histórico</h3><div class="tablewrap"><table><thead><tr><th>Data</th><th>Colaborador</th><th>Quantidade</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${esc(r.Data_fmt || r.Data_iso || "—")}</td><td>${esc(r.Requisitante || "—")}</td><td>${fmt(n(r.Qtde_num))}</td></tr>`).join("")}</tbody></table></div></div>
      </div>`);
  }

  function render() {
    const all = stats(), rows = filtered(all);
    const totalStock = selectors.stockTotal("Botinas");
    const totalOut = selectors.sumQuantities(selectors.byCategory("Botinas"));
    const attention = all.filter(x => x.cls !== "ok");
    const avg = all.reduce((a,x)=>a+x.media,0);
    const critical = all.filter(x=>x.cls==="danger").length;
    const models = [...new Set(all.map(x=>x.modelo))];
    const recommendations = attention.slice(0, 6).map(x => ({...x, comprar: Math.max(0, Math.ceil((x.media * 4) - x.estoque))}));

    documentRef.getElementById("botinasContent").innerHTML = `
      ${pills(all)}
      <div class="boots-hero">
        <div><div class="boots-eyebrow">CONTROLE OPERACIONAL · ${operatingYear}</div><h3>Dashboard de Gestão de Botinas</h3><p>Controle por modelo e tamanho, com estoque atual, consumo e indicação automática de reposição.</p></div>
        <div class="boots-hero-status ${critical ? "danger" : attention.length ? "warn" : "ok"}">${critical ? "Prioridade imediata" : attention.length ? "Planejar reposição" : "Estoque dentro da meta"}<small>${attention.length} item(ns) exigem atenção</small></div>
      </div>
      <div class="boots-kpis">
        <div class="boots-kpi"><span>Total em estoque</span><b>${fmt(totalStock)}</b><small>pares</small></div>
        <div class="boots-kpi"><span>Saídas em ${operatingYear}</span><b>${fmt(totalOut)}</b><small>pares retirados</small></div>
        <div class="boots-kpi"><span>Média mensal</span><b>${fmt(avg)}</b><small>pares/mês</small></div>
        <div class="boots-kpi"><span>Itens em alerta</span><b class="${attention.length ? "red":""}">${fmt(attention.length)}</b><small>modelo + tamanho</small></div>
      </div>
      <div class="boots-grid">
        <section class="boots-panel wide"><div class="boots-panel-head"><div><h3>Estoque por tamanho e modelo</h3><p>Itens críticos, abaixo do mínimo e com cobertura reduzida aparecem primeiro.</p></div></div>
          <div class="tablewrap"><table><thead><tr><th>Modelo</th><th>Tam.</th><th>Estoque</th><th>Média/mês</th><th>Cobertura</th><th>Status</th></tr></thead><tbody>
          ${rows.map(x=>`<tr data-action="boots-item" data-key="${encodeURIComponent(x.k)}" class="clickable"><td><b>${esc(x.modelo)}</b></td><td>${esc(x.tamanho)}</td><td class="${x.cls==="danger"?"red":""}">${fmt(x.estoque)}</td><td>${fmt(x.media)}</td><td>${x.media ? fmt(x.cobertura)+" mês(es)" : "Sem consumo"}</td><td><span class="boots-badge ${x.cls}">${x.status}</span></td></tr>`).join("") || "<tr><td colspan='6'>Sem dados.</td></tr>"}
          </tbody></table></div>
        </section>
        <section class="boots-panel"><div class="boots-panel-head"><div><h3>Recomendação de compra</h3><p>Meta calculada para aproximadamente 4 meses de cobertura.</p></div></div>
          ${recommendations.length ? recommendations.map(x=>`<div class="boots-recommend"><div><b>${esc(x.modelo)} · ${esc(x.tamanho)}</b><small>Estoque: ${fmt(x.estoque)} · Média: ${fmt(x.media)}/mês</small></div><strong>${fmt(x.comprar)} pares</strong></div>`).join("") : "<p class='muted'>Nenhuma compra indicada no momento.</p>"}
        </section>
      </div>
      <div class="boots-grid">
        <section class="boots-panel"><div class="boots-panel-head"><div><h3>Distribuição por modelo</h3><p>${models.length} modelo(s) identificados.</p></div></div>
          ${models.map(m=>{const q=all.filter(x=>x.modelo===m).reduce((a,x)=>a+x.estoque,0);return `<div class="boots-model-row"><span>${esc(m)}</span><b>${fmt(q)} pares</b><div><i style="width:${Math.min(100,(q/Math.max(1,totalStock))*100)}%"></i></div></div>`}).join("")}
        </section>
        <section class="boots-panel"><div class="boots-panel-head"><div><h3>Resumo de consumo</h3><p>Principais itens por quantidade retirada.</p></div></div>
          ${[...all].sort((a,b)=>b.saidas-a.saidas).slice(0,8).map(x=>`<div class="boots-consumption"><span>${esc(x.modelo)} · ${esc(x.tamanho)}</span><b>${fmt(x.saidas)}</b></div>`).join("")}
        </section>
      </div>
      <div class="boots-note"><b>Regra de controle:</b> o estoque é analisado separadamente por modelo + tamanho. Não misture numerações diferentes ao decidir uma compra.</div>
    `;
  }

  function setFilter(value) { filter = decodeURIComponent(value || "todos"); render(); }

  return Object.freeze({ render, setFilter, openItem });
}
