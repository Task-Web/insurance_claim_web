FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /uvx /bin/

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    UV_DEFAULT_INDEX=https://pypi.org/simple \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY app ./app
RUN printf '%s\n' '# Insurance Claim State' > ./STATE.md

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
