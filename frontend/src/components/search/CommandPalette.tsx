import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Search,
  FileText,
  Mail,
  Loader2,
  X,
  Folder,
  FileSpreadsheet,
  Presentation,
  FileCode,
} from 'lucide-react';
import { searchApi } from '../../api/client';
import { useSearchScope } from '../../context/SearchContext';
import type { FileItem, LetterRecord } from '../../api/types';

export const CommandPalette: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [scopedFolder, setScopedFolder] = useState<{ folderId: string | null; folderName: string | null } | null>(null);
  const [results, setResults] = useState<{ documents: FileItem[]; letters: LetterRecord[] }>({
    documents: [],
    letters: [],
  });
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const { scope } = useSearchScope();

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      } else if (e.key === 'Escape' && isOpen) {
        setIsOpen(false);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) {
      if (scope.folderId && scope.folderName) {
        setScopedFolder({ folderId: scope.folderId, folderName: scope.folderName });
      } else {
        setScopedFolder(null);
      }
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery('');
      setResults({ documents: [], letters: [] });
    }
  }, [isOpen, scope]);

  // Debounced search with folder scoping
  useEffect(() => {
    if (!query.trim()) {
      setResults({ documents: [], letters: [] });
      setIsLoading(false);
      return;
    }

    const timer = setTimeout(async () => {
      setIsLoading(true);
      try {
        const res = await searchApi.unified(query.trim(), scopedFolder?.folderId || undefined);
        setResults(res);
      } catch {
        // ignore
      } finally {
        setIsLoading(false);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [query, scopedFolder]);

  if (!isOpen) return null;

  const totalHits = results.documents.length + results.letters.length;

  const getDocIcon = (doc: FileItem) => {
    if (doc.is_folder) return <Folder className="w-4 h-4 text-slate-500 shrink-0" />;
    const name = doc.name.toLowerCase();
    if (name.endsWith('.docx') || name.endsWith('.doc')) return <FileText className="w-4 h-4 text-blue-600 shrink-0" />;
    if (name.endsWith('.xlsx') || name.endsWith('.xls') || name.endsWith('.csv')) return <FileSpreadsheet className="w-4 h-4 text-emerald-600 shrink-0" />;
    if (name.endsWith('.pptx') || name.endsWith('.ppt')) return <Presentation className="w-4 h-4 text-amber-600 shrink-0" />;
    return <FileCode className="w-4 h-4 text-slate-500 shrink-0" />;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-16 sm:pt-20 p-3 sm:p-4 select-none">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity"
        onClick={() => setIsOpen(false)}
      />

      {/* Palette Container */}
      <div className="relative w-full max-w-xl rounded-2xl bg-white shadow-2xl border border-slate-200/90 overflow-hidden z-10 animate-scale-up font-sans">
        {/* Search Input Bar */}
        <div className="flex items-center gap-2 px-3 sm:px-4 py-3 border-b border-slate-100 bg-slate-50/50">
          <Search className="w-4 h-4 text-slate-400 shrink-0" />

          {/* Folder Scope Chip */}
          {scopedFolder?.folderId && (
            <div className="flex items-center gap-1 px-2 py-0.5 rounded-md bg-blue-50 border border-blue-200 text-blue-700 text-xs font-medium shrink-0">
              <Folder className="w-3.5 h-3.5 text-blue-600 shrink-0" />
              <span className="truncate max-w-[120px] sm:max-w-[160px]">{scopedFolder.folderName}</span>
              <button
                type="button"
                onClick={() => setScopedFolder(null)}
                className="text-blue-500 hover:text-blue-800 p-0.5 rounded hover:bg-blue-100/60 transition-colors ml-0.5"
                title="Clear folder filter and search all documents"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          )}

          <input
            ref={inputRef}
            type="text"
            placeholder={
              scopedFolder?.folderId
                ? `Search within ${scopedFolder.folderName}...`
                : 'Search all files, documents, and letters...'
            }
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Backspace' && !query && scopedFolder) {
                setScopedFolder(null);
              }
            }}
            className="w-full bg-transparent text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none"
          />

          {isLoading ? (
            <Loader2 className="w-4 h-4 text-blue-600 animate-spin shrink-0" />
          ) : query ? (
            <button
              onClick={() => setQuery('')}
              className="text-slate-400 hover:text-slate-600 p-1 rounded-md hover:bg-slate-200/60 transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          ) : (
            <kbd className="text-[10px] bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded-md shadow-2xs font-mono border border-slate-200/60">
              ESC
            </kbd>
          )}
        </div>

        {/* Results List */}
        <div className="max-h-96 overflow-y-auto p-2 divide-y divide-slate-50">
          {query.trim() && !isLoading && totalHits === 0 && (
            <div className="py-12 text-center text-xs text-slate-400">
              No matching files or letters found.
            </div>
          )}

          {/* Documents Group */}
          {results.documents.length > 0 && (
            <div className="py-1.5">
              <p className="px-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                Documents & Files ({results.documents.length})
              </p>
              {results.documents.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => {
                    setIsOpen(false);
                    if (doc.is_folder) {
                      navigate('/drive/personal');
                    } else {
                      navigate(`/editor/${doc.id}`);
                    }
                  }}
                  className="w-full flex items-center justify-between px-3 py-2 text-left rounded-xl hover:bg-slate-50 transition-colors group"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    {getDocIcon(doc)}
                    <span className="text-xs font-medium text-slate-800 truncate group-hover:text-blue-600 transition-colors">
                      {doc.name}
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-400 ml-2 shrink-0">
                    {doc.is_folder ? 'Folder' : `${Math.max(1, Math.round(doc.size_bytes / 1024))} KB`}
                  </span>
                </button>
              ))}
            </div>
          )}

          {/* Letters Group */}
          {results.letters.length > 0 && (
            <div className="py-1.5">
              <p className="px-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">
                Official Correspondence ({results.letters.length})
              </p>
              {results.letters.map((letter) => (
                <button
                  key={letter.id}
                  onClick={() => {
                    setIsOpen(false);
                    navigate(`/letters`);
                  }}
                  className="w-full flex items-center justify-between px-3 py-2 text-left rounded-xl hover:bg-slate-50 transition-colors group"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <Mail className="w-4 h-4 text-blue-600 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-slate-800 truncate group-hover:text-blue-600 transition-colors">
                        {letter.subject}
                      </p>
                      <p className="text-[10px] text-slate-400 truncate">{letter.reference_number}</p>
                    </div>
                  </div>
                  <span className="text-[10px] text-slate-400 ml-2 shrink-0">
                    {letter.date_ec}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
