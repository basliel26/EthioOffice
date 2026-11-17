import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { AppShell } from './components/layout/AppShell';
import { CommandPalette } from './components/search/CommandPalette';
import { LoginPage } from './pages/auth/LoginPage';
import { RegisterOrgPage } from './pages/auth/RegisterOrgPage';
import { DrivePage } from './pages/drive/DrivePage';
import { LettersPage } from './pages/letters/LettersPage';
import { AdminAuditPage } from './pages/admin/AdminAuditPage';
import { AdminUsersPage } from './pages/admin/AdminUsersPage';
import { AdminOrganizationPage } from './pages/admin/AdminOrganizationPage';
import { UserProfilePage } from './pages/profile/UserProfilePage';
import { DocumentEditorPage } from './pages/editor/DocumentEditorPage';
import { PublicSharePage } from './pages/public/PublicSharePage';
import { PublicDropboxPage } from './pages/public/PublicDropboxPage';

const ProtectedLayout: React.FC = () => {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-zinc-50 text-xs text-zinc-400">
        እየተጫነ ነው (Loading EthioOffice)...
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <>
      <AppShell />
      <CommandPalette />
    </>
  );
};

const ProtectedEditorRoute: React.FC = () => {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen w-full flex items-center justify-center bg-zinc-50 text-xs text-zinc-400">
        እየተጫነ ነው (Loading EthioOffice Document)...
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <DocumentEditorPage />;
};

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public Portal & Auth Routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterOrgPage />} />
          <Route path="/share/:token" element={<PublicSharePage />} />
          <Route path="/dropbox/:token" element={<PublicDropboxPage />} />

          {/* Fullscreen Document Workspace Route */}
          <Route path="/editor/:fileId" element={<ProtectedEditorRoute />} />

          {/* Authenticated Application Shell Routes */}
          <Route element={<ProtectedLayout />}>
            <Route path="/" element={<Navigate to="/drive/personal" replace />} />
            
            {/* Drive & File Workspace */}
            <Route path="/drive" element={<Navigate to="/drive/personal" replace />} />
            <Route path="/drive/personal" element={<DrivePage viewMode="PERSONAL" />} />
            <Route path="/drive/company" element={<DrivePage viewMode="COMPANY" />} />
            <Route path="/drive/shared" element={<DrivePage viewMode="SHARED" />} />
            <Route path="/drive/starred" element={<DrivePage viewMode="STARRED" />} />
            <Route path="/drive/recent" element={<DrivePage viewMode="RECENT" />} />
            <Route path="/drive/trash" element={<DrivePage viewMode="TRASH" />} />

            {/* Official Letter Registry */}
            <Route path="/letters" element={<LettersPage />} />
            <Route path="/letters/:id" element={<LettersPage />} />

            {/* Admin & Compliance */}
            <Route path="/admin/organization" element={<AdminOrganizationPage />} />
            <Route path="/admin/audit" element={<AdminAuditPage />} />
            <Route path="/admin/users" element={<AdminUsersPage />} />

            {/* User Profile */}
            <Route path="/profile" element={<UserProfilePage />} />
          </Route>

          {/* Fallback */}
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
