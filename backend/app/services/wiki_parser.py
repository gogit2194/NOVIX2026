from bs4 import BeautifulSoup
from typing import Dict, List


class WikiStructuredParser:
    """
    Algorithmic parser for Wiki pages to extract structured data without LLM.
    Focuses on infoboxes, key sections, tables, and introductions.
    """

    SECTION_KEYWORDS = {
        "appearance": ["外貌", "外观", "Appearance", "形象", "造型", "衣着"],
        "personality": ["性格", "人格", "特点", "性情", "Personality"],
        "background": ["背景", "经历", "故事", "来历", "生平", "简介", "Background"],
        "abilities": ["能力", "技能", "战斗", "招式", "Abilities", "Skills"],
        "relationships": ["关系", "人际", "羁绊", "相关人物", "Relationships"],
    }

    FIELD_MAPPING = {
        "name": ["姓名", "Name", "名字", "本名"],
        "gender": ["性别", "Gender", "Sex"],
        "age": ["年龄", "Age"],
        "birthday": ["生日", "Birthday"],
        "height": ["身高", "Height"],
        "weight": ["体重", "Weight"],
        "voice": ["配音", "CV", "声优", "Voice"],
        "affiliation": ["所属", "阵营", "组织", "Affiliation"],
        "identity": ["身份", "职业", "Title", "Identity"],
    }

    def parse_page(self, html: str, title: str = "") -> Dict:
        """Parse full page into structured data"""
        soup = BeautifulSoup(html, "lxml")

        infobox_data = self.extract_infobox(soup)
        sections = self.extract_sections_by_header(soup)
        summary = self.extract_summary(soup)
        tables = self.extract_tables(soup)

        return {
            "title": title,
            "infobox": infobox_data,
            "sections": sections,
            "summary": summary,
            "tables": tables,
        }

    def extract_infobox(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract data from standard Wiki infobox"""
        data: Dict[str, str] = {}

        infobox = soup.find(
            "table",
            class_=lambda c: c and ("infobox" in c or "wikitable" in c or "basic-info" in c),
        )

        if not infobox:
            return data

        for row in infobox.find_all("tr"):
            header = row.find("th")
            value = row.find("td")

            if not header and not value:
                cols = row.find_all("td")
                if len(cols) == 2:
                    header = cols[0]
                    value = cols[1]

            if header and value:
                key_text = header.get_text(strip=True)
                val_text = value.get_text(strip=True)
                if not key_text or not val_text:
                    continue

                mapped_key = None
                for std_key, keywords in self.FIELD_MAPPING.items():
                    if any(kw in key_text for kw in keywords):
                        mapped_key = std_key
                        break

                if mapped_key:
                    data[mapped_key] = val_text
                else:
                    if 1 < len(key_text) < 15:
                        data[key_text] = val_text

        return data

    def extract_tables(self, soup: BeautifulSoup) -> List[List[str]]:
        """Extract compact table rows for LLM context"""
        tables: List[List[str]] = []
        content = soup.find("div", class_="mw-parser-output") or soup.find("body") or soup

        identity_keys = ["姓名", "本名", "别名", "身份", "职业", "性别", "生日", "身高", "体重", "所属", "阵营", "配音", "种族"]
        skill_noise = ["攻击", "伤害", "技能", "冷却", "等级", "效果", "倍率", "命中", "普攻", "重击"]

        for table in content.find_all("table")[:3]:
            rows: List[str] = []
            raw_text = table.get_text(" ", strip=True)
            if not raw_text:
                continue

            has_identity = any(key in raw_text for key in identity_keys)
            has_skill_noise = any(key in raw_text for key in skill_noise)
            if has_skill_noise and not has_identity:
                continue

            for row in table.find_all("tr")[:12]:
                cells = row.find_all(["th", "td"])
                if not cells:
                    continue
                texts = [cell.get_text(" ", strip=True) for cell in cells]
                texts = [text for text in texts if text]
                if not texts:
                    continue
                if len(texts) == 2:
                    rows.append(f"{texts[0]}: {texts[1]}")
                else:
                    rows.append(" | ".join(texts))
            if rows:
                tables.append(rows)

        return tables

    def extract_sections_by_header(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract paragraphs under specific headers"""
        sections: Dict[str, str] = {}

        headers = soup.find_all(["h2", "h3"])

        for header in headers:
            headline = header.find("span", class_="mw-headline")
            header_text = headline.get_text(strip=True) if headline else header.get_text(strip=True)

            section_type = None
            for s_type, keywords in self.SECTION_KEYWORDS.items():
                if any(kw in header_text for kw in keywords):
                    section_type = s_type
                    break

            if section_type and section_type not in sections:
                content_parts = []
                for sibling in header.find_next_siblings():
                    if sibling.name in ["h2", "h3"]:
                        break

                    if sibling.name == "p":
                        text = sibling.get_text(strip=True)
                        if len(text) > 10:
                            content_parts.append(text)
                    elif sibling.name in ["ul", "ol"]:
                        items = [li.get_text(strip=True) for li in sibling.find_all("li")]
                        if items:
                            content_parts.append("\n".join(items[:5]))

                    if len(content_parts) >= 5:
                        break

                if content_parts:
                    sections[section_type] = "\n".join(content_parts)

        return sections

    def extract_summary(self, soup: BeautifulSoup) -> str:
        """Extract the first meaningful paragraph as summary"""
        for p in soup.find_all("p"):
            is_clean = True
            for parent in p.parents:
                if parent.name in ["table", "li", "ul", "footer"]:
                    is_clean = False
                    break
                if parent.get("class") and any("navbox" in c for c in parent.get("class")):
                    is_clean = False
                    break

            if is_clean:
                text = p.get_text(strip=True)
                if len(text) > 30:
                    return text

        return ""

    def format_for_llm(self, parsed: Dict, max_chars: int = 50000) -> str:
        """Format parsed data into a compact LLM-ready text."""
        parts: List[str] = []
        title = str(parsed.get("title", "") or "").strip()
        summary = str(parsed.get("summary", "") or "").strip()
        infobox = parsed.get("infobox") or {}
        sections = parsed.get("sections") or {}

        if title:
            parts.append(f"{title}")
        if summary:
            parts.append(summary)

        if infobox:
            lines = [f"{k}: {v}" for k, v in infobox.items() if k and v]
            if lines:
                parts.append("\n".join(lines))

        if sections:
            for _, content in sections.items():
                if not content:
                    continue
                parts.append(content)

        text = "\n\n".join([p for p in parts if p]).strip()
        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "\n\n[Content truncated]"
        return text

    def format_for_preview(self, parsed: Dict, max_chars: int = 1200) -> str:
        """Create short preview text for UI."""
        title = str(parsed.get("title", "") or "").strip()
        summary = str(parsed.get("summary", "") or "").strip()
        sections = parsed.get("sections") or {}

        parts: List[str] = []
        if title:
            parts.append(title)
        if summary:
            parts.append(summary)
        if not summary and sections:
            first_section = next(iter(sections.values()), "")
            if first_section:
                parts.append(first_section)

        text = "\n\n".join([p for p in parts if p]).strip()
        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "..."
        return text


wiki_parser = WikiStructuredParser()

