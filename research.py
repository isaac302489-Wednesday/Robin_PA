"""Background research engine - completely free, no API keys needed"""
from duckduckgo_search import DDGS

async def search_web(query: str, max_results: int = 8):
    """Search the web using DuckDuckGo (100% free, unlimited)"""
    try:
        with DDGS() as ddgs:
            results = []
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", "No title"),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", "")
                })
            return results
    except Exception as e:
        return [{"title": "Search Error", "snippet": str(e), "url": ""}]
