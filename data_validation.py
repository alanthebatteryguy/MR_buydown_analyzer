import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Add at the top with other imports
import pytz

# Update validation constants
MIN_VALID_VOLUME = 100
IGNORE_ZERO_VOLUME = True
MAX_TIME_GAP_MINUTES = 90

def is_market_hours(dt):
    """Check if datetime is within US market hours (9:30 AM - 4:00 PM ET)"""
    if not dt.tzinfo:
        dt = pytz.utc.localize(dt)
    et_time = dt.astimezone(pytz.timezone('US/Eastern'))
    if et_time.weekday() >= 5:  # Weekend
        return False
    return (et_time.hour > 9 or (et_time.hour == 9 and et_time.minute >= 30)) and et_time.hour < 16

def validate_volume(data_df, min_volume=MIN_VALID_VOLUME, ignore_zero=IGNORE_ZERO_VOLUME):
    """Check if volume meets minimum threshold"""
    if ignore_zero:
        valid_data = data_df[data_df['volume'] > 0]
    else:
        valid_data = data_df
        
    if valid_data['volume'].min() < min_volume:
        logger.warning(f"Volume below threshold: {valid_data['volume'].min()} < {min_volume}")
        return False
    return True

def validate_time_continuity(data_df, max_gap_minutes=MAX_TIME_GAP_MINUTES):
    """Check for gaps in timestamp data during market hours"""
    if len(data_df) <= 1:
        return True
        
    sorted_df = data_df.sort_values('timestamp')
    time_diffs = sorted_df['timestamp'].diff().dropna()
    
    # Find largest gap during market hours
    max_diff = 0
    for idx, diff in time_diffs.items():
        prev_time = sorted_df.loc[idx - 1, 'timestamp']
        curr_time = sorted_df.loc[idx, 'timestamp']
        
        if is_market_hours(prev_time) and is_market_hours(curr_time):
            diff_minutes = diff.total_seconds() / 60
            if diff_minutes > max_diff:
                max_diff = diff_minutes
    
    if max_diff > max_gap_minutes:
        logger.warning(f"Market hour time gap exceeds threshold: {max_diff} minutes > {max_gap_minutes} minutes")
        return False
    return True

# Remove the duplicate validate_time_continuity function
def validate_price_variance(data_df, max_swing_pct=2.0):
    """Check if price swings exceed threshold"""
    high_low_pct = ((data_df['high'] - data_df['low']) / data_df['low']) * 100
    if high_low_pct.max() > max_swing_pct:
        logger.warning(f"Price swing exceeds threshold: {high_low_pct.max()}% > {max_swing_pct}%")
        return False
    return True

# Remove this duplicate function - KEEP THE MARKET-HOUR AWARE VERSION ABOVE
# def validate_time_continuity(data_df, max_gap_minutes=20):
    """Check for gaps in timestamp data"""
    if len(data_df) <= 1:
        return True
        
    sorted_df = data_df.sort_values('timestamp')
    time_diffs = sorted_df['timestamp'].diff().dropna()
    max_diff = time_diffs.max().total_seconds() / 60
    
    if max_diff > max_gap_minutes:
        logger.warning(f"Time gap exceeds threshold: {max_diff} minutes > {max_gap_minutes} minutes")
        return False
    return True

def validate_mort_correlation(mbb_data, lookback_days=30, min_correlation=0.7):
    """
    Compare MBB price movements with Treasury yields as fallback
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)
    
    try:
        # First try ^TNX (10-Year Treasury Yield)
        treasury_data = yf.download('^TNX', 
                                  start=start_date.strftime('%Y-%m-%d'),
                                  end=end_date.strftime('%Y-%m-%d'),
                                  interval='1d')
        
        # Fallback to ^TYX (30-Year) if needed
        if len(treasury_data) < 5:
            treasury_data = yf.download('^TYX', 
                                      start=start_date.strftime('%Y-%m-%d'),
                                      end=end_date.strftime('%Y-%m-%d'),
                                      interval='1d')

        # Get ^MORT data
        mort_data = yf.download(
            "^MORT", 
            start=start_date.strftime('%Y-%m-%d'),
            end=end_date.strftime('%Y-%m-%d'),
            interval='1d'
        )
        
        # Get MBB data if not provided
        if mbb_data is None or len(mbb_data) == 0:
            mbb_data = yf.download(
                "MBB", 
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                interval='1d'
            )
        
        # Ensure we have enough data points
        if len(mort_data) < 5 or len(mbb_data) < 5:
            logger.warning(f"Insufficient data points for correlation: MORT={len(mort_data)}, MBB={len(mbb_data)}")
            return False
            
        # Calculate daily returns
        mort_returns = mort_data['Close'].pct_change().dropna()
        mbb_returns = mbb_data['Close'].pct_change().dropna()
        
        # Align dates and calculate correlation
        common_dates = sorted(set(mort_returns.index) & set(mbb_returns.index))
        if len(common_dates) < 5:
            logger.warning(f"Insufficient common dates for correlation: {len(common_dates)}")
            return False
            
        mort_aligned = mort_returns.loc[common_dates]
        mbb_aligned = mbb_returns.loc[common_dates]
        
        correlation = mort_aligned.corr(mbb_aligned)
        
        if correlation < min_correlation:
            logger.warning(f"MBB-MORT correlation below threshold: {correlation:.2f} < {min_correlation}")
            return False
            
        logger.info(f"MBB-MORT correlation: {correlation:.2f}")
        return True
        
    except Exception as e:
        logger.error(f"Error validating MORT correlation: {str(e)}")
        return False

def run_all_validations(data_df):
    """Run all validation checks on the provided data"""
    results = {
        "volume_check": validate_volume(data_df),
        "price_variance_check": validate_price_variance(data_df),
        "time_continuity_check": validate_time_continuity(data_df),
        "mort_correlation_check": validate_mort_correlation(data_df)
    }
    
    return all(results.values()), results