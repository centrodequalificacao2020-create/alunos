# syntax=docker/dockerfile:1
# ───────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# Evita arquivos .pyc e garante logs em tempo real
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependências de sistema necessárias para o reportlab (geração de PDF)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfreetype6 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Camada de dependências Python (cacheada enquanto requirements.txt não mudar) ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Código da aplicação (camada que muda com cada git pull) ──
COPY . .

# Usuário não-root por segurança
RUN groupadd -r cqp && useradd --no-log-init -r -g cqp cqp \
    && mkdir -p /data && chown cqp:cqp /data
USER cqp

EXPOSE 5000

# 2 workers = ideal para 2 núcleos físicos do i5-3210M
CMD ["gunicorn", "--workers", "2", "--bind", "0.0.0.0:5000", \
     "--access-logfile", "-", "--error-logfile", "-", "app:app"]
