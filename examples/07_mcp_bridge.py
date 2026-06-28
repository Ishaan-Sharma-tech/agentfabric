"""
07_mcp_bridge.py — Model Context Protocol (MCP) server & client example.
"""
import asyncio
from agent_fabric.mcp.server import MCPServer
from agent_fabric.mcp.manager import mcp_manager

async def main():
    server = MCPServer()
    init_res = await server.handle_jsonrpc_request('{"jsonrpc":"2.0","id":1,"method":"initialize"}')
    print("MCP Server Init Response:", init_res)

if __name__ == "__main__":
    asyncio.run(main())
