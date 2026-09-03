import os
import logging
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FredClient:
    def __init__(self):
        self.api_key = os.getenv("FRED_API_KEY")
        if not self.api_key or "paste_your" in self.api_key:
            raise ValueError("FRED_API_KEY is not set correctly in .env")
        
        self.base_url = "https://api.stlouisfed.org/fred"
        
        # Core series identified in the implementation plan
        self.target_series = {
            "PCEPILFE": "Core PCE Price Index",
            "CPIAUCSL": "CPI All Items",
            "CPILFESL": "Core CPI",
            "UNRATE": "Unemployment Rate",
            "PAYEMS": "Nonfarm Payrolls",
            "FEDFUNDS": "Fed Funds Effective Rate",
            "DGS2": "2-Year Treasury Yield",
            "DGS10": "10-Year Treasury Yield",
            "T10YIE": "10-Year Breakeven Inflation",
            "GDPC1": "Real GDP",
            "CIVPART": "Labor Force Participation Rate",
            "LNS11300060": "Prime-Age LFPR (25-54)"
        }

    def fetch_series_observations(self, series_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch the most recent observations for a series, along with their realtime (release) dates.
        We use realtime_start as a proxy for release_date for MVP purposes.
        """
        url = f"{self.base_url}/series/observations"
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc", # Get newest first
            "limit": limit
        }
        
        try:
            logger.info(f"Fetching observations for {series_id}")
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                observations = []
                for obs in data.get('observations', []):
                    # Only parse valid numeric values
                    if obs.get('value') != '.':
                        try:
                            observations.append({
                                'date': obs['date'],
                                'value': float(obs['value']),
                                'release_date': obs['realtime_start'] # Track when this was available
                            })
                        except ValueError:
                            continue
                return observations
            else:
                logger.error(f"Failed to fetch {series_id}: {response.text}")
                return []
        except Exception as e:
            logger.error(f"Error fetching {series_id}: {e}")
            return []

if __name__ == "__main__":
    client = FredClient()
    
    print("Testing FRED API connection...")
    
    # Test with Unemployment Rate (UNRATE)
    series_id = "UNRATE"
    print(f"\nFetching recent data for: {client.target_series[series_id]} ({series_id})")
    
    observations = client.fetch_series_observations(series_id, limit=5)
    
    if observations:
        print(f"Successfully fetched {len(observations)} observations!")
        for obs in observations:
            print(f"Date: {obs['date']} | Value: {obs['value']}% | Was Available On: {obs['release_date']}")
    else:
        print("Failed to fetch observations.")
