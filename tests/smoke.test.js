import test from "node:test";
import assert from "node:assert/strict";

import { demoDashboardData } from "../data/dashboard-data.demo.js";
import { createDataSelectors } from "../src/core/data-selectors.js";
import { createComponents } from "../src/core/components.js";
import { createToolsModule } from "../src/modules/tools.js";
import { createBootsModule } from "../src/modules/boots.js";
import { createBagsModule } from "../src/modules/bags.js";
import { createGenericModule } from "../src/modules/generic.js";
import { createHomeModule } from "../src/modules/home.js";

class FakeClassList {
  add() {}
  remove() {}
}

class FakeElement {
  constructor(id = "") {
    this.id = id;
    this.innerHTML = "";
    this.textContent = "";
    this.value = "";
    this.classList = new FakeClassList();
    this.dataset = {};
  }

  setAttribute() {}
  addEventListener() {}
  focus() {}
  insertAdjacentHTML(_position, html) {
    this.innerHTML += html;
  }
}

class FakeDocument {
  constructor() {
    this.elements = new Map();
    [
      "homeCards",
      "genericTitle",
      "genericSub",
      "genericContent",
      "botinasContent",
      "sacolasContent",
      "ferramentasBuscaNome",
      "ferramentasResultados",
      "modal",
      "modalTitle",
      "modalSub",
      "modalBody"
    ].forEach((id) => this.elements.set(id, new FakeElement(id)));
  }

  getElementById(id) {
    if (!this.elements.has(id)) {
      this.elements.set(id, new FakeElement(id));
    }
    return this.elements.get(id);
  }

  querySelectorAll() {
    return [];
  }

  addEventListener() {}
}

test("módulos principais renderizam com massa sintética", () => {
  globalThis.window = {
    alert() {},
    open() {},
    scrollTo() {}
  };

  const documentRef = new FakeDocument();
  const selectors = createDataSelectors(demoDashboardData);
  const components = createComponents({
    bagsPerPackage: selectors.metadata.bagsPerPackage
  });
  const modal = {
    open() {},
    close() {}
  };
  const whatsapp = {
    enabled: false,
    open() {}
  };

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

  home.render();
  generic.render("Uniformes");
  tools.render();
  documentRef.getElementById("ferramentasBuscaNome").value = "escada";
  tools.search();
  boots.render();
  bags.render();

  assert.match(documentRef.getElementById("homeCards").innerHTML, /Botinas/);
  assert.match(
    documentRef.getElementById("botinasContent").innerHTML,
    /Prioridades por modelo e tamanho/
  );
  const bagsHtml = documentRef.getElementById("sacolasContent").innerHTML;
  assert.match(bagsHtml, /Decisão automática · Sacolas/);
  assert.match(bagsHtml, /Estoque atual/);
  assert.match(bagsHtml, /Insights importantes/);
  assert.doesNotMatch(bagsHtml, /bags-filterbar/);
  const toolLocationHtml = documentRef.getElementById("ferramentasLocalizacao").innerHTML;
  assert.match(toolLocationHtml, /COLABORADOR TESTE/);
  assert.match(toolLocationHtml, /Almoxarifado/);
});
