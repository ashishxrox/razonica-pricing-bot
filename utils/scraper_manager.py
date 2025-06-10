# Scraper_manager.py

import asyncio
import importlib
from typing import List, Dict, Any

# Define a mapping between platform name and its scraper module/class name
SCRAPERS = {
    "ajio": "scrapers.Ajio_scraper_re",
    "myntra": "scrapers.Myntra_scraper_re",
    "amazon": "scrapers.Amazon_scrape_re",
    "flipkart": "scrapers.Flipkart_scrape_re"
}


class ScraperManager:
    def __init__(self):
        self._scrapers = {}

    def load_scraper(self, platform: str):
        """
        Dynamically load the scraper module for a platform.
        Assumes each module exposes an async function: `async def scrape(keywords: List[str], limit: int)`
        """
        if platform not in SCRAPERS:
            raise ValueError(f"Unsupported platform: {platform}")
        if platform not in self._scrapers:
            module_path = SCRAPERS[platform]
            module = importlib.import_module(module_path)
            if not hasattr(module, "scrape"):
                raise AttributeError(f"Module {module_path} missing required `scrape` function")
            self._scrapers[platform] = module.scrape
        return self._scrapers[platform]

    async def scrape_platform(self, platform: str, keywords: List[str], limit: int) -> List[Dict[str, Any]]:
        """Run the specified platform scraper with given inputs."""
        scrape_func = self.load_scraper(platform)
        return await scrape_func(keywords, limit)

    async def run_all(self, platforms: List[str], keywords: List[str], limit: int) -> Dict[str, List[Dict[str, Any]]]:
        """
        Launch all selected platform scrapers concurrently.
        Returns a dictionary mapping platform -> list of result dicts.
        """
        tasks = []
        for platform in platforms:
            tasks.append(self.scrape_platform(platform, keywords, limit))

        results_list = await asyncio.gather(*tasks, return_exceptions=True)
        aggregated: Dict[str, List[Dict[str, Any]]] = {}
        for platform, result in zip(platforms, results_list):
            if isinstance(result, Exception):
                aggregated[platform] = []
                print(f"[ScraperManager] Error scraping {platform}: {result}")
            else:
                aggregated[platform] = result

        return aggregated

# If run as script for testing
if __name__ == "__main__":
    import json
    async def main():
        manager = ScraperManager()
        platforms = ["myntra", "ajio", "amazon","flipkart"]
        keywords = ["saree"]
        limit = 2
        results = await manager.run_all(platforms, keywords, limit)

        # Print some results
        for platform, items in results.items():
            print(f"\n--- {platform.upper()} ({len(items)} items) ---")
            for item in items[:3]:
                print(item)

        # Save to JSON
        output_path = "scraped_data.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=4)
        print(f"\nSaved results to {output_path}")

    asyncio.run(main())

