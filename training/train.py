"""Treina um Prophet com fechamentos diários de BTC-USD do Yahoo Finance."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf
from prophet import Prophet
from prophet.serialize import model_to_json


ROOT = Path(__file__).resolve().parents[1]
START_DATE = "2024-01-01"
TEST_DAYS = 30


def main():
    data_dir = ROOT / "data"
    artifacts_dir = ROOT / "artifacts"
    data_dir.mkdir(exist_ok=True)
    artifacts_dir.mkdir(exist_ok=True)
    yf.set_tz_cache_location(str(ROOT / ".cache" / "yfinance"))

    # 1. Baixar o histórico, excluindo o dia atual, que ainda não terminou em UTC.
    today = datetime.now(timezone.utc).date().isoformat()
    history = yf.download(
        "BTC-USD",
        start=START_DATE,
        end=today,
        interval="1d",
        auto_adjust=False,
        multi_level_index=False,
        threads=False,
        progress=False,
    )
    if history is None or history.empty:
        raise RuntimeError(
            "O Yahoo Finance não retornou dados. Verifique a conexão e tente novamente."
        )

    # 2. Prophet usa ds para a data (sem fuso horário) e y para o valor observado.
    data = history[["Close"]].reset_index().rename(columns={"Date": "ds", "Close": "y"})
    data["ds"] = pd.to_datetime(data["ds"], utc=True).dt.tz_localize(None)
    data["y"] = pd.to_numeric(data["y"], errors="coerce")
    data = data.dropna().drop_duplicates("ds").sort_values("ds").reset_index(drop=True)
    if len(data) < TEST_DAYS * 2:
        raise ValueError("São necessários pelo menos 60 fechamentos diários para treinar e avaliar.")
    data.to_csv(data_dir / "btc_usd.csv", index=False)

    # 3. Reservar os 30 últimos registros para uma avaliação cronológica.
    # Todas as datas de teste são previstas a partir de um único corte no histórico.
    train = data.iloc[:-TEST_DAYS]
    test = data.iloc[-TEST_DAYS:]
    evaluation_model = Prophet(daily_seasonality=False)
    evaluation_model.fit(train)
    evaluation = evaluation_model.predict(test[["ds"]])
    errors = test["y"].to_numpy() - evaluation["yhat"].to_numpy()
    metrics = {
        "test_observations": TEST_DAYS,
        "train_end": train["ds"].max().date().isoformat(),
        "test_start": test["ds"].min().date().isoformat(),
        "test_end": test["ds"].max().date().isoformat(),
        "mae_usd": float(abs(errors).mean()),
        "rmse_usd": float((errors**2).mean() ** 0.5),
    }

    # 4. Treinar o modelo final com todo o histórico e prever o dia seguinte.
    model = Prophet(daily_seasonality=False)
    model.fit(data)
    future = model.make_future_dataframe(periods=1, freq="D", include_history=False)
    prediction = model.predict(future)[["ds", "yhat", "yhat_lower", "yhat_upper"]]

    # 5. Salvar em JSON para que o backend possa carregar o modelo posteriormente.
    (artifacts_dir / "model.json").write_text(model_to_json(model), encoding="utf-8")
    (artifacts_dir / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    prediction.to_csv(artifacts_dir / "previsao.csv", index=False)

    print(f"Histórico: {len(data)} dias, de {data['ds'].min():%Y-%m-%d} a {data['ds'].max():%Y-%m-%d}")
    print(f"MAE no teste: US$ {metrics['mae_usd']:,.2f}")
    print(f"RMSE no teste: US$ {metrics['rmse_usd']:,.2f}")
    print("Previsão do fechamento do próximo dia em USD:")
    print(prediction.to_string(index=False))
    print(f"Modelo salvo em: {artifacts_dir / 'model.json'}")


if __name__ == "__main__":
    main()
