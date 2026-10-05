"""API que carrega o modelo salvo e fornece previsões de BTC-USD."""

from contextlib import asynccontextmanager
from datetime import date as Date, timedelta
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from prophet.serialize import model_from_json
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "artifacts" / "model.json"
FRONTEND_PATH = ROOT / "frontend"
MAX_HORIZON_DAYS = 30


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: Date = Field(description="Data do fechamento em UTC, no formato YYYY-MM-DD.")


class PredictResponse(BaseModel):
    symbol: str
    currency: str
    date: Date
    predicted_close: FiniteFloat
    lower_bound: FiniteFloat
    upper_bound: FiniteFloat
    interval_width: float


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Carrega o modelo uma única vez, antes de começar a atender requisições.
    if not MODEL_PATH.is_file():
        raise RuntimeError(
            f"Modelo não encontrado em {MODEL_PATH}. "
            "Execute primeiro: docker compose run --rm training"
        )
    try:
        model = model_from_json(MODEL_PATH.read_text(encoding="utf-8"))
    except (ValueError, KeyError, TypeError) as error:
        raise RuntimeError("O arquivo do modelo é inválido. Execute o treinamento novamente.") from error

    app.state.model = model
    app.state.last_training_date = model.history["ds"].max().date()
    try:
        yield
    finally:
        app.state.model = None


app = FastAPI(title="Predição de BTC-USD", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=FRONTEND_PATH), name="static")


@app.get("/", include_in_schema=False)
def index():
    """Entrega a página cliente pelo mesmo endereço da API."""
    return FileResponse(FRONTEND_PATH / "index.html", media_type="text/html")


@app.get("/health")
def health(request: Request):
    """Indica que a API iniciou com o modelo carregado."""
    return {
        "status": "ok",
        "model_loaded": request.app.state.model is not None,
        "symbol": "BTC-USD",
        "currency": "USD",
        "last_training_date": request.app.state.last_training_date,
        "max_horizon_days": MAX_HORIZON_DAYS,
    }


@app.post("/predict", response_model=PredictResponse)
def predict(body: PredictRequest, request: Request):
    """Prevê uma data futura usando somente o modelo já treinado."""
    last_date = request.app.state.last_training_date
    max_date = last_date + timedelta(days=MAX_HORIZON_DAYS)
    if not last_date < body.date <= max_date:
        raise HTTPException(
            status_code=400,
            detail=(
                f"A data deve estar entre {last_date + timedelta(days=1)} e {max_date}, "
                "após o último fechamento usado no treinamento."
            ),
        )

    future = pd.DataFrame({"ds": [pd.Timestamp(body.date)]})
    model = request.app.state.model
    result = model.predict(future).iloc[0]
    return {
        "symbol": "BTC-USD",
        "currency": "USD",
        "date": body.date,
        "predicted_close": float(result["yhat"]),
        "lower_bound": float(result["yhat_lower"]),
        "upper_bound": float(result["yhat_upper"]),
        "interval_width": model.interval_width,
    }
