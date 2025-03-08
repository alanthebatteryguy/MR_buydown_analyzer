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
    
    def plot_payback_comparison(self, data, figsize=(12, 8)):
        """
        Create a chart comparing payback periods for 1-point and 2-point buydowns
        with visual indicators for good and bad deals
        
        Args:
            data: DataFrame with historical buydown data
            figsize: Figure size as (width, height) tuple
            
        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=figsize)
        
        # Calculate payback periods
        data['payback_years_1pt'] = data['buydown_cost_1pt'] / (data['monthly_savings_1pt'] * 12)
        data['payback_years_2pt'] = data['buydown_cost_2pt'] / (data['monthly_savings_2pt'] * 12)
        
        # Create scatter plots with size based on rate reduction
        scatter_1pt = ax.scatter(data['date'], data['payback_years_1pt'],
                                c=data['rate_reduction_1pt'], cmap='RdYlGn_r',
                                s=150, alpha=0.7, label='1-Point Buydown')
        scatter_2pt = ax.scatter(data['date'], data['payback_years_2pt'],
                                c=data['rate_reduction_2pt'], cmap='RdYlGn_r',
                                s=150, alpha=0.7, label='2-Point Buydown')
        
        # Add reference lines and regions for deal quality
        ax.axhspan(0, 1.0, color='g', alpha=0.1, label='Great Deal Zone')
        ax.axhspan(1.0, 3.5, color='y', alpha=0.1, label='Good Deal Zone')
        ax.axhspan(3.5, plt.ylim()[1], color='r', alpha=0.1, label='Bad Deal Zone')
        
        ax.axhline(y=3.5, color='r', linestyle='--', alpha=0.5, label='Max Good Deal (3.5 years)')
        ax.axhline(y=1.0, color='g', linestyle='--', alpha=0.5, label='Great Deal (1 year)')
        
        # Customize the plot
        ax.set_xlabel('Date')
        ax.set_ylabel('Payback Period (Years)')
        ax.set_title('Buydown Payback Period Comparison')
        ax.grid(True, alpha=0.3)
        
        # Add colorbar to show rate reduction
        cbar = plt.colorbar(scatter_1pt)
        cbar.set_label('Rate Reduction (bps)')
        
        # Rotate date labels
        plt.xticks(rotation=45)
        
        # Add legend with custom ordering
        handles, labels = ax.get_legend_handles_labels()
        order = [4, 5, 0, 1, 2, 3]  # Reorder to group zones and lines together
        ax.legend([handles[i] for i in order], [labels[i] for i in order],
                 bbox_to_anchor=(1.15, 1), loc='upper left')
        
        # Adjust layout to prevent label cutoff
        plt.tight_layout()
        
        return fig
    
    def prepare_payback_data(self, data, loan_amount=300000):
        """
        Prepare data for payback period comparison visualization
        
        Args:
            data: DataFrame with historical rate and price data
            loan_amount: Loan amount for calculations
            
        Returns:
            DataFrame with payback periods and rate reductions
        """
        result = []
        
        # Group by date
        for date, group in data.groupby('date'):
            # Sort rates from highest to lowest
            sorted_rates = sorted(group['original_rate'].unique(), reverse=True)
            sorted_prices = [group[group['original_rate'] == rate]['original_price'].iloc[0] for rate in sorted_rates]
            
            # Calculate for each rate (except the lowest)
            for i in range(len(sorted_rates) - 1):
                # Current rate and price
                current_rate = sorted_rates[i]
                current_price = sorted_prices[i]
                
                # Calculate 10bps increments
                for j in range(1, min(len(sorted_rates) - i, 6)):  # Up to 50bps in 10bps increments
                    target_rate = sorted_rates[i + j]
                    target_price = sorted_prices[i + j]
                    rate_reduction = (current_rate - target_rate) * 100  # Convert to basis points
                    
                    # Calculate for 1-point buydown
                    buydown_cost_1pt = loan_amount * 0.01  # 1% of loan amount
                    
                    # Calculate for 2-point buydown
                    buydown_cost_2pt = loan_amount * 0.02  # 2% of loan amount
                    
                    # Calculate monthly payment at both rates
                    payment_current = self._calculate_monthly_payment(current_rate, loan_amount)
                    payment_target = self._calculate_monthly_payment(target_rate, loan_amount)
                    monthly_savings = payment_current - payment_target
                    
                    # Calculate payback periods
                    payback_months_1pt = buydown_cost_1pt / monthly_savings if monthly_savings > 0 else float('inf')
                    payback_months_2pt = buydown_cost_2pt / monthly_savings if monthly_savings > 0 else float('inf')
                    
                    # Determine deal quality based on rate reduction per point
                    # Bad deal: 100bps for 0.25% reduction or less
                    # Good deal: 100bps for 0.35% reduction or more
                    # Great deal: Payback period of 1-3.5 years
                    
                    # For 1-point buydown
                    reduction_per_point_1pt = rate_reduction / 1.0
                    if reduction_per_point_1pt >= 35:  # 0.35% or more reduction per point
                        deal_quality_1pt = 'Great' if payback_months_1pt/12 <= 3.5 else 'Good'
                    elif reduction_per_point_1pt >= 25:  # 0.25% reduction per point
                        deal_quality_1pt = 'Neutral'
                    else:
                        deal_quality_1pt = 'Bad'
                    
                    # For 2-point buydown
                    reduction_per_point_2pt = rate_reduction / 2.0
                    if reduction_per_point_2pt >= 35:  # 0.35% or more reduction per point
                        deal_quality_2pt = 'Great' if payback_months_2pt/12 <= 3.5 else 'Good'
                    elif reduction_per_point_2pt >= 25:  # 0.25% reduction per point
                        deal_quality_2pt = 'Neutral'
                    else:
                        deal_quality_2pt = 'Bad'
                    
                    # Store results
                    result.append({
                        'date': date,
                        'original_rate': current_rate,
                        'target_rate': target_rate,
                        'rate_reduction_1pt': rate_reduction,
                        'rate_reduction_2pt': rate_reduction,
                        'reduction_per_point_1pt': reduction_per_point_1pt,
                        'reduction_per_point_2pt': reduction_per_point_2pt,
                        'buydown_cost_1pt': buydown_cost_1pt,
                        'buydown_cost_2pt': buydown_cost_2pt,
                        'monthly_savings_1pt': monthly_savings,
                        'monthly_savings_2pt': monthly_savings,
                        'payback_months_1pt': payback_months_1pt,
                        'payback_months_2pt': payback_months_2pt,
                        'payback_years_1pt': payback_months_1pt / 12,
                        'payback_years_2pt': payback_months_2pt / 12,
                        'deal_quality_1pt': deal_quality_1pt,
                        'deal_quality_2pt': deal_quality_2pt
                    })
        
        return pd.DataFrame(result)
    
    def _calculate_monthly_payment(self, annual_rate, loan_amount, loan_term_years=30):
        """
        Calculate monthly mortgage payment
        
        Args:
            annual_rate: Annual interest rate (decimal)
            loan_amount: Loan principal amount
            loan_term_years: Loan term in years
            
        Returns:
            Monthly payment amount
        """
        loan_term_months = loan_term_years * 12
        monthly_rate = annual_rate / 12
        
        if monthly_rate == 0:
            return loan_amount / loan_term_months
            
        payment = (monthly_rate * loan_amount) / (1 - (1 + monthly_rate) ** -loan_term_months)
        return payment