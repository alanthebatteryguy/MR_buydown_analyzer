from data_ingestion import get_fred_mbs_data
from sqlalchemy import create_engine
import google.generativeai as genai
import os

def handle_nlu_query(query: str) -> str:
    """Process natural language queries about MBS data"""
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
    model = genai.GenerativeModel('gemini-pro')
    
    prompt = f"""Convert this mortgage analytics query to SQL:
    {query}
    
    Database schema:
    - fred_data (date, value, series)
    - mbs_prices (date, coupon_rate, price)
    - daily_roi (date, original_rate, buydown_rate, roi, breakeven_months)
    
    Return ONLY the SQL query without explanations.
    """
    
    try:
        response = model.generate_content(prompt)
        engine = create_engine('sqlite:///mbs_data.db')
        result = pd.read_sql(response.text, engine)
        return f"Here's what I found:\n{result.to_markdown()}"
    except Exception as e:
        return f"Error processing query: {str(e)}"