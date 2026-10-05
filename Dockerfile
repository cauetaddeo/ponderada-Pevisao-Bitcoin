# Usa uma imagem Linux baseada no Debian Bookworm, com Python 3.12 e tamanho reduzido.
FROM python:3.12-slim-bookworm

# PYTHONDONTWRITEBYTECODE evita a criação de arquivos de bytecode (.pyc).
# PYTHONUNBUFFERED faz os logs do Python aparecerem imediatamente no terminal.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Define /app como diretório de trabalho para os próximos comandos e para o treinamento.
WORKDIR /app

# Copia a lista de dependências para /app antes do código, permitindo reutilizar a camada de instalação.
COPY requirements.txt ./

# Instala as dependências durante a construção da imagem, sem guardar o cache de downloads do pip.
RUN python -m pip install --no-cache-dir -r requirements.txt

# Copia os scripts de treinamento do projeto para /app/training dentro da imagem.
COPY training/ ./training/

# Executa o treinamento quando o container é iniciado; ao terminar o script, o container encerra.
CMD ["python", "training/train.py"]
