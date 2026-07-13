/**
 * Serviço de WhatsApp.
 *
 * Por padrão o envio direto fica desativado. Em produção, prefira um endpoint
 * autenticado no n8n, para que telefone e regras de autorização não fiquem
 * expostos no HTML público.
 */
export function createWhatsAppService(features = {}) {
  const enabled = features.directWhatsAppEnabled === true;

  function open({ phone, message }) {
    if (!enabled) {
      window.alert(
        "O WhatsApp direto está desativado nesta versão. " +
          "Use a futura integração protegida pelo n8n."
      );
      return;
    }

    if (!phone) {
      window.alert("Telefone não cadastrado para este colaborador.");
      return;
    }

    const url =
      `https://wa.me/${encodeURIComponent(phone)}` +
      `?text=${encodeURIComponent(message)}`;
    window.open(url, "_blank", "noopener");
  }

  return Object.freeze({ enabled, open });
}
