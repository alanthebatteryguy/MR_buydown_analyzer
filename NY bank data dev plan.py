NY bank data dev plan

Your PRD specifies the need for MBS price data for coupon rates between 3% and 7.5% to calculate the ROI of buydown options in 10 bps increments (Section 4). While Fannie Mae, Freddie Mac, and Ginnie Mae provide pool-level data (e.g., weighted average coupon rates), they typically do not include current market prices at the granularity required for your application. The NY Fed, however, publishes daily TBA transaction summaries in CSV format, including weighted average prices for specific coupon rates (e.g., 3.0%, 3.5%, etc.), which are directly applicable for calculating buydown costs and ROI. This data is free, reliable, and easier to automate compared to scraping or accessing GSE (Government-Sponsored Enterprise) datasets, which may require complex parsing or lack price information.
Action Plan Overview
Instead of visiting GSE websites and downloading pool datasets manually, we’ll:
Fetch Daily TBA Price Data from NY Fed: Automate retrieval of CSV files containing MBS prices.

Process and Store Data: Parse the data, store it in your mbs_prices table, and interpolate prices for 10 bps increments.

Compute ROI: Calculate ROI for buydown scenarios and update the daily_roi table.

Automate the Process: Set up a script to run daily via a cron job.

Integrate with Existing Codebase: Modify specific files to incorporate this data source.

Below, I list the exact changes to your codebase, including step-by-step instructions and code snippets.
Detailed Changes to the Codebase
1. Update data_ingestion.py
This file handles data retrieval and storage. We’ll add functions to fetch NY Fed data, interpolate prices, and manage the ingestion process.
Step 1.1: Add Required Imports
Location: Top of data_ingestion.py

Change: Add requests and numpy imports for HTTP requests and interpolation.

Code:
python

import requests
import numpy as np

Step 1.2: Define get_nyfed_mbs_data()
Purpose: Fetch daily TBA transaction data from the NY Fed.

Location: After initialize_schema() (around line 55).

Code:
python

def get_nyfed_mbs_data(trade_date=None):
    """Fetch daily MBS TBA price data from NY Fed per PRD 3.1.1"""
    from datetime import date, timedelta
    if trade_date is None:
        trade_date = date.today() - timedelta(days=1)  # Assume data is available next day
    url = f"https://markets.newyorkfed.org/api/mbs/transactions/{trade_date.strftime('%Y-%m-%d')}.csv"
    try:
        response = requests.get(url)
        response.raise_for_status()
        df = pd.read_csv(response.content)
        # Filter for purchase trades and aggregate prices
        df = df[df['Trade Type'] == 'Purchase']
        df = df.groupby('Coupon')['Weighted Average Price'].mean().reset_index()
        df['date'] = trade_date
        df.rename(columns={'Coupon': 'coupon_rate', 'Weighted Average Price': 'price'}, inplace=True)
        return detect_anomalies(df[['date', 'coupon_rate', 'price']])
    except requests.RequestException as e:
        print(f"Error fetching NY Fed data: {e}")
        return pd.DataFrame()

Notes:
Uses detect_anomalies() (already in your code) to validate data.

Assumes data is for the previous day; adjust if real-time data is preferred.

Step 1.3: Add interpolate_mbs_prices()
Purpose: Interpolate prices for coupon rates from 3.0% to 7.5% in 0.1% increments, per PRD Section 4.

Location: After get_nyfed_mbs_data().

Code:
python

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

Step 1.4: Add get_mbs_prices_for_date()
Purpose: Retrieve and interpolate prices for a specific date, used by ROI calculations and API.

Location: After interpolate_mbs_prices().

Code:
python

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

Step 1.5: Initialize mbs_prices Table in initialize_schema()
Purpose: Ensure the mbs_prices table exists (it’s referenced but not created in the current schema).

Location: Inside initialize_schema() (around line 45).

Change: Add table definition if not present.

Code:
python

