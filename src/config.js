/**
 * Configuração estática de apresentação.
 * Dados operacionais continuam no arquivo gerado em /data.
 */
export const CATEGORIES = Object.freeze([
  ["Ferramentas", "🛠️", "Ferramentas/equipamentos controlados"],
  ["Uniformes", "👕", "Retiradas de uniformes"],
  ["Botinas", "🥾", "Análise por tamanho e estoque"],
  ["Enxadas", "⛏️", "Retiradas de enxadas"],
  ["Sacolas", "🛍️", "Consumo, estoque e previsão"]
]);

export const EVENTS = Object.freeze([
  {
    id: "taboa",
    nome: "Festa Taboa Lascada",
    inicio: "08-01",
    fim: "08-03",
    forca: "alta",
    margem: 0.25,
    desc: "Evento forte. O histórico é usado para a margem sazonal."
  },
  {
    id: "evangelico",
    nome: "Dia do Evangélico",
    inicio: "08-25",
    fim: "08-25",
    forca: "alta",
    margem: 0.2,
    desc: "Feriado municipal com atenção elevada."
  },
  {
    id: "fatima",
    nome: "Nossa Senhora de Fátima",
    inicio: "05-13",
    fim: "05-13",
    forca: "media",
    margem: 0.1,
    desc: "Padroeira do município. Atenção moderada."
  },
  {
    id: "emancipacao",
    nome: "Emancipação do Município",
    inicio: "12-21",
    fim: "12-21",
    forca: "media",
    margem: 0.1,
    desc: "Feriado municipal de fim de ano."
  }
]);
