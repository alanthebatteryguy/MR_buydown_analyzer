import logging
import pandas as pd
from data_collector import fetch_mbb_data, process_data, initialize_db, update_database

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    try:
        # Initialize database
        logger.info('Initializing database...')
        engine = initialize_db()
        
        # Fetch data
        logger.info('Fetching MBB data...')
        data = fetch_mbb_data()
        
        if data is not None:
            logger.info(f'Successfully fetched data with shape: {data.shape}')
            logger.info('\nSample data:')
            print(data.head())
            
            # Process data
            logger.info('\nProcessing data...')
            processed = process_data(data)
            logger.info(f'Processed {len(processed)} records')
            if processed:
                logger.info('\nSample processed record:')
                print(processed[0])
                
                # Update database
                logger.info('\nUpdating database...')
                update_database(engine)
                logger.info('Database update complete')
        else:
            logger.error('Failed to fetch data')
    
    except Exception as e:
        logger.error(f'Error in data collection process: {str(e)}')

if __name__ == '__main__':
    main()