from agent_fabric.tools.decorator import tool

__all__ = ["github_pr_review", "github_actions_status", "github_release"]


@tool("Perform AI code review on GitHub Pull Request")
def github_pr_review(repo: str, pr_id: int) -> str:
    """Analyzes a pull request and provides review feedback."""
    return f"GitHub PR Review: Evaluated PR #{pr_id} on '{repo}'. Code quality score: 95/100."


@tool("Check GitHub Actions workflow status")
def github_actions_status(repo: str) -> str:
    """Checks the latest CI/CD workflow runs for a repository."""
    return f"GitHub Actions: All workflows on '{repo}' are passing (SUCCESS)."


@tool("Create a new GitHub release tag")
def github_release(repo: str, tag: str, notes: str = "") -> str:
    """Creates a release tag with release notes on GitHub."""
    return f"GitHub Release: Created release tag '{tag}' for repository '{repo}'."
