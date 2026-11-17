import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Folder,
  FileText,
  Plus,
  Upload,
  Trash2,
  RotateCcw,
  Star,
  Lock,
  Tag as TagIcon,
  ChevronRight,
  Download,
  Edit2,
  Search,
  Check,
  Share2,
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
    { id: null, name: 'መነሻ (Home)' },
  ]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Modals & form state
  const [showFolderModal, setShowFolderModal] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [showRenameModal, setShowRenameModal] = useState(false);
  const [targetFile, setTargetFile] = useState<FileItem | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [showTagModal, setShowTagModal] = useState(false);
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);
  const [showEmptyTrashModal, setShowEmptyTrashModal] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

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

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const uploadedFiles = e.target.files;
    if (!uploadedFiles || uploadedFiles.length === 0) return;

    const file = uploadedFiles[0];
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
      setFiles((prev) =>
        prev.map((f) => (f.id === file.id ? { ...f, is_starred: !f.is_starred } : f))
      );
    } catch {
      // ignore
    }
  };

  const handleDelete = async (file: FileItem) => {
    try {
      const isPermanent = viewMode === 'TRASH';
      await filesApi.delete(file.id, isPermanent);
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

  const filteredFiles = files.filter((f) => {
    if (!selectedTagFilter) return true;
    return f.tags?.includes(selectedTagFilter);
  });

  const getPageTitle = () => {
    switch (viewMode) {
      case 'COMPANY':
        return 'የድርጅት ድራይቭ (Company Drive)';
      case 'SHARED':
        return 'ከእኔ ጋር የተጋሩ (Shared with Me)';
      case 'STARRED':
        return 'ተመራጭ ሰነዶች (Starred Items)';
      case 'RECENT':
        return 'የቅርብ ጊዜ እንቅስቃሴዎች (Recent Documents)';
      case 'TRASH':
        return 'ሪሳይክል ቢን (Recycle Bin)';
      default:
        return 'የግል ድራይቭ (My Personal Drive)';
    }
  };

  return (
    <div className="space-y-6 select-none font-sans">
      {/* Top Action & Breadcrumbs Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-zinc-100">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900 tracking-tight">{getPageTitle()}</h1>
          {/* Breadcrumbs for folder navigation */}
          {viewMode !== 'STARRED' && viewMode !== 'RECENT' && (
            <div className="flex items-center gap-1.5 mt-1.5 text-xs text-zinc-500">
              {breadcrumbs.map((b, idx) => (
                <React.Fragment key={b.name + idx}>
                  {idx > 0 && <ChevronRight className="w-3.5 h-3.5 text-zinc-400" />}
                  <button
                    onClick={() => handleNavigateBreadcrumb(idx)}
                    className={`hover:text-zinc-900 transition-colors ${
                      idx === breadcrumbs.length - 1 ? 'font-medium text-zinc-900' : ''
                    }`}
                  >
                    {b.name}
                  </button>
                </React.Fragment>
              ))}
            </div>
          )}
        </div>

        {/* Action Buttons & Quick Search */}
        <div className="flex items-center gap-2">
          {viewMode !== 'TRASH' && (
            <div className="w-48 hidden md:block">
              <Input
                placeholder="በዚህ ማህደር ፈልግ..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                leftIcon={<Search className="w-3.5 h-3.5" />}
              />
            </div>
          )}
          {viewMode === 'TRASH' ? (
            <Button
              variant="danger"
              size="sm"
              leftIcon={<Trash2 className="w-4 h-4" />}
              onClick={() => setShowEmptyTrashModal(true)}
              disabled={files.length === 0}
            >
              ሪሳይክል ቢኑን ባዶ አድርግ (Empty Trash)
            </Button>
          ) : (
            <>
              <Button
                variant="subtle"
                size="sm"
                leftIcon={<Plus className="w-4 h-4" />}
                onClick={() => setShowFolderModal(true)}
              >
                አዲስ ፎልደር (New Folder)
              </Button>
              <Button
                variant="primary"
                size="sm"
                leftIcon={<Upload className="w-4 h-4" />}
                onClick={() => fileInputRef.current?.click()}
              >
                ፋይል ስቀል (Upload File)
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
      </div>

      {/* Filter and Tag Chips Row */}
      {availableTags.length > 0 && viewMode !== 'TRASH' && (
        <div className="flex items-center gap-2 overflow-x-auto pb-1">
          <span className="text-xs text-zinc-400 shrink-0">መለያዎች (Tags):</span>
          <button
            onClick={() => setSelectedTagFilter(null)}
            className={`px-2.5 py-1 text-xs rounded-lg transition-colors ${
              selectedTagFilter === null
                ? 'bg-zinc-900 text-white'
                : 'bg-zinc-100 text-zinc-600 hover:bg-zinc-200/60'
            }`}
          >
            ሁሉም
          </button>
          {availableTags.map((t) => (
            <button
              key={t.id}
              onClick={() => setSelectedTagFilter(selectedTagFilter === t.name ? null : t.name)}
              className={`flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-lg transition-colors ${
                selectedTagFilter === t.name
                  ? 'bg-zinc-900 text-white'
                  : 'bg-zinc-100/80 text-zinc-700 hover:bg-zinc-200/60'
              }`}
            >
              <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: t.color }} />
              <span>{t.name}</span>
            </button>
          ))}
        </div>
      )}

      {/* Files & Folders Content List */}
      <div className="bg-white rounded-2xl shadow-xs border border-zinc-200/60 overflow-hidden">
        {isLoading ? (
          <div className="py-20 text-center text-xs text-zinc-400">እየተጫነ ነው (Loading files)...</div>
        ) : filteredFiles.length === 0 ? (
          <div className="py-20 text-center space-y-2">
            <Folder className="w-8 h-8 text-zinc-300 mx-auto" />
            <p className="text-sm font-medium text-zinc-900">ይህ ማህደር ባዶ ነው (No files found)</p>
            <p className="text-xs text-zinc-400">አዲስ ፋይል ወይም ፎልደር በማከል ስራዎን ይጀምሩ።</p>
          </div>
        ) : (
          <div className="divide-y divide-zinc-100">
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
                className="flex items-center justify-between p-3.5 hover:bg-zinc-50/70 transition-colors group cursor-pointer"
              >
                {/* Left: Star + Icon + Name + Tags */}
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  {viewMode !== 'TRASH' && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleToggleStar(file);
                      }}
                      className="text-zinc-300 hover:text-amber-500 p-0.5 rounded transition-colors"
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
                      <Folder className="w-5 h-5 text-zinc-500" />
                    ) : (
                      <FileText className="w-5 h-5 text-zinc-400" />
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-zinc-900 truncate">
                        {file.name}
                      </span>
                      {file.is_locked && (
                        <span className="inline-flex items-center gap-1 text-[10px] bg-amber-50 text-amber-700 px-1.5 py-0.5 rounded">
                          <Lock className="w-3 h-3" />
                          <span>{file.lock_info?.locked_by_name || 'ተቆልፏል'}</span>
                        </span>
                      )}
                    </div>
                    {/* Tags row */}
                    {file.tags && file.tags.length > 0 && (
                      <div className="flex items-center gap-1 mt-1">
                        {file.tags.map((tg) => (
                          <span
                            key={tg}
                            className="text-[10px] bg-zinc-100 text-zinc-600 px-1.5 py-0.2 rounded"
                          >
                            {tg}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Right: Size, Date, Actions */}
                <div className="flex items-center gap-6 shrink-0 text-xs text-zinc-400">
                  <span className="w-20 text-right">
                    {file.is_folder ? `${file.file_count || 0} ፋይሎች` : `${Math.round(file.size_bytes / 1024)} KB`}
                  </span>

                  <span className="w-32 text-right hidden sm:inline">
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
                          className="p-1 text-zinc-400 hover:text-emerald-700 rounded hover:bg-zinc-100"
                          title="መልስ (Restore)"
                        >
                          <RotateCcw className="w-4 h-4" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(file);
                          }}
                          className="p-1 text-zinc-400 hover:text-red-700 rounded hover:bg-zinc-100"
                          title="ለዘላለም ሰርዝ (Delete Permanently)"
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
                          className="p-1 text-zinc-400 hover:text-zinc-700 rounded hover:bg-zinc-100"
                          title="አጋራ (Share)"
                        >
                          <Share2 className="w-3.5 h-3.5" />
                        </button>
                        {!file.is_folder && (
                          <a
                            href={`/api/v1/files/${file.id}/download`}
                            onClick={(e) => e.stopPropagation()}
                            className="p-1 text-zinc-400 hover:text-zinc-700 rounded hover:bg-zinc-100"
                            title="አውርድ (Download)"
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
                          className="p-1 text-zinc-400 hover:text-zinc-700 rounded hover:bg-zinc-100"
                          title="ስም ቀይር (Rename)"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
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
                            className="p-1 text-zinc-400 hover:text-zinc-700 rounded hover:bg-zinc-100"
                            title="መለያዎችን አስተካክል (Assign Tags)"
                          >
                            <TagIcon className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(file);
                          }}
                          className="p-1 text-zinc-400 hover:text-red-600 rounded hover:bg-zinc-100"
                          title="ሰርዝ (Trash)"
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
        title="አዲስ ፎልደር ፍጠር (Create New Folder)"
      >
        <form onSubmit={handleCreateFolder} className="space-y-4">
          <Input
            placeholder="የፎልደር ስም (Folder Name)"
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            required
            autoFocus
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" type="button" onClick={() => setShowFolderModal(false)}>
              ተመለስ (Cancel)
            </Button>
            <Button variant="primary" type="submit">
              ፍጠር (Create)
            </Button>
          </div>
        </form>
      </Modal>

      {/* 2. Rename Modal */}
      <Modal
        isOpen={showRenameModal}
        onClose={() => setShowRenameModal(false)}
        title="ስም ቀይር (Rename Item)"
      >
        <form onSubmit={handleRenameSubmit} className="space-y-4">
          <Input
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            required
            autoFocus
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" type="button" onClick={() => setShowRenameModal(false)}>
              ተመለስ (Cancel)
            </Button>
            <Button variant="primary" type="submit">
              ቀይር (Save)
            </Button>
          </div>
        </form>
      </Modal>

      {/* 3. Assign Tags Modal */}
      <Modal
        isOpen={showTagModal}
        onClose={() => setShowTagModal(false)}
        title="የሰነድ መለያዎች (Assign Classification Tags)"
        description={targetFile?.name}
      >
        <div className="space-y-3">
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
                  className={`flex items-center justify-between p-2 rounded-lg border text-xs text-left transition-colors ${
                    isSelected
                      ? 'border-zinc-900 bg-zinc-50'
                      : 'border-zinc-200/80 hover:bg-zinc-50'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: tag.color }} />
                    <span className="font-medium text-zinc-900">{tag.name}</span>
                  </div>
                  {isSelected && <Check className="w-3.5 h-3.5 text-zinc-900" />}
                </button>
              );
            })}
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-zinc-100">
            <Button variant="ghost" onClick={() => setShowTagModal(false)}>
              ተመለስ (Cancel)
            </Button>
            <Button variant="primary" onClick={handleTagAssignSubmit}>
              አስቀምጥ (Save Tags)
            </Button>
          </div>
        </div>
      </Modal>

      {/* 4. Empty Trash Confirmation Modal */}
      <Modal
        isOpen={showEmptyTrashModal}
        onClose={() => setShowEmptyTrashModal(false)}
        title="ሪሳይክል ቢኑን ባዶ ማድረግ ይፈልጋሉ?"
        description="ይህ እርምጃ በሪሳይክል ቢን ውስጥ ያሉትን ሁሉንም ፋይሎች ለዘላለም ይሰርዛል፤ ማከማቻ ቦታውንም ያስመልሳል። ይህን እርምጃ መመለስ አይቻልም።"
      >
        <div className="flex justify-end gap-2 pt-4">
          <Button variant="ghost" onClick={() => setShowEmptyTrashModal(false)}>
            ተመለስ (Cancel)
          </Button>
          <Button variant="danger" onClick={handleEmptyTrash}>
            ሁሉንም ለዘላለም ሰርዝ (Empty Trash)
          </Button>
        </div>
      </Modal>

      {/* 5. Document & Folder Sharing Modal */}
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
