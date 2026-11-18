import React, { useState, useEffect } from 'react';
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom';
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
  Building2,
  FolderKanban,
  Database,
  Menu,
  X,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { filesApi } from '../../api/client';
import { NotificationDropdown } from './NotificationDropdown';
import { DualCalendarDropdown } from './DualCalendarDropdown';
import type { StorageAnalytics } from '../../api/types';

export const AppShell: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [analytics, setAnalytics] = useState<StorageAnalytics | null>(null);

  useEffect(() => {
    const loadStorage = async () => {
      try {
        const data = await filesApi.getAnalytics();
        setAnalytics(data);
      } catch {
        // non-fatal
      }
    };
    loadStorage();
  }, []);

  // Close mobile drawer on route change
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const getPageTitle = (path: string): string => {
    if (path.startsWith('/drive/personal')) return 'Personal Drive';
    if (path.startsWith('/drive/company')) return 'Company Drive';
    if (path.startsWith('/drive/shared')) return 'Shared with me';
    if (path.startsWith('/drive/starred')) return 'Starred Documents';
    if (path.startsWith('/drive/recent')) return 'Recent Activity';
    if (path.startsWith('/drive/trash')) return 'Recycle Bin';
    if (path.startsWith('/letters')) return 'Letter Registry';
    if (path.startsWith('/admin/organization')) return 'Organization Profile';
    if (path.startsWith('/admin/audit')) return 'Audit Ledger & Compliance';
    if (path.startsWith('/admin/users')) return 'Employee Directory';
    if (path.startsWith('/profile')) return 'User Profile';
    return 'Workspace';
  };

  const navItemClass = ({ isActive }: { isActive: boolean }) =>
    `flex items-center gap-2.5 px-3 py-2 text-xs font-semibold rounded-xl transition-all duration-150 select-none ${
      isCollapsed ? 'md:justify-center md:px-2 md:py-2.5' : ''
    } ${
      isActive
        ? 'bg-blue-50 text-blue-700 shadow-2xs font-bold'
        : 'text-slate-600 hover:text-slate-900 hover:bg-slate-100/80 font-medium'
    }`;

  const isAdmin = user?.role === 'ADMIN' || user?.role === 'SUPER_ADMIN';

  const formatBytes = (bytes: number) => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const usedBytes = analytics?.total_used_bytes || 0;
  const quotaBytes = analytics?.storage_limit_bytes || 100 * 1024 * 1024 * 1024;
  const percentageUsed = Math.min(100, Math.round((usedBytes / quotaBytes) * 100));

  return (
    <div className="min-h-screen w-full flex bg-slate-50/70 font-sans text-slate-900 antialiased overflow-x-hidden">
      {/* Mobile Drawer Backdrop */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 bg-slate-950/40 backdrop-blur-xs z-40 md:hidden transition-opacity"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Collapsible / Responsive Left Sidebar */}
      <aside
        className={`bg-white border-r border-slate-200/80 flex flex-col justify-between shrink-0 h-screen shadow-2xs transition-all duration-200 ease-in-out
          fixed inset-y-0 left-0 z-50 md:sticky md:top-0
          ${isMobileMenuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
          ${isCollapsed ? 'md:w-18 w-64' : 'w-64'}
        `}
      >
        <div>
          {/* Organization Brand Header (Company Logo collapses/expands sidebar) */}
          <div
            className={`p-4 flex items-center border-b border-slate-100 ${
              isCollapsed ? 'md:justify-center justify-between' : 'justify-between'
            }`}
          >
            <div className="flex items-center gap-3 min-w-0">
              <button
                type="button"
                onClick={() => setIsCollapsed(!isCollapsed)}
                className="w-9 h-9 rounded-xl bg-blue-50 hover:bg-blue-100 border border-blue-200/80 text-blue-600 flex items-center justify-center font-bold text-xs tracking-wider shrink-0 shadow-xs transition-all active:scale-95 cursor-pointer focus:outline-none"
                title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              >
                <FolderKanban className="w-5 h-5 text-blue-600" />
              </button>
              <div className={`min-w-0 flex-1 ${isCollapsed ? 'md:hidden' : ''}`}>
                <h2 className="text-sm font-bold text-slate-900 truncate tracking-tight">
                  {user?.organization.name || 'Wine Technologies'}
                </h2>
                <p className="text-[11px] text-slate-400 font-medium truncate">
                  {user?.organization.slug ? `@${user.organization.slug}` : 'Private Workspace'}
                </p>
              </div>
            </div>

            {/* Mobile close button */}
            <button
              type="button"
              onClick={() => setIsMobileMenuOpen(false)}
              className="md:hidden p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
              title="Close navigation"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Navigation Items */}
          <div className="p-3 space-y-6 overflow-y-auto max-h-[calc(100vh-220px)]">
            {/* Drive Section */}
            <div>
              <p className={`px-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2 ${isCollapsed ? 'md:hidden' : ''}`}>
                Drive & Files
              </p>
              <nav className="space-y-0.5">
                <NavLink to="/drive/personal" className={navItemClass} title="Personal Drive">
                  <HardDrive className="w-4 h-4 shrink-0" />
                  <span className={isCollapsed ? 'md:hidden' : ''}>Personal Drive</span>
                </NavLink>
                <NavLink to="/drive/company" className={navItemClass} title="Company Drive">
                  <Building2 className="w-4 h-4 shrink-0" />
                  <span className={isCollapsed ? 'md:hidden' : ''}>Company Drive</span>
                </NavLink>
                <NavLink to="/drive/shared" className={navItemClass} title="Shared with me">
                  <Share2 className="w-4 h-4 shrink-0" />
                  <span className={isCollapsed ? 'md:hidden' : ''}>Shared with me</span>
                </NavLink>
                <NavLink to="/drive/starred" className={navItemClass} title="Starred">
                  <Star className="w-4 h-4 shrink-0" />
                  <span className={isCollapsed ? 'md:hidden' : ''}>Starred</span>
                </NavLink>
                <NavLink to="/drive/recent" className={navItemClass} title="Recent">
                  <Clock className="w-4 h-4 shrink-0" />
                  <span className={isCollapsed ? 'md:hidden' : ''}>Recent</span>
                </NavLink>
                <NavLink to="/drive/trash" className={navItemClass} title="Trash">
                  <Trash2 className="w-4 h-4 shrink-0" />
                  <span className={isCollapsed ? 'md:hidden' : ''}>Trash</span>
                </NavLink>
              </nav>
            </div>

            {/* Official Letters Section */}
            <div>
              <p className={`px-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2 ${isCollapsed ? 'md:hidden' : ''}`}>
                Correspondence
              </p>
              <nav className="space-y-0.5">
                <NavLink to="/letters" className={navItemClass} end title="Letter Registry">
                  <Mail className="w-4 h-4 shrink-0" />
                  <span className={isCollapsed ? 'md:hidden' : ''}>Letter Registry</span>
                </NavLink>
              </nav>
            </div>

            {/* Admin Section */}
            {isAdmin && (
              <div>
                <p className={`px-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2 ${isCollapsed ? 'md:hidden' : ''}`}>
                  Administration
                </p>
                <nav className="space-y-0.5">
                  <NavLink to="/admin/organization" className={navItemClass} title="Organization Profile">
                    <Shield className="w-4 h-4 shrink-0" />
                    <span className={isCollapsed ? 'md:hidden' : ''}>Organization Profile</span>
                  </NavLink>
                  <NavLink to="/admin/audit" className={navItemClass} title="Audit Ledger">
                    <FileCheck className="w-4 h-4 shrink-0" />
                    <span className={isCollapsed ? 'md:hidden' : ''}>Audit Ledger</span>
                  </NavLink>
                  <NavLink to="/admin/users" className={navItemClass} title="Employee Directory">
                    <Users2 className="w-4 h-4 shrink-0" />
                    <span className={isCollapsed ? 'md:hidden' : ''}>Employee Directory</span>
                  </NavLink>
                </nav>
              </div>
            )}
          </div>
        </div>

        {/* Bottom Section: Storage Quota Meter + User Card */}
        <div className="p-3 border-t border-slate-100 bg-white space-y-2.5">
          {/* Storage Quota Bar */}
          <div className={isCollapsed ? 'hidden md:block' : ''}>
            {isCollapsed ? (
              <div className="flex justify-center py-1" title={`Storage: ${percentageUsed}% used`}>
                <Database className="w-4 h-4 text-blue-600" />
              </div>
            ) : (
              <div className="p-2.5 rounded-xl bg-slate-50 border border-slate-100 space-y-1.5">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="font-semibold text-slate-700 flex items-center gap-1.5">
                    <Database className="w-3.5 h-3.5 text-blue-600" />
                    <span>Storage</span>
                  </span>
                  <span className="text-slate-500 font-medium">{percentageUsed}%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-200/80 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-600 rounded-full transition-all duration-300"
                    style={{ width: `${percentageUsed}%` }}
                  />
                </div>
                <p className="text-[10px] text-slate-400">
                  {formatBytes(usedBytes)} of {formatBytes(quotaBytes)} used
                </p>
              </div>
            )}
          </div>

          {/* User Profile Card */}
          <div
            className={`flex items-center rounded-xl hover:bg-slate-50 transition-colors border border-transparent hover:border-slate-100 ${
              isCollapsed ? 'md:justify-center md:p-1 justify-between p-2' : 'justify-between p-2'
            }`}
          >
            <NavLink to="/profile" className="flex items-center gap-2.5 min-w-0 flex-1" title={user?.full_name}>
              <div className="w-8 h-8 rounded-full bg-blue-50 border border-blue-100 text-blue-700 flex items-center justify-center font-bold text-xs shrink-0">
                {user?.full_name?.slice(0, 1).toUpperCase() || 'U'}
              </div>
              <div className={`min-w-0 flex-1 text-left ${isCollapsed ? 'md:hidden' : ''}`}>
                <p className="text-xs font-bold text-slate-900 truncate">{user?.full_name}</p>
                <p className="text-[10px] text-slate-400 font-medium truncate">{user?.email}</p>
              </div>
            </NavLink>
            <button
              onClick={handleLogout}
              className={`p-1.5 text-slate-400 hover:text-red-600 rounded-lg hover:bg-slate-100 transition-colors shrink-0 ${
                isCollapsed ? 'md:hidden' : ''
              }`}
              title="Sign Out"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Area */}
      <div className="flex-1 flex flex-col min-w-0 w-full">
        {/* Top Header Bar */}
        <header className="h-14 bg-white border-b border-slate-200/80 px-2.5 sm:px-4 md:px-6 flex items-center justify-between sticky top-0 z-30 shadow-2xs gap-1.5 sm:gap-3 w-full min-w-0">
          {/* Left: Mobile Menu Toggle + Page Title (Pure English & Prominent) */}
          <div className="flex items-center gap-1.5 sm:gap-2.5 min-w-0 shrink">
            <button
              type="button"
              onClick={() => setIsMobileMenuOpen(true)}
              className="md:hidden p-1.5 sm:p-2 text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-xl transition-colors focus:outline-none shrink-0"
              title="Open navigation menu"
            >
              <Menu className="w-5 h-5" />
            </button>

            <h1 className="text-sm sm:text-base md:text-lg lg:text-xl font-bold text-slate-900 tracking-tight truncate min-w-0">
              {getPageTitle(location.pathname)}
            </h1>
          </div>

          {/* Center: Search Bar (Fluid & Gracefully Collapsing) */}
          <div className="flex-1 max-w-xs md:max-w-md mx-1 sm:mx-2 md:mx-4 min-w-0 flex justify-center">
            {/* Full search button on sm and up */}
            <button
              onClick={() => {
                const event = new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true });
                window.dispatchEvent(event);
              }}
              className="hidden sm:flex w-full items-center justify-between px-2.5 sm:px-3.5 py-1.5 rounded-xl bg-slate-100/80 hover:bg-slate-200/70 border border-slate-200/60 text-slate-500 hover:text-slate-800 transition-all text-xs font-medium shadow-2xs min-w-0"
            >
              <div className="flex items-center gap-2 truncate min-w-0">
                <Search className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                <span className="truncate hidden md:inline">Search documents, files, letters...</span>
                <span className="truncate md:hidden">Search...</span>
              </div>
              <kbd className="hidden lg:inline-block text-[10px] bg-white text-slate-400 px-1.5 py-0.5 rounded-md shadow-2xs font-mono ml-2 border border-slate-200/60 shrink-0">
                Ctrl+K
              </kbd>
            </button>

            {/* Compact search icon button on narrow mobile < sm */}
            <button
              onClick={() => {
                const event = new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true });
                window.dispatchEvent(event);
              }}
              className="sm:hidden p-2 text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded-xl transition-colors shrink-0"
              title="Search (Ctrl+K)"
            >
              <Search className="w-4 h-4" />
            </button>
          </div>

          {/* Right: Dual Calendar Popover + Notification Dropdown */}
          <div className="flex items-center gap-1 sm:gap-2 shrink-0">
            {/* Interactive Dual Calendar Dropdown */}
            <DualCalendarDropdown />

            {/* Notification Dropdown */}
            <NotificationDropdown />
          </div>
        </header>

        {/* Page Content Canvas */}
        <main className="flex-1 p-3 sm:p-5 md:p-6 overflow-y-auto min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
