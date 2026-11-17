import React, { useState, useEffect } from 'react';
import { 
  Users, 
  Link2, 
  Copy, 
  Check, 
  Lock, 
  Trash2, 
  Eye, 
  UploadCloud, 
  ShieldCheck, 
  AlertCircle 
} from 'lucide-react';
import { Modal } from '../ui/Modal';
import { Tabs } from '../ui/Tabs';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Badge } from '../ui/Badge';
import { sharesApi, authApi } from '../../api/client';
import type { 
  FileItem, 
  ShareResponse, 
  ShareLinkResponse, 
  UserProfile 
} from '../../api/types';

interface ShareModalProps {
  isOpen: boolean;
  onClose: () => void;
  file: FileItem | null;
}

export const ShareModal: React.FC<ShareModalProps> = ({ isOpen, onClose, file }) => {
  const [activeTab, setActiveTab] = useState<'internal' | 'public'>('internal');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  // Internal sharing state
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [selectedUserId, setSelectedUserId] = useState<string>('');
  const [permission, setPermission] = useState<'VIEWER' | 'EDITOR'>('VIEWER');
  const [internalShares, setInternalShares] = useState<ShareResponse[]>([]);

  // Public link state
  const [publicLinks, setPublicLinks] = useState<ShareLinkResponse[]>([]);
  const [linkAccessType, setLinkAccessType] = useState<'VIEW_ONLY' | 'ALLOW_DOWNLOAD' | 'UPLOAD_DROPBOX'>('ALLOW_DOWNLOAD');
  const [requirePassword, setRequirePassword] = useState(false);
  const [linkPassword, setLinkPassword] = useState('');
  const [maxDownloads, setMaxDownloads] = useState<number | undefined>(undefined);

  useEffect(() => {
    if (!isOpen || !file) return;

    setError(null);
    loadShares();
    loadUsers();
  }, [isOpen, file]);

  const loadShares = async () => {
    if (!file) return;
    setIsLoading(true);
    try {
      const [shares, links] = await Promise.all([
        sharesApi.listShares(file.id),
        sharesApi.listPublicLinks(file.id),
      ]);
      setInternalShares(shares);
      setPublicLinks(links);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'የማጋራት መረጃዎችን መጫን አልተቻለም';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const loadUsers = async () => {
    try {
      const data = await authApi.listUsers();
      setUsers(data);
    } catch {
      // non-fatal
    }
  };

  const handleCreateInternalShare = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !selectedUserId) return;

    setError(null);
    setIsLoading(true);
    try {
      await sharesApi.createShare(file.id, {
        target_user_id: selectedUserId,
        permission,
      });
      setSelectedUserId('');
      await loadShares();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'ማጋራት አልተሳካም';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRevokeInternalShare = async (shareId: string) => {
    if (!file) return;
    try {
      await sharesApi.revokeShare(shareId);
      setInternalShares((prev) => prev.filter((s) => s.id !== shareId));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'ፍቃድ ማንሳት አልተቻለም';
      setError(msg);
    }
  };

  const handleCreatePublicLink = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setError(null);
    setIsLoading(true);
    try {
      await sharesApi.createPublicLink(file.id, {
        access_type: linkAccessType,
        password: requirePassword && linkPassword.trim() ? linkPassword.trim() : undefined,
        max_downloads: maxDownloads ? Number(maxDownloads) : undefined,
      });
      setLinkPassword('');
      setRequirePassword(false);
      setMaxDownloads(undefined);
      await loadShares();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'የውጭ አገናኝ መፍጠር አልተቻለም';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRevokePublicLink = async (linkId: string) => {
    try {
      await sharesApi.revokePublicLink(linkId);
      setPublicLinks((prev) => prev.filter((l) => l.id !== linkId));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'አገናኝ ማንሳት አልተቻለም';
      setError(msg);
    }
  };

  const handleCopyLink = (token: string, accessType: string) => {
    const origin = window.location.origin;
    const path = accessType === 'UPLOAD_DROPBOX' ? `/dropbox/${token}` : `/share/${token}`;
    const fullUrl = `${origin}${path}`;
    navigator.clipboard.writeText(fullUrl);
    setCopiedToken(token);
    setTimeout(() => setCopiedToken(null), 2500);
  };

  if (!file) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`ሰነድ አጋራ (Share): ${file.name}`}
      maxWidth="xl"
    >
      <div className="space-y-5">
        {/* Tab Selector */}
        <Tabs
          activeId={activeTab}
          onChange={(id) => setActiveTab(id as 'internal' | 'public')}
          items={[
            {
              id: 'internal',
              label: 'የውስጥ ሰራተኞች (Internal Colleagues)',
              icon: <Users className="w-3.5 h-3.5" />,
              count: internalShares.length,
            },
            {
              id: 'public',
              label: 'የውጭ አገናኝ (Public Link)',
              icon: <Link2 className="w-3.5 h-3.5" />,
              count: publicLinks.length,
            },
          ]}
        />

        {error && (
          <div className="flex items-center gap-2 p-3 bg-red-50 text-red-700 text-xs rounded-lg">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Tab 1: Internal Users Sharing */}
        {activeTab === 'internal' && (
          <div className="space-y-5">
            <form onSubmit={handleCreateInternalShare} className="space-y-3 p-3.5 bg-zinc-50/70 rounded-xl">
              <label className="block text-xs font-medium text-zinc-700">
                ሰራተኛ ይምረጡ (Select Colleague)
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <select
                  value={selectedUserId}
                  onChange={(e) => setSelectedUserId(e.target.value)}
                  className="sm:col-span-2 text-xs bg-white px-3 py-2 border border-zinc-200/80 rounded-lg text-zinc-800 focus:outline-none focus:ring-1 focus:ring-zinc-400"
                  required
                >
                  <option value="">ሰራተኛ ይምረጡ...</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name} ({u.email}) - {u.role}
                    </option>
                  ))}
                </select>

                <select
                  value={permission}
                  onChange={(e) => setPermission(e.target.value as 'VIEWER' | 'EDITOR')}
                  className="text-xs bg-white px-3 py-2 border border-zinc-200/80 rounded-lg text-zinc-800 focus:outline-none focus:ring-1 focus:ring-zinc-400"
                >
                  <option value="VIEWER">ማየት ብቻ (Viewer)</option>
                  <option value="EDITOR">ማስተካከል (Editor)</option>
                </select>
              </div>

              <div className="flex justify-end pt-1">
                <Button
                  type="submit"
                  size="sm"
                  variant="primary"
                  isLoading={isLoading}
                  disabled={!selectedUserId}
                  leftIcon={<Users className="w-3.5 h-3.5" />}
                >
                  አጋራ (Grant Access)
                </Button>
              </div>
            </form>

            {/* List of active internal shares */}
            <div className="space-y-2">
              <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
                የተጋሩ ሰራተኞች (Shared Colleagues)
              </h4>

              {internalShares.length === 0 ? (
                <p className="text-xs text-zinc-400 py-3 text-center">
                  ይህ ሰነድ እስካሁን ለማንም አልተጋራም (No active internal shares)
                </p>
              ) : (
                <div className="divide-y divide-zinc-100 rounded-lg border border-zinc-100">
                  {internalShares.map((s) => (
                    <div key={s.id} className="flex items-center justify-between p-3 text-xs">
                      <div className="flex items-center gap-2.5">
                        <div className="w-7 h-7 rounded-full bg-zinc-100 flex items-center justify-center font-medium text-zinc-600 text-xs">
                          {(s.target_user_name || 'U').charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <p className="font-medium text-zinc-800">
                            {s.target_user_name || s.target_department_name || 'Unknown'}
                          </p>
                          <p className="text-[10px] text-zinc-400">
                            የተጋራው በ: {s.shared_by_name}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <Badge variant={s.permission === 'EDITOR' ? 'success' : 'neutral'}>
                          {s.permission === 'EDITOR' ? 'አዘጋጅ (Editor)' : 'ተመልካች (Viewer)'}
                        </Badge>
                        <button
                          type="button"
                          onClick={() => handleRevokeInternalShare(s.id)}
                          className="p-1 text-zinc-400 hover:text-red-600 rounded transition-colors"
                          title="ፍቃድ አንሳ (Revoke)"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Tab 2: Public Links Sharing */}
        {activeTab === 'public' && (
          <div className="space-y-5">
            <form onSubmit={handleCreatePublicLink} className="space-y-3.5 p-3.5 bg-zinc-50/70 rounded-xl">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => setLinkAccessType('ALLOW_DOWNLOAD')}
                  className={`p-2.5 text-left rounded-lg text-xs transition-all border ${
                    linkAccessType === 'ALLOW_DOWNLOAD'
                      ? 'bg-white border-zinc-900 shadow-xs text-zinc-900'
                      : 'bg-white/50 border-zinc-200/70 text-zinc-600 hover:bg-white'
                  }`}
                >
                  <div className="flex items-center gap-1.5 font-medium mb-1">
                    <Eye className="w-3.5 h-3.5" />
                    <span>አውርድ (Download)</span>
                  </div>
                  <p className="text-[10px] text-zinc-400">ማውረድና ማየት ይፈቀዳል</p>
                </button>

                <button
                  type="button"
                  onClick={() => setLinkAccessType('VIEW_ONLY')}
                  className={`p-2.5 text-left rounded-lg text-xs transition-all border ${
                    linkAccessType === 'VIEW_ONLY'
                      ? 'bg-white border-zinc-900 shadow-xs text-zinc-900'
                      : 'bg-white/50 border-zinc-200/70 text-zinc-600 hover:bg-white'
                  }`}
                >
                  <div className="flex items-center gap-1.5 font-medium mb-1">
                    <ShieldCheck className="w-3.5 h-3.5" />
                    <span>ማየት ብቻ (View Only)</span>
                  </div>
                  <p className="text-[10px] text-zinc-400">ያለ ማውረድ መብት ብቻ</p>
                </button>

                <button
                  type="button"
                  onClick={() => setLinkAccessType('UPLOAD_DROPBOX')}
                  className={`p-2.5 text-left rounded-lg text-xs transition-all border ${
                    linkAccessType === 'UPLOAD_DROPBOX'
                      ? 'bg-white border-zinc-900 shadow-xs text-zinc-900'
                      : 'bg-white/50 border-zinc-200/70 text-zinc-600 hover:bg-white'
                  }`}
                >
                  <div className="flex items-center gap-1.5 font-medium mb-1">
                    <UploadCloud className="w-3.5 h-3.5" />
                    <span>ድሮፕ ቦክስ (Dropbox)</span>
                  </div>
                  <p className="text-[10px] text-zinc-400">ፋይሎችን እንዲያስቀምጡ</p>
                </button>
              </div>

              {/* Password & Security options */}
              <div className="space-y-2 pt-1 border-t border-zinc-200/50">
                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2 text-xs text-zinc-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={requirePassword}
                      onChange={(e) => setRequirePassword(e.target.checked)}
                      className="rounded text-zinc-900 focus:ring-zinc-500 w-3.5 h-3.5"
                    />
                    <span>በይለፍ ቃል ጠብቅ (Require Password)</span>
                  </label>
                </div>

                {requirePassword && (
                  <div className="pt-1">
                    <Input
                      type="password"
                      placeholder="የይለፍ ቃል (Password)..."
                      value={linkPassword}
                      onChange={(e) => setLinkPassword(e.target.value)}
                      leftIcon={<Lock className="w-3.5 h-3.5" />}
                      required={requirePassword}
                    />
                  </div>
                )}
              </div>

              <div className="flex justify-end pt-1">
                <Button
                  type="submit"
                  size="sm"
                  variant="primary"
                  isLoading={isLoading}
                  leftIcon={<Link2 className="w-3.5 h-3.5" />}
                >
                  አገናኝ ፍጠር (Generate Public Link)
                </Button>
              </div>
            </form>

            {/* List of active public links */}
            <div className="space-y-2">
              <h4 className="text-xs font-medium text-zinc-500 uppercase tracking-wider">
                ንቁ የውጭ አገናኞች (Active Public Links)
              </h4>

              {publicLinks.length === 0 ? (
                <p className="text-xs text-zinc-400 py-3 text-center">
                  ምንም ንቁ የውጭ አገናኝ የለም (No active public links)
                </p>
              ) : (
                <div className="divide-y divide-zinc-100 rounded-lg border border-zinc-100">
                  {publicLinks.map((link) => (
                    <div key={link.id} className="p-3 text-xs flex items-center justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant="neutral">
                            {link.access_type === 'UPLOAD_DROPBOX' ? 'ድሮፕ ቦክስ (Dropbox)' : link.access_type}
                          </Badge>
                          {link.is_password_protected && (
                            <span className="inline-flex items-center gap-1 text-[10px] text-amber-700 bg-amber-50 px-1.5 py-0.2 rounded">
                              <Lock className="w-2.5 h-2.5" />
                              የይለፍ ቃል አለው
                            </span>
                          )}
                          <span className="text-[10px] text-zinc-400">
                            የወረደበት ብዛት: {link.download_count}
                          </span>
                        </div>
                        <p className="text-[11px] font-mono text-zinc-500 truncate">
                          /share/{link.token}
                        </p>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => handleCopyLink(link.token, link.access_type)}
                          leftIcon={
                            copiedToken === link.token ? (
                              <Check className="w-3.5 h-3.5 text-emerald-600" />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )
                          }
                        >
                          {copiedToken === link.token ? 'ተቀድቷል' : 'ቅዳ (Copy)'}
                        </Button>

                        <button
                          type="button"
                          onClick={() => handleRevokePublicLink(link.id)}
                          className="p-1.5 text-zinc-400 hover:text-red-600 rounded transition-colors"
                          title="አገናኝ አንሳ (Revoke Link)"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        <div className="flex justify-end pt-2 border-t border-zinc-100">
          <Button variant="ghost" size="sm" onClick={onClose}>
            ዝጋ (Done)
          </Button>
        </div>
      </div>
    </Modal>
  );
};
