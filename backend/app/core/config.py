from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import computed_field


class Settings(BaseSettings):
    PROJECT_NAME: str = "EthioOffice API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = "ethiooffice-dev-secret-key-change-in-production-12345"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day
    LICENSE_SIGNING_KEY: str = "ethiooffice-offline-licensing-master-key-2026"

    # Deployment Topology (Hybrid: On-Premise Intranet vs Cloud SaaS)
    DEPLOYMENT_MODE: str = "ON_PREMISE"  # "ON_PREMISE" | "CLOUD_SAAS"
    ALLOW_PUBLIC_REGISTRATION: bool = False  # False for private intranet servers, True for public cloud
    ORGANIZATION_NAME: Optional[str] = "Wine Technologies"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ]
    
    # Database
    DATABASE_URL: Optional[str] = None
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "ethiooffice"

    @computed_field
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # File Storage
    STORAGE_ROOT: str = "./storage_data"
    MAX_UPLOAD_SIZE_MB: int = 500
    
    # Euro-Office / Collabora WOPI Integration
    EURO_OFFICE_URL: str = "http://localhost:9980"
    EURO_OFFICE_JWT_SECRET: str = "euro-office-secret-change-in-production"
    BACKEND_INTERNAL_URL: str = "http://host.docker.internal:8000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
