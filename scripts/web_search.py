#!/usr/bin/env python3
"""Fallback web search tool for use when Claude Code's built-in WebSearch is unavailable
(e.g., when using third-party API proxies that don't support the tool).

Search priority: Tavily (AI-optimized) → DuckDuckGo (free fallback)

Features:
  - Proxy support via HTTP_PROXY / HTTPS_PROXY environment variables
  - Result quality filtering (removes noise, irrelevant domains)
  - Multi-query batch search (--queries "q1" "q2" "q3")
  - Query splitting for long CJK queries (better DDG results)

Usage:
  python scripts/web_search.py -q "中国目标行业市场规模"
  python scripts/web_search.py -q "示例公司 营收" --provider tavily -n 3
  python scripts/web_search.py --queries "目标行业市场规模" "示例公司营收" "目标行业趋势" -o tmp/search_batch.json
  python scripts/web_search.py -q "中国目标细分市场发展现状及未来趋势分析" --split-query

Environment:
  TAVILY_API_KEY  — required for Tavily provider. Get free key at https://tavily.com
  HTTP_PROXY / HTTPS_PROXY — optional proxy URL for outbound requests
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from urllib.parse import urlparse


# ── Proxy detection ──────────────────────────────────────────────

def detect_proxy():
    """Detect proxy from standard environment variables."""
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        val = os.environ.get(var)
        if val:
            return val
    return None


PROXY = detect_proxy()

# ── Result quality filtering ─────────────────────────────────────

# Domains that are never useful for industry research
BLOCKED_DOMAINS = {
    "microsoft.com", "support.microsoft.com", "answers.microsoft.com",
    "learn.microsoft.com", "office.com", "live.com", "outlook.com",
    "xbox.com", "windows.com", "bing.com",
    "youtube.com", "facebook.com", "twitter.com", "x.com",
    "instagram.com", "tiktok.com", "reddit.com",
    "amazon.com", "ebay.com",
    # Chinese noise
    "zhihu.com/question",  # Q&A noise (keep zhihu.com/column)
    "douyin.com", "kuaishou.com",
    # Proxy/VPN/tool sites
    "clash.download", "github.com/Clash", "v2ray.com",
    # Generic content farms
    "wikihow.com", "quora.com", "pinterest.com",
}

# Domains that are high-quality for Chinese industry research
TRUSTED_DOMAINS = {
    "iresearch.com.cn", "chyxx.com", "chinabaogao.com",
    "chinairn.com", "askci.com", "163.com", "sohu.com",
    "36kr.com", "yilantop.com", "chinabeauty.cn",
    "maogepingbeauty.com", "baike.baidu.com",
    "wikipedia.org", "euromonitor.com",
    "pdf.dfcfw.com", "eastmoney.com", "cninfo.com.cn",
    "gonyn.com", "marymur.com",
}


def _domain_of(url: str) -> str:
    """Extract root domain from URL."""
    try:
        host = urlparse(url).hostname or ""
        parts = host.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return host
    except Exception:
        return ""


def filter_results(results: list[dict], query: str = "") -> list[dict]:
    """Filter out low-quality or irrelevant search results."""
    filtered = []
    seen_urls = set()

    for r in results:
        url = r.get("url", "")
        title = r.get("title", "").strip()
        snippet = r.get("snippet", "").strip()

        # Deduplicate by URL
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Skip empty results
        if not url or (not title and not snippet):
            continue

        # Skip blocked domains
        domain = _domain_of(url)
        if any(domain.endswith(bd) for bd in BLOCKED_DOMAINS):
            continue

        # Skip extremely short snippets (likely junk)
        if snippet and len(snippet) < 20:
            continue

        # Boost score for trusted domains
        is_trusted = any(domain.endswith(td) for td in TRUSTED_DOMAINS)

        # Basic relevance check: if query has CJK chars, check overlap
        relevance = 0.0
        if query:
            query_chars = set(re.findall(r'[\u4e00-\u9fff]', query))
            text_chars = set(re.findall(r'[\u4e00-\u9fff]', title + snippet))
            if query_chars:
                overlap = len(query_chars & text_chars) / len(query_chars)
                relevance = overlap

        r["_quality_score"] = (1.0 if is_trusted else 0.0) + relevance
        r["_is_trusted"] = is_trusted
        filtered.append(r)

    # Sort by quality score descending
    filtered.sort(key=lambda x: x["_quality_score"], reverse=True)

    # Remove internal scoring fields
    for r in filtered:
        r.pop("_quality_score", None)
        r.pop("_is_trusted", None)

    return filtered


# ── Query splitting ──────────────────────────────────────────────

def split_cjk_query(query: str) -> list[str]:
    """Split a long CJK query into shorter sub-queries for better DDG results.

    Strategy: split on common delimiters, then group short segments.
    If the query is short enough (< 15 chars), return as-is.
    """
    if len(query) < 15:
        return [query]

    # Split on spaces, commas, Chinese punctuation
    segments = re.split(r'[\s,，、；;。.!！?？]+', query)
    segments = [s.strip() for s in segments if s.strip()]

    if len(segments) <= 1:
        # No good split points — try splitting on 与/和/及
        parts = re.split(r'[与和及]', query)
        if len(parts) > 1:
            return [p.strip() for p in parts if p.strip()]
        # Last resort: take first 10 chars
        return [query[:12]]

    # Group segments into queries of ~2-3 segments each
    queries = []
    for seg in segments:
        # Skip pure numbers and very short segments
        if re.match(r'^\d+$', seg) or len(seg) < 3:
            if queries:
                queries[-1] += " " + seg  # Append to previous as context
            continue
        if len(seg) >= 4:
            queries.append(seg)
        elif queries:
            queries[-1] += " " + seg
        else:
            queries.append(seg)

    return queries[:4]  # Cap at 4 sub-queries


# ── Search providers ─────────────────────────────────────────────

def search_tavily(query: str, max_results: int = 5) -> list[dict]:
    """Search via Tavily API."""
    try:
        from tavily import TavilyClient
    except ImportError:
        raise RuntimeError("tavily-python not installed. Run: pip install tavily-python")

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("TAVILY_API_KEY environment variable not set")

    client = TavilyClient(api_key=api_key)
    response = client.search(query=query, max_results=max_results, search_depth="advanced")

    results = []
    for item in response.get("results", []):
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": item.get("content", ""),
            "source": "tavily",
        })
    return results


def search_duckduckgo(query: str, max_results: int = 5) -> list[dict]:
    """Search via DuckDuckGo."""
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            raise RuntimeError("ddgs not installed. Run: pip install ddgs")

    if PROXY:
        print(f"[web_search] Using proxy: {PROXY}", file=sys.stderr)

    with DDGS(proxy=PROXY) as ddgs:
        raw = list(ddgs.text(query, max_results=max_results))

    results = []
    for item in raw:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("href", ""),
            "snippet": item.get("body", ""),
            "source": "duckduckgo",
        })
    return results


def search_auto(query: str, max_results: int = 5) -> list[dict]:
    """Auto mode: try Tavily first, fallback to DuckDuckGo."""
    if os.environ.get("TAVILY_API_KEY"):
        try:
            results = search_tavily(query, max_results)
            if results:
                return results
        except Exception as e:
            print(f"[web_search] Tavily failed: {e}", file=sys.stderr)
    else:
        print("[web_search] TAVILY_API_KEY not set, skipping Tavily", file=sys.stderr)

    try:
        print("[web_search] Falling back to DuckDuckGo", file=sys.stderr)
        return search_duckduckgo(query, max_results)
    except Exception as e:
        print(f"[web_search] DuckDuckGo failed: {e}", file=sys.stderr)
        return []


def search_multi_query(queries: list[str], provider: str, max_results: int = 5) -> list[dict]:
    """Run multiple queries and merge + deduplicate results."""
    search_fn = PROVIDERS[provider]
    all_results = []
    seen_urls = set()

    for q in queries:
        try:
            results = search_fn(q, max_results)
            for r in results:
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    r["_query"] = q  # Track which query found this
                    all_results.append(r)
        except Exception as e:
            print(f"[web_search] Query '{q}' failed: {e}", file=sys.stderr)

    # Clean up internal field
    for r in all_results:
        r.pop("_query", None)

    return all_results


PROVIDERS = {
    "tavily": search_tavily,
    "duckduckgo": search_duckduckgo,
    "auto": search_auto,
}


# ── CLI ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fallback web search with quality filtering (Tavily → DuckDuckGo)"
    )
    parser.add_argument("--query", "-q", help="Single search query")
    parser.add_argument(
        "--queries", nargs="+",
        help="Multiple queries (batch mode, results merged and deduplicated)"
    )
    parser.add_argument(
        "--split-query", action="store_true",
        help="Auto-split long CJK query into shorter sub-queries for better results"
    )
    parser.add_argument(
        "--provider",
        choices=list(PROVIDERS.keys()),
        default="auto",
        help="Search provider (default: auto = Tavily → DuckDuckGo)",
    )
    parser.add_argument(
        "--max-results", "-n", type=int, default=5,
        help="Max results per query (default: 5)"
    )
    parser.add_argument(
        "--no-filter", action="store_true",
        help="Disable quality filtering"
    )
    parser.add_argument(
        "--output", "-o", help="Output JSON file path (default: stdout)"
    )
    args = parser.parse_args()

    if not args.query and not args.queries:
        parser.error("Must specify --query or --queries")

    # Resolve queries
    queries = args.queries or [args.query]
    if args.split_query and len(queries) == 1:
        queries = split_cjk_query(queries[0])
        print(f"[web_search] Split into {len(queries)} sub-queries: {queries}", file=sys.stderr)

    # Search
    if len(queries) > 1:
        print(f"[web_search] Running {len(queries)} queries...", file=sys.stderr)
        results = search_multi_query(queries, args.provider, args.max_results)
    else:
        search_fn = PROVIDERS[args.provider]
        results = search_fn(queries[0], args.max_results)

    # Filter
    if not args.no_filter:
        query_for_filter = " ".join(queries)
        before = len(results)
        results = filter_results(results, query_for_filter)
        filtered = before - len(results)
        if filtered:
            print(f"[web_search] Filtered out {filtered} low-quality results", file=sys.stderr)

    # Output
    provider_used = args.provider
    if provider_used == "auto" and results:
        provider_used = results[0].get("source", "unknown")

    output = {
        "queries": queries,
        "provider": provider_used,
        "result_count": len(results),
        "timestamp": datetime.now().isoformat(),
        "results": results,
    }

    json_str = json.dumps(output, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"[web_search] {len(results)} results written to {args.output}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
