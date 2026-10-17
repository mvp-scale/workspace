FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY nr ./nr
COPY catalogue.csv .
ENV NR_DB=/data/queue.sqlite NR_PORT=8140
EXPOSE 8140
# serve.py binds 127.0.0.1 for the dev container; in Docker publish through the host network or set a bind via a reverse proxy
CMD ["python", "-m", "nr.serve"]
