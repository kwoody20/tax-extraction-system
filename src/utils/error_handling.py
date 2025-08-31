#!/usr/bin/env python3
"""
Error handling and retry logic for tax extraction system
"""

import time
import logging
import functools
from typing import Any, Callable, Optional, Type, Tuple, List
from datetime import datetime, timedelta
import traceback
from enum import Enum

logger = logging.getLogger(__name__)

class ExtractionError(Exception):
    """Base exception for extraction errors"""
    pass

class NetworkError(ExtractionError):
    """Network-related errors"""
    pass

class ParseError(ExtractionError):
    """HTML/Data parsing errors"""
    pass

class ValidationError(ExtractionError):
    """Data validation errors"""
    pass

class RateLimitError(ExtractionError):
    """Rate limiting errors"""
    pass

class AuthenticationError(ExtractionError):
    """Authentication/Authorization errors"""
    pass

class ConfigurationError(ExtractionError):
    """Configuration errors"""
    pass

class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"        # Can continue, minor issue
    MEDIUM = "medium"  # Should retry, may succeed
    HIGH = "high"      # Critical, unlikely to succeed on retry
    FATAL = "fatal"    # Cannot continue, stop processing

class ErrorHandler:
    """Centralized error handling and recovery"""
    
    def __init__(self):
        self.error_history: List[dict] = []
        self.error_counts: dict = {}
        self.last_errors: dict = {}
    
    def log_error(self, 
                  error: Exception,
                  context: dict,
                  severity: ErrorSeverity = ErrorSeverity.MEDIUM) -> dict:
        """Log an error with context"""
        error_record = {
            'timestamp': datetime.now().isoformat(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'severity': severity.value,
            'context': context,
            'traceback': traceback.format_exc()
        }
        
        self.error_history.append(error_record)
        
        # Update error counts
        error_key = f"{context.get('domain', 'unknown')}:{type(error).__name__}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        self.last_errors[error_key] = datetime.now()
        
        # Log based on severity
        if severity == ErrorSeverity.FATAL:
            logger.critical(f"Fatal error: {error_record}")
        elif severity == ErrorSeverity.HIGH:
            logger.error(f"High severity error: {error_record}")
        elif severity == ErrorSeverity.MEDIUM:
            logger.warning(f"Medium severity error: {error_record}")
        else:
            logger.info(f"Low severity error: {error_record}")
        
        return error_record
    
    def should_retry(self, error: Exception, attempt: int, max_attempts: int) -> bool:
        """Determine if an operation should be retried"""
        # Don't retry fatal errors
        if isinstance(error, (ConfigurationError, AuthenticationError)):
            return False
        
        # Don't exceed max attempts
        if attempt >= max_attempts:
            return False
        
        # Retry network and rate limit errors
        if isinstance(error, (NetworkError, RateLimitError)):
            return True
        
        # Retry parse errors only a limited number of times
        if isinstance(error, ParseError) and attempt < 2:
            return True
        
        # Default: retry on generic errors
        if isinstance(error, Exception) and attempt < max_attempts:
            return True
        
        return False
    
    def get_retry_delay(self, 
                       error: Exception, 
                       attempt: int,
                       base_delay: float = 1.0,
                       max_delay: float = 60.0) -> float:
        """Calculate retry delay with exponential backoff"""
        if isinstance(error, RateLimitError):
            # Longer delay for rate limiting
            delay = min(base_delay * (3 ** attempt), max_delay)
        else:
            # Standard exponential backoff
            delay = min(base_delay * (2 ** attempt), max_delay)
        
        # Add jitter to prevent thundering herd
        import random
        jitter = random.uniform(0, delay * 0.1)
        
        return delay + jitter
    
    def get_error_summary(self) -> dict:
        """Get summary of errors"""
        return {
            'total_errors': len(self.error_history),
            'error_counts': self.error_counts,
            'recent_errors': self.error_history[-10:] if self.error_history else [],
            'error_rate': self._calculate_error_rate()
        }
    
    def _calculate_error_rate(self) -> dict:
        """Calculate error rate over time windows"""
        now = datetime.now()
        windows = {
            '1_minute': timedelta(minutes=1),
            '5_minutes': timedelta(minutes=5),
            '1_hour': timedelta(hours=1)
        }
        
        rates = {}
        for window_name, window_delta in windows.items():
            cutoff = now - window_delta
            recent_errors = [
                e for e in self.error_history
                if datetime.fromisoformat(e['timestamp']) > cutoff
            ]
            rates[window_name] = len(recent_errors)
        
        return rates

def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
) -> Callable:
    """
    Decorator for retrying functions with exponential backoff
    
    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries
        exceptions: Tuple of exceptions to catch and retry
        on_retry: Optional callback function called on each retry
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            error_handler = ErrorHandler()
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    # Log attempt if not first
                    if attempt > 0:
                        logger.info(f"Retry attempt {attempt + 1}/{max_attempts} for {func.__name__}")
                    
                    # Call the function
                    result = func(*args, **kwargs)
                    
                    # Success - reset any error state if needed
                    if attempt > 0:
                        logger.info(f"Retry successful for {func.__name__}")
                    
                    return result
                    
                except exceptions as e:
                    last_exception = e
                    
                    # Log the error
                    context = {
                        'function': func.__name__,
                        'attempt': attempt + 1,
                        'max_attempts': max_attempts,
                        'args': str(args)[:200],  # Truncate for logging
                        'kwargs': str(kwargs)[:200]
                    }
                    
                    severity = ErrorSeverity.MEDIUM
                    if attempt == max_attempts - 1:
                        severity = ErrorSeverity.HIGH
                    
                    error_handler.log_error(e, context, severity)
                    
                    # Check if we should retry
                    if not error_handler.should_retry(e, attempt + 1, max_attempts):
                        logger.error(f"Not retrying {func.__name__} due to error type: {type(e).__name__}")
                        raise
                    
                    # If this is the last attempt, raise the exception
                    if attempt == max_attempts - 1:
                        logger.error(f"Max retries exceeded for {func.__name__}")
                        raise
                    
                    # Calculate delay
                    delay = error_handler.get_retry_delay(e, attempt, base_delay, max_delay)
                    logger.info(f"Waiting {delay:.2f} seconds before retry...")
                    
                    # Call retry callback if provided
                    if on_retry:
                        on_retry(e, attempt, delay)
                    
                    # Wait before retrying
                    time.sleep(delay)
            
            # This should not be reached, but just in case
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator

class CircuitBreaker:
    """
    Circuit breaker pattern implementation to prevent cascading failures
    """
    
    def __init__(self,
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60,
                 expected_exception: Type[Exception] = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half-open
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        if self.state == 'open':
            if self._should_attempt_reset():
                self.state = 'half-open'
                logger.info(f"Circuit breaker entering half-open state for {func.__name__}")
            else:
                raise Exception(f"Circuit breaker is open for {func.__name__}")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        
        time_since_failure = time.time() - self.last_failure_time
        return time_since_failure >= self.recovery_timeout
    
    def _on_success(self):
        """Handle successful call"""
        if self.state == 'half-open':
            logger.info("Circuit breaker reset to closed state")
        self.failure_count = 0
        self.state = 'closed'
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = 'open'
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")

def validate_response(response: dict, required_fields: List[str]) -> bool:
    """
    Validate that a response contains required fields with valid data
    
    Args:
        response: Response dictionary to validate
        required_fields: List of required field names
    
    Returns:
        bool: True if valid, raises ValidationError if not
    """
    missing_fields = []
    invalid_fields = []
    
    for field in required_fields:
        if field not in response:
            missing_fields.append(field)
        elif response[field] is None or response[field] == '':
            invalid_fields.append(field)
    
    if missing_fields:
        raise ValidationError(f"Missing required fields: {missing_fields}")
    
    if invalid_fields:
        raise ValidationError(f"Invalid or empty fields: {invalid_fields}")
    
    return True

def safe_extract(extractor_func: Callable, 
                 fallback_value: Any = None,
                 log_errors: bool = True) -> Any:
    """
    Safely execute an extraction function with error handling
    
    Args:
        extractor_func: Function to execute
        fallback_value: Value to return on error
        log_errors: Whether to log errors
    
    Returns:
        Extracted value or fallback value
    """
    try:
        return extractor_func()
    except Exception as e:
        if log_errors:
            logger.warning(f"Extraction failed: {e}, using fallback value: {fallback_value}")
        return fallback_value