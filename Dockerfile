FROM python:3.12-slim

# Runtime server parameters — all overridable via container/stack env vars.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATABASE_URL=sqlite:////data/o365replicator.db \
    HOST=0.0.0.0 \
    PORT=8080 \
    FORWARDED_ALLOW_IPS=* \
    WEB_CONCURRENCY=1 \
    LOG_LEVEL=info

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# SQLite lives on a mounted volume so records survive container restarts.
RUN mkdir -p /data
VOLUME ["/data"]

# Documentation only; the actual listen port is $PORT and Portainer maps it.
EXPOSE 8080

# Healthcheck honours $PORT so it keeps working when the port is overridden.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
  CMD python -c "import os,urllib.request,sys; p=os.environ.get('PORT','8080'); sys.exit(0 if urllib.request.urlopen('http://localhost:%s/healthz' % p).status==200 else 1)"

# Serves plain HTTP; Cloudflare (tunnel) terminates HTTPS at the edge.
# --proxy-headers + --forwarded-allow-ips lets the app trust Cloudflare's
# X-Forwarded-Proto/For headers so request.scheme reflects the public https
# (used for the connector URLs shown on the Access page). The origin is only
# reachable via the tunnel, so trusting all upstream IPs is acceptable here.
#
# Shell form with `exec` so env vars expand AND uvicorn becomes PID 1 (clean
# SIGTERM handling / fast container stop).
CMD ["sh", "-c", "exec uvicorn app.main:app --host \"$HOST\" --port \"$PORT\" --proxy-headers --forwarded-allow-ips \"$FORWARDED_ALLOW_IPS\" --workers \"$WEB_CONCURRENCY\" --log-level \"$LOG_LEVEL\""]
