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
  const [maxDownloads] = useState<number | undefined>(undefined);

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
      const msg = err instanceof Error ? err.message : 'Failed to load share settings';
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
      const msg = err instanceof Error ? err.message : 'Failed to create internal share';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRevokeInternalShare = async (shareId: string) => {
    if (!file) return;
    try {
      await sharesApi.revokeShare(shareId);
      await loadShares();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to revoke access';
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
        password: requirePassword && linkPassword ? linkPassword : undefined,
        max_downloads: maxDownloads,
      });
      setLinkPassword('');
      setRequirePassword(false);
      await loadShares();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create public link';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRevokePublicLink = async (linkId: string) => {
    if (!file) return;
    try {
      await sharesApi.revokePublicLink(linkId);
      await loadShares();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to revoke public link';
      setError(msg);
    }
  };

  const handleCopyLink = (token: string, accessType: string) => {
    const origin = window.location.origin;
    const url = accessType === 'UPLOAD_DROPBOX' 
      ? `${origin}/dropbox/${token}` 
      : `${origin}/share/${token}`;
    
    navigator.clipboard.writeText(url);
    setCopiedToken(token);
    setTimeout(() => setCopiedToken(null), 2500);
  };

  if (!file) return null;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Share: ${file.name}`}
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
              label: 'Internal Colleagues',
              icon: <Users className="w-3.5 h-3.5" />,
              count: internalShares.length,
            },
            {
              id: 'public',
              label: 'Public Link',
              icon: <Link2 className="w-3.5 h-3.5" />,
              count: publicLinks.length,
            },
          ]}
        />

        {error && (
          <div className="flex items-center gap-2 p-3 bg-red-50 text-red-700 text-xs rounded-xl border border-red-200">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Tab 1: Internal Users Sharing */}
        {activeTab === 'internal' && (
          <div className="space-y-5">
            <form onSubmit={handleCreateInternalShare} className="space-y-3 p-3.5 bg-slate-50 border border-slate-200/80 rounded-xl">
              <label className="block text-xs font-bold text-slate-700">
                Select Colleague
              </label>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <select
                  value={selectedUserId}
                  onChange={(e) => setSelectedUserId(e.target.value)}
                  className="sm:col-span-2 text-xs bg-white px-3 py-2 border border-slate-200/80 rounded-lg text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-300"
                  required
                >
                  <option value="">Select colleague...</option>
                  {users.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.full_name} ({u.email}) - {u.role}
                    </option>
                  ))}
                </select>

                <select
                  value={permission}
                  onChange={(e) => setPermission(e.target.value as 'VIEWER' | 'EDITOR')}
                  className="text-xs bg-white px-3 py-2 border border-slate-200/80 rounded-lg text-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-300 font-medium"
                >
                  <option value="VIEWER">Viewer</option>
                  <option value="EDITOR">Editor</option>
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
                  Grant Access
                </Button>
              </div>
            </form>

            {/* List of active internal shares */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                Shared Colleagues
              </h4>

              {internalShares.length === 0 ? (
                <p className="text-xs text-slate-400 py-4 text-center">
                  This item is not shared with any colleagues yet.
                </p>
              ) : (
                <div className="divide-y divide-slate-100 rounded-xl border border-slate-200/80 overflow-hidden bg-white">
                  {internalShares.map((s) => (
                    <div key={s.id} className="flex items-center justify-between p-3 text-xs">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-full bg-blue-50 text-blue-700 flex items-center justify-center font-bold text-xs border border-blue-100">
                          {(s.target_user_name || 'U').charAt(0).toUpperCase()}
                        </div>
                        <div>
                          <p className="font-bold text-slate-900">
                            {s.target_user_name || s.target_department_name || 'Unknown'}
                          </p>
                          <p className="text-[10px] text-slate-400">
                            Shared by {s.shared_by_name}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2">
                        <Badge variant={s.permission === 'EDITOR' ? 'success' : 'neutral'}>
                          {s.permission === 'EDITOR' ? 'Editor' : 'Viewer'}
                        </Badge>
                        <button
                          type="button"
                          onClick={() => handleRevokeInternalShare(s.id)}
                          className="p-1.5 text-slate-400 hover:text-red-600 rounded-lg hover:bg-slate-100 transition-colors"
                          title="Revoke access"
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
            <form onSubmit={handleCreatePublicLink} className="space-y-3.5 p-3.5 bg-slate-50 border border-slate-200/80 rounded-xl">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => setLinkAccessType('ALLOW_DOWNLOAD')}
                  className={`p-2.5 text-left rounded-xl text-xs transition-all border ${
                    linkAccessType === 'ALLOW_DOWNLOAD'
                      ? 'bg-white border-blue-600 shadow-2xs text-blue-900 font-semibold'
                      : 'bg-white/60 border-slate-200/70 text-slate-600 hover:bg-white'
                  }`}
                >
                  <div className="flex items-center gap-1.5 font-bold mb-1">
                    <Eye className="w-3.5 h-3.5 text-blue-600" />
                    <span>Download</span>
                  </div>
                  <p className="text-[10px] text-slate-400 font-normal">Allow viewing and downloading</p>
                </button>

                <button
                  type="button"
                  onClick={() => setLinkAccessType('VIEW_ONLY')}
                  className={`p-2.5 text-left rounded-xl text-xs transition-all border ${
                    linkAccessType === 'VIEW_ONLY'
                      ? 'bg-white border-blue-600 shadow-2xs text-blue-900 font-semibold'
                      : 'bg-white/60 border-slate-200/70 text-slate-600 hover:bg-white'
                  }`}
                >
                  <div className="flex items-center gap-1.5 font-bold mb-1">
                    <ShieldCheck className="w-3.5 h-3.5 text-blue-600" />
                    <span>View Only</span>
                  </div>
                  <p className="text-[10px] text-slate-400 font-normal">Preview without download</p>
                </button>

                <button
                  type="button"
                  onClick={() => setLinkAccessType('UPLOAD_DROPBOX')}
                  className={`p-2.5 text-left rounded-xl text-xs transition-all border ${
                    linkAccessType === 'UPLOAD_DROPBOX'
                      ? 'bg-white border-blue-600 shadow-2xs text-blue-900 font-semibold'
                      : 'bg-white/60 border-slate-200/70 text-slate-600 hover:bg-white'
                  }`}
                >
                  <div className="flex items-center gap-1.5 font-bold mb-1">
                    <UploadCloud className="w-3.5 h-3.5 text-blue-600" />
                    <span>Dropbox</span>
                  </div>
                  <p className="text-[10px] text-slate-400 font-normal">Allow others to upload files</p>
                </button>
              </div>

              {/* Password & Security options */}
              <div className="space-y-2 pt-2 border-t border-slate-200/60">
                <div className="flex items-center justify-between">
                  <label className="flex items-center gap-2 text-xs font-semibold text-slate-700 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={requirePassword}
                      onChange={(e) => setRequirePassword(e.target.checked)}
                      className="rounded text-blue-600 focus:ring-blue-500 w-3.5 h-3.5"
                    />
                    <span>Require Password</span>
                  </label>
                </div>

                {requirePassword && (
                  <div className="pt-1">
                    <Input
                      type="password"
                      placeholder="Access password..."
                      value={linkPassword}
                      onChange={(e) => setLinkPassword(e.target.value)}
                      leftIcon={<Lock className="w-3.5 h-3.5 text-slate-400" />}
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
                  Generate Public Link
                </Button>
              </div>
            </form>

            {/* List of active public links */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                Active Public Links
              </h4>

              {publicLinks.length === 0 ? (
                <p className="text-xs text-slate-400 py-4 text-center">
                  No active public links for this item.
                </p>
              ) : (
                <div className="divide-y divide-slate-100 rounded-xl border border-slate-200/80 overflow-hidden bg-white">
                  {publicLinks.map((link) => (
                    <div key={link.id} className="p-3 text-xs flex items-center justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <Badge variant="neutral">
                            {link.access_type === 'UPLOAD_DROPBOX' ? 'Dropbox' : link.access_type}
                          </Badge>
                          {link.is_password_protected && (
                            <span className="inline-flex items-center gap-1 text-[10px] text-amber-700 bg-amber-50 px-2 py-0.5 rounded-md border border-amber-200/70 font-medium">
                              <Lock className="w-2.5 h-2.5" />
                              Password Protected
                            </span>
                          )}
                          <span className="text-[10px] text-slate-400">
                            Downloads: {link.download_count}
                          </span>
                        </div>
                        <p className="text-[11px] font-mono text-slate-500 truncate">
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
                          {copiedToken === link.token ? 'Copied!' : 'Copy Link'}
                        </Button>

                        <button
                          type="button"
                          onClick={() => handleRevokePublicLink(link.id)}
                          className="p-1.5 text-slate-400 hover:text-red-600 rounded-lg hover:bg-slate-100 transition-colors"
                          title="Revoke Link"
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

        <div className="flex justify-end pt-2 border-t border-slate-100">
          <Button variant="ghost" size="sm" onClick={onClose}>
            Done
          </Button>
        </div>
      </div>
    </Modal>
  );
};
