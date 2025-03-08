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

# Load environment variables
load_dotenv()

def initialize_schema():
    """Create database tables for the application"""
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
    
    metadata.create_all(engine)

def get_fred_mbs_data():
    """Get mortgage rate data from FRED"""
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
                'coupon_rate': None  # Placeholder for future MBS data
            })
            df = pd.concat([df, temp_df], ignore_index=True)
        except Exception as e:
            print(f"FRED Error: {str(e)}")
    
    return df

def store_data(df):
    """Store data in SQLite"""
    engine = create_engine(SQLITE_PATH)
    
    if 'series' in df.columns:
        fred_df = df[df['series'].notnull()]
        fred_df.to_sql('fred_data', engine, if_exists='append', index=False)

def send_alert(message_data):
    """Send email alert for data issues"""
    msg = MIMEMultipart()
    msg['From'] = os.getenv('ALERT_EMAIL')
    msg['To'] = os.getenv('ADMIN_EMAIL')
    msg['Subject'] = f"MBS Data Alert"
    
    body = f"""
    <h2>Data Alert</h2>
    {message_data.to_html(index=False) if hasattr(message_data, 'to_html') else message_data}
    <p>Review immediately in dashboard or database.</p>
    """
    msg.attach(MIMEText(body, 'html'))
    
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(os.getenv('ALERT_EMAIL'), os.getenv('EMAIL_PASSWORD'))
            server.send_message(msg)
    except Exception as e:
        print(f"Email alert error: {str(e)}")
