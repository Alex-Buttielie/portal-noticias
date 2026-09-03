FROM python:3.12-slim

# Impede a criação de .pyc e força stdout/stderr sem buffer — logs aparecem
# imediatamente em `docker compose logs` (essencial para diagnosticar em
# produção, ver LOGGING em config/settings.py).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# curl é usado pelo HEALTHCHECK abaixo. Nada além disso é necessário nesta
# imagem porque psycopg2-binary já traz binário pré-compilado (dispensa
# libpq-dev/gcc, mantendo a imagem pequena).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Usuário não-root — rodar como root dentro do container amplia
# desnecessariamente o blast radius de qualquer RCE na aplicação ou numa
# dependência.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/staticfiles /app/media \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "60"]
