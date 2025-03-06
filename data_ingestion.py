import os
import pandas as pd
from sqlalchemy import create_engine, MetaData, Table, Column, Float, Date, String, inspect, text
from fredapi import Fred
from dotenv import load_dotenv
from io import StringIO
import google.generativeai as genai
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from calculations import calculate_roi

import requests
import numpy as np

# Define SQLite path constant
SQLITE_PATH = 'sqlite:///mbs_data.db'

def _nyfed_data_exists(trade_date):
    """Check if NY Fed MBS data exists for the specified trade_date."""
    url = f"https://markets.newyorkfed.org/api/mbs/transactions/{trade_date.strftime('%Y-%m-%d')}.csv"
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'}
    try:
        print(f"Checking data availability for {trade_date.strftime('%Y-%m-%d')}")
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        if len(response.content) < 100:
            print(f"Data for {trade_date.strftime('%Y-%m-%d')} exists but appears incomplete")
            return False
        print(f"Data for {trade_date.strftime('%Y-%m-%d')} exists and appears valid")
        return True
    except requests.RequestException as e:
        print(f"Error checking data for {trade_date.strftime('%Y-%m-%d')}: {str(e)}")
        return False

# Load environment variables
load_dotenv()

def detect_anomalies(df):
    """PRD 3.1.3 - Basic price change validation"""
    if len(df) == 0:
        return df
    
    engine = create_engine(SQLITE_PATH)
    prev_prices = pd.read_sql(
        "SELECT coupon_rate, price FROM mbs_prices WHERE date = (SELECT MAX(date) FROM mbs_prices WHERE date < ?)",
        engine, params=[df['date'].iloc[0]]
    )
    
    if not prev_prices.empty:
        merged = df.merge(prev_prices, on='coupon_rate', suffixes=('', '_prev'))
        merged['change'] = abs((merged['price'] - merged['price_prev']) / merged['price_prev'])
        anomalies = merged[merged['change'] > 0.05]
        if not anomalies.empty:
            print(f"⚠️ Price anomalies detected: {anomalies[['coupon_rate', 'price']]}")
    
    return df

def initialize_schema():
    """PRD 3.1.2 - Create tables per spec"""
    engine = create_engine(SQLITE_PATH)
    inspector = inspect(engine)
    metadata = MetaData()
    
    if 'daily_roi' not in inspector.get_table_names():
        Table('daily_roi', metadata,
            Column('date', Date, primary_key=True),
            Column('original_rate', Float, primary_key=True),
            Column('buydown_rate', Float, primary_key=True),
            Column('roi', Float),
            Column('breakeven_months', Float)
        )
    
    if 'mbs_prices' not in inspector.get_table_names():
        Table('mbs_prices', metadata,
            Column('date', Date, primary_key=True),
            Column('coupon_rate', Float, primary_key=True),
            Column('price', Float)
        )
    
    metadata.create_all(engine)

def get_nyfed_mbs_data(trade_date=None):
    """Fetch daily MBS TBA price data from NY Fed per PRD 3.1.1"""
    from pandas.tseries.holiday import USFederalHolidayCalendar
    import datetime
    
    # Ensure holiday calendar covers dates through 2026
    fed_holidays = USFederalHolidayCalendar().holidays(start='2024-01-01', end='2026-12-31').date.tolist()
    biz_day = pd.offsets.CustomBusinessDay(holidays=fed_holidays)
    
    if trade_date is None:
        # Use today's date directly instead of calculating from base_date
        today = pd.Timestamp.today()
        # Log the actual date being used
        print(f"Current date: {today}")
        base_date = today - pd.DateOffset(days=1)
        trade_date = (base_date - 3 * biz_day).date()
        print(f"Calculated trade date: {trade_date}")
    
    # Convert trade_date to date object if it's a datetime
    if isinstance(trade_date, datetime.datetime):
        trade_date_obj = trade_date.date()
    else:
        trade_date_obj = trade_date
        
    # Always attempt to fetch real data from NY Fed API
    print(f"Fetching real data for date: {trade_date_obj}")
        
    # Normal processing for real dates
    attempts = 0
    while attempts < 20:  # Increased from 5 to 20 business days
        if not _nyfed_data_exists(trade_date):
            try:
                url = f"https://markets.newyorkfed.org/api/mbs/transactions/{trade_date.strftime('%Y-%m-%d')}.csv"
                print(f"Attempting to fetch data from URL: {url}")
                response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                response.raise_for_status()
                df = pd.read_csv(StringIO(response.text))
                df = df[df['Trade Type'] == 'Purchase']
                df = df.groupby('Coupon')['Weighted Average Price'].mean().reset_index()
                df['date'] = trade_date
                df.rename(columns={'Coupon': 'coupon_rate', 'Weighted Average Price': 'price'}, inplace=True)
                return detect_anomalies(df[['date', 'coupon_rate', 'price']])
            except requests.RequestException as e:
                print(f"Failed to fetch data for {trade_date}: {e}")
        
        trade_date -= biz_day
        attempts += 1
    
    raise Exception(f"No MBS data found after {attempts} business days")

