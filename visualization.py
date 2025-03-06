import matplotlib.pyplot as plt
import seaborn as sns
from sqlalchemy import create_engine
import pandas as pd

def plot_mbs_prices(coupon_rates: list):
    engine = create_engine('sqlite:///mbs_data.db')
    df = pd.read_sql(
        f"SELECT * FROM mbs_prices WHERE coupon_rate IN ({','.join(map(str, coupon_rates))})",
        engine
    )
    
    plt.figure(figsize=(12, 6))
    sns.lineplot(data=df, x='date', y='price', hue='coupon_rate')
    plt.title('MBS Price Trends by Coupon Rate')
    return save_plot(plt)

def plot_roi_trends(original_rate=None, buydown_rate=None):
    engine = create_engine('sqlite:///mbs_data.db')
    query = "SELECT date, AVG(roi) as avg_roi FROM daily_roi"
    params = {}
    if original_rate and buydown_rate:
        query += " WHERE original_rate = :original_rate AND buydown_rate = :buydown_rate"
        params = {'original_rate': original_rate, 'buydown_rate': buydown_rate}
    query += " GROUP BY date"
    df = pd.read_sql(query, engine, params=params)
    
    plt.figure(figsize=(12, 6))
    sns.lineplot(data=df, x='date', y='avg_roi')
    plt.title('Average ROI Trends Over Time')
    return save_plot(plt)

def save_plot(plot):
    plot.tight_layout()
    plot.savefig('static/plot.png')
    plot.clf()
    return 'static/plot.png'