FROM --platform=linux/arm64 ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Install AWS Pricing MCP Server
RUN uv pip install --system awslabs.aws-pricing-mcp-server

# Set environment variables
ENV FASTMCP_LOG_LEVEL=ERROR
ENV AWS_REGION=us-west-2

# Create non-root user
RUN useradd -m -u 1000 bedrock_agentcore && \
    chown -R bedrock_agentcore:bedrock_agentcore /app

USER bedrock_agentcore

# Run the MCP server
CMD ["uvx", "awslabs.aws-pricing-mcp-server@latest"]
