const CONFIG = {
  whatsappNumber: "5599999999999",
  brandName: "Attiva Cred",
};

const TRACKING_EVENTS = {
  viewContent: "ViewContent",
  startQuiz: "StartQuiz",
  question1: "Question1",
  question2: "Question2",
  question3: "Question3",
  qualifiedLead: "QualifiedLead",
  whatsappClick: "WhatsAppClick",
};

const questions = [
  {
    id: "clt",
    event: TRACKING_EVENTS.question1,
    kicker: "Perfil CLT",
    title: "Atualmente voce trabalha com carteira assinada?",
    helper: "Essa pergunta ajuda a direcionar a consulta para o produto correto.",
    options: ["Sim, trabalho registrado", "Nao trabalho registrado"],
  },
  {
    id: "tempo",
    event: TRACKING_EVENTS.question2,
    kicker: "Tempo no emprego",
    title: "Ha quanto tempo voce esta no emprego atual?",
    helper: "Nao precisa ser exato. Escolha a faixa mais proxima.",
    options: ["Menos de 3 meses", "3 a 6 meses", "6 a 12 meses", "Mais de 12 meses"],
  },
  {
    id: "renda",
    event: TRACKING_EVENTS.question3,
    kicker: "Faixa de renda",
    title: "Qual sua faixa aproximada de renda mensal?",
    helper: "Use uma estimativa. Nao pedimos comprovante nesta etapa.",
    options: ["Ate R$ 1.800", "R$ 1.801 a R$ 2.500", "R$ 2.501 a R$ 4.000", "Acima de R$ 4.000"],
  },
  {
    id: "objetivo",
    event: "Question4",
    kicker: "Objetivo da consulta",
    title: "O que voce quer fazer agora?",
    helper: "Isso ajuda o atendimento a continuar a conversa com mais contexto.",
    options: ["Consultar valor disponivel", "Reduzir parcelas", "Organizar dividas", "Apenas entender as opcoes"],
  },
];

const state = {
  currentQuestion: 0,
  answers: {},
};

const screens = {
  intro: document.querySelector('[data-screen="intro"]'),
  quiz: document.querySelector('[data-screen="quiz"]'),
  analysis: document.querySelector('[data-screen="analysis"]'),
  result: document.querySelector('[data-screen="result"]'),
};

const startButton = document.querySelector("[data-start]");
const backButton = document.querySelector("[data-back]");
const whatsappButton = document.querySelector("[data-whatsapp]");
const progress = document.querySelector("[data-progress]");
const stepLabel = document.querySelector("[data-step-label]");
const questionKicker = document.querySelector("[data-question-kicker]");
const questionTitle = document.querySelector("[data-question-title]");
const questionHelper = document.querySelector("[data-question-helper]");
const answerGrid = document.querySelector("[data-answer-grid]");
const summary = document.querySelector("[data-summary]");

function track(eventName, payload = {}) {
  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push({
    event: eventName,
    ...payload,
  });

  if (typeof window.fbq === "function") {
    window.fbq("trackCustom", eventName, payload);
  }

  console.info("[tracking-ready]", eventName, payload);
}

function showScreen(name) {
  Object.entries(screens).forEach(([screenName, element]) => {
    const active = screenName === name;
    element.hidden = !active;
    element.classList.toggle("screen-active", active);
  });
}

function renderQuestion() {
  const question = questions[state.currentQuestion];
  const step = state.currentQuestion + 1;
  const percentage = (step / questions.length) * 100;

  stepLabel.textContent = `Pergunta ${step} de ${questions.length}`;
  progress.style.width = `${percentage}%`;
  questionKicker.textContent = question.kicker;
  questionTitle.textContent = question.title;
  questionHelper.textContent = question.helper;
  answerGrid.innerHTML = "";

  question.options.forEach((option) => {
    const button = document.createElement("button");
    button.className = "answer-button";
    button.type = "button";
    button.textContent = option;
    button.addEventListener("click", () => answerQuestion(question, option));
    answerGrid.appendChild(button);
  });

  backButton.hidden = state.currentQuestion === 0;
  track(question.event, { step, question_id: question.id });
}

function answerQuestion(question, option) {
  state.answers[question.id] = option;

  if (state.currentQuestion < questions.length - 1) {
    state.currentQuestion += 1;
    renderQuestion();
    return;
  }

  showAnalysis();
}

function showAnalysis() {
  showScreen("analysis");

  window.setTimeout(() => {
    renderResult();
    showScreen("result");
    track(TRACKING_EVENTS.qualifiedLead, {
      clt: state.answers.clt,
      tempo: state.answers.tempo,
      renda: state.answers.renda,
      objetivo: state.answers.objetivo,
    });
  }, 1450);
}

function renderResult() {
  const labels = {
    clt: "Carteira assinada",
    tempo: "Tempo no emprego",
    renda: "Renda aproximada",
    objetivo: "Objetivo",
  };

  summary.innerHTML = "";
  Object.entries(labels).forEach(([key, label]) => {
    const item = document.createElement("li");
    item.textContent = `${label}: ${state.answers[key] || "Nao informado"}`;
    summary.appendChild(item);
  });
}

function buildWhatsAppUrl() {
  const message = [
    "Ola, quero continuar minha consulta de credito CLT.",
    `Carteira assinada: ${state.answers.clt || "Nao informado"}.`,
    `Tempo no emprego atual: ${state.answers.tempo || "Nao informado"}.`,
    `Faixa de renda: ${state.answers.renda || "Nao informado"}.`,
    `Objetivo: ${state.answers.objetivo || "Nao informado"}.`,
  ].join("\n");

  return `https://wa.me/${CONFIG.whatsappNumber}?text=${encodeURIComponent(message)}`;
}

startButton.addEventListener("click", () => {
  state.currentQuestion = 0;
  state.answers = {};
  showScreen("quiz");
  track(TRACKING_EVENTS.startQuiz);
  renderQuestion();
});

backButton.addEventListener("click", () => {
  if (state.currentQuestion === 0) return;
  state.currentQuestion -= 1;
  renderQuestion();
});

whatsappButton.addEventListener("click", () => {
  track(TRACKING_EVENTS.whatsappClick, {
    clt: state.answers.clt,
    tempo: state.answers.tempo,
    renda: state.answers.renda,
    objetivo: state.answers.objetivo,
  });

  window.location.href = buildWhatsAppUrl();
});

track(TRACKING_EVENTS.viewContent);
