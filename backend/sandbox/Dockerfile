# Sandbox Docker image for LexCore — Phase 14 / BRIDGE-01 (D-P14-08).
#
# Extends the standard Python slim image (same base as llm-sandbox default).
# Pre-bakes ToolClient at /sandbox/tool_client.py so LLM-generated code
# can do `from tool_client import ToolClient` without any pip install.
#
# Build: docker build -t lexcore-sandbox:latest backend/sandbox/
# This image tag matches settings.sandbox_image default in config.py.
#
# Note: This is NOT the Railway production image (that is backend/Dockerfile).
# This image runs as the llm-sandbox container for code execution.

FROM python:3.12-slim

# Create sandbox output directory
RUN mkdir -p /sandbox/output

# Pre-bake ToolClient — stdlib only, no pip installs needed
COPY tool_client.py /sandbox/tool_client.py

# Make /sandbox writeable so runtime stub injection can write /sandbox/stubs.py
RUN chmod 777 /sandbox

# Default working directory for executed code
WORKDIR /sandbox
