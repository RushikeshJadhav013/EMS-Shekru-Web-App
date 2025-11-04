from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Employee Management System"
    DATABASE_URL: str = "mysql+pymysql://root:root@localhost/empl"
    JWT_SECRET: str = "supersecretjwtkey"
    JWT_ALGORITHM: str = "HS256"
    OTP_EXPIRY_MINUTES: int = 5

settings = Settings()
