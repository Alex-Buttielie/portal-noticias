FROM python:3.12-slim
WORKDIR /app
COPY apps/api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/api ./
EXPOSE 8000
CMD ["gunicorn","config.wsgi:application","--bind","0.0.0.0:8000","--workers","2"]
