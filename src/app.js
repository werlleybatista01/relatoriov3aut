import { dashboardData } from "../data/dashboard-data.js";
import { escapeHtml } from "./core/formatters.js";
import { createDataSelectors } from "./core/data-selectors.js";
import { createComponents } from "./core/components.js";
import { createNavigation } from "./core/navigation.js";
import { createModal } from "./core/modal.js";
import { createDownloadService } from "./services/download-service.js";
import { createWhatsAppService } from "./services/whatsapp-service.js";
import { createToolsModule } from "./modules/tools.js";
import { createBootsModule } from "./modules/boots.js";
import { createBagsModule } from "./modules/bags.js";
import { createGenericModule } from "./modules/generic.js";
import { createHomeModule } from "./modules/home.js";

/**
 * Compõe os módulos da aplicação.
 *
 * Este arquivo conhece as dependências entre os módulos, mas não implementa
 * regras de estoque, classificação ou apresentação específica.
 */
export function createDashboardApp(payload = dashboardData, documentRef = document) {
  if (!payload || payload.schemaVersion !== 2) {
    throw new Error("Formato de dados incompatível. Esperado schemaVersion 2.");
  }

  const selectors = createDataSelectors(payload);
  const components = createComponents({
    bagsPerPackage: selectors.metadata.bagsPerPackage
  });
  const navigation = createNavigation(documentRef);
  const modal = createModal(documentRef);
  const download = createDownloadService(selectors.metadata);
  const whatsapp = createWhatsAppService(selectors.features);

  const tools = createToolsModule({
    selectors,
    modal,
    whatsapp,
    documentRef
  });

  const boots = createBootsModule({
    selectors,
    components,
    modal,
    documentRef
  });

  const bags = createBagsModule({
    selectors,
    components,
    modal,
    documentRef
  });

  const generic = createGenericModule({
    selectors,
    components,
    tools,
    documentRef
  });

  const home = createHomeModule({
    selectors,
    tools,
    documentRef
  });

  function updateHeader() {
    const { metadata } = selectors;
    const period = documentRef.getElementById("periodoHeader");
    const generated = documentRef.getElementById("geradoHeader");

    if (period) {
      period.textContent = [
        metadata.periodStart || "—",
        "a",
        metadata.periodEnd || "—",
        `· operacional ${metadata.operatingYear}`
      ].join(" ");
    }

    if (generated) {
      generated.textContent = metadata.generatedAt || "Ainda não gerado";
    }
  }

  function openCategory(category) {
    if (category === "Botinas") {
      boots.render();
      navigation.showSection("botinas");
      return;
    }

    if (category === "Sacolas") {
      bags.render();
      navigation.showSection("sacolas");
      return;
    }

    generic.render(category);
    navigation.showSection("generic");
  }

  function handleAction(element) {
    const action = element.dataset.action;

    switch (action) {
      case "open-category":
        openCategory(element.dataset.category);
        break;
      case "navigate-home":
        navigation.showSection("home");
        break;
      case "download-report":
        download.download();
        break;
      case "modal-close":
        modal.close();
        break;
      case "tools-whatsapp":
        tools.openWhatsApp(element.dataset.code);
        break;
      case "tools-view-person":
        tools.viewPerson(element.dataset.code);
        break;
      case "tools-clear":
        tools.clear();
        break;
      case "boots-filter":
        boots.setFilter(element.dataset.model);
        break;
      case "boots-item":
        boots.openItem(element.dataset.key);
        break;
      case "boots-person":
        boots.openPerson(element.dataset.value);
        break;
      case "bags-person":
        bags.openPerson(element.dataset.value);
        break;
      case "bags-event":
        bags.openEvent(element.dataset.eventId);
        break;
      default:
        break;
    }
  }

  function bindEvents() {
    documentRef.addEventListener("click", (event) => {
      const element = event.target.closest("[data-action]");
      if (!element) return;
      event.preventDefault();
      handleAction(element);
    });

    documentRef.addEventListener("input", (event) => {
      const element = event.target.closest("[data-input-action]");
      if (!element) return;
      if (element.dataset.inputAction === "tools-search") {
        tools.search();
      }
    });

    documentRef.addEventListener("keydown", (event) => {
      if (!["Enter", " "].includes(event.key)) return;
      const element = event.target.closest('[role="button"][data-action]');
      if (!element) return;
      event.preventDefault();
      handleAction(element);
    });

    documentRef.getElementById("modal")?.addEventListener("click", (event) => {
      if (event.target.id === "modal") modal.close();
    });
  }

  function renderFatalError(error) {
    const homeSection = documentRef.getElementById("home");
    if (!homeSection) return;

    const message = escapeHtml(error instanceof Error ? error.message : String(error));
    homeSection.insertAdjacentHTML(
      "afterbegin",
      `<div class="app-error">
        <b>Não foi possível iniciar o dashboard.</b><br>${message}
      </div>`
    );
  }

  function init() {
    try {
      updateHeader();
      bindEvents();
      home.render();
    } catch (error) {
      console.error(error);
      renderFatalError(error);
    }
  }

  return Object.freeze({ init });
}
