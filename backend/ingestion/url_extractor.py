from __future__ import annotations

from collections.abc import Iterable
from typing import TypedDict
from urllib.parse import urldefrag, urljoin

import httpx
from bs4 import BeautifulSoup


class ExtractedUrlPage(TypedDict):
    page_number: int
    text: str


REMOVED_TAGS = ("script", "style", "nav", "footer", "header")
SKIPPED_HREF_PREFIXES = ("#", "javascript:", "mailto:", "tel:")


async def fetch_html(url: str) -> str:
    timeout = httpx.Timeout(20.0, connect=10.0)
    headers = {
        "User-Agent": (
            "CasePilotBot/1.0 (+https://casepilot.local) "
            "Python httpx content ingestion"
        )
    }
    async with httpx.AsyncClient(
        timeout=timeout, headers=headers, follow_redirects=True
    ) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


def extract_visible_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(REMOVED_TAGS):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines()]
    visible_lines = [line for line in lines if line]
    return "\n".join(visible_lines)


def extract_links_from_html(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.lower().startswith(SKIPPED_HREF_PREFIXES):
            continue

        absolute_url = urljoin(base_url, href)
        absolute_url, _fragment = urldefrag(absolute_url)
        if absolute_url and absolute_url not in seen:
            seen.add(absolute_url)
            links.append(absolute_url)

    return links


def filter_links_by_pattern(links: Iterable[str], pattern: str | None) -> list[str]:
    if not pattern:
        return list(links)
    return [link for link in links if pattern in link]


async def extract_url_pages(url: str) -> list[ExtractedUrlPage]:
    html = await fetch_html(url)
    text = extract_visible_text_from_html(html)
    return [{"page_number": 0, "text": text}]


async def discover_links(url: str, url_pattern: str | None = None) -> list[str]:
    html = await fetch_html(url)
    links = extract_links_from_html(html, url)
    return filter_links_by_pattern(links, url_pattern)
