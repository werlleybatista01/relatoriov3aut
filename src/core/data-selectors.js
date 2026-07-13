import { recordYear, sumQuantities, toNumber } from "./formatters.js";

/**
 * Cria seletores de dados a partir de um payload imutável.
 *
 * A interface não conhece a origem Access/Python; ela consome apenas
 * o contrato do arquivo data/dashboard-data.js.
 */
export function createDataSelectors(payload) {
  const metadata = payload.metadata;
  const withdrawals = Array.from(payload.withdrawals || []);
  const stock = Array.from(payload.stock || []);
  const openTools = Array.from(payload.openTools || []);

  function operationalRows() {
    return withdrawals.filter(
      (row) => recordYear(row) === Number(metadata.operatingYear)
    );
  }

  function seasonalRows() {
    const allowedYears = new Set([
      Number(metadata.seasonalHistoryYear),
      Number(metadata.operatingYear)
    ]);
    return withdrawals.filter((row) => allowedYears.has(recordYear(row)));
  }

  function byCategory(category) {
    return operationalRows().filter((row) => row.Categoria === category);
  }

  function seasonalByCategory(category) {
    return seasonalRows().filter((row) => row.Categoria === category);
  }

  function stockByCategory(category) {
    return stock.filter((row) => row.Categoria === category);
  }

  function stockTotal(category) {
    return stockByCategory(category).reduce(
      (total, row) => total + toNumber(row.QtdeEstoque),
      0
    );
  }

  return Object.freeze({
    metadata,
    features: payload.features || {},
    withdrawals,
    stock,
    openTools,
    operationalRows,
    seasonalRows,
    byCategory,
    seasonalByCategory,
    stockByCategory,
    stockTotal,
    sumQuantities
  });
}
