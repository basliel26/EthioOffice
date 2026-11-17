import React from 'react';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(({
  label,
  error,
  leftIcon,
  rightIcon,
  className = '',
  id,
  ...props
}, ref) => {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={inputId} className="block text-xs font-medium text-zinc-600 mb-1.5">
          {label}
        </label>
      )}
      <div className="relative flex items-center">
        {leftIcon && (
          <span className="absolute left-3 text-zinc-400 pointer-events-none shrink-0">
            {leftIcon}
          </span>
        )}
        <input
          id={inputId}
          ref={ref}
          className={`w-full rounded-lg bg-zinc-50/80 border border-zinc-200/80 px-3 py-2 text-sm text-zinc-900 placeholder:text-zinc-400 transition-colors focus:bg-white focus:border-zinc-400 focus:outline-none focus:ring-1 focus:ring-zinc-400 disabled:opacity-50 ${
            leftIcon ? 'pl-9' : ''
          } ${rightIcon ? 'pr-9' : ''} ${error ? 'border-red-400 focus:border-red-500 focus:ring-red-400' : ''} ${className}`}
          {...props}
        />
        {rightIcon && (
          <span className="absolute right-3 text-zinc-400 shrink-0">
            {rightIcon}
          </span>
        )}
      </div>
      {error && (
        <p className="mt-1 text-xs text-red-500">{error}</p>
      )}
    </div>
  );
});

Input.displayName = 'Input';
