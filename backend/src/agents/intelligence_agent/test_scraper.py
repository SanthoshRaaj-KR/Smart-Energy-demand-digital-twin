"""
Quick test script to verify the scraper fixes work correctly.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from scrapers.multi_source import MultiSourceScraper

def test_quick_scrape():
    """Test the scraper with timeout and SSL bypass."""
    print("=" * 70)
    print("TESTING SCRAPER WITH TIMEOUT & SSL BYPASS")
    print("=" * 70)
    
    scraper = MultiSourceScraper()
    
    # Test targeted scrape (faster)
    print("\n[TEST] Running targeted scrape (official + energy feeds only)...")
    articles = scraper.scrape_targeted()
    
    print(f"\n{'='*70}")
    print(f"✅ SUCCESS! Scraped {len(articles)} articles")
    print(f"{'='*70}")
    
    if articles:
        print("\nSample articles:")
        for i, article in enumerate(articles[:5], 1):
            print(f"\n{i}. {article.title[:80]}")
            print(f"   Source: {article.source_name}")
            print(f"   URL: {article.url[:70]}...")
    
    return len(articles) > 0

if __name__ == "__main__":
    success = test_quick_scrape()
    sys.exit(0 if success else 1)
