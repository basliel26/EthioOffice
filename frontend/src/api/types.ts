export interface SystemContext {
  deployment_mode: 'ON_PREMISE' | 'CLOUD_SAAS';
  organization_name?: string;
  organization_slug?: string;
  allow_public_registration: boolean;
  system_name: string;
}

export interface OrganizationSummary {
  id: string;
  name: string;
  slug: string;
  tin_number?: string;
  logo_url?: string;
  theme_color: string;
  license_tier?: string;
  license_status?: string;
  days_remaining?: number;
  is_grace_period?: boolean;
  license_warning?: string;
}

export interface DepartmentSummary {
  id: string;
  name: string;
  code: string;
  is_lead: boolean;
}

export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  phone_number?: string;
  role: 'SUPER_ADMIN' | 'ADMIN' | 'MANAGER' | 'STAFF';
  is_active: boolean;
  is_locked: boolean;
  avatar_url?: string;
  organization: OrganizationSummary;
  departments: DepartmentSummary[];
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserProfile;
}

export interface EthiopianDateInfo {
  year: number;
  month: number;
  day: number;
  formatted_amharic: string;
  formatted_english: string;
}

export interface FiscalYearInfo {
  label: string;
  start_date: string;
  end_date: string;
}

export interface CalendarTodayResponse {
  gregorian_date: string;
  ethiopian_date: EthiopianDateInfo;
  fiscal_year: FiscalYearInfo;
}

export interface TagItem {
  id: string;
  organization_id: string;
  name: string;
  color: string;
  file_count: number;
  created_at: string;
}

export interface FileItem {
  id: string;
  name: string;
  is_folder: boolean;
  parent_id?: string;
  drive_type: 'PERSONAL' | 'COMPANY';
  mime_type?: string;
  size_bytes: number;
  owner_id: string;
  owner_name?: string;
  department_id?: string;
  is_deleted: boolean;
  is_locked: boolean;
  is_starred: boolean;
  tags: string[];
  lock_info?: {
    locked_by_name: string;
    locked_by_id: string;
    reason?: string;
    expires_at: string;
  };
  subfolder_count?: number;
  file_count?: number;
  created_at: string;
  updated_at: string;
  ec_created_at?: string;
}

export interface FileVersionSummary {
  id: string;
  version_number: number;
  size_bytes: number;
  checksum_sha256: string;
  change_summary?: string;
  created_by_name?: string;
  created_at: string;
  ec_created_at?: string;
}

export interface RecentFileItem {
  file: FileItem;
  last_action: string;
  last_action_amharic: string;
  last_action_at: string;
  last_action_at_ec?: string;
}

export interface EmptyTrashResponse {
  purged_count: number;
  freed_bytes: number;
  freed_mb: number;
}

export interface NotificationItem {
  id: string;
  event_type: string;
  title: string;
  title_amharic: string;
  message: string;
  message_amharic: string;
  link?: string;
  is_read: boolean;
  read_at?: string;
  actor_name?: string;
  created_at: string;
  ec_created_at?: string;
}

export interface NotificationListResponse {
  total: number;
  unread_count: number;
  items: NotificationItem[];
}

export interface LetterAttachment {
  id: string;
  letter_id: string;
  file_id: string;
  file_name: string;
  mime_type?: string;
  size_bytes: number;
  attachment_type: 'PRIMARY_SIGNED_PDF' | 'SUPPORTING_DOCUMENT' | 'ANNEX';
  notes?: string;
  attached_by_name?: string;
  created_at: string;
  ec_created_at?: string;
}

