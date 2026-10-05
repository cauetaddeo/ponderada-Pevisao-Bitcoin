"""Demonstra o fluxo HTTP real. Execute com o backend já iniciado."""

import csv
import json
import math
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parents[1]


def request(path, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(BASE_URL + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=10) as response:
            return response.status, response.read().decode("utf-8")
    except HTTPError as error:
        return error.code, error.read().decode("utf-8")


def main():
    status, html = request("/")
    assert status == 200 and "Previsão do Bitcoin" in html
    print("GET /: 200")

    status, body = request("/health")
    health = json.loads(body)
    assert status == 200 and health["model_loaded"] is True
    print(f"GET /health: {status} {body}")

    next_date = (date.fromisoformat(health["last_training_date"]) + timedelta(days=1)).isoformat()
    status, body = request("/predict", {"date": next_date})
    prediction = json.loads(body)
    assert status == 200 and prediction["date"] == next_date
    assert prediction["symbol"] == "BTC-USD" and prediction["currency"] == "USD"
    with (ROOT / "artifacts" / "previsao.csv").open(encoding="utf-8", newline="") as file:
        exported = next(csv.DictReader(file))
    assert exported["ds"] == next_date
    assert math.isclose(prediction["predicted_close"], float(exported["yhat"]), rel_tol=1e-9, abs_tol=1e-7)
    print(f"POST /predict: {status} {body}")

    status, _ = request("/predict", {"date": health["last_training_date"]})
    assert status == 400
    print("POST /predict com data fora do período: 400")

    status, _ = request("/predict", {"date": "data-invalida"})
    assert status == 422
    print("POST /predict com data inválida: 422")
    print("Integração HTTP concluída: previsão igual ao artefato exportado.")


if __name__ == "__main__":
    main()
