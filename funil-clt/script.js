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
  disqualifiedLead: "DisqualifiedLead",
  whatsappClick: "WhatsAppClick",
};

const questions = [
  {
    id: "clt",
    event: TRACKING_EVENTS.question1,
    kicker: "Perfil CLT",
    title: "Atualmente você trabalha com carteira assinada?",
    helper: "Essa resposta ajuda a direcionar a consulta para o produto correto.",
    options: ["Sim, trabalho registrado", "Não trabalho registrado"],
  },
  {
    id: "tempo",
    event: TRACKING_EVENTS.question2,
    kicker: "Tempo no emprego",
    title: "Há quanto tempo você está no emprego atual?",
    helper: "Para o crédito CLT, normalmente é necessário ter pelo menos 6 meses no emprego atual.",
    options: ["Menos de 3 meses", "3 a menos de 6 meses", "6 a 12 meses", "Mais de 12 meses"],
  },
  {
    id: "emprestimo",
    event: TRACKING_EVENTS.question3,
    kicker: "Empréstimo CLT",
    title: "Você já possui algum empréstimo CLT ativo?",
    helper: "Isso ajuda o atendimento a entender se é uma nova consulta ou uma possível reorganização.",
    options: [
      "Sim, há menos de 1 mês",
      "Sim, há mais de 1 mês",
      "Ainda não possuo empréstimo CLT ativo",
    ],
  },
  {
    id: "renda",
    event: "Question4",
    kicker: "Faixa de renda",
    title: "Qual sua faixa aproximada de renda mensal?",
    helper: "Use uma estimativa. Não pedimos comprovante nesta etapa.",
    options: ["Até R$ 1.800", "R$ 1.801 a R$ 2.500", "R$ 2.501 a R$ 4.000", "Acima de R$ 4.000"],
  },
  {
    id: "objetivo",
    event: "Question5",
    kicker: "Objetivo da consulta",
    title: "O que você quer fazer agora?",
    helper: "Essa resposta ajuda o atendimento a continuar a conversa com mais contexto.",
    options: ["Consultar valor disponível", "Reduzir parcelas", "Organizar dívidas", "Apenas entender as opções"],
  },
];

const state = {
  currentQuestion: 0,
  answers: {},
  eligible: false,
};

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

function isEligible() {
  const hasClt = state.answers.clt === "Sim, trabalho registrado";
  const hasMinimumTime = ["6 a 12 meses", "Mais de 12 meses"].includes(state.answers.tempo);

  return hasClt && hasMinimumTime;
}

function initQuiz() {
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
  const resultBadge = document.querySelector("[data-result-badge]");
  const resultTitle = document.querySelector("[data-result-title]");
  const resultCopy = document.querySelector("[data-result-copy]");

  function showScreen(name) {
    Object.entries(screens).forEach(([screenName, element]) => {
      const active = screenName === name;
      element.hidden = !active;
      element.classList.toggle("screen-active", active);
    });

    window.scrollTo({ top: 0, behavior: "smooth" });
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
      state.eligible = isEligible();
      renderResult();
      showScreen("result");

      const eventName = state.eligible
        ? TRACKING_EVENTS.qualifiedLead
        : TRACKING_EVENTS.disqualifiedLead;

      track(eventName, buildTrackingPayload());
    }, 1450);
  }

  function renderResult() {
    const labels = {
      clt: "Carteira assinada",
      tempo: "Tempo no emprego",
      emprestimo: "Empréstimo CLT ativo",
      renda: "Renda aproximada",
      objetivo: "Objetivo",
    };

    summary.innerHTML = "";
    Object.entries(labels).forEach(([key, label]) => {
      const item = document.createElement("li");
      item.textContent = `${label}: ${state.answers[key] || "Não informado"}`;
      summary.appendChild(item);
    });

    if (state.eligible) {
      resultBadge.textContent = "Consulta iniciada";
      resultTitle.textContent = "Pronto! Vamos continuar sua consulta.";
      resultCopy.textContent =
        "Para verificar as condições disponíveis para o seu perfil, continue pelo WhatsApp com suas respostas já organizadas.";
      whatsappButton.hidden = false;
      return;
    }

    resultBadge.textContent = "Perfil fora da regra CLT";
    resultTitle.textContent = "Neste momento, o crédito CLT pode não estar disponível.";
    resultCopy.textContent =
      "Pelas respostas informadas, o perfil não atende aos critérios básicos deste MVP. Para o crédito CLT, normalmente é necessário trabalhar registrado e ter pelo menos 6 meses no emprego atual.";
    whatsappButton.hidden = true;
  }

  function buildTrackingPayload() {
    return {
      clt: state.answers.clt,
      tempo: state.answers.tempo,
      emprestimo: state.answers.emprestimo,
      renda: state.answers.renda,
      objetivo: state.answers.objetivo,
      eligible: state.eligible,
    };
  }

  function buildWhatsAppUrl() {
    const message = [
      "Olá, quero continuar minha consulta de crédito CLT.",
      `Carteira assinada: ${state.answers.clt || "Não informado"}.`,
      `Tempo no emprego atual: ${state.answers.tempo || "Não informado"}.`,
      `Empréstimo CLT ativo: ${state.answers.emprestimo || "Não informado"}.`,
      `Faixa de renda: ${state.answers.renda || "Não informado"}.`,
      `Objetivo: ${state.answers.objetivo || "Não informado"}.`,
    ].join("\n");

    return `https://wa.me/${CONFIG.whatsappNumber}?text=${encodeURIComponent(message)}`;
  }

  startButton.addEventListener("click", () => {
    state.currentQuestion = 0;
    state.answers = {};
    state.eligible = false;
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
    track(TRACKING_EVENTS.whatsappClick, buildTrackingPayload());
    window.location.href = buildWhatsAppUrl();
  });

  track(TRACKING_EVENTS.viewContent);
}

document.addEventListener("DOMContentLoaded", initQuiz);
