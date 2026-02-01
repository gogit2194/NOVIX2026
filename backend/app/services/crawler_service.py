"""
Crawler Service for Fanfiction Feature
Scrapes Wiki pages and extracts content using multiple strategies:
1. MediaWiki API (parse action)
2. Direct HTML scraping (fallback)
"""

import asyncio
import re
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse, urldefrag, parse_qs, quote, unquote

import aiohttp
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.utils.logger import get_logger
from .wiki_parser import wiki_parser

logger = get_logger(__name__)


class CrawlerService:
    """Service for scraping Wiki pages"""

    MAX_PREVIEW_CHARS = 1200
    MAX_LLM_CHARS = 50000
    MAX_LINKS = 400

    def __init__(self):
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

        retry = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def scrape_page(self, url: str) -> Dict[str, Any]:
        """
        Scrape a Wiki page and extract main content.
        Uses API when available, falls back to HTML scraping.
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            if "fandom.com" in domain:
                result = self._scrape_mediawiki_parse(url, parsed)
            elif "moegirl.org" in domain:
                result = self._scrape_mediawiki_parse(url, parsed)
            elif "wikipedia.org" in domain:
                result = self._scrape_wikipedia(url, parsed)
            elif "huijiwiki.com" in domain or "wiki" in domain:
                result = self._scrape_mediawiki_parse(url, parsed)
            else:
                result = self._scrape_html(url)

            if result.get("success", False):
                if not result.get("content") and not result.get("links"):
                    result["content"] = (
                        f"Page Title: {result.get('title', 'Unknown')}\n\n"
                        "This page has no extractable text. Please open it in a browser."
                    )
                    result["links"] = []

            return result

        except Exception as exc:
            return {
                "success": False,
                "error": str(exc),
                "url": url,
                "content": "",
                "links": [],
                "llm_content": "",
            }

    def _extract_mediawiki_title(self, parsed) -> Optional[str]:
        if "index.php" in parsed.path:
            query_params = parse_qs(parsed.query)
            title = query_params.get("title", [None])[0]
            return unquote(title) if title else None

        path_parts = parsed.path.strip("/").split("/")
        if not path_parts:
            return None
        if path_parts[0] == "wiki" and len(path_parts) > 1:
            return unquote("/".join(path_parts[1:]))
        if path_parts[0] != "index.php":
            return unquote(parsed.path.strip("/"))
        return None

    def _get_mediawiki_api_url(self, parsed) -> str:
        path_parts = parsed.path.strip("/").split("/")
        lang_prefix = ""
        if len(path_parts) > 0 and len(path_parts[0]) == 2 and path_parts[0] != "wiki":
            lang_prefix = f"/{path_parts[0]}"
        return f"{parsed.scheme}://{parsed.netloc}{lang_prefix}/api.php"

    def _scrape_mediawiki_parse(self, url: str, parsed) -> Dict[str, Any]:
        """Generic MediaWiki parse-action scraper (Fandom/Moegirl/Huiji/etc.)"""
        article_name = self._extract_mediawiki_title(parsed)
        if not article_name:
            return self._scrape_html(url)

        api_url = self._get_mediawiki_api_url(parsed)
        params = {
            "action": "parse",
            "page": article_name,
            "prop": "text|categories",
            "format": "json",
            "redirects": "1",
        }

        try:
            response = self.session.get(api_url, params=params, timeout=15)
            response.raise_for_status()
            response.encoding = "utf-8"
            data = response.json()

            if "error" in data:
                return self._scrape_html(url)

            parse_data = data.get("parse", {})
            title = parse_data.get("title", "Untitled")
            html_content = parse_data.get("text", {}).get("*", "")

            if not html_content:
                return self._scrape_html(url)

            return self._build_from_html(html_content, title, url)

        except Exception as exc:
            logger.error(f"MediaWiki parse error: {exc}")
            return self._scrape_html(url)

    def _scrape_wikipedia(self, url: str, parsed) -> Dict[str, Any]:
        """Scrape Wikipedia using REST API and mobile HTML."""
        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) < 2 or path_parts[0] != "wiki":
            return self._scrape_html(url)

        article_name = "/".join(path_parts[1:])

        try:
            content_url = f"{parsed.scheme}://{parsed.netloc}/api/rest_v1/page/mobile-html/{quote(article_name)}"
            content_resp = self.session.get(content_url, timeout=15)
            content_resp.raise_for_status()
            html = content_resp.text

            title = ""
            try:
                soup_preview = BeautifulSoup(html[:5000], "lxml")
                title_tag = soup_preview.find("title")
                if title_tag:
                    title = title_tag.get_text(strip=True).split(" - ")[0]
            except Exception as exc:
                logger.warning(f"Failed to extract title: {exc}")

            return self._build_from_html(html, title or article_name, url)
        except Exception:
            return self._scrape_html(url)

    def _scrape_html(self, url: str) -> Dict[str, Any]:
        """Fallback HTML scraping method"""
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()

            if response.encoding and response.encoding.lower() in ["iso-8859-1", "ascii"]:
                detected = response.apparent_encoding
                response.encoding = detected if detected else "utf-8"
            elif not response.encoding:
                response.encoding = "utf-8"

            parsed_check = urlparse(url)
            if any(x in parsed_check.netloc for x in ["moegirl", "baike", "hudong", "zh."]):
                response.encoding = "utf-8"

            html = response.text
            title = ""
            try:
                soup_preview = BeautifulSoup(html[:5000], "lxml")
                title_tag = soup_preview.find("title")
                if title_tag:
                    title = title_tag.get_text(strip=True).split(" - ")[0]
            except Exception as exc:
                logger.warning(f"Failed to extract title: {exc}")

            return self._build_from_html(html, title, url)

        except Exception as exc:
            return {
                "success": False,
                "error": f"Failed to load page: {exc}",
                "url": url,
                "content": "",
                "links": [],
                "llm_content": "",
            }

    def _build_from_html(self, html: str, title: str, url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, "lxml")
        parsed_data = wiki_parser.parse_page(html, title=title or "Untitled")

        has_structure = any(
            [
                parsed_data.get("summary"),
                parsed_data.get("sections"),
                parsed_data.get("infobox"),
                parsed_data.get("tables"),
            ]
        )

        if not has_structure:
            fallback_text = self._extract_text_from_soup(soup)
            parsed_data = {
                "title": title or "Untitled",
                "summary": fallback_text[:800],
                "sections": {"content": fallback_text},
                "infobox": {},
                "tables": [],
            }

        llm_content = wiki_parser.format_for_llm(parsed_data, max_chars=self.MAX_LLM_CHARS)
        # 追加更多正文段落，尽可能还原页面信息
        extra_paragraphs = []
        for p in soup.find_all("p")[:80]:
            text = p.get_text(" ", strip=True)
            if len(text) >= 20:
                extra_paragraphs.append(text)
        if extra_paragraphs:
            llm_content = f"{llm_content}\n\n" + "\n".join(extra_paragraphs)

        # 再追加纯文本兜底，确保长内容传递给 LLM
        fallback_text = self._extract_text_from_soup(soup)
        if fallback_text:
            llm_content = f"{llm_content}\n\n{fallback_text[:20000]}"
        preview_content = wiki_parser.format_for_preview(parsed_data, max_chars=self.MAX_PREVIEW_CHARS)
        if not preview_content:
            preview_content = llm_content[: self.MAX_PREVIEW_CHARS]

        links = self._extract_links(soup, url)
        is_list_page = len(links) > 10

        return {
            "success": True,
            "title": parsed_data.get("title") or title or "Untitled",
            "content": self._clean_content(preview_content),
            "llm_content": self._clean_content(llm_content),
            "links": links,
            "is_list_page": is_list_page,
            "url": url,
        }

    def _extract_text_from_soup(self, soup: BeautifulSoup) -> str:
        """Extract main text content from soup with smart list/table handling"""
        content_selectors = [
            ("div", {"class": "mw-parser-output"}),
            ("div", {"id": "mw-content-text"}),
            ("div", {"class": "page-content"}),
            ("article", {}),
            ("main", {}),
        ]

        content = None
        for tag, attrs in content_selectors:
            content = soup.find(tag, attrs) if attrs else soup.find(tag)
            if content:
                break

        if not content:
            content = soup.find("body")

        if not content:
            return ""

        tables = content.find_all("table")
        lists = content.find_all(["ul", "ol"])
        is_list_heavy = len(tables) > 2 or len(lists) > 3

        for unwanted in content.find_all(["nav", "aside", "footer", "script", "style", "noscript"]):
            unwanted.decompose()

        if not is_list_heavy:
            for cls in ["navbox", "toc", "sidebar", "infobox", "navigation", "mw-editsection", "reference"]:
                for elem in content.find_all(class_=re.compile(cls, re.I)):
                    elem.decompose()

        text_parts = []
        first_p = content.find("p")
        if first_p:
            intro = first_p.get_text(strip=True)
            if intro and len(intro) > 20:
                text_parts.append(f"## 简介\n{intro}\n")

        for elem in content.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
            text = elem.get_text(strip=True)
            if not text or len(text) < 3:
                continue

            if elem.name in ["h1", "h2"]:
                text_parts.append(f"\n## {text}\n")
            elif elem.name in ["h3", "h4"]:
                text_parts.append(f"\n### {text}\n")
            else:
                text_parts.append(text)

        if len(text_parts) < 5 and tables:
            for table in tables[:3]:
                rows = table.find_all("tr")
                for row in rows[:10]:
                    cells = row.find_all(["td", "th"])
                    row_text = " | ".join([c.get_text(strip=True) for c in cells if c.get_text(strip=True)])
                    if row_text:
                        text_parts.append(row_text)

        result = "\n\n".join(text_parts)
        if not result or len(result) < 50:
            result = content.get_text(separator="\n", strip=True)[:1000]

        return result

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict[str, str]]:
        """Extract internal links with enhanced table/category support"""
        base_domain = urlparse(base_url).netloc
        links: List[Dict[str, str]] = []
        seen_urls = set()

        content = soup.find("div", class_="mw-parser-output") or soup.find("body")
        if not content:
            return []

        def add_link(href: str, link_text: str) -> None:
            full_url = urljoin(base_url, href)
            full_url, _ = urldefrag(full_url)
            if urlparse(full_url).netloc != base_domain:
                return
            if any(x in href.lower() for x in ["special:", "file:", "talk:", "template:", "user:"]):
                return
            if not link_text or len(link_text) < 2:
                return
            if full_url not in seen_urls:
                seen_urls.add(full_url)
                links.append({"title": link_text, "url": full_url})

        tables = content.find_all("table")
        for table in tables[:20]:
            for a_tag in table.find_all("a", href=True):
                add_link(a_tag["href"], a_tag.get_text(strip=True))
                if len(links) >= self.MAX_LINKS:
                    break
            if len(links) >= self.MAX_LINKS:
                break

        if len(links) < self.MAX_LINKS:
            lists = content.find_all(["ul", "ol"])
            for lst in lists[:20]:
                for a_tag in lst.find_all("a", href=True):
                    add_link(a_tag["href"], a_tag.get_text(strip=True))
                    if len(links) >= self.MAX_LINKS:
                        break
                if len(links) >= self.MAX_LINKS:
                    break

        if len(links) < self.MAX_LINKS:
            for a_tag in content.find_all("a", href=True):
                add_link(a_tag["href"], a_tag.get_text(strip=True))
                if len(links) >= self.MAX_LINKS:
                    break

        return links

    def _clean_content(self, content: str) -> str:
        """Clean and normalize content"""
        if not content:
            return ""

        content = re.sub(r"\n{3,}", "\n\n", content)
        content = re.sub(r" {2,}", " ", content)
        return content.strip()

    async def scrape_pages_concurrent(self, urls: List[str], concurrency: int = 6) -> List[Dict[str, Any]]:
        """
        Scrape multiple pages concurrently using thread pool executor.
        Returns a list of structured data compatible with extraction.
        """
        import concurrent.futures

        loop = asyncio.get_event_loop()

        with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [loop.run_in_executor(executor, self._scrape_for_batch, url) for url in urls]
            results = await asyncio.gather(*futures)

        return list(results)

    def _scrape_for_batch(self, url: str) -> Dict[str, Any]:
        """Wrapper around scrape_page that formats result for batch extraction"""
        try:
            result = self.scrape_page(url)
            return {
                "success": result.get("success", False),
                "url": url,
                "title": result.get("title", ""),
                "content": result.get("content", ""),
                "llm_content": result.get("llm_content", ""),
                "error": result.get("error"),
            }
        except Exception as exc:
            return {"success": False, "url": url, "error": str(exc)}

    async def _scrape_single_async(self, session: aiohttp.ClientSession, url: str, semaphore: asyncio.Semaphore) -> Dict[str, Any]:
        """Async scrape a single page and use WikiStructuredParser"""
        async with semaphore:
            try:
                headers = {"User-Agent": self.headers["User-Agent"]}
                parsed = urlparse(url)
                force_utf8 = any(x in parsed.netloc for x in ["moegirl", "baike", "zh."])

                timeout = aiohttp.ClientTimeout(total=30)
                async with session.get(url, headers=headers, timeout=timeout) as response:
                    if response.status != 200:
                        logger.warning(f"HTTP {response.status} for {url}")
                        return {"success": False, "url": url, "error": f"Status {response.status}"}

                    content_bytes = await response.read()

                    if force_utf8:
                        html = content_bytes.decode("utf-8", errors="replace")
                    else:
                        encoding = response.get_encoding() or "utf-8"
                        try:
                            html = content_bytes.decode(encoding, errors="replace")
                        except (UnicodeDecodeError, LookupError) as exc:
                            logger.warning(f"Failed to decode with {encoding}: {exc}")
                            html = content_bytes.decode("utf-8", errors="replace")

                    title = ""
                    try:
                        soup_preview = BeautifulSoup(html[:5000], "lxml")
                        title_tag = soup_preview.find("title")
                        if title_tag:
                            title = title_tag.get_text(strip=True).split(" - ")[0]
                    except Exception as exc:
                        logger.warning(f"Failed to extract title: {exc}")

                    parsed_data = wiki_parser.parse_page(html, title=title or url.split("/")[-1])
                    parsed_data["url"] = url
                    parsed_data["success"] = True

                    if not any(
                        [
                            parsed_data.get("infobox"),
                            parsed_data.get("sections"),
                            parsed_data.get("summary"),
                            parsed_data.get("tables"),
                        ]
                    ):
                        soup = BeautifulSoup(html, "lxml")
                        content_div = soup.find("div", class_="mw-parser-output") or soup.find("body")
                        if content_div:
                            raw_paragraphs = []
                            for p in content_div.find_all("p")[:5]:
                                text = p.get_text(strip=True)
                                if len(text) > 20:
                                    raw_paragraphs.append(text)

                            if raw_paragraphs:
                                parsed_data["summary"] = "\n".join(raw_paragraphs[:2])
                                parsed_data["sections"] = {"background": "\n".join(raw_paragraphs)}

                    parsed_data["llm_content"] = wiki_parser.format_for_llm(parsed_data, max_chars=self.MAX_LLM_CHARS)
                    return parsed_data

            except Exception as exc:
                logger.error(f"Concurrent scraper failed {url}: {exc}")
                return {"success": False, "url": url, "error": str(exc)}


crawler_service = CrawlerService()
