"""Background research engine - multiple free sources for reliability"""
import asyncio
from duckduckgo_search import DDGS

async def search_web(query: str, max_results: int = 8):
    """Search the web using DuckDuckGo (100% free, unlimited)"""
    try:
        # Run DDGS in a thread pool since it can block
        def _ddgs_search():
            with DDGS() as ddgs:
                results = []
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", "No title"),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", "")
                    })
                return results

        results = await asyncio.to_thread(_ddgs_search)

        if not results:
            # Fallback: try with lite backend
            def _ddgs_fallback():
                with DDGS() as ddgs:
                    results = []
                    for r in ddgs.text(query, max_results=max_results, backend="lite"):
                        results.append({
                            "title": r.get("title", "No title"),
                            "url": r.get("href", ""),
                            "snippet": r.get("body", "")
                        })
                    return results

            results = await asyncio.to_thread(_ddgs_fallback)

        return results if results else []

    except Exception as e:
        print(f"[SEARCH ERROR] {e}")
        return []
