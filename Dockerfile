# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install poetry
RUN pip install --no-cache-dir poetry==1.8.4

# Copy all project files
COPY pyproject.toml poetry.lock* ./
COPY src/ ./src/

# Configure poetry to not create virtual environment in container
RUN poetry config virtualenvs.create false

# Install dependencies and package (without dev dependencies for production)
RUN poetry install --no-interaction --no-ansi --without dev

# Default environment variables
ENV ROS2_MEDKIT_BASE_URL=http://host.docker.internal:8080/api/v1 \
    ROS2_MEDKIT_TIMEOUT_S=30

# Expose port for HTTP transport
EXPOSE 8765

# Create entrypoint script (HTTP is default)
RUN echo '#!/bin/bash\n\
if [ "$1" = "stdio" ]; then\n\
    shift\n\
    exec ros2-medkit-mcp-stdio "$@"\n\
elif [ "$1" = "http" ]; then\n\
    shift\n\
    exec ros2-medkit-mcp-http --host 0.0.0.0 --port 8765 "$@"\n\
else\n\
    exec ros2-medkit-mcp-http --host 0.0.0.0 --port 8765 "$@"\n\
fi' > /entrypoint.sh && chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD []
