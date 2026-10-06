FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY scraper/ scraper/
COPY web/ web/
COPY run.py .

# Scraped data persists in a mounted volume
RUN mkdir -p data
VOLUME /app/data

EXPOSE 5001

# Proxy config can be passed at runtime:
#   docker run -e ROTATING_PROXY=http://user:pass@host:port ...
# (environment variables take precedence over a mounted .env)
CMD ["python", "run.py", "--host", "0.0.0.0"]