def initialize_schema():
    """PRD 3.1.2 - Create tables per spec"""
    engine = create_engine(SQLITE_PATH)
    inspector = inspect(engine)
    metadata = MetaData()
    
    if 'daily_roi' not in inspector.get_table_names():
        Table('daily_roi', metadata,
            Column('date', Date, primary_key=True),
            Column('coupon_rate', Float, primary_key=True),
            Column('price', Float),
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

Step 1.6: Enhance store_data() for Robustness
Purpose: Ensure NY Fed data is stored correctly and handle duplicates.

Location: Replace existing store_data() (lines 82-95).

Code:
python

def store_data(df):
    """Store in SQLite with schema validation"""
    engine = create_engine(SQLITE_PATH)
    
    if 'series' in df.columns:
        fred_df = df[df['series'].notnull()]
        fred_df.to_sql('fred_data', engine, if_exists='append', index=False)
    
    if 'coupon_rate' in df.columns and 'price' in df.columns:
        price_df = df[['date', 'coupon_rate', 'price']]
        # Remove duplicates based on primary key (date, coupon_rate)
        with engine.connect() as conn:
            conn.execute(
                text("DELETE FROM mbs_prices WHERE date = :date AND coupon_rate IN :rates"),
                {'date': price_df['date'].iloc[0], 'rates': tuple(price_df['coupon_rate'])}
            )
        price_df.to_sql('mbs_prices', engine, if_exists='append', index=False)

2. Update calculations.py
Modify the ROI calculation to support buydown analysis and update the daily_roi table schema.
Step 2.1: Update daily_roi Table Schema
Purpose: Reflect buydown analysis with original_rate and buydown_rate.

Location: Handled in initialize_schema() above, but ensure consistency in calculate_roi().

Action: Update daily_roi schema to:
python

Table('daily_roi', metadata,
    Column('date', Date, primary_key=True),
    Column('original_rate', Float, primary_key=True),
    Column('buydown_rate', Float, primary_key=True),
    Column('roi', Float),
    Column('breakeven_months', Float)
)

Step 2.2: Modify calculate_roi()
Purpose: Adjust to use original_rate and buydown_rate, remove price column.

Location: Replace existing calculate_roi() (lines 25-53).

Code:
python

def calculate_roi(loan_amount: float, original_rate: float, buydown_rate: float, 
                  price_data: dict, date: str) -> dict:
    """PRD 3.2.3 - Unified implementation for buydown ROI"""
    price1 = price_data.get(original_rate)
    price2 = price_data.get(buydown_rate)
    if price1 is None or price2 is None:
        return {'roi_percent': 0, 'breakeven_months': 0}
    
    # Core calculations
    monthly_pmt1 = calculate_monthly_payment(original_rate, loan_amount)
    monthly_pmt2 = calculate_monthly_payment(buydown_rate, loan_amount)
    monthly_savings = monthly_pmt1 - monthly_pmt2
    
    cost = (price1 - price2) * loan_amount
    roi = (monthly_savings * 12 / cost) * 100 if cost > 0 else 0
    breakeven = (cost / monthly_savings) if monthly_savings > 0 else 0
    
    # Database storage
    engine = create_engine('sqlite:///mbs_data.db')
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO daily_roi (date, original_rate, buydown_rate, roi, breakeven_months)
                VALUES (:date, :original_rate, :buydown_rate, :roi, :breakeven)
            """),
            [{"date": date, "original_rate": original_rate, "buydown_rate": buydown_rate, 
              "roi": roi, "breakeven": breakeven}]
        )
    
    return {'roi_percent': roi, 'breakeven_months': breakeven}

3. Update app.py
Enhance the API to use real-time NY Fed data instead of placeholders.
Step 3.1: Add Helper Function get_latest_date()
Purpose: Retrieve the most recent date in mbs_prices.

Location: Before route definitions (around line 6).

Code:
python

def get_latest_date():
    engine = create_engine('sqlite:///mbs_data.db')
    with engine.connect() as conn:
        result = conn.execute(text("SELECT MAX(date) FROM mbs_prices"))
        return result.fetchone()[0]

Step 3.2: Update /api/roi Route
Purpose: Use actual MBS prices for specified rates.

Location: Replace existing /api/roi route (lines 19-30).

Code:
python

@app.route('/api/roi/<float:loan_amount>/<float:original_rate>/<float:buydown_rate>')
def get_roi(loan_amount, original_rate, buydown_rate):
    latest_date = get_latest_date()
    if not latest_date:
        return jsonify({"error": "No MBS data available"}), 404
    price_data = get_mbs_prices_for_date(latest_date)
    if original_rate not in price_data or buydown_rate not in price_data:
        return jsonify({"error": "Requested rates not available"}), 400
    result = calculate_roi(
        loan_amount=loan_amount,
        original_rate=original_rate,
        buydown_rate=buydown_rate,
        price_data=price_data,
        date=latest_date
    )
    return jsonify(result)

Notes: Updates the route to accept both original_rate and buydown_rate, aligning with the PRD.

4. Update visualization.py
Adjust visualizations to reflect the new daily_roi schema.
Step 4.1: Update plot_roi_trends()
Purpose: Reflect the updated daily_roi table with original_rate and buydown_rate.

Location: Replace existing plot_roi_trends() (lines 18-28).

Code:
python

def plot_roi_trends(original_rate=None, buydown_rate=None):
    engine = create_engine('sqlite:///mbs_data.db')
    query = "SELECT date, AVG(roi) as avg_roi FROM daily_roi"
    params = {}
    if original_rate and buydown_rate:
        query += " WHERE original_rate = :original_rate AND buydown_rate = :buydown_rate"
        params = {'original_rate': original_rate, 'buydown_rate': buydown_rate}
    query += " GROUP BY date"
    df = pd.read_sql(query, engine, params=params)
    
    plt.figure(figsize=(12, 6))
    sns.lineplot(data=df, x='date', y='avg_roi')
    plt.title('Average ROI Trends Over Time')
    return save_plot(plt)

5. Update nlu_queries.py
Ensure NLU reflects the updated schema.
Step 5.1: Update Schema in handle_nlu_query()
Location: Inside prompt string (line 11).

Change: Update daily_roi schema description.

Code:
python

prompt = f"""Convert this mortgage analytics query to SQL:
{query}

Database schema:
- fred_data (date, value, series)
- mbs_prices (date, coupon_rate, price)
- daily_roi (date, original_rate, buydown_rate, roi, breakeven_months)

Return ONLY the SQL query without explanations.
"""

6. Create Automation Script
Purpose: Automate daily data ingestion and ROI computation.

File: New file daily_update.py

Code:
python

from data_ingestion import get_nyfed_mbs_data, store_data, get_mbs_prices_for_date, calculate_roi

if __name__ == '__main__':
    df = get_nyfed_mbs_data()
    if not df.empty:
        store_data(df)
        date = df['date'].iloc[0]
        price_data = get_mbs_prices_for_date(date)
        for original_rate in price_data.keys():
            for increment in [0.1, 0.2, 0.3, 0.4, 0.5]:
                buydown_rate = original_rate - increment
                if buydown_rate in price_data:
                    calculate_roi(
                        loan_amount=300000,  # Configurable via .env if needed
                        original_rate=original_rate,
                        buydown_rate=buydown_rate,
                        price_data=price_data,
                        date=date
                    )

Cron Job: Add to crontab to run daily (e.g., at 1 AM):

0 1 * * * /usr/bin/python3 /path/to/daily_update.py

7. Update requirements.txt
Purpose: Ensure requests is included (already present as requests==2.32.3).

Verification Steps
Test Data Ingestion: Run get_nyfed_mbs_data() manually and verify data in mbs_prices.

Test Interpolation: Call get_mbs_prices_for_date() with a known date and check rates from 3.0% to 7.5%.

Test ROI: Run daily_update.py and verify daily_roi entries.

Test API: Access /api/roi/300000/5.0/4.9 and confirm valid JSON response.

Test Visualizations: Call plot_roi_trends(5.0, 4.9) and check the generated plot.

