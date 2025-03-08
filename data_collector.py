import yfinance as yf
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
import logging
import pandas as pd
from sqlalchemy import text  # Add for raw SQL
import pytz  # Add missing import

# Simplified logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

Base = declarative_base()

class MBBCoupon(Base):
    __tablename__ = 'mbs_coupons'
    timestamp = Column(DateTime, primary_key=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

def initialize_db():
    engine = create_engine('sqlite:///mbs_test.db')
    
    # Add connection test
    try:
        with engine.connect() as conn:
            # Drop existing table if it exists
            conn.execute(text("DROP TABLE IF EXISTS mbs_coupons"))
            conn.execute(text("SELECT 1"))
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        raise
    
    Base.metadata.create_all(engine)
    return engine

def fetch_mbb_data():
    try:
        data = yf.download(
            tickers='MBB',
            period='1d',
            interval='15m',
            prepost=True,
            threads=True
        )
        
        # Convert to Eastern Time before date check
        data.index = data.index.tz_convert('America/New_York')
        max_timestamp = data.index.max()
        
        # Get current time in Eastern Time
        eastern_now = datetime.now(pytz.timezone('America/New_York'))
        
        if max_timestamp > eastern_now:
            logger.error(f"Future timestamp detected: {max_timestamp} vs {eastern_now}")
            return None
            
        # Return all OHLCV data
        return data.reset_index()
    except Exception as e:
        logger.error(f"Data fetch failed: {str(e)}")
        return None

def process_data(raw_df):
    # Ensure we have all required columns
    if 'Datetime' not in raw_df.columns:
        raw_df = raw_df.reset_index()
    
    # Select OHLCV data
    processed = raw_df[['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume']]
    
    # Standardize column names to lowercase
    processed.rename(columns={
        'Datetime': 'timestamp',
        'Open': 'open',
        'High': 'high',
        'Low': 'low',
        'Close': 'close',
        'Volume': 'volume'
    }, inplace=True)
    
    return processed.to_dict('records')

def update_database(engine):
    raw_data = fetch_mbb_data()
    if raw_data is not None:
        # Process the data to get all OHLCV fields
        processed_data = pd.DataFrame(process_data(raw_data))
        
        # Add market hours validation
        market_open = pd.Timestamp.now(tz='America/New_York').replace(hour=9, minute=30)
        market_close = market_open.replace(hour=16)
        
        valid_hours = processed_data['timestamp'].dt.time.between(
            market_open.time(), 
            market_close.time()
        )
        
        if not valid_hours.all():
            logger.error(f"Non-market hours detected: {processed_data[~valid_hours]}")
            return
        
        # Convert to Eastern Time explicitly
        processed_data['timestamp'] = pd.to_datetime(processed_data['timestamp']).dt.tz_convert('America/New_York')
        
        # Enhanced validation
        price_validation = (
            (processed_data['close'] < 90) | 
            (processed_data['close'] > 110) |
            (processed_data['close'].diff().abs().gt(2))  # No >2$ swings in 15m
        )
        if price_validation.any():
            logger.error(f"Validation failed on rows: {processed_data[price_validation]}")
            return

        # Create temp table for atomic upsert
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TEMPORARY TABLE temp_mbs AS
                SELECT * FROM mbs_coupons WHERE 1=0
            """))
            
            processed_data.to_sql('temp_mbs', conn, if_exists='append', index=False)
            
            # SQLite UPSERT with all OHLCV fields
            conn.execute(text("""
                INSERT INTO mbs_coupons (timestamp, open, high, low, close, volume)
                SELECT timestamp, open, high, low, close, volume FROM temp_mbs
                ON CONFLICT(timestamp) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume
            """))
            conn.commit()
            
        logger.info(f"Upserted {len(processed_data)} records")