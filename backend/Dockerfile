# Usa Python 3.12 em Linux, como no container de treinamento.
FROM python:3.12-slim-bookworm

# Evita arquivos .pyc e permite acompanhar os logs sem atraso.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Define a pasta de execução da aplicação dentro do container.
WORKDIR /app

# Copia primeiro as dependências para aproveitar o cache de construção.
COPY backend/requirements.txt ./requirements.txt

# Instala as bibliotecas necessárias para carregar o modelo e servir a API.
RUN python -m pip install --no-cache-dir -r requirements.txt

# Copia o código Python do backend para a imagem.
COPY backend/ ./backend/

# Copia a página cliente e seus arquivos CSS e JavaScript.
COPY frontend/ ./frontend/

# Documenta a porta usada pelo servidor; o Compose publica essa porta no host.
EXPOSE 8000

# Inicia o Uvicorn aceitando conexões pela rede do container.
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
