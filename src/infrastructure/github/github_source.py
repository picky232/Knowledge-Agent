import base64
import json
import subprocess

from domains.record.entities.record import SourceDocument
from domains.record.repositories.i_document_source import IDocumentSource


class GithubSource(IDocumentSource):
    def __init__(self, limit_repos: int = 20):
        self.limit_repos = limit_repos

    def fetch(self) -> list:
        repos = self._gh_json([
            "repo", "list", "--limit", str(self.limit_repos),
            "--json", "name,nameWithOwner,description,url,createdAt,updatedAt",
        ])
        documents = []
        for repo in repos:
            readme = self._fetch_readme(repo["nameWithOwner"])
            commits = self._fetch_recent_commits(repo["nameWithOwner"])

            content_parts = [repo.get("description") or ""]
            if readme:
                content_parts.append(readme)
            if commits:
                content_parts.append("최근 커밋:\n" + "\n".join(commits))

            documents.append(SourceDocument(
                id=f"github:{repo['nameWithOwner']}",
                source="github",
                project=repo["name"],
                title=repo["nameWithOwner"],
                url=repo["url"],
                content="\n\n".join(p for p in content_parts if p).strip() or repo["name"],
                created_at=repo.get("createdAt", ""),
                updated_at=repo.get("updatedAt", ""),
            ))
        return documents

    def _fetch_readme(self, name_with_owner: str) -> str:
        try:
            raw = subprocess.run(
                ["gh", "api", f"repos/{name_with_owner}/readme"],
                capture_output=True, text=True, timeout=30, check=True,
            ).stdout
            data = json.loads(raw)
            return base64.b64decode(data["content"]).decode("utf-8", errors="ignore")
        except Exception:
            return ""

    def _fetch_recent_commits(self, name_with_owner: str) -> list:
        try:
            raw = subprocess.run(
                ["gh", "api", f"repos/{name_with_owner}/commits?per_page=10"],
                capture_output=True, text=True, timeout=30, check=True,
            ).stdout
            data = json.loads(raw)
            return [c["commit"]["message"].splitlines()[0] for c in data]
        except Exception:
            return []

    def _gh_json(self, args: list):
        raw = subprocess.run(
            ["gh"] + args, capture_output=True, text=True, timeout=30, check=True,
        ).stdout
        return json.loads(raw)
