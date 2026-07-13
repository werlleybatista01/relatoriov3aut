import {
  escapeHtml,
  formatNumber,
  groupBy,
  groupByMonth,
  monthLabel,
  parseIsoLocal,
  sumQuantities,
  toNumber
} from "../core/formatters.js";

/**
 * Módulo de botinas.
 *
 * A decisão usa a combinação modelo + tamanho. A regra de cobertura permanece
 * igual à versão validada: vermelho até um mês, amarelo abaixo de quatro meses.
 */
export function createBootsModule({
  selectors,
  components,
  modal,
  documentRef = document
}) {
  const esc = escapeHtml;
  const fmt = formatNumber;
  const n = toNumber;
  const parseISO = parseIsoLocal;
  const { renderBars, renderTable } = components;
  const { operatingYear, referenceDate } = selectors.metadata;
  const stockByCat = selectors.stockByCategory;
  const stockTotal = selectors.stockTotal;
  let botinaModeloFiltro = "todos";

  function extrairTamanho(txt) {
    let m = String(txt || "").match(/(?:^|[^0-9])([3-5][0-9])(?:[^0-9]|$)/);
    return m ? m[1] : "";
  }
  function normalizarModeloBotinaTexto(txt) {
    let t = String(txt || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .toUpperCase();
    if (t.includes("MOTORISTA")) return "Botina motorista";
    if (t.includes("PVC") || t.includes("BORRACHA")) {
      if (t.includes("BRANCA") || t.includes("BRANCO")) return "Bota PVC branca";
      if (t.includes("PRETA") || t.includes("PRETO")) return "Bota PVC preta";
      return "Bota PVC";
    }
    if (t.includes("BOTINA") || t.includes("SEGURANCA")) return "Botina de segurança";
    return "Modelo não identificado";
  }
  function modeloBotina(r) {
    return r.Modelo || normalizarModeloBotinaTexto(r["Nome do Produto"]);
  }
  function chaveBotina(modelo, tam) {
    return `${modelo}|||${tam}`;
  }
  function rotuloBotina(modelo, tam) {
    return `${modelo} · ${tam === "Sem tamanho" ? "sem tamanho" : "tam. " + tam}`;
  }
  function botinaStockByKey() {
    let m = {};
    stockByCat("Botinas").forEach((e) => {
      let modelo = modeloBotina(e),
        tam = String(
          e.Tamanho || extrairTamanho(e["Nome do Produto"]) || "Sem tamanho"
        ),
        k = chaveBotina(modelo, tam);
      if (!m[k]) m[k] = { estoque: 0, minimo: 0, modelo, tam, origens: [] };
      m[k].estoque += n(e.QtdeEstoque);
      m[k].minimo += n(e.EstoqueMin);
      m[k].origens.push(...(e.ProdutosOrigem || []));
    });
    return m;
  }
  function mesesCompletosBotina(arr) {
    let atual = referenceDate.slice(0, 7),
      keys = [
        ...new Set(
          arr
            .map((r) => (r.Data_iso || "").slice(0, 7))
            .filter(Boolean)
            .filter((k) => k !== atual)
        )
      ];
    if (!keys.length)
      keys = [
        ...new Set(arr.map((r) => (r.Data_iso || "").slice(0, 7)).filter(Boolean))
      ];
    return Math.max(1, keys.length);
  }
  function botinaStats() {
    let arr = selectors.byCategory("Botinas"),
      st = botinaStockByKey(),
      meses = mesesCompletosBotina(arr),
      m = {};
    arr.forEach((r) => {
      let modelo = modeloBotina(r),
        tam = String(
          r.Tamanho || extrairTamanho(r["Nome do Produto"]) || "Sem tamanho"
        ),
        k = chaveBotina(modelo, tam);
      if (!m[k])
        m[k] = {
          k,
          modelo,
          tam,
          q: 0,
          n: 0,
          rows: [],
          estoque: 0,
          minimo: 0,
          media: 0,
          cobertura: 999,
          status: "Normal",
          cls: "ok"
        };
      m[k].q += n(r.Qtde_num);
      m[k].n++;
      m[k].rows.push(r);
    });
    Object.entries(st).forEach(([k, s]) => {
      if (!m[k])
        m[k] = {
          k,
          modelo: s.modelo,
          tam: s.tam,
          q: 0,
          n: 0,
          rows: [],
          estoque: 0,
          minimo: 0,
          media: 0,
          cobertura: 999,
          status: "Normal",
          cls: "ok"
        };
      m[k].estoque = s.estoque;
      m[k].minimo = s.minimo;
      m[k].origens = s.origens;
    });
    let rank = { danger: 0, warn: 1, ok: 2 };
    return Object.values(m)
      .map((x) => {
        x.media = x.q / meses;
        x.cobertura = x.media ? x.estoque / x.media : 999;
        let cadastroRuim =
          x.tam === "Sem tamanho" || x.modelo === "Modelo não identificado";
        if (cadastroRuim) {
          x.status = "Revisar cadastro";
          x.cls = "warn";
        } else if (x.estoque <= 0 && x.q > 0) {
          x.status = "Sem estoque";
          x.cls = "danger";
        } else if (x.media > 0 && x.cobertura <= 1) {
          x.status = "Crítico";
          x.cls = "danger";
        } else if (x.media > 0 && x.cobertura < 4) {
          x.status = "Abaixo da meta";
          x.cls = "warn";
        } else {
          x.status = "Normal";
          x.cls = "ok";
        }
        return x;
      })
      .sort(
        (a, b) =>
          rank[a.cls] - rank[b.cls] ||
          b.q - a.q ||
          a.modelo.localeCompare(b.modelo) ||
          Number(a.tam) - Number(b.tam)
      );
  }
  function botinaStatsFiltrados(stats) {
    return botinaModeloFiltro === "todos"
      ? stats
      : stats.filter((s) => s.modelo === botinaModeloFiltro);
  }
  function botinaRowsFiltradas(arr) {
    return botinaModeloFiltro === "todos"
      ? arr
      : arr.filter((r) => modeloBotina(r) === botinaModeloFiltro);
  }
  function renderBotinaPills(stats) {
    let modelos = [...new Set(stats.map((s) => s.modelo))].sort();
    return `<div class="pillbar"><button class="pill ${botinaModeloFiltro === "todos" ? "active" : ""}" data-action="boots-filter" data-model="todos">Todos os modelos</button>${modelos.map((m) => `<button class="pill ${botinaModeloFiltro === m ? "active" : ""}" data-action="boots-filter" data-model="${encodeURIComponent(m)}">${esc(m)}</button>`).join("")}</div>`;
  }
  function botinaColaboradores(arr) {
    let g = groupBy(arr, "Requisitante");
    return g.map((x) => {
      let itens = groupBy(
        x.rows.map((r) => ({
          ...r,
          ItemBotina: rotuloBotina(
            modeloBotina(r),
            String(r.Tamanho || extrairTamanho(r["Nome do Produto"]) || "Sem tamanho")
          )
        })),
        "ItemBotina"
      );
      let dates = x.rows
        .map((r) => r.Data_iso)
        .filter(Boolean)
        .sort();
      let gaps = [];
      for (let i = 1; i < dates.length; i++)
        gaps.push(Math.round((parseISO(dates[i]) - parseISO(dates[i - 1])) / 86400000));
      let mediaTroca = gaps.length
        ? Math.round(gaps.reduce((a, b) => a + b, 0) / gaps.length)
        : null;
      return { ...x, principal: itens[0]?.k || "-", mediaTroca };
    });
  }
  function openItemBotina(keyEnc) {
    let key = decodeURIComponent(keyEnc),
      [modelo, tam] = key.split("|||"),
      arr = selectors
        .byCategory("Botinas")
        .filter(
          (r) =>
            modeloBotina(r) === modelo &&
            String(
              r.Tamanho || extrairTamanho(r["Nome do Produto"]) || "Sem tamanho"
            ) === tam
        ),
      pessoas = groupBy(arr, "Requisitante"),
      st = botinaStats().find((s) => s.k === key);
    modal.open(
      rotuloBotina(modelo, tam),
      `${fmt(sumQuantities(arr))} par(es) retirado(s) em ${operatingYear} · estoque ${fmt(st?.estoque || 0)}`,
      `<div class="two"><div class="panel"><h3>Quem retirou</h3>${renderBars(pessoas, 30, "boots-person")}</div><div class="panel"><h3>Histórico do item</h3>${renderTable(arr)}</div></div>`
    );
  }
  function openPessoaBotina(nomeEnc) {
    let nome = decodeURIComponent(nomeEnc),
      arr = selectors
        .byCategory("Botinas")
        .filter((r) => (r.Requisitante || "Não informado") === nome),
      porItem = groupBy(
        arr.map((r) => ({
          ...r,
          ItemBotina: rotuloBotina(
            modeloBotina(r),
            String(r.Tamanho || extrairTamanho(r["Nome do Produto"]) || "Sem tamanho")
          )
        })),
        "ItemBotina"
      );
    modal.open(
      "Retiradas de botinas · " + nome,
      `${fmt(sumQuantities(arr))} par(es) em ${fmt(arr.length)} registro(s) de ${operatingYear}`,
      `<div class="two"><div class="panel"><h3>Modelos e tamanhos</h3>${renderBars(porItem, 20)}</div><div class="panel"><h3>Datas e produtos</h3>${renderTable(arr)}</div></div>`
    );
  }
  function botinaStatusGeral(stats) {
    let crit = stats.filter((s) => s.cls === "danger"),
      warn = stats.filter((s) => s.cls === "warn"),
      cad = stats.filter((s) => s.status === "Revisar cadastro");
    if (crit.length)
      return {
        cls: "danger",
        badge: "🚨 Prioridade imediata",
        txt: "Existem botinas em situação crítica",
        desc: `${crit.length} combinação(ões) de modelo e tamanho estão sem estoque ou com até um mês de cobertura.`
      };
    if (warn.length)
      return {
        cls: "warn",
        badge: "⚠️ Planejar reposição",
        txt: "Existem botinas abaixo da meta",
        desc: `${warn.length} combinação(ões) precisam de atenção${cad.length ? `, incluindo ${cad.length} cadastro(s) incompleto(s)` : ""}.`
      };
    return {
      cls: "ok",
      badge: "✅ Estoque confortável",
      txt: "Estoque de botinas dentro da meta",
      desc: "As combinações com consumo possuem cobertura igual ou superior a quatro meses."
    };
  }
  function renderBotinaPrioridades(stats) {
    let rows = stats
      .map(
        (s) =>
          `<tr data-action="boots-item" data-key="${encodeURIComponent(s.k)}" style="cursor:pointer"><td><b>${esc(s.modelo)}</b></td><td>${esc(s.tam)}</td><td>${fmt(s.estoque)}</td><td>${fmt(s.q)}</td><td>${fmt(s.media)}</td><td>${s.media ? fmt(s.cobertura) + " mês(es)" : "Sem consumo"}</td><td><span class="recommend-badge ${s.cls === "danger" ? "danger" : s.cls === "warn" ? "warn" : ""}">${s.status}</span></td></tr>`
      )
      .join("");
    return `<div class="tablewrap"><table><thead><tr><th>Modelo</th><th>Tamanho</th><th>Estoque</th><th>Saídas ${operatingYear}</th><th>Média/mês</th><th>Cobertura</th><th>Status</th></tr></thead><tbody>${rows || '<tr><td colspan="7">Sem dados no filtro.</td></tr>'}</tbody></table></div>`;
  }
  function renderBotinaEstoqueConsumo(stats) {
    let max = Math.max(1, ...stats.map((s) => Math.max(s.estoque, s.q)));
    return (
      stats
        .map(
          (s) =>
            `<div class="prod" data-action="boots-item" data-key="${encodeURIComponent(s.k)}"><b>${esc(rotuloBotina(s.modelo, s.tam))}</b><div class="bar" title="Estoque atual" style="margin-top:9px"><span style="width:${Math.max(3, (s.estoque / max) * 100)}%;background:linear-gradient(90deg,#076eb0,#16813a)"></span></div><div class="bar" title="Saídas em ${operatingYear}" style="margin-top:5px"><span style="width:${Math.max(3, (s.q / max) * 100)}%;background:linear-gradient(90deg,#f6c431,#b77900)"></span></div><small>Estoque ${fmt(s.estoque)} · saídas ${fmt(s.q)} · ${s.status}</small></div>`
        )
        .join("") || '<p class="muted">Sem dados no filtro.</p>'
    );
  }
  function renderBotinas() {
    let arrTodos = selectors.byCategory("Botinas"),
      allStats = botinaStats(),
      stats = botinaStatsFiltrados(allStats),
      arr = botinaRowsFiltradas(arrTodos),
      st = botinaStatusGeral(allStats),
      total = sumQuantities(arrTodos),
      estoque = stockTotal("Botinas"),
      mediaTotal = allStats.reduce((a, s) => a + s.media, 0),
      crit = allStats.filter((s) => s.cls !== "ok"),
      reqs = botinaColaboradores(arr),
      meses = groupByMonth(arr),
      modelos = groupBy(
        arrTodos.map((r) => ({ ...r, ModeloAgrupado: modeloBotina(r) })),
        "ModeloAgrupado"
      ),
      cadastro = allStats.filter(
        (s) => s.tam === "Sem tamanho" || s.modelo === "Modelo não identificado"
      ),
      top = allStats.filter((s) => s.cls !== "ok").slice(0, 5);
    documentRef.getElementById("botinasContent").innerHTML =
      `${renderBotinaPills(allStats)}<div class="decision"><div class="decision-main status-${st.cls}"><div class="eyebrow">Decisão automática · Botinas · ${operatingYear}</div><div class="decision-title">${st.txt}</div><p class="decision-text">A análise agora cruza <b>modelo + tamanho</b>. Botina de segurança, botina motorista e bota PVC não são mais somadas como se fossem o mesmo produto. A meta operacional é manter aproximadamente <b>4 meses de cobertura</b> para cada combinação com consumo.</p><div class="mini-grid"><div class="mini"><span>Estoque total</span><b>${fmt(estoque)}</b><small>pares em todos os modelos</small></div><div class="mini"><span>Saídas em ${operatingYear}</span><b>${fmt(total)}</b><small>pares retirados</small></div><div class="mini"><span>Média mensal</span><b>${fmt(mediaTotal)}</b><small>pares/mês</small></div><div class="mini"><span>Itens com atenção</span><b>${fmt(crit.length)}</b><small>modelo + tamanho</small></div></div></div><aside class="decision-side status-${st.cls}"><span class="recommend-badge ${st.cls === "danger" ? "danger" : st.cls === "warn" ? "warn" : ""}">${st.badge}</span><h3>Leitura rápida</h3><p class="muted">${st.desc}</p>${top.length ? `<div class="risk-box ${st.cls === "danger" ? "danger" : ""}"><b>Prioridades para conferir:</b><br>${top.map((s) => `${esc(rotuloBotina(s.modelo, s.tam))} — ${s.status}`).join("<br>")}</div>` : '<div class="risk-box"><b>Sem prioridade imediata:</b> manter o acompanhamento mensal.</div>'}</aside></div>${cadastro.length ? `<div class="note"><b>Atenção ao cadastro:</b> existem ${cadastro.length} item(ns) sem tamanho ou modelo plenamente identificado. Eles aparecem separadamente e não são somados a outros tamanhos.</div>` : ""}<div class="panel"><h2>Prioridades por modelo e tamanho</h2><p class="muted">Vermelho: sem estoque ou até 1 mês. Amarelo: menos de 4 meses ou cadastro incompleto. Verde: cobertura adequada. Clique em uma linha para ver quem retirou e as datas.</p>${renderBotinaPrioridades(stats)}</div><div class="two"><div class="panel"><h2>Estoque x saídas</h2><p class="muted">Barra superior: estoque. Barra inferior: saídas de ${operatingYear}.</p><div class="prodgrid">${renderBotinaEstoqueConsumo(stats)}</div></div><div class="panel"><h2>Itens que exigem atenção</h2>${renderBotinaPrioridades(stats.filter((s) => s.cls !== "ok").length ? stats.filter((s) => s.cls !== "ok") : stats.slice(0, 6))}</div></div><div class="two"><div class="panel"><h2>Consumo mensal</h2>${renderBars(
        meses.map((x) => ({ ...x, k: monthLabel(x.k) })),
        24
      )}</div><div class="panel"><h2>Consumo por modelo</h2>${renderBars(modelos, 10)}</div></div><div class="two"><div class="panel"><h2>Colaboradores e trocas</h2><p class="muted">Clique no colaborador para ver modelos, tamanhos e datas.</p><div class="tablewrap"><table><thead><tr><th>Colaborador</th><th>Qtd</th><th>Item principal</th><th>Média entre retiradas</th></tr></thead><tbody>${reqs
        .slice(0, 25)
        .map(
          (r) =>
            `<tr role="button" tabindex="0" data-action="boots-person" data-value="${encodeURIComponent(r.k)}" style="cursor:pointer"><td><b>${esc(r.k)}</b></td><td>${fmt(r.q)}</td><td>${esc(r.principal)}</td><td>${r.mediaTroca ? fmt(r.mediaTroca) + " dias" : "—"}</td></tr>`
        )
        .join(
          ""
        )}</tbody></table></div></div><div class="panel"><h2>Quem mais retirou</h2>${renderBars(reqs, 15, "boots-person")}</div></div><div class="panel"><h2>Investigação por modelo e tamanho</h2><p class="muted">Cada cartão representa um item operacional distinto.</p><div class="prodgrid">${stats.map((s) => `<div class="prod" data-action="boots-item" data-key="${encodeURIComponent(s.k)}"><b>🥾 ${esc(rotuloBotina(s.modelo, s.tam))}</b><br>Estoque ${fmt(s.estoque)} · saídas ${fmt(s.q)}<br><small>${s.status}</small></div>`).join("")}</div></div>`;
  }

  function setFilter(encodedModel) {
    botinaModeloFiltro = decodeURIComponent(encodedModel || "todos");
    renderBotinas();
  }

  return Object.freeze({
    render: renderBotinas,
    setFilter,
    openItem: openItemBotina,
    openPerson: openPessoaBotina
  });
}
