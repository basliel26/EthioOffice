import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, FileText, Mail, Loader2, X } from 'lucide-react';
import { searchApi } from '../../api/client';
import type { FileItem, LetterRecord } from '../../api/types';

export const CommandPalette: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<{ documents: FileItem[]; letters: LetterRecord[] }>({
    documents: [],
    letters: [],
  });
  const [isLoading, setIsLoading] = useState(false);
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

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
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery('');
      setResults({ documents: [], letters: [] });
    }
  }, [isOpen]);

  // Debounced search
  useEffect(() => {
    if (!query.trim()) {
      setResults({ documents: [], letters: [] });
      setIsLoading(false);
      return;
    }

    const timer = setTimeout(async () => {
      setIsLoading(true);
      try {
        const res = await searchApi.unified(query.trim());
        setResults(res);
      } catch {
        // ignore
      } finally {
        setIsLoading(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [query]);

  if (!isOpen) return null;

  const totalHits = results.documents.length + results.letters.length;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 p-4 select-none">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-zinc-950/25 backdrop-blur-xs transition-opacity"
        onClick={() => setIsOpen(false)}
      />

      {/* Palette Container */}
      <div className="relative w-full max-w-xl rounded-2xl bg-white shadow-2xl border border-zinc-200/80 overflow-hidden z-10 animate-scale-up">
        {/* Search Input Bar */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-zinc-100">
          <Search className="w-4 h-4 text-zinc-400 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            placeholder="ፈልግ... ሰነዶች ወይም ደብዳቤዎች (Search files, reference numbers, subjects)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full bg-transparent text-sm text-zinc-900 placeholder:text-zinc-400 focus:outline-none"
          />
          {isLoading ? (
            <Loader2 className="w-4 h-4 text-zinc-400 animate-spin shrink-0" />
          ) : query ? (
            <button
              onClick={() => setQuery('')}
              className="text-zinc-400 hover:text-zinc-600 p-0.5 rounded"
            >
              <X className="w-4 h-4" />
            </button>
          ) : (
            <kbd className="text-[10px] bg-zinc-100 text-zinc-400 px-1.5 py-0.5 rounded shadow-2xs font-mono">
              ESC
            </kbd>
          )}
        </div>

        {/* Results List */}
        <div className="max-h-96 overflow-y-auto p-2 divide-y divide-zinc-50">
          {query.trim() && !isLoading && totalHits === 0 && (
            <div className="py-12 text-center text-xs text-zinc-400">
              ምንም ውጤት አልተገኘም (No matching files or letters found)
            </div>
          )}

          {/* Documents Group */}
          {results.documents.length > 0 && (
            <div className="py-2">
              <p className="px-3 text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">
                ሰነዶች (Documents)
              </p>
              {results.documents.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => {
                    setIsOpen(false);
                    navigate('/drive/personal');
                  }}
                  className="w-full flex items-center justify-between px-3 py-2 text-left rounded-lg hover:bg-zinc-50 transition-colors group"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <FileText className="w-4 h-4 text-zinc-400 group-hover:text-zinc-700 shrink-0" />
                    <span className="text-xs font-medium text-zinc-900 truncate">{doc.name}</span>
                  </div>
                  <span className="text-[10px] text-zinc-400 ml-2 shrink-0">
                    {Math.round(doc.size_bytes / 1024)} KB
                  </span>
                </button>
              ))}
            </div>
          )}

          {/* Letters Group */}
          {results.letters.length > 0 && (
            <div className="py-2">
              <p className="px-3 text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">
                ደብዳቤዎች (Official Letters)
              </p>
              {results.letters.map((letter) => (
                <button
                  key={letter.id}
                  onClick={() => {
                    setIsOpen(false);
                    navigate(`/letters/${letter.id}`);
                  }}
                  className="w-full flex items-center justify-between px-3 py-2 text-left rounded-lg hover:bg-zinc-50 transition-colors group"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <Mail className="w-4 h-4 text-zinc-400 group-hover:text-zinc-700 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-zinc-900 truncate">{letter.subject}</p>
                      <p className="text-[10px] text-zinc-400 truncate">{letter.reference_number}</p>
                    </div>
                  </div>
                  <span className="text-[10px] text-zinc-400 ml-2 shrink-0">
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
