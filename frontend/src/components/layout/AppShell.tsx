import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  HardDrive,
  Users2,
  Share2,
  Star,
  Clock,
  Trash2,
  Mail,
  Shield,
  FileCheck,
  Search,
  LogOut,
  Calendar,
  Building,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { NotificationDropdown } from './NotificationDropdown';

export const AppShell: React.FC = () => {
  const { user, calendarInfo, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItemClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2.5 px-3 py-2 text-xs font-medium rounded-lg transition-colors select-none ${
      isActive
        ? 'bg-zinc-900 text-white shadow-xs'
        : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100/70'
    }`;

  const isAdmin = user?.role === 'ADMIN' || user?.role === 'SUPER_ADMIN';

  return (
    <div className="min-h-screen w-full flex bg-zinc-50/50 font-sans text-zinc-900 antialiased">
      {/* Minimal Left Sidebar */}
      <aside className="w-64 bg-white border-r border-zinc-200/60 flex flex-col justify-between shrink-0 h-screen sticky top-0">
        <div>
          {/* Organization Brand Header */}
          <div className="p-4 flex items-center gap-3 border-b border-zinc-100">
            <div className="w-8 h-8 rounded-xl bg-zinc-900 text-white flex items-center justify-center font-semibold text-xs tracking-wider shrink-0 shadow-xs">
              {user?.organization.name?.slice(0, 2).toUpperCase() || 'EO'}
            </div>
            <div className="min-w-0 flex-1">
              <h2 className="text-xs font-semibold text-zinc-900 truncate tracking-tight">
                {user?.organization.name || 'EthioOffice'}
              </h2>
              <p className="text-[10px] text-zinc-400 truncate">
                {user?.organization.slug ? `@${user.organization.slug}` : 'Enterprise Suite'}
              </p>
            </div>
          </div>

          {/* Navigation Items */}
          <div className="p-3 space-y-6 overflow-y-auto max-h-[calc(100vh-180px)]">
            {/* Drive Section */}
            <div>
              <p className="px-3 text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">
                ሰነዶች እና ድራይቭ (Drive)
              </p>
              <nav className="space-y-0.5">
                <NavLink to="/drive/personal" className={navItemClass}>
                  <HardDrive className="w-4 h-4 shrink-0" />
                  <span>የግል ድራይቭ (My Drive)</span>
                </NavLink>
                <NavLink to="/drive/company" className={navItemClass}>
                  <Building className="w-4 h-4 shrink-0" />
                  <span>የድርጅት ድራይቭ (Company)</span>
                </NavLink>
                <NavLink to="/drive/shared" className={navItemClass}>
                  <Share2 className="w-4 h-4 shrink-0" />
                  <span>የተጋሩ (Shared With Me)</span>
                </NavLink>
                <NavLink to="/drive/starred" className={navItemClass}>
                  <Star className="w-4 h-4 shrink-0" />
                  <span>ተመራጭ (Starred)</span>
                </NavLink>
                <NavLink to="/drive/recent" className={navItemClass}>
                  <Clock className="w-4 h-4 shrink-0" />
                  <span>የቅርብ ጊዜ (Recent)</span>
                </NavLink>
                <NavLink to="/drive/trash" className={navItemClass}>
                  <Trash2 className="w-4 h-4 shrink-0" />
                  <span>ሪሳይክል ቢን (Trash)</span>
                </NavLink>
              </nav>
            </div>

            {/* Official Letters Section */}
            <div>
              <p className="px-3 text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">
                የደብዳቤ መዝገብ (Letters)
              </p>
              <nav className="space-y-0.5">
                <NavLink to="/letters" className={navItemClass} end>
                  <Mail className="w-4 h-4 shrink-0" />
                  <span>የደብዳቤዎች መዝገብ ቤት</span>
                </NavLink>
              </nav>
            </div>

            {/* Admin Section */}
            {isAdmin && (
              <div>
                <p className="px-3 text-[10px] font-semibold text-zinc-400 uppercase tracking-wider mb-1.5">
                  አስተዳደር እና ቁጥጥር (Admin)
                </p>
                <nav className="space-y-0.5">
                  <NavLink to="/admin/organization" className={navItemClass}>
                    <Shield className="w-4 h-4 shrink-0" />
                    <span>ድርጅት እና ፍቃድ (License)</span>
                  </NavLink>
                  <NavLink to="/admin/audit" className={navItemClass}>
                    <FileCheck className="w-4 h-4 shrink-0" />
                    <span>የቁጥጥር መዝገብ (Audit Ledger)</span>
                  </NavLink>
                  <NavLink to="/admin/users" className={navItemClass}>
                    <Users2 className="w-4 h-4 shrink-0" />
                    <span>ሰራተኞች (User Directory)</span>
                  </NavLink>
                </nav>
              </div>
            )}
          </div>
        </div>

        {/* User Card & Logout Footer */}
        <div className="p-3 border-t border-zinc-100 bg-white">
          <div className="flex items-center justify-between p-2 rounded-xl hover:bg-zinc-50 transition-colors">
            <NavLink to="/profile" className="flex items-center gap-2.5 min-w-0 flex-1">
              <div className="w-7 h-7 rounded-full bg-zinc-200 text-zinc-700 flex items-center justify-center font-medium text-xs shrink-0">
                {user?.full_name?.slice(0, 1).toUpperCase() || 'U'}
              </div>
              <div className="min-w-0 flex-1 text-left">
                <p className="text-xs font-medium text-zinc-900 truncate">{user?.full_name}</p>
                <p className="text-[10px] text-zinc-400 truncate">{user?.email}</p>
              </div>
            </NavLink>
            <button
              onClick={handleLogout}
              className="p-1.5 text-zinc-400 hover:text-zinc-700 rounded-lg hover:bg-zinc-100 transition-colors shrink-0"
              title="ውጣ (Sign Out)"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header Bar */}
        <header className="h-14 bg-white border-b border-zinc-200/60 px-6 flex items-center justify-between sticky top-0 z-30">
          {/* Quick Search Button */}
          <button
            onClick={() => {
              const event = new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true });
              window.dispatchEvent(event);
            }}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-zinc-100/70 hover:bg-zinc-200/60 text-zinc-500 hover:text-zinc-700 transition-colors text-xs font-medium"
          >
            <Search className="w-3.5 h-3.5" />
            <span>ፈልግ... (Search files or letters)</span>
            <kbd className="text-[10px] bg-white text-zinc-400 px-1.5 py-0.5 rounded shadow-2xs font-mono ml-2">
              ⌘K
            </kbd>
          </button>

          {/* Right Header Utilities */}
          <div className="flex items-center gap-3">
            {/* Ethiopian Calendar Badge */}
            {calendarInfo?.ethiopian_date && (
              <div className="flex items-center gap-1.5 text-xs text-zinc-600 bg-zinc-50 border border-zinc-200/60 px-2.5 py-1 rounded-lg">
                <Calendar className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                <span className="font-medium text-zinc-700">
                  {calendarInfo.ethiopian_date.formatted_amharic}
                </span>
              </div>
            )}

            {/* Notification Dropdown */}
            <NotificationDropdown />
          </div>
        </header>

        {/* Page Content Canvas */}
        <main className="flex-1 p-6 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
