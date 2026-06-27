"""
Built-in tools provided by AgentFabric.
Importing this package automatically registers built-in tools in the global tool registry.
"""
from agent_fabric.tools.builtin.web_search import web_search as web_search
from agent_fabric.tools.builtin.url_reader import url_reader as url_reader
from agent_fabric.tools.builtin.file_ops import read_file as read_file, write_file as write_file
from agent_fabric.tools.builtin.file_write import file_write as file_write
from agent_fabric.tools.builtin.shell_execute import shell_execute as shell_execute
from agent_fabric.tools.builtin.http_request import http_request as http_request

__all__ = ["web_search", "url_reader", "read_file", "write_file", "file_write", "shell_execute", "http_request"]
