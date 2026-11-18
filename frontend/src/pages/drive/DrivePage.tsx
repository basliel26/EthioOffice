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
  Download,
  Edit2,
  Search,
  Check,
  Share2,
  FileSpreadsheet,
  Presentation,
  FilePlus2,
  ExternalLink,
} from 'lucide-react';
import { filesApi, tagsApi, sharesApi } from '../../api/client';
import type { FileItem, TagItem } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Modal } from '../../components/ui/Modal';
import { ShareModal } from '../../components/drive/ShareModal';

interface DrivePageProps {
  viewMode?: 'PERSONAL' | 'COMPANY' | 'SHARED' | 'STARRED' | 'RECENT' | 'TRASH';
}

export const DrivePage: React.FC<DrivePageProps> = ({ viewMode = 'PERSONAL' }) => {
  const navigate = useNavigate();
  const [files, setFiles] = useState<FileItem[]>([]);
  const [availableTags, setAvailableTags] = useState<TagItem[]>([]);
  const [selectedTagFilter, setSelectedTagFilter] = useState<string | null>(null);
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null);
  const [breadcrumbs, setBreadcrumbs] = useState<Array<{ id: string | null; name: string }>>([
    { id: null, name: 'Home' },
  ]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);

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

  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const loadData = async () => {
    setIsLoading(true);
    try {
      if (viewMode === 'STARRED') {
        const data = await filesApi.listStarred();
        setFiles(data);
      } else if (viewMode === 'RECENT') {
        const data = await filesApi.getRecent(30);
        setFiles(data.map((r) => r.file));
      } else if (viewMode === 'TRASH') {
        const data = await filesApi.list('TRASH', currentFolderId || undefined, searchQuery);
        setFiles(data);
      } else if (viewMode === 'SHARED') {
        const data = await sharesApi.listSharedWithMe();
        setFiles(data);
      } else {
        const driveType = viewMode === 'COMPANY' ? 'COMPANY' : 'PERSONAL';
        const data = await filesApi.list(driveType, currentFolderId || undefined, searchQuery);
        setFiles(data);
      }

      const tags = await tagsApi.list();
      setAvailableTags(tags);
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [viewMode, currentFolderId, searchQuery]);

  const handleCreateFolder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFolderName.trim()) return;

    try {
      const driveType = viewMode === 'COMPANY' ? 'COMPANY' : 'PERSONAL';
      await filesApi.createFolder(newFolderName.trim(), driveType, currentFolderId || undefined);
      setNewFolderName('');
      setShowFolderModal(false);
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

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const driveType = viewMode === 'COMPANY' ? 'COMPANY' : 'PERSONAL';
      await filesApi.upload(file, driveType, currentFolderId || undefined);
      if (fileInputRef.current) fileInputRef.current.value = '';
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
      loadData();
    } catch {
      // ignore
    }
  };

  const handleRestore = async (file: FileItem) => {
    try {
      await filesApi.restore(file.id);
      loadData();
    } catch {
      // ignore
    }
  };

  const handleEmptyTrash = async () => {
    try {
      await filesApi.emptyTrash();
      setShowEmptyTrashModal(false);
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
      loadData();
    } catch {
      // ignore
    }
  };

  const handleOpenFolder = (folder: FileItem) => {
    setCurrentFolderId(folder.id);
    setBreadcrumbs((prev) => [...prev, { id: folder.id, name: folder.name }]);
  };

  const handleNavigateBreadcrumb = (index: number) => {
    const target = breadcrumbs[index];
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

  const filteredFiles = files.filter((f) => {
    if (!selectedTagFilter) return true;
    return f.tags?.includes(selectedTagFilter);
  });

  return (
    <div className="space-y-3 select-none font-sans">
      {/* Tier 1: Location / URI Path Bar (Windows Explorer Style) */}
      <div className="flex items-center justify-between py-0.5">
        <div className="flex items-center gap-1.5 overflow-x-auto text-sm">
          {viewMode !== 'STARRED' && viewMode !== 'RECENT' ? (
            breadcrumbs.map((b, idx) => (
              <React.Fragment key={b.name + idx}>
                {idx > 0 && <ChevronRight className="w-3.5 h-3.5 text-slate-400 shrink-0" />}
                <button
                  onClick={() => handleNavigateBreadcrumb(idx)}
                  className={`transition-colors whitespace-nowrap ${
                    idx === breadcrumbs.length - 1
                      ? 'text-slate-800 font-medium cursor-default'
                      : 'text-slate-500 hover:text-slate-900 font-normal'
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
                  <span className="text-slate-800 font-medium">Starred Documents</span>
                </>
              ) : (
                <>
                  <Clock className="w-4 h-4 text-blue-600 shrink-0" />
                  <span className="text-slate-800 font-medium">Recent Activity</span>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Tier 2: Action Toolbar / Command Ribbon */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-200/80">
        {/* Left: Action Buttons */}
        <div className="flex items-center gap-2 flex-wrap">
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
          ) : (
            <>
              {/* New Folder Button with FolderPlus Icon */}
              <Button
                variant="subtle"
                size="sm"
                leftIcon={<FolderPlus className="w-4 h-4 text-amber-500" />}
                onClick={() => setShowFolderModal(true)}
              >
                New Folder
              </Button>

              {/* New Document Button with FilePlus2 Icon */}
              <Button
                variant="subtle"
                size="sm"
                leftIcon={<FilePlus2 className="w-4 h-4 text-blue-600" />}
                onClick={() => {
                  setNewDocName('');
                  setNewDocType('docx');
                  setShowDocModal(true);
                }}
              >
                New Document
              </Button>

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
          )}
        </div>

        {/* Right: In-Folder Search */}
        {viewMode !== 'TRASH' && (
          <div className="w-full sm:w-56 md:w-64">
            <Input
              placeholder="Search in folder..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              leftIcon={<Search className="w-3.5 h-3.5 text-slate-400" />}
            />
          </div>
        )}
      </div>

      {/* Filter and Tag Chips Row */}
      {availableTags.length > 0 && viewMode !== 'TRASH' && (
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          <span className="text-xs font-semibold text-slate-400 shrink-0">Tags:</span>
          <button
            onClick={() => setSelectedTagFilter(null)}
            className={`px-3 py-1 text-xs rounded-lg transition-all font-semibold ${
              selectedTagFilter === null
                ? 'bg-blue-600 text-white shadow-2xs'
                : 'bg-slate-100/90 text-slate-600 hover:bg-slate-200/70 border border-slate-200/60'
            }`}
          >
            All
          </button>
          {availableTags.map((t) => (
            <button
              key={t.id}
              onClick={() => setSelectedTagFilter(selectedTagFilter === t.name ? null : t.name)}
              className={`flex items-center gap-1.5 px-3 py-1 text-xs rounded-lg transition-all font-semibold ${
                selectedTagFilter === t.name
                  ? 'bg-blue-600 text-white shadow-2xs'
                  : 'bg-slate-100/90 text-slate-700 hover:bg-slate-200/70 border border-slate-200/60'
              }`}
            >
              <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: t.color }} />
              <span>{t.name}</span>
            </button>
          ))}
        </div>
      )}

      {/* Files & Folders Content List */}
      <div className="bg-white rounded-2xl shadow-xs border border-slate-200/80 overflow-hidden">
        {isLoading ? (
          <div className="py-20 text-center text-xs font-medium text-slate-400">Loading files...</div>
        ) : filteredFiles.length === 0 ? (
          <div className="py-20 text-center space-y-2">
            <Folder className="w-10 h-10 text-slate-300 mx-auto" />
            <p className="text-sm font-bold text-slate-800">This folder is empty</p>
            <p className="text-xs text-slate-400">Upload a document or create a new file or folder to get started.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {filteredFiles.map((file) => (
              <div
                key={file.id}
                onDoubleClick={() => {
                  if (file.is_folder) {
                    handleOpenFolder(file);
                  } else {
                    navigate(`/editor/${file.id}`);
                  }
                }}
                className="flex items-center justify-between p-3.5 hover:bg-slate-50/80 transition-colors group cursor-pointer"
              >
                {/* Left: Star + Icon + Name + Tags */}
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  {viewMode !== 'TRASH' && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleToggleStar(file);
                      }}
                      className="text-slate-300 hover:text-amber-500 p-0.5 rounded transition-colors shrink-0"
                      title={file.is_starred ? 'Remove Star' : 'Star Document'}
                    >
                      <Star
                        className={`w-4 h-4 ${
                          file.is_starred ? 'fill-amber-400 text-amber-400' : ''
                        }`}
                      />
                    </button>
                  )}

                  <div className="shrink-0">
                    {file.is_folder ? (
                      <Folder className="w-5 h-5 text-blue-600 fill-blue-50/70" />
                    ) : (
                      <FileText className="w-5 h-5 text-slate-400" />
                    )}
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

                  {/* Actions Dropdown / Quick Buttons */}
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
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setTargetFile(file);
                            setShowShareModal(true);
                          }}
                          className="p-1.5 text-slate-400 hover:text-blue-600 rounded-lg hover:bg-slate-100 transition-colors"
                          title="Share"
                        >
                          <Share2 className="w-4 h-4" />
                        </button>
                        {!file.is_folder && (
                          <a
                            href={`/api/v1/files/${file.id}/download`}
                            onClick={(e) => e.stopPropagation()}
                            className="p-1.5 text-slate-400 hover:text-blue-600 rounded-lg hover:bg-slate-100 transition-colors"
                            title="Download"
                          >
                            <Download className="w-4 h-4" />
                          </a>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setTargetFile(file);
                            setRenameValue(file.name);
                            setShowRenameModal(true);
                          }}
                          className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100 transition-colors"
                          title="Rename"
                        >
                          <Edit2 className="w-4 h-4" />
                        </button>
                        {!file.is_folder && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setTargetFile(file);
                              setSelectedTagIds(
                                availableTags
                                  .filter((t) => file.tags?.includes(t.name))
                                  .map((t) => t.id)
                              );
                              setShowTagModal(true);
                            }}
                            className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100 transition-colors"
                            title="Assign Tags"
                          >
                            <TagIcon className="w-4 h-4" />
                          </button>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(file);
                          }}
                          className="p-1.5 text-slate-400 hover:text-red-600 rounded-lg hover:bg-slate-100 transition-colors"
                          title="Move to Recycle Bin"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 1. New Folder Modal */}
      <Modal
        isOpen={showFolderModal}
        onClose={() => setShowFolderModal(false)}
        title="Create New Folder"
      >
        <form onSubmit={handleCreateFolder} className="space-y-4">
          <Input
            placeholder="Folder name"
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
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
        title="Create New Document"
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
    </div>
  );
};
