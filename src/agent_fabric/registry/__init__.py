"""
AgentFabric Registry & Distribution engine.
"""
from agent_fabric.registry.catalog import PackageMetadata as PackageMetadata, RegistryCatalog as RegistryCatalog, registry_catalog as registry_catalog
from agent_fabric.registry.installer import install_package as install_package, update_packages as update_packages
from agent_fabric.registry.scaffold import scaffold_plugin as scaffold_plugin

__all__ = [
    "PackageMetadata",
    "RegistryCatalog",
    "registry_catalog",
    "install_package",
    "update_packages",
    "scaffold_plugin"
]
