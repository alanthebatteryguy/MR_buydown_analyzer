import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import io
import base64
from matplotlib.figure import Figure
import logging

logger = logging.getLogger(__name__)

class BuydownVisualizer:
    """
    Creates visualizations for mortgage rate buydown analysis
    """
    
    def __init__(self, theme='default'):
        """
        Initialize visualizer with theme settings
        
        Args:
            theme: Visual theme ('default', 'dark', 'light')
        """
        self.theme = theme
        self._setup_theme()
    
    def _setup_theme(self):
        """Configure matplotlib theme based on settings"""
        if self.theme == 'dark':
            plt.style.use('dark_background')
        elif self.theme == 'light':
            plt.style.use('seaborn-whitegrid')
        else:
            plt.style.use('seaborn')
    
    def plot_roi_vs_coupon(self, data, date=None, figsize=(10, 6)):
        """
        Create Chart A: ROI vs. Coupon Rate for a given day
        
        Args:
            data: DataFrame with coupon rates and ROI values
            date: Specific date for the chart title
            figsize: Figure size as (width, height) tuple
            
        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot ROI vs original rate
        ax.plot(data['original_rate'] * 100, data['roi'], marker='o', linestyle='-', label='ROI (%)')
        
        # Add labels and title
        ax.set_xlabel('Coupon Rate (%)')
        ax.set_ylabel('ROI (%)')
        
        if date:
            ax.set_title(f'ROI vs. Coupon Rate on {date}')
        else:
            ax.set_title('ROI vs. Coupon Rate')
            
        # Add grid and legend
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Format x-axis as percentages
        ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f'{x:.1f}%'))
        
        return fig
    
    def plot_roi_vs_time(self, data, rate=None, figsize=(10, 6)):
        """
        Create Chart B: ROI vs. Time for a selected coupon rate
        
        Args:
            data: DataFrame with dates and ROI values
            rate: Specific coupon rate to highlight
            figsize: Figure size as (width, height) tuple
            
        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=figsize)
        
        # Filter data if rate is specified
        if rate is not None:
            filtered_data = data[data['original_rate'].round(3) == round(rate, 3)]
            
            if filtered_data.empty:
                logger.warning(f"No data found for rate {rate}")
                ax.text(0.5, 0.5, f"No data available for {rate*100:.2f}%", 
                        horizontalalignment='center', verticalalignment='center')
                return fig
                
            # Plot ROI vs time for specific rate
            ax.plot(filtered_data['date'], filtered_data['roi'], marker='o', linestyle='-', 
                   label=f'ROI for {rate*100:.2f}%')
            
            ax.set_title(f'ROI vs. Time for {rate*100:.2f}% Coupon Rate')
        else:
            # Group by date and original_rate
            grouped = data.groupby(['date', 'original_rate'])['roi'].mean().reset_index()
            
            # Plot for each unique rate
            for rate_val in grouped['original_rate'].unique():
                rate_data = grouped[grouped['original_rate'] == rate_val]
                ax.plot(rate_data['date'], rate_data['roi