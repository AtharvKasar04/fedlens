"""
FRED Data Ingestion Module

This module is responsible for retrieving macroeconomic indicator data from the Federal Reserve Economic Data (FRED) API and persisting it to the PostgreSQL database. The data ingested here serves as the empirical ground truth for evaluating FOMC statements. 

Key Operations:
- Initializes a connection to the FRED API via `FredClient`.
- Iterates through a predefined list of target economic series.
- Fetches historical observations and ensures they are stored with their original release dates to prevent look-ahead bias during historical analysis.

Configuration Parameters:
- `frequency`: Adjusts the sampling frequency (default: "Monthly").
- `limit`: Controls the historical window of data fetched (default: 120 months / 10 years).
"""
import logging
from datetime import datetime

from app.ingestion.fred_client import FredClient
from app.db.session import SessionLocal
from app.db.models import EconomicSeries, EconomicObservation
from app.core.logger import setup_logger

logger = setup_logger(__name__)

class FredIngester:
    """
    The orchestrator for downloading FRED data. It connects the API client (FredClient) 
    to our Database (SQLAlchemy).
    """
    def __init__(self):
        # Initialize the API client that handles the actual HTTP requests
        self.client = FredClient()
        
    def populate_database(self):
        """
        The main loop. It goes through every economic indicator we care about (UNRATE, PCE, etc.),
        downloads the latest data points, and safely inserts them into the database without duplicating.
        """
        db = SessionLocal()
        
        try:
            logger.info("Starting FRED Data Ingestion...")
            
            for fred_id, name in self.client.target_series.items():
                # 1. Ensure the series exists in the DB
                series = db.query(EconomicSeries).filter(EconomicSeries.fred_id == fred_id).first()
                if not series:
                    logger.info(f"Adding new series to DB: {name} ({fred_id})")
                    series = EconomicSeries(
                        fred_id=fred_id,
                        name=name,
                        frequency="Monthly", # Simplification for MVP
                    )
                    db.add(series)
                    db.commit()
                    db.refresh(series)
                    
                # 2. Fetch the latest observations
                logger.info(f"Fetching observations for {fred_id}...")
                observations = self.client.fetch_series_observations(fred_id, limit=120) # Last 10 years
                
                # 3. Save observations to DB
                new_records = 0
                for obs in observations:
                    obs_date = datetime.strptime(obs['date'], "%Y-%m-%d").date()
                    release_date = datetime.strptime(obs['release_date'], "%Y-%m-%d").date()
                    
                    # Check if this exact observation already exists
                    existing = db.query(EconomicObservation).filter(
                        EconomicObservation.series_id == series.id,
                        EconomicObservation.observation_date == obs_date
                    ).first()
                    
                    if not existing:
                        new_obs = EconomicObservation(
                            series_id=series.id,
                            observation_date=obs_date,
                            value=obs['value'],
                            release_date=release_date
                        )
                        db.add(new_obs)
                        new_records += 1
                        
                db.commit()
                logger.info(f"Saved {new_records} new observations for {fred_id}.")
                
            logger.info("FRED Ingestion Complete!")
            
        except Exception as e:
            logger.error(f"Error during FRED ingestion: {e}")
            db.rollback()
        finally:
            db.close()

if __name__ == "__main__":
    ingester = FredIngester()
    ingester.populate_database()
