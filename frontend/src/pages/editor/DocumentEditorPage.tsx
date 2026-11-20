import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Lock,
  LockOpen,
  Share2,
  Download,
  History,
  Check,
  Loader2,
  AlertCircle,
  FileText,
  FileSpreadsheet,
  Presentation,
  X,
  Sparkles,
  Save,
  Bold,
  Italic,
  Underline,
  Strikethrough,
  AlignLeft,
  AlignCenter,
  AlignRight,
  List as ListIcon,
  ListOrdered,
  Heading1,
  Heading2,
  RotateCcw,
  ShieldAlert,
} from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { ShareModal } from '../../components/drive/ShareModal';
import { euroOfficeApi, filesApi } from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import type {
  EuroOfficeConfigResponse,
  CoAuthorItem,
  FileItem,
  FileVersionSummary,
} from '../../api/types';

export const DocumentEditorPage: React.FC = () => {
  const { fileId } = useParams<{ fileId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  // Core Document State
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fileItem, setFileItem] = useState<FileItem | null>(null);
  const [_docConfig, setDocConfig] = useState<EuroOfficeConfigResponse | null>(null);
  const [coAuthors, setCoAuthors] = useState<CoAuthorItem[]>([]);

  // Content & Editing State
  const [content, setContent] = useState<string>('');
  const [originalContent, setOriginalContent] = useState<string>('');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving' | 'unsaved' | 'error'>('saved');
  const [lastSavedTime, setLastSavedTime] = useState<Date | null>(null);

  // Formatting State
  const [selectedFont, setSelectedFont] = useState<string>('Inter');
  const [selectedFontSize, setSelectedFontSize] = useState<string>('14px');
  const [textAlign, setTextAlign] = useState<'left' | 'center' | 'right'>('left');

  // Concurrency & Lock State
  const [isLockedByMe, setIsLockedByMe] = useState(false);
  const [isLockedByOther, setIsLockedByOther] = useState(false);
  const [lockHolderName, setLockHolderName] = useState<string | null>(null);
  const [isLocking, setIsLocking] = useState(false);

  // Version History Drawer State
  const [showHistoryDrawer, setShowHistoryDrawer] = useState(false);
  const [versions, setVersions] = useState<FileVersionSummary[]>([]);
  const [isLoadingVersions, setIsLoadingVersions] = useState(false);
  const [isReverting, setIsReverting] = useState(false);

  // Share Modal State
  const [showShareModal, setShowShareModal] = useState(false);

  // Document Server Status
  const [isDocumentServerOnline, setIsDocumentServerOnline] = useState(false);

  // Auto-save debounce timer ref
  const autoSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Helper for document format icons
  const renderDocIcon = (filename?: string, sizeClass: string = 'w-4 h-4') => {
    if (!filename) return <FileText className={sizeClass} />;
    const ext = filename.split('.').pop()?.toLowerCase();
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
      default:
        return <FileText className={`${sizeClass} text-slate-500`} />;
    }
  };

  // Load document data and configuration
  const loadDocument = useCallback(async () => {
    if (!fileId) return;
    setIsLoading(true);
    setError(null);

    try {
      // 1. Fetch file item metadata
      const file = await filesApi.get(fileId);
      setFileItem(file);

      // 2. Fetch Euro-Office config
      const config = await euroOfficeApi.getConfig(fileId, 'en');
      setDocConfig(config);

      // 3. Inspect lock status
      if (file.is_locked && file.lock_info) {
        const isCurrentHolder = file.lock_info.locked_by_id === user?.id;
        setIsLockedByMe(isCurrentHolder);
        setIsLockedByOther(!isCurrentHolder);
        setLockHolderName(file.lock_info.locked_by_name);
      } else {
        setIsLockedByMe(false);
        setIsLockedByOther(false);
        setLockHolderName(null);
      }

      // 4. Fetch real document text/content
      try {
        const textData = await euroOfficeApi.getTextContent(fileId);
        setContent(textData.content || '');
        setOriginalContent(textData.content || '');
        setSaveStatus('saved');
      } catch {
        // Fallback to title placeholder if unreadable binary
        setContent(`# ${file.name}\n\nStart typing your document content here...`);
        setOriginalContent(`# ${file.name}\n\nStart typing your document content here...`);
      }

      // 5. Fetch co-authors
      try {
        const coauthorsRes = await euroOfficeApi.getCoauthors(fileId);
        setCoAuthors(coauthorsRes.coauthors);
      } catch {
        setCoAuthors([]);
      }

      // 6. Check Euro-Office Document Server connectivity
      try {
        const health = await euroOfficeApi.getHealth();
        setIsDocumentServerOnline(health.status === 'UP');
      } catch {
        setIsDocumentServerOnline(false);
      }

      // 7. Pre-fetch versions for history drawer
      try {
        setIsLoadingVersions(true);
        const vers = await filesApi.listVersions(fileId);
        setVersions(vers);
      } catch {
        setVersions([]);
      } finally {
        setIsLoadingVersions(false);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load document';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [fileId, user?.id]);

  useEffect(() => {
    loadDocument();
  }, [loadDocument]);

  // Save handler (Supports both manual Save and debounced auto-save)
  const handleSave = useCallback(
    async (isAutoSave: boolean = false, customContent?: string) => {
      if (!fileId || isSaving) return;
      const contentToSave = customContent !== undefined ? customContent : content;
      if (contentToSave === originalContent && !hasUnsavedChanges) return;

      setIsSaving(true);
      setSaveStatus('saving');

      try {
        const summary = isAutoSave ? 'Auto-saved revision' : 'Manual revision save';
        const updated = await euroOfficeApi.saveText(fileId, contentToSave, summary);
        setFileItem(updated);
        setOriginalContent(contentToSave);
        setHasUnsavedChanges(false);
        setSaveStatus('saved');
        setLastSavedTime(new Date());

        // Refresh version list in background
        try {
          const freshVersions = await filesApi.listVersions(fileId);
          setVersions(freshVersions);
        } catch {
          // ignore background update error
        }
      } catch (err: unknown) {
        setSaveStatus('error');
        if (!isAutoSave) {
          const msg = err instanceof Error ? err.message : 'Save failed';
          alert(`Save error: ${msg}`);
        }
      } finally {
        setIsSaving(false);
      }
    },
    [fileId, isSaving, content, originalContent, hasUnsavedChanges]
  );

  // Content change handler with debounced auto-save (3 seconds idle)
  const handleContentChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    if (isLockedByOther) return;
    const newContent = e.target.value;
    setContent(newContent);
    setHasUnsavedChanges(newContent !== originalContent);
    setSaveStatus('unsaved');

    // Reset auto-save debounce timer
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
    }
    autoSaveTimerRef.current = setTimeout(() => {
      handleSave(true, newContent);
    }, 3500);
  };

  // Global Keyboard Shortcuts (Ctrl+S / Cmd+S for manual save)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        handleSave(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleSave]);

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      if (autoSaveTimerRef.current) {
        clearTimeout(autoSaveTimerRef.current);
      }
    };
  }, []);

  // Lock / Unlock Toggle
  const handleToggleLock = async () => {
    if (!fileId || isLocking || isLockedByOther) return;
    setIsLocking(true);
    try {
      if (isLockedByMe) {
        await filesApi.releaseLock(fileId);
        setIsLockedByMe(false);
        setLockHolderName(null);
        if (fileItem) {
          setFileItem({ ...fileItem, is_locked: false, lock_info: undefined });
        }
      } else {
        await filesApi.acquireLock(fileId, 'Editing in Euro-Office Workspace', 180);
        setIsLockedByMe(true);
        setLockHolderName(user?.full_name || 'You');
        if (fileItem) {
          setFileItem({
            ...fileItem,
            is_locked: true,
            lock_info: {
              locked_by_name: user?.full_name || 'You',
              locked_by_id: user?.id || '',
              reason: 'Editing in Euro-Office Workspace',
              expires_at: new Date(Date.now() + 180 * 60000).toISOString(),
            },
          });
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Lock operation failed';
      alert(msg);
    } finally {
      setIsLocking(false);
    }
  };

  // Revert to historical version from inside the editor
  const handleRevertVersion = async (versionNumber: number) => {
    if (!fileId || isReverting) return;
    setIsReverting(true);
    try {
      await filesApi.revertVersion(fileId, versionNumber);
      // Reload document content
      const textData = await euroOfficeApi.getTextContent(fileId);
      setContent(textData.content || '');
      setOriginalContent(textData.content || '');
      setHasUnsavedChanges(false);
      setSaveStatus('saved');
      // Refresh versions
      const freshVersions = await filesApi.listVersions(fileId);
      setVersions(freshVersions);
      setShowHistoryDrawer(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Revert failed';
      alert(`Rollback failed: ${msg}`);
    } finally {
      setIsReverting(false);
    }
  };

  // Formatting Helpers for Textarea insertion
  const applyFormatting = (prefix: string, suffix: string = prefix, placeholder: string = 'text') => {
    const textarea = textareaRef.current;
    if (!textarea || isLockedByOther) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selected = content.substring(start, end) || placeholder;
    const replacement = `${prefix}${selected}${suffix}`;
    const newContent = content.substring(0, start) + replacement + content.substring(end);

    setContent(newContent);
    setHasUnsavedChanges(true);
    setSaveStatus('unsaved');

    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + prefix.length, start + prefix.length + selected.length);
    }, 0);
  };

  const applyLinePrefix = (prefix: string) => {
    const textarea = textareaRef.current;
    if (!textarea || isLockedByOther) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const before = content.substring(0, start);
    const lineStart = before.lastIndexOf('\n') + 1;
    const newContent = content.substring(0, lineStart) + prefix + content.substring(lineStart);

    setContent(newContent);
    setHasUnsavedChanges(true);
    setSaveStatus('unsaved');

    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(start + prefix.length, end + prefix.length);
    }, 0);
  };

  // Loading Screen
  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center text-xs text-slate-500 gap-3 font-sans">
        <Loader2 className="w-6 h-6 animate-spin text-blue-600" />
        <span className="font-medium text-slate-700">Loading Euro-Office Document Workspace...</span>
      </div>
    );
  }

  // Error Screen
  if (error || !fileItem) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6 text-center font-sans">
        <div className="w-12 h-12 rounded-2xl bg-red-50 border border-red-200 flex items-center justify-center text-red-600 mb-4">
          <AlertCircle className="w-6 h-6" />
        </div>
        <h2 className="text-sm font-bold text-slate-900 mb-1">Failed to Open Document</h2>
        <p className="text-xs text-slate-500 max-w-md mb-6">{error || 'Document not found or access denied.'}</p>
        <Button variant="primary" size="sm" onClick={() => navigate('/drive/personal')}>
          Back to Drive
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-slate-100/70 overflow-hidden font-sans select-none">
      {/* 1. Header Toolbar */}
      <header className="h-13 bg-white border-b border-slate-200/90 px-3 sm:px-4 flex items-center justify-between shrink-0 shadow-2xs z-20">
        {/* Left: Back Navigation + Document Title + Badges */}
        <div className="flex items-center gap-2.5 min-w-0">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer"
            title="Back to Drive"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>

          <div className="flex items-center gap-2 min-w-0">
            <div className="p-1.5 rounded-lg bg-slate-50 border border-slate-200/60 shrink-0">
              {renderDocIcon(fileItem.name, 'w-4 h-4')}
            </div>
            <span
              className="text-xs sm:text-sm font-bold text-slate-800 truncate max-w-[150px] sm:max-w-xs md:max-w-md"
              title={fileItem.name}
            >
              {fileItem.name}
            </span>
            <Badge variant="neutral" className="uppercase text-[9px] tracking-wider px-1.5 py-0.5">
              {fileItem.name.split('.').pop() || 'DOC'}
            </Badge>

            {isLockedByOther ? (
              <span className="hidden sm:inline-flex items-center gap-1 text-[10px] bg-amber-50 text-amber-700 px-2 py-0.5 rounded-md border border-amber-200 font-semibold">
                <Lock className="w-3 h-3 text-amber-600" />
                <span>View Only (Locked by {lockHolderName})</span>
              </span>
            ) : (
              <span className="hidden sm:inline-flex items-center gap-1 text-[10px] bg-blue-50 text-blue-700 px-2 py-0.5 rounded-md border border-blue-200 font-semibold">
                <span>Editing Mode</span>
              </span>
            )}

            <span className="hidden lg:inline-flex items-center gap-1.5 text-[10px] text-slate-500 font-medium px-2 py-0.5 rounded-md bg-slate-50 border border-slate-200/80">
              <span className={`w-1.5 h-1.5 rounded-full ${isDocumentServerOnline ? 'bg-emerald-500' : 'bg-blue-500'}`} />
              <span>{isDocumentServerOnline ? 'Euro-Office Server Online' : 'Native CAS Engine'}</span>
            </span>
          </div>
        </div>

        {/* Center: Live Save Status & Lock Check-out Button */}
        <div className="hidden md:flex items-center gap-3 text-xs">
          {/* Save Status Indicator */}
          <div className="flex items-center gap-1.5">
            {saveStatus === 'saving' ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin text-blue-600" />
                <span className="text-[11px] font-medium text-slate-500">Saving changes...</span>
              </>
            ) : saveStatus === 'unsaved' ? (
              <>
                <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
                <span className="text-[11px] font-medium text-amber-600">Unsaved changes</span>
              </>
            ) : saveStatus === 'error' ? (
              <>
                <AlertCircle className="w-3.5 h-3.5 text-red-600" />
                <span className="text-[11px] font-semibold text-red-600">Save failed</span>
              </>
            ) : (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-600" />
                <span className="text-[11px] font-medium text-slate-500">
                  Saved to Drive {lastSavedTime ? `(${lastSavedTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})` : ''}
                </span>
              </>
            )}
          </div>

          <div className="h-3 w-px bg-slate-200" />

          {/* Checkout Lock Toggle */}
          <button
            type="button"
            onClick={handleToggleLock}
            disabled={isLockedByOther || isLocking}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
              isLockedByOther
                ? 'bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200'
                : isLockedByMe
                ? 'bg-amber-50 text-amber-800 border border-amber-200 hover:bg-amber-100'
                : 'bg-white border border-slate-200/90 text-slate-600 hover:bg-slate-50'
            }`}
            title={isLockedByOther ? `Locked by ${lockHolderName}` : isLockedByMe ? 'Release Lock' : 'Acquire Exclusive Check-Out Lock'}
          >
            {isLockedByMe ? (
              <>
                <Lock className="w-3 h-3 text-amber-600" />
                <span>Locked by You</span>
              </>
            ) : (
              <>
                <LockOpen className="w-3 h-3 text-slate-500" />
                <span>Check Out</span>
              </>
            )}
          </button>
        </div>

        {/* Right Actions: Save Button + History + Share + Download */}
        <div className="flex items-center gap-1.5 sm:gap-2">
          {/* Active Co-Authors Avatars */}
          {coAuthors.length > 0 && (
            <div className="flex items-center -space-x-1.5 mr-1" title="Active Collaborators">
              {coAuthors.slice(0, 3).map((author) => (
                <div
                  key={author.user_id}
                  title={`${author.full_name} (${author.role})`}
                  className="w-6 h-6 rounded-full bg-blue-600 text-white flex items-center justify-center text-[10px] font-bold border-2 border-white ring-1 ring-slate-200"
                >
                  {author.full_name.charAt(0).toUpperCase()}
                </div>
              ))}
            </div>
          )}

          {/* Manual Save Button */}
          {!isLockedByOther && (
            <Button
              variant="primary"
              size="sm"
              isLoading={isSaving}
              leftIcon={<Save className="w-3.5 h-3.5" />}
              onClick={() => handleSave(false)}
              className="text-xs"
              title="Save Changes (Ctrl+S)"
            >
              <span className="hidden sm:inline">Save</span>
            </Button>
          )}

          {/* History Drawer Toggle */}
          <Button
            variant="subtle"
            size="sm"
            onClick={() => setShowHistoryDrawer(!showHistoryDrawer)}
            leftIcon={<History className="w-3.5 h-3.5 text-slate-600" />}
            className="text-xs"
            title="Revision History & Rollback"
          >
            <span className="hidden sm:inline">History</span>
            {versions.length > 0 && (
              <span className="text-[10px] font-bold px-1.5 py-0.2 bg-slate-200 text-slate-700 rounded-full">
                {versions.length}
              </span>
            )}
          </Button>

          {/* Share Button */}
          <Button
            variant="subtle"
            size="sm"
            onClick={() => setShowShareModal(true)}
            leftIcon={<Share2 className="w-3.5 h-3.5 text-slate-600" />}
            className="text-xs"
            title="Share & Permissions"
          >
            <span className="hidden sm:inline">Share</span>
          </Button>

          {/* Download Original File */}
          <a
            href={`/api/v1/files/${fileItem.id}/download`}
            download={fileItem.name}
            className="p-1.5 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors cursor-pointer border border-slate-200/80"
            title="Download Document"
          >
            <Download className="w-4 h-4" />
          </a>
        </div>
      </header>

      {/* 2. Read-Only Lock Banner if locked by colleague */}
      {isLockedByOther && (
        <div className="bg-amber-50 border-b border-amber-200/80 px-4 py-2 flex items-center justify-between text-xs text-amber-800">
          <div className="flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-amber-600 shrink-0" />
            <span>
              <strong>Document is checked out:</strong> {lockHolderName} is currently editing this document. You are in read-only view mode to prevent conflicting modifications.
            </span>
          </div>
        </div>
      )}

      {/* 3. Formatting Toolbar for Built-In Document Workspace */}
      <div className="bg-white border-b border-slate-200/80 px-3 sm:px-6 py-1.5 flex items-center gap-1 sm:gap-2 overflow-x-auto text-xs shrink-0 select-none">
        {/* Font Family Dropdown */}
        <select
          value={selectedFont}
          onChange={(e) => setSelectedFont(e.target.value)}
          className="text-xs px-2 py-1 rounded-md border border-slate-200 bg-white font-medium text-slate-700 hover:border-slate-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
          title="Select Font Family"
        >
          <option value="Inter">Inter (System Default)</option>
          <option value="'Abyssinica SIL', serif">Abyssinica SIL (Ge'ez / Amharic)</option>
          <option value="'Nyala', sans-serif">Nyala (Ethiopic Standard)</option>
          <option value="Calibri, sans-serif">Calibri</option>
          <option value="Georgia, serif">Georgia</option>
          <option value="'Courier New', monospace">Courier New (Monospace)</option>
        </select>

        {/* Font Size Dropdown */}
        <select
          value={selectedFontSize}
          onChange={(e) => setSelectedFontSize(e.target.value)}
          className="text-xs px-2 py-1 rounded-md border border-slate-200 bg-white font-medium text-slate-700 hover:border-slate-300 focus:outline-none focus:ring-1 focus:ring-blue-500"
          title="Font Size"
        >
          <option value="12px">12 pt</option>
          <option value="14px">14 pt</option>
          <option value="16px">16 pt</option>
          <option value="18px">18 pt</option>
          <option value="20px">20 pt</option>
          <option value="24px">24 pt</option>
        </select>

        <div className="h-4 w-px bg-slate-200 mx-1 shrink-0" />

        {/* Inline Formatting Buttons */}
        <button
          type="button"
          onClick={() => applyFormatting('**', '**', 'bold text')}
          disabled={isLockedByOther}
          className="p-1.5 rounded-md hover:bg-slate-100 text-slate-600 hover:text-slate-900 transition-colors disabled:opacity-40 cursor-pointer"
          title="Bold (**text**)"
        >
          <Bold className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          onClick={() => applyFormatting('*', '*', 'italic text')}
          disabled={isLockedByOther}
          className="p-1.5 rounded-md hover:bg-slate-100 text-slate-600 hover:text-slate-900 transition-colors disabled:opacity-40 cursor-pointer"
          title="Italic (*text*)"
        >
          <Italic className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          onClick={() => applyFormatting('<u>', '</u>', 'underlined text')}
          disabled={isLockedByOther}
          className="p-1.5 rounded-md hover:bg-slate-100 text-slate-600 hover:text-slate-900 transition-colors disabled:opacity-40 cursor-pointer"
          title="Underline"
        >
          <Underline className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          onClick={() => applyFormatting('~~', '~~', 'strikethrough text')}
          disabled={isLockedByOther}
          className="p-1.5 rounded-md hover:bg-slate-100 text-slate-600 hover:text-slate-900 transition-colors disabled:opacity-40 cursor-pointer"
          title="Strikethrough"
        >
          <Strikethrough className="w-3.5 h-3.5" />
        </button>

        <div className="h-4 w-px bg-slate-200 mx-1 shrink-0" />

        {/* Headings */}
        <button
          type="button"
          onClick={() => applyLinePrefix('# ')}
          disabled={isLockedByOther}
          className="p-1.5 rounded-md hover:bg-slate-100 text-slate-600 hover:text-slate-900 transition-colors disabled:opacity-40 cursor-pointer"
          title="Heading 1"
        >
          <Heading1 className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          onClick={() => applyLinePrefix('## ')}
          disabled={isLockedByOther}
          className="p-1.5 rounded-md hover:bg-slate-100 text-slate-600 hover:text-slate-900 transition-colors disabled:opacity-40 cursor-pointer"
          title="Heading 2"
        >
          <Heading2 className="w-3.5 h-3.5" />
        </button>

        <div className="h-4 w-px bg-slate-200 mx-1 shrink-0" />

        {/* Lists */}
        <button
          type="button"
          onClick={() => applyLinePrefix('- ')}
          disabled={isLockedByOther}
          className="p-1.5 rounded-md hover:bg-slate-100 text-slate-600 hover:text-slate-900 transition-colors disabled:opacity-40 cursor-pointer"
          title="Bullet List"
        >
          <ListIcon className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          onClick={() => applyLinePrefix('1. ')}
          disabled={isLockedByOther}
          className="p-1.5 rounded-md hover:bg-slate-100 text-slate-600 hover:text-slate-900 transition-colors disabled:opacity-40 cursor-pointer"
          title="Numbered List"
        >
          <ListOrdered className="w-3.5 h-3.5" />
        </button>

        <div className="h-4 w-px bg-slate-200 mx-1 shrink-0" />

        {/* Alignments */}
        <button
          type="button"
          onClick={() => setTextAlign('left')}
          className={`p-1.5 rounded-md transition-colors cursor-pointer ${
            textAlign === 'left' ? 'bg-blue-50 text-blue-600 font-bold' : 'text-slate-600 hover:bg-slate-100'
          }`}
          title="Align Left"
        >
          <AlignLeft className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          onClick={() => setTextAlign('center')}
          className={`p-1.5 rounded-md transition-colors cursor-pointer ${
            textAlign === 'center' ? 'bg-blue-50 text-blue-600 font-bold' : 'text-slate-600 hover:bg-slate-100'
          }`}
          title="Align Center"
        >
          <AlignCenter className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          onClick={() => setTextAlign('right')}
          className={`p-1.5 rounded-md transition-colors cursor-pointer ${
            textAlign === 'right' ? 'bg-blue-50 text-blue-600 font-bold' : 'text-slate-600 hover:bg-slate-100'
          }`}
          title="Align Right"
        >
          <AlignRight className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* 4. Main Document Workspace Canvas & Revision History Drawer */}
      <div className="flex-1 relative flex min-h-0 overflow-hidden">
        {/* Document Sheet Canvas */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-8 flex justify-center items-start">
          <div className="w-full max-w-4xl bg-white shadow-md border border-slate-200/80 rounded-2xl p-8 sm:p-14 min-h-[950px] flex flex-col justify-between transition-all">
            <div className="space-y-4">
              {/* Top Watermark bar */}
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 text-xs text-slate-400">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-3.5 h-3.5 text-blue-600" />
                  <span className="font-semibold text-slate-700">Euro-Office Native Workspace</span>
                </div>
                <div className="font-mono text-[11px] text-slate-400">
                  CAS Version: v{versions[0]?.version_number || 1}
                </div>
              </div>

              {/* Editable Document Body */}
              <textarea
                ref={textareaRef}
                value={content}
                onChange={handleContentChange}
                readOnly={isLockedByOther}
                placeholder="Start typing your document text here..."
                style={{
                  fontFamily: selectedFont,
                  fontSize: selectedFontSize,
                  textAlign: textAlign,
                }}
                className={`w-full min-h-[750px] border-none outline-none resize-none leading-relaxed text-slate-800 placeholder-slate-300 ${
                  isLockedByOther ? 'bg-slate-50/50 cursor-not-allowed' : 'bg-transparent'
                }`}
              />
            </div>

            {/* Document Bottom Footer */}
            <div className="pt-6 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400">
              <span>{fileItem.name}</span>
              <span>
                {content.length} characters • {content.trim().split(/\s+/).filter(Boolean).length} words
              </span>
            </div>
          </div>
        </main>

        {/* 5. In-Editor Revision History Slide-Out Drawer */}
        {showHistoryDrawer && (
          <aside className="w-80 sm:w-88 lg:w-96 bg-white border-l border-slate-200/90 shadow-xl flex flex-col z-30 animate-fade-in shrink-0">
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100 bg-slate-50/60">
              <div className="flex items-center gap-2">
                <History className="w-4 h-4 text-blue-600" />
                <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wide">
                  Version History
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setShowHistoryDrawer(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-200/60 transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              <p className="text-xs text-slate-500 leading-relaxed">
                Immutable revisions saved in Content-Addressable Storage. Reverting creates a zero-duplicate rollback revision.
              </p>

              {isLoadingVersions ? (
                <div className="py-12 text-center text-xs text-slate-400 space-y-2">
                  <Loader2 className="w-5 h-5 animate-spin mx-auto text-blue-600" />
                  <p>Loading revisions...</p>
                </div>
              ) : versions.length === 0 ? (
                <div className="py-10 text-center text-xs text-slate-400">
                  <p>No historical revisions found.</p>
                </div>
              ) : (
                <div className="relative pl-4 space-y-4 before:absolute before:left-1.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
                  {versions.map((ver, idx) => {
                    const isCurrent = idx === 0;
                    return (
                      <div
                        key={ver.id || ver.version_number}
                        className="relative p-3 rounded-xl bg-white border border-slate-200 shadow-2xs space-y-2 text-xs"
                      >
                        <span
                          className={`absolute -left-[19px] top-4 w-2.5 h-2.5 rounded-full ring-4 ring-white ${
                            isCurrent ? 'bg-blue-600' : 'bg-slate-300'
                          }`}
                        />
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-slate-800">
                            Version {ver.version_number}
                          </span>
                          {isCurrent && (
                            <span className="text-[9px] font-bold px-1.5 py-0.5 bg-blue-50 text-blue-700 border border-blue-200 rounded-md">
                              Current
                            </span>
                          )}
                        </div>

                        <div className="text-[11px] text-slate-500 space-y-0.5">
                          <p>
                            <span className="font-medium text-slate-700">Author:</span>{' '}
                            {ver.created_by_name || 'Author'}
                          </p>
                          <p className="text-blue-700 font-medium">
                            {ver.ec_created_at || 'EC Date'}
                          </p>
                          <p className="text-slate-400">
                            {ver.created_at ? new Date(ver.created_at).toLocaleString() : ''}
                          </p>
                        </div>

                        {ver.change_summary && (
                          <p className="text-[11px] text-slate-600 italic bg-slate-50 p-1.5 rounded-md">
                            "{ver.change_summary}"
                          </p>
                        )}

                        {!isCurrent && (
                          <div className="pt-1">
                            <Button
                              variant="secondary"
                              size="sm"
                              isLoading={isReverting}
                              leftIcon={<RotateCcw className="w-3 h-3" />}
                              onClick={() => handleRevertVersion(ver.version_number)}
                              className="w-full text-[11px] py-1 text-slate-700 hover:text-blue-600"
                            >
                              Revert to this version
                            </Button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </aside>
        )}
      </div>

      {/* Share Modal */}
      {showShareModal && (
        <ShareModal
          isOpen={showShareModal}
          onClose={() => setShowShareModal(false)}
          file={fileItem}
        />
      )}
    </div>
  );
};
