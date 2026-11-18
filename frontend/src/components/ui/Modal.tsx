import React, { useEffect } from 'react';
import { X } from 'lucide-react';

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  icon?: React.ReactNode;
  description?: string;
  children: React.ReactNode;
  maxWidth?: 'sm' | 'md' | 'lg' | 'xl' | '2xl';
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  icon,
  description,
  children,
  maxWidth = 'md',
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const maxWidths = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
    '2xl': 'max-w-2xl',
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Subtle Backdrop with blur */}
      <div 
        className="fixed inset-0 bg-zinc-950/25 backdrop-blur-xs transition-opacity animate-fade-in"
        onClick={onClose} 
      />

      {/* Clean borderless dialog container */}
      <div className={`relative w-full ${maxWidths[maxWidth]} rounded-2xl bg-white shadow-2xl p-6 transition-all duration-200 z-10 animate-scale-up font-sans`}>
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            {icon && (
              <div className="w-10 h-10 rounded-xl bg-slate-100/90 border border-slate-200/60 flex items-center justify-center text-slate-700 shrink-0">
                {icon}
              </div>
            )}
            <div>
              {title && <h3 className="text-base font-bold text-slate-900">{title}</h3>}
              {description && <p className="mt-0.5 text-xs text-slate-500 font-medium">{description}</p>}
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-700 p-1.5 rounded-lg hover:bg-slate-100 transition-colors shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div>{children}</div>
      </div>
    </div>
  );
};
