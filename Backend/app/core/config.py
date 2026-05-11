from pydantic_settings import BaseSettings
import os
from datetime import datetime
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "Employee Management System"
    # DATABASE_URL: str = "mysql+pymysql://root:root@localhost/empl"
    DATABASE_URL: str = "mysql+pymysql://staffly:staff9612@localhost/empl"
    # Keep connection usage conservative for low-memory nodes.
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "4"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "2"))
    DB_POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "1800"))
    JWT_SECRET: str = "supersecretjwtkey"
    JWT_ALGORITHM: str = "HS256"
    OTP_EXPIRY_SECONDS: int = 300

    @property
    def OTP_EXPIRY_MINUTES(self) -> float:
        """Calculate OTP expiry in minutes from seconds"""
        return self.OTP_EXPIRY_SECONDS / 60
    

    
    # Environment-based OTP settings
    ENVIRONMENT: str = os.getenv("development", "testing")  # development, testing, production
    TESTING_OTP: str = os.getenv("TESTING_OTP", "123456")  # Fixed OTP for testing
    ENABLE_EMAIL_OTP: bool = os.getenv("ENABLE_EMAIL_OTP", "false").lower() == "true"
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "")
    
    @property
    def is_development(self) -> bool:
        return self.ENVIRONMENT.lower() == "development"
    
    @property
    def is_testing(self) -> bool:
        return self.ENVIRONMENT.lower() == "testing"
    
    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"
    
    @property
    def should_use_fixed_otp(self) -> bool:
        """Use fixed OTP in development and testing environments"""
        return self.is_development or self.is_testing
    
    @property
    def should_send_email(self) -> bool:
        """Send email only in production or when explicitly enabled"""
        return self.is_production or self.ENABLE_EMAIL_OTP
    
    @property
    def OTP_EXPIRY_MINUTES(self) -> int:
        """Convert OTP expiry from seconds to minutes"""
        return self.OTP_EXPIRY_SECONDS // 60
    
    class Config:
        # Load env file based on ENVIRONMENT variable or ENV_FILE override
        # Production: ENV_FILE=.env.production python main.py
        env_file = os.getenv("ENV_FILE", ".env.testing")
        extra = "ignore"  # Ignore extra fields in env files for backward compatibility
 
def get_ist_now() -> datetime:
    """Get current datetime in IST (server is set to IST)."""
    return datetime.now()

def utc_to_ist(utc_dt: datetime) -> datetime:
    """Deprecated: project is IST-only. Returns input unchanged."""
    return utc_dt

def ist_to_utc(ist_dt: datetime) -> datetime:
    """Deprecated: project is IST-only. Returns input unchanged."""
    return ist_dt

settings = Settings()