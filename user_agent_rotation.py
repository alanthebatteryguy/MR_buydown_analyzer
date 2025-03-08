import random
import logging
import time

logger = logging.getLogger(__name__)

class UserAgentRotator:
    """
    Provides rotating user agents for API requests to avoid rate limiting
    """
    
    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:89.0) Gecko/20100101 Firefox/89.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/91.0.864.59 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59"
        ]
        self.last_used_index = -1
        self.request_timestamps = []
        self.min_delay_seconds = 3  # Minimum delay between requests
    
    def get_next_user_agent(self):
        """Get the next user agent in rotation"""
        self.last_used_index = (self.last_used_index + 1) % len(self.user_agents)
        return self.user_agents[self.last_used_index]
    
    def get_random_user_agent(self):
        """Get a random user agent"""
        return random.choice(self.user_agents)
    
    def wait_if_needed(self):
        """
        Enforce delay between requests to comply with rate limits
        Returns the number of seconds waited
        """
        now = time.time()
        
        # Clean up old timestamps (older than 60 seconds)
        self.request_timestamps = [ts for ts in self.request_timestamps if now - ts < 60]
        
        # If we have recent requests, check if we need to wait
        if self.request_timestamps:
            last_request = max(self.request_timestamps)
            time_since_last = now - last_request
            
            if time_since_last < self.min_delay_seconds:
                wait_time = self.min_delay_seconds - time_since_last
                logger.debug(f"Rate limiting: Waiting {wait_time:.2f} seconds")
                time.sleep(wait_time)
                now = time.time()  # Update current time after waiting
        
        # Record this request
        self.request_timestamps.append(now)
        return now