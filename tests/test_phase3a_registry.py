import pytest
from fastapi.testclient import TestClient

from agent_fabric.registry.catalog import registry_catalog, PackageMetadata
from agent_fabric.registry.installer import install_package, update_packages
from agent_fabric.registry.scaffold import scaffold_plugin
from agent_fabric.server.app import create_app


def test_registry_catalog():
    """Verify registry catalog searching and indexing."""
    pkgs = registry_catalog.search(query="hackernews")
    assert len(pkgs) >= 1
    assert pkgs[0].name == "agent-fabric-plugin-hackernews"
    
    pkg = registry_catalog.get_package("agent-fabric-plugin-github")
    assert pkg is not None
    assert pkg.type == "plugin"
    
    # Register package
    new_pkg = PackageMetadata(name="test-custom-pkg", description="Test Pkg")
    registry_catalog.register_package(new_pkg)
    assert registry_catalog.get_package("test-custom-pkg") is not None


def test_package_installer_and_scaffold():
    """Verify installing packages and scaffolding plugins."""
    res_install = install_package("agent-fabric-plugin-hackernews")
    assert "Successfully installed" in res_install
    
    res_update = update_packages()
    assert "Successfully updated" in res_update or "No installed" in res_update
    
    res_scaffold = scaffold_plugin("scaffolded-demo-plugin")
    assert "Successfully scaffolded" in res_scaffold or "already exists" in res_scaffold


def test_registry_api_endpoints():
    """Verify REST API routes for registry search and package inspection."""
    app = create_app()
    client = TestClient(app)
    
    res_search = client.get("/registry/search?q=github")
    assert res_search.status_code == 200
    data_search = res_search.json()
    assert len(data_search) >= 1
    assert data_search[0]["name"] == "agent-fabric-plugin-github"
    
    res_pkg = client.get("/registry/packages/agent-fabric-plugin-hackernews")
    assert res_pkg.status_code == 200
    assert res_pkg.json()["name"] == "agent-fabric-plugin-hackernews"
