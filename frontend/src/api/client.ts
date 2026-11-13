import axios from 'axios';
import type { 
  LoginResponse, 
  UserProfile, 
  CalendarTodayResponse, 
  FileItem, 
  LetterRecord 
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

// API helper functions
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
  logout: () => {
    localStorage.removeItem('ethiooffice_token');
    localStorage.removeItem('ethiooffice_user');
  },
};

export const calendarApi = {
  getToday: async (): Promise<CalendarTodayResponse> => {
    const res = await api.get<CalendarTodayResponse>('/calendar/today');
    return res.data;
  },
};

export const filesApi = {
  list: async (driveType: 'PERSONAL' | 'COMPANY' | 'TRASH', parentId?: string): Promise<FileItem[]> => {
    const params = new URLSearchParams({ drive_type: driveType });
    if (parentId) params.append('parent_id', parentId);
    const res = await api.get<FileItem[]>(`/files?${params.toString()}`);
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
  delete: async (fileId: string): Promise<{ message: string }> => {
    const res = await api.delete<{ message: string }>(`/files/${fileId}`);
    return res.data;
  },
};

export const lettersApi = {
  list: async (direction?: 'INWARD' | 'OUTWARD', search?: string): Promise<LetterRecord[]> => {
    const params = new URLSearchParams();
    if (direction) params.append('direction', direction);
    if (search) params.append('search', search);
    const res = await api.get<LetterRecord[]>(`/letters?${params.toString()}`);
    return res.data;
  },
  create: async (data: {
    reference_number: string;
    direction: 'INWARD' | 'OUTWARD';
    subject: string;
    sender_entity: string;
    recipient_entity: string;
    notes?: string;
  }): Promise<LetterRecord> => {
    const res = await api.post<LetterRecord>('/letters', data);
    return res.data;
  },
};
