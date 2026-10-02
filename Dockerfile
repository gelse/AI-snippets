FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends make \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir pyyaml ruff \
    && touch /opt/venv/.stamp
ENV VENV=/opt/venv
ENV PATH=/opt/venv/bin:$PATH

WORKDIR /opt/ai-snippets
COPY . /opt/ai-snippets

CMD ["make", "help"]