export interface LetterRoutingItem {
  id: string;
  letter_id: string;
  from_user_id: string;
  from_user_name?: string;
  from_department_id?: string;
  from_department_name?: string;
  to_user_id?: string;
  to_user_name?: string;
  to_department_id: string;
  to_department_name?: string;
  transferred_at: string;
  action_required: 'FOR_ACTION' | 'FOR_INFORMATION' | 'FOR_APPROVAL' | 'FOR_COMMENT' | 'FOR_FILING';
  priority: 'NORMAL' | 'URGENT' | 'VERY_URGENT';
  instructions?: string;
  status: 'PENDING' | 'ACKNOWLEDGED' | 'IN_PROGRESS' | 'COMPLETED' | 'REJECTED';
  acknowledged_at?: string;
  completed_at?: string;
  response_notes?: string;
}

export interface LetterRecord {
  id: string;
  organization_id: string;
  department_id?: string;
  department_name?: string;
  reference_number: string;
  external_reference_number?: string;
  direction: 'INWARD' | 'OUTWARD' | 'INTERNAL_MEMO';
  status: 'DRAFT' | 'PENDING_APPROVAL' | 'APPROVED' | 'DISPATCHED' | 'RECEIVED' | 'ARCHIVED';
  confidentiality: 'NORMAL' | 'CONFIDENTIAL' | 'STRICTLY_CONFIDENTIAL';
  urgency: 'NORMAL' | 'URGENT' | 'VERY_URGENT';
  delivery_method?: 'HAND_DELIVERY' | 'POSTAL' | 'COURIER' | 'ELECTRONIC_EMAIL' | 'INTERNAL_DISPATCH' | string;
  subject: string;
  sender_entity: string;
  sender_contact?: string;
  recipient_entity: string;
  recipient_contact?: string;
  cc_entities?: string[];
  date_ec: string;
  date_gc: string;
  ethiopian_year?: number;
  due_date_gc?: string;
  due_date_ec?: string;
  is_overdue: boolean;
  days_remaining?: number;
  approved_at_gc?: string;
  approved_by_id?: string;
  rejected_at_gc?: string;
  rejected_by_id?: string;
  rejection_reason?: string;
  dispatched_at_gc?: string;
  dispatched_at_ec?: string;
  dispatched_by_id?: string;
  attachment_file_id?: string;
  attachment_filename?: string;
  reply_to_letter_id?: string;
  notes?: string;
  created_by_id?: string;
  assigned_to_id?: string;
  created_at: string;
  updated_at: string;
}

export interface LetterDetail extends LetterRecord {
  routings: LetterRoutingItem[];
  attachments: LetterAttachment[];
  reply_count: number;
}

export interface LetterAnalyticsSummary {
  total_letters: number;
  inward_count: number;
  outward_count: number;
  memo_count: number;
  pending_approval_count: number;
  dispatched_count: number;
  received_count: number;
  archived_count: number;
  urgent_open_count: number;
  overdue_sla_count: number;
  confidential_count: number;
  by_department: Record<string, number>;
  by_urgency: Record<string, number>;
}

export interface DepartmentItem {
  id: string;
  name: string;
  code: string;
  description?: string;
  parent_id?: string;
  member_count: number;
  subdepartment_count: number;
  storage_quota_bytes?: number;
  used_storage_bytes: number;
  storage_quota_gb?: number;
}

export interface AuditLogItem {
  id: number;
  action: string;
  target_type: string;
  target_id?: string;
  target_name?: string;
  user_id?: string;
  user_name?: string;
  client_ip?: string;
  details?: Record<string, unknown>;
  created_at: string;
  ec_created_at?: string;
  entry_hash?: string;
  prev_hash?: string;
}

export interface AuditLedgerVerification {
  is_valid: boolean;
  total_records: number;
  verified_records: number;
  genesis_hash?: string;
  latest_hash?: string;
  discrepancy_details?: string;
}

export interface StorageAnalytics {
  total_used_bytes: number;
  storage_limit_bytes: number;
  percentage_used: number;
  personal_drive_bytes: number;
  company_drive_bytes: number;
  trash_bytes: number;
  total_files: number;
  total_folders: number;
}

