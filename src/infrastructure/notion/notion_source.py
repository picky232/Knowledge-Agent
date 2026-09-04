import requests

from domains.record.entities.record import SourceDocument
from domains.record.repositories.i_document_source import IDocumentSource

API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionSource(IDocumentSource):
    def __init__(self, token: str, max_pages: int = 500):
        self.token = token
        self.max_pages = max_pages
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def fetch(self) -> list:
        pages = self._search_pages()
        documents = []
        for page in pages:
            title = self._extract_title(page)
            content = self._extract_page_text(page["id"])
            documents.append(SourceDocument(
                id=f"notion:{page['id']}",
                source="notion",
                project=title,
                title=title,
                url=page.get("url", ""),
                content=content or title,
                created_at=page.get("created_time", ""),
                updated_at=page.get("last_edited_time", ""),
            ))
        return documents

    def _search_pages(self) -> list:
        pages = []
        cursor = None
        while len(pages) < self.max_pages:
            body = {
                "filter": {"property": "object", "value": "page"},
                "page_size": 100,
            }
            if cursor:
                body["start_cursor"] = cursor

            resp = requests.post(
                f"{API_BASE}/search", headers=self.headers, json=body, timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            pages.extend(data.get("results", []))

            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")

        return pages[: self.max_pages]

    def _extract_title(self, page: dict) -> str:
        props = page.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                texts = prop.get("title", [])
                joined = "".join(t.get("plain_text", "") for t in texts)
                if joined:
                    return joined
        return "(제목 없음)"

    def _extract_page_text(self, page_id: str) -> str:
        texts = []
        cursor = None
        for _ in range(5):
            params = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            resp = requests.get(
                f"{API_BASE}/blocks/{page_id}/children",
                headers=self.headers, params=params, timeout=30,
            )
            if resp.status_code != 200:
                break
            data = resp.json()
            for block in data.get("results", []):
                texts.append(self._block_to_text(block))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return "\n".join(t for t in texts if t)

    def _block_to_text(self, block: dict) -> str:
        block_type = block.get("type", "")
        payload = block.get(block_type, {})
        rich_text = payload.get("rich_text", [])
        return "".join(t.get("plain_text", "") for t in rich_text)
