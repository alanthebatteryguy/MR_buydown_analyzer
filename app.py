from flask import Flask, render_template, jsonify, request, Response
from sqlalchemy import create_engine, text, desc
from sqlalchemy.orm import sessionmaker
from data_collector import initialize_db, MBBCoupon
from calculations import calculate_roi
import pandas as pd
from datetime import datetime, timedelta
import io
import csv
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize database
engine = initialize_db()
Session = sessionmaker(bind=engine)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/mbb_data')
def get_mbb_data():
    try:
        # Get time range from query parameter
        time_range = request.args.get('range', '1d')
        
        # Calculate start date based on range
        end_date = datetime.now()
        if time_range == '1d':
            start_date = end_date - timedelta(days=1)
        elif time_range == '1w':
            start_date = end_date - timedelta(weeks=1)
        elif time_range == '1m':
            start_date = end_date - timedelta(days=30)
        elif time_range == '3m':
            start_date = end_date - timedelta(days=90)
        elif time_range == '1y':
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date - timedelta(days=1)
        
        # Query database
        session = Session()
        data = session.query(MBBCoupon).filter(
            MBBCoupon.timestamp >= start_date
        ).order_by(MBBCoupon.timestamp).all()
        session.close()
        
        # Format data for charts
        timestamps = [entry.timestamp.isoformat() for entry in data]
        prices = [entry.close for entry in data]
        volumes = [entry.volume for entry in data]
        
        # Calculate implied rates
        rates = [calculate_implied_rate(price) for price in prices]
        
        # Format full data for table
        full_data = [{
            'timestamp': entry.timestamp.isoformat(),
            'open': entry.open,
            'high': entry.high,
            'low': entry.low,
            'close': entry.close,
            'volume': entry.volume
        } for entry in data]
        
        return jsonify({
            'timestamps': timestamps,
            'prices': prices,
            'volumes': volumes,
            'rates': rates,
            'full_data': full_data
        })
    except Exception as e:
        logger.error(f"Error fetching MBB data: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/roi/<float:loan_amount>/<float:original_rate>/<float:buydown_rate>')
def get_roi(loan_amount, original_rate, buydown_rate):
    try:
        # Get loan term from query parameter (default to 30 years)
        loan_term = int(request.args.get('term', 30))
        
        # Convert rates from percentage to decimal
        original_rate_decimal = original_rate / 100
        buydown_rate_decimal = buydown_rate / 100
        
        # Calculate monthly payments
        original_payment = calculate_monthly_payment(loan_amount, original_rate_decimal, loan_term)
        buydown_payment = calculate_monthly_payment(loan_amount, buydown_rate_decimal, loan_term)
        
        # Calculate monthly savings
        monthly_savings = original_payment - buydown_payment
        
        # Calculate buydown cost (1 point = 1% of loan amount)
        rate_diff = original_rate - buydown_rate
        buydown_cost = rate_diff * loan_amount / 100
        
        # Calculate breakeven period in months
        breakeven_months = round(buydown_cost / monthly_savings) if monthly_savings > 0 else float('inf')
        
        return jsonify({
            'original_payment': original_payment,
            'buydown_payment': buydown_payment,
            'monthly_savings': monthly_savings,
            'buydown_cost': buydown_cost,
            'breakeven_months': breakeven_months
        })
    except Exception as e:
        logger.error(f"Error calculating ROI: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/query', methods=['POST'])
def process_query():
    try:
        query = request.json.get('query', '')
        
        # Process natural language query
        # This is a placeholder - will be implemented with NLP in nlu_queries.py
        response = process_natural_language_query(query)
        
        return jsonify({'answer': response})
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/export_data')
def export_data():
    try:
        # Get time range from query parameter
        time_range = request.args.get('range', '1m')  # Default to 1 month
        
        # Calculate start date based on range
        end_date = datetime.now()
        if time_range == '1d':
            start_date = end_date - timedelta(days=1)
        elif time_range == '1w':
            start_date = end_date - timedelta(weeks=1)
        elif time_range == '1m':
            start_date = end_date - timedelta(days=30)
        elif time_range == '3m':
            start_date = end_date - timedelta(days=90)
        elif time_range == '1y':
            start_date = end_date - timedelta(days=365)
        else:
            start_date = end_date - timedelta(days=30)
        
        # Query database
        session = Session()
        data = session.query(MBBCoupon).filter(
            MBBCoupon.timestamp >= start_date
        ).order_by(MBBCoupon.timestamp).all()
        session.close()
        
        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Timestamp', 'Open', 'High', 'Low', 'Close', 'Volume', 'Implied Rate'])
        
        # Write data
        for entry in data:
            implied_rate = calculate_implied_rate(entry.close)
            writer.writerow([
                entry.timestamp,
                entry.open,
                entry.high,
                entry.low,
                entry.close,
                entry.volume,
                implied_rate
            ])
        
        # Prepare response
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=mbb_data.csv'}
        )
    except Exception as e:
        logger.error(f"Error exporting data: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Helper functions
def calculate_monthly_payment(loan_amount, annual_rate, loan_term_years):
    loan_term_months = loan_term_years * 12
    monthly_rate = annual_rate / 12
    
    if monthly_rate == 0:
        return loan_amount / loan_term_months
    
    payment = (monthly_rate * loan_amount) / (1 - (1 + monthly_rate) ** -loan_term_months)
    return payment

def calculate_implied_rate(mbb_price):
    # Derived from historical correlation analysis
    base_rate = 2.5  # Minimum observed rate
    price_ratio = (mbb_price - 90) / (120 - 90)  # Normalize 90-120 price range
    return round(base_rate + (6.0 * price_ratio), 3)

def process_natural_language_query(query):
    # Placeholder for NLP processing
    # This will be implemented with more sophisticated NLP in nlu_queries.py
    query = query.lower()
    
    if 'current rate' in query or 'latest rate' in query:
        session = Session()
        latest = session.query(MBBCoupon).order_by(desc(MBBCoupon.timestamp)).first()
        session.close()
        
        if latest:
            rate = calculate_implied_rate(latest.close)
            return f"The current implied mortgage rate is {rate}% based on the latest MBB price of ${latest.close:.2f}."
    
    if 'breakeven' in query or 'break even' in query:
        return "The breakeven period is calculated by dividing the buydown cost by the monthly payment savings. You can use our calculator on the home page to get a personalized breakeven analysis."
    
    return "I'm sorry, I don't have enough information to answer that question yet. Please try a different query or check back later as our natural language capabilities are being enhanced."

if __name__ == '__main__':
    app.run(debug=True)