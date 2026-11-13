export interface OrganizationSummary {
  id: string;
  name: string;
  slug: string;
  tin_number?: string;
  logo_url?: string;
  theme_color: string;
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
  role: 'SUPER_ADMIN' | 'ADMIN' | 'MANAGER' | 'STAFF';
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
  lock_info?: {
    locked_by_name: string;
    locked_by_id: string;
    reason?: string;
    expires_at: string;
  };
  created_at: string;
  updated_at: string;
  ec_created_at?: string;
}

export interface LetterRecord {
  id: string;
  reference_number: string;
  direction: 'INWARD' | 'OUTWARD';
  status: 'DRAFT' | 'PENDING_APPROVAL' | 'APPROVED' | 'DISPATCHED' | 'RECEIVED' | 'ARCHIVED';
  subject: string;
  sender_entity: string;
  recipient_entity: string;
  date_ec: string;
  date_gc: string;
  attachment_file_id?: string;
  notes?: string;
  created_at: string;
}
