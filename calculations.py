def calculate_monthly_payment(rate, loan_amount, years=30):
    """Calculate monthly mortgage payment using amortization formula"""
    monthly_rate = rate / 100 / 12
    months = years * 12
    payment = (monthly_rate * loan_amount) / (1 - (1 + monthly_rate) ** -months)
    return payment

def calculate_roi(loan_amount: float, original_rate: float, buydown_rate: float, 
                 price_data: dict, date: str) -> dict:
    """Calculate ROI for buydown between two rates"""
    price1 = price_data.get(original_rate)
    price2 = price_data.get(buydown_rate)
    if price1 is None or price2 is None:
        return {'roi_percent': 0, 'breakeven_months': 0}
    
    # Calculate buydown cost
    cost = (price1 - price2) * loan_amount
    
    # Calculate monthly payments
    monthly_pmt1 = calculate_monthly_payment(original_rate, loan_amount)
    monthly_pmt2 = calculate_monthly_payment(buydown_rate, loan_amount)
    monthly_savings = monthly_pmt1 - monthly_pmt2
    
    # Calculate ROI and breakeven
    roi = (monthly_savings * 12 / cost) * 100 if cost > 0 else 0
    breakeven = (cost / monthly_savings) if monthly_savings > 0 else 0
    
    return {'roi_percent': roi, 'breakeven_months': breakeven}