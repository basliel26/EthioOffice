import React from 'react';

export interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'neutral';
  size?: 'sm' | 'md';
  className?: string;
  dot?: boolean;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'default',
  size = 'md',
  className = '',
  dot = false,
}) => {
  const variants = {
    default: 'bg-zinc-100 text-zinc-700',
    neutral: 'bg-zinc-50 text-zinc-600 border border-zinc-200/50',
    success: 'bg-emerald-50 text-emerald-700',
    warning: 'bg-amber-50 text-amber-700',
    danger: 'bg-red-50 text-red-700',
    info: 'bg-sky-50 text-sky-700',
  };

  const dotColors = {
    default: 'bg-zinc-500',
    neutral: 'bg-zinc-400',
    success: 'bg-emerald-500',
    warning: 'bg-amber-500',
    danger: 'bg-red-500',
    info: 'bg-sky-500',
  };

  const sizes = {
    sm: 'text-[11px] px-2 py-0.5 font-medium rounded-md gap-1.5',
    md: 'text-xs px-2.5 py-1 font-medium rounded-md gap-1.5',
  };

  return (
    <span className={`inline-flex items-center shrink-0 tracking-tight ${variants[variant]} ${sizes[size]} ${className}`}>
      {dot && <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${dotColors[variant]}`} />}
      {children}
    </span>
  );
};
