import numpy as np
import pandas as pd
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class MortgageBuydownCalculator:
    """
    Handles all calculations related to mortgage rate buydowns
    including buydown costs, monthly savings, and ROI
    """
    
    def __init__(self, loan_amount=300000, loan_term_years=30):
        """
        Initialize calculator with loan parameters
        
        Args:
            loan_amount: Principal loan amount in dollars
            loan_term_years: Loan term in years (default: 30)
        """
        self.loan_amount = loan_amount
        self.loan_term_years = loan_term_years
        self.loan_term_months = loan_term_years * 12
    
    def calculate_monthly_payment(self, annual_rate):
        """
        Calculate monthly mortgage payment using standard amortization formula
        
        Args:
            annual_rate: Annual interest rate (e.g., 0.05 for 5%)
            
        Returns:
            Monthly payment amount
        """
        # Convert annual rate to monthly
        monthly_rate = annual_rate / 12
        
        # Calculate monthly payment using amortization formula
        # P = (r * PV) / (1 - (1 + r)^-n)
        # Where:
        # P = monthly payment
        # r = monthly interest rate
        # PV = loan amount (present value)
        # n = total number of payments (loan term in months)
        
        if monthly_rate == 0:
            return self.loan_amount / self.loan_term_months
            
        payment = (monthly_rate * self.loan_amount) / (1 - (1 + monthly_rate) ** -self.loan_term_months)
        return payment
    
    def calculate_buydown_cost(self, price_r1, price_r2):
        """
        Calculate the cost to buy down from rate r1 to rate r2
        
        Args:
            price_r1: MBS price at rate r1
            price_r2: MBS price at rate r2
            
        Returns:
            Cost to buy down in dollars
        """
        # Buydown Cost = (Price_r1 - Price_r2) × Loan Amount
        price_diff = price_r1 - price_r2
        buydown_cost = price_diff * self.loan_amount / 100  # Divide by 100 since prices are in percentage points
        return buydown_cost
    
    def calculate_monthly_savings(self, rate_r1, rate_r2):
        """
        Calculate monthly savings from buying down from rate r1 to rate r2
        
        Args:
            rate_r1: Original interest rate (e.g., 0.05 for 5%)
            rate_r2: Reduced interest rate (e.g., 0.045 for 4.5%)
            
        Returns:
            Monthly savings in dollars
        """
        payment_r1 = self.calculate_monthly_payment(rate_r1)
        payment_r2 = self.calculate_monthly_payment(rate_r2)
        monthly_savings = payment_r1 - payment_r2
        return monthly_savings
    
    def calculate_roi(self, rate_r1, rate_r2, price_r1, price_r2):
        """
        Calculate ROI for buying down from rate r1 to rate r2
        
        Args:
            rate_r1: Original interest rate (e.g., 0.05 for 5%)
            rate_r2: Reduced interest rate (e.g., 0.045 for 4.5%)
            price_r1: MBS price at rate r1
            price_r2: MBS price at rate r2
            
        Returns:
            ROI as a percentage
        """
        buydown_cost = self.calculate_buydown_cost(price_r1, price_r2)
        
        if buydown_cost <= 0:
            logger.warning(f"Invalid buydown cost: {buydown_cost} for rates {rate_r1} to {rate_r2}")
            return None
            
        monthly_savings = self.calculate_monthly_savings(rate_r1, rate_r2)
        annual_savings = monthly_savings * 12
        
        # ROI = (Annual Savings / Buydown Cost) * 100%
        roi = (annual_savings / buydown_cost) * 100
        return roi
    
    def calculate_incremental_buydowns(self, rates, prices, increment=0.001):
        """
        Calculate ROI for incremental buydowns (e.g., in 10 bps steps)
        
        Args:
            rates: List of available coupon rates
            prices: List of corresponding MBS prices
            increment: Rate increment in decimal (0.001 = 10 bps)
            
        Returns:
            DataFrame with buydown options and their ROIs
        """
        results = []
        
        # Create rate-price mapping
        rate_price_map = dict(zip(rates, prices))
        
        # Sort rates for processing
        sorted_rates = sorted(rates)
        
        for i, rate in enumerate(sorted_rates):
            if i == 0:
                continue  # Skip the lowest rate as we can't buy down from it
                
            # Current rate and price
            current_rate = rate
            current_price = rate_price_map[rate]
            
            # Calculate buydowns in specified increments
            target_rate = current_rate
            while target_rate - increment >= min(sorted_rates):
                target_rate -= increment
                
                # Find closest available rate
                closest_rate = min(sorted_rates, key=lambda x: abs(x - target_rate))
                target_price = rate_price_map[closest_rate]
                
                # Calculate metrics
                buydown_cost = self.calculate_buydown_cost(current_price, target_price)
                monthly_savings = self.calculate_monthly_savings(current_rate, closest_rate)
                roi = self.calculate_roi(current_rate, closest_rate, current_price, target_price)
                
                # Store results
                results.append({
                    'original_rate': current_rate,
                    'target_rate': closest_rate,
                    'rate_difference': current_rate - closest_rate,
                    'original_price': current_price,
                    'target_price': target_price,
                    'buydown_cost': buydown_cost,
                    'monthly_savings': monthly_savings,
                    'annual_savings': monthly_savings * 12,
                    'roi': roi
                })
        
        return pd.DataFrame(results)
    
    def analyze_time_series(self, time_series_data):
        """
        Analyze ROI changes over time for different buydown options
        
        Args:
            time_series_data: DataFrame with dates, rates, and prices
            
        Returns:
            DataFrame with ROI values over time
        """
        results = []
        
        # Group by date
        for date, group in time_series_data.groupby('date'):
            rates = group['rate'].values
            prices = group['price'].values
            
            # Calculate buydowns for this date
            daily_results = self.calculate_incremental_buydowns(rates, prices)
            
            # Add date column
            daily_results['date'] = date
            
            # Append to results
            results.append(daily_results)
        
        # Combine all results
        if results:
            return pd.concat(results, ignore_index=True)
        else:
            return pd.DataFrame()