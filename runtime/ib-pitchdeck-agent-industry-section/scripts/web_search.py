#!/usr/bin/env python3
"""Search helper used by the skill research workflow.

The helper is provider-based so the same interface can use:
- SearXNG (local/remote instance)
- DuckDuckGo (ddgs / duckduckgo-search package)
- Tavily

In `auto` mode, provider order comes from `source_registry.json`:
`search_connectors.provider_order` (fallback: `searxng` -> `duckduckgo` -> `tavily`).
Features:
  - Proxy support via HTTP_PROXY / HTTPS_PROXY environment variables
  - Result quality filtering (removes noise, irrelevant domains)
  - Multi-query batch search (--queries "q1" "q2" "q3")
  - Query splitting for long CJK queries (better DDG results)
  - Site/domain-constrained search (--site, --sites, --site-mode)
  - Source registry integration (--source-registry, --source-pack)

Usage:
  python scripts/web_search.py -q "中国目标行业市场规模"
  python scripts/web_search.py -q "示例公司 营收" --provider tavily -n 3
  python scripts/web_search.py --queries "目标行业市场规模" "示例公司营收" "目标行业趋势" -o tmp/search_batch.json
  python scripts/web_search.py -q "中国目标细分市场发展现状及未来趋势分析" --split-query
  python scripts/web_search.py -q "年度报告 营收" --site cninfo.com.cn --site-mode priority
  python scripts/web_search.py -q "行业趋势" --source-pack china_official --source-registry templates/source_registry.json
  python scripts/web_search.py -q "行业趋势" --use-default-packs --source-registry templates/source_registry.json

Environment:
  TAVILY_API_KEY  - required for Tavily provider. Get free key at https://tavily.com
  HTTP_PROXY / HTTPS_PROXY - optional proxy URL for outbound requests
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCE_REGISTRY = SCRIPT_DIR.parent / "templates" / "source_registry.json"
SEARXNG_ENV = ("SEARXNG_BASE_URL", "SEARXNG_URL", "SEARXNG_ENDPOINT")
DEFAULT_PROVIDER_ORDER = ("searxng", "duckduckgo", "tavily")


# ── Proxy detection ──────────────────────────────────────────────

def detect_proxy():
    """Detect proxy from standard environment variables."""
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        val = os.environ.get(var)
        if val:
            return val
    return None


PROXY = detect_proxy()


@dataclass(frozen=True)
class SourceConnectorConfig:
    provider_order: tuple[str, ...]
    searxng_url: str
    searxng_timeout: float


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_timeout(value: Any, default: float) -> float:
    candidate = _coerce_float(value, default)
    if candidate <= 0:
        return max(default, 1.0)
    return candidate


def _pick_first(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _normalize_provider(provider: str) -> str:
    return str(provider or "").strip().lower()


def _load_connector_config(path: str) -> SourceConnectorConfig:
    registry = {}
    source_registry_path = Path(path or "").expanduser()
    if source_registry_path.exists():
        with source_registry_path.open("r", encoding="utf-8") as f:
            registry = json.load(f)
    connectors = registry.get("search_connectors", {})
    order = connectors.get("provider_order") or connectors.get("order") or connectors.get("provider_preference") or DEFAULT_PROVIDER_ORDER
    provider_order = tuple(str(item).strip().lower() for item in order if str(item).strip())
    if not provider_order:
        provider_order = DEFAULT_PROVIDER_ORDER

    searxng_cfg = connectors.get("searxng", {}) if isinstance(connectors, dict) else {}
    if not isinstance(searxng_cfg, dict):
        searxng_cfg = {}
    env_url = _pick_first(
        os.environ.get("SEARXNG_BASE_URL"),
        os.environ.get("SEARXNG_URL"),
        os.environ.get("SEARXNG_ENDPOINT"),
        searxng_cfg.get("default_url"),
    )
    return SourceConnectorConfig(
        provider_order=provider_order,
        searxng_url=env_url.strip(),
        searxng_timeout=_coerce_timeout(
            _pick_first(searxng_cfg.get("timeout_seconds"), os.environ.get("SEARXNG_TIMEOUT")), 20.0
        ),
    )


# ── Result quality filtering ─────────────────────────────────────

# Do not hard-code trusted industry sources here. Source quality should come
# from templates/source_registry.json and research policy, not from project- or
# sector-specific defaults in this fallback search helper.
TRUSTED_DOMAINS: set[str] = set()


def _host_of(url: str) -> str:
    """Extract normalized hostname from URL without collapsing public suffixes."""
    try:
        host = (urlparse(url).hostname or "").lower().strip(".")
        return host[4:] if host.startswith("www.") else host
    except Exception:
        return ""


def _host_matches(host: str, domain: str) -> bool:
    host = host.lower().strip(".")
    domain = domain.lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    if domain.startswith("www."):
        domain = domain[4:]
    return bool(domain) and (host == domain or host.endswith("." + domain))


def _url_matches_rule(url: str, rule: str) -> bool:
    """Match a host-only rule or a host/path rule against a URL."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    rule = rule.lower().strip()
    if not rule:
        return False
    if "://" in rule:
        parsed_rule = urlparse(rule)
        rule_host = (parsed_rule.hostname or "").lower().strip(".")
        rule_path = parsed_rule.path.rstrip("/")
    else:
        rule_host, _, rule_path = rule.partition("/")
        rule_host = rule_host.strip(".")
        rule_path = "/" + rule_path.rstrip("/") if rule_path else ""
    if rule_host.startswith("www."):
        rule_host = rule_host[4:]
    if not _host_matches(host, rule_host):
        return False
    if rule_path:
        return parsed.path.rstrip("/").startswith(rule_path)
    return True


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

        host = _host_of(url)

        # Skip extremely short snippets (likely junk)
        if snippet and len(snippet) < 20:
            continue

        # Boost score for trusted domains
        is_trusted = any(_host_matches(host, td) for td in TRUSTED_DOMAINS)

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
        # No good split points - try splitting on 与/和/及
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


