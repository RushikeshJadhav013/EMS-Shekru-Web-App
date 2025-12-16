from pydantic_settings import BaseSettings
import os
from datetime import datetime

class Settings(BaseSettings):
    PROJECT_NAME: str = "Employee Management System"
    DATABASE_URL: str = "mysql+pymysql://root:root@localhost/empl"
    # DATABASE_URL: str = "mysql+pymysql://staffly:staff9612@localhost/empl"
    JWT_SECRET: str = "supersecretjwtkey"
    JWT_ALGORITHM: str = "HS256"
    OTP_EXPIRY_SECONDS: int = 120
    FIREBASE_CREDENTIALS_PATH: str = "/home/ubuntu/Documents/Staffly/EMS-Shekru-Web-App/Backend/firebase_service_acc.json"

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
    
    class Config:
        # Default to testing env file; override via ENV_FILE for other modes
        env_file = os.getenv("ENV_FILE", ".env.testing")

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