FROM python:3.11-slim-bookworm

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies for PyQt6, Xvfb, VNC, noVNC, and Google Chrome
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    x11vnc \
    novnc \
    websockify \
    openbox \
    # PyQt6 / Qt dependencies
    libgl1-mesa-dri \
    libgl1-mesa-glx \
    libegl1 \
    libx11-xcb1 \
    libxcb-cursor0 \
    libxcb-shape0 \
    libxcb-xfixes0 \
    libxcb-shm0 \
    libxcb-sync1 \
    libglib2.0-0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxkbcommon-x11-0 \
    libdbus-1-3 \
    # Chrome dependencies for SeleniumBase
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    # Utilities
    wget \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Chrome and ChromeDriver via SeleniumBase tool
RUN seleniumbase install chrome

# Copy the rest of the application
COPY . .

# Copy and make start.sh executable
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Expose noVNC port (browser client)
EXPOSE 8080

# Set environment variables for display
ENV DISPLAY=:99
ENV RESOLUTION=1280x800x24

CMD ["/start.sh"]
