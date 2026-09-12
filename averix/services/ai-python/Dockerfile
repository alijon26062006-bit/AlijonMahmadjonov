# The analysis service.
#
# Never exposed publicly: it sits behind the API, reachable only from it, and
# authenticated by a shared token on every request.

FROM python:3.12-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# A virtual environment copied wholesale into the runtime stage, so the
# runtime has no build tooling in it.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt ./
RUN pip install --require-hashes --no-deps -r requirements.txt 2>/dev/null \
 || pip install -r requirements.txt

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# curl is the only extra: the container's own health check uses it.
RUN apt-get update \
 && apt-get install --no-install-recommends -y curl \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10001 --create-home averix

COPY --from=build /opt/venv /opt/venv

WORKDIR /app
COPY --chown=averix:averix app ./app

USER averix
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# One worker per container; scale by adding containers rather than threads,
# so a slow model call cannot starve the others.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers"]
