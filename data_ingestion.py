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

# Define SQLite path constant
SQLITE_PATH = 'sqlite:///mbs_data.db'

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
    
    # Use inspect properly to check if table exists
    inspector = inspect(engine)
    if 'daily_roi' not in inspector.get_table_names():
        metadata = MetaData()
        Table('daily_roi', metadata,
            Column('date', Date, primary_key=True),
            Column('coupon_rate', Float, primary_key=True),
            Column('price', Float),
            Column('roi', Float),
            Column('breakeven_months', Float)
        )
        metadata.create_all(engine)

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
    
    # Separate FRED data from future scraped MBS prices
    if 'series' in df.columns:
        fred_df = df[df['series'].notnull()]
        fred_df.to_sql('fred_data', engine, if_exists='append', index=False)
    
    # Existing MBS price handling remains for scraping data
    if 'coupon_rate' in df.columns and 'price' in df.columns:
        price_df = df[['date', 'coupon_rate', 'price']]
        price_df.to_sql('mbs_prices', engine, if_exists='append', index=False)

def ai_validate_anomalies(anomalies):
    """Use Gemini to validate potential anomalies using the building_plan_analyzer pattern"""
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel(os.getenv('GEMINI_MODEL_NAME'))

    prompt = f"""Analyze these MBS price anomalies and classify them as valid or suspicious:
    {anomalies.to_markdown(index=False)}
    
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
            [prompt, anomalies.to_markdown()],
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
        return {'valid': anomalies, 'suspicious': pd.DataFrame()}

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
