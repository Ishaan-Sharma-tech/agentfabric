"""
Built-in tools provided by AgentFabric: web_search, url_reader, read_file, write_file.
Importing this package automatically registers these tools in the global tool registry.
"""
from agent_fabric.tools.builtin.web_search import web_search as web_search
from agent_fabric.tools.builtin.url_reader import url_reader as url_reader
from agent_fabric.tools.builtin.file_ops import read_file as read_file, write_file as write_file

__all__ = ["web_search", "url_reader", "read_file", "write_file"]
