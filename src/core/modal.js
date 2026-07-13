/**
 * Controlador do modal principal.
 */
export function createModal(documentRef = document) {
  const modal = documentRef.getElementById("modal");
  const title = documentRef.getElementById("modalTitle");
  const subtitle = documentRef.getElementById("modalSub");
  const body = documentRef.getElementById("modalBody");

  function open(modalTitle, modalSubtitle, modalBody) {
    title.textContent = modalTitle;
    subtitle.innerHTML = modalSubtitle;
    body.innerHTML = modalBody;
    modal.classList.add("on");
    modal.setAttribute("aria-hidden", "false");
  }

  function close() {
    modal.classList.remove("on");
    modal.setAttribute("aria-hidden", "true");
  }

  return Object.freeze({ open, close });
}
