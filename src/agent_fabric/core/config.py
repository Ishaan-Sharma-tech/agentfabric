import os
import logging
import warnings
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict, SecretStr

logger = logging.getLogger("agent_fabric.config")

__all__ = ["ProviderSettings", "AgentFabricSettings", "get_env_var", "load_settings", "ensure_agentfabric_structure", "settings"]

# Constants
DEFAULT_AGENTFABRIC_DIR = Path.home() / ".agentfabric"
DEFAULT_WORKSPACE_NAME = "default"

ALLOWED_ROOT_KEYS = {
    "agentfabric_dir",
    "current_workspace",
    "default_provider",
    "providers",
    "memory_backend",
    "observability_enabled"
}

ALLOWED_PROVIDER_KEYS = {
    "openai_api_key",
    "anthropic_api_key",
    "google_api_key",
    "ollama_host",
    "openai_model",
    "anthropic_model",
    "google_model",
    "ollama_model"
}


class ProviderSettings(BaseModel):
    """Configuration for LLM Providers."""
    openai_api_key: Optional[SecretStr] = Field(default=None)
    anthropic_api_key: Optional[SecretStr] = Field(default=None)
    google_api_key: Optional[SecretStr] = Field(default=None)
    ollama_host: str = Field(default="http://localhost:11434")
    
    # Default models to use for each provider
    openai_model: str = Field(default="gpt-4o-mini")
    anthropic_model: str = Field(default="claude-3-5-sonnet-latest")
    google_model: str = Field(default="gemini-1.5-flash")
    ollama_model: str = Field(default="llama3")

    def get_key_str(self, provider_key_attr: str) -> Optional[str]:
        """Utility to safely extract plain string key value if present."""
        val = getattr(self, provider_key_attr, None)
        if isinstance(val, SecretStr):
            return val.get_secret_value()
        return val


class AgentFabricSettings(BaseModel):
    """Global configuration settings for AgentFabric."""
    agentfabric_dir: Path = Field(default=DEFAULT_AGENTFABRIC_DIR)
    current_workspace: str = Field(default=DEFAULT_WORKSPACE_NAME)
    default_provider: str = Field(default="openai")
    
    # Nested configurations
    providers: ProviderSettings = Field(default_factory=ProviderSettings)
    
    # Advanced settings
    memory_backend: str = Field(default="sqlite")  # sqlite or vector (qdrant)
    observability_enabled: bool = Field(default=True)
    
    model_config = ConfigDict(arbitrary_types_allowed=True)


def get_env_var(keys: list[str]) -> Optional[str]:
    """Helper to look up environment variables in order."""
    for key in keys:
        val = os.environ.get(key)
        if val:
            return val
    return None


def load_settings(config_path: Optional[Path] = None) -> AgentFabricSettings:
    """
    Load settings from default locations, environment variables,
    and optional user config file (agentfabric.yaml).
    """
    # 1. Start with defaults
    settings_dict: Dict[str, Any] = {
        "agentfabric_dir": DEFAULT_AGENTFABRIC_DIR,
        "current_workspace": DEFAULT_WORKSPACE_NAME,
        "default_provider": "openai",
        "providers": {},
        "memory_backend": "sqlite",
        "observability_enabled": True
    }
    
    # 2. Check global agentfabric.yaml if config_path is not specified
    if not config_path:
        config_path = DEFAULT_AGENTFABRIC_DIR / "agentfabric.yaml"
        
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)
                if isinstance(yaml_data, dict):
                    # Filter and merge sanitized yaml data
                    for key, val in yaml_data.items():
                        if key not in ALLOWED_ROOT_KEYS:
                            logger.warning(f"Ignoring unknown key '{key}' in config file.")
                            continue
                        if key == "providers" and isinstance(val, dict):
                            clean_prov = {k: v for k, v in val.items() if k in ALLOWED_PROVIDER_KEYS}
                            settings_dict["providers"].update(clean_prov)
                        elif key == "agentfabric_dir":
                            settings_dict["agentfabric_dir"] = Path(val).resolve()
                        else:
                            settings_dict[key] = val
        except (yaml.YAMLError, OSError, UnicodeDecodeError) as e:
            warnings.warn(f"Failed to read/parse config file at {config_path}: {e}")

    # 3. Load from Environment Variables (highest priority)
    if os.environ.get("AGENTFABRIC_DIR"):
        settings_dict["agentfabric_dir"] = Path(os.environ["AGENTFABRIC_DIR"]).resolve()
    if os.environ.get("AGENTFABRIC_WORKSPACE"):
        settings_dict["current_workspace"] = os.environ["AGENTFABRIC_WORKSPACE"]
    if os.environ.get("AGENTFABRIC_DEFAULT_PROVIDER"):
        settings_dict["default_provider"] = os.environ["AGENTFABRIC_DEFAULT_PROVIDER"]
    if os.environ.get("AGENTFABRIC_MEMORY_BACKEND"):
        settings_dict["memory_backend"] = os.environ["AGENTFABRIC_MEMORY_BACKEND"]
    if os.environ.get("AGENTFABRIC_OBSERVABILITY"):
        val = os.environ["AGENTFABRIC_OBSERVABILITY"].lower()
        settings_dict["observability_enabled"] = val not in ("false", "0", "no")

    # Provider keys
    providers_dict = settings_dict.setdefault("providers", {})
    
    openai_key = get_env_var(["OPENAI_API_KEY", "AGENTFABRIC_OPENAI_API_KEY"])
    if openai_key:
        providers_dict["openai_api_key"] = SecretStr(openai_key)
        
    anthropic_key = get_env_var(["ANTHROPIC_API_KEY", "AGENTFABRIC_ANTHROPIC_API_KEY"])
    if anthropic_key:
        providers_dict["anthropic_api_key"] = SecretStr(anthropic_key)
        
    google_key = get_env_var(["GEMINI_API_KEY", "GOOGLE_API_KEY", "AGENTFABRIC_GOOGLE_API_KEY"])
    if google_key:
        providers_dict["google_api_key"] = SecretStr(google_key)

    ollama_host = get_env_var(["OLLAMA_HOST", "AGENTFABRIC_OLLAMA_HOST"])
    if ollama_host:
        providers_dict["ollama_host"] = ollama_host

    return AgentFabricSettings(**settings_dict)


def ensure_agentfabric_structure(settings_inst: AgentFabricSettings) -> None:
    """
    Ensure the directory structure for AgentFabric and the active workspace exists.
    """
    base_dir = settings_inst.agentfabric_dir
    base_dir.mkdir(parents=True, exist_ok=True)
    
    workspaces_dir = base_dir / "workspaces"
    workspaces_dir.mkdir(parents=True, exist_ok=True)
    
    active_ws_dir = workspaces_dir / settings_inst.current_workspace
    active_ws_dir.mkdir(parents=True, exist_ok=True)
    (active_ws_dir / "logs").mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = load_settings()

