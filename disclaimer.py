import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class DisclaimerManager:
    """
    Manages disclaimers for data sources and other legal requirements
    """
    
    def __init__(self):
        self.disclaimers = {
            "data_source": "Data sourced from Yahoo Finance. This tool is not affiliated with or endorsed by Yahoo Finance.",
            "financial_advice": "This tool provides analysis for informational purposes only and does not constitute financial advice.",
            "accuracy": "While we strive for accuracy, we make no guarantees about the correctness of calculations or predictions.",
            "timestamp": f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        }
    
    def get_disclaimer(self, key=None):
        """Get a specific disclaimer or all disclaimers"""
        if key is not None:
            return self.disclaimers.get(key, "")
        return self.disclaimers
    
    def get_full_disclaimer_text(self):
        """Get formatted text with all disclaimers"""
        return "\n\n".join(self.disclaimers.values())
    
    def get_html_disclaimer(self):
        """Get HTML formatted disclaimers for web display"""
        html = "<div class='disclaimers'>"
        for key, text in self.disclaimers.items():
            html += f"<p class='disclaimer {key}'>{text}</p>"
        html += "</div>"
        return html
    
    def update_timestamp(self):
        """Update the timestamp in the disclaimers"""
        self.disclaimers["timestamp"] = f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"