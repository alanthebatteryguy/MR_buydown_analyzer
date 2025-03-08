def calculate_monthly_payment(rate, loan_amount, years=30):
    """Calculate monthly mortgage payment using amortization formula"""
    monthly_rate = rate / 100 / 12
    months = years * 12
    payment = (monthly_rate * loan_amount) / (1 - (1 + monthly_rate) ** -months)
    return payment

def calculate_roi(rate, loan_amount=300000, buydown_increment=0.25):
    """Calculate ROI for a rate buydown
    
    Args:
        rate: Current mortgage rate (can be a single value or from MBS data)
        loan_amount: Loan amount in dollars (default: $300,000)
        buydown_increment: How much to buy down the rate (default: 0.25%)
        
    Returns:
        ROI percentage value
    """
    # If rate is already a percentage (e.g., 5.5), use as is
    # If it's a price (e.g., 95.5), convert to rate using a simple model
    if rate > 20:  # Likely a price, not a rate
        original_rate = 100 / rate * 6  # Simple conversion model
    else:
        original_rate = rate
    
    buydown_rate = original_rate - buydown_increment
    
    # Calculate monthly payments
    monthly_pmt1 = calculate_monthly_payment(original_rate, loan_amount)
    monthly_pmt2 = calculate_monthly_payment(buydown_rate, loan_amount)
    monthly_savings = monthly_pmt1 - monthly_pmt2
    
    # Calculate buydown cost (1 point = 1% of loan amount)
    buydown_cost = buydown_increment * loan_amount
    
    # Calculate ROI
    annual_savings = monthly_savings * 12
    roi = (annual_savings / buydown_cost) * 100 if buydown_cost > 0 else 0
    
    return roi