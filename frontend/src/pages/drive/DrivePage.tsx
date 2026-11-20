import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Folder,
  FolderPlus,
  FileText,
  Upload,
  Trash2,
  RotateCcw,
  Star,
  Lock,
  Clock,
  Tag as TagIcon,
  ChevronRight,
  ChevronDown,
  Download,
  Edit2,
  Check,
  Share2,
  MoreVertical,
  FileSpreadsheet,
  Presentation,
  FilePlus2,
  ExternalLink,
  List,
  LayoutGrid,
  Filter,
  X,
  Info,
} from 'lucide-react';
import { filesApi, tagsApi, sharesApi } from '../../api/client';
import { useSearchScope } from '../../context/SearchContext';
import type { FileItem, TagItem } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Modal } from '../../components/ui/Modal';
import { ShareModal } from '../../components/drive/ShareModal';
import { FileDetailsPanel } from '../../components/drive/FileDetailsPanel';

interface DrivePageProps {
  viewMode?: 'PERSONAL' | 'COMPANY' | 'SHARED' | 'STARRED' | 'RECENT' | 'TRASH';
}

// Instant client-side cache for 0ms partition switching & folder browsing
const driveMemoryCache = new Map<string, FileItem[]>();
const tagsMemoryCache: { data: TagItem[] | null; timestamp: number } = { data: null, timestamp: 0 };

