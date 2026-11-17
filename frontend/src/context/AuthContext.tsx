import React, { createContext, useContext, useState, useEffect } from 'react';
import { authApi, calendarApi, notificationsApi } from '../api/client';
import type { UserProfile, CalendarTodayResponse } from '../api/types';

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  isLoading: boolean;
  calendarInfo: CalendarTodayResponse | null;
  unreadCount: number;
  login: (email: string, pass: string) => Promise<UserProfile>;
  logout: () => void;
  updateUser: (updated: UserProfile) => void;
  refreshUnreadCount: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(() => {
    const saved = localStorage.getItem('ethiooffice_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('ethiooffice_token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [calendarInfo, setCalendarInfo] = useState<CalendarTodayResponse | null>(null);
  const [unreadCount, setUnreadCount] = useState<number>(0);

  const refreshUnreadCount = async () => {
    if (!token) return;
    try {
      const count = await notificationsApi.getUnreadCount();
      setUnreadCount(count);
    } catch {
      // ignore in background
    }
  };

  useEffect(() => {
    async function init() {
      try {
        if (token) {
          const profile = await authApi.getMe();
          setUser(profile);
          localStorage.setItem('ethiooffice_user', JSON.stringify(profile));
        }

        // Fetch today's Ethiopian calendar date
        try {
          const cal = await calendarApi.getToday();
          setCalendarInfo(cal);
        } catch {
          // ignore
        }

        // Fetch unread notifications
        if (token) {
          try {
            const count = await notificationsApi.getUnreadCount();
            setUnreadCount(count);
          } catch {
            // ignore
          }
        }
      } catch {
        authApi.logout();
        setUser(null);
        setToken(null);
      } finally {
        setIsLoading(false);
      }
    }
    init();
  }, [token]);

  const login = async (email: string, pass: string): Promise<UserProfile> => {
    const res = await authApi.login(email, pass);
    setUser(res.user);
    setToken(res.access_token);
    try {
      const count = await notificationsApi.getUnreadCount();
      setUnreadCount(count);
    } catch {
      // ignore
    }
    return res.user;
  };

  const logout = () => {
    authApi.logout();
    setUser(null);
    setToken(null);
  };

  const updateUser = (updated: UserProfile) => {
    setUser(updated);
    localStorage.setItem('ethiooffice_user', JSON.stringify(updated));
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        calendarInfo,
        unreadCount,
        login,
        logout,
        updateUser,
        refreshUnreadCount,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
