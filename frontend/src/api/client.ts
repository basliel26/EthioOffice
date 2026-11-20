import axios from 'axios';
import type { 
  LoginResponse, 
  UserProfile, 
  CalendarTodayResponse, 
  FileItem, 
  FileVersionSummary,
  RecentFileItem,
  EmptyTrashResponse,
  TagItem,
  NotificationListResponse,
  NotificationItem,
  LetterRecord,
  LetterDetail,
  AuditLogItem,
  AuditLedgerVerification,
  StorageAnalytics,
  EuroOfficeConfigResponse,
  ActiveCoAuthorsResponse,
  EuroOfficeSessionHistoryResponse,
  EuroOfficeHealthResponse,
  ShareResponse,
  ShareLinkResponse,
  PublicLinkMetadataResponse,
  PublicLinkAccessSession,
  SystemContext,
} from './types';

export const api = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach Authorization Bearer token if present
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('ethiooffice_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Intercept 401 Unauthorized to auto-clear session
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !error.config.url.includes('/auth/login')) {
      localStorage.removeItem('ethiooffice_token');
      localStorage.removeItem('ethiooffice_user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// -------------------------------------------------------------
// 1. Authentication & IAM API
// -------------------------------------------------------------
export const authApi = {
  login: async (email: string, password: string): Promise<LoginResponse> => {
    const res = await api.post<LoginResponse>('/auth/login', { email, password });
    localStorage.setItem('ethiooffice_token', res.data.access_token);
    localStorage.setItem('ethiooffice_user', JSON.stringify(res.data.user));
    return res.data;
  },
  getMe: async (): Promise<UserProfile> => {
    const res = await api.get<UserProfile>('/auth/me');
    return res.data;
  },
  updateProfile: async (data: { full_name?: string; phone_number?: string; avatar_url?: string }): Promise<UserProfile> => {
    const res = await api.patch<UserProfile>('/auth/profile', data);
    localStorage.setItem('ethiooffice_user', JSON.stringify(res.data));
    return res.data;
  },
  changePassword: async (data: { current_password: string; new_password: string }): Promise<{ message: string }> => {
    const res = await api.post<{ message: string }>('/auth/change-password', data);
    return res.data;
  },
  provisionTenant: async (payload: {
    organization_name: string;
    slug: string;
    tin_number?: string;
    admin_email: string;
    admin_password: string;
    admin_full_name: string;
  }): Promise<unknown> => {
    const res = await api.post('/organizations/provision', payload);
    return res.data;
  },
  listUsers: async (): Promise<UserProfile[]> => {
    const res = await api.get<UserProfile[]>('/auth/users');
    return res.data;
  },
  lockUser: async (userId: string, data?: { lock_duration_hours?: number; reason?: string }): Promise<{ message: string }> => {
    const res = await api.post<{ message: string }>(`/auth/users/${userId}/lock`, data || {});
    return res.data;
  },
  unlockUser: async (userId: string): Promise<{ message: string }> => {
    const res = await api.post<{ message: string }>(`/auth/users/${userId}/unlock`);
    return res.data;
  },
  resetUserPassword: async (userId: string, new_password: string): Promise<{ message: string }> => {
    const res = await api.post<{ message: string }>(`/auth/users/${userId}/reset-password`, { new_password });
    return res.data;
  },
  logout: () => {
    localStorage.removeItem('ethiooffice_token');
    localStorage.removeItem('ethiooffice_user');
  },
};

// -------------------------------------------------------------
// 2. Ethiopian Calendar (ባሕረ ሐሳብ) API
// -------------------------------------------------------------
export const calendarApi = {
  getToday: async (): Promise<CalendarTodayResponse> => {
    const res = await api.get<CalendarTodayResponse>('/calendar/today');
    return res.data;
  },
};

// -------------------------------------------------------------
// 3. Drive & Files API
// -------------------------------------------------------------
export const filesApi = {
  list: async (driveType: 'PERSONAL' | 'COMPANY' | 'TRASH', parentId?: string, search?: string): Promise<FileItem[]> => {
    const params = new URLSearchParams({ drive_type: driveType });
    if (parentId) params.append('parent_id', parentId);
    if (search) params.append('search', search);
    const res = await api.get<FileItem[]>(`/files?${params.toString()}`);
    return res.data;
  },
  get: async (fileId: string): Promise<FileItem> => {
    const res = await api.get<FileItem>(`/files/${fileId}`);
    return res.data;
  },
  upload: async (file: File, driveType: 'PERSONAL' | 'COMPANY' = 'PERSONAL', parentId?: string): Promise<FileItem> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('drive_type', driveType);
    if (parentId) formData.append('parent_id', parentId);
    const res = await api.post<FileItem>('/files/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
  createFolder: async (name: string, driveType: 'PERSONAL' | 'COMPANY', parentId?: string): Promise<FileItem> => {
    const res = await api.post<FileItem>('/files/folder', {
      name,
      drive_type: driveType,
      parent_id: parentId || null,
    });
    return res.data;
  },
  createDocument: async (data: {
    name?: string;
    doc_type: 'docx' | 'xlsx' | 'pptx' | 'txt';
    drive_type?: 'PERSONAL' | 'COMPANY';
    parent_id?: string;
  }): Promise<FileItem> => {
    const res = await api.post<FileItem>('/files/new-document', data);
    return res.data;
  },
  rename: async (fileId: string, new_name: string): Promise<FileItem> => {
    const res = await api.patch<FileItem>(`/files/${fileId}/rename`, { new_name });
    return res.data;
  },
  move: async (fileId: string, new_parent_id: string | null): Promise<FileItem> => {
    const res = await api.patch<FileItem>(`/files/${fileId}/move`, { new_parent_id });
    return res.data;
  },
  delete: async (fileId: string, permanent: boolean = false): Promise<unknown> => {
    const res = await api.delete(`/files/${fileId}?permanent=${permanent}`);
    return res.data;
  },
  restore: async (fileId: string): Promise<unknown> => {
    const res = await api.post(`/files/${fileId}/restore`);
    return res.data;
  },
  star: async (fileId: string): Promise<{ message: string }> => {
    const res = await api.post<{ message: string }>(`/files/${fileId}/star`);
    return res.data;
  },
  unstar: async (fileId: string): Promise<{ message: string }> => {
    const res = await api.delete<{ message: string }>(`/files/${fileId}/star`);
    return res.data;
  },
  listStarred: async (): Promise<FileItem[]> => {
    const res = await api.get<FileItem[]>('/files/starred');
    return res.data;
  },
  getRecent: async (limit: number = 20): Promise<RecentFileItem[]> => {
    const res = await api.get<RecentFileItem[]>(`/files/recent?limit=${limit}`);
    return res.data;
  },
  emptyTrash: async (): Promise<EmptyTrashResponse> => {
    const res = await api.post<EmptyTrashResponse>('/files/trash/empty');
    return res.data;
  },
  assignTags: async (fileId: string, tagIds: string[]): Promise<unknown> => {
    const res = await api.post(`/files/${fileId}/tags`, { tag_ids: tagIds });
    return res.data;
  },
  removeTag: async (fileId: string, tagId: string): Promise<unknown> => {
    const res = await api.delete(`/files/${fileId}/tags/${tagId}`);
    return res.data;
  },
  getFileTags: async (fileId: string): Promise<TagItem[]> => {
    const res = await api.get<TagItem[]>(`/files/${fileId}/tags`);
    return res.data;
  },
  getAnalytics: async (): Promise<StorageAnalytics> => {
    const res = await api.get<StorageAnalytics>('/files/analytics/summary');
    return res.data;
  },
  acquireLock: async (fileId: string, reason?: string, duration_minutes: number = 120): Promise<unknown> => {
    const res = await api.post(`/files/${fileId}/lock`, { reason, duration_minutes });
    return res.data;
  },
  releaseLock: async (fileId: string, force: boolean = false): Promise<unknown> => {
    const res = await api.post(`/files/${fileId}/unlock`, { force });
    return res.data;
  },
  downloadFile: async (fileId: string, filename: string): Promise<void> => {
    const res = await api.get(`/files/${fileId}/download`, { responseType: 'blob' });
    const url = window.URL.createObjectURL(new Blob([res.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
  listVersions: async (fileId: string): Promise<FileVersionSummary[]> => {
    const res = await api.get<FileVersionSummary[]>(`/files/${fileId}/versions`);
    return res.data;
  },
  downloadVersion: async (fileId: string, versionNumber: number, filename: string): Promise<void> => {
    const res = await api.get(`/files/${fileId}/versions/${versionNumber}/download`, { responseType: 'blob' });
    const url = window.URL.createObjectURL(new Blob([res.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', filename);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },
  revertVersion: async (fileId: string, versionNumber: number): Promise<FileItem> => {
    const res = await api.post<FileItem>(`/files/${fileId}/versions/${versionNumber}/revert`);
    return res.data;
  },
  uploadNewVersion: async (fileId: string, file: File, changeSummary?: string): Promise<FileItem> => {
    const formData = new FormData();
    formData.append('file', file);
    if (changeSummary) {
      formData.append('change_summary', changeSummary);
    }
    const res = await api.post<FileItem>(`/files/${fileId}/versions`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
};

// -------------------------------------------------------------
// 4. Tags & Taxonomy API
// -------------------------------------------------------------
export const tagsApi = {
  list: async (): Promise<TagItem[]> => {
    const res = await api.get<TagItem[]>('/tags');
    return res.data;
  },
  create: async (name: string, color: string): Promise<TagItem> => {
    const res = await api.post<TagItem>('/tags', { name, color });
    return res.data;
  },
  delete: async (tagId: string): Promise<{ message: string }> => {
    const res = await api.delete<{ message: string }>(`/tags/${tagId}`);
    return res.data;
  },
};

// -------------------------------------------------------------
// 5. In-App Notifications API
// -------------------------------------------------------------
export const notificationsApi = {
  list: async (unreadOnly: boolean = false): Promise<NotificationListResponse> => {
    const res = await api.get<NotificationListResponse>(`/notifications?unread_only=${unreadOnly}`);
    return res.data;
  },
  getUnreadCount: async (): Promise<number> => {
    const res = await api.get<{ unread_count: number }>('/notifications/unread-count');
    return res.data.unread_count;
  },
  markRead: async (id: string): Promise<NotificationItem> => {
    const res = await api.patch<NotificationItem>(`/notifications/${id}/read`);
    return res.data;
  },
  markAllRead: async (): Promise<{ message: string; updated_count: number }> => {
    const res = await api.post<{ message: string; updated_count: number }>('/notifications/mark-all-read');
    return res.data;
  },
};

// -------------------------------------------------------------
// 6. Letter Registry (የደብዳቤ መዝገብ) API
// -------------------------------------------------------------
export const lettersApi = {
  list: async (params?: {
    direction?: string;
    status?: string;
    confidentiality?: string;
    urgency?: string;
    search?: string;
  }): Promise<LetterRecord[]> => {
    const query = new URLSearchParams();
    if (params?.direction) query.append('direction', params.direction);
    if (params?.status) query.append('status', params.status);
    if (params?.confidentiality) query.append('confidentiality', params.confidentiality);
    if (params?.urgency) query.append('urgency', params.urgency);
    if (params?.search) query.append('search', params.search);
    const res = await api.get<LetterRecord[]>(`/letters?${query.toString()}`);
    return res.data;
  },
  getDetail: async (id: string): Promise<LetterDetail> => {
    const res = await api.get<LetterDetail>(`/letters/${id}`);
    return res.data;
  },
  create: async (data: {
    direction: 'INWARD' | 'OUTWARD' | 'INTERNAL_MEMO';
    subject: string;
    sender_entity: string;
    recipient_entity: string;
    reference_number?: string;
    confidentiality?: string;
    urgency?: string;
    notes?: string;
  }): Promise<LetterRecord> => {
    const res = await api.post<LetterRecord>('/letters', data);
    return res.data;
  },
  approve: async (id: string): Promise<LetterDetail> => {
    const res = await api.post<LetterDetail>(`/letters/${id}/approve`, { action: 'APPROVE' });
    return res.data;
  },
  reject: async (id: string, reason: string): Promise<LetterDetail> => {
    const res = await api.post<LetterDetail>(`/letters/${id}/approve`, { action: 'REJECT', rejection_reason: reason });
    return res.data;
  },
  route: async (id: string, data: { to_department_id: string; to_user_id?: string; action_required: string; instructions?: string }): Promise<unknown> => {
    const res = await api.post(`/letters/${id}/route`, data);
    return res.data;
  },
  attachFile: async (letterId: string, fileId: string, attachmentType: string = 'SUPPORTING_DOCUMENT', notes?: string): Promise<unknown> => {
    const res = await api.post(`/letters/${letterId}/attachments`, {
      file_id: fileId,
      attachment_type: attachmentType,
      notes,
    });
    return res.data;
  },
  deleteAttachment: async (letterId: string, attachmentId: string): Promise<{ message: string }> => {
    const res = await api.delete<{ message: string }>(`/letters/${letterId}/attachments/${attachmentId}`);
    return res.data;
  },
  archive: async (id: string): Promise<unknown> => {
    const res = await api.post(`/letters/${id}/archive`);
    return res.data;
  },
};

// -------------------------------------------------------------
// 7. Full-Text Search API
// -------------------------------------------------------------
export const searchApi = {
  unified: async (q: string, folder_id?: string | null): Promise<{ documents: FileItem[]; letters: LetterRecord[] }> => {
    let url = `/search/unified?q=${encodeURIComponent(q)}`;
    if (folder_id) {
      url += `&folder_id=${encodeURIComponent(folder_id)}`;
    }
    const res = await api.get<{ documents: FileItem[]; letters: LetterRecord[] }>(url);
    return res.data;
  },
  autocomplete: async (q: string): Promise<string[]> => {
    const res = await api.get<{ suggestions: string[] }>(`/search/suggest?q=${encodeURIComponent(q)}`);
    return res.data.suggestions;
  },
};

// -------------------------------------------------------------
// 8. Audit & Compliance API
// -------------------------------------------------------------
export const auditApi = {
  listLogs: async (params?: { action?: string; limit?: number; skip?: number }): Promise<AuditLogItem[]> => {
    const query = new URLSearchParams();
    if (params?.action) query.append('action', params.action);
    if (params?.limit) query.append('limit', String(params.limit));
    if (params?.skip) query.append('skip', String(params.skip));
    const res = await api.get<AuditLogItem[]>(`/audit/logs?${query.toString()}`);
    return res.data;
  },
  verifyLedger: async (): Promise<AuditLedgerVerification> => {
    const res = await api.get<AuditLedgerVerification>('/audit/verify');
    return res.data;
  },
};

// -------------------------------------------------------------
// 9. Euro-Office / ONLYOFFICE Collaborative Editor API
// -------------------------------------------------------------
export const wopiApi = {
  getEmbedUrl: async (fileId: string): Promise<{ file_id: string; wopi_src: string; access_token: string; iframe_url: string }> => {
    const res = await api.get<{ file_id: string; wopi_src: string; access_token: string; iframe_url: string }>(`/wopi/${fileId}/url`);
    return res.data;
  },
};

export const euroOfficeApi = {
  getHealth: async (): Promise<EuroOfficeHealthResponse> => {
    const res = await api.get<EuroOfficeHealthResponse>('/euro-office/health');
    return res.data;
  },
  getConfig: async (fileId: string, lang: string = 'en'): Promise<EuroOfficeConfigResponse> => {
    const res = await api.get<EuroOfficeConfigResponse>(`/euro-office/config/${fileId}?lang=${lang}`);
    return res.data;
  },
  getCoauthors: async (fileId: string): Promise<ActiveCoAuthorsResponse> => {
    const res = await api.get<ActiveCoAuthorsResponse>(`/euro-office/${fileId}/coauthors`);
    return res.data;
  },
  getSessions: async (fileId: string): Promise<EuroOfficeSessionHistoryResponse> => {
    const res = await api.get<EuroOfficeSessionHistoryResponse>(`/euro-office/${fileId}/sessions`);
    return res.data;
  },
  dispatchCommand: async (fileId: string, command: string, userdata?: string): Promise<{ error: number; message: string }> => {
    const res = await api.post<{ error: number; message: string }>('/euro-office/command', {
      file_id: fileId,
      command,
      userdata,
    });
    return res.data;
  },
  getTextContent: async (fileId: string): Promise<{ content: string; format: string }> => {
    const res = await api.get<{ content: string; format: string }>(`/euro-office/${fileId}/text-content`);
    return res.data;
  },
  saveText: async (fileId: string, content: string, changeSummary?: string, isAutoSave?: boolean): Promise<FileItem> => {
    const res = await api.post<FileItem>(`/euro-office/${fileId}/save-text`, {
      content,
      change_summary: changeSummary,
      is_auto_save: Boolean(isAutoSave),
    });
    return res.data;
  },
};

// -------------------------------------------------------------
// 10. Sharing & Collaboration API (Module 6)
// -------------------------------------------------------------
export const sharesApi = {
  listSharedWithMe: async (): Promise<FileItem[]> => {
    const res = await api.get<FileItem[]>('/shares/with-me');
    return res.data;
  },
  createShare: async (fileId: string, data: {
    target_user_id?: string;
    target_department_id?: string;
    permission: 'VIEWER' | 'EDITOR';
    expires_at?: string;
  }): Promise<ShareResponse> => {
    const res = await api.post<ShareResponse>(`/shares/file/${fileId}`, data);
    return res.data;
  },
  listShares: async (fileId: string): Promise<ShareResponse[]> => {
    const res = await api.get<ShareResponse[]>(`/shares/file/${fileId}`);
    return res.data;
  },
  revokeShare: async (shareId: string): Promise<{ message: string }> => {
    const res = await api.delete<{ message: string }>(`/shares/${shareId}`);
    return res.data;
  },
  createPublicLink: async (fileId: string, data: {
    access_type: 'VIEW_ONLY' | 'ALLOW_DOWNLOAD' | 'UPLOAD_DROPBOX';
    password?: string;
    expires_at?: string;
    max_downloads?: number;
  }): Promise<ShareLinkResponse> => {
    const res = await api.post<ShareLinkResponse>(`/shares/links/file/${fileId}`, data);
    return res.data;
  },
  listPublicLinks: async (fileId: string): Promise<ShareLinkResponse[]> => {
    const res = await api.get<ShareLinkResponse[]>(`/shares/links/file/${fileId}`);
    return res.data;
  },
  revokePublicLink: async (linkId: string): Promise<{ message: string }> => {
    const res = await api.delete<{ message: string }>(`/shares/links/${linkId}`);
    return res.data;
  },
};

// -------------------------------------------------------------
// 11. Public Unauthenticated Access API (Public Portals)
// -------------------------------------------------------------
export const publicApi = {
  getMetadata: async (token: string): Promise<PublicLinkMetadataResponse> => {
    const res = await api.get<PublicLinkMetadataResponse>(`/public/links/${token}`);
    return res.data;
  },
  verifyPassword: async (token: string, password: string): Promise<PublicLinkAccessSession> => {
    const res = await api.post<PublicLinkAccessSession>(`/public/links/${token}/verify`, { password });
    return res.data;
  },
  getDownloadUrl: (token: string, password?: string): string => {
    const base = `/api/v1/public/links/${token}/download`;
    return password ? `${base}?password=${encodeURIComponent(password)}` : base;
  },
  uploadToDropbox: async (token: string, file: File, password?: string): Promise<FileItem> => {
    const formData = new FormData();
    formData.append('file', file);
    if (password) formData.append('password', password);
    const res = await api.post<FileItem>(`/public/links/${token}/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },
};

// -------------------------------------------------------------
// 12. System Deployment & Topology Probe (Offline/On-Prem vs Cloud)
// -------------------------------------------------------------
export const systemApi = {
  getContext: async (): Promise<SystemContext> => {
    const res = await api.get<SystemContext>('/system/context');
    return res.data;
  },
};
