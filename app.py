from flask import Flask, render_template, jsonify
from data_ingestion import get_fred_mbs_data, initialize_schema
from calculations import calculate_roi
import pandas as pd

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    initialize_schema()
    fred_data = get_fred_mbs_data()
    return render_template('dashboard.html', 
                         rates=fred_data[fred_data['series'] == '30yr_fixed_rate'])

def get_latest_date():
    engine = create_engine('sqlite:///mbs_data.db')
    with engine.connect() as conn:
        result = conn.execute(text("SELECT MAX(date) FROM mbs_prices"))
        return result.fetchone()[0]

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

if __name__ == '__main__':
    app.run(debug=True)