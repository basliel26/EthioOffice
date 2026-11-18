import React, { useState, useEffect, useRef } from 'react';
import { Calendar as CalendarIcon, Clock, X } from 'lucide-react';
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

  const { ethiopian_date, fiscal_year, gregorian_date } = calendarInfo;

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
        className="flex items-center gap-2 text-xs font-semibold text-slate-700 bg-blue-50/80 hover:bg-blue-100/70 border border-blue-200/70 px-3 py-1.5 rounded-xl transition-all shadow-2xs focus:outline-none focus:ring-2 focus:ring-blue-300"
        title="Click to view dual Ethiopian & Gregorian Calendar"
      >
        <CalendarIcon className="w-3.5 h-3.5 text-blue-600 shrink-0" />
        <span className="font-bold text-slate-800">
          {ethiopian_date.formatted_english || ethiopian_date.formatted_amharic}
        </span>
        <span className="text-[11px] text-blue-600 font-medium">
          ({gDateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })})
        </span>
      </button>

      {/* Popover Dual Calendar Card */}
      {isOpen && (
        <div className="absolute right-0 mt-2 w-80 sm:w-96 bg-white rounded-2xl shadow-xl border border-slate-200/90 p-5 z-50 animate-scale-up font-sans">
          {/* Card Header */}
          <div className="flex items-center justify-between pb-3.5 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                <CalendarIcon className="w-4 h-4" />
              </div>
              <div>
                <h4 className="text-xs font-bold text-slate-900 tracking-tight">
                  Calendar Synchronization
                </h4>
                <p className="text-[10px] text-slate-400 font-medium">ባሕረ ሐሳብ • Bahire Hasab Engine</p>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Dual Date Cards */}
          <div className="grid grid-cols-2 gap-2.5 my-4">
            {/* Ethiopian Panel */}
            <div className="p-3 bg-blue-50/60 border border-blue-100 rounded-xl space-y-1">
              <span className="text-[10px] font-bold text-blue-700 uppercase tracking-wider block">
                Ethiopian (ዓ.ም)
              </span>
              <p className="text-base font-extrabold text-slate-900">
                {ethiopian_date.day} {ethiopian_date.month === 3 ? 'Hidar' : currentMonthName.split(' ')[0]}
              </p>
              <p className="text-[11px] font-medium text-slate-600">
                {ethiopian_date.formatted_amharic}
              </p>
              <p className="text-[10px] text-blue-600 font-semibold pt-1">
                Year: {ethiopian_date.year} E.C.
              </p>
            </div>

            {/* Gregorian Panel */}
            <div className="p-3 bg-slate-50 border border-slate-200/70 rounded-xl space-y-1">
              <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider block">
                Gregorian (G.C.)
              </span>
              <p className="text-base font-extrabold text-slate-900">
                {gDateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              </p>
              <p className="text-[11px] font-medium text-slate-600">
                {gFormatted.split(',')[0]}
              </p>
              <p className="text-[10px] text-slate-500 font-semibold pt-1">
                Year: {gDateObj.getFullYear()}
              </p>
            </div>
          </div>

          {/* Mini Month Grid */}
          <div className="pt-2 border-t border-slate-100">
            <div className="flex items-center justify-between text-xs font-bold text-slate-800 mb-2">
              <span>{currentMonthName}</span>
              <span className="text-[11px] text-slate-400 font-medium">30 Days</span>
            </div>

            {/* 30-Day Grid */}
            <div className="grid grid-cols-7 gap-1 text-center text-xs">
              {Array.from({ length: daysInCurrentMonth }, (_, i) => i + 1).map((dayNum) => {
                const isToday = dayNum === ethiopian_date.day;
                return (
                  <div
                    key={dayNum}
                    className={`py-1.5 rounded-lg font-semibold text-xs transition-colors ${
                      isToday
                        ? 'bg-blue-600 text-white shadow-xs font-bold'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    {dayNum}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Fiscal Year Footer */}
          {fiscal_year?.label && (
            <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-500">
              <span className="flex items-center gap-1.5 text-slate-400">
                <Clock className="w-3.5 h-3.5 text-blue-600" />
                <span>Fiscal Year:</span>
              </span>
              <span className="font-semibold text-slate-700">{fiscal_year.label}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
