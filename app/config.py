from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080  # 7 days

    business_name: str = "My Electrical Services"
    business_abn: str = ""
    business_phone: str = ""
    business_email: str = ""
    business_address: str = ""

    # SMTP — leave smtp_host empty to disable email (PDF download still works)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_ssl: bool = False

    # Public URL of this API (used in approve/decline links in emails)
    public_url: str = "http://localhost:8765"

    class Config:
        env_file = ".env"


settings = Settings()
