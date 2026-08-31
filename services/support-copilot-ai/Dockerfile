FROM ghcr.io/astral-sh/uv:0.10.8@sha256:88234bc9e09c2b2f6d176a3daf411419eb0370d450a08129257410de9cfafd2a AS uv

FROM python:3.11.16-slim-trixie@sha256:1042b61448fef4ba92d16a8c7eb4996d027568ce64792a7877fd88511e0af7c6 AS build

COPY --from=uv /uv /uvx /bin/

WORKDIR /app
COPY services/support-copilot-ai/requirements.txt services/support-copilot-ai/requirements.lock.txt ./
RUN uv venv --python python3 /opt/venv \
    && uv pip sync --python /opt/venv/bin/python --require-hashes requirements.lock.txt

FROM python:3.11.16-slim-trixie@sha256:1042b61448fef4ba92d16a8c7eb4996d027568ce64792a7877fd88511e0af7c6

USER root
RUN apt-get update \
    && apt-get upgrade --yes \
    && python -m pip uninstall --yes setuptools pip \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 appuser \
    && useradd --create-home --shell /usr/sbin/nologin --uid 10001 --gid 10001 appuser \
    && install --directory --owner=10001 --group=10001 --mode=0750 /var/lib/support-copilot-ai

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
