/**
 * Massa sintética para desenvolvimento e testes manuais.
 * Nenhum registro corresponde a uma pessoa real.
 */
export const demoDashboardData = Object.freeze({
  schemaVersion: 2,
  metadata: Object.freeze({
    generatedAt: "10/07/2026 12:00:00",
    referenceDate: "2026-07-10",
    periodStart: "01/01/2026",
    periodEnd: "10/07/2026",
    operatingYear: 2026,
    seasonalHistoryYear: 2025,
    bagsPerPackage: 100,
    downloadUrl: ""
  }),
  features: Object.freeze({
    directWhatsAppEnabled: false,
    personalDataIncluded: false,
    homologationMode: true
  }),
  withdrawals: Object.freeze([
    Object.freeze({
      Item: "1",
      "Nome do Produto": "BOTINA DE SEGURANÇA 42",
      Qtde: "2",
      "Unidade Medida": "UN",
      Requisitante: "COLABORADOR TESTE",
      Data_fmt: "10/01/2026",
      Data_iso: "2026-01-10",
      Ano: 2026,
      Mes: "2026-01",
      DiaSemana: "Sábado",
      Status: "",
      Observação: "",
      "Nº Retirada": "TESTE-001",
      "Responsável pelo Registro": "TESTE",
      Categoria: "Botinas",
      Modelo: "Botina de segurança",
      Tamanho: "42",
      Qtde_num: 2,
      Pacotes_num: 0
    }),
    Object.freeze({
      Item: "2",
      "Nome do Produto": "SACOLA PARA COLETA",
      Qtde: "100",
      "Unidade Medida": "sacolas",
      Requisitante: "COLABORADOR TESTE",
      Data_fmt: "15/02/2026",
      Data_iso: "2026-02-15",
      Ano: 2026,
      Mes: "2026-02",
      DiaSemana: "Domingo",
      Status: "",
      Observação: "",
      "Nº Retirada": "TESTE-002",
      "Responsável pelo Registro": "TESTE",
      Categoria: "Sacolas",
      Modelo: "",
      Tamanho: "",
      Qtde_num: 100,
      Pacotes_num: 1
    })
  ]),
  stock: Object.freeze([
    Object.freeze({
      Categoria: "Botinas",
      Modelo: "Botina de segurança",
      Tamanho: "42",
      "Nome do Produto": "Botina de segurança - tamanho 42",
      QtdeEstoque: 8,
      EstoqueMin: 3,
      PacotesEstoque: 0,
      PacotesMin: 0,
      SacolasPorPacote: 0,
      ProdutosOrigem: ["BOTINA DE SEGURANÇA 42"]
    }),
    Object.freeze({
      Categoria: "Sacolas",
      Modelo: "",
      Tamanho: "",
      "Nome do Produto": "SACOLA PARA COLETA",
      QtdeEstoque: 1200,
      EstoqueMin: 300,
      PacotesEstoque: 12,
      PacotesMin: 3,
      SacolasPorPacote: 100,
      ProdutosOrigem: ["SACOLA PARA COLETA"]
    })
  ]),
  openTools: Object.freeze([])
});
