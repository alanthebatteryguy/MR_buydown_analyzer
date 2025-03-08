from data_collector import initialize_db, MBBCoupon
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

def check_data_status():
    """Check the status of MBB data collection"""
    # Initialize database connection
    engine = initialize_db()
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Count total records
    total_count = session.query(MBBCoupon).count()
    print(f"Total MBB records in database: {total_count}")
    
    if total_count == 0:
        print("No data found. Run data_collector.py to populate the database.")
        session.close()
        return
    
    # Get date range
    first = session.query(MBBCoupon).order_by(MBBCoupon.timestamp).first()
    last = session.query(MBBCoupon).order_by(MBBCoupon.timestamp.desc()).first()
    
    print(f"Date range: {first.timestamp.date()} to {last.timestamp.date()}")
    
    # Check for gaps in data
    current_date = first.timestamp.date()
    end_date = last.timestamp.date()
    
    missing_dates = []
    weekend_dates = []
    
    while current_date <= end_date:
        # Skip weekends (no trading)
        if current_date.weekday() >= 5:  # 5=Saturday, 6=Sunday
            current_date += timedelta(days=1)
            weekend_dates.append(current_date)
            continue
        
        # Check if we have data for this date
        count = session.query(MBBCoupon).filter(
            MBBCoupon.timestamp >= datetime.combine(current_date, datetime.min.time()),
            MBBCoupon.timestamp < datetime.combine(current_date + timedelta(days=1), datetime.min.time())
        ).count()
        
        if count == 0:
            missing_dates.append(current_date)
        
        current_date += timedelta(days=1)
    
    # Check if up to date
    today = datetime.now().date()
    days_behind = (today - last.timestamp.date()).days
    
    if days_behind > 0:
        print(f"Data is {days_behind} days behind (last record: {last.timestamp.date()})")
    else:
        print("Data is up to date!")
    
    # Report missing dates (excluding weekends and holidays)
    if missing_dates:
        print(f"Found {len(missing_dates)} missing trading days:")
        for date in missing_dates[:10]:  # Show first 10 only
            print(f"  - {date}")
        if len(missing_dates) > 10:
            print(f"  ... and {len(missing_dates) - 10} more")
    else:
        print("No missing trading days found!")
    
    session.close()

if __name__ == "__main__":
    check_data_status()