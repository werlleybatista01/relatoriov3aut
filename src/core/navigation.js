/**
 * Navegação interna de uma aplicação de página única.
 *
 * O dashboard continua com um único index.html, mas a lógica de navegação
 * não fica misturada aos módulos de negócio.
 */
export function createNavigation(documentRef = document) {
  function showSection(id) {
    documentRef
      .querySelectorAll(".section")
      .forEach((section) => section.classList.remove("active"));

    const target = documentRef.getElementById(id);
    if (!target) {
      throw new Error(`Seção não encontrada: ${id}`);
    }

    target.classList.add("active");
    window.scrollTo(0, 0);
  }

  return Object.freeze({ showSection });
}
