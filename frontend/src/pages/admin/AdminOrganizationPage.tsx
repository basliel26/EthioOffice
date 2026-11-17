import React, { useState, useEffect } from 'react';
import { HardDrive } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { filesApi } from '../../api/client';
import type { StorageAnalytics } from '../../api/types';
import { Badge } from '../../components/ui/Badge';

export const AdminOrganizationPage: React.FC = () => {
  const { user } = useAuth();
  const [analytics, setAnalytics] = useState<StorageAnalytics | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await filesApi.getAnalytics();
        setAnalytics(data);
      } catch {
        // ignore
      }
    }
    load();
  }, []);

  const org = user?.organization;

  return (
    <div className="space-y-6 select-none font-sans">
      {/* Header */}
      <div className="pb-4 border-b border-zinc-100">
        <h1 className="text-lg font-semibold text-zinc-900 tracking-tight">
          ድርጅት እና የፍቃድ አስተዳደር (Organization & License)
        </h1>
        <p className="text-xs text-zinc-500 mt-0.5">
          የድርጅቱ መረጃ፣ የፍቃድ ሁኔታ (License Status) እና የማከማቻ ቦታ አጠቃቀም
        </p>
      </div>

      {/* Corporate Profile Card */}
      <div className="bg-white rounded-2xl p-6 border border-zinc-200/60 shadow-xs space-y-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-2xl bg-zinc-900 text-white flex items-center justify-center font-bold text-base shadow-xs">
            {org?.name?.slice(0, 2).toUpperCase() || 'EO'}
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-900">{org?.name}</h3>
            <p className="text-xs text-zinc-400">መለያ ቁጥር (Slug): @{org?.slug}</p>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-4 border-t border-zinc-100 text-xs">
          <div>
            <span className="text-zinc-400 block text-[10px] uppercase">የግብር ከፋይ ቁጥር (TIN)</span>
            <span className="font-medium text-zinc-900 mt-0.5 block">{org?.tin_number || 'አልተመዘገበም'}</span>
          </div>
          <div>
            <span className="text-zinc-400 block text-[10px] uppercase">የፍቃድ ደረጃ (License Tier)</span>
            <span className="font-semibold text-zinc-900 mt-0.5 block">
              <Badge variant="default">{org?.license_tier || 'ENTERPRISE'}</Badge>
            </span>
          </div>
          <div>
            <span className="text-zinc-400 block text-[10px] uppercase">የፍቃድ ሁኔታ (Status)</span>
            <span className="font-medium text-emerald-700 mt-0.5 block">
              <Badge variant="success" dot>ንቁ (Active)</Badge>
            </span>
          </div>
          <div>
            <span className="text-zinc-400 block text-[10px] uppercase">የቀሩ ቀናት (Days Remaining)</span>
            <span className="font-medium text-zinc-900 mt-0.5 block">{org?.days_remaining ?? 'ያልተገደበ'} ቀናት</span>
          </div>
        </div>
      </div>

      {/* Storage Analytics Card */}
      {analytics && (
        <div className="bg-white rounded-2xl p-6 border border-zinc-200/60 shadow-xs space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <HardDrive className="w-4 h-4 text-zinc-500" />
              <h3 className="text-xs font-semibold text-zinc-900">የማከማቻ ቦታ አጠቃቀም (Storage Quota)</h3>
            </div>
            <span className="text-xs font-semibold text-zinc-900">
              {Math.round(analytics.total_used_bytes / (1024 * 1024))} MB / {Math.round(analytics.storage_limit_bytes / (1024 * 1024 * 1024))} GB ({analytics.percentage_used}%)
            </span>
          </div>

          {/* Minimal progress bar */}
          <div className="w-full bg-zinc-100 rounded-full h-2 overflow-hidden">
            <div
              className="bg-zinc-900 h-2 rounded-full transition-all duration-300"
              style={{ width: `${Math.min(100, analytics.percentage_used)}%` }}
            />
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 text-xs">
            <div className="p-3 bg-zinc-50 rounded-xl">
              <span className="text-zinc-400 block text-[10px]">የግል ድራይቭ</span>
              <span className="font-semibold text-zinc-900 block mt-0.5">
                {Math.round(analytics.personal_drive_bytes / (1024 * 1024))} MB
              </span>
            </div>
            <div className="p-3 bg-zinc-50 rounded-xl">
              <span className="text-zinc-400 block text-[10px]">የድርጅት ድራይቭ</span>
              <span className="font-semibold text-zinc-900 block mt-0.5">
                {Math.round(analytics.company_drive_bytes / (1024 * 1024))} MB
              </span>
            </div>
            <div className="p-3 bg-zinc-50 rounded-xl">
              <span className="text-zinc-400 block text-[10px]">ሪሳይክል ቢን</span>
              <span className="font-semibold text-zinc-900 block mt-0.5">
                {Math.round(analytics.trash_bytes / (1024 * 1024))} MB
              </span>
            </div>
            <div className="p-3 bg-zinc-50 rounded-xl">
              <span className="text-zinc-400 block text-[10px]">ጠቅላላ ፋይሎች</span>
              <span className="font-semibold text-zinc-900 block mt-0.5">
                {analytics.total_files} ፋይሎች ({analytics.total_folders} ፎልደሮች)
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
