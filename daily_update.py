import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from typing import Optional
import requests

from data_ingestion import (
    initialize_schema,
    get_nyfed_mbs_data,
    store_data,
    get_mbs_prices_for_date,
    send_alert,
    ai_validate_anomalies
)
from calculations import calculate_roi
import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('daily_update.log', maxBytes=1e6, backupCount=3),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def validate_dataframe(df) -> bool:
    """Validate DataFrame structure and content"""
    required_columns = {'date', 'coupon_rate', 'price'}
    if not required_columns.issubset(df.columns):
        logger.error(f"Missing required columns: {required_columns - set(df.columns)}")
        return False
    
    if df['price'].isnull().any():
        logger.error("Null values found in price data")
        return False
    
    if (df['price'] <= 0).any():
        logger.error("Invalid price values <= 0 detected")
        return False
    
    return True

def get_trade_date() -> datetime:
    """Get current trade date"""
    today = pd.Timestamp.today().normalize()
    return today.to_pydatetime()

def process_update(trade_date: Optional[datetime] = None) -> int:
    """Main update workflow with retry logic"""
    try:
        initialize_schema()
        
        # Get validated trade date
        trade_date = trade_date or get_trade_date()
        logger.info(f"Processing update for {trade_date.strftime('%Y-%m-%d')}")

        # Data retrieval with retry
        df = get_nyfed_mbs_data(trade_date)
        if df.empty:
            logger.warning("No data available for processing")
            return 1

        # Data validation
        if not validate_dataframe(df):
            logger.error("Data validation failed")
            return 2

        # Anomaly detection workflow
        anomalies = ai_validate_anomalies(df)
        if not anomalies['suspicious'].empty:
            send_alert(anomalies['suspicious'])
            logger.warning(f"Sent alert for {len(anomalies['suspicious'])} suspicious entries")

        # Store validated data
        store_data(anomalies['valid'])
        logger.info(f"Stored {len(anomalies['valid'])} validated records")

        # ROI calculations
        price_data = get_mbs_prices_for_date(trade_date)
        for original_rate in price_data:
            for increment in [0.1, 0.25, 0.5]:
                buydown_rate = round(original_rate - increment, 2)
                if buydown_rate in price_data:
                    calculate_roi(
                        loan_amount=300000,
                        original_rate=original_rate,
                        buydown_rate=buydown_rate,
                        price_data=price_data,
                        date=trade_date
                    )
        logger.info("Completed ROI calculations")

        return 0

    except requests.RequestException as e:
        logger.error(f"Network error occurred: {str(e)}")
        return 3
    except pd.errors.EmptyDataError:
        logger.error("Received empty data from source")
        return 4
    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        return 5

if __name__ == "__main__":
    try:
        exit_code = process_update()
        logger.info(f"Update completed with exit code: {exit_code}")
    except KeyboardInterrupt:
        logger.warning("Process interrupted by user")
        exit_code = 6
    finally:
        exit(exit_code)