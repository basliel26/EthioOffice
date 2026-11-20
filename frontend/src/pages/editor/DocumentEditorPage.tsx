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
  Monitor,
  RefreshCw,
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

// Global declaration for ONLYOFFICE / Euro-Office DocsAPI
declare global {
  interface Window {
    DocsAPI?: {
      DocEditor: new (
        placeholderId: string,
        config: unknown
      ) => {
        destroyEditor?: () => void;
        [key: string]: unknown;
      };
    };
  }
}

export const DocumentEditorPage: React.FC = () => {
  const { fileId } = useParams<{ fileId: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  // Core Document State
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fileItem, setFileItem] = useState<FileItem | null>(null);
  const [docConfig, setDocConfig] = useState<EuroOfficeConfigResponse | null>(null);
  const [coAuthors, setCoAuthors] = useState<CoAuthorItem[]>([]);

  // Dual-Engine State ('euro-office' for ONLYOFFICE iframe, 'native' for built-in A4 canvas)
  const [activeEngine, setActiveEngine] = useState<'euro-office' | 'native'>('native');
  const [isDocumentServerOnline, setIsDocumentServerOnline] = useState(false);
  const [docServerUrl, setDocServerUrl] = useState<string>('http://localhost:8080');
  const [isEditorInitialized, setIsEditorInitialized] = useState(false);
  const [editorLoadError, setEditorLoadError] = useState<string | null>(null);
  const editorInstanceRef = useRef<{ destroyEditor?: () => void } | null>(null);

  // Content & Editing State (Native Engine)
  const [content, setContent] = useState<string>('');
  const [originalContent, setOriginalContent] = useState<string>('');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'saved' | 'saving' | 'unsaved' | 'error'>('saved');
  const [lastSavedTime, setLastSavedTime] = useState<Date | null>(null);

  // Formatting State (Native Engine)
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

  // 1. Load document data and configuration
  const loadDocument = useCallback(async () => {
    if (!fileId) return;
    setIsLoading(true);
    setError(null);

    try {
      // Fetch file item metadata
      const file = await filesApi.get(fileId);
      setFileItem(file);

      // Fetch Euro-Office config
      let cfg: EuroOfficeConfigResponse | null = null;
      try {
        cfg = await euroOfficeApi.getConfig(fileId, 'en');
        setDocConfig(cfg);
      } catch (e) {
        console.warn('Euro-Office config error', e);
      }

      // Check lock status
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

      // Fetch document text content for native canvas fallback
      try {
        const textData = await euroOfficeApi.getTextContent(fileId);
        setContent(textData.content || '');
        setOriginalContent(textData.content || '');
        setSaveStatus('saved');
      } catch {
        setContent('');
        setOriginalContent('');
      }

      // Fetch co-authors
      try {
        const coauthorsRes = await euroOfficeApi.getCoauthors(fileId);
        setCoAuthors(coauthorsRes.coauthors);
      } catch {
        setCoAuthors([]);
      }

      // Check Euro-Office Document Server connectivity probe
      try {
        const health = await euroOfficeApi.getHealth();
        const isUp = health.status === 'UP';
        setIsDocumentServerOnline(isUp);
        if (health.document_server_url) {
          setDocServerUrl(health.document_server_url);
        }
        // If server is online, default to Euro-Office server engine; otherwise native canvas
        setActiveEngine(isUp ? 'euro-office' : 'native');
      } catch {
        setIsDocumentServerOnline(false);
        setActiveEngine('native');
      }

      // Pre-fetch versions for history drawer
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

  // 2. ONLYOFFICE / Euro-Office Dynamic Script Loader & Iframe Mount
  useEffect(() => {
    if (activeEngine !== 'euro-office' || !isDocumentServerOnline || !docConfig) {
      return;
    }

    const scriptId = 'euro-office-api-script';
    const scriptUrl = `${docServerUrl.replace(/\/$/, '')}/web-apps/apps/api/documents/api.js`;

    const initEditor = () => {
      if (!window.DocsAPI) {
        setEditorLoadError('Euro-Office DocsAPI not found on Document Server');
        return;
      }

      // Clean up previous instance if running
      if (editorInstanceRef.current && typeof editorInstanceRef.current.destroyEditor === 'function') {
        try {
          editorInstanceRef.current.destroyEditor();
        } catch {
          // ignore cleanup error
        }
        editorInstanceRef.current = null;
      }

      try {
        const container = document.getElementById('euro-office-iframe-container');
        if (!container) return;
        container.innerHTML = '';

        const editorConfigWithEvents = {
          documentType: docConfig.documentType,
          document: docConfig.document,
          editorConfig: docConfig.editorConfig,
          token: docConfig.token,
          width: '100%',
          height: '100%',
          type: 'desktop',
          events: {
            onAppReady: () => {
              setIsEditorInitialized(true);
              setSaveStatus('saved');
            },
            onDocumentReady: () => {
              setIsEditorInitialized(true);
              setSaveStatus('saved');
            },
            onDocumentStateChange: (event: { data: boolean }) => {
              setHasUnsavedChanges(Boolean(event.data));
              setSaveStatus(event.data ? 'unsaved' : 'saved');
            },
            onError: (event: unknown) => {
              console.error('Euro-Office Document Server error event:', event);
              setEditorLoadError('Euro-Office Document Server returned an error.');
            },
          },
        };

        editorInstanceRef.current = new window.DocsAPI.DocEditor(
          'euro-office-iframe-container',
          editorConfigWithEvents
        );
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to instantiate Euro-Office editor';
        setEditorLoadError(msg);
      }
    };

    if (window.DocsAPI) {
      initEditor();
      return;
    }

    const existingScript = document.getElementById(scriptId) as HTMLScriptElement | null;
    if (existingScript) {
      existingScript.onload = () => initEditor();
      existingScript.onerror = () => {
        setEditorLoadError(`Unable to reach Euro-Office server at ${scriptUrl}`);
        setIsDocumentServerOnline(false);
        setActiveEngine('native');
      };
      return;
    }

    const script = document.createElement('script');
    script.id = scriptId;
    script.src = scriptUrl;
    script.async = true;
    script.onload = () => initEditor();
    script.onerror = () => {
      setEditorLoadError(`Failed to load DocsAPI script from ${scriptUrl}`);
      setIsDocumentServerOnline(false);
      setActiveEngine('native');
    };
    document.body.appendChild(script);

    return () => {
      if (editorInstanceRef.current && typeof editorInstanceRef.current.destroyEditor === 'function') {
        try {
          editorInstanceRef.current.destroyEditor();
        } catch {
          // ignore
        }
        editorInstanceRef.current = null;
      }
    };
  }, [activeEngine, isDocumentServerOnline, docConfig, docServerUrl]);

  // 3. Save handler for Native Canvas (Manual Save & debounced AutoSave)
  const handleSave = useCallback(
    async (isAutoSave: boolean = false, customContent?: string) => {
      if (!fileId || isSaving) return;

      // If in Euro-Office server mode, trigger forcesave command
      if (activeEngine === 'euro-office') {
        setIsSaving(true);
        setSaveStatus('saving');
        try {
          await euroOfficeApi.dispatchCommand(fileId, 'forcesave');
          setSaveStatus('saved');
          setLastSavedTime(new Date());
          setHasUnsavedChanges(false);
        } catch (err) {
          console.warn('Euro-Office forcesave command response:', err);
          setSaveStatus('saved');
        } finally {
          setIsSaving(false);
        }
        return;
      }

      // Native Canvas saving
      const contentToSave = customContent !== undefined ? customContent : content;
      if (contentToSave === originalContent && !hasUnsavedChanges) return;

      setIsSaving(true);
      setSaveStatus('saving');

      try {
        const summary = isAutoSave ? 'Auto-saved revision' : 'Manual revision save';
        const updated = await euroOfficeApi.saveText(fileId, contentToSave, summary, isAutoSave);
        setFileItem(updated);
        setOriginalContent(contentToSave);
        setHasUnsavedChanges(false);
        setSaveStatus('saved');
        setLastSavedTime(new Date());

        try {
          const freshVersions = await filesApi.listVersions(fileId);
          setVersions(freshVersions);
        } catch {
          // ignore
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
    [fileId, isSaving, activeEngine, content, originalContent, hasUnsavedChanges]
  );

  // Content change handler for Native Canvas with debounced auto-save
  const handleContentChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    if (isLockedByOther) return;
    const newContent = e.target.value;
    setContent(newContent);
    setHasUnsavedChanges(newContent !== originalContent);
    setSaveStatus('unsaved');

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
      const textData = await euroOfficeApi.getTextContent(fileId);
      setContent(textData.content || '');
      setOriginalContent(textData.content || '');
      setHasUnsavedChanges(false);
      setSaveStatus('saved');
      const freshVersions = await filesApi.listVersions(fileId);
      setVersions(freshVersions);
      setShowHistoryDrawer(false);

      // If in Euro-Office mode, reload document config
      if (activeEngine === 'euro-office') {
        const freshConfig = await euroOfficeApi.getConfig(fileId, 'en');
        setDocConfig(freshConfig);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Revert failed';
      alert(`Rollback failed: ${msg}`);
    } finally {
      setIsReverting(false);
    }
  };

  // Retry probe for Euro-Office server
  const handleProbeServer = async () => {
    try {
      const health = await euroOfficeApi.getHealth();
      const isUp = health.status === 'UP';
      setIsDocumentServerOnline(isUp);
      if (isUp) {
        if (health.document_server_url) setDocServerUrl(health.document_server_url);
        setActiveEngine('euro-office');
        setEditorLoadError(null);
      } else {
        alert('Euro-Office Document Server is still unreachable on port 8080.');
      }
    } catch {
      setIsDocumentServerOnline(false);
      alert('Euro-Office Document Server check failed.');
    }
  };

  // Formatting Helpers for Native Canvas Textarea
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
              className="text-xs sm:text-sm font-bold text-slate-800 truncate max-w-[130px] sm:max-w-xs md:max-w-sm"
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
          </div>
        </div>

        {/* Center: Dual-Engine Switcher + Save Status & Lock Check-out Button */}
        <div className="hidden md:flex items-center gap-3 text-xs">
          {/* Engine Selector */}
          <div className="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200/80">
            <button
              type="button"
              onClick={() => setActiveEngine('euro-office')}
              disabled={!isDocumentServerOnline}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all cursor-pointer ${
                activeEngine === 'euro-office'
                  ? 'bg-white text-blue-600 shadow-2xs'
                  : !isDocumentServerOnline
                  ? 'text-slate-400 cursor-not-allowed opacity-60'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
              title={
                isDocumentServerOnline
                  ? 'Full Euro-Office ONLYOFFICE Suite'
                  : 'Euro-Office Document Server is offline on port 8080'
              }
            >
              <Monitor className="w-3 h-3" />
              <span>Euro-Office</span>
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  isDocumentServerOnline ? 'bg-emerald-500' : 'bg-slate-300'
                }`}
              />
            </button>
            <button
              type="button"
              onClick={() => setActiveEngine('native')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all cursor-pointer ${
                activeEngine === 'native'
                  ? 'bg-white text-blue-600 shadow-2xs'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
              title="Native Sovereign Canvas Editor"
            >
              <Sparkles className="w-3 h-3" />
              <span>Native Canvas</span>
            </button>
          </div>

          {!isDocumentServerOnline && (
            <button
              type="button"
              onClick={handleProbeServer}
              className="p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition-colors"
              title="Check if Euro-Office Server is now online"
            >
              <RefreshCw className="w-3 h-3" />
            </button>
          )}

          <div className="h-3 w-px bg-slate-200" />

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

      {/* 3. Formatting Toolbar (Rendered ONLY in Native Canvas Mode) */}
      {activeEngine === 'native' && (
        <div className="bg-white border-b border-slate-200/80 px-3 sm:px-6 py-1.5 flex items-center gap-1 sm:gap-2 overflow-x-auto text-xs shrink-0 select-none">
          {/* Font Family Dropdown with Ethiopian Ge'ez Fonts */}
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
      )}

      {/* 4. Main Document Workspace (Dual Engine Display) */}
      <div className="flex-1 relative flex min-h-0 overflow-hidden">
        {/* ENGINE 1: Euro-Office / ONLYOFFICE Iframe Canvas */}
        <div className={`flex-1 w-full h-full relative overflow-hidden bg-slate-100 ${activeEngine === 'euro-office' && isDocumentServerOnline ? 'block' : 'hidden'}`}>
          {!isEditorInitialized && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-50 z-10 gap-3">
              <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
              <p className="text-xs font-semibold text-slate-700">Connecting to Euro-Office Suite Engine...</p>
              <p className="text-[11px] text-slate-400">Loading OpenXML collaborative workspace</p>
            </div>
          )}
          {editorLoadError && (
            <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-amber-50 border border-amber-200 px-4 py-2.5 rounded-xl text-xs text-amber-900 shadow-md z-20 flex items-center gap-3">
              <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
              <span>{editorLoadError}</span>
              <button
                type="button"
                onClick={() => setActiveEngine('native')}
                className="px-2.5 py-1 rounded-md bg-amber-200 hover:bg-amber-300 text-amber-900 font-semibold cursor-pointer"
              >
                Switch to Native Canvas
              </button>
            </div>
          )}
          {/* The ONLYOFFICE container element (kept permanently mounted to prevent reload cycles) */}
          <div id="euro-office-iframe-container" className="w-full h-full" />
        </div>

        {/* ENGINE 2: Native Canvas Clean Paper Sheet */}
        <main className={`flex-1 overflow-y-auto p-4 sm:p-8 flex-col justify-start items-center ${activeEngine === 'native' ? 'flex' : 'hidden'}`}>
            {/* Authentic A4 Clean White Paper */}
            <div className="w-full max-w-[850px] bg-white shadow-[0_4px_25px_-5px_rgba(0,0,0,0.08)] border border-slate-200/90 rounded-sm px-10 sm:px-18 py-12 sm:py-20 min-h-[1100px] flex flex-col transition-all">
              {/* Clean Editable Document Canvas */}
              <textarea
                ref={textareaRef}
                value={content}
                onChange={handleContentChange}
                readOnly={isLockedByOther}
                placeholder=""
                style={{
                  fontFamily: selectedFont,
                  fontSize: selectedFontSize,
                  textAlign: textAlign,
                }}
                className={`w-full flex-1 min-h-[950px] border-none outline-none resize-none leading-relaxed text-slate-800 placeholder-slate-300 ${
                  isLockedByOther ? 'bg-slate-50/50 cursor-not-allowed' : 'bg-transparent'
                }`}
              />
            </div>

            {/* Non-intrusive Document Status Footer (Outside the paper) */}
            <div className="w-full max-w-[850px] py-3 px-2 flex items-center justify-between text-[11px] text-slate-400">
              <div className="flex items-center gap-3">
                <span className="font-medium text-slate-500">{fileItem.name}</span>
                <span>•</span>
                <span>CAS Version: v{versions[0]?.version_number || 1}</span>
              </div>
              <div>
                {content.length} characters • {content.trim().split(/\s+/).filter(Boolean).length} words
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
