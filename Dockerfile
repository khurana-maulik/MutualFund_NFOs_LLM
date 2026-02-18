# Use Python 3.13 slim image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Copy requirements first (for layer caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Set environment variables
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Download Ollama model on build (optional, can be done at runtime)
RUN ollama serve & sleep 5 && ollama pull qwen2.5 && pkill ollama

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

# Start Ollama in background and run Streamlit
CMD ollama serve & sleep 3 && streamlit run app.py
