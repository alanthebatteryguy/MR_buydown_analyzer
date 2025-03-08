import yfinance as yf
from sqlalchemy import create_engine, Column, Integer, Float, DateTime, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import logging
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define database
Base = declarative_base()

class MBBCoupon(Base):
    __tablename__ = 'mbb_coupons'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    
    def __repr__(self):
        return f"<MBBCoupon(timestamp='{self.timestamp}', close='{self.close}')>"

def initialize_db():
    """Initialize the database and return engine"""
    db_path = os.path.join(os.path.dirname(__file__), 'mbb_data.db')
    engine = create_engine(f'sqlite:///{db_path}')
    Base.metadata.create_all(engine)
    return engine

def fetch_historical_mbb_data(ticker="MBB", period="3mo"):
    """
    Fetch historical MBB data from yfinance
    
    Args:
        ticker: The ticker symbol (default: MBB for iShares MBS ETF)
        period: Time period to fetch (default: 3mo for 3 months)
               Options: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    
    Returns:
        DataFrame with historical data
    """
    try:
        logger.info(f"Fetching historical data for {ticker} over {period}")
        mbb = yf.Ticker(ticker)
        hist = mbb.history(period=period)
        
        if hist.empty:
            logger.warning(f"No data returned for {ticker}")
            return None
            
        logger.info(f"Successfully fetched {len(hist)} records")
        return hist
    except Exception as e:
        logger.error(f"Error fetching historical data: {str(e)}")
        return None

def populate_historical_data():
    """Populate database with historical MBB data"""
    engine = initialize_db()
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Check if we already have data
    existing_count = session.query(MBBCoupon).count()
    if existing_count > 0:
        logger.info(f"Database already contains {existing_count} records. Skipping historical data population.")
        session.close()
        return
    
    # Fetch historical data (3 months)
    hist_data = fetch_historical_mbb_data(period="3mo")
    
    if hist_data is None or hist_data.empty:
        logger.error("Failed to fetch historical data")
        session.close()
        return
    
    # Add historical data to database
    records_added = 0
    for index, row in hist_data.iterrows():
        # Convert pandas timestamp to datetime
        timestamp = index.to_pydatetime()
        
        # Create new record
        new_record = MBBCoupon(
            timestamp=timestamp,
            open=float(row['Open']),
            high=float(row['High']),
            low=float(row['Low']),
            close=float(row['Close']),
            volume=int(row['Volume'])
        )
        
        session.add(new_record)
        records_added += 1
    
    # Commit changes
    session.commit()
    logger.info(f"Added {records_added} historical records to database")
    session.close()

def update_daily_data():
    """Update database with latest MBB data"""
    engine = initialize_db()
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Get latest data in database
    latest = session.query(MBBCoupon).order_by(MBBCoupon.timestamp.desc()).first()
    
    # If no data exists, populate with historical data
    if latest is None:
        session.close()
        populate_historical_data()
        return
    
    # Calculate date range to fetch (from latest record to today)
    latest_date = latest.timestamp.date()
    today = datetime.now().date()
    
    # If already up to date, skip
    if latest_date >= today:
        logger.info("Data already up to date")
        session.close()
        return
    
    # Fetch data for missing period
    days_diff = (today - latest_date).days
    period = f"{days_diff + 5}d"  # Add a few extra days to ensure overlap
    
    hist_data = fetch_historical_mbb_data(period=period)
    
    if hist_data is None or hist_data.empty:
        logger.error("Failed to fetch recent data")
        session.close()
        return
    
    # Add new data to database
    records_added = 0
    for index, row in hist_data.iterrows():
        # Convert pandas timestamp to datetime
        timestamp = index.to_pydatetime()
        
        # Skip if record already exists
        if timestamp.date() <= latest_date:
            continue
        
        # Create new record
        new_record = MBBCoupon(
            timestamp=timestamp,
            open=float(row['Open']),
            high=float(row['High']),
            low=float(row['Low']),
            close=float(row['Close']),
            volume=int(row['Volume'])
        )
        
        session.add(new_record)
        records_added += 1
    
    # Commit changes
    session.commit()
    logger.info(f"Added {records_added} new records to database")
    session.close()

if __name__ == "__main__":
    # When run directly, update the database
    update_daily_data()