FROM ghcr.io/astral-sh/uv:0.10.8@sha256:88234bc9e09c2b2f6d176a3daf411419eb0370d450a08129257410de9cfafd2a AS uv

FROM python:3.11.16-alpine3.24@sha256:cc19a3e1085aba7d26690cf0725d9a3e083cbea0feec34ba8133d40a8ac1d399 AS build

COPY --from=uv /uv /uvx /bin/

WORKDIR /app
COPY services/support-copilot-ai/requirements.txt services/support-copilot-ai/requirements.lock.txt ./
RUN uv venv --python python3 /opt/venv \
    && uv pip sync --python /opt/venv/bin/python --require-hashes requirements.lock.txt

FROM python:3.11.16-alpine3.24@sha256:cc19a3e1085aba7d26690cf0725d9a3e083cbea0feec34ba8133d40a8ac1d399

# Alpine's setpriv package is sourced from util-linux and serves the Compose privilege drop.
# The official Python base bundles pip and setuptools, but runtime uses only /opt/venv.
RUN apk add --no-cache setpriv=2.42.3-r1 \
    && python -m pip uninstall --yes pip setuptools \
    && addgroup -g 10001 appuser \
    && adduser -D -H -s /sbin/nologin -u 10001 -G appuser appuser \
    && mkdir -p /var/lib/support-copilot-ai \
    && chown appuser:appuser /var/lib/support-copilot-ai \
    && chmod 0750 /var/lib/support-copilot-ai

WORKDIR /app
COPY --from=build --chown=10001:10001 /opt/venv /opt/venv
COPY --chown=10001:10001 services/support-copilot-ai/app ./app

ENV PATH=/opt/venv/bin:$PATH \
    EMBEDDING_ARTIFACT_ROOT=/var/lib/support-copilot-ai \
    EMBEDDING_ARTIFACT_BUILD_POLICY=require-active

VOLUME ["/var/lib/support-copilot-ai"]

USER 10001:10001
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
