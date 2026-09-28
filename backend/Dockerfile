FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir --upgrade pip \
	&& uv sync --frozen --no-dev

COPY . .

EXPOSE 3000

ENV PYTHONPATH=/app/src

CMD ["uv", "run", "--no-sync", "python", "-m", "src.main"]
