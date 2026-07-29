#!/bin/bash

# Clean up lock files from previous runs to prevent Xvfb startup errors
rm -f /tmp/.X99-lock
rm -rf /tmp/.X11-unix/X99

# Force software rendering for OpenGL (fixes Qt6/PyQt6 segmentation faults in headless Docker)
export LIBGL_ALWAYS_SOFTWARE=1
export GALLIUM_DRIVER=llvmpipe
export QT_DEBUG_PLUGINS=1

# Start Xvfb (Virtual Framebuffer)
echo "Starting Xvfb on display :99 with resolution ${RESOLUTION}..."
Xvfb :99 -screen 0 ${RESOLUTION} &
sleep 1

# Start lightweight window manager
echo "Starting Openbox window manager..."
openbox-session &
sleep 1

# Start VNC Server (no password, for local development convenience)
echo "Starting VNC server on port 5900..."
x11vnc -display :99 -forever -shared -nopw -rfbport 5900 &
sleep 1

# Start websockify for noVNC web client
echo "Starting noVNC websockify server on port 8080..."
websockify --web=/usr/share/novnc/ 8080 localhost:5900 &
sleep 1

# Determine running mode
if [ "$RUN_MODE" = "CLI" ]; then
    echo "🚀 Running in CLI Mode..."
    exec python main.py
else
    echo "🚀 Running in GUI Mode..."
    exec python facebook_ui.py
fi
