from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "Employee Management System"
    DATABASE_URL: str = "mysql+pymysql://root:root@localhost/empl"
    #DATABASE_URL: str = "mysql+pymysql://staffly:staff9612@localhost/empl"
    JWT_SECRET: str = "supersecretjwtkey"
    JWT_ALGORITHM: str = "HS256"
    OTP_EXPIRY_SECONDS: int = 30
    
    @property
    def OTP_EXPIRY_MINUTES(self) -> float:
        """Calculate OTP expiry in minutes from seconds"""
        return self.OTP_EXPIRY_SECONDS / 60
    
    # Environment-based OTP settings
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")  # development, testing, production
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

settings = Settings()
