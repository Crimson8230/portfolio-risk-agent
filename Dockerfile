FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements-lock.txt ./
RUN python -m pip install --no-cache-dir -r requirements-lock.txt

COPY portfolio/ ./portfolio/
COPY tools/ ./tools/
COPY agent/ ./agent/
COPY tests/ ./tests/
COPY cli.py pytest.ini ./
COPY data/assets.json data/sample_portfolio.json data/invalid_portfolio.json ./data/

USER 10001:10001

ENTRYPOINT ["python", "cli.py"]
CMD ["data/sample_portfolio.json"]
