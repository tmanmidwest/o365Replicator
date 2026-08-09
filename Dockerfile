FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_URL=sqlite:////data/o365replicator.db

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# SQLite lives on a mounted volume so records survive container restarts.
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8080/healthz').status==200 else 1)"

# Serves plain HTTP; Cloudflare (tunnel) terminates HTTPS at the edge.
# --proxy-headers + --forwarded-allow-ips lets the app trust Cloudflare's
# X-Forwarded-Proto/For headers so request.scheme reflects the public https
# (used for the connector URLs shown on the Access page). The origin is only
# reachable via the tunnel, so trusting all upstream IPs is acceptable here.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
