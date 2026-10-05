// Verifica o comportamento do cliente em um DOM simulado, com a API já rodando.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("../.cache/frontend-qa/node_modules/jsdom");

const root = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(root, "frontend/index.html"), "utf8");
const script = fs.readFileSync(path.join(root, "frontend/app.js"), "utf8");
const baseUrl = "http://127.0.0.1:8000";
const realFetch = (url, options) => fetch(new URL(url, baseUrl), options);

async function waitFor(check) {
  const deadline = Date.now() + 5000;
  while (!check()) {
    if (Date.now() > deadline) throw new Error("Tempo esgotado esperando a atualização do cliente.");
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
}

function createClient(fetchImplementation) {
  const dom = new JSDOM(html, { url: baseUrl, runScripts: "outside-only" });
  dom.window.fetch = (...args) => fetchImplementation(dom.window, ...args);
  dom.window.eval(script);
  return dom;
}

async function main() {
  const health = await (await realFetch("/health")).json();
  const expected = await (await realFetch("/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ date: new Date(Date.parse(health.last_training_date) + 86400000).toISOString().slice(0, 10) }),
  })).json();

  let predictionRequests = 0;
  const dom = createClient((window, url, options) => {
    if (url === "/predict") predictionRequests += 1;
    return realFetch(url, options);
  });
  try {
    const window = dom.window;
    const document = window.document;
    const input = document.querySelector("#date");
    const button = document.querySelector("#predict-button");
    const form = document.querySelector("#prediction-form");
    const result = document.querySelector("#result");
    await waitFor(() => !button.disabled);
    assert.equal(document.querySelector("#status").textContent, "Modelo disponível");
    assert.equal(input.value, expected.date);
    assert.equal(input.min, expected.date);
    assert.equal(input.max, new Date(Date.parse(health.last_training_date) + health.max_horizon_days * 86400000).toISOString().slice(0, 10));
    console.log("PASS: saúde da API define o período e a data inicial do formulário.");

    form.dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true }));
    assert.equal(button.disabled, true);
    await waitFor(() => !button.disabled && !result.hidden);
    const money = new window.Intl.NumberFormat("pt-BR", { style: "currency", currency: "USD" });
    assert.equal(document.querySelector("#predicted-close").textContent, money.format(expected.predicted_close));
    assert.equal(document.querySelector("#interval-label").textContent, "Intervalo de incerteza de 80%");
    assert.equal(predictionRequests, 1);
    assert.match(document.querySelector("#result-title").textContent, /UTC/);
    console.log("PASS: formulário chama o container e exibe o preço esperado em USD.");

    input.value = health.last_training_date;
    input.dispatchEvent(new window.Event("input", { bubbles: true }));
    assert.equal(result.hidden, true);
    assert.equal(input.checkValidity(), false);
    form.dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true }));
    assert.equal(predictionRequests, 1);
    console.log("PASS: alteração de data remove o resultado anterior e impede data fora do período.");

    input.value = input.max;
    window.fetch = async () => new Response(JSON.stringify({ detail: "Erro de previsão para teste." }), {
      status: 400, headers: { "Content-Type": "application/json" },
    });
    form.dispatchEvent(new window.Event("submit", { bubbles: true, cancelable: true }));
    await waitFor(() => !button.disabled && !document.querySelector("#error").hidden);
    assert.equal(document.querySelector("#error").textContent, "Erro de previsão para teste.");
    assert.equal(result.hidden, true);
    console.log("PASS: erro da API é exibido e libera o formulário para nova tentativa.");
  } finally {
    dom.window.close();
  }

  const offline = createClient(async (window) => { throw new window.TypeError("Failed to fetch"); });
  try {
    const document = offline.window.document;
    const retry = document.querySelector("#retry-button");
    await waitFor(() => !retry.hidden);
    assert.equal(document.querySelector("#date").disabled, true);
    assert.equal(document.querySelector("#status").textContent, "Serviço indisponível");
    offline.window.fetch = realFetch;
    retry.click();
    await waitFor(() => !document.querySelector("#predict-button").disabled);
    assert.equal(retry.hidden, true);
    assert.equal(document.querySelector("#status").textContent, "Modelo disponível");
    console.log("PASS: falha de conexão mostra nova tentativa, que recupera o formulário.");
  } finally {
    offline.window.close();
  }
  console.log("5 verificações do cliente concluídas em DOM simulado.");
}

main().catch((error) => { console.error(error); process.exitCode = 1; });
