const form = document.querySelector("#prediction-form");
const dateInput = document.querySelector("#date");
const button = document.querySelector("#predict-button");
const status = document.querySelector("#status");
const error = document.querySelector("#error");
const result = document.querySelector("#result");
const retryButton = document.querySelector("#retry-button");
const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "USD" });
const dates = new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC" });

// Usa UTC para manter a mesma data do fechamento informada pela API.
function addDays(isoDate, days) {
  const date = new Date(`${isoDate}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function formatDate(isoDate) {
  return dates.format(new Date(`${isoDate}T00:00:00Z`));
}

async function readResponse(response) {
  const data = await response.json();
  if (!response.ok) {
    throw new Error(typeof data.detail === "string" ? data.detail : "Confira a data informada e tente novamente.");
  }
  return data;
}

async function loadHealth() {
  dateInput.disabled = true;
  button.disabled = true;
  result.hidden = true;
  error.hidden = true;
  retryButton.hidden = true;
  status.textContent = "Conectando…";
  status.className = "status";
  try {
    const health = await readResponse(await fetch("/health"));
    if (!health.model_loaded) throw new Error("O modelo ainda não está disponível.");
    dateInput.min = addDays(health.last_training_date, 1);
    dateInput.max = addDays(health.last_training_date, health.max_horizon_days);
    dateInput.value = dateInput.min;
    document.querySelector("#history").textContent = `Modelo treinado com fechamentos até ${formatDate(health.last_training_date)}.`;
    document.querySelector("#range").textContent = `Período disponível: ${formatDate(dateInput.min)} a ${formatDate(dateInput.max)}.`;
    status.textContent = "Modelo disponível";
    status.className = "status ready";
    dateInput.disabled = false;
    button.disabled = false;
  } catch (failure) {
    status.textContent = "Serviço indisponível";
    status.className = "status offline";
    document.querySelector("#history").textContent = "Não foi possível consultar o modelo.";
    document.querySelector("#range").textContent = "";
    error.textContent = failure instanceof TypeError ? "Não foi possível conectar à API. Verifique se o servidor está rodando." : failure.message;
    error.hidden = false;
    retryButton.hidden = false;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!form.reportValidity()) return;
  error.hidden = true;
  result.hidden = true;
  button.disabled = true;
  button.textContent = "Calculando…";
  dateInput.disabled = true;
  try {
    const prediction = await readResponse(await fetch("/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ date: dateInput.value }),
    }));
    document.querySelector("#result-title").textContent = `Fechamento de ${formatDate(prediction.date)} (UTC)`;
    document.querySelector("#predicted-close").textContent = money.format(prediction.predicted_close);
    document.querySelector("#lower-bound").textContent = money.format(prediction.lower_bound);
    document.querySelector("#upper-bound").textContent = money.format(prediction.upper_bound);
    document.querySelector("#interval-label").textContent = `Intervalo de incerteza de ${Math.round(prediction.interval_width * 100)}%`;
    result.hidden = false;
  } catch (failure) {
    error.textContent = failure instanceof TypeError ? "Falha de conexão. Tente consultar novamente." : failure.message;
    error.hidden = false;
  } finally {
    dateInput.disabled = false;
    button.disabled = false;
    button.textContent = "Consultar previsão";
  }
});

// Esconde a previsão anterior quando a data é alterada.
dateInput.addEventListener("input", () => { result.hidden = true; error.hidden = true; });
retryButton.addEventListener("click", loadHealth);
loadHealth();
