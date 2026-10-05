"""Testes HTTP da API usando o artefato real do treinamento."""

from datetime import timedelta

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend import main


@pytest.fixture
def client():
    # O contexto inicia o lifespan e carrega o mesmo modelo usado pela aplicação.
    with TestClient(main.app) as test_client:
        yield test_client


def test_health_reports_loaded_model(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["symbol"] == "BTC-USD"
    assert body["currency"] == "USD"
    history = pd.read_csv(main.MODEL_PATH.parent.parent / "data" / "btc_usd.csv")
    assert body["last_training_date"] == history["ds"].max()


def test_homepage_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Previsão do Bitcoin" in response.text
    assert 'id="prediction-form"' in response.text


@pytest.mark.parametrize(
    ("path", "content_type"),
    [("/static/app.js", "javascript"), ("/static/style.css", "text/css")],
)
def test_frontend_assets_are_served(client, path, content_type):
    response = client.get(path)
    assert response.status_code == 200
    assert content_type in response.headers["content-type"]


def test_predict_matches_training_export(client):
    # Compara a resposta HTTP com a previsão produzida pelo script de treinamento.
    exported = pd.read_csv(main.MODEL_PATH.parent / "previsao.csv").iloc[0]
    response = client.post("/predict", json={"date": exported["ds"]})
    assert response.status_code == 200
    body = response.json()
    assert body["date"] == exported["ds"]
    assert body["symbol"] == "BTC-USD"
    assert body["currency"] == "USD"
    assert body["predicted_close"] == pytest.approx(exported["yhat"], rel=1e-9, abs=1e-7)
    assert body["lower_bound"] < body["upper_bound"]
    assert body["interval_width"] == 0.8


@pytest.mark.parametrize("days", [0, -1, main.MAX_HORIZON_DAYS + 1])
def test_predict_rejects_dates_outside_horizon(client, days):
    requested_date = client.app.state.last_training_date + timedelta(days=days)
    response = client.post("/predict", json={"date": requested_date.isoformat()})
    assert response.status_code == 400


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"date": "data-invalida"},
        {"date": "2026-02-30"},
        {"date": None},
        {"date": "2026-10-05", "symbol": "ETH-USD"},
    ],
)
def test_predict_rejects_invalid_payloads(client, body):
    response = client.post("/predict", json=body)
    assert response.status_code == 422


def test_predict_accepts_last_allowed_date(client):
    requested_date = client.app.state.last_training_date + timedelta(days=main.MAX_HORIZON_DAYS)
    response = client.post("/predict", json={"date": requested_date.isoformat()})
    assert response.status_code == 200
    assert response.json()["date"] == requested_date.isoformat()


def test_startup_fails_without_model(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "MODEL_PATH", tmp_path / "missing.json")
    with pytest.raises(RuntimeError, match="Modelo não encontrado"):
        with TestClient(main.app):
            pass


def test_startup_fails_with_invalid_model(monkeypatch, tmp_path):
    invalid_model = tmp_path / "invalid.json"
    invalid_model.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(main, "MODEL_PATH", invalid_model)
    with pytest.raises(RuntimeError, match="arquivo do modelo é inválido"):
        with TestClient(main.app):
            pass
