import { escapeHtml, formatNumber, toNumber } from "../core/formatters.js";

const STORAGE_KEY_COBRANCA_FERRAMENTAS = "almoxarifado:ferramentas:cobranca:v1";
const ITENS_SEM_COBRANCA_AUTOMATICA = ["rastelo"];
const WEBHOOK_REGRAS_COBRANCA =
  "https://mcp-n8n.gtcqed.easypanel.host/webhook/f32d8ef1-1867-45ea-8304-422587fe3087/almoxarifado/excecoes-notificacao";

/**
 * Módulo de equipamentos devolvíveis.
 *
 * A classificação e o cálculo do saldo são realizados no Python.
 * Este módulo apenas filtra, agrupa e apresenta os saldos já consolidados.
 */
export function normalizarPesquisaFerramentas(txt) {
  return String(txt || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();
}

export function chaveFerramenta(row) {
  return [
    row.NumeroRetirada || "",
    row.CodigoProduto || "",
    row.CodigoCliente || "",
    row.Produto || ""
  ].join("|");
}

export function ehItemSemCobrancaAutomatica(row) {
  const texto = normalizarPesquisaFerramentas(
    [row.Produto, row.CategoriaEstoque].join(" ")
  );
  return ITENS_SEM_COBRANCA_AUTOMATICA.some((item) => texto.includes(item));
}

export function deveCobrarFerramenta(row, controlesCobranca = {}, referenceDateISO = "") {
  const controle = controlesCobranca[chaveFerramenta(row)] || {};
  const hoje = referenceDateISO || new Date().toISOString().slice(0, 10);

  if (controle.naoCobrar) return false;
  if (controle.prorrogadoAte && controle.prorrogadoAte >= hoje) return false;
  if (ehItemSemCobrancaAutomatica(row)) return false;

  return true;
}

export function montarPlanoCobrancaFerramentas({
  openTools,
  controlesCobranca = {},
  referenceDateISO = "",
  onlyOverdue = true
}) {
  return openTools.filter((row) => {
    if (onlyOverdue && row.StatusClasse !== "danger") return false;
    return deveCobrarFerramenta(row, controlesCobranca, referenceDateISO);
  });
}

export function createToolsModule({
  selectors,
  modal,
  whatsapp,
  documentRef = document
}) {
  const openTools = selectors.openTools;
  const stock = selectors.stock;
  const esc = escapeHtml;
  const fmt = formatNumber;
  const n = toNumber;
  let ferramentasBusca = "";
  let controlesCobranca = carregarControlesCobranca();

  function janela() {
    return documentRef.defaultView || globalThis.window || {};
  }

  function hojeISO() {
    return new Date().toISOString().slice(0, 10);
  }

  function somarDiasISO(dias) {
    const data = new Date();
    data.setDate(data.getDate() + Number(dias || 0));
    return data.toISOString().slice(0, 10);
  }

  function formatarDataISO(iso) {
    if (!iso) return "";
    const [ano, mes, dia] = String(iso).split("-");
    return ano && mes && dia ? `${dia}/${mes}/${ano}` : iso;
  }

  function carregarControlesCobranca() {
    try {
      const storage = janela().localStorage;
      return storage ? JSON.parse(storage.getItem(STORAGE_KEY_COBRANCA_FERRAMENTAS) || "{}") : {};
    } catch (_error) {
      return {};
    }
  }

  function salvarControlesCobranca() {
    try {
      const storage = janela().localStorage;
      if (storage) storage.setItem(STORAGE_KEY_COBRANCA_FERRAMENTAS, JSON.stringify(controlesCobranca));
    } catch (_error) {
      // O dashboard continua funcionando mesmo se o navegador bloquear storage.
    }
  }

  function registrarRegraCobrancaNoN8n(itemKey, payload) {
    const item = openTools.find((row) => chaveFerramenta(row) === itemKey);
    if (!item || !item.NumeroRetirada) return;
    const win = janela();
    if (!win.fetch) return;

    win.fetch(WEBHOOK_REGRAS_COBRANCA, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        codigo: item.NumeroRetirada,
        nome: item.Colaborador || "",
        produto: item.Produto || "",
        ...payload
      })
    }).catch((error) => {
      console.warn("Não foi possível registrar a regra de cobrança no n8n.", error);
    });
  }

  function controleFerramenta(row) {
    return controlesCobranca[chaveFerramenta(row)] || {};
  }
  function cobrancaPausada(row) {
    return !deveCobrarFerramenta(row, controlesCobranca, hojeISO());
  }
  function statusCobrancaFerramenta(row) {
    const controle = controleFerramenta(row);
    if (controle.naoCobrar) {
      return statusFerramentaBadge("ok", "Sem cobrança");
    }
    if (controle.prorrogadoAte && controle.prorrogadoAte >= hojeISO()) {
      return statusFerramentaBadge("warn", `Prorrogado até ${formatarDataISO(controle.prorrogadoAte)}`);
    }
    if (ehItemSemCobrancaAutomatica(row)) {
      return statusFerramentaBadge("ok", "Uso contínuo");
    }
    return statusFerramentaBadge(row.StatusClasse, row.StatusTexto);
  }
  function controlesLinhaFerramenta(row) {
    const code = encodeURIComponent(chaveFerramenta(row));
    const pausada = cobrancaPausada(row);
    return `<div class="tool-actions"><button class="btn ghost" type="button" data-action="tools-extend" data-code="${code}" data-days="7">+7 dias</button><button class="btn ghost" type="button" data-action="tools-extend" data-code="${code}" data-days="15">+15 dias</button>${pausada ? `<button class="btn yellow" type="button" data-action="tools-charge" data-code="${code}">Voltar a cobrar</button>` : `<button class="btn yellow" type="button" data-action="tools-no-charge" data-code="${code}">Não cobrar</button>`}</div>`;
  }
  function ferramentasAbertasFiltradas() {
    let termo = normalizarPesquisaFerramentas(ferramentasBusca);
    if (!termo) return openTools;
    return openTools.filter((r) =>
      normalizarPesquisaFerramentas(
        (r.Colaborador || "") + " " + (r.Produto || "")
      ).includes(termo)
    );
  }
  function estoqueFerramentas() {
    return stock.filter((row) => row.Categoria === "Ferramentas");
  }
  function nomeEstoqueFerramenta(row) {
    return row["Nome do Produto"] || row.Produto || row.NomeProduto || "Ferramenta";
  }
  function codigoFerramenta(row) {
    return String(row.CodigoProduto || row.Codigo || row.Item || "").trim();
  }
  function ferramentaCombinaTermo(row, termo) {
    return normalizarPesquisaFerramentas(
      [
        nomeEstoqueFerramenta(row),
        row.CategoriaEstoque,
        row.Modelo,
        row.ProdutosOrigem?.join(" ")
      ].join(" ")
    ).includes(termo);
  }
  function linhasLocalizacaoFerramentas() {
    const termo = normalizarPesquisaFerramentas(ferramentasBusca);
    if (!termo) return [];

    const openMatches = openTools.filter((row) =>
      normalizarPesquisaFerramentas(
        [
          row.Colaborador,
          row.Produto,
          row.CategoriaEstoque,
          row.NumeroRetirada
        ].join(" ")
      ).includes(termo)
    );
    const openRows = openMatches.map((row) => ({
      type: "person",
      code: row.CodigoProduto || "",
      product: row.Produto,
      quantity: n(row.QuantidadeEmAberto),
      holder: row.Colaborador || "Não informado",
      detail: row.DataRetirada ? `Retirada em ${row.DataRetirada}` : "Com colaborador",
      statusClass: row.StatusClasse,
      statusText: row.StatusTexto || row.Status || "Com colaborador"
    }));
    const openKeys = new Set(
      openMatches.map((row) => row.CodigoProduto || normalizarPesquisaFerramentas(row.Produto))
    );

    estoqueFerramentas()
      .filter((row) => {
        const code = codigoFerramenta(row);
        return (
          ferramentaCombinaTermo(row, termo) ||
          (code && openKeys.has(code)) ||
          openKeys.has(normalizarPesquisaFerramentas(nomeEstoqueFerramenta(row)))
        );
      })
      .forEach((row) => {
        const available = n(row.QtdeEstoque);
        if (available <= 0) return;
        openRows.push({
          type: "stock",
          code: codigoFerramenta(row),
          product: nomeEstoqueFerramenta(row),
          quantity: available,
          holder: "Almoxarifado",
          detail: "Disponível no estoque",
          statusClass: "stock",
          statusText: "Disponível"
        });
      });

    return openRows.sort((a, b) => {
      if (a.type !== b.type) return a.type === "person" ? -1 : 1;
      return normalizarPesquisaFerramentas(a.product).localeCompare(
        normalizarPesquisaFerramentas(b.product)
      );
    });
  }
  function renderLocalizacaoFerramentas() {
    const termo = normalizarPesquisaFerramentas(ferramentasBusca);
    if (!termo) return "";

    const rows = linhasLocalizacaoFerramentas();
    if (!rows.length) {
      return `<div class="tools-dropdown"><div class="tools-dropdown-empty">Nenhuma ferramenta ou colaborador encontrado para esta pesquisa.</div></div>`;
    }

    const total = rows.reduce((sum, row) => sum + n(row.quantity), 0);
    return `<div class="tools-dropdown"><div class="tools-dropdown-head"><span>${fmt(rows.length)} localização(ões) encontrada(s)</span><span>${fmt(total)} unidade(s)</span></div><div class="tools-dropdown-list">${rows
      .map(
        (row) =>
          `<div class="tools-location-row"><div><b>${esc(row.product)}</b><small>${esc(row.detail)}</small></div><strong>${fmt(row.quantity)} un.</strong><div><b>${esc(row.holder)}</b></div>${statusFerramentaBadge(row.statusClass, row.statusText)}</div>`
      )
      .join("")}</div></div>`;
  }
  function agruparFerramentasPorPessoa(arr) {
    let m = {};
    arr.forEach((r) => {
      let k = r.CodigoCliente || r.Colaborador || "Não informado";
      if (!m[k])
        m[k] = {
          codigo: k,
          nome: r.Colaborador || "Não informado",
          telefone: r.TelefoneWhatsApp || "",
          itens: [],
          qtd: 0,
          atrasados: 0,
          maisAntiga: "",
          maisAntigaISO: "",
          pior: "ok"
        };
      let p = m[k];
      p.itens.push(r);
      p.qtd += n(r.QuantidadeEmAberto);
      if (r.StatusClasse === "danger" && deveCobrarFerramenta(r)) {
        p.atrasados += n(r.QuantidadeEmAberto);
        p.pior = "danger";
      } else if (r.StatusClasse === "warn" && deveCobrarFerramenta(r) && p.pior !== "danger") p.pior = "warn";
      if (!p.maisAntigaISO || String(r.DataRetiradaISO || "") < p.maisAntigaISO) {
        p.maisAntigaISO = r.DataRetiradaISO || "";
        p.maisAntiga = r.DataRetirada || "";
      }
      if (!p.telefone && r.TelefoneWhatsApp) p.telefone = r.TelefoneWhatsApp;
    });
    return Object.values(m).sort(
      (a, b) =>
        b.atrasados - a.atrasados ||
        (a.maisAntigaISO || "9999").localeCompare(b.maisAntigaISO || "9999") ||
        a.nome.localeCompare(b.nome)
    );
  }
  function statusFerramentaBadge(cls, txt) {
    return `<span class="recommend-badge ${cls === "danger" ? "danger" : cls === "warn" ? "warn" : ""}">${esc(txt)}</span>`;
  }
  function tabelaFerramentasAbertas(arr) {
    let rows = arr
      .map(
        (r) =>
          `<tr><td data-label="Ferramenta">${esc(r.Produto)}</td><td data-label="Qtd. com a pessoa"><b>${fmt(r.QuantidadeEmAberto)}</b></td><td data-label="Retirada">${esc(r.DataRetirada)}</td><td data-label="Prazo">${esc(r.PrazoDevolucao)}</td><td data-label="Dias com o colaborador">${fmt(r.DiasFora)} dias</td><td data-label="Situação">${statusCobrancaFerramenta(r)}</td><td data-label="Nº retirada">${esc(r.NumeroRetirada)}</td><td data-label="Cobrança">${controlesLinhaFerramenta(r)}</td></tr>`
      )
      .join("");
    return `<div class="tablewrap"><table><thead><tr><th>Ferramenta</th><th>Qtd. com a pessoa</th><th>Retirada</th><th>Prazo</th><th>Dias com o colaborador</th><th>Situação</th><th>Nº retirada</th><th>Cobrança</th></tr></thead><tbody>${rows || '<tr><td colspan="8">Nenhum item em aberto.</td></tr>'}</tbody></table></div>`;
  }
  function abrirItensPessoaFerramentas(codigoEnc) {
    let codigo = decodeURIComponent(codigoEnc),
      p = agruparFerramentasPorPessoa(openTools).find(
        (x) => String(x.codigo) === codigo
      );
    if (!p) return;
    let atrasados = p.itens.filter(
      (r) => r.StatusClasse === "danger" && deveCobrarFerramenta(r)
    );
    modal.open(
      "Ferramentas com " + p.nome,
      `${fmt(p.qtd)} item(ns) em aberto · ${fmt(atrasados.reduce((a, r) => a + n(r.QuantidadeEmAberto), 0))} atrasado(s)`,
      tabelaFerramentasAbertas(p.itens)
    );
  }
  function mensagemWhatsAppFerramentas(p) {
    let atrasados = montarPlanoCobrancaFerramentas({
      openTools: p.itens,
      controlesCobranca,
      referenceDateISO: hojeISO()
    });
    let linhas = atrasados
      .slice(0, 8)
      .map(
        (r) =>
          `• ${r.Produto} — qtd. ${fmt(r.QuantidadeEmAberto)}, prazo ${r.PrazoDevolucao}`
      );
    if (atrasados.length > 8) linhas.push(`• e mais ${atrasados.length - 8} item(ns)`);
    let primeiro =
      String(p.nome || "")
        .trim()
        .split(/\s+/)[0] || "";
    return `Olá, ${primeiro}. Consta no almoxarifado que os seguintes itens estão com prazo de devolução vencido:\n\n${linhas.join("\n")}\n\nPoderia verificar, por favor?`;
  }
  function abrirWhatsAppFerramentas(codigoEnc) {
    const codigo = decodeURIComponent(codigoEnc);
    const pessoa = agruparFerramentasPorPessoa(openTools).find(
      (item) => String(item.codigo) === codigo
    );
    if (!pessoa || !pessoa.atrasados) return;
    whatsapp.open({
      phone: pessoa.telefone,
      message: mensagemWhatsAppFerramentas(pessoa)
    });
  }
  function cartaoPessoaFerramentas(p) {
    let temAtraso = p.atrasados > 0,
      acao =
        temAtraso && whatsapp.enabled
          ? p.telefone
            ? `<button class="btn green" type="button" data-action="tools-whatsapp" data-code="${encodeURIComponent(p.codigo)}">WhatsApp</button>`
            : `<button class="btn ghost" type="button" disabled title="Telefone não cadastrado">Sem telefone</button>`
          : "";
    return `<div class="panel" style="border-left:6px solid ${p.pior === "danger" ? "var(--critico)" : p.pior === "warn" ? "var(--alerta)" : "var(--ok)"};margin-bottom:12px"><div class="topbar" style="margin-bottom:8px"><div><h3>${esc(p.nome)}</h3><p class="muted">${fmt(p.itens.length)} tipo(s) de item · ${fmt(p.qtd)} unidade(s) em aberto${p.maisAntiga ? ` · retirada mais antiga: ${esc(p.maisAntiga)}` : ""}</p></div><div class="actions">${temAtraso ? statusFerramentaBadge("danger", fmt(p.atrasados) + " atrasado(s)") : statusFerramentaBadge(p.pior, p.pior === "warn" ? "Vence em breve" : "No prazo")}<button class="btn ghost" type="button" data-action="tools-view-person" data-code="${encodeURIComponent(p.codigo)}">Ver itens</button>${acao}</div></div></div>`;
  }
  function atualizarPesquisaFerramentas() {
    let input = documentRef.getElementById("ferramentasBuscaNome");
    if (input) ferramentasBusca = input.value;
    const localizacao = documentRef.getElementById("ferramentasLocalizacao");
    if (localizacao) localizacao.innerHTML = renderLocalizacaoFerramentas();
    let arr = ferramentasAbertasFiltradas(),
      pessoas = agruparFerramentasPorPessoa(arr),
      box = documentRef.getElementById("ferramentasResultados");
    if (!box) return;
    let total = arr.reduce((a, r) => a + n(r.QuantidadeEmAberto), 0),
      atrasados = arr
        .filter((r) => r.StatusClasse === "danger" && deveCobrarFerramenta(r))
        .reduce((a, r) => a + n(r.QuantidadeEmAberto), 0),
      semTelefone = pessoas.filter((p) => p.atrasados > 0 && !p.telefone).length,
      integracao = whatsapp.enabled
        ? `<div class="kpi"><span>Sem telefone</span><br><b>${fmt(semTelefone)}</b></div>`
        : `<div class="kpi kpi-contact"><span>Contato</span><b class="integration-name">n8n</b><small class="integration-status">WhatsApp direto desativado</small></div>`;
    box.innerHTML = `<div class="panel"><p class="leitura">Mostrando itens que continuam com colaboradores. Rastelos ficam como uso contínuo e não entram na cobrança automática. Use +7/+15 dias ou Não cobrar dentro de “Ver itens” para pausar cobranças sem apagar o histórico.</p><div class="kpis"><div class="kpi"><span>Pessoas com itens</span><br><b>${fmt(pessoas.length)}</b></div><div class="kpi"><span>Itens em aberto</span><br><b>${fmt(total)}</b></div><div class="kpi"><span>Itens para cobrar</span><br><b>${fmt(atrasados)}</b></div>${integracao}</div></div>${pessoas.length ? pessoas.map(cartaoPessoaFerramentas).join("") : `<div class="panel"><h2>Nenhum item encontrado</h2><p class="muted">Não há saldo em aberto para a pesquisa informada.</p></div>`}`;
  }
  function limparPesquisaFerramentas() {
    ferramentasBusca = "";
    let input = documentRef.getElementById("ferramentasBuscaNome");
    if (input) {
      input.value = "";
      input.focus();
    }
    atualizarPesquisaFerramentas();
  }
  function renderFerramentas() {
    documentRef.getElementById("genericTitle").textContent =
      "Equipamentos devolvíveis com colaboradores";
    documentRef.getElementById("genericSub").textContent =
      "Mostra apenas equipamentos que precisam retornar. Ferramentas fixas e materiais de consumo ficam fora da contagem.";
    documentRef.getElementById("genericContent").innerHTML =
      `<div class="panel"><h2>Pesquisar colaborador ou ferramenta</h2><p class="muted">Digite parte do nome da pessoa ou do equipamento. Itens devolvidos, ferramentas fixas e materiais de consumo não aparecem.</p><div class="tools-search-wrap"><div class="searchbar" style="grid-template-columns:minmax(0,1fr) auto"><input id="ferramentasBuscaNome" type="search" autocomplete="off" placeholder="Ex.: Nilton, martelete, escada..." value="${esc(ferramentasBusca)}" data-input-action="tools-search"><button class="btn ghost" type="button" data-action="tools-clear">Limpar pesquisa</button></div><div id="ferramentasLocalizacao"></div></div></div><div id="ferramentasResultados"></div>`;
    atualizarPesquisaFerramentas();
  }
  function atualizarModalPessoaPorItemKey(itemKey) {
    const item = openTools.find((row) => chaveFerramenta(row) === itemKey);
    if (item) abrirItensPessoaFerramentas(encodeURIComponent(item.CodigoCliente || item.Colaborador || "Não informado"));
  }
  function prorrogarFerramenta(itemKeyEnc, dias) {
    const itemKey = decodeURIComponent(itemKeyEnc);
    controlesCobranca[itemKey] = {
      ...controlesCobranca[itemKey],
      naoCobrar: false,
      prorrogadoAte: somarDiasISO(dias)
    };
    salvarControlesCobranca();
    registrarRegraCobrancaNoN8n(itemKey, {
      acao: "prorrogar",
      dias: Number(dias || 0),
      prorrogado_ate: controlesCobranca[itemKey].prorrogadoAte
    });
    atualizarPesquisaFerramentas();
    atualizarModalPessoaPorItemKey(itemKey);
  }
  function naoCobrarFerramenta(itemKeyEnc) {
    const itemKey = decodeURIComponent(itemKeyEnc);
    controlesCobranca[itemKey] = {
      ...controlesCobranca[itemKey],
      naoCobrar: true,
      prorrogadoAte: ""
    };
    salvarControlesCobranca();
    registrarRegraCobrancaNoN8n(itemKey, { acao: "nao_cobrar" });
    atualizarPesquisaFerramentas();
    atualizarModalPessoaPorItemKey(itemKey);
  }
  function voltarCobrarFerramenta(itemKeyEnc) {
    const itemKey = decodeURIComponent(itemKeyEnc);
    delete controlesCobranca[itemKey];
    salvarControlesCobranca();
    atualizarPesquisaFerramentas();
    atualizarModalPessoaPorItemKey(itemKey);
  }

  function getHomeMetrics() {
    const people = agruparFerramentasPorPessoa(openTools);
    const ferramentasParaCobrar = montarPlanoCobrancaFerramentas({
      openTools,
      controlesCobranca,
      referenceDateISO: hojeISO()
    });
    return {
      quantity: openTools.reduce((total, row) => total + n(row.QuantidadeEmAberto), 0),
      people: people.length,
      overdue: ferramentasParaCobrar
        .reduce((total, row) => total + n(row.QuantidadeEmAberto), 0)
    };
  }

  function getAutomationChargePlan() {
    return montarPlanoCobrancaFerramentas({
      openTools,
      controlesCobranca,
      referenceDateISO: hojeISO()
    });
  }

  return Object.freeze({
    render: renderFerramentas,
    search: atualizarPesquisaFerramentas,
    clear: limparPesquisaFerramentas,
    viewPerson: abrirItensPessoaFerramentas,
    openWhatsApp: abrirWhatsAppFerramentas,
    extend: prorrogarFerramenta,
    noCharge: naoCobrarFerramenta,
    charge: voltarCobrarFerramenta,
    getHomeMetrics,
    getAutomationChargePlan
  });
}
