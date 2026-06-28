import json
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from agent_fabric.core.config import settings

logger = logging.getLogger("agent_fabric.registry.catalog")

__all__ = ["PackageMetadata", "RegistryCatalog"]


class PackageMetadata(BaseModel):
    """Metadata representation of a registered plugin or skill package."""
    name: str
    type: str = Field("plugin", description="Type of package (plugin, skill, tool)")
    version: str = "1.0.0"
    description: str = ""
    author: str = "Community"
    tags: List[str] = Field(default_factory=list)
    downloads: int = 0
    repository: Optional[str] = None


BUILTIN_REGISTRY_CATALOG = [
    {
        "name": "agent-fabric-plugin-hackernews",
        "type": "plugin",
        "version": "1.0.0",
        "description": "Built-in HackerNews stories fetcher plugin.",
        "author": "AgentFabric Team",
        "tags": ["news", "tech", "builtin"],
        "downloads": 1250,
        "repository": "https://github.com/Ishaan-Sharma-tech/agentfabric"
    },
    {
        "name": "agent-fabric-plugin-github",
        "type": "plugin",
        "version": "1.0.0",
        "description": "Built-in GitHub repository inspection plugin.",
        "author": "AgentFabric Team",
        "tags": ["developer", "code", "github"],
        "downloads": 980,
        "repository": "https://github.com/Ishaan-Sharma-tech/agentfabric"
    },
    {
        "name": "agent-fabric-plugin-gmail",
        "type": "plugin",
        "version": "0.1.0",
        "description": "Gmail triage and email drafting plugin.",
        "author": "Community",
        "tags": ["email", "productivity"],
        "downloads": 450,
        "repository": "https://github.com/agentfabric/plugin-gmail"
    }
]


class RegistryCatalog:
    """
    Catalog manager responsible for searching, indexing, and caching registry packages.
    """
    def __init__(self) -> None:
        self.catalog_file = settings.agentfabric_dir / "registry.json"
        self._load_catalog()

    def _load_catalog(self) -> None:
        if not self.catalog_file.exists():
            self._save_catalog(BUILTIN_REGISTRY_CATALOG)
            
        try:
            with open(self.catalog_file, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
                self.packages = [PackageMetadata(**item) for item in raw_data]
        except Exception as e:
            logger.warning(f"Failed to load registry catalog from '{self.catalog_file}': {e}")
            self.packages = [PackageMetadata(**item) for item in BUILTIN_REGISTRY_CATALOG]

    def _save_catalog(self, items: List[Dict[str, Any]]) -> None:
        try:
            self.catalog_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.catalog_file, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save registry catalog to '{self.catalog_file}': {e}")

    def search(self, query: str = "", tag: Optional[str] = None) -> List[PackageMetadata]:
        """Search registered packages by keyword query or tag."""
        results = []
        q_clean = query.strip().lower()
        for pkg in self.packages:
            matches_query = (
                not q_clean or 
                q_clean in pkg.name.lower() or 
                q_clean in pkg.description.lower() or 
                any(q_clean in t.lower() for t in pkg.tags)
            )
            matches_tag = not tag or any(tag.lower() == t.lower() for t in pkg.tags)
            if matches_query and matches_tag:
                results.append(pkg)
        return results

    def get_package(self, name: str) -> Optional[PackageMetadata]:
        """Retrieve package metadata by exact name."""
        for pkg in self.packages:
            if pkg.name == name:
                return pkg
        return None

    def register_package(self, pkg: PackageMetadata) -> None:
        """Publish or update a package in local catalog cache."""
        for i, existing in enumerate(self.packages):
            if existing.name == pkg.name:
                self.packages[i] = pkg
                self._save_catalog([p.model_dump() for p in self.packages])
                return
        self.packages.append(pkg)
        self._save_catalog([p.model_dump() for p in self.packages])


registry_catalog = RegistryCatalog()
