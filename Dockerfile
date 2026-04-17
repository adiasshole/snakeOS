FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/snakeos
COPY pyproject.toml README.md ./
COPY snakeos ./snakeos
COPY config ./config

RUN pip3 install --no-cache-dir --break-system-packages .

RUN install -D -m0644 config/services.example.toml /etc/snakeos/services.toml

STOPSIGNAL SIGTERM

# Container PID 1: supervises child services from /etc/snakeos/services.toml
ENTRYPOINT ["python3", "-m", "snakeos", "init", "--config", "/etc/snakeos/services.toml"]
