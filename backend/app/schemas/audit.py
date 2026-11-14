import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict


class AuditLogItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
    user_name: Optional[str] = None
    user_email: Optional[str] = None

    action: str
    action_amharic: str
    target_type: str
    target_id: Optional[uuid.UUID] = None
    target_name: str
    details: Optional[Dict[str, Any]] = None

    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    severity: str = "INFO"
    status: str = "SUCCESS"

    prev_hash: Optional[str] = None
    entry_hash: Optional[str] = None

    created_at: datetime
    ec_created_at: Optional[str] = None


class AuditLogQueryResponse(BaseModel):
    total: int
    items: List[AuditLogItemResponse]
    limit: int
    offset: int


class AuditIntegrityResponse(BaseModel):
    is_valid: bool
    organization_id: uuid.UUID
    total_records_checked: int
    genesis_hash: Optional[str] = None
    latest_hash: Optional[str] = None
    compromised_row_id: Optional[int] = None
    error_message: Optional[str] = None
    verified_at: datetime


class AuditAnomalyItem(BaseModel):
    type: str  # "BRUTE_FORCE", "MASS_DOWNLOAD", "AFTER_HOURS_ACCESS", "PRIVILEGE_VIOLATION"
    severity: str
    description: str
    actor_id: Optional[uuid.UUID] = None
    actor_name: Optional[str] = None
    ip_address: Optional[str] = None
    count: int = 1
    timestamp: datetime
    ec_timestamp: Optional[str] = None


class AuditDashboardSummary(BaseModel):
    total_events: int
    today_events: int
    critical_events: int
    failed_events: int
    action_category_breakdown: Dict[str, int]
    top_active_users: List[Dict[str, Any]]
    recent_anomalies: List[AuditAnomalyItem]


class SystemHealthResponse(BaseModel):
    status: str
    uptime_seconds: float
    database_connected: bool
    database_pool_size: int
    database_checked_out: int
    disk_total_gb: float
    disk_used_gb: float
    disk_free_gb: float
    disk_usage_percent: float
    memory_process_mb: float
    cpu_count: int
    version: str


class AuditActionItem(BaseModel):
    action: str
    name_amharic: str
    category: str