export interface PublicShareItem {
  id: string;
  file_id: string;
  file_name: string;
  is_folder: boolean;
  token: string;
  access_type: 'VIEW_ONLY' | 'DOWNLOAD' | 'DROPBOX';
  is_password_protected: boolean;
  expires_at?: string;
  max_downloads?: number;
  download_count: number;
  is_active: boolean;
  created_at: string;
  ec_created_at?: string;
  public_url: string;
}

// -------------------------------------------------------------
// Module 7: Euro-Office / ONLYOFFICE Integration Types
// -------------------------------------------------------------
export interface DocumentPermissions {
  edit: boolean;
  download: boolean;
  print: boolean;
  review: boolean;
  comment: boolean;
}

export interface DocumentUser {
  id: string;
  name: string;
}

export interface DocumentObject {
  fileType: string;
  key: string;
  title: string;
  url: string;
  permissions: DocumentPermissions;
}

export interface EditorCustomization {
  autosave: boolean;
  forcesave: boolean;
  chat: boolean;
  comments: boolean;
  customer?: Record<string, string>;
  defaultFont: string;
  font?: Record<string, unknown>;
  uiTheme: string;
}

export interface EditorConfig {
  mode: 'view' | 'edit';
  lang: string;
  callbackUrl: string;
  user: DocumentUser;
  customization: EditorCustomization;
}

export interface EuroOfficeConfigResponse {
  documentType: 'word' | 'cell' | 'slide';
  document: DocumentObject;
  editorConfig: EditorConfig;
  token: string;
  server_url?: string;
}

export interface CoAuthorItem {
  user_id: string;
  full_name: string;
  email: string;
  role: string;
  is_current_user: boolean;
}

export interface ActiveCoAuthorsResponse {
  file_id: string;
  document_key: string;
  is_editing: boolean;
  coauthor_count: number;
  coauthors: CoAuthorItem[];
}

export interface EuroOfficeSessionItem {
  id: string;
  document_key: string;
  file_id: string;
  active_user_count: number;
  is_editing: boolean;
  last_saved_at?: string;
  created_at: string;
  ec_created_at?: string;
}

export interface EuroOfficeSessionHistoryResponse {
  file_id: string;
  total_sessions: number;
  sessions: EuroOfficeSessionItem[];
}

export interface EuroOfficeHealthResponse {
  status: 'UP' | 'DEGRADED' | 'UNCONFIGURED';
  document_server_url: string;
  jwt_enabled: boolean;
  supported_formats: string[];
  default_ethiopian_font: string;
}

// -------------------------------------------------------------
// Module 6: Internal Shares & Public Links Types
// -------------------------------------------------------------
export interface ShareResponse {
  id: string;
  file_id: string;
  file_name: string;
  is_folder: boolean;
  shared_by_id: string;
  shared_by_name: string;
  target_user_id?: string;
  target_user_name?: string;
  target_department_id?: string;
  target_department_name?: string;
  permission: 'VIEWER' | 'EDITOR';
  expires_at?: string;
  created_at: string;
  ec_created_at?: string;
}

export interface ShareLinkResponse {
  id: string;
  file_id: string;
  file_name: string;
  is_folder: boolean;
  token: string;
  access_type: 'VIEW_ONLY' | 'ALLOW_DOWNLOAD' | 'UPLOAD_DROPBOX';
  is_password_protected: boolean;
  expires_at?: string;
  max_downloads?: number;
  download_count: number;
  is_active: boolean;
  created_at: string;
  ec_created_at?: string;
  public_url?: string;
}

export interface PublicLinkMetadataResponse {
  token: string;
  file_name: string;
  is_folder: boolean;
  size_bytes: number;
  mime_type?: string;
  access_type: 'VIEW_ONLY' | 'ALLOW_DOWNLOAD' | 'UPLOAD_DROPBOX';
  is_password_protected: boolean;
  expires_at?: string;
  created_at: string;
  ec_created_at?: string;
}

export interface PublicLinkAccessSession {
  token: string;
  access_granted: boolean;
  message: string;
}
