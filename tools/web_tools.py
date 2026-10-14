"""Web & Social Media Ingestion Tools for Prince AI Team (per SPEC.md §7).

Allows fetching and extracting clean text and metadata from URLs, including
X (Twitter) posts via public oEmbed, technical articles, and documentation.
"""

import html
import re
import requests
from typing import Any, Dict, List, Optional
from logging_utils.logger import get_logger

logger = get_logger("WebTools")

URL_REGEX = re.compile(r"https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)")


class WebTools:
    """Tools to parse and fetch web & social post content safely."""

    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def extract_urls(self, text: str) -> List[str]:
        """Finds all URLs inside a text prompt."""
        if not text:
            return []
        return URL_REGEX.findall(text)

    def fetch_url_content(self, url: str) -> Dict[str, Any]:
        """Fetches metadata and readable content from a URL."""
        clean_url = url.strip()
        url_lower = clean_url.lower()

        # Handle X (Twitter) URLs via syndication and oEmbed
        if "x.com" in url_lower or "twitter.com" in url_lower:
            tweet_id_match = re.search(r"status/(\d+)", clean_url)
            if tweet_id_match:
                tweet_id = tweet_id_match.group(1)
                try:
                    syn_resp = requests.get(
                        f"https://cdn.syndication.twimg.com/tweet-result?id={tweet_id}&token=5",
                        headers=self.headers,
                        timeout=self.timeout
                    )
                    if syn_resp.status_code == 200:
                        s_data = syn_resp.json()
                        author = s_data.get("user", {}).get("name", "Unknown Author")
                        handle = s_data.get("user", {}).get("screen_name", "")
                        full_text = s_data.get("note_tweet", {}).get("text") or s_data.get("text", "")
                        return {
                            "success": True,
                            "url": clean_url,
                            "platform": "x",
                            "author": f"{author} (@{handle})" if handle else author,
                            "title": f"Post by {author} on X",
                            "description": full_text[:200],
                            "text_content": full_text
                        }
                except Exception as e:
                    logger.debug(f"Syndication fetch failed, falling back to oEmbed: {e}")

            return self._fetch_x_oembed(clean_url)

        # Handle general web pages
        return self._fetch_generic_web(clean_url)

    def _fetch_x_oembed(self, url: str) -> Dict[str, Any]:
        """Fetches public X/Twitter post text via publish.twitter.com/oembed."""
        oembed_endpoint = f"https://publish.twitter.com/oembed?url={url}"
        try:
            resp = requests.get(oembed_endpoint, headers=self.headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                raw_html = data.get("html", "")
                author_name = data.get("author_name", "Unknown Author")
                author_url = data.get("author_url", "")

                text_content = self._clean_tweet_html(raw_html)
                return {
                    "success": True,
                    "url": url,
                    "platform": "x",
                    "author": author_name,
                    "author_url": author_url,
                    "title": f"Post by {author_name} on X",
                    "description": text_content[:200],
                    "text_content": text_content
                }
            else:
                logger.warning(f"X oEmbed returned status {resp.status_code} for {url}")
                return {
                    "success": False,
                    "url": url,
                    "platform": "x",
                    "error": f"HTTP {resp.status_code} from Twitter oEmbed"
                }
        except Exception as e:
            logger.error(f"Error fetching X post {url}: {e}")
            return {
                "success": False,
                "url": url,
                "platform": "x",
                "error": str(e)
            }

    def _clean_tweet_html(self, raw_html: str) -> str:
        """Strips HTML tags and formatters from oEmbed HTML to extract the pure text."""
        # Replace <br> and </p> with newlines
        text = re.sub(r"(?i)<br\s*/?>", "\n", raw_html)
        text = re.sub(r"(?i)</p>", "\n\n", text)
        
        # Remove trailing date link (e.g., &mdash; Satya Nadella (@satyanadella) <a href="...">October 12, 2026</a>)
        text = re.sub(r"(?i)&mdash;.*$", "", text, flags=re.DOTALL)
        text = re.sub(r"(?i)—.*$", "", text, flags=re.DOTALL)

        # Remove all remaining HTML tags
        text = re.sub(r"<[^>]+>", "", text)
        # Unescape HTML entities
        text = html.unescape(text)
        return text.strip()

    def _fetch_generic_web(self, url: str) -> Dict[str, Any]:
        """Fetches generic web page title and description metadata."""
        try:
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            if resp.status_code != 200:
                return {
                    "success": False,
                    "url": url,
                    "platform": "web",
                    "error": f"HTTP {resp.status_code}"
                }

            page_text = resp.text
            
            # Extract title
            title_match = re.search(r"(?i)<title[^>]*>(.*?)</title>", page_text)
            title = html.unescape(title_match.group(1).strip()) if title_match else ""

            # Extract OpenGraph description or meta description
            desc_match = re.search(r'(?i)<meta\s+property=["\']og:description["\']\s+content=["\'](.*?)["\']', page_text)
            if not desc_match:
                desc_match = re.search(r'(?i)<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', page_text)

            description = html.unescape(desc_match.group(1).strip()) if desc_match else ""

            text_content = description or title or "Web page content"

            return {
                "success": True,
                "url": url,
                "platform": "web",
                "title": title,
                "description": description,
                "text_content": text_content
            }
        except Exception as e:
            logger.error(f"Error fetching web page {url}: {e}")
            return {
                "success": False,
                "url": url,
                "platform": "web",
                "error": str(e)
            }


default_web_tools = WebTools()
