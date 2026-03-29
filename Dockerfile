FROM python:3.11-slim

# Install ffmpeg for audio conversion
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create downloads directory
RUN mkdir -p /app/downloads

CMD ["python", "bot.py"]
