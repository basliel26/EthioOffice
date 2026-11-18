import React, { useState, useEffect, useRef } from 'react';
import { Calendar as CalendarIcon, X } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

export const DualCalendarDropdown: React.FC = () => {
  const { calendarInfo } = useAuth();
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  if (!calendarInfo?.ethiopian_date) return null;

  const { ethiopian_date, gregorian_date } = calendarInfo;

  // Format full Gregorian date string e.g. "Wednesday, November 18, 2026"
  const gDateObj = new Date(gregorian_date);
  const gFormatted = gDateObj.toLocaleDateString('en-US', {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });

  // Ethiopian month names
  const ethiopianMonths = [
    'Meskerem (መስከረም)',
    'Tikimt (ጥቅምት)',
    'Hidar (ህዳር)',
    'Tahsas (ታኅሣሥ)',
    'Tir (ጥር)',
    'Yekatit (የካቲት)',
    'Megabit (መጋቢት)',
    'Miyazya (ሚያዝያ)',
    'Ginbot (ግንቦት)',
    'Sene (ሰኔ)',
    'Hamle (ሐምሌ)',
    'Nehase (ነሐሴ)',
    'Pagume (ጳጉሜን)',
  ];

  const currentMonthName = ethiopianMonths[(ethiopian_date.month - 1) % 13];
  const daysInCurrentMonth = ethiopian_date.month === 13 ? (ethiopian_date.year % 4 === 3 ? 6 : 5) : 30;

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Clickable Header Date Pill */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-1.5 sm:gap-2 text-xs sm:text-sm font-semibold text-slate-700 bg-blue-50/80 hover:bg-blue-100/70 border border-blue-200/70 px-2 sm:px-3 py-1.5 rounded-xl transition-all shadow-2xs focus:outline-none focus:ring-2 focus:ring-blue-300 shrink-0"
        title="Click to view dual Ethiopian & Gregorian Calendar"
      >
        <CalendarIcon className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-blue-600 shrink-0" />
        {/* Full date on wide screens (>= 1100px) */}
        <span className="font-bold text-slate-900 truncate hidden xl:inline">
          {ethiopian_date.formatted_english || ethiopian_date.formatted_amharic}
        </span>
        {/* Compact date on medium/narrow screens: e.g. "10 Hidar" */}
        <span className="font-bold text-slate-900 truncate xl:hidden hidden sm:inline">
          {ethiopian_date.day} {ethiopian_date.month === 3 ? 'Hidar' : currentMonthName.split(' ')[0]}
        </span>
        {/* Day number only on very small screens: e.g. "10" */}
        <span className="font-bold text-slate-900 sm:hidden">
          {ethiopian_date.day}
        </span>
        <span className="text-[11px] sm:text-xs text-blue-600 font-medium hidden 2xl:inline">
          ({gDateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })})
        </span>
      </button>

      {/* Popover Dual Calendar Card (Compact & Scaled to Screen) */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-[calc(100vw-2rem)] max-w-[305px] bg-white rounded-2xl shadow-xl border border-slate-200/90 p-3 sm:p-3.5 z-50 animate-scale-up font-sans select-none">
          {/* Card Header (Clean & Compact) */}
          <div className="flex items-center justify-between pb-2 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-md bg-blue-50 text-blue-600 flex items-center justify-center shrink-0">
                <CalendarIcon className="w-3.5 h-3.5" />
              </div>
              <div>
                <h3 className="text-xs sm:text-sm font-bold text-slate-900 tracking-tight leading-tight">
                  Calendar
                </h3>
                <p className="text-[10px] text-slate-400 font-medium">Ethiopian & Gregorian</p>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="p-1 text-slate-400 hover:text-slate-600 rounded-md hover:bg-slate-100 transition-colors"
              title="Close"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Dual Date Cards */}
          <div className="grid grid-cols-2 gap-2 my-2.5">
            {/* Ethiopian Panel */}
            <div className="p-2 bg-blue-50/60 border border-blue-100 rounded-lg space-y-0.5">
              <span className="text-[9px] font-bold text-blue-700 uppercase tracking-wider block">
                Ethiopian (ዓ.ም)
              </span>
              <p className="text-sm sm:text-base font-extrabold text-slate-900 leading-snug">
                {ethiopian_date.day} {ethiopian_date.month === 3 ? 'Hidar' : currentMonthName.split(' ')[0]}
              </p>
              <p className="text-[10px] font-medium text-slate-600 truncate">
                {ethiopian_date.formatted_amharic}
              </p>
              <p className="text-[9px] text-blue-600 font-semibold pt-0.5">
                Year {ethiopian_date.year} E.C.
              </p>
            </div>

            {/* Gregorian Panel */}
            <div className="p-2 bg-slate-50 border border-slate-200/70 rounded-lg space-y-0.5">
              <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider block">
                Gregorian (G.C.)
              </span>
              <p className="text-sm sm:text-base font-extrabold text-slate-900 leading-snug">
                {gDateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              </p>
              <p className="text-[10px] font-medium text-slate-600 truncate">
                {gFormatted.split(',')[0]}
              </p>
              <p className="text-[9px] text-slate-500 font-semibold pt-0.5">
                Year {gDateObj.getFullYear()}
              </p>
            </div>
          </div>

          {/* Mini Month Grid */}
          <div className="pt-2 border-t border-slate-100">
            <div className="flex items-center justify-between text-[11px] font-bold text-slate-800 mb-1.5">
              <span>{currentMonthName}</span>
              <span className="text-[10px] text-slate-400 font-medium">30 Days</span>
            </div>

            {/* 30-Day Grid */}
            <div className="grid grid-cols-7 gap-1 text-center">
              {Array.from({ length: daysInCurrentMonth }, (_, i) => i + 1).map((dayNum) => {
                const isToday = dayNum === ethiopian_date.day;
                return (
                  <div
                    key={dayNum}
                    className={`py-0.5 sm:py-1 rounded-md text-[10px] sm:text-[11px] font-semibold transition-colors ${
                      isToday
                        ? 'bg-blue-600 text-white shadow-2xs font-bold'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    {dayNum}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
