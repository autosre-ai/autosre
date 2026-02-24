FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install kubectl
RUN curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
    && rm kubectl

# Copy project files
COPY pyproject.toml README.md ./
COPY sre_agent/ ./sre_agent/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Copy UI (pre-built)
COPY ui/dist/ ./ui/dist/

# Copy config and examples
COPY config/ ./config/
COPY examples/ ./examples/

# Expose port
EXPOSE 8080

# Run the application
CMD ["sre-agent", "ui", "--host", "0.0.0.0", "--port", "8080"]
