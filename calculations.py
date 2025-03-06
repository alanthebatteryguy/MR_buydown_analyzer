def calculate_monthly_payment(rate, loan_amount, years=30):
    """Calculate monthly mortgage payment using amortization formula"""
    monthly_rate = rate / 100 / 12
    months = years * 12
    payment = (monthly_rate * loan_amount) / (1 - (1 + monthly_rate) ** -months)
    return payment

def calculate_roi(rate1, rate2, loan_amount, price1, price2):
    """Calculate ROI for buydown between two rates"""
    # Calculate buydown cost
    cost = (price1 - price2) * loan_amount
    
    # Calculate monthly payments
    payment1 = calculate_monthly_payment(rate1, loan_amount)
    payment2 = calculate_monthly_payment(rate2, loan_amount)
    
    # Monthly savings and annualized ROI
    monthly_savings = payment1 - payment2
    return (monthly_savings * 12 / cost) * 100 if cost != 0 else 0


# Replace all versions with this unified implementation
from sqlalchemy import create_engine, text

def calculate_roi(loan_amount: float, original_rate: float, buydown_rate: float, 
                 price_data: dict, date: str) -> dict:
    """PRD 3.2.3 - Unified implementation for buydown ROI"""
    price1 = price_data.get(original_rate)
    price2 = price_data.get(buydown_rate)
    if price1 is None or price2 is None:
        return {'roi_percent': 0, 'breakeven_months': 0}
    
    monthly_pmt1 = calculate_monthly_payment(original_rate, loan_amount)
    monthly_pmt2 = calculate_monthly_payment(buydown_rate, loan_amount)
    monthly_savings = monthly_pmt1 - monthly_pmt2
    
    cost = (price1 - price2) * loan_amount
    roi = (monthly_savings * 12 / cost) * 100 if cost > 0 else 0
    breakeven = (cost / monthly_savings) if monthly_savings > 0 else 0
    
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