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

@app.route('/api/roi/<float:loan_amount>/<float:rate>')
def get_roi(loan_amount, rate):
    # Placeholder for actual price data retrieval
    price_data = {5.0: 102.5, 5.5: 101.75}  # Example data
    result = calculate_roi(
        loan_amount=loan_amount,
        original_rate=5.0,  # Example base rate
        buydown_rate=rate,
        price_data=price_data,
        date=pd.Timestamp.now().strftime('%Y-%m-%d')
    )
    return jsonify(result)

if __name__ == '__main__':
    app.run(debug=True)