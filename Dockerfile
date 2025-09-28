# Electronics HAL - Production Docker Image
# Multi-stage build for optimized container size

# Stage 1: Build environment
FROM python:3.11-slim as builder

# Install system dependencies for building
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    pkg-config \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install uv

# Set working directory
WORKDIR /build

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies in virtual environment
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN uv sync --frozen

# Stage 2: Runtime environment
FROM python:3.11-slim as runtime

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    # VISA runtime dependencies
    libusb-1.0-0 \
    libusb-dev \
    # For instrument communication
    udev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r hal && useradd -r -g hal -s /bin/bash hal

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=hal:hal . .

# Create necessary directories
RUN mkdir -p /app/logs /app/reports /app/test_data /app/monitoring_data /app/simulation_data \
    && chown -R hal:hal /app

# Switch to non-root user
USER hal

# Set Python path
ENV PYTHONPATH="/app:$PYTHONPATH"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import hal; print('HAL module loads successfully')" || exit 1

# Default command
CMD ["python", "-m", "hal.cli", "--help"]