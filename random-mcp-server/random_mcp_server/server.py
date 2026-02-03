"""MCP server for generating random numbers."""

import random
import sys

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool


server = Server("random-mcp-server")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="get_random_number",
            description="Generate a random number between 1 and 100",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    if name == "get_random_number":
        number = random.randint(1, 100)

        # Output debug info to stderr
        print(f"[DEBUG] Generated random number: {number}", file=sys.stderr)

        return [TextContent(type="text", text=str(number))]

    raise ValueError(f"Unknown tool: {name}")


async def run_server():
    """Run the MCP server."""
    print("[DEBUG] Starting random-mcp-server...", file=sys.stderr)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main():
    """Main entry point."""
    import asyncio
    asyncio.run(run_server())


if __name__ == "__main__":
    main()
