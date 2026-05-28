"""Tiny MCP server used by materials/agents/03-mcp/.

Exposes two arithmetic tools (add, multiply) over stdio, using the FastMCP
helper from the official `mcp` Python SDK. Run as a subprocess of an MCP
client; not meant to be invoked directly except for the smoke test below.

Smoke test (does not exercise MCP, just verifies the module loads):
    python -c "import materials.agents.demo_app.mcp_server"

The real usage lives in 02-writing-a-tiny-mcp-server.md and
03-using-mcp-in-the-agent.md.
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("calculator")


@mcp.tool()
def add(a: int, b: int) -> int:
    """Add two integers. Returns the integer sum."""
    return a + b


@mcp.tool()
def multiply(a: int, b: int) -> int:
    """Multiply two integers. Returns the integer product."""
    return a * b


if __name__ == "__main__":
    mcp.run()
