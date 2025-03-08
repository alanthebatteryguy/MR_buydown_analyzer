import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import os

# Import our modules
from data_collector import fetch_mbb_data, initialize_db, process_data
from data_validation import run_all_validations, validate_mort_correlation
from data_retention import enforce_data_retention

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_data_collection():
    """Test data collection from Yahoo Finance"""
    logger.info("Testing data collection...")
    
    # Fetch data
    raw_data = fetch_mbb_data()
    
    if raw_data is None or len(raw_data) == 0:
        logger.error("❌ Data collection failed: No data returned")
        return False
    
    logger.info(f"✅ Successfully collected {len(raw_data)} data points")
    logger.info(f"Sample data:\n{raw_data.head()}")
    return True

def test_data_validation():
    """Test data validation functions"""
    logger.info("Testing data validation...")
    
    # Fetch data for validation
    raw_data = fetch_mbb_data()
    
    if raw_data is None or len(raw_data) == 0:
        logger.error("❌ Data validation skipped: No data to validate")
        return False
    
    # Process data
    processed = process_data(raw_data)
    df = pd.DataFrame(processed)
    
    # Run validations
    try:
        valid, results = run_all_validations(df)
    except Exception as e:
        logger.warning(f"⚠️ Validation partially failed: {str(e)}")
        valid = False
        results = {}
    
    # Log results
    for check, result in results.items():
        status = "✅" if result else "❌"
        logger.info(f"{status} {check}: {result}")
    
    return valid

def test_database_operations():
    """Test database insert and retrieval"""
    logger.info("Testing database operations...")
    
    # Initialize test database
    test_engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(test_engine)
    
    # Create test data with varied key formats
    test_data = [{
        'Timestamp': '2024-05-01 09:30:00',
        'OPEN': 100.0,
        'HIGH': 101.0,
        'Low': 99.0,
        'close': 100.5,
        'Volume': 10000
    }]
    
    # Test insert
    try:
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=test_engine)
        session = Session()
        
        for record in test_data:
            clean_record = {str(k).lower(): v for k, v in record.items()}
            session.add(MBBCoupon(**clean_record))
        
        session.commit()
        logger.info("✅ Database insert test passed")
        return True
    except Exception as e:
        logger.error(f"❌ Database insert failed: {str(e)}")
        return False
    finally:
        session.close()
    
    # Initialize database
    engine = initialize_db()
    
    # Fetch and process data
    raw_data = fetch_mbb_data()
    
    if raw_data is None:
        logger.error("❌ Database test skipped: No data to store")
        return False
    
    # Process data
    processed = process_data(raw_data)
    
    try:
        # Insert data
        from sqlalchemy.orm import sessionmaker
        Session = sessionmaker(bind=engine)
        session = Session()
        
        from data_collector import MBBCoupon
        
        # Clear test data first
        test_start = datetime.now() - timedelta(hours=1)
        session.query(MBBCoupon).filter(MBBCoupon.timestamp >= test_start).delete()
        
        # Insert new records
        for record in processed:
            coupon = MBBCoupon(**record)
            session.add(coupon)
        
        session.commit()
        
        # Verify data was inserted
        count = session.query(MBBCoupon).filter(MBBCoupon.timestamp >= test_start).count()
        logger.info(f"✅ Successfully inserted {count} records")
        
        # Test data retrieval
        latest = session.query(MBBCoupon).order_by(MBBCoupon.timestamp.desc()).first()
        logger.info(f"Latest record: {latest.timestamp} - Close: {latest.close}")
        
        session.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Database operations failed: {str(e)}")
        return False

