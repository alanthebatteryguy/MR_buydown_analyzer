from data_collector import initialize_db, MBBCoupon
from sqlalchemy.orm import sessionmaker

# Initialize database connection
engine = initialize_db()
Session = sessionmaker(bind=engine)
session = Session()

# Count records
count = session.query(MBBCoupon).count()
print(f"Total MBB records in database: {count}")

# Get date range
if count > 0:
    first = session.query(MBBCoupon).order_by(MBBCoupon.timestamp).first()
    last = session.query(MBBCoupon).order_by(MBBCoupon.timestamp.desc()).first()
    print(f"Date range: {first.timestamp} to {last.timestamp}")

session.close()