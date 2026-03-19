# -*- coding: utf-8 -*-
"""
browser.py — Web browsing engine for NEXUS agents.

Two-tier approach:
  1. Jina Reader (fast, no browser, free) — for most pages
  2. Playwright (full headless Chrome) — for JS-heavy sites

Usage:
  pip install playwright
  playwright install chromium
"""

import urllib.request
import urllib.parse
import json
import re
import sys
import os

TIMEOUT = 20

# ── Jina Reader — instant URL to clean text, no browser needed ───────────────

def read_url_jina(url: str) -> str:
    """Convert any URL to clean readable text via Jina Reader. Free, no key."""
    jina_url = f"https://r.jina.ai/{url}"
    try:
        req = urllib.request.Request(jina_url, headers={
            "User-Agent": "NEXUS-Agency/1.0",
            "Accept": "text/plain",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            # Trim to reasonable size
            return content[:8000].strip()
    except Exception as e:
        print(f"[Browser] Jina error for {url[:60]}: {e}")
        return ""


# ── DuckDuckGo Search — free, no API key ─────────────────────────────────────

def search_web(query: str, num_results: int = 6) -> list:
    """
    Search the web via DuckDuckGo HTML endpoint.
    Returns list of {title, url, snippet}.
    """
    encoded = urllib.parse.quote_plus(query)
    search_url = f"https://html.duckduckgo.com/html/?q={encoded}"

    try:
        req = urllib.request.Request(search_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[Browser] DDG search error: {e}")
        return []

    results = []

    # Parse result links
    link_pattern = re.compile(
        r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        re.DOTALL | re.IGNORECASE
    )
    snippet_pattern = re.compile(
        r'class="result__snippet"[^>]*>(.*?)</(?:a|span|div)>',
        re.DOTALL | re.IGNORECASE
    )

    links = link_pattern.findall(html)
    snippets = snippet_pattern.findall(html)

    for i, (url, title) in enumerate(links[:num_results]):
        # DDG uses redirect URLs — extract real URL
        if "uddg=" in url:
            try:
                real_url = urllib.parse.unquote(
                    re.search(r"uddg=([^&]+)", url).group(1)
                )
                url = real_url
            except Exception:
                pass

        title = re.sub(r"<[^>]+>", "", title).strip()
        snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip() if i < len(snippets) else ""

        if url and title and not url.startswith("//duckduckgo"):
            results.append({
                "title": title[:100],
                "url": url,
                "snippet": snippet[:200],
            })

    return results


def format_search_results(query: str, results: list) -> str:
    if not results:
        return f"🔍 *Search: {query}*\n\nNo results found. Try different keywords."

    lines = [
        f"🔍 *Web Search  |  {query}*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"_{len(results)} results_\n",
    ]
    for i, r in enumerate(results, 1):
        lines.append(
            f"*{i}. [{r['title']}]({r['url']})*\n"
            f"   _{r['snippet']}_\n"
        )
    lines.append("_Use /browse [url] to read any result in full_")
    return "\n".join(lines)


# ── Playwright — full headless Chrome for JS-heavy sites ─────────────────────

def _playwright_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        return True
    except ImportError:
        return False


def read_url_playwright(url: str) -> str:
    """Use headless Chromium to render and read a page."""
    if not _playwright_available():
        return ""

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)  # Let JS render

            # Extract readable text
            content = page.evaluate("""() => {
                // Remove noise
                ['script','style','nav','footer','header','aside',
                 '.ad','.ads','#cookie','#banner'].forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => el.remove());
                });
                return document.body ? document.body.innerText : document.documentElement.innerText;
            }""")

            browser.close()
            # Clean up whitespace
            content = re.sub(r'\n{3,}', '\n\n', content or "").strip()
            return content[:8000]
    except Exception as e:
        print(f"[Browser] Playwright error for {url[:60]}: {e}")
        return ""


def screenshot_url(url: str, save_path: str) -> bool:
    """Take a screenshot of a URL. Returns True on success."""
    if not _playwright_available():
        return False
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            page.screenshot(path=save_path, full_page=False)
            browser.close()
            return True
    except Exception as e:
        print(f"[Browser] Screenshot error: {e}")
        return False


# ── Smart router — Jina first, Playwright fallback ────────────────────────────

def read_page(url: str) -> str:
    """
    Read a URL intelligently.
    Tries Jina first (fast), falls back to Playwright if content is thin.
    """
    # Fix URL if no protocol
    if not url.startswith("http"):
        url = "https://" + url

    print(f"[Browser] Reading: {url[:80]}")

    # Try Jina first
    content = read_url_jina(url)
    if content and len(content) > 200:
        print(f"[Browser] Jina OK ({len(content)} chars)")
        return content

    # Fall back to Playwright
    if _playwright_available():
        print(f"[Browser] Falling back to Playwright...")
        content = read_url_playwright(url)
        if content:
            print(f"[Browser] Playwright OK ({len(content)} chars)")
            return content

    return f"Could not read content from {url}. The page may require authentication or be unavailable."


def format_page_summary(url: str, content: str, question: str = "") -> str:
    """Format page content for passing to Claude."""
    if question:
        return (
            f"URL: {url}\n\n"
            f"Page content:\n{content}\n\n"
            f"User question: {question}\n\n"
            f"Answer the question based on the page content above."
        )
    return (
        f"URL: {url}\n\n"
        f"Page content:\n{content}\n\n"
        f"Summarize this page. Extract the key information, main points, and anything actionable."
    )
