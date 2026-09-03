import logging
from bs4 import BeautifulSoup
"""
Federal Reserve Web Scraping Client

This module handles the direct acquisition of primary source documents from the Federal Reserve's official website. It targets specific press release URLs and isolates the monetary policy text from the surrounding HTML structure.

Key Operations:
1. HTTP Requests: Connects to `federalreserve.gov` to download the raw HTML of FOMC communications.
2. DOM Parsing: Utilizes BeautifulSoup to navigate the Document Object Model, targeting specific `div` containers to extract only the relevant statement text while stripping away headers, footers, and stylistic elements.

Configuration Parameters:
- DOM Selectors: The CSS selectors and HTML tags used to isolate the text are defined in `get_statement`. These must be updated if the Federal Reserve redesigns their web architecture.
"""
import requests
from typing import List, Dict, Optional
import datetime
import re
from app.core.logger import setup_logger

logger = setup_logger(__name__)

class FedScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        })
        self.base_url = "https://www.federalreserve.gov"
        
    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch a page and return its HTML text."""
        try:
            logger.info(f"Fetching {url}")
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                response.encoding = 'utf-8' # Force UTF-8 for Fed site
                return response.text
            else:
                logger.warning(f"Failed to fetch {url}: Status code {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None

    def clean_text(self, html: str) -> str:
        """Extract and clean text from article HTML."""
        soup = BeautifulSoup(html, 'lxml')
        
        # The main content is usually in a div with id 'article' or similar. 
        # Fed statements often have their core text in div#article
        article = soup.find('div', id='article')
        if not article:
            # Fallback if id='article' is not present
            article = soup.find('div', class_='col-xs-12 col-sm-8 col-md-8')
            if not article:
                article = soup.find('body')
                
        # Remove script and style tags
        for script in article(["script", "style", "nav", "footer", "header"]):
            script.extract()
            
        text = article.get_text(separator='\n')
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text

    def get_statement(self, date_str: str) -> Optional[str]:
        """
        Fetch statement for a specific date (YYYYMMDD).
        Statement URL format: /newsevents/pressreleases/monetaryYYYYMMDDa.htm
        """
        url = f"{self.base_url}/newsevents/pressreleases/monetary{date_str}a.htm"
        html = self.fetch_page(url)
        if html:
            return self.clean_text(html)
        return None

    def get_minutes(self, date_str: str) -> Optional[str]:
        """
        Fetch minutes for a specific date (YYYYMMDD).
        Minutes URL format: /monetarypolicy/fomcminutesYYYYMMDD.htm
        """
        url = f"{self.base_url}/monetarypolicy/fomcminutes{date_str}.htm"
        html = self.fetch_page(url)
        if html:
            return self.clean_text(html)
        return None

    def get_recent_meeting_dates(self) -> List[str]:
        """
        Fetch the calendar page and parse out the most recent meeting dates.
        Returns a list of date strings in YYYYMMDD format.
        """
        # Using the last 16 meetings (Exactly 2 years: Sept 2024 - Sept 2026)
        dates = [
            "20260729",
            "20260617",
            "20260429",
            "20260318",
            "20260128",
            "20251210",
            "20251029",
            "20250917",
            "20250730",
            "20250618",
            "20250507",
            "20250319",
            "20250129",
            "20241218",
            "20241107",
            "20240918"
        ]
        return dates

if __name__ == "__main__":
    scraper = FedScraper()
    dates = scraper.get_recent_meeting_dates()
    
    print(f"Testing scraper on 3 recent meetings...")
    for date in dates[:3]:
        print(f"\n--- Meeting Date: {date} ---")
        
        statement = scraper.get_statement(date)
        if statement:
            print(f"Statement found. Length: {len(statement)} chars")
            print(f"Snippet: {statement[:200]}...\n")
        else:
            print("Statement NOT found.")
            
        minutes = scraper.get_minutes(date)
        if minutes:
            print(f"Minutes found. Length: {len(minutes)} chars")
            print(f"Snippet: {minutes[:200]}...\n")
        else:
            print("Minutes NOT found.")
