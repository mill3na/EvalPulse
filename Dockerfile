# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip wheel --wheel-dir /wheels .

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN useradd --create-home --shell /usr/sbin/nologin evalpulse \
 && mkdir -p /data \
 && chown evalpulse:evalpulse /data
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-index --find-links=/wheels evalpulse && rm -rf /wheels
COPY src ./src
COPY .streamlit ./.streamlit
USER evalpulse
EXPOSE 8000 8501
CMD ["uvicorn", "evalpulse.api:app", "--host", "0.0.0.0", "--port", "8000"]