def test_basic_calculations():
    """Test basic mortgage calculations"""
    logger.info("Testing basic mortgage calculations...")
    
    # Test parameters
    loan_amount = 300000
    loan_term_years = 30
    loan_term_months = loan_term_years * 12
    
    # Test monthly payment calculation
    def calculate_monthly_payment(annual_rate):
        monthly_rate = annual_rate / 12
        if monthly_rate == 0:
            return loan_amount / loan_term_months
        payment = (monthly_rate * loan_amount) / (1 - (1 + monthly_rate) ** -loan_term_months)
        return payment
    
    # Test rates
    test_rates = [0.03, 0.035, 0.04, 0.045, 0.05, 0.055, 0.06]
    
    # Calculate payments
    payments = [calculate_monthly_payment(rate) for rate in test_rates]
    
    # Display results
    for rate, payment in zip(test_rates, payments):
        logger.info(f"Monthly payment at {rate*100:.1f}%: ${payment:.2f}")
    
    # Test buydown cost calculation
    def calculate_buydown_cost(price_r1, price_r2):
        price_diff = price_r1 - price_r2
        buydown_cost = price_diff * loan_amount / 100
        return buydown_cost
    
    # Test prices
    test_prices = [95, 96, 97, 98, 99, 100, 101]
    
    # Calculate buydown costs
    for i in range(len(test_prices) - 1):
        price_r1 = test_prices[i]
        price_r2 = test_prices[i+1]
        cost = calculate_buydown_cost(price_r1, price_r2)
        logger.info(f"Cost to buy down from price {price_r1} to {price_r2}: ${cost:.2f}")
    
    # Test ROI calculation
    def calculate_roi(rate_r1, rate_r2, price_r1, price_r2):
        buydown_cost = calculate_buydown_cost(price_r1, price_r2)
        if buydown_cost <= 0:
            return None
        
        payment_r1 = calculate_monthly_payment(rate_r1)
        payment_r2 = calculate_monthly_payment(rate_r2)
        monthly_savings = payment_r1 - payment_r2
        annual_savings = monthly_savings * 12
        
        roi = (annual_savings / buydown_cost) * 100
        return roi
    
    # Calculate ROI for each rate pair
    for i in range(len(test_rates) - 1):
        rate_r1 = test_rates[i+1]  # Start from higher rate
        rate_r2 = test_rates[i]    # Buy down to lower rate
        price_r1 = test_prices[i+1]
        price_r2 = test_prices[i]
        
        roi = calculate_roi(rate_r1, rate_r2, price_r1, price_r2)
        logger.info(f"ROI for buying down from {rate_r1*100:.1f}% to {rate_r2*100:.1f}%: {roi:.2f}%")
    
    # Create a simple visualization
    plt.figure(figsize=(10, 6))
    plt.plot([r*100 for r in test_rates[1:]], 
             [calculate_roi(test_rates[i+1], test_rates[i], test_prices[i+1], test_prices[i]) 
              for i in range(len(test_rates)-1)], 
             marker='o')
    plt.title('ROI vs. Original Coupon Rate')
    plt.xlabel('Original Coupon Rate (%)')
    plt.ylabel('ROI (%)')
    plt.grid(True)
    
    # Save the plot
    os.makedirs('test_output', exist_ok=True)
    plt.savefig('test_output/roi_test.png')
    logger.info("✅ Test visualization saved to test_output/roi_test.png")
    
    return True

def run_all_tests():
    """Run all tests and report results"""
    tests = [
        ("Data Collection", test_data_collection),
        ("Data Validation", test_data_validation),
        ("Database Operations", test_database_operations),
        ("Basic Calculations", test_basic_calculations)
    ]
    
    results = []
    
    logger.info("=== Starting Core Functionality Tests ===")
    
    for name, test_func in tests:
        logger.info(f"\n=== Testing {name} ===")
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            logger.error(f"Test failed with exception: {str(e)}")
            results.append((name, False))
    
    logger.info("\n=== Test Results Summary ===")
    all_passed = True
    for name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{status} - {name}")
        if not result:
            all_passed = False
    
    if all_passed:
        logger.info("\n🎉 All tests passed! The core functionality is working correctly.")
    else:
        logger.info("\n⚠️ Some tests failed. Please review the logs for details.")

if __name__ == "__main__":
    run_all_tests()