#!/usr/bin/env python3
"""
Configuration management for tax extraction system
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass, field, asdict
import logging

logger = logging.getLogger(__name__)

@dataclass
class ScraperConfig:
    """Configuration for individual site scrapers"""
    domain: str
    name: str
    search_method: str  # 'direct_link', 'search_form', 'interactive'
    selectors: Dict[str, str] = field(default_factory=dict)
    extraction_steps: list = field(default_factory=list)
    wait_time: int = 10
    retry_count: int = 3
    retry_delay: int = 5
    requires_javascript: bool = False
    rate_limit_delay: float = 2.0
    timeout: int = 30

@dataclass
class SystemConfig:
    """System-wide configuration"""
    # Browser settings
    headless: bool = True
    browser_type: str = "chrome"  # chrome, firefox, edge
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    # Processing settings
    max_workers: int = 1
    batch_size: int = 10
    save_intermediate: bool = True
    
    # Retry settings
    max_retries: int = 3
    retry_backoff_factor: float = 2.0
    
    # Logging settings
    log_level: str = "INFO"
    log_file: str = "tax_extraction.log"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Output settings
    output_dir: str = "output"
    save_screenshots: bool = False
    save_html: bool = False
    
    # Connection settings
    connection_timeout: int = 30
    read_timeout: int = 60
    
    # Data validation
    validate_addresses: bool = True
    validate_amounts: bool = True
    min_valid_amount: float = 0.0
    max_valid_amount: float = 1000000.0

class ConfigManager:
    """Manages application configuration"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or "config.json"
        self.system_config = self._load_system_config()
        self.scraper_configs = self._load_scraper_configs()
        self._setup_directories()
    
    def _load_system_config(self) -> SystemConfig:
        """Load system configuration from file or environment"""
        config_data = {}
        
        # Try to load from file
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    file_config = json.load(f)
                    config_data.update(file_config.get('system', {}))
            except Exception as e:
                logger.warning(f"Could not load config file: {e}")
        
        # Override with environment variables
        env_mappings = {
            'TAX_EXTRACTOR_HEADLESS': ('headless', lambda x: x.lower() == 'true'),
            'TAX_EXTRACTOR_BROWSER': ('browser_type', str),
            'TAX_EXTRACTOR_MAX_WORKERS': ('max_workers', int),
            'TAX_EXTRACTOR_LOG_LEVEL': ('log_level', str),
            'TAX_EXTRACTOR_OUTPUT_DIR': ('output_dir', str),
        }
        
        for env_key, (config_key, converter) in env_mappings.items():
            if env_value := os.getenv(env_key):
                try:
                    config_data[config_key] = converter(env_value)
                except ValueError:
                    logger.warning(f"Invalid value for {env_key}: {env_value}")
        
        return SystemConfig(**config_data)
    
    def _load_scraper_configs(self) -> Dict[str, ScraperConfig]:
        """Load scraper configurations"""
        configs = {}
        
        # Default configurations
        default_configs = {
            'actweb.acttax.com': {
                'name': 'Montgomery County',
                'search_method': 'direct_link',
                'selectors': {
                    'property_address': '//td[contains(text(),"Property Address")]/following-sibling::td',
                    'amount_due': '//td[contains(text(),"Total Due")]/following-sibling::td',
                    'previous_year': '//td[contains(text(),"Prior Year")]/following-sibling::td',
                    'account_number': '//td[contains(text(),"Account")]/following-sibling::td',
                },
                'requires_javascript': False,
                'rate_limit_delay': 2.0,
            },
            'www.hctax.net': {
                'name': 'Harris County',
                'search_method': 'search_form',
                'selectors': {
                    'search_button': '//a[contains(text(),"Search/Pay")]',
                    'account_input': '//input[@id="account"]',
                    'submit_button': '//button[@type="submit"]',
                    'property_address': '//div[@class="property-address"]',
                    'amount_due': '//span[@class="amount-due"]',
                },
                'requires_javascript': True,
                'rate_limit_delay': 3.0,
            },
            'treasurer.maricopa.gov': {
                'name': 'Maricopa County',
                'search_method': 'search_form',
                'selectors': {
                    'search_input': '//input[@id="parcel-search"]',
                    'search_button': '//button[@type="submit"]',
                    'property_info': '//div[@class="property-details"]',
                    'tax_amount': '//span[contains(@class,"tax-amount")]',
                },
                'requires_javascript': True,
                'rate_limit_delay': 2.5,
            },
            'tax.aldine.k12.tx.us': {
                'name': 'Aldine ISD',
                'search_method': 'direct_link',
                'selectors': {
                    'property_info': '//div[@class="account-details"]',
                    'amount_due': '//span[contains(@class,"total-due")]',
                    'property_address': '//div[contains(@class,"address")]',
                },
                'requires_javascript': False,
                'rate_limit_delay': 2.0,
            },
        }
        
        # Load from config file if exists
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    file_config = json.load(f)
                    if 'scrapers' in file_config:
                        for domain, config in file_config['scrapers'].items():
                            if domain in default_configs:
                                default_configs[domain].update(config)
                            else:
                                default_configs[domain] = config
            except Exception as e:
                logger.warning(f"Could not load scraper configs: {e}")
        
        # Create ScraperConfig objects
        for domain, config in default_configs.items():
            configs[domain] = ScraperConfig(domain=domain, **config)
        
        return configs
    
    def _setup_directories(self):
        """Create necessary directories"""
        directories = [
            self.system_config.output_dir,
            os.path.join(self.system_config.output_dir, 'screenshots'),
            os.path.join(self.system_config.output_dir, 'html'),
            os.path.join(self.system_config.output_dir, 'logs'),
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def get_scraper_config(self, domain: str) -> Optional[ScraperConfig]:
        """Get configuration for a specific scraper"""
        return self.scraper_configs.get(domain)
    
    def add_scraper_config(self, domain: str, config: Dict[str, Any]):
        """Add or update a scraper configuration"""
        self.scraper_configs[domain] = ScraperConfig(domain=domain, **config)
    
    def save_config(self):
        """Save current configuration to file"""
        config_data = {
            'system': asdict(self.system_config),
            'scrapers': {
                domain: asdict(config) 
                for domain, config in self.scraper_configs.items()
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        logger.info(f"Configuration saved to {self.config_file}")
    
    def validate_config(self) -> bool:
        """Validate configuration settings"""
        errors = []
        
        # Validate system config
        if self.system_config.max_workers < 1:
            errors.append("max_workers must be at least 1")
        
        if self.system_config.batch_size < 1:
            errors.append("batch_size must be at least 1")
        
        if self.system_config.min_valid_amount < 0:
            errors.append("min_valid_amount must be non-negative")
        
        if self.system_config.max_valid_amount <= self.system_config.min_valid_amount:
            errors.append("max_valid_amount must be greater than min_valid_amount")
        
        # Validate scraper configs
        for domain, config in self.scraper_configs.items():
            if config.retry_count < 0:
                errors.append(f"{domain}: retry_count must be non-negative")
            
            if config.rate_limit_delay < 0:
                errors.append(f"{domain}: rate_limit_delay must be non-negative")
        
        if errors:
            for error in errors:
                logger.error(f"Configuration error: {error}")
            return False
        
        return True

# Singleton instance
_config_manager: Optional[ConfigManager] = None

def get_config() -> ConfigManager:
    """Get the global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

def reset_config():
    """Reset the configuration manager (mainly for testing)"""
    global _config_manager
    _config_manager = None