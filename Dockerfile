FROM python:3.14-slim AS builder
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.1
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev --extra postgresql --extra pdf --no-editable

FROM python:3.14-slim
RUN groupadd --gid 10001 forge && useradd --uid 10001 --gid forge --create-home forge
WORKDIR /app
COPY --from=builder --chown=forge:forge /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER forge
EXPOSE 8090
CMD ["uvicorn", "forge_rag.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8090", "--no-access-log"]
