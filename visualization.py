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
            plt.style.use('seaborn-v0_8-whitegrid')
        else:
            plt.style.use('default')
    
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
                ax.plot(rate_data['date'], rate_data['roi'], marker='o', linestyle='-', 
                       label=f'ROI for {rate_val*100:.2f}%')
            
            ax.set_title('ROI vs. Time for All Coupon Rates')
        
        # Add labels and formatting
        ax.set_xlabel('Date')
        ax.set_ylabel('ROI (%)')
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Format y-axis as percentages
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.1f}%'))
        
        # Rotate date labels for better readability
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        return fig
    
    def plot_cost_effectiveness_vs_time(self, data, metric='buydown_cost', rate=None, figsize=(10, 6)):
        """
        Create Chart C: Cost Effectiveness vs. Time
        
        Args:
            data: DataFrame with dates and cost metrics
            metric: Which cost metric to plot ('buydown_cost' or 'cost_per_basis_point')
            rate: Specific coupon rate to highlight
            figsize: Figure size as (width, height) tuple
            
        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=figsize)
        
        # Calculate cost per basis point if needed
        if metric == 'cost_per_basis_point' and 'cost_per_basis_point' not in data.columns:
            if 'rate_difference' in data.columns and 'buydown_cost' in data.columns:
                data['cost_per_basis_point'] = data['buydown_cost'] / (data['rate_difference'] * 100)
            else:
                logger.warning("Cannot calculate cost per basis point: missing required columns")
                metric = 'buydown_cost'
        
        # Filter data if rate is specified
        if rate is not None:
            filtered_data = data[data['original_rate'].round(3) == round(rate, 3)]
            
            if filtered_data.empty:
                logger.warning(f"No data found for rate {rate}")
                ax.text(0.5, 0.5, f"No data available for {rate*100:.2f}%", 
                        horizontalalignment='center', verticalalignment='center')
                return fig
                
            # Plot cost vs time for specific rate
            ax.plot(filtered_data['date'], filtered_data[metric], marker='o', linestyle='-', 
                   label=f'{metric.replace("_", " ").title()} for {rate*100:.2f}%')
            
            title_metric = 'Buydown Cost' if metric == 'buydown_cost' else 'Cost per Basis Point'
            ax.set_title(f'{title_metric} vs. Time for {rate*100:.2f}% Coupon Rate')
        else:
            # Group by date and original_rate
            grouped = data.groupby(['date', 'original_rate'])[metric].mean().reset_index()
            
            # Plot for each unique rate
            for rate_val in grouped['original_rate'].unique():
                rate_data = grouped[grouped['original_rate'] == rate_val]
                ax.plot(rate_data['date'], rate_data[metric], marker='o', linestyle='-', 
                       label=f'{rate_val*100:.2f}%')
            
            title_metric = 'Buydown Cost' if metric == 'buydown_cost' else 'Cost per Basis Point'
            ax.set_title(f'{title_metric} vs. Time for All Coupon Rates')
        
        # Add labels and formatting
        ax.set_xlabel('Date')
        
        if metric == 'buydown_cost':
            ax.set_ylabel('Buydown Cost ($)')
            # Format y-axis as currency
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'${y:,.0f}'))
        else:
            ax.set_ylabel('Cost per Basis Point ($)')
            # Format y-axis as currency
            ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'${y:,.0f}'))
        
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Rotate date labels for better readability
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        return fig
    
    def add_hover_tooltips(self, fig, data):
        """
        Add interactive hover tooltips to a matplotlib figure
        
        Args:
            fig: Matplotlib figure to add tooltips to
            data: DataFrame with data points
            
        Returns:
            Enhanced figure with tooltips
        """
        from matplotlib.backend_bases import MouseEvent
        import matplotlib.pyplot as plt
        
        # Create annotation object for tooltip
        annot = fig.axes[0].annotate("", xy=(0, 0), xytext=(20, 20),
                            textcoords="offset points",
                            bbox=dict(boxstyle="round", fc="w", alpha=0.8),
                            arrowprops=dict(arrowstyle="->"))
        annot.set_visible(False)
        
        # Function to update annotation on hover
        def update_annot(ind, line, data):
            x, y = line.get_data()
            annot.xy = (x[ind["ind"][0]], y[ind["ind"][0]])
            
            # Get the corresponding data point
            idx = ind["ind"][0]
            if idx < len(data):
                point_data = data.iloc[idx]
                
                # Create tooltip text based on available columns
                text = ""
                if 'date' in point_data:
                    text += f"Date: {point_data['date']}\n"
                if 'original_rate' in point_data:
                    text += f"Rate: {point_data['original_rate']*100:.2f}%\n"
                if 'roi' in point_data:
                    text += f"ROI: {point_data['roi']:.2f}%\n"
                if 'buydown_cost' in point_data:
                    text += f"Cost: ${point_data['buydown_cost']:,.2f}\n"
                if 'monthly_savings' in point_data:
                    text += f"Monthly Savings: ${point_data['monthly_savings']:,.2f}"
                
                annot.set_text(text)
        
        # Function to handle hover events
        def hover(event):
            if event.inaxes == fig.axes[0]:
                for i, line in enumerate(fig.axes[0].get_lines()):
                    cont, ind = line.contains(event)
                    if cont:
                        update_annot(ind, line, data)
                        annot.set_visible(True)
                        fig.canvas.draw_idle()
                        return
                annot.set_visible(False)
                fig.canvas.draw_idle()
        
        # Connect hover event to figure
        fig.canvas.mpl_connect("motion_notify_event", hover)
        
        return fig
    
    def filter_by_date_range(self, data, start_date=None, end_date=None):
        """
        Filter data by date range
        
        Args:
            data: DataFrame with date column
            start_date: Start date for filtering (inclusive)
            end_date: End date for filtering (inclusive)
            
        Returns:
            Filtered DataFrame
        """
        filtered_data = data.copy()
        
        if start_date is not None:
            filtered_data = filtered_data[filtered_data['date'] >= pd.to_datetime(start_date)]
            
        if end_date is not None:
            filtered_data = filtered_data[filtered_data['date'] <= pd.to_datetime(end_date)]
            
        return filtered_data
    
    def filter_by_rate_range(self, data, min_rate=None, max_rate=None):
        """
        Filter data by coupon rate range
        
        Args:
            data: DataFrame with original_rate column
            min_rate: Minimum rate for filtering (inclusive)
            max_rate: Maximum rate for filtering (inclusive)
            
        Returns:
            Filtered DataFrame
        """
        filtered_data = data.copy()
        
        if min_rate is not None:
            filtered_data = filtered_data[filtered_data['original_rate'] >= min_rate]
            
        if max_rate is not None:
            filtered_data = filtered_data[filtered_data['original_rate'] <= max_rate]
            
        return filtered_data
    
    def export_figure(self, fig, filename, format='png', dpi=300):
        """
        Export figure to file
        
        Args:
            fig: Matplotlib figure to export
            filename: Output filename
            format: Output format ('png' or 'pdf')
            dpi: Resolution for raster formats
            
        Returns:
            True if successful, False otherwise
        """
        try:
            fig.savefig(filename, format=format, dpi=dpi, bbox_inches='tight')
            logger.info(f"Figure exported to {filename}")
            return True
        except Exception as e:
            logger.error(f"Error exporting figure: {e}")
            return False
    
    def figure_to_base64(self, fig, format='png', dpi=100):
        """
        Convert figure to base64 string for web embedding
        
        Args:
            fig: Matplotlib figure to convert
            format: Output format ('png' or 'pdf')
            dpi: Resolution for raster formats
            
        Returns:
            Base64 encoded string
        """
        buf = io.BytesIO()
        fig.savefig(buf, format=format, dpi=dpi, bbox_inches='tight')
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        return img_str