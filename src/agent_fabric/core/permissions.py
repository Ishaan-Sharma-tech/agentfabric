import fnmatch
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field

__all__ = ["Capability", "check_permission", "AgentFabricPermissionError", "DEVELOPER_CAPABILITIES", "READ_ONLY_CAPABILITIES", "SANDBOXED_CAPABILITIES"]


class Capability(BaseModel):
    """
    Represents a capability token that grants permission to access a resource.
    Inspired by capability-based security models.
    """
    resource: str = Field(..., description="Target resource: e.g. 'file', 'network', 'system', 'memory', 'llm'")
    action: str = Field(..., description="Action type: e.g. 'read', 'write', 'execute', 'query', '*'")
    scope: str = Field(default="*", description="Scope constraint: e.g. path prefix, domain name, or '*'")

    def matches(self, required: "Capability") -> bool:
        """Check if this capability satisfies the required capability."""
        # 1. Match resource
        if self.resource != "*" and self.resource != required.resource:
            return False

        # 2. Match action
        if self.action != "*" and self.action != required.action:
            return False

        # 3. Match scope
        if self.scope == "*":
            return True
            
        if required.scope == "*":
            # Granted scope is not "*", so it cannot satisfy a requirement for all scopes
            return False

        # Try path-based prefix match if resource is 'file'
        if self.resource == "file" or required.resource == "file":
            try:
                g_path = Path(self.scope).resolve()
                r_path = Path(required.scope).resolve()
                if g_path == r_path or g_path in r_path.parents:
                    return True
            except Exception:
                pass

        # Fallback to standard glob prefix/pattern matching
        return fnmatch.fnmatch(required.scope, self.scope)


# Common templates for Capabilities
DEVELOPER_CAPABILITIES = [
    Capability(resource="*", action="*", scope="*")
]

READ_ONLY_CAPABILITIES = [
    Capability(resource="file", action="read", scope="*"),
    Capability(resource="memory", action="read", scope="*"),
    Capability(resource="llm", action="execute", scope="*")
]

SANDBOXED_CAPABILITIES = [
    Capability(resource="file", action="read", scope="*"),
    Capability(resource="file", action="write", scope="*"),
    Capability(resource="memory", action="*", scope="*"),
    Capability(resource="llm", action="execute", scope="*"),
    Capability(resource="network", action="execute", scope="*"),  # Allow standard API requests
    Capability(resource="system", action="execute", scope="echo *")  # Disallow arbitrary system calls
]


def check_permission(granted: List[Capability], required: Capability) -> bool:
    """
    Validates if any of the granted capabilities satisfies the required capability.
    """
    for cap in granted:
        if cap.matches(required):
            return True
    return False


class AgentFabricPermissionError(Exception):
    """Raised when an agent does not have permission to execute an action or tool."""
    def __init__(self, required: Capability, agent_name: str):
        self.required = required
        self.agent_name = agent_name
        super().__init__(
            f"Agent '{agent_name}' lacks capability: "
            f"resource='{required.resource}', action='{required.action}', scope='{required.scope}'"
        )

