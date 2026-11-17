import React, { useState, useEffect } from 'react';
import { Bell, Check, Clock } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { notificationsApi } from '../../api/client';
import type { NotificationItem } from '../../api/types';
import { Badge } from '../ui/Badge';

export const NotificationDropdown: React.FC = () => {
  const { unreadCount, refreshUnreadCount } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const loadNotifications = async () => {
    setIsLoading(true);
    try {
      const res = await notificationsApi.list(false);
      setNotifications(res.items);
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadNotifications();
    }
  }, [isOpen]);

  const handleMarkAsRead = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await notificationsApi.markRead(id);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      refreshUnreadCount();
    } catch {
      // ignore
    }
  };

  const handleMarkAllAsRead = async () => {
    try {
      await notificationsApi.markAllRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      refreshUnreadCount();
    } catch {
      // ignore
    }
  };

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-2 text-zinc-500 hover:text-zinc-900 rounded-lg hover:bg-zinc-100 transition-colors focus:outline-none"
        aria-label="Notifications"
      >
        <Bell className="w-4 h-4" />
        {unreadCount > 0 && (
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-red-600 ring-2 ring-white" />
        )}
      </button>

      {isOpen && (
        <>
          <div 
            className="fixed inset-0 z-40" 
            onClick={() => setIsOpen(false)} 
          />
          <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-2xl bg-white shadow-xl border border-zinc-200/70 p-4 z-50 animate-scale-up">
            <div className="flex items-center justify-between pb-3 border-b border-zinc-100">
              <div className="flex items-center gap-2">
                <h4 className="text-sm font-semibold text-zinc-900">ማሳወቂያዎች (Notifications)</h4>
                {unreadCount > 0 && (
                  <Badge variant="danger" size="sm">
                    {unreadCount}
                  </Badge>
                )}
              </div>
              {unreadCount > 0 && (
                <button
                  onClick={handleMarkAllAsRead}
                  className="text-[11px] text-zinc-500 hover:text-zinc-900 transition-colors"
                >
                  ሁሉንም አንብብ (Mark all read)
                </button>
              )}
            </div>

            <div className="divide-y divide-zinc-50 max-h-80 overflow-y-auto">
              {isLoading ? (
                <div className="py-8 text-center text-xs text-zinc-400">እየተጫነ ነው...</div>
              ) : notifications.length === 0 ? (
                <div className="py-8 text-center text-xs text-zinc-400">ምንም ማሳወቂያ የለም (No notifications)</div>
              ) : (
                notifications.slice(0, 10).map((n) => (
                  <div
                    key={n.id}
                    className={`py-3 px-1 transition-colors flex items-start justify-between gap-3 ${
                      !n.is_read ? 'bg-zinc-50/50' : ''
                    }`}
                  >
                    <div className="space-y-1 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium text-zinc-900">{n.title_amharic || n.title}</span>
                        {!n.is_read && (
                          <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                        )}
                      </div>
                      <p className="text-xs text-zinc-500 leading-relaxed">{n.message_amharic || n.message}</p>
                      <div className="flex items-center gap-2 text-[10px] text-zinc-400">
                        <Clock className="w-3 h-3" />
                        <span>{n.ec_created_at || new Date(n.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                    {!n.is_read && (
                      <button
                        onClick={(e) => handleMarkAsRead(n.id, e)}
                        className="text-zinc-400 hover:text-zinc-700 p-1 rounded-md hover:bg-zinc-200/50"
                        title="Mark as read"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
};
