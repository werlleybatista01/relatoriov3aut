/**
 * Serviço de download.
 *
 * Não existe senha no JavaScript: qualquer segredo entregue ao navegador
 * pode ser inspecionado. A proteção real deve ser feita em um backend.
 */
export function createDownloadService(metadata) {
  function download() {
    if (!metadata.downloadUrl) {
      window.alert("O relatório ainda não foi gerado para esta versão de homologação.");
      return;
    }

    const anchor = document.createElement("a");
    anchor.href = metadata.downloadUrl;
    anchor.download = "";
    anchor.rel = "noopener";
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
  }

  return Object.freeze({ download });
}