# ── Source registry ──────────────────────────────────────────────

def load_source_registry(path: str) -> dict:
    """Load source_registry.json and return the parsed object."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def default_source_packs(registry_path: str) -> list[str]:
    """Return default source pack names from the registry."""
    registry = load_source_registry(registry_path)
    packs = registry.get("default_packs", [])
    if not isinstance(packs, list):
        raise RuntimeError("source registry default_packs must be an array")
    return [str(pack) for pack in packs]


def resolve_domains(
    source_pack_names: list[str],
    extra_domains: list[str],
    registry_path: Optional[str] = None,
) -> list[str]:
    """Resolve source pack names and extra domains into a flat, deduplicated domain list.

    Priority: explicit domains first, then source pack domains in order.
    """
    domains = list(extra_domains)
    seen = set(domains)

    if not source_pack_names:
        return domains

    if not registry_path:
        raise RuntimeError("source packs specified but no source registry path is available")

    try:
        registry = load_source_registry(registry_path)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        raise RuntimeError(f"cannot load source registry: {e}") from e

    packs = registry.get("source_packs", {})
    for pack_name in source_pack_names:
        pack = packs.get(pack_name)
        if pack is None:
            raise RuntimeError(f"source pack '{pack_name}' not found in registry")
        pack_domains = pack.get("domains", [])
        if not isinstance(pack_domains, list):
            raise RuntimeError(f"source pack '{pack_name}' domains must be an array")
        for d in pack_domains:
            if d not in seen:
                domains.append(d)
                seen.add(d)

    return domains


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


def search_searxng(
    query: str,
    max_results: int = 5,
    base_url: str = "",
    timeout: float = 20.0,
    search_path: str = "/search",
    format_param: str = "json",
) -> list[dict]:
    """Search via SearXNG endpoint."""
    if not base_url:
        raise RuntimeError("SearXNG base URL not configured. Set SEARXNG_BASE_URL or source_registry search_connectors.searxng.default_url.")

    base = base_url.rstrip("/")
    endpoint = f"{base}{search_path}"
    params = {
        "q": query,
        "format": format_param,
    }
    url = f"{endpoint}?{urlencode(params)}"

    request = Request(url, headers={"User-Agent": "ib-pitchdeck-agent-industry-section/web-search"})
    try:
        with urlopen(request, timeout=timeout, context=None) as response:
            payload = json.load(response)
    except URLError as exc:
        raise RuntimeError(f"SearXNG request failed: {exc}") from exc
    except Exception as exc:  # pragma: no cover - defensive for backend variations
        raise RuntimeError(f"SearXNG response parse error: {exc}") from exc

    raw_results = payload.get("results") if isinstance(payload, dict) else []
    if not isinstance(raw_results, list):
        raw_results = []

    results = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        results.append({
            "title": str(item.get("title", "")).strip(),
            "url": str(item.get("url", "") or item.get("href", "")).strip(),
            "snippet": str(item.get("content", "") or item.get("snippet", "") or item.get("description", "")).strip(),
            "provider": "searxng",
        })

    return results[:max_results]


def search_auto(
    query: str,
    max_results: int = 5,
    *,
    source_registry: str = str(DEFAULT_SOURCE_REGISTRY),
    searxng_url: str = "",
    searxng_timeout: float | None = None,
) -> list[dict]:
    """Auto mode: try providers by search_connectors.provider_order."""
    connector_cfg = _load_connector_config(source_registry)
    providers = connector_cfg.provider_order or DEFAULT_PROVIDER_ORDER
    for provider in providers:
        provider_key = _normalize_provider(provider)
        try:
            if provider_key == "searxng":
                registry = load_source_registry(source_registry)
                search_cfg = registry.get("search_connectors", {}).get("searxng", {})
                cfg_timeout = _coerce_timeout(search_cfg.get("timeout_seconds"), connector_cfg.searxng_timeout)
                timeout = (
                    _coerce_timeout(searxng_timeout, cfg_timeout)
                    if searxng_timeout is not None
                    else cfg_timeout
                )
                base_url = _pick_first(searxng_url, connector_cfg.searxng_url)
                results = search_searxng(
                    query,
                    max_results=max_results,
                    base_url=base_url,
                    timeout=timeout,
                    search_path=str(search_cfg.get("search_path") or "/search"),
                    format_param=str(search_cfg.get("format") or search_cfg.get("format_param") or "json"),
                )
            elif provider_key == "duckduckgo":
                results = search_duckduckgo(query, max_results=max_results)
            elif provider_key == "tavily":
                results = search_tavily(query, max_results=max_results)
            else:
                print(f"[web_search] Unknown provider '{provider}', skipping", file=sys.stderr)
                continue
        except Exception as exc:
            print(f"[web_search] {provider_key} failed: {exc}", file=sys.stderr)
            continue
        if results:
            return results
    raise RuntimeError("all web search providers failed or returned no results")


def _build_site_query(query: str, domain: str) -> str:
    """Build a site:domain query string."""
    return f"site:{domain} {query}"


def search_with_sites(
    queries: list[str],
    sites: list[str],
    site_mode: str,
    provider: str,
    max_results: int,
    source_packs: list[str],
) -> tuple[list[dict], list[dict]]:
    """Run queries with site: constraints and return (all_results, query_log_entries).

    site_mode='only': only run site-constrained queries.
    site_mode='priority': run site-constrained queries first, then fallback unrestricted if results are sparse.
    """
    # Site search only works reliably with DuckDuckGo in this workflow.
    # Tavily and SearXNG are not reliable for explicit site-domain constrained queries here.
    effective_provider = provider
    if provider in ("auto", "tavily", "searxng"):
        print("[web_search] Site search requires DuckDuckGo; switching provider to duckduckgo", file=sys.stderr)
        effective_provider = "duckduckgo"

    search_fn = PROVIDERS[effective_provider]
    all_results = []
    seen_urls = set()
    query_log = []

    for q in queries:
        for domain in sites:
            site_query = _build_site_query(q, domain)
            log_entry = {
                "query": site_query,
                "domain": domain,
                "result_count": 0,
                "mode": site_mode,
            }
            try:
                results = search_fn(site_query, max_results)
                log_entry["result_count"] = len(results)
                for r in results:
                    if r["url"] not in seen_urls:
                        seen_urls.add(r["url"])
                        all_results.append(r)
            except Exception as e:
                print(f"[web_search] Site query '{site_query}' failed: {e}", file=sys.stderr)
            query_log.append(log_entry)

    # In priority mode, if site-constrained results are sparse, fall back to unrestricted
    if site_mode == "priority" and len(all_results) < max_results:
        print(f"[web_search] Site-constrained results sparse ({len(all_results)}); running unrestricted queries...", file=sys.stderr)
        for q in queries:
            log_entry = {
                "query": q,
                "domain": None,
                "result_count": 0,
                "mode": "unrestricted_fallback",
            }
            try:
                results = search_fn(q, max_results)
                log_entry["result_count"] = len(results)
                for r in results:
                    if r["url"] not in seen_urls:
                        seen_urls.add(r["url"])
                        all_results.append(r)
            except Exception as e:
                print(f"[web_search] Unrestricted query '{q}' failed: {e}", file=sys.stderr)
            query_log.append(log_entry)

    return all_results, query_log


def search_multi_query(
    queries: list[str],
    provider: str,
    max_results: int = 5,
    *,
    source_registry: str = str(DEFAULT_SOURCE_REGISTRY),
    searxng_url: str = "",
    searxng_timeout: float | None = None,
) -> list[dict]:
    """Run multiple queries and merge + deduplicate results."""
    if provider == "auto":
        search_fn = lambda query, count: search_auto(
            query,
            count,
            source_registry=source_registry,
            searxng_url=searxng_url,
            searxng_timeout=searxng_timeout,
        )
    else:
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
    "searxng": search_searxng,
    "tavily": search_tavily,
    "duckduckgo": search_duckduckgo,
    "auto": search_auto,
}


# ── CLI ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Fallback web search with quality filtering (SearXNG -> DuckDuckGo -> Tavily)"
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
        help="Search provider (default: auto = SearXNG -> DuckDuckGo -> Tavily)",
    )
    parser.add_argument(
        "--provider-registry",
        default=str(DEFAULT_SOURCE_REGISTRY),
        help="Path to templates/source_registry.json for search connector config.",
    )
    parser.add_argument(
        "--searxng-url",
        default="",
        help="Override SearXNG base URL when provider is searxng/auto.",
    )
    parser.add_argument(
        "--searxng-timeout",
        type=float,
        default=None,
        help="Override SearXNG timeout seconds when provider is searxng/auto.",
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
    # Site / domain-constrained search
    parser.add_argument(
        "--site",
        help="Constrain search to a single domain (e.g., cninfo.com.cn). Forces DuckDuckGo provider."
    )
    parser.add_argument(
        "--sites", nargs="+",
        help="Constrain search to multiple domains. Forces DuckDuckGo provider."
    )
    parser.add_argument(
        "--site-mode",
        choices=["priority", "only"],
        default="priority",
        help="priority = site search first, fallback unrestricted if sparse; only = site search only (default: priority)"
    )
    parser.add_argument(
        "--source-registry",
        default=str(DEFAULT_SOURCE_REGISTRY),
        help="Path to templates/source_registry.json for resolving source packs"
    )
    parser.add_argument(
        "--source-pack", action="append", dest="source_packs", default=[],
        help="Source pack name(s) from the registry to use as domain constraints (repeatable: --source-pack china_official --source-pack consulting_reports)"
    )
    parser.add_argument(
        "--use-default-packs", action="store_true",
        help="Use default_packs from the source registry as domain constraints. Opt-in only to avoid excessive site: queries."
    )
    args = parser.parse_args()

    if not args.query and not args.queries:
        parser.error("Must specify --query or --queries")

    # Resolve queries
    queries = args.queries or [args.query]
    if args.split_query and len(queries) == 1:
        queries = split_cjk_query(queries[0])
        print(f"[web_search] Split into {len(queries)} sub-queries: {queries}", file=sys.stderr)

    # Resolve sites from --site, --sites, and --source-pack
    sites = []
    if args.site:
        sites.append(args.site)
    if args.sites:
        for s in args.sites:
            if s not in sites:
                sites.append(s)

    source_packs = list(args.source_packs)
    if args.use_default_packs and not source_packs:
        try:
            source_packs = default_source_packs(args.source_registry)
            if source_packs:
                print(f"[web_search] Using default source packs: {source_packs}", file=sys.stderr)
        except Exception as e:
            raise RuntimeError(f"cannot load default source packs: {e}") from e

    # Resolve source pack domains
    if source_packs:
        pack_domains = resolve_domains(source_packs, [], args.source_registry)
        for d in pack_domains:
            if d not in sites:
                sites.append(d)

    query_log = []
    if sites:
        print(f"[web_search] Site mode: {args.site_mode}, domains: {sites}", file=sys.stderr)
        provider_for_site = args.provider
        if provider_for_site == "auto":
            provider_for_site = _normalize_provider(_load_connector_config(args.provider_registry).provider_order[0])
        all_results, query_log = search_with_sites(
            queries=queries,
            sites=sites,
            site_mode=args.site_mode,
            provider=provider_for_site if provider_for_site else args.provider,
            max_results=args.max_results,
            source_packs=source_packs,
        )
        provider_used = "duckduckgo"  # Site search always uses DDG
    elif len(queries) > 1:
        print(f"[web_search] Running {len(queries)} queries...", file=sys.stderr)
        all_results = search_multi_query(
            queries,
            args.provider,
            args.max_results,
            source_registry=str(args.provider_registry),
            searxng_url=str(args.searxng_url),
            searxng_timeout=args.searxng_timeout,
        )
        provider_used = args.provider
        if provider_used == "auto" and all_results:
            provider_used = all_results[0].get("source", "unknown")
        # Build simple query log for non-site mode
        for q in queries:
            query_log.append({
                "query": q,
                "domain": None,
                "result_count": None,
                "mode": "unrestricted",
            })
    else:
        search_fn = PROVIDERS[args.provider]
        if args.provider == "auto":
            all_results = search_fn(
                queries[0],
                args.max_results,
                source_registry=str(args.provider_registry),
                searxng_url=str(args.searxng_url),
                searxng_timeout=args.searxng_timeout,
            )
        elif args.provider == "searxng":
            connector = _load_connector_config(str(args.provider_registry))
            search_cfg = load_source_registry(args.provider_registry).get("search_connectors", {}).get("searxng", {})
            all_results = search_fn(
                queries[0],
                args.max_results,
                base_url=connector.searxng_url or str(args.searxng_url),
                timeout=_coerce_timeout(args.searxng_timeout, connector.searxng_timeout),
                search_path=str(search_cfg.get("search_path") or "/search"),
                format_param=str(search_cfg.get("format") or search_cfg.get("format_param") or "json"),
            )
        else:
            all_results = search_fn(queries[0], args.max_results)
        provider_used = args.provider
        if provider_used == "auto" and all_results:
            provider_used = all_results[0].get("source", "unknown")
        query_log.append({
            "query": queries[0],
            "domain": None,
            "result_count": None,
            "mode": "unrestricted",
        })

    results = all_results

    # Filter
    if not args.no_filter:
        query_for_filter = " ".join(queries)
        before = len(results)
        results = filter_results(results, query_for_filter)
        filtered = before - len(results)
        if filtered:
            print(f"[web_search] Filtered out {filtered} low-quality results", file=sys.stderr)

    # Populate actual result counts in query log after filtering
    # (We don't know per-query counts post-merge, so leave as-is or update from pre-filter)

    output = {
        "queries": queries,
        "provider": provider_used,
        "result_count": len(results),
        "timestamp": datetime.now().isoformat(),
        "results": results,
    }

    # Add site/search metadata when site search or source packs are active
    if sites:
        output["site_mode"] = args.site_mode
        output["sites"] = sites
        output["source_packs"] = source_packs
        output["queries_executed"] = query_log
    elif source_packs:
        output["source_packs"] = source_packs
        output["queries_executed"] = query_log

    json_str = json.dumps(output, ensure_ascii=False, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            f.write(json_str)
        print(f"[web_search] {len(results)} results written to {args.output}", file=sys.stderr)
    else:
        print(json_str)

    if not results:
        print("[web_search] ERROR: no search results returned", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
