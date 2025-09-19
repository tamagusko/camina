# CAMINA Production Pipeline - Docker Image
# Optimized for RTX 3060 training and development

# Use NVIDIA PyTorch base image with CUDA support
FROM nvcr.io/nvidia/pytorch:23.08-py3

# Set working directory
WORKDIR /app

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV CUDA_VISIBLE_DEVICES=0

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    wget \
    curl \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libglib2.0-0 \
    libgl1-mesa-glx \
    libgthread-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install additional dependencies for production pipeline
RUN pip install --no-cache-dir \
    ultralytics>=8.0.200 \
    roboflow>=1.0.0 \
    wandb>=0.15.0 \
    tensorboard>=2.13.0 \
    onnx>=1.14.0 \
    onnxruntime-gpu>=1.15.0

# Copy source code
COPY . .

# Create necessary directories
RUN mkdir -p \
    /app/data \
    /app/models \
    /app/logs \
    /app/config \
    /app/output

# Set permissions
RUN chmod +x camina_dataset_creator.py camina_yolo11n_trainer.py

# Create non-root user for security
RUN useradd -m -u 1000 camina && \
    chown -R camina:camina /app

# Switch to non-root user
USER camina

# Expose ports for monitoring
EXPOSE 6006 8080

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=60s --retries=3 \
    CMD python -c "import torch; print(f'GPU available: {torch.cuda.is_available()}')" || exit 1

# Default command
CMD ["python", "--version"]

# Build-time metadata
LABEL maintainer="CAMINA Team"
LABEL description="CAMINA Production Pipeline - Urban Mobility Object Detection"
LABEL version="1.0.0"
LABEL cuda.version="11.8"
LABEL pytorch.version="2.0"

# Usage examples:
# Build: docker build -t camina-production .
#
# Dataset creation:
# docker run --gpus all -v /path/to/data:/app/data \
#   camina-production python camina_dataset_creator.py \
#   /app/data/images /app/data/output --validate
#
# Training:
# docker run --gpus all -v /path/to/data:/app/data \
#   camina-production python camina_yolo11n_trainer.py \
#   /app/data/dataset /app/data/training --edge-optimization
#
# Interactive development:
# docker run -it --gpus all -v /path/to/data:/app/data \
#   -p 6006:6006 -p 8080:8080 camina-production /bin/bash