"""
Configuration module for Hardware Alpha system.
Centralized configuration with environment variable support and validation.
"""

import os
import sys
from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import timedelta
import logging

# Third-party imports
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logging.warning("python-dotenv not installed, using system environment variables")

@dataclass
class FirebaseConfig:
    """Firebase configuration with validation"""
    project_id: str
    private_key_id: str
    private_key: str
    client_email: str
    client_id: str
    client_x509_cert_url: str
    
    @classmethod
    def from_env(cls) -> Optional['FirebaseConfig']:
        """Load Firebase config from environment variables"""
        try:
            # Firebase Admin SDK expects the private key with escaped newlines
            private_key = os.getenv('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n')
            
            if not private_key or len(private_key) < 100:
                logging.error("Firebase private key is invalid or missing")
                return None
                
            return cls(
                project_id=os.getenv('FIREBASE_PROJECT_ID', ''),
                private_key_id=os.getenv('FIREBASE_PRIVATE_KEY_ID', ''),
                private_key=private_key,
                client_email=os.getenv('FIREBASE_CLIENT_EMAIL', ''),
                client_id=os.getenv('FIREBASE_CLIENT_ID', ''),
                client_x509_cert_url=os.getenv('FIREBASE_CLIENT_X509_CERT_URL', '')
            )
        except Exception as e:
            logging.error(f"Failed to load Firebase config: {str(e)}")
            return None

@dataclass
class APIConfig:
    """API configuration for external services"""
    # Apple Refurbished RSS (no auth required)
    apple_refurbished_rss: str = "https://www.apple.com/shop/refurbished/feed/mac"
    
    # eBay API (requires OAuth2 - will request if needed)
    ebay_app_id: Optional[str] = os.getenv('EBAY_APP_ID')
    ebay_cert_id: Optional[str] = os.getenv('EBAY_CERT_ID')
    ebay_dev_id: Optional[str] = os.getenv('EBAY_DEV_ID')
    
    # Reddit API for sentiment analysis
    reddit_client_id: Optional[str] = os.getenv('REDDIT_CLIENT_ID')
    reddit_client_secret: Optional[str] = os.getenv('REDDIT_CLIENT_SECRET')
    reddit_user_agent: str = "HardwareAlpha/1.0 (by Autonomous Agent)"
    
    # SEC EDGAR API (public, no auth)
    sec_edgar_base: str = "https://www.sec.gov/Archives/edgar/data"
    
    # Telegram alerting
    telegram_bot_token: Optional[str] = os.getenv('TELEGRAM_BOT_TOKEN')
    telegram_chat_id: Optional[str] = os.getenv('TELEGRAM_CHAT_ID')

@dataclass
class ModelConfig:
    """Machine learning model configuration"""
    # Training parameters
    train_test_split: float = 0.8
    random_state: int = 42
    cv_folds: int = 5
    
    # Feature engineering
    lookback_window_days: int = 90
    forecast_horizon_days: int = 45
    
    # Model hyperparameters (will be tuned)
    arima_order: tuple = (2, 1, 2)
    gb_n_estimators: int = 100
    gb_max_depth: int = 5
    
    # Confidence intervals
    bootstrap_samples: int = 1000
    confidence_level: float = 0.95

@dataclass
class TargetConfig:
    """Target hardware specifications"""
    target_name: str = "Mac Studio M2 Ultra"
    target_models: List[str] = None
    
    def __post_init__(self):
        if self.target_models is None:
            self.target_models = [
                "Mac13,1",  # Mac Studio M2 Ultra base
                "Mac13,2",  # Mac Studio M2 Ultra upgraded
            ]
    
    # Price thresholds (in USD)
    msrp: float = 3999.00  # Base model MSRP
    emergency_buy_threshold: float = 2800.00  # Immediate purchase price
    target_acquisition_price: float = 3200.00  # Ideal price point
    
    # Hardware specifications for filtering
    min_ram_gb: int = 64
    min_storage_tb: int = 1
    acceptable_configs: List[Dict] = None
    
    def __post_init__(self):
        if self.acceptable_configs is None:
            self.acceptable_configs = [
                {"ram_gb": 64, "storage_tb": 1, "cpu_cores": 24, "gpu_cores": 60},
                {"ram_gb": 128, "storage_tb": 2, "cpu_cores": 24, "gpu_cores": 60},
                {"ram_gb": 192, "storage_tb": 4, "cpu_cores": 24, "gpu_cores": 76},
            ]

class HardwareAlphaConfig:
    """Main configuration class"""
    
    def __init__(self):
        self.firebase = FirebaseConfig.from_env()
        self.api = APIConfig()
        self.model = ModelConfig()
        self.target = TargetConfig()
        
        # System settings
        self.scan_interval_minutes = 30  # How often to scan markets
        self.max_retries = 3
        self.retry_delay_seconds = 5
        
        # Budget model parameters
        self.daily_trading_capital = 1000.00  # USD available for trading
        self.minimum_cash_reserve = 5000.00  # Minimum cash to maintain
        self.hardware_budget_allocation = 0.7  # Max % of capital for hardware
        
        # Logging configuration
        self.log_level = logging.INFO
        self.log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
    def validate(self) -> bool:
        """Validate configuration"""
        errors = []
        
        if not self.firebase:
            errors.append("Firebase configuration is invalid or missing")
        
        if not self.api.telegram_bot_token or not self.api.telegram_chat_id:
            logging.warning("Telegram bot token or chat ID not configured - alerts disabled")
        
        # Validate target configuration
        if self.target.emergency_buy_threshold > self.target.msrp:
            errors.append(f"Emergency buy threshold ({self.target.emergency_buy_threshold}) cannot exceed MSRP ({self.target.msrp})")
        
        if errors:
            for error in errors:
                logging.error(f"Configuration error: {error}")
            return False
        
        return True

# Global configuration instance
config = HardwareAlphaConfig()