import React, { useState, useEffect, useCallback } from 'react';
import {
  X,
  FileText,
  Folder,
  Calendar,
  Clock,
  User,
  HardDrive,
  Lock,
  Unlock,
  History,
  Download,
  RotateCcw,
  Upload,
  Star,
  Tag,
  Copy,
  Check,
  ExternalLink,
  AlertCircle,
  FileSpreadsheet,
  Presentation,
  File as FileIcon,
  Layers,
  ChevronRight,
  Info,
} from 'lucide-react';
import { Button } from '../ui/Button';
import { Modal } from '../ui/Modal';
import { filesApi } from '../../api/client';
import type { FileItem, FileVersionSummary } from '../../api/types';

interface FileDetailsPanelProps {
  item: FileItem | null;
  currentFolder?: { id?: string | null; name: string };
  driveType: 'PERSONAL' | 'COMPANY';
  isOpen: boolean;
  onClose: () => void;
  onItemUpdated?: (updatedItem: FileItem) => void;
  onNavigateFolder?: (folder: FileItem) => void;
  onOpenEditor?: (file: FileItem) => void;
  onManageTags?: (file: FileItem) => void;
  onToggleStar?: (file: FileItem) => void;
}

export const FileDetailsPanel: React.FC<FileDetailsPanelProps> = ({
  item,
  currentFolder,
  driveType,
  isOpen,
  onClose,
  onItemUpdated,
  onNavigateFolder,
  onOpenEditor,
  onManageTags,
  onToggleStar,
}) => {
  const [activeTab, setActiveTab] = useState<'details' | 'versions'>('details');

  // Version History State
  const [versions, setVersions] = useState<FileVersionSummary[]>([]);
  const [isLoadingVersions, setIsLoadingVersions] = useState(false);
  const [versionError, setVersionError] = useState<string | null>(null);

  // Upload Revision Modal State
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [changeSummary, setChangeSummary] = useState('');
  const [isUploadingVersion, setIsUploadingVersion] = useState(false);

  // Revert Confirmation Modal State
  const [revertingVersion, setRevertingVersion] = useState<FileVersionSummary | null>(null);
  const [isReverting, setIsReverting] = useState(false);

  // Lock Modal State
  const [showLockModal, setShowLockModal] = useState(false);
  const [lockReason, setLockReason] = useState('Editing document');
  const [lockDuration, setLockDuration] = useState(120);
  const [isLocking, setIsLocking] = useState(false);
  const [isUnlocking, setIsUnlocking] = useState(false);

  // Download State
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadingVersionNum, setDownloadingVersionNum] = useState<number | null>(null);

  // Copied checksum feedback
  const [copiedChecksum, setCopiedChecksum] = useState<string | null>(null);

  // Reset tab to details when item changes or is a folder
  useEffect(() => {
    if (!item || item.is_folder) {
      setActiveTab('details');
    }
  }, [item?.id, item?.is_folder]);

  // Load versions whenever a file is selected and versions tab is viewed
  const loadVersions = useCallback(async (fileId: string) => {
    setIsLoadingVersions(true);
    setVersionError(null);
    try {
      const data = await filesApi.listVersions(fileId);
      setVersions(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load version history';
      setVersionError(msg);
    } finally {
      setIsLoadingVersions(false);
    }
  }, []);

  useEffect(() => {
    if (item && !item.is_folder) {
      loadVersions(item.id);
    } else {
      setVersions([]);
    }
  }, [item?.id, item?.is_folder, loadVersions]);

  if (!isOpen) return null;

  // Format bytes helper
  const formatBytes = (bytes: number): string => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  // Icon helper based on file extension
  const renderItemIcon = (file: FileItem, sizeClass: string = 'w-8 h-8') => {
    if (file.is_folder) {
      return <Folder className={`${sizeClass} text-blue-500 fill-blue-50`} />;
    }
    const ext = file.name.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'docx':
      case 'doc':
        return <FileText className={`${sizeClass} text-blue-600`} />;
      case 'xlsx':
      case 'xls':
      case 'csv':
        return <FileSpreadsheet className={`${sizeClass} text-emerald-600`} />;
      case 'pptx':
      case 'ppt':
        return <Presentation className={`${sizeClass} text-amber-600`} />;
      case 'pdf':
        return <FileText className={`${sizeClass} text-red-600`} />;
      case 'txt':
        return <FileText className={`${sizeClass} text-slate-600`} />;
      default:
        return <FileIcon className={`${sizeClass} text-slate-500`} />;
    }
  };

  // Determine doc type label
  const getItemTypeLabel = (file: FileItem) => {
    if (file.is_folder) return 'Folder';
    const ext = file.name.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'docx':
      case 'doc':
        return 'Microsoft Word Document (.docx)';
      case 'xlsx':
      case 'xls':
        return 'Microsoft Excel Spreadsheet (.xlsx)';
      case 'csv':
        return 'CSV Spreadsheet (.csv)';
      case 'pptx':
      case 'ppt':
        return 'Microsoft PowerPoint Presentation (.pptx)';
      case 'pdf':
        return 'PDF Document (.pdf)';
      case 'txt':
        return 'Plain Text Document (.txt)';
      default:
        return `${ext?.toUpperCase() || 'Binary'} File`;
    }
  };

  const isEditableOfficeDoc = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    return ['docx', 'xlsx', 'pptx', 'txt'].includes(ext || '');
  };

  // Download Current File Handler
  const handleDownloadCurrent = async () => {
    if (!item || item.is_folder) return;
    setIsDownloading(true);
    try {
      await filesApi.downloadFile(item.id, item.name);
    } catch {
      alert('Failed to download document. Please verify network access.');
    } finally {
      setIsDownloading(false);
    }
  };

  // Download Historical Version Handler
  const handleDownloadHistorical = async (v: FileVersionSummary) => {
    if (!item) return;
    setDownloadingVersionNum(v.version_number);
    try {
      const ext = item.name.includes('.') ? `.${item.name.split('.').pop()}` : '';
      const base = item.name.replace(/\.[^/.]+$/, '');
      const downloadName = `${base}_v${v.version_number}${ext}`;
      await filesApi.downloadVersion(item.id, v.version_number, downloadName);
    } catch {
      alert(`Failed to download Version ${v.version_number}.`);
    } finally {
      setDownloadingVersionNum(null);
    }
  };

  // Upload Revision Handler
  const handleUploadRevision = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!item || !uploadFile) return;
    setIsUploadingVersion(true);
    try {
      const updated = await filesApi.uploadNewVersion(item.id, uploadFile, changeSummary.trim() || undefined);
      setShowUploadModal(false);
      setUploadFile(null);
      setChangeSummary('');
      await loadVersions(item.id);
      if (onItemUpdated) onItemUpdated(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to upload revision';
      alert(`Upload failed: ${msg}`);
    } finally {
      setIsUploadingVersion(false);
    }
  };

  // Revert Version Handler (Module 5 Zero-storage CAS rollback)
  const handleRevertConfirm = async () => {
    if (!item || !revertingVersion) return;
    setIsReverting(true);
    try {
      const updated = await filesApi.revertVersion(item.id, revertingVersion.version_number);
      setRevertingVersion(null);
      await loadVersions(item.id);
      if (onItemUpdated) onItemUpdated(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to revert version';
      alert(`Revert failed: ${msg}`);
    } finally {
      setIsReverting(false);
    }
  };

  // Lock Document Handler
  const handleAcquireLock = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!item) return;
    setIsLocking(true);
    try {
      await filesApi.acquireLock(item.id, lockReason.trim() || undefined, lockDuration);
      setShowLockModal(false);
      const updated: FileItem = {
        ...item,
        is_locked: true,
        lock_info: {
          locked_by_name: 'You (Current User)',
          locked_by_id: item.owner_id,
          reason: lockReason.trim(),
          expires_at: new Date(Date.now() + lockDuration * 60 * 1000).toISOString(),
        },
      };
      if (onItemUpdated) onItemUpdated(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to acquire check-out lock';
      alert(`Lock failed: ${msg}`);
    } finally {
      setIsLocking(false);
    }
  };

  // Unlock Document Handler
  const handleReleaseLock = async () => {
    if (!item) return;
    setIsUnlocking(true);
    try {
      await filesApi.releaseLock(item.id);
      const updated: FileItem = {
        ...item,
        is_locked: false,
        lock_info: undefined,
      };
      if (onItemUpdated) onItemUpdated(updated);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to release lock';
      alert(`Unlock failed: ${msg}`);
    } finally {
      setIsUnlocking(false);
    }
  };

  // Copy SHA256 helper
  const handleCopyChecksum = (checksum: string) => {
    navigator.clipboard.writeText(checksum);
    setCopiedChecksum(checksum);
    setTimeout(() => setCopiedChecksum(null), 2000);
  };

  return (
    <aside
      aria-label="File details inspector"
      className="w-80 sm:w-88 lg:w-96 shrink-0 bg-white border border-slate-200/90 rounded-2xl shadow-sm flex flex-col font-sans transition-all duration-200 overflow-hidden"
    >
      {/* Panel Top Bar: Title & Close Button */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-slate-50/50">
        <div className="flex items-center gap-2">
          <Info className="w-4 h-4 text-blue-600" />
          <h3 className="text-xs font-bold text-slate-800 tracking-wide uppercase">
            Inspector & History
          </h3>
        </div>
        <button
          type="button"
          onClick={onClose}
          title="Close details panel"
          className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Tabs Switcher: Details vs Version History */}
      <div className="flex border-b border-slate-200/80 bg-white px-2">
        <button
          type="button"
          onClick={() => setActiveTab('details')}
          className={`flex-1 py-2.5 text-xs font-semibold text-center transition-all border-b-2 cursor-pointer ${
            activeTab === 'details'
              ? 'border-blue-600 text-blue-600 bg-blue-50/30'
              : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
          }`}
        >
          Details
        </button>
        {/* [HALTED: Version History feature disabled for now]
        <button
          type="button"
          onClick={() => {
            if (item && !item.is_folder) {
              setActiveTab('versions');
            }
          }}
          disabled={!item || item.is_folder}
          className={`flex-1 py-2.5 text-xs font-semibold text-center transition-all border-b-2 flex items-center justify-center gap-1.5 cursor-pointer ${
            !item || item.is_folder
              ? 'opacity-40 cursor-not-allowed border-transparent text-slate-400'
              : activeTab === 'versions'
              ? 'border-blue-600 text-blue-600 bg-blue-50/30'
              : 'border-transparent text-slate-500 hover:text-slate-800 hover:border-slate-300'
          }`}
        >
          <History className="w-3.5 h-3.5" />
          <span>Versions</span>
          {versions.length > 0 && (
            <span className="text-[10px] font-bold px-1.5 py-0.2 bg-blue-100 text-blue-700 rounded-full">
              {versions.length}
            </span>
          )}
        </button>
        */}
      </div>

      {/* Panel Body Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-5">
        {!item ? (
          /* Empty / Default State: Current Folder Overview */
          <div className="py-8 px-2 text-center space-y-4">
            <div className="w-14 h-14 mx-auto rounded-2xl bg-blue-50 border border-blue-100 flex items-center justify-center text-blue-600">
              <Folder className="w-7 h-7" />
            </div>
            <div className="space-y-1">
              <h4 className="text-sm font-bold text-slate-800">
                {currentFolder?.name || (driveType === 'COMPANY' ? 'Company Drive' : 'Personal Drive')}
              </h4>
              <p className="text-xs text-slate-400">
                {driveType === 'COMPANY' ? 'Shared Organization Partition' : 'Your Private Workspace'}
              </p>
            </div>
            <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-left space-y-2">
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <HardDrive className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="font-medium">Drive Type:</span>
                <span className="text-slate-800 font-semibold">{driveType}</span>
              </div>
              <p className="text-[11px] text-slate-400 leading-relaxed pt-1 border-t border-slate-200/60">
                Select any file or folder in the list to inspect metadata, view historical revisions, manage tags, or acquire check-out locks.
              </p>
            </div>
          </div>
        ) : activeTab === 'details' ? (
          /* =========================================================
             DETAILS TAB
             ========================================================= */
          <div className="space-y-5 animate-fade-in">
            {/* Header Card: Icon, Name & Quick Actions */}
            <div className="p-3.5 rounded-xl bg-slate-50/80 border border-slate-200/70 space-y-3">
              <div className="flex items-start gap-3">
                <div className="p-2.5 rounded-xl bg-white border border-slate-200/70 shadow-2xs shrink-0">
                  {renderItemIcon(item, 'w-6 h-6')}
                </div>
                <div className="min-w-0 flex-1">
                  <h4
                    className="text-xs font-bold text-slate-900 break-words line-clamp-2"
                    title={item.name}
                  >
                    {item.name}
                  </h4>
                  <p className="text-[11px] text-slate-500 font-medium mt-0.5">
                    {getItemTypeLabel(item)}
                  </p>
                </div>
              </div>

              {/* Quick Actions Row */}
              <div className="flex items-center gap-1.5 pt-2 border-t border-slate-200/60">
                {!item.is_folder && isEditableOfficeDoc(item.name) && onOpenEditor && (
                  <Button
                    variant="primary"
                    size="sm"
                    className="flex-1 text-[11px]"
                    leftIcon={<ExternalLink className="w-3.5 h-3.5" />}
                    onClick={() => onOpenEditor(item)}
                  >
                    Open
                  </Button>
                )}

                {item.is_folder && onNavigateFolder && (
                  <Button
                    variant="primary"
                    size="sm"
                    className="flex-1 text-[11px]"
                    leftIcon={<ChevronRight className="w-3.5 h-3.5" />}
                    onClick={() => onNavigateFolder(item)}
                  >
                    Open Folder
                  </Button>
                )}

                {!item.is_folder && (
                  <Button
                    variant="secondary"
                    size="sm"
                    className="text-[11px]"
                    isLoading={isDownloading}
                    leftIcon={<Download className="w-3.5 h-3.5" />}
                    onClick={handleDownloadCurrent}
                    title="Download current file"
                  >
                    Download
                  </Button>
                )}

                {onToggleStar && (
                  <button
                    type="button"
                    onClick={() => onToggleStar(item)}
                    title={item.is_starred ? 'Remove Star' : 'Star Document'}
                    className={`p-1.5 rounded-lg border transition-colors cursor-pointer ${
                      item.is_starred
                        ? 'border-amber-300 bg-amber-50 text-amber-500'
                        : 'border-slate-200 bg-white text-slate-400 hover:text-amber-500 hover:border-slate-300'
                    }`}
                  >
                    <Star
                      className={`w-3.5 h-3.5 ${
                        item.is_starred ? 'fill-amber-400 text-amber-400' : ''
                      }`}
                    />
                  </button>
                )}
              </div>
            </div>

            {/* Lock / Concurrency Control Card (Files only) */}
            {!item.is_folder && (
              <div className="p-3 rounded-xl border border-slate-200/80 bg-white space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {item.is_locked ? (
                      <Lock className="w-4 h-4 text-amber-600" />
                    ) : (
                      <Unlock className="w-4 h-4 text-emerald-600" />
                    )}
                    <span className="text-xs font-bold text-slate-800">
                      Concurrency Lock
                    </span>
                  </div>
                  <span
                    className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                      item.is_locked
                        ? 'bg-amber-100 text-amber-800 border border-amber-200'
                        : 'bg-emerald-100 text-emerald-800 border border-emerald-200'
                    }`}
                  >
                    {item.is_locked ? 'Locked' : 'Available'}
                  </span>
                </div>

                {item.is_locked ? (
                  <div className="space-y-2 pt-1 text-[11px] text-slate-600">
                    <p className="leading-snug">
                      <span className="font-semibold text-slate-700">Holder:</span>{' '}
                      {item.lock_info?.locked_by_name || 'Active User'}
                    </p>
                    {item.lock_info?.reason && (
                      <p className="leading-snug">
                        <span className="font-semibold text-slate-700">Reason:</span>{' '}
                        {item.lock_info.reason}
                      </p>
                    )}
                    <Button
                      variant="secondary"
                      size="sm"
                      isLoading={isUnlocking}
                      onClick={handleReleaseLock}
                      className="w-full text-xs text-amber-700 hover:bg-amber-50"
                      leftIcon={<Unlock className="w-3.5 h-3.5" />}
                    >
                      Release Lock
                    </Button>
                  </div>
                ) : (
                  <div className="pt-1">
                    <p className="text-[11px] text-slate-500 mb-2 leading-relaxed">
                      Check out this document to prevent colleagues from overwriting your modifications.
                    </p>
                    <Button
                      variant="subtle"
                      size="sm"
                      onClick={() => setShowLockModal(true)}
                      className="w-full text-xs text-slate-700 hover:bg-slate-100"
                      leftIcon={<Lock className="w-3.5 h-3.5 text-slate-600" />}
                    >
                      Check Out / Lock
                    </Button>
                  </div>
                )}
              </div>
            )}

            {/* Properties List */}
            <div className="space-y-3">
              <h5 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                File Properties
              </h5>

              <div className="divide-y divide-slate-100 border border-slate-200/80 rounded-xl bg-white overflow-hidden text-xs">
                {/* Size */}
                <div className="flex items-center justify-between p-2.5">
                  <span className="text-slate-500 flex items-center gap-2">
                    <HardDrive className="w-3.5 h-3.5 text-slate-400" />
                    Size
                  </span>
                  <span className="font-semibold text-slate-800">
                    {item.is_folder
                      ? `${item.file_count || 0} items`
                      : formatBytes(item.size_bytes)}
                  </span>
                </div>

                {/* Drive Partition */}
                <div className="flex items-center justify-between p-2.5">
                  <span className="text-slate-500 flex items-center gap-2">
                    <Layers className="w-3.5 h-3.5 text-slate-400" />
                    Partition
                  </span>
                  <span className="font-semibold text-slate-800">
                    {item.drive_type === 'COMPANY' ? 'Company Drive' : 'Personal Drive'}
                  </span>
                </div>

                {/* Owner */}
                <div className="flex items-center justify-between p-2.5">
                  <span className="text-slate-500 flex items-center gap-2">
                    <User className="w-3.5 h-3.5 text-slate-400" />
                    Author / Owner
                  </span>
                  <span className="font-semibold text-slate-800">
                    {item.owner_name || 'Current User'}
                  </span>
                </div>

                {/* Created Date (Dual Calendar: Ethiopian + Gregorian) */}
                <div className="p-2.5 space-y-1">
                  <div className="flex items-center justify-between text-slate-500">
                    <span className="flex items-center gap-2">
                      <Calendar className="w-3.5 h-3.5 text-slate-400" />
                      Created (EC / GC)
                    </span>
                    <span className="font-semibold text-blue-700">
                      {item.ec_created_at || 'EC Date'}
                    </span>
                  </div>
                  <div className="text-[11px] text-right text-slate-400">
                    {item.created_at ? new Date(item.created_at).toLocaleString() : 'N/A'}
                  </div>
                </div>

                {/* Modified Date */}
                {item.updated_at && (
                  <div className="p-2.5 space-y-1">
                    <div className="flex items-center justify-between text-slate-500">
                      <span className="flex items-center gap-2">
                        <Clock className="w-3.5 h-3.5 text-slate-400" />
                        Last Modified
                      </span>
                      <span className="font-medium text-slate-700">
                        {new Date(item.updated_at).toLocaleDateString()}
                      </span>
                    </div>
                    <div className="text-[11px] text-right text-slate-400">
                      {new Date(item.updated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Tags Section */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h5 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                  Tags & Taxonomy
                </h5>
                {onManageTags && (
                  <button
                    type="button"
                    onClick={() => onManageTags(item)}
                    className="text-xs font-semibold text-blue-600 hover:text-blue-700 cursor-pointer"
                  >
                    Edit Tags
                  </button>
                )}
              </div>

              {item.tags && item.tags.length > 0 ? (
                <div className="flex flex-wrap gap-1.5 p-2 rounded-xl bg-slate-50 border border-slate-100">
                  {item.tags.map((tg) => (
                    <span
                      key={tg}
                      className="inline-flex items-center gap-1 text-[11px] font-semibold bg-white text-slate-700 border border-slate-200 px-2.5 py-0.5 rounded-md shadow-2xs"
                    >
                      <Tag className="w-3 h-3 text-slate-400" />
                      <span>{tg}</span>
                    </span>
                  ))}
                </div>
              ) : (
                <div className="p-3 text-center rounded-xl border border-dashed border-slate-200 text-slate-400 text-xs">
                  No tags assigned yet.{' '}
                  {onManageTags && (
                    <button
                      type="button"
                      onClick={() => onManageTags(item)}
                      className="text-blue-600 font-semibold hover:underline cursor-pointer"
                    >
                      Add tag
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        ) : (
          /* =========================================================
             VERSION HISTORY TAB (Module 5)
             ========================================================= */
          <div className="space-y-4 animate-fade-in">
            {/* Top: Upload New Revision Button */}
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <h5 className="text-xs font-bold text-slate-800">
                  Revision Timeline
                </h5>
                <p className="text-[11px] text-slate-400">
                  CAS-deduplicated immutable version ledger
                </p>
              </div>
              <Button
                variant="primary"
                size="sm"
                className="text-xs"
                leftIcon={<Upload className="w-3.5 h-3.5" />}
                onClick={() => setShowUploadModal(true)}
              >
                Upload Revision
              </Button>
            </div>

            {/* Error state */}
            {versionError && (
              <div className="p-3 rounded-xl bg-red-50 border border-red-200 text-xs text-red-700 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 shrink-0 text-red-600 mt-0.5" />
                <span>{versionError}</span>
              </div>
            )}

            {/* Loading state */}
            {isLoadingVersions ? (
              <div className="py-12 text-center space-y-2">
                <div className="w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto" />
                <p className="text-xs text-slate-400">Loading revisions...</p>
              </div>
            ) : versions.length === 0 ? (
              <div className="py-10 text-center text-xs text-slate-400 space-y-2">
                <History className="w-8 h-8 text-slate-300 mx-auto" />
                <p className="font-semibold text-slate-600">No revisions found</p>
                <p className="text-[11px]">Upload a new revision above to start tracking versions.</p>
              </div>
            ) : (
              /* Versions List */
              <div className="relative pl-4 space-y-4 before:absolute before:left-1.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
                {versions.map((ver, idx) => {
                  const isCurrent = idx === 0;
                  return (
                    <div
                      key={ver.id || ver.version_number}
                      className="relative p-3 rounded-xl bg-white border border-slate-200/90 shadow-2xs space-y-2.5 transition-all hover:border-blue-300"
                    >
                      {/* Timeline Dot Indicator */}
                      <span
                        className={`absolute -left-[19px] top-4 w-2.5 h-2.5 rounded-full ring-4 ring-white ${
                          isCurrent ? 'bg-blue-600' : 'bg-slate-300'
                        }`}
                      />

                      {/* Version Header */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs font-bold text-slate-900">
                            Version {ver.version_number}
                          </span>
                          {isCurrent && (
                            <span className="text-[9px] font-bold px-1.5 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 rounded-md">
                              Current
                            </span>
                          )}
                        </div>

                        <span className="text-[11px] font-semibold text-slate-500">
                          {formatBytes(ver.size_bytes)}
                        </span>
                      </div>

                      {/* Author & Dual Dates */}
                      <div className="text-[11px] text-slate-500 space-y-1">
                        <div className="flex items-center gap-1.5">
                          <User className="w-3 h-3 text-slate-400" />
                          <span className="font-medium text-slate-700">
                            {ver.created_by_name || 'System / Author'}
                          </span>
                        </div>

                        <div className="flex items-center justify-between text-slate-400">
                          <span className="text-blue-700 font-medium">
                            {ver.ec_created_at || 'EC Date'}
                          </span>
                          <span>
                            {ver.created_at ? new Date(ver.created_at).toLocaleString() : ''}
                          </span>
                        </div>
                      </div>

                      {/* Change Summary Note */}
                      {ver.change_summary && (
                        <div className="p-2 rounded-lg bg-slate-50 border border-slate-100 text-[11px] text-slate-600 italic">
                          "{ver.change_summary}"
                        </div>
                      )}

                      {/* Checksum SHA256 */}
                      <div className="flex items-center justify-between pt-1 border-t border-slate-100 text-[10px] text-slate-400 font-mono">
                        <span className="truncate max-w-[170px]" title={ver.checksum_sha256}>
                          sha256:{ver.checksum_sha256.substring(0, 14)}...
                        </span>
                        <button
                          type="button"
                          onClick={() => handleCopyChecksum(ver.checksum_sha256)}
                          title="Copy SHA-256 Checksum"
                          className="flex items-center gap-1 text-slate-400 hover:text-blue-600 transition-colors cursor-pointer"
                        >
                          {copiedChecksum === ver.checksum_sha256 ? (
                            <>
                              <Check className="w-3 h-3 text-emerald-600" />
                              <span className="text-emerald-600">Copied</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3 h-3" />
                              <span>Copy</span>
                            </>
                          )}
                        </button>
                      </div>

                      {/* Version Action Buttons */}
                      <div className="flex items-center gap-2 pt-1">
                        <Button
                          variant="subtle"
                          size="sm"
                          isLoading={downloadingVersionNum === ver.version_number}
                          className="flex-1 text-[11px] py-1"
                          leftIcon={<Download className="w-3 h-3" />}
                          onClick={() => handleDownloadHistorical(ver)}
                        >
                          Download
                        </Button>

                        {!isCurrent && (
                          <Button
                            variant="secondary"
                            size="sm"
                            className="flex-1 text-[11px] py-1 text-slate-700 hover:text-blue-600 hover:border-blue-200"
                            leftIcon={<RotateCcw className="w-3 h-3" />}
                            onClick={() => setRevertingVersion(ver)}
                          >
                            Revert
                          </Button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* =========================================================
          MODAL: Upload New Revision
          ========================================================= */}
      <Modal
        isOpen={showUploadModal}
        onClose={() => {
          if (!isUploadingVersion) {
            setShowUploadModal(false);
            setUploadFile(null);
            setChangeSummary('');
          }
        }}
        title="Upload New Revision"
        icon={<Upload className="w-5 h-5 text-blue-600" />}
        description={`Increment ${item?.name || 'document'} to a new revision with CAS deduplication.`}
      >
        <form onSubmit={handleUploadRevision} className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5">
              Select Replacement File
            </label>
            <input
              type="file"
              required
              onChange={(e) => {
                if (e.target.files && e.target.files[0]) {
                  setUploadFile(e.target.files[0]);
                }
              }}
              className="w-full text-xs text-slate-600 file:mr-3 file:py-2 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 cursor-pointer border border-slate-200 rounded-lg p-1.5"
            />
            {uploadFile && (
              <p className="text-[11px] text-slate-400 mt-1">
                Selected: <span className="font-semibold text-slate-700">{uploadFile.name}</span> ({formatBytes(uploadFile.size)})
              </p>
            )}
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5">
              Revision Summary Note (Optional)
            </label>
            <input
              type="text"
              value={changeSummary}
              onChange={(e) => setChangeSummary(e.target.value)}
              placeholder="e.g. Updated financial figures, approved by auditor"
              className="w-full text-xs px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              maxLength={255}
            />
            <p className="text-[11px] text-slate-400 mt-1">
              Provides context in the audit ledger for why this revision was made.
            </p>
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={isUploadingVersion}
              onClick={() => {
                setShowUploadModal(false);
                setUploadFile(null);
                setChangeSummary('');
              }}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isUploadingVersion}
              disabled={!uploadFile}
            >
              Upload Revision
            </Button>
          </div>
        </form>
      </Modal>

      {/* =========================================================
          MODAL: Revert Historical Version Confirmation
          ========================================================= */}
      <Modal
        isOpen={!!revertingVersion}
        onClose={() => {
          if (!isReverting) setRevertingVersion(null);
        }}
        title="Revert Document to Historical Version"
        icon={<RotateCcw className="w-5 h-5 text-blue-600" />}
        description={`Roll back ${item?.name} to Version ${revertingVersion?.version_number}?`}
      >
        <div className="space-y-4">
          <div className="p-3.5 bg-blue-50/70 border border-blue-200/80 rounded-xl space-y-2 text-xs text-slate-700">
            <p className="font-semibold text-blue-900">
              Zero-Storage Rollback Architecture:
            </p>
            <p className="text-slate-600 leading-relaxed">
              EthioOffice will create a new current revision (Version {(versions[0]?.version_number || 1) + 1}) referencing the immutable Content-Addressable payload of Version {revertingVersion?.version_number}. No data is overwritten or lost.
            </p>
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={isReverting}
              onClick={() => setRevertingVersion(null)}
            >
              Cancel
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              isLoading={isReverting}
              onClick={handleRevertConfirm}
            >
              Confirm Revert
            </Button>
          </div>
        </div>
      </Modal>

      {/* =========================================================
          MODAL: Check-Out / Lock Document
          ========================================================= */}
      <Modal
        isOpen={showLockModal}
        onClose={() => {
          if (!isLocking) setShowLockModal(false);
        }}
        title="Lock Document (Exclusive Check-Out)"
        icon={<Lock className="w-5 h-5 text-amber-600" />}
        description="Prevent other users from editing or modifying this document while you are working on it."
      >
        <form onSubmit={handleAcquireLock} className="space-y-4">
          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5">
              Lock Reason
            </label>
            <input
              type="text"
              value={lockReason}
              onChange={(e) => setLockReason(e.target.value)}
              placeholder="e.g. Updating quarterly contract terms"
              className="w-full text-xs px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              maxLength={255}
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-700 mb-1.5">
              Duration
            </label>
            <select
              value={lockDuration}
              onChange={(e) => setLockDuration(Number(e.target.value))}
              className="w-full text-xs px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
            >
              <option value={30}>30 Minutes</option>
              <option value={60}>1 Hour</option>
              <option value={120}>2 Hours (Default)</option>
              <option value={240}>4 Hours</option>
              <option value={480}>8 Hours (Full Working Day)</option>
            </select>
            <p className="text-[11px] text-slate-400 mt-1">
              The lock automatically expires after this duration if not renewed.
            </p>
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={isLocking}
              onClick={() => setShowLockModal(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
              isLoading={isLocking}
            >
              Acquire Lock
            </Button>
          </div>
        </form>
      </Modal>
    </aside>
  );
};