def get_fred_mbs_data():
    """PRD 3.1.1 - FRED data integration for mortgage rates"""
    fred = Fred(api_key=os.getenv('FRED_API_KEY'))
    
    series_map = {
        'MORTGAGE30US': '30yr_fixed_rate',
        # Add treasury yields if needed later
        # 'GS10': '10yr_treasury_yield'
    }

    df = pd.DataFrame()
    for series_id, col_name in series_map.items():
        try:
            data = fred.get_series(series_id)
            temp_df = pd.DataFrame({
                'date': data.index,
                'value': data.values,
                'series': col_name,
                'coupon_rate': None  # Placeholder for scraped MBS data
            })
            df = pd.concat([df, temp_df], ignore_index=True)
        except Exception as e:
            print(f"FRED Error: {str(e)}")
    
    return df

def store_data(df):
    """Store in SQLite with schema validation"""
    engine = create_engine(SQLITE_PATH)
    
    if 'series' in df.columns:
        fred_df = df[df['series'].notnull()]
        fred_df.to_sql('fred_data', engine, if_exists='append', index=False)
    
    if 'coupon_rate' in df.columns and 'price' in df.columns:
        price_df = df[['date', 'coupon_rate', 'price']]
        # Simpler approach: delete by date only, then insert new records
        with engine.connect() as conn:
            conn.execute(
                text("DELETE FROM mbs_prices WHERE date = :date"),
                {'date': price_df['date'].iloc[0]}
            )
        price_df.to_sql('mbs_prices', engine, if_exists='append', index=False)

def interpolate_mbs_prices(df, min_rate=3.0, max_rate=7.5, step=0.1):
    """Interpolate MBS prices for desired coupon rates per PRD 4"""
    available_rates = sorted(df['coupon_rate'].unique())
    desired_rates = np.arange(min_rate, max_rate + step, step)
    interpolated = {}
    for rate in desired_rates:
        if rate in available_rates:
            interpolated[rate] = df[df['coupon_rate'] == rate]['price'].mean()
        else:
            lower = max([r for r in available_rates if r < rate], default=None)
            upper = min([r for r in available_rates if r > rate], default=None)
            if lower and upper:
                lower_price = df[df['coupon_rate'] == lower]['price'].mean()
                upper_price = df[df['coupon_rate'] == upper]['price'].mean()
                weight = (rate - lower) / (upper - lower)
                interpolated[rate] = lower_price * (1 - weight) + upper_price * weight
            elif lower:
                interpolated[rate] = df[df['coupon_rate'] == lower]['price'].mean()
            elif upper:
                interpolated[rate] = df[df['coupon_rate'] == upper]['price'].mean()
    return interpolated

def get_mbs_prices_for_date(date, min_rate=3.0, max_rate=7.5, step=0.1):
    """Fetch and interpolate MBS prices for a given date"""
    engine = create_engine(SQLITE_PATH)
    df = pd.read_sql(
        "SELECT coupon_rate, price FROM mbs_prices WHERE date = :date",
        engine,
        params={'date': date}
    )
    if df.empty:
        return {}
    return interpolate_mbs_prices(df, min_rate, max_rate, step)

def ai_validate_anomalies(df):
    """Use Gemini to validate potential anomalies using the building_plan_analyzer pattern"""
    # Check if we're using mock data (for future dates)
    if df['date'].iloc[0].year >= 2025:
        print(f"Using mock validation for future date: {df['date'].iloc[0]}")
        # For mock data, just return all as valid
        return {
            'valid': df,
            'suspicious': pd.DataFrame(columns=df.columns)
        }
        
    # Only use Gemini API for real historical data
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel(os.getenv('GEMINI_MODEL_NAME'))

    prompt = f"""Analyze these MBS price anomalies and classify them as valid or suspicious:
    {df.to_markdown(index=False)}
    
    Consider these factors:
    1. Historical price patterns for each coupon rate
    2. Federal Reserve rate changes in the last 7 days
    3. Correlation between adjacent coupon rates
    4. Typical daily trading ranges from Mortgage News Daily
    
    Format response as:
    | coupon_rate | date       | price | classification |
    |-------------|------------|-------|-----------------|    
    """

    try:
        response = model.generate_content(
            [prompt, df.to_markdown()],
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                top_p=0.95,
                top_k=50
            )
        )
        
        # Parse the response
        classified = pd.read_csv(StringIO(response.text), sep='|', skipinitialspace=True)
        valid = classified[classified['classification'] == 'valid']
        suspicious = classified[classified['classification'] == 'suspicious']
        
        return {
            'valid': valid[['coupon_rate', 'date', 'price']],
            'suspicious': suspicious[['coupon_rate', 'date', 'price']]
        }
        
    except Exception as e:
        print(f"Gemini API error: {str(e)}")
        return {'valid': df, 'suspicious': pd.DataFrame()}

def send_alert(suspicious_anomalies):
    """PRD 5.1 - Send email alert for suspicious anomalies"""
    msg = MIMEMultipart()
    msg['From'] = os.getenv('ALERT_EMAIL')
    msg['To'] = os.getenv('ADMIN_EMAIL')
    msg['Subject'] = f"MBS Price Alert: {len(suspicious_anomalies)} Suspicious Entries"
    
    body = f"""
    <h2>Potential Pricing Anomalies Detected</h2>
    {suspicious_anomalies.to_html(index=False)}
    <p>Review immediately in dashboard or database.</p>
    """
    msg.attach(MIMEText(body, 'html'))
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(os.getenv('ALERT_EMAIL'), os.getenv('EMAIL_PASSWORD'))
        server.send_message(msg)
