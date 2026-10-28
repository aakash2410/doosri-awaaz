FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Offline speech and embedding models for the browser simulator (~170 MB, fetched once at build).
RUN python -m engine.fetch_models --web
ENV DOOSRI_LOCKED_PACKS=class2-market-numbers
EXPOSE 8000
CMD ["sh", "-c", "uvicorn doosri.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