export const DrivePage: React.FC<DrivePageProps> = ({ viewMode = 'PERSONAL' }) => {
  const navigate = useNavigate();
  const initialKey = `${viewMode}_root`;
  const initialCached = driveMemoryCache.get(initialKey);

  const [files, setFiles] = useState<FileItem[]>(initialCached || []);
  const [availableTags, setAvailableTags] = useState<TagItem[]>(tagsMemoryCache.data || []);
  const [selectedTagFilter, setSelectedTagFilter] = useState<string | null>(null);
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null);

  const getRootBreadcrumbName = (mode: string) => {
    switch (mode) {
      case 'COMPANY':
        return 'Home';
      case 'SHARED':
        return 'Shared';
      case 'TRASH':
        return 'Deleted Items';
      case 'STARRED':
        return 'Favorites';
      case 'RECENT':
        return 'Recent Files';
      case 'PERSONAL':
      default:
        return 'Home';
    }
  };

  const [breadcrumbs, setBreadcrumbs] = useState<Array<{ id: string | null; name: string }>>([
    { id: null, name: getRootBreadcrumbName(viewMode) },
  ]);
  const [isLoading, setIsLoading] = useState(!initialCached);
  const requestIdRef = useRef(0);
  const { setSearchScope, clearSearchScope } = useSearchScope();

  // Reset folder navigation & breadcrumbs when switching between drive views
  useEffect(() => {
    const key = `${viewMode}_root`;
    const cached = driveMemoryCache.get(key);
    if (cached) {
      setFiles(cached);
      setIsLoading(false);
    } else {
      setFiles([]);
      setIsLoading(true);
    }
    setCurrentFolderId(null);
    setBreadcrumbs([{ id: null, name: getRootBreadcrumbName(viewMode) }]);
    setSelectedTagFilter(null);
    setSelectedItem(null);
    setShowNewDocMenu(false);
    setCanvasContextMenu(null);
    setRowContextMenu(null);
    setActiveRowMenuId(null);
  }, [viewMode]);

  // Handle clicking active drive in sidebar: smooth reset to root
  useEffect(() => {
    const handleNavRoot = () => {
      setFiles([]);
      setCurrentFolderId(null);
      setSelectedItem(null);
      setBreadcrumbs([{ id: null, name: getRootBreadcrumbName(viewMode) }]);
      setSelectedTagFilter(null);
    };
    window.addEventListener('ethiooffice-nav-root', handleNavRoot);
    return () => window.removeEventListener('ethiooffice-nav-root', handleNavRoot);
  }, [viewMode]);

  useEffect(() => {
    if (currentFolderId && breadcrumbs.length > 1) {
      const activeFolder = breadcrumbs[breadcrumbs.length - 1];
      setSearchScope({ folderId: currentFolderId, folderName: activeFolder.name });
    } else {
      clearSearchScope();
    }
    return () => {
      clearSearchScope();
    };
  }, [currentFolderId, breadcrumbs]);

  // Modals & form state
  const [showFolderModal, setShowFolderModal] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  
  // New File/Document Modal
  const [showDocModal, setShowDocModal] = useState(false);
  const [newDocName, setNewDocName] = useState('');
  const [newDocType, setNewDocType] = useState<'docx' | 'xlsx' | 'pptx' | 'txt'>('docx');
  const [isCreatingDoc, setIsCreatingDoc] = useState(false);

  const [showRenameModal, setShowRenameModal] = useState(false);
  const [targetFile, setTargetFile] = useState<FileItem | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [showTagModal, setShowTagModal] = useState(false);
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);
  const [showEmptyTrashModal, setShowEmptyTrashModal] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);

  // Dropdown & Context Menu state
  const [showNewDocMenu, setShowNewDocMenu] = useState(false);
  const [canvasContextMenu, setCanvasContextMenu] = useState<{ x: number; y: number } | null>(null);
  const [rowContextMenu, setRowContextMenu] = useState<{ x: number; y: number; file: FileItem } | null>(null);
  const [activeRowMenuId, setActiveRowMenuId] = useState<string | null>(null);

  // Filter & Layout State
  type TypeFilter = 'ALL' | 'FOLDERS' | 'DOCX' | 'XLSX' | 'PPTX' | 'TXT' | 'PDF';
  const [selectedTypeFilter, setSelectedTypeFilter] = useState<TypeFilter>('ALL');
  const [showTagFilterMenu, setShowTagFilterMenu] = useState(false);
  const [showTypeFilterMenu, setShowTypeFilterMenu] = useState(false);
  const [displayLayout, setDisplayLayout] = useState<'list' | 'grid'>(() => {
    const saved = localStorage.getItem('ethiooffice_drive_layout');
    return saved === 'grid' ? 'grid' : 'list';
  });

  const handleToggleLayout = (layout: 'list' | 'grid') => {
    setDisplayLayout(layout);
    localStorage.setItem('ethiooffice_drive_layout', layout);
  };

  // Details Inspector State & Selected Item
  const [selectedItem, setSelectedItem] = useState<FileItem | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState<boolean>(() => {
    try {
      return localStorage.getItem('ethiooffice_details_panel_open') === 'true';
    } catch {
      return false;
    }
  });

  const handleToggleDetails = () => {
    setIsDetailsOpen((prev) => {
      const next = !prev;
      localStorage.setItem('ethiooffice_details_panel_open', next ? 'true' : 'false');
      return next;
    });
  };

  const handleItemUpdated = (updatedItem: FileItem) => {
    setFiles((prev) => prev.map((f) => (f.id === updatedItem.id ? updatedItem : f)));
    setSelectedItem(updatedItem);
    const cacheKey = currentFolderId ? `${viewMode}_folder_${currentFolderId}` : `${viewMode}_root`;
    driveMemoryCache.delete(cacheKey);
  };

  const newDocMenuRef = useRef<HTMLDivElement>(null);
  const tagMenuRef = useRef<HTMLDivElement>(null);
  const typeMenuRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const openCanvasContextMenu = (e: React.MouseEvent) => {
    if (viewMode !== 'PERSONAL' && viewMode !== 'COMPANY') return;
    e.preventDefault();
    const menuWidth = 230;
    const menuHeight = 260;
    const x = Math.min(e.clientX, window.innerWidth - menuWidth - 16);
    const y = Math.min(e.clientY, window.innerHeight - menuHeight - 16);
    setRowContextMenu(null);
    setActiveRowMenuId(null);
    setCanvasContextMenu({ x, y });
  };

  const openRowContextMenu = (e: React.MouseEvent, file: FileItem) => {
    e.preventDefault();
    e.stopPropagation();
    const menuWidth = 210;
    const menuHeight = 280;
    const x = Math.min(e.clientX, window.innerWidth - menuWidth - 16);
    const y = Math.min(e.clientY, window.innerHeight - menuHeight - 16);
    setCanvasContextMenu(null);
    setActiveRowMenuId(null);
    setRowContextMenu({ x, y, file });
  };

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (newDocMenuRef.current && !newDocMenuRef.current.contains(e.target as Node)) {
        setShowNewDocMenu(false);
      }
      if (tagMenuRef.current && !tagMenuRef.current.contains(e.target as Node)) {
        setShowTagFilterMenu(false);
      }
      if (typeMenuRef.current && !typeMenuRef.current.contains(e.target as Node)) {
        setShowTypeFilterMenu(false);
      }
      setCanvasContextMenu(null);
      setRowContextMenu(null);
      setActiveRowMenuId(null);
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setShowNewDocMenu(false);
        setShowTagFilterMenu(false);
        setShowTypeFilterMenu(false);
        setCanvasContextMenu(null);
        setRowContextMenu(null);
        setActiveRowMenuId(null);
      }
    };
    window.addEventListener('mousedown', handleClickOutside);
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('mousedown', handleClickOutside);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, []);

  const documentTypeOptions = [
    {
      id: 'docx' as const,
      name: 'Word Document',
      extension: '.docx',
      description: 'Editable in Euro-Office Document Editor',
      icon: <FileText className="w-5 h-5 text-blue-600" />,
      badgeColor: 'bg-blue-100 text-blue-700',
    },
    {
      id: 'xlsx' as const,
      name: 'Excel Spreadsheet',
      extension: '.xlsx',
      description: 'Editable in Euro-Office Sheets',
      icon: <FileSpreadsheet className="w-5 h-5 text-emerald-600" />,
      badgeColor: 'bg-emerald-100 text-emerald-700',
    },
    {
      id: 'pptx' as const,
      name: 'PowerPoint Presentation',
      extension: '.pptx',
      description: 'Editable in Euro-Office Slides',
      icon: <Presentation className="w-5 h-5 text-amber-600" />,
      badgeColor: 'bg-amber-100 text-amber-700',
    },
    {
      id: 'txt' as const,
      name: 'Plain Text Document',
      extension: '.txt',
      description: 'Simple plain text note file',
      icon: <FileText className="w-5 h-5 text-slate-600" />,
      badgeColor: 'bg-slate-100 text-slate-700',
    },
  ];

  const loadData = async (folderId: string | null = currentFolderId) => {
    const reqId = ++requestIdRef.current;
    const key = `${viewMode}_${folderId || 'root'}`;

    if (!driveMemoryCache.has(key)) {
      setIsLoading(true);
    }

    try {
      let fetchPromise: Promise<FileItem[]>;
      if (viewMode === 'STARRED') {
        fetchPromise = filesApi.listStarred();
      } else if (viewMode === 'RECENT') {
        fetchPromise = filesApi.getRecent(30).then((r) => r.map((item) => item.file));
      } else if (viewMode === 'TRASH') {
        fetchPromise = filesApi.list('TRASH', folderId || undefined);
      } else if (viewMode === 'SHARED') {
        fetchPromise = sharesApi.listSharedWithMe();
      } else {
        const driveType = viewMode === 'COMPANY' ? 'COMPANY' : 'PERSONAL';
        fetchPromise = filesApi.list(driveType, folderId || undefined);
      }

      let tagsPromise: Promise<TagItem[]>;
      if (tagsMemoryCache.data && Date.now() - tagsMemoryCache.timestamp < 60000) {
        tagsPromise = Promise.resolve(tagsMemoryCache.data);
      } else {
        tagsPromise = tagsApi.list().then((tags) => {
          tagsMemoryCache.data = tags;
          tagsMemoryCache.timestamp = Date.now();
          return tags;
        });
      }

      const [data, tags] = await Promise.all([fetchPromise, tagsPromise]);

      if (reqId !== requestIdRef.current) return;
      driveMemoryCache.set(key, data);
      setFiles(data);
      setAvailableTags(tags);
    } catch {
      // ignore
    } finally {
      if (reqId === requestIdRef.current) {
        setIsLoading(false);
      }
    }
  };

  useEffect(() => {
    loadData(currentFolderId);
  }, [viewMode, currentFolderId]);

  const handleCreateFolder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFolderName.trim()) return;

    try {
      const driveType = viewMode === 'COMPANY' ? 'COMPANY' : 'PERSONAL';
      await filesApi.createFolder(newFolderName.trim(), driveType, currentFolderId || undefined);
      setNewFolderName('');
      setShowFolderModal(false);
      driveMemoryCache.clear();
      loadData();
    } catch {
      // ignore
    }
  };

  const handleCreateDocument = async (e: React.FormEvent, openInEditor: boolean = false) => {
    e.preventDefault();
    if (!newDocName.trim()) return;

    setIsCreatingDoc(true);
    try {
      const driveType = viewMode === 'COMPANY' ? 'COMPANY' : 'PERSONAL';
      const created = await filesApi.createDocument({
        name: newDocName.trim(),
        doc_type: newDocType,
        drive_type: driveType,
        parent_id: currentFolderId || undefined,
      });
      setNewDocName('');
      setShowDocModal(false);
      driveMemoryCache.clear();
      await loadData();
      if (openInEditor) {
        navigate(`/editor/${created.id}`);
      }
    } catch {
      // ignore
    } finally {
      setIsCreatingDoc(false);
    }
  };

  const handleQuickCreateDocument = async (docType: 'docx' | 'xlsx' | 'pptx' | 'txt') => {
    setShowNewDocMenu(false);
    setCanvasContextMenu(null);
    setRowContextMenu(null);
    setIsCreatingDoc(true);
    try {
      const driveType = viewMode === 'COMPANY' ? 'COMPANY' : 'PERSONAL';
      const defaultNames: Record<string, string> = {
        docx: 'New Document',
        xlsx: 'New Spreadsheet',
        pptx: 'New Presentation',
        txt: 'New Text Document',
      };
      const created = await filesApi.createDocument({
        name: defaultNames[docType],
        doc_type: docType,
        drive_type: driveType,
        parent_id: currentFolderId || undefined,
      });
      driveMemoryCache.clear();
      await loadData();
      navigate(`/editor/${created.id}`);
    } catch {
      // ignore
    } finally {
      setIsCreatingDoc(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const driveType = viewMode === 'COMPANY' ? 'COMPANY' : 'PERSONAL';
      await filesApi.upload(file, driveType, currentFolderId || undefined);
      if (fileInputRef.current) fileInputRef.current.value = '';
      driveMemoryCache.clear();
      loadData();
    } catch {
      // ignore
    }
  };

  const handleToggleStar = async (file: FileItem) => {
    try {
      if (file.is_starred) {
        await filesApi.unstar(file.id);
      } else {
        await filesApi.star(file.id);
      }
      driveMemoryCache.clear();
      loadData();
    } catch {
      // ignore
    }
  };

  const handleDelete = async (file: FileItem) => {
    try {
      if (viewMode === 'TRASH') {
        await filesApi.delete(file.id, true);
      } else {
        await filesApi.delete(file.id, false);
      }
      driveMemoryCache.clear();
      loadData();
    } catch {
      // ignore
    }
  };

  const handleRestore = async (file: FileItem) => {
    try {
      await filesApi.restore(file.id);
      driveMemoryCache.clear();
      loadData();
    } catch {
      // ignore
    }
  };

  const handleEmptyTrash = async () => {
    try {
      await filesApi.emptyTrash();
      setShowEmptyTrashModal(false);
      driveMemoryCache.clear();
      loadData();
    } catch {
      // ignore
    }
  };

  const handleRenameSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!targetFile || !renameValue.trim()) return;

    try {
      await filesApi.rename(targetFile.id, renameValue.trim());
      setShowRenameModal(false);
      setTargetFile(null);
      driveMemoryCache.clear();
      loadData();
    } catch {
      // ignore
    }
  };

  const handleTagAssignSubmit = async () => {
    if (!targetFile) return;

    try {
      await filesApi.assignTags(targetFile.id, selectedTagIds);
      setShowTagModal(false);
      setTargetFile(null);
      driveMemoryCache.clear();
      loadData();
    } catch {
      // ignore
    }
  };

  const handleOpenFolder = (folder: FileItem) => {
    setSelectedItem(null);
    const key = `${viewMode}_${folder.id}`;
    const cached = driveMemoryCache.get(key);
    if (cached) {
      setFiles(cached);
      setIsLoading(false);
    } else {
      setFiles([]);
      setIsLoading(true);
    }
    setCurrentFolderId(folder.id);
    setBreadcrumbs((prev) => [...prev, { id: folder.id, name: folder.name }]);
  };

  const handleNavigateBreadcrumb = (index: number) => {
    setSelectedItem(null);
    const target = breadcrumbs[index];
    const key = `${viewMode}_${target.id || 'root'}`;
    const cached = driveMemoryCache.get(key);
    if (cached) {
      setFiles(cached);
      setIsLoading(false);
    } else {
      setFiles([]);
      setIsLoading(true);
    }
    setCurrentFolderId(target.id);
    setBreadcrumbs((prev) => prev.slice(0, index + 1));
  };

  const formatFileSize = (bytes: number) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const getFileIcon = (file: FileItem, sizeClass: string = 'w-5 h-5') => {
    if (file.is_folder) {
      return <Folder className={`${sizeClass} text-blue-600 fill-blue-50/70 shrink-0`} />;
    }
    const name = file.name.toLowerCase();
    if (name.endsWith('.docx') || name.endsWith('.doc')) {
      return <FileText className={`${sizeClass} text-blue-600 shrink-0`} />;
    }
    if (name.endsWith('.xlsx') || name.endsWith('.xls') || name.endsWith('.csv')) {
      return <FileSpreadsheet className={`${sizeClass} text-emerald-600 shrink-0`} />;
    }
    if (name.endsWith('.pptx') || name.endsWith('.ppt')) {
      return <Presentation className={`${sizeClass} text-amber-600 shrink-0`} />;
    }
    if (name.endsWith('.pdf')) {
      return <FileText className={`${sizeClass} text-rose-600 shrink-0`} />;
    }
    if (name.endsWith('.txt')) {
      return <FileText className={`${sizeClass} text-slate-500 shrink-0`} />;
    }
    return <FileText className={`${sizeClass} text-slate-400 shrink-0`} />;
  };

  const getTypeFilterLabel = (type: TypeFilter): string => {
    switch (type) {
      case 'FOLDERS':
        return 'Folders';
      case 'DOCX':
        return 'Word (.docx)';
      case 'XLSX':
        return 'Excel (.xlsx)';
      case 'PPTX':
        return 'PowerPoint (.pptx)';
      case 'TXT':
        return 'Text (.txt)';
      case 'PDF':
        return 'PDF (.pdf)';
      case 'ALL':
      default:
        return 'All Types';
    }
  };

  const typeFilterOptions = [
    { id: 'ALL' as const, label: 'All Types', icon: <FileText className="w-3.5 h-3.5 text-slate-400" /> },
    { id: 'FOLDERS' as const, label: 'Folders', icon: <Folder className="w-3.5 h-3.5 text-blue-600" /> },
    { id: 'DOCX' as const, label: 'Word Documents (.docx)', icon: <FileText className="w-3.5 h-3.5 text-blue-600" /> },
    { id: 'XLSX' as const, label: 'Spreadsheets (.xlsx)', icon: <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" /> },
    { id: 'PPTX' as const, label: 'Presentations (.pptx)', icon: <Presentation className="w-3.5 h-3.5 text-amber-600" /> },
    { id: 'TXT' as const, label: 'Text Notes (.txt)', icon: <FileText className="w-3.5 h-3.5 text-slate-500" /> },
    { id: 'PDF' as const, label: 'PDF Documents (.pdf)', icon: <FileText className="w-3.5 h-3.5 text-rose-600" /> },
  ];

  const filteredFiles = files.filter((f) => {
    if (selectedTagFilter && !f.tags?.includes(selectedTagFilter)) {
      return false;
    }
    if (selectedTypeFilter === 'FOLDERS') {
      return f.is_folder;
    }
    if (selectedTypeFilter === 'DOCX') {
      return !f.is_folder && f.name.toLowerCase().endsWith('.docx');
    }
    if (selectedTypeFilter === 'XLSX') {
      return !f.is_folder && (f.name.toLowerCase().endsWith('.xlsx') || f.name.toLowerCase().endsWith('.csv'));
    }
    if (selectedTypeFilter === 'PPTX') {
      return !f.is_folder && f.name.toLowerCase().endsWith('.pptx');
    }
    if (selectedTypeFilter === 'TXT') {
      return !f.is_folder && f.name.toLowerCase().endsWith('.txt');
    }
    if (selectedTypeFilter === 'PDF') {
      return !f.is_folder && f.name.toLowerCase().endsWith('.pdf');
    }
    return true;
  });

  const folderCount = filteredFiles.filter((f) => f.is_folder).length;
  const fileCount = filteredFiles.filter((f) => !f.is_folder).length;

  const renderMenuActions = (file: FileItem) => {
    if (viewMode === 'TRASH') {
      return (
        <>
          <button
            type="button"
            onClick={() => {
              setActiveRowMenuId(null);
              handleRestore(file);
            }}
            className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-slate-50 text-xs font-medium text-slate-800 hover:text-emerald-700 transition-colors cursor-pointer"
          >
            <RotateCcw className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>Restore Item</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setActiveRowMenuId(null);
              handleDelete(file);
            }}
            className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-red-50 text-xs font-medium text-red-600 transition-colors cursor-pointer"
          >
            <Trash2 className="w-4 h-4 text-red-600 shrink-0" />
            <span>Delete Permanently</span>
          </button>
        </>
      );
    }

    return (
      <>
        <button
          type="button"
          onClick={() => {
            setActiveRowMenuId(null);
            if (file.is_folder) {
              handleOpenFolder(file);
            } else {
              navigate(`/editor/${file.id}`);
            }
          }}
          className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-slate-50 text-xs font-medium text-slate-800 hover:text-blue-600 transition-colors cursor-pointer"
        >
          <ExternalLink className="w-4 h-4 text-slate-500 shrink-0" />
          <span>{file.is_folder ? 'Open Folder' : 'Open in Editor'}</span>
        </button>

        <button
          type="button"
          onClick={() => {
            setActiveRowMenuId(null);
            setSelectedItem(file);
            setIsDetailsOpen(true);
            localStorage.setItem('ethiooffice_details_panel_open', 'true');
          }}
          className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-slate-50 text-xs font-medium text-slate-800 hover:text-blue-600 transition-colors cursor-pointer"
        >
          <Info className="w-4 h-4 text-slate-500 shrink-0" />
          <span>Details & Versions</span>
        </button>

        {!file.is_folder && (
          <a
            href={`/api/v1/files/${file.id}/download`}
            onClick={() => setActiveRowMenuId(null)}
            className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-slate-50 text-xs font-medium text-slate-800 hover:text-blue-600 transition-colors"
          >
            <Download className="w-4 h-4 text-slate-500 shrink-0" />
            <span>Download</span>
          </a>
        )}

        <button
          type="button"
          onClick={() => {
            setActiveRowMenuId(null);
            setTargetFile(file);
            setShowShareModal(true);
          }}
          className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-slate-50 text-xs font-medium text-slate-800 hover:text-blue-600 transition-colors cursor-pointer"
        >
          <Share2 className="w-4 h-4 text-slate-500 shrink-0" />
          <span>Share & Permissions</span>
        </button>

        {!file.is_folder && (
          <button
            type="button"
            onClick={() => {
              setActiveRowMenuId(null);
              setTargetFile(file);
              setSelectedTagIds(
                availableTags
                  .filter((t) => file.tags?.includes(t.name))
                  .map((t) => t.id)
              );
              setShowTagModal(true);
            }}
            className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-slate-50 text-xs font-medium text-slate-800 hover:text-blue-600 transition-colors cursor-pointer"
          >
            <TagIcon className="w-4 h-4 text-slate-500 shrink-0" />
            <span>Assign Tags</span>
          </button>
        )}

        <button
          type="button"
          onClick={() => {
            setActiveRowMenuId(null);
            setTargetFile(file);
            setRenameValue(file.name);
            setShowRenameModal(true);
          }}
          className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-slate-50 text-xs font-medium text-slate-800 hover:text-blue-600 transition-colors cursor-pointer"
        >
          <Edit2 className="w-4 h-4 text-slate-500 shrink-0" />
          <span>Rename</span>
        </button>

        <button
          type="button"
          onClick={() => {
            setActiveRowMenuId(null);
            handleToggleStar(file);
          }}
          className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-slate-50 text-xs font-medium text-slate-800 hover:text-blue-600 transition-colors cursor-pointer"
        >
          <Star className={`w-4 h-4 ${file.is_starred ? 'fill-amber-400 text-amber-400' : 'text-slate-500'} shrink-0`} />
          <span>{file.is_starred ? 'Remove Star' : 'Add to Starred'}</span>
        </button>

        <div className="border-t border-slate-100 my-1" />

        <button
          type="button"
          onClick={() => {
            setActiveRowMenuId(null);
            handleDelete(file);
          }}
          className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-red-50 text-xs font-medium text-red-600 transition-colors cursor-pointer"
        >
          <Trash2 className="w-4 h-4 text-red-600 shrink-0" />
          <span>Move to Recycle Bin</span>
        </button>
      </>
    );
  };

  return (
    <div className="space-y-3 select-none font-sans">
      {/* Location Breadcrumbs & Action Buttons on the Same Line */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-2.5 border-b border-slate-200/80">
        {/* Left: Location / Breadcrumbs (Same size as navbar title, perfectly dialed, no bold) */}
        <div className="flex items-center gap-1.5 overflow-x-auto min-w-0">
          {viewMode !== 'STARRED' && viewMode !== 'RECENT' ? (
            breadcrumbs.map((b, idx) => (
              <React.Fragment key={b.name + idx}>
                {idx > 0 && <ChevronRight className="w-3.5 h-3.5 text-slate-300 shrink-0" />}
                <button
                  onClick={() => handleNavigateBreadcrumb(idx)}
                  className={`transition-colors whitespace-nowrap text-[13px] sm:text-[14px] md:text-[16px] lg:text-[18px] font-normal ${
                    idx === breadcrumbs.length - 1
                      ? 'text-slate-800 cursor-default'
                      : 'text-slate-400 hover:text-slate-700'
                  }`}
                >
                  <span>{b.name}</span>
                </button>
              </React.Fragment>
            ))
          ) : (
            <div className="flex items-center gap-2">
              {viewMode === 'STARRED' ? (
                <>
                  <Star className="w-4 h-4 text-amber-500 fill-amber-400 shrink-0" />
                  <span className="text-slate-800 text-[13px] sm:text-[14px] md:text-[16px] lg:text-[18px] font-normal">
                    Favorites & Starred
                  </span>
                </>
              ) : (
                <>
                  <Clock className="w-4 h-4 text-blue-600 shrink-0" />
                  <span className="text-slate-800 text-[13px] sm:text-[14px] md:text-[16px] lg:text-[18px] font-normal">
                    Recent Files
                  </span>
                </>
              )}
            </div>
          )}
        </div>

        {/* Right: Action Buttons (Aligned on the exact same line) */}
        <div className="flex items-center justify-end gap-2 shrink-0">
          {viewMode === 'TRASH' ? (
            <Button
              variant="danger"
              size="sm"
              leftIcon={<Trash2 className="w-4 h-4" />}
              onClick={() => setShowEmptyTrashModal(true)}
              disabled={files.length === 0}
            >
              Empty Recycle Bin
            </Button>
          ) : viewMode === 'PERSONAL' || viewMode === 'COMPANY' ? (
            <>
              {/* New Folder Button with Neutral Icon */}
              <Button
                variant="subtle"
                size="sm"
                leftIcon={<FolderPlus className="w-4 h-4 text-slate-600" />}
                onClick={() => setShowFolderModal(true)}
              >
                New Folder
              </Button>

              {/* New Document Button with Dropdown Menu */}
              <div className="relative" ref={newDocMenuRef}>
                <Button
                  variant="subtle"
                  size="sm"
                  leftIcon={<FilePlus2 className="w-4 h-4 text-slate-600" />}
                  rightIcon={<ChevronDown className="w-3.5 h-3.5 text-slate-400 -mr-0.5" />}
                  onClick={() => setShowNewDocMenu((prev) => !prev)}
                  isLoading={isCreatingDoc}
                >
                  New Document
                </Button>

                {showNewDocMenu && (
                  <div className="absolute right-0 top-full mt-1.5 w-60 rounded-xl bg-white shadow-xl border border-slate-200/90 py-1.5 z-40 animate-scale-up font-sans">
                    <p className="px-3 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                      Create Document
                    </p>
                    {documentTypeOptions.map((type) => (
                      <button
                        key={type.id}
                        type="button"
                        onClick={() => handleQuickCreateDocument(type.id)}
                        className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-slate-50 transition-colors group cursor-pointer"
                      >
                        <div className="flex items-center gap-2.5 min-w-0">
                          {type.icon}
                          <span className="text-xs font-medium text-slate-800 group-hover:text-blue-600 transition-colors truncate">
                            {type.name}
                          </span>
                        </div>
                        <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded ${type.badgeColor}`}>
                          {type.extension}
                        </span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Upload File Button */}
              <Button
                variant="primary"
                size="sm"
                leftIcon={<Upload className="w-4 h-4" />}
                onClick={() => fileInputRef.current?.click()}
              >
                Upload File
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                onChange={handleFileUpload}
              />
            </>
          ) : null}
        </div>
      </div>

      {/* Sub-Toolbar: Filtering Controls (Left) & Item Count / Layout Switcher (Right) */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 px-0.5">
        {/* Left Side: Tag & Type Filter Dropdowns */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* 1. Tag Filter Dropdown */}
          {availableTags.length > 0 && viewMode !== 'TRASH' && (
            <div className="relative" ref={tagMenuRef}>
              <button
                type="button"
                onClick={() => {
                  setShowTagFilterMenu((prev) => !prev);
                  setShowTypeFilterMenu(false);
                }}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-xl border transition-all ${
                  selectedTagFilter
                    ? 'bg-blue-50 border-blue-300 text-blue-700 font-semibold shadow-2xs'
                    : 'bg-white border-slate-200/80 text-slate-700 hover:bg-slate-50 font-medium'
                }`}
              >
                <TagIcon className="w-3.5 h-3.5 text-slate-500" />
                <span>{selectedTagFilter ? `Tag: ${selectedTagFilter}` : 'Tag'}</span>
                <ChevronDown className="w-3 h-3 text-slate-400" />
              </button>

              {showTagFilterMenu && (
                <div className="absolute left-0 top-full mt-1.5 w-48 rounded-xl bg-white shadow-xl border border-slate-200/90 py-1.5 z-40 animate-scale-up">
                  <p className="px-3 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                    Filter by Tag
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedTagFilter(null);
                      setShowTagFilterMenu(false);
                    }}
                    className="w-full flex items-center justify-between px-3 py-1.5 text-xs text-left text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    <span>All Tags</span>
                    {selectedTagFilter === null && <Check className="w-3.5 h-3.5 text-blue-600" />}
                  </button>
                  <div className="border-t border-slate-100 my-1" />
                  {availableTags.map((tag) => (
                    <button
                      key={tag.id}
                      type="button"
                      onClick={() => {
                        setSelectedTagFilter(tag.name);
                        setShowTagFilterMenu(false);
                      }}
                      className="w-full flex items-center justify-between px-3 py-1.5 text-xs text-left text-slate-700 hover:bg-slate-50 transition-colors"
                    >
                      <div className="flex items-center gap-2 truncate">
                        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: tag.color }} />
                        <span className="truncate">{tag.name}</span>
                      </div>
                      {selectedTagFilter === tag.name && <Check className="w-3.5 h-3.5 text-blue-600 shrink-0" />}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 2. Type Filter Dropdown */}
          <div className="relative" ref={typeMenuRef}>
            <button
              type="button"
              onClick={() => {
                setShowTypeFilterMenu((prev) => !prev);
                setShowTagFilterMenu(false);
              }}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-xl border transition-all ${
                selectedTypeFilter !== 'ALL'
                  ? 'bg-blue-50 border-blue-300 text-blue-700 font-semibold shadow-2xs'
                  : 'bg-white border-slate-200/80 text-slate-700 hover:bg-slate-50 font-medium'
              }`}
            >
              <Filter className="w-3.5 h-3.5 text-slate-500" />
              <span>{getTypeFilterLabel(selectedTypeFilter)}</span>
              <ChevronDown className="w-3 h-3 text-slate-400" />
            </button>

            {showTypeFilterMenu && (
              <div className="absolute left-0 top-full mt-1.5 w-52 rounded-xl bg-white shadow-xl border border-slate-200/90 py-1.5 z-40 animate-scale-up">
                <p className="px-3 py-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                  Filter by Type
                </p>
                {typeFilterOptions.map((opt) => (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => {
                      setSelectedTypeFilter(opt.id);
                      setShowTypeFilterMenu(false);
                    }}
                    className="w-full flex items-center justify-between px-3 py-1.5 text-xs text-left text-slate-700 hover:bg-slate-50 transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      {opt.icon}
                      <span>{opt.label}</span>
                    </div>
                    {selectedTypeFilter === opt.id && <Check className="w-3.5 h-3.5 text-blue-600 shrink-0" />}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Reset Filters button */}
          {(selectedTagFilter || selectedTypeFilter !== 'ALL') && (
            <button
              type="button"
              onClick={() => {
                setSelectedTagFilter(null);
                setSelectedTypeFilter('ALL');
              }}
              className="flex items-center gap-1 text-[11px] font-semibold text-slate-400 hover:text-slate-700 px-2 py-1 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
            >
              <X className="w-3 h-3" />
              <span>Reset</span>
            </button>
          )}
        </div>

        {/* Right Side: Item Count & List/Grid Layout Toggle */}
        <div className="flex items-center gap-3 self-end sm:self-auto shrink-0">
          <span className="text-xs text-slate-400 font-medium whitespace-nowrap">
            {filteredFiles.length === 0
              ? '0 items'
              : `${filteredFiles.length} item${filteredFiles.length > 1 ? 's' : ''}${
                  folderCount > 0 && fileCount > 0
                    ? ` (${folderCount} folder${folderCount > 1 ? 's' : ''}, ${fileCount} file${fileCount > 1 ? 's' : ''})`
                    : ''
                }`}
          </span>

          <div className="flex items-center bg-slate-100 p-0.5 rounded-lg border border-slate-200/70">
            <button
              type="button"
              onClick={() => handleToggleLayout('list')}
              title="List View"
              className={`p-1 rounded-md transition-all cursor-pointer ${
                displayLayout === 'list'
                  ? 'bg-white shadow-2xs text-blue-600 font-semibold'
                  : 'text-slate-400 hover:text-slate-700'
              }`}
            >
              <List className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => handleToggleLayout('grid')}
              title="Grid View"
              className={`p-1 rounded-md transition-all cursor-pointer ${
                displayLayout === 'grid'
                  ? 'bg-white shadow-2xs text-blue-600 font-semibold'
                  : 'text-slate-400 hover:text-slate-700'
              }`}
            >
              <LayoutGrid className="w-4 h-4" />
            </button>
          </div>

          {/* Details Inspector Toggle */}
          <button
            type="button"
            onClick={handleToggleDetails}
            title={isDetailsOpen ? 'Hide Details Inspector' : 'Show Details Inspector'}
            className={`p-1.5 rounded-lg border transition-all cursor-pointer ${
              isDetailsOpen
                ? 'bg-blue-50 border-blue-300 text-blue-600 shadow-2xs'
                : 'bg-white border-slate-200/80 text-slate-500 hover:text-slate-800 hover:bg-slate-50'
            }`}
          >
            <Info className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Files Area with Collapsible Right-Side Details Inspector Panel */}
      <div className="flex flex-col lg:flex-row gap-4 items-start">
        <div
          onContextMenu={openCanvasContextMenu}
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              setSelectedItem(null);
            }
          }}
          className="flex-1 w-full min-w-0 bg-white rounded-2xl shadow-xs border border-slate-200/80 p-2 sm:p-3 min-h-[420px]"
        >
        {isLoading ? (
          <div className="py-20 text-center text-xs font-medium text-slate-400">Loading files...</div>
        ) : filteredFiles.length === 0 ? (
          <div
            onContextMenu={openCanvasContextMenu}
            className="flex flex-col items-center justify-center py-20 space-y-2 cursor-default select-none"
          >
            <Folder className="w-10 h-10 text-slate-300 mx-auto" />
            <p className="text-sm font-bold text-slate-800">This folder is empty</p>
            <p className="text-xs text-slate-400">Upload a document, create a new file or right-click anywhere to get started.</p>
          </div>
        ) : displayLayout === 'grid' ? (
          /* Grid View */
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-2.5 sm:gap-3">
            {filteredFiles.map((file) => {
              const isSelected = selectedItem?.id === file.id;
              return (
                <div
                  key={file.id}
                  onClick={() => setSelectedItem(file)}
                  onContextMenu={(e) => {
                    setSelectedItem(file);
                    openRowContextMenu(e, file);
                  }}
                  onDoubleClick={() => {
                    if (file.is_folder) {
                      handleOpenFolder(file);
                    } else {
                      navigate(`/editor/${file.id}`);
                    }
                  }}
                  className={`group relative flex flex-col justify-between p-3.5 rounded-2xl border transition-all cursor-pointer select-none ${
                    isSelected
                      ? 'bg-blue-50/40 border-blue-500 ring-2 ring-blue-500/20 shadow-sm'
                      : 'bg-white border-slate-200/80 hover:border-blue-400 hover:shadow-md'
                  }`}
                >
                {/* Top: Icon + Star & Three-dots */}
                <div className="flex items-start justify-between gap-1.5">
                  <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100/90 group-hover:bg-blue-50/70 transition-colors">
                    {getFileIcon(file, 'w-6 h-6')}
                  </div>

                  <div className="flex items-center gap-0.5">
                    {viewMode !== 'TRASH' && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleToggleStar(file);
                        }}
                        className={`p-1 rounded-md text-slate-300 hover:text-amber-500 transition-colors cursor-pointer ${
                          file.is_starred ? 'text-amber-400 opacity-100' : 'opacity-0 group-hover:opacity-100'
                        }`}
                        title={file.is_starred ? 'Remove Star' : 'Star Document'}
                      >
                        <Star
                          className={`w-3.5 h-3.5 ${
                            file.is_starred ? 'fill-amber-400 text-amber-400' : ''
                          }`}
                        />
                      </button>
                    )}

                    {/* Three Dots Action Button */}
                    <div className="relative">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveRowMenuId(activeRowMenuId === file.id ? null : file.id);
                        }}
                        className="p-1 rounded-md text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
                        title="More options"
                      >
                        <MoreVertical className="w-3.5 h-3.5" />
                      </button>

                      {/* Three-dots Menu in Grid View */}
                      {activeRowMenuId === file.id && (
                        <div
                          onClick={(e) => e.stopPropagation()}
                          className="absolute right-0 top-full mt-1 w-52 rounded-xl bg-white shadow-xl border border-slate-200/90 py-1.5 z-40 animate-scale-up font-sans text-left"
                        >
                          {renderMenuActions(file)}
                        </div>
                      )}
                    </div>
                  </div>
                </div>

                {/* Middle: Name & Lock */}
                <div className="mt-3 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span
                      className="text-xs font-semibold text-slate-800 group-hover:text-blue-600 transition-colors truncate"
                      title={file.name}
                    >
                      {file.name}
                    </span>
                    {file.is_locked && <Lock className="w-3 h-3 text-amber-600 shrink-0" />}
                  </div>

                  {/* Tags if any */}
                  {file.tags && file.tags.length > 0 && (
                    <div className="flex items-center gap-1 mt-1 overflow-hidden">
                      {file.tags.slice(0, 2).map((tg) => (
                        <span
                          key={tg}
                          className="text-[9px] font-semibold bg-slate-100 text-slate-600 px-1.5 py-0.5 rounded truncate"
                        >
                          {tg}
                        </span>
                      ))}
                      {file.tags.length > 2 && (
                        <span className="text-[9px] text-slate-400 font-medium">
                          +{file.tags.length - 2}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Bottom: Meta info */}
                <div className="flex items-center justify-between text-[11px] text-slate-400 font-medium mt-3 pt-2 border-t border-slate-100">
                  <span>{file.is_folder ? `${file.file_count || 0} items` : formatFileSize(file.size_bytes)}</span>
                  <span className="truncate max-w-[80px] text-right">
                    {file.ec_created_at || (file.created_at ? new Date(file.created_at).toLocaleDateString() : '')}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
        ) : (
          /* List View */
          <div className="space-y-1 sm:space-y-1.5">
            {filteredFiles.map((file) => {
              const isSelected = selectedItem?.id === file.id;
              return (
                <div
                  key={file.id}
                  onClick={() => setSelectedItem(file)}
                  onContextMenu={(e) => {
                    setSelectedItem(file);
                    openRowContextMenu(e, file);
                  }}
                  onDoubleClick={() => {
                    if (file.is_folder) {
                      handleOpenFolder(file);
                    } else {
                      navigate(`/editor/${file.id}`);
                    }
                  }}
                  className={`flex items-center justify-between p-3 sm:px-4 rounded-xl border transition-all group cursor-pointer ${
                    isSelected
                      ? 'bg-blue-50/50 border-blue-500 ring-1 ring-blue-500/30'
                      : 'border-transparent hover:border-slate-200/70 hover:bg-slate-50/80'
                  }`}
                >
                {/* Left: Star + Icon + Name + Tags */}
                <div className="flex items-center min-w-0 flex-1">
                  {viewMode !== 'TRASH' && (
                    <div
                      className={`overflow-hidden transition-all duration-300 ease-out shrink-0 flex items-center justify-center ${
                        file.is_starred
                          ? 'w-6 opacity-100 mr-2.5'
                          : 'w-0 opacity-0 group-hover:w-6 group-hover:opacity-100 group-hover:mr-2.5'
                      }`}
                    >
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleToggleStar(file);
                        }}
                        className={`p-0.5 rounded transition-colors duration-200 hover:text-amber-500 cursor-pointer ${
                          file.is_starred ? 'text-amber-400' : 'text-slate-300'
                        }`}
                        title={file.is_starred ? 'Remove Star' : 'Star Document'}
                      >
                        <Star
                          className={`w-4 h-4 transition-transform duration-300 ease-out ${
                            file.is_starred ? 'fill-amber-400 text-amber-400' : 'group-hover:scale-105'
                          }`}
                        />
                      </button>
                    </div>
                  )}

                  <div className="shrink-0 mr-3 transition-transform duration-300 ease-out group-hover:scale-105 group-hover:rotate-2">
                    {getFileIcon(file, 'w-5 h-5')}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-slate-900 group-hover:text-blue-600 transition-colors truncate">
                        {file.name}
                      </span>
                      {file.is_locked && (
                        <span className="inline-flex items-center gap-1 text-[10px] bg-amber-50 text-amber-700 px-2 py-0.5 rounded-md border border-amber-200/70 shrink-0 font-medium">
                          <Lock className="w-3 h-3" />
                          <span>Locked by {file.lock_info?.locked_by_name || 'User'}</span>
                        </span>
                      )}
                    </div>
                    {/* Tags row */}
                    {file.tags && file.tags.length > 0 && (
                      <div className="flex items-center gap-1.5 mt-1">
                        {file.tags.map((tg) => (
                          <span
                            key={tg}
                            className="text-[10px] font-semibold bg-slate-100 text-slate-600 px-2 py-0.5 rounded-md border border-slate-200/60"
                          >
                            {tg}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Right: Size, Date, Actions */}
                <div className="flex items-center gap-4 sm:gap-6 shrink-0 text-xs text-slate-400">
                  <span className="w-16 sm:w-20 text-right font-medium text-slate-600">
                    {file.is_folder ? `${file.file_count || 0} items` : formatFileSize(file.size_bytes)}
                  </span>

                  <span className="w-28 sm:w-32 text-right hidden sm:inline font-medium text-slate-500">
                    {file.ec_created_at || new Date(file.created_at).toLocaleDateString()}
                  </span>

                  {/* Actions Dropdown / Three-Dots Button */}
                  <div className="flex items-center gap-1">
                    {viewMode === 'TRASH' ? (
                      <>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleRestore(file);
                          }}
                          className="p-1.5 text-slate-400 hover:text-emerald-700 rounded-lg hover:bg-slate-100 transition-colors"
                          title="Restore"
                        >
                          <RotateCcw className="w-4 h-4" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(file);
                          }}
                          className="p-1.5 text-slate-400 hover:text-red-600 rounded-lg hover:bg-slate-100 transition-colors"
                          title="Delete Permanently"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </>
                    ) : (
                      <>
                        {!file.is_folder && (
                          <a
                            href={`/api/v1/files/${file.id}/download`}
                            onClick={(e) => e.stopPropagation()}
                            className="p-1.5 text-slate-400 hover:text-blue-600 rounded-lg hover:bg-slate-100 transition-colors opacity-0 group-hover:opacity-100 hidden sm:inline-block"
                            title="Download"
                          >
                            <Download className="w-4 h-4" />
                          </a>
                        )}

                        {/* Three-Dots Menu Button */}
                        <div className="relative">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setActiveRowMenuId(activeRowMenuId === file.id ? null : file.id);
                            }}
                            className={`p-1.5 rounded-lg transition-colors ${
                              activeRowMenuId === file.id
                                ? 'bg-slate-100 text-slate-800'
                                : 'text-slate-400 hover:text-slate-700 hover:bg-slate-100'
                            }`}
                            title="More options"
                          >
                            <MoreVertical className="w-4 h-4" />
                          </button>

                          {/* Dropdown Menu */}
                          {activeRowMenuId === file.id && (
                            <div
                              onClick={(e) => e.stopPropagation()}
                              className="absolute right-0 top-full mt-1 w-52 rounded-xl bg-white shadow-xl border border-slate-200/90 py-1.5 z-40 animate-scale-up font-sans text-left"
                            >
                              {renderMenuActions(file)}
                            </div>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>

      {isDetailsOpen && (
        <FileDetailsPanel
          item={selectedItem}
          currentFolder={breadcrumbs[breadcrumbs.length - 1]}
          driveType={viewMode === 'COMPANY' ? 'COMPANY' : 'PERSONAL'}
          isOpen={isDetailsOpen}
          onClose={() => {
            setIsDetailsOpen(false);
            localStorage.setItem('ethiooffice_details_panel_open', 'false');
          }}
          onItemUpdated={handleItemUpdated}
          onNavigateFolder={handleOpenFolder}
          onOpenEditor={(f) => navigate(`/editor/${f.id}`)}
          onManageTags={(f) => {
            setTargetFile(f);
            setSelectedTagIds(
              availableTags
                .filter((t) => f.tags?.includes(t.name))
                .map((t) => t.id)
            );
            setShowTagModal(true);
          }}
          onToggleStar={handleToggleStar}
        />
      )}
    </div>

      {/* 1. New Folder Modal */}
      <Modal
        isOpen={showFolderModal}
        onClose={() => setShowFolderModal(false)}
        icon={<FolderPlus className="w-5 h-5 text-slate-700" />}
        title="Create New Folder"
        description={`Location: ${breadcrumbs.map((b) => b.name).join(' / ')}`}
      >
        <form onSubmit={handleCreateFolder} className="space-y-4">
          <Input
            placeholder="Folder name (e.g. Finance, Contracts, Projects)"
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            leftIcon={<Folder className="w-4 h-4 text-slate-400" />}
            required
            autoFocus
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" type="button" onClick={() => setShowFolderModal(false)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit">
              Create Folder
            </Button>
          </div>
        </form>
      </Modal>

      {/* 2. Create New Document Modal (Windows Explorer / EuroOffice Style) */}
      <Modal
        isOpen={showDocModal}
        onClose={() => setShowDocModal(false)}
        icon={<FilePlus2 className="w-5 h-5 text-slate-700" />}
        title="Create New Document"
        description={`Location: ${breadcrumbs.map((b) => b.name).join(' / ')}`}
        maxWidth="lg"
      >
        <form onSubmit={(e) => handleCreateDocument(e, false)} className="space-y-4">
          {/* Document Type Selector Cards */}
          <div className="space-y-2">
            <label className="block text-xs font-bold text-slate-700">
              Select Document Format:
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {documentTypeOptions.map((opt) => {
                const isSelected = newDocType === opt.id;
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => setNewDocType(opt.id)}
                    className={`p-3 rounded-xl border text-left transition-all ${
                      isSelected
                        ? 'border-blue-600 bg-blue-50/80 shadow-2xs ring-1 ring-blue-500'
                        : 'border-slate-200/80 hover:bg-slate-50 bg-white'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        {opt.icon}
                        <span className="font-bold text-slate-900 text-xs sm:text-sm">
                          {opt.name}
                        </span>
                      </div>
                      <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded-md ${opt.badgeColor}`}>
                        {opt.extension}
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-400 font-medium">
                      {opt.description}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Document Name Input */}
          <div className="space-y-1.5 pt-2">
            <label className="block text-xs font-bold text-slate-700">
              Document Name:
            </label>
            <Input
              placeholder="e.g. Quarterly Strategy Plan"
              value={newDocName}
              onChange={(e) => setNewDocName(e.target.value)}
              required
              autoFocus
            />
            {newDocName.trim() && (
              <p className="text-[11px] text-slate-500 font-medium">
                Will be saved as: <span className="font-mono font-bold text-blue-600">{newDocName.trim().endsWith(`.${newDocType}`) ? newDocName.trim() : `${newDocName.trim()}.${newDocType}`}</span>
              </p>
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex items-center justify-between pt-3 border-t border-slate-100">
            <Button variant="ghost" type="button" onClick={() => setShowDocModal(false)}>
              Cancel
            </Button>
            <div className="flex items-center gap-2">
              <Button
                variant="subtle"
                type="submit"
                isLoading={isCreatingDoc}
              >
                Create
              </Button>
              <Button
                variant="primary"
                type="button"
                onClick={(e) => handleCreateDocument(e, true)}
                isLoading={isCreatingDoc}
                leftIcon={<ExternalLink className="w-3.5 h-3.5" />}
              >
                Create & Open
              </Button>
            </div>
          </div>
        </form>
      </Modal>

      {/* 3. Rename Modal */}
      <Modal
        isOpen={showRenameModal}
        onClose={() => setShowRenameModal(false)}
        title="Rename Item"
      >
        <form onSubmit={handleRenameSubmit} className="space-y-4">
          <Input
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            required
            autoFocus
          />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" type="button" onClick={() => setShowRenameModal(false)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit">
              Save Changes
            </Button>
          </div>
        </form>
      </Modal>

      {/* 4. Assign Tags Modal */}
      <Modal
        isOpen={showTagModal}
        onClose={() => setShowTagModal(false)}
        title="Assign Classification Tags"
        description={targetFile?.name}
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2 max-h-60 overflow-y-auto">
            {availableTags.map((tag) => {
              const isSelected = selectedTagIds.includes(tag.id);
              return (
                <button
                  key={tag.id}
                  type="button"
                  onClick={() =>
                    setSelectedTagIds((prev) =>
                      isSelected ? prev.filter((id) => id !== tag.id) : [...prev, tag.id]
                    )
                  }
                  className={`flex items-center justify-between p-2.5 rounded-xl border text-xs text-left transition-all font-medium ${
                    isSelected
                      ? 'border-blue-600 bg-blue-50/80 text-blue-900 shadow-2xs font-semibold'
                      : 'border-slate-200/80 hover:bg-slate-50 text-slate-700'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: tag.color }} />
                    <span>{tag.name}</span>
                  </div>
                  {isSelected && <Check className="w-3.5 h-3.5 text-blue-600" />}
                </button>
              );
            })}
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button variant="ghost" onClick={() => setShowTagModal(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleTagAssignSubmit}>
              Save Tags
            </Button>
          </div>
        </div>
      </Modal>

      {/* 5. Empty Recycle Bin Confirmation Modal */}
      <Modal
        isOpen={showEmptyTrashModal}
        onClose={() => setShowEmptyTrashModal(false)}
        title="Empty Recycle Bin?"
        description="This action will permanently delete all files currently in the Recycle Bin and free up storage space. This action cannot be undone."
      >
        <div className="flex justify-end gap-2 pt-4">
          <Button variant="ghost" onClick={() => setShowEmptyTrashModal(false)}>
            Cancel
          </Button>
          <Button variant="danger" onClick={handleEmptyTrash}>
            Empty Recycle Bin
          </Button>
        </div>
      </Modal>

      {/* 6. Document & Folder Sharing Modal */}
      <ShareModal
        isOpen={showShareModal}
        onClose={() => {
          setShowShareModal(false);
          setTargetFile(null);
        }}
        file={targetFile}
      />

      {/* 7. Canvas Empty Space Right-Click Menu */}
      {canvasContextMenu && (
        <div
          style={{ top: `${canvasContextMenu.y}px`, left: `${canvasContextMenu.x}px` }}
          className="fixed z-50 w-56 rounded-xl bg-white shadow-2xl border border-slate-200/90 py-1.5 animate-scale-up font-sans select-none text-left"
        >
          <button
            type="button"
            onClick={() => {
              setCanvasContextMenu(null);
              setShowFolderModal(true);
            }}
            className="w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-slate-50 text-xs font-medium text-slate-800 hover:text-blue-600 transition-colors cursor-pointer"
          >
            <FolderPlus className="w-4 h-4 text-slate-600 shrink-0" />
            <span>New Folder</span>
          </button>

          <div className="border-t border-slate-100 my-1" />

          <p className="px-3 py-0.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
            New Document
          </p>
          {documentTypeOptions.map((type) => (
            <button
              key={type.id}
              type="button"
              onClick={() => {
                setCanvasContextMenu(null);
                handleQuickCreateDocument(type.id);
              }}
              className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-slate-50 transition-colors group cursor-pointer"
            >
              <div className="flex items-center gap-2.5 min-w-0">
                {type.icon}
                <span className="text-xs font-medium text-slate-800 group-hover:text-blue-600 transition-colors truncate">
                  {type.name}
                </span>
              </div>
              <span className={`text-[10px] font-mono font-bold px-1.5 py-0.5 rounded ${type.badgeColor}`}>
                {type.extension}
              </span>
            </button>
          ))}

          <div className="border-t border-slate-100 my-1" />

          <button
            type="button"
            onClick={() => {
              setCanvasContextMenu(null);
              fileInputRef.current?.click();
            }}
            className="w-full flex items-center gap-2.5 px-3 py-2 text-left hover:bg-slate-50 text-xs font-medium text-slate-800 hover:text-blue-600 transition-colors cursor-pointer"
          >
            <Upload className="w-4 h-4 text-slate-600 shrink-0" />
            <span>Upload File</span>
          </button>
        </div>
      )}

      {/* 8. File & Folder Item Right-Click Menu */}
      {rowContextMenu && (
        <div
          style={{ top: `${rowContextMenu.y}px`, left: `${rowContextMenu.x}px` }}
          className="fixed z-50 w-52 rounded-xl bg-white shadow-2xl border border-slate-200/90 py-1.5 animate-scale-up font-sans select-none text-left"
        >
          {viewMode === 'TRASH' ? (
            <>
              <button
                type="button"
                onClick={() => {
                  const f = rowContextMenu.file;
                  setRowContextMenu(null);
                  handleRestore(f);
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-slate-50 text-xs font-medium text-emerald-700 transition-colors cursor-pointer"
              >
                <RotateCcw className="w-4 h-4 shrink-0" />
                <span>Restore File</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  const f = rowContextMenu.file;
                  setRowContextMenu(null);
                  handleDelete(f);
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-red-50 text-xs font-medium text-red-600 transition-colors cursor-pointer"
              >
                <Trash2 className="w-4 h-4 shrink-0" />
                <span>Delete Permanently</span>
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                onClick={() => {
                  const f = rowContextMenu.file;
                  setRowContextMenu(null);
                  if (f.is_folder) {
                    handleOpenFolder(f);
                  } else {
                    navigate(`/editor/${f.id}`);
                  }
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-slate-50 text-xs font-medium text-slate-800 hover:text-blue-600 transition-colors cursor-pointer"
              >
                <ExternalLink className="w-4 h-4 text-slate-500 shrink-0" />
                <span>{rowContextMenu.file.is_folder ? 'Open Folder' : 'Open in Editor'}</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  const f = rowContextMenu.file;
                  setRowContextMenu(null);
                  setSelectedItem(f);
                  setIsDetailsOpen(true);
                  localStorage.setItem('ethiooffice_details_panel_open', 'true');
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-slate-50 text-xs font-medium text-slate-800 hover:text-blue-600 transition-colors cursor-pointer"
              >
                <Info className="w-4 h-4 text-slate-500 shrink-0" />
                <span>Details & Versions</span>
              </button>

              {!rowContextMenu.file.is_folder && (
                <a
                  href={`/api/v1/files/${rowContextMenu.file.id}/download`}
                  onClick={() => setRowContextMenu(null)}
                  className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-slate-50 text-xs font-medium text-slate-800 hover:text-blue-600 transition-colors"
                >
                  <Download className="w-4 h-4 text-slate-500 shrink-0" />
                  <span>Download</span>
                </a>
              )}

              <button
                type="button"
                onClick={() => {
                  const f = rowContextMenu.file;
                  setRowContextMenu(null);
                  setTargetFile(f);
                  setShowShareModal(true);
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-slate-50 text-xs font-medium text-slate-800 hover:text-blue-600 transition-colors cursor-pointer"
              >
                <Share2 className="w-4 h-4 text-slate-500 shrink-0" />
                <span>Share & Permissions</span>
              </button>

              {!rowContextMenu.file.is_folder && (
                <button
                  type="button"
                  onClick={() => {
                    const f = rowContextMenu.file;
                    setRowContextMenu(null);
                    setTargetFile(f);
                    setSelectedTagIds(
                      availableTags
                        .filter((t) => f.tags?.includes(t.name))
                        .map((t) => t.id)
                    );
                    setShowTagModal(true);
                  }}
                  className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-slate-50 text-xs font-medium text-slate-800 hover:text-blue-600 transition-colors cursor-pointer"
                >
                  <TagIcon className="w-4 h-4 text-slate-500 shrink-0" />
                  <span>Assign Tags</span>
                </button>
              )}

              <button
                type="button"
                onClick={() => {
                  const f = rowContextMenu.file;
                  setRowContextMenu(null);
                  setTargetFile(f);
                  setRenameValue(f.name);
                  setShowRenameModal(true);
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-slate-50 text-xs font-medium text-slate-800 hover:text-blue-600 transition-colors cursor-pointer"
              >
                <Edit2 className="w-4 h-4 text-slate-500 shrink-0" />
                <span>Rename</span>
              </button>

              <div className="border-t border-slate-100 my-1" />

              <button
                type="button"
                onClick={() => {
                  const f = rowContextMenu.file;
                  setRowContextMenu(null);
                  handleToggleStar(f);
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-slate-50 text-xs font-medium text-slate-800 hover:text-amber-600 transition-colors cursor-pointer"
              >
                <Star className={`w-4 h-4 shrink-0 ${rowContextMenu.file.is_starred ? 'text-amber-500 fill-amber-400' : 'text-slate-500'}`} />
                <span>{rowContextMenu.file.is_starred ? 'Remove Star' : 'Star Document'}</span>
              </button>

              <div className="border-t border-slate-100 my-1" />

              <button
                type="button"
                onClick={() => {
                  const f = rowContextMenu.file;
                  setRowContextMenu(null);
                  handleDelete(f);
                }}
                className="w-full flex items-center gap-2.5 px-3 py-2 hover:bg-red-50 text-xs font-medium text-red-600 transition-colors cursor-pointer"
              >
                <Trash2 className="w-4 h-4 text-red-500 shrink-0" />
                <span>Move to Recycle Bin</span>
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
};
