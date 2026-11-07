FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir uv==0.13.0

WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY ific_guard ./ific_guard
COPY generetated-files/m4_satellite_filter.csv ./generetated-files/m4_satellite_filter.csv
COPY data/masks ./masks
ENV IFIC_MASK_DIR=/app/masks
RUN uv sync --frozen --no-dev

RUN useradd --create-home app && mkdir -p /app/data && chown -R app /app/data
USER app
ENV PATH="/app/.venv/bin:$PATH"
