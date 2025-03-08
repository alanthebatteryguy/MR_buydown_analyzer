from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def enforce_data_retention(db_path='sqlite:///mbs_data.db', retention_years=2):
    """
    Enforce data retention policy by removing data older than specified period
    
    Args:
        db_path: Path to SQLite database or SQLAlchemy engine
        retention_years: Number of years to keep data
        
    Returns:
        int: Number of records deleted
    """
    try:
        # Handle both engine objects and connection strings
        if hasattr(db_path, 'connect'):
            engine = db_path
        else:
            engine = create_engine(db_path)
        cutoff_date = datetime.now() - timedelta(days=365 * retention_years)
        
        with engine.connect() as conn:
            # Delete records older than retention period
            result = conn.execute(
                text("DELETE FROM mbs_coupons WHERE timestamp < :cutoff_date"),
                {"cutoff_date": cutoff_date}
            )
            
            deleted_count = result.rowcount
            logger.info(f"Data retention policy enforced: {deleted_count} records deleted (older than {cutoff_date})")
            
        # Vacuum database to reclaim space - must be outside transaction
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(text("VACUUM"))
            
        return deleted_count
            
    except Exception as e:
        logger.error(f"Error enforcing data retention policy: {str(e)}")
        return -1