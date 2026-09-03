import logging
from bs4 import BeautifulSoup
import requests
from typing import List, Dict, Optional
import datetime
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        # Hardcoding the last 10 meetings for 2024-2023 for MVP reliability
        # In a full production system, we would parse the calendar page dynamically.
        # Format is YYYYMMDD. For two-day meetings, this is the SECOND day.
        dates = [
            "20240918",
            "20240731",
            "20240612",
            "20240501",
            "20240320",
            "20240131",
            "20231213",
            "20231101",
            "20230920",
            "20230726"
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
