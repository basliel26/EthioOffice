import React, { useState, useEffect } from 'react';
import {
  Users2,
  Lock,
  Unlock,
  KeyRound,
  Search,
} from 'lucide-react';
import { authApi } from '../../api/client';
import type { UserProfile } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Modal } from '../../components/ui/Modal';
import { Badge } from '../../components/ui/Badge';

export const AdminUsersPage: React.FC = () => {
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Modals
  const [selectedUser, setSelectedUser] = useState<UserProfile | null>(null);
  const [showLockModal, setShowLockModal] = useState(false);
  const [lockDuration, setLockDuration] = useState('24');
  const [lockReason, setLockReason] = useState('');
  const [showResetModal, setShowResetModal] = useState(false);
  const [newPassword, setNewPassword] = useState('');

  const loadUsers = async () => {
    setIsLoading(true);
    try {
      const data = await authApi.listUsers();
      setUsers(data);
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, []);

  const handleLockUser = async () => {
    if (!selectedUser) return;
    try {
      await authApi.lockUser(selectedUser.id, {
        lock_duration_hours: parseInt(lockDuration, 10),
        reason: lockReason.trim() || undefined,
      });
      setShowLockModal(false);
      setSelectedUser(null);
      setLockReason('');
      loadUsers();
    } catch {
      // ignore
    }
  };

  const handleUnlockUser = async (user: UserProfile) => {
    try {
      await authApi.unlockUser(user.id);
      loadUsers();
    } catch {
      // ignore
    }
  };

  const handleResetPassword = async () => {
    if (!selectedUser || !newPassword.trim()) return;
    try {
      await authApi.resetUserPassword(selectedUser.id, newPassword.trim());
      setShowResetModal(false);
      setSelectedUser(null);
      setNewPassword('');
      loadUsers();
    } catch {
      // ignore
    }
  };

  const filteredUsers = users.filter(
    (u) =>
      u.full_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.email.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-6 select-none font-sans">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-zinc-100">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900 tracking-tight">
            ሰራተኞች እና ተጠቃሚዎች (Employee Directory)
          </h1>
          <p className="text-xs text-zinc-500 mt-0.5">
            የድርጅት ሰራተኞች ዝርዝር፣ የደህንነት እገዳዎች እና የይለፍ ቃል አስተዳደር
          </p>
        </div>

        <div className="w-full sm:w-64">
          <Input
            placeholder="በስም ወይም ኢሜይል ፈልግ..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            leftIcon={<Search className="w-3.5 h-3.5" />}
          />
        </div>
      </div>

      {/* Users Table */}
      <div className="bg-white rounded-2xl shadow-xs border border-zinc-200/60 overflow-hidden">
        {isLoading ? (
          <div className="py-20 text-center text-xs text-zinc-400">ተጠቃሚዎች እየተጫኑ ነው...</div>
        ) : filteredUsers.length === 0 ? (
          <div className="py-20 text-center space-y-2">
            <Users2 className="w-8 h-8 text-zinc-300 mx-auto" />
            <p className="text-sm font-medium text-zinc-900">ምንም ሰራተኛ አልተገኘም</p>
          </div>
        ) : (
          <div className="divide-y divide-zinc-100">
            {filteredUsers.map((u) => (
              <div
                key={u.id}
                className="flex items-center justify-between p-4 hover:bg-zinc-50/70 transition-colors"
              >
                {/* Left: Avatar, Name, Email, Role */}
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-full bg-zinc-100 text-zinc-700 flex items-center justify-center font-semibold text-xs shrink-0">
                    {u.full_name?.slice(0, 1).toUpperCase()}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-zinc-900 truncate">
                        {u.full_name}
                      </span>
                      <Badge variant={u.role === 'ADMIN' ? 'default' : 'neutral'} size="sm">
                        {u.role}
                      </Badge>
                      {u.is_locked ? (
                        <Badge variant="danger" size="sm" dot>
                          የታገደ (Locked)
                        </Badge>
                      ) : (
                        <Badge variant="success" size="sm" dot>
                          ንቁ (Active)
                        </Badge>
                      )}
                    </div>
                    <p className="text-[11px] text-zinc-400 mt-0.5">{u.email}</p>
                  </div>
                </div>

                {/* Right: Security Actions */}
                <div className="flex items-center gap-2 shrink-0">
                  {u.is_locked ? (
                    <Button
                      variant="subtle"
                      size="sm"
                      leftIcon={<Unlock className="w-3.5 h-3.5" />}
                      onClick={() => handleUnlockUser(u)}
                    >
                      እገዳ አንሳ (Unlock)
                    </Button>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      leftIcon={<Lock className="w-3.5 h-3.5 text-zinc-500" />}
                      onClick={() => {
                        setSelectedUser(u);
                        setShowLockModal(true);
                      }}
                    >
                      አግድ (Lock)
                    </Button>
                  )}

                  <Button
                    variant="ghost"
                    size="sm"
                    leftIcon={<KeyRound className="w-3.5 h-3.5 text-zinc-500" />}
                    onClick={() => {
                      setSelectedUser(u);
                      setShowResetModal(true);
                    }}
                  >
                    ይለፍ ቃል ቀይር
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Lock User Modal */}
      <Modal
        isOpen={showLockModal}
        onClose={() => setShowLockModal(false)}
        title="ተጠቃሚን ማገድ (Lock Employee Account)"
        description={selectedUser ? `${selectedUser.full_name} (${selectedUser.email})` : ''}
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-zinc-600 mb-1.5">የእገዳ ቆይታ (Duration)</label>
            <select
              value={lockDuration}
              onChange={(e) => setLockDuration(e.target.value)}
              className="w-full rounded-lg bg-zinc-50 border border-zinc-200 px-3 py-2 text-xs text-zinc-900 focus:outline-none"
            >
              <option value="1">1 ሰዓት (1 hour)</option>
              <option value="24">24 ሰዓታት (24 hours)</option>
              <option value="168">7 ቀናት (7 days)</option>
              <option value="87600">ላልተወሰነ ጊዜ (Indefinite)</option>
            </select>
          </div>

          <Input
            label="የእገዳ ምክንያት (Reason)"
            placeholder="የደህንነት ምርመራ..."
            value={lockReason}
            onChange={(e) => setLockReason(e.target.value)}
          />

          <div className="flex justify-end gap-2 pt-3 border-t border-zinc-100">
            <Button variant="ghost" onClick={() => setShowLockModal(false)}>
              ተመለስ (Cancel)
            </Button>
            <Button variant="danger" onClick={handleLockUser}>
              አግድ (Confirm Lock)
            </Button>
          </div>
        </div>
      </Modal>

      {/* Reset Password Modal */}
      <Modal
        isOpen={showResetModal}
        onClose={() => setShowResetModal(false)}
        title="የይለፍ ቃል በግድ መቀየር (Force Password Reset)"
        description={selectedUser ? `${selectedUser.full_name} (${selectedUser.email})` : ''}
      >
        <div className="space-y-4">
          <Input
            label="አዲስ የይለፍ ቃል (New Password)"
            type="password"
            placeholder="ቢያንስ 8 ፊደላት እና ቁጥር"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            autoFocus
          />

          <div className="flex justify-end gap-2 pt-3 border-t border-zinc-100">
            <Button variant="ghost" onClick={() => setShowResetModal(false)}>
              ተመለስ (Cancel)
            </Button>
            <Button variant="primary" onClick={handleResetPassword}>
              ይለፍ ቃል አዘጋጅ (Reset Password)
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
