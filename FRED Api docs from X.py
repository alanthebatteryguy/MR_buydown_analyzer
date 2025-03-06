"""
FRED API Integration Guide

Key Points:
1. Current FRED Series in Use:
   - MORTGAGE30US: 30-Year Fixed Rate Mortgage Average

2. Deprecated/Created Elements:
   - Removed invalid MBSSELLPRICES reference
   - Added series validation in get_fred_mbs_data()

3. Data Flow:
   FRED Data -> fred_data table -> Dashboard Display

4. Error Handling:
   - Failed series fetches logged to console
   - Null handling for missing environment variables

Example Valid Query:
from data_ingestion import get_fred_mbs_data

fred_df = get_fred_mbs_data()
print(fred_df[fred_df['series'] == '30yr_fixed_rate'])
"""