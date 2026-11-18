import React from 'react';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  labelClassName?: string;
  inputSize?: 'sm' | 'md' | 'lg';
  error?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(({
  label,
  labelClassName = '',
  inputSize = 'md',
  error,
  leftIcon,
  rightIcon,
  className = '',
  id,
  ...props
}, ref) => {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  const sizeStyles = {
    sm: 'px-2.5 py-1.5 text-xs',
    md: 'px-3 py-2 text-sm',
    lg: 'px-3.5 py-2.5 text-base',
  };

  const iconLeftPad = {
    sm: 'pl-8',
    md: 'pl-9',
    lg: 'pl-10',
  };

  const iconRightPad = {
    sm: 'pr-8',
    md: 'pr-9',
    lg: 'pr-10',
  };

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={inputId} className={`block mb-1.5 ${labelClassName ? labelClassName : 'text-xs font-medium text-zinc-600'}`}>
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
          className={`w-full rounded-xl bg-zinc-50/70 border border-zinc-200/80 ${sizeStyles[inputSize]} text-zinc-900 placeholder:text-zinc-400 transition-all focus:bg-white focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100 disabled:opacity-50 ${
            leftIcon ? iconLeftPad[inputSize] : ''
          } ${rightIcon ? iconRightPad[inputSize] : ''} ${error ? 'border-red-400 focus:border-red-500 focus:ring-red-400' : ''} ${className}`}
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
