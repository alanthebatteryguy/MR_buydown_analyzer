from flask import Flask, render_template, jsonify, request, Response
from sqlalchemy import create_engine, text, desc
from sqlalchemy.orm import sessionmaker
from data_collector import initialize_db, MBBCoupon
from calculations import calculate_roi, calculate_monthly_payment
from visualization import BuydownVisualizer
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

# Initialize visualizer
visualizer = BuydownVisualizer()

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

@app.route('/api/charts/roi_vs_coupon')
def get_roi_vs_coupon_chart():
    try:
        # Get date parameter
        date_str = request.args.get('date')
        date = pd.to_datetime(date_str) if date_str else None
        
        # Query database for data
        session = Session()
        data = session.query(MBBCoupon).all()
        session.close()
        
        # Convert to DataFrame
        df = pd.DataFrame([(d.close, calculate_roi(d.close)) for d in data],
                         columns=['original_rate', 'roi'])
        
        # Generate chart
        fig = visualizer.plot_roi_vs_coupon(df, date=date)
        
        # Convert to base64
        img_str = visualizer.figure_to_base64(fig)
        
        return jsonify({'chart': img_str})
    except Exception as e:
        logger.error(f"Error generating ROI vs Coupon chart: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/charts/roi_vs_time')
def get_roi_vs_time_chart():
    try:
        # Get rate parameter
        rate = request.args.get('rate', type=float)
        
        # Query database for data
        session = Session()
        data = session.query(MBBCoupon).all()
        session.close()
        
        # Convert to DataFrame
        df = pd.DataFrame([(d.timestamp, d.close, calculate_roi(d.close)) for d in data],
                         columns=['date', 'original_rate', 'roi'])
        
        # Generate chart
        fig = visualizer.plot_roi_vs_time(df, rate=rate)
        
        # Convert to base64
        img_str = visualizer.figure_to_base64(fig)
        
        return jsonify({'chart': img_str})
    except Exception as e:
        logger.error(f"Error generating ROI vs Time chart: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/charts/cost_effectiveness')
def get_cost_effectiveness_chart():
    try:
        # Get parameters
        metric = request.args.get('metric', 'buydown_cost')
        rate = request.args.get('rate', type=float)
        
        # Query database for data
        session = Session()
        data = session.query(MBBCoupon).all()
        session.close()
        
        # Convert to DataFrame
        df = pd.DataFrame([(d.timestamp, d.close, calculate_roi(d.close)) for d in data],
                         columns=['date', 'original_rate', 'roi'])
        
        # Add cost metrics
        df['buydown_cost'] = df['original_rate'] * 1000  # Example calculation
        df['rate_difference'] = df['original_rate'].diff()
        
        # Generate chart
        fig = visualizer.plot_cost_effectiveness_vs_time(df, metric=metric, rate=rate)
        
        # Convert to base64
        img_str = visualizer.figure_to_base64(fig)
        
        return jsonify({'chart': img_str})
    except Exception as e:
        logger.error(f"Error generating Cost Effectiveness chart: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/roi/<float:loan_amount>/<float:original_rate>/<float:buydown_rate>')
def get_roi(loan_amount, original_rate, buydown_rate):
    try:
        # Get loan term from query parameter (default to 30 years)
        loan_term = int(request.args.get('term', 30))
        
        # Calculate monthly payments (rates are already in percentage form)
        original_payment = calculate_monthly_payment(original_rate, loan_amount, loan_term)
        buydown_payment = calculate_monthly_payment(buydown_rate, loan_amount, loan_term)
        
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

# Add this function definition after the imports and before the app initialization
def calculate_implied_rate(price):
    """Calculate implied interest rate from MBS price
    
    Args:
        price: MBS price (e.g., 95.5)
        
    Returns:
        Implied interest rate as a percentage
    """
    # Simple conversion model: higher price = lower rate
    if price <= 0:
        return 0
    implied_rate = 100 / price * 6  # Simple conversion model
    return implied_rate

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

@app.route('/chat')
def chat():
    return render_template('chat.html')

@app.route('/api/payback_comparison')
def get_payback_comparison():
    try:
        # Get time range from query parameter (default to 1 month)
        time_range = request.args.get('range', '1m')
        loan_amount = float(request.args.get('loan_amount', 300000))
        
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
        
        # Format data for analysis
        formatted_data = []
        for entry in data:
            formatted_data.append({
                'date': entry.timestamp,
                'original_rate': calculate_implied_rate(entry.close),
                'original_price': entry.close
            })
        
        # Convert to DataFrame
        df = pd.DataFrame(formatted_data)
        
        # Prepare data for payback period comparison
        payback_data = visualizer.prepare_payback_data(df, loan_amount=loan_amount)
        
        # Format data for response
        dates = [d.strftime('%Y-%m-%d') for d in payback_data['date'].unique()]
        
        # Get 1-point and 2-point buydown data
        one_point_data = payback_data[payback_data['buydown_cost_1pt'] == loan_amount * 0.01]
        two_point_data = payback_data[payback_data['buydown_cost_2pt'] == loan_amount * 0.02]
        
        # Calculate average payback periods by date
        one_point_avg = one_point_data.groupby('date')['payback_years_1pt'].mean().reset_index()
        two_point_avg = two_point_data.groupby('date')['payback_years_2pt'].mean().reset_index()
        
        # Format for response
        one_point_values = [float(v) for v in one_point_avg['payback_years_1pt'].values]
        two_point_values = [float(v) for v in two_point_avg['payback_years_2pt'].values]
        
        # Get deal quality metrics
        good_deals = payback_data[payback_data['deal_quality'] == 'Good'].to_dict('records')
        bad_deals = payback_data[payback_data['deal_quality'] == 'Bad'].to_dict('records')
        
        # Format deals for response
        good_deals_formatted = [{
            'from_rate': f"{d['original_rate']*100:.2f}%",
            'to_rate': f"{d['target_rate']*100:.2f}%",
            'points': 1 if d['buydown_cost_1pt'] == loan_amount * 0.01 else 2,
            'reduction': f"{d['rate_reduction_1pt']/100:.2f}%",
            'payback': f"{d['payback_years_1pt']:.1f} years"
        } for d in good_deals[:5]]  # Top 5 good deals
        
        return jsonify({
            'dates': dates,
            'one_point_payback': one_point_values,
            'two_point_payback': two_point_values,
            'good_deals': good_deals_formatted,
            'threshold_good': 3.5,  # Years threshold for good deal
            'threshold_great': 1.0   # Years threshold for great deal
        })
    except Exception as e:
        logger.error(f"Error generating payback comparison: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Add this new route to handle ROI calculations
# Around line 413
# Change the function name to avoid the conflict
@app.route('/api/roi/<int:loan_amount>/<float:current_rate>/<float:buydown_amount>', methods=['GET'])
def calculate_roi_endpoint(loan_amount, current_rate, buydown_amount):
    term = request.args.get('term', default=30, type=int)
    
    # Calculate buydown rate
    buydown_rate = current_rate - buydown_amount
    
    # Calculate monthly payments
    original_payment = calculate_monthly_payment(current_rate, loan_amount, term)
    buydown_payment = calculate_monthly_payment(buydown_rate, loan_amount, term)
    
    # Calculate monthly savings
    monthly_savings = original_payment - buydown_payment
    
    # Calculate buydown cost (1 point = 1% of loan amount)
    buydown_cost = buydown_amount * loan_amount / 100
    
    # Calculate breakeven period in months
    breakeven_months = round(buydown_cost / monthly_savings) if monthly_savings > 0 else float('inf')
    
    # Calculate ROI
    annual_savings = monthly_savings * 12
    roi = (annual_savings / buydown_cost) * 100 if buydown_cost > 0 else 0
    
    return jsonify({
        'roi': roi,
        'original_payment': original_payment,
        'buydown_payment': buydown_payment,
        'monthly_savings': monthly_savings,
        'annual_savings': annual_savings,
        'buydown_cost': buydown_cost,
        'breakeven_months': breakeven_months
    })

if __name__ == '__main__':
    app.run(debug=True)