import { useState, useEffect } from 'react';
import { 
  Folder, 
  Files, 
  Trash2, 
  Cloud, 
  Search, 
  Plus, 
  Mail, 
  Calendar, 
  ArrowDownLeft, 
  ArrowUpRight 
} from 'lucide-react';
import { authApi, calendarApi, filesApi, lettersApi } from './api/client';
import type { 
  UserProfile, 
  CalendarTodayResponse, 
  FileItem, 
  LetterRecord 
} from './api/types';

export default function App() {
  const [activeTab, setActiveTab] = useState<'my-files' | 'company' | 'letters' | 'trash'>('company');
  const [user, setUser] = useState<UserProfile | null>(null);
  const [calendarInfo, setCalendarInfo] = useState<CalendarTodayResponse | null>(null);
  const [files, setFiles] = useState<FileItem[]>([]);
  const [letters, setLetters] = useState<LetterRecord[]>([]);
  const [letterSearch, setLetterSearch] = useState<string>('');
  
  // Modals
  const [showFolderModal, setShowFolderModal] = useState<boolean>(false);
  const [newFolderName, setNewFolderName] = useState<string>('');
  const [showLetterModal, setShowLetterModal] = useState<boolean>(false);
  const [newLetter, setNewLetter] = useState({
    reference_number: '',
    direction: 'INWARD' as 'INWARD' | 'OUTWARD',
    subject: '',
    sender_entity: '',
    recipient_entity: '',
    notes: '',
  });

  // Initial load & automatic demo authentication
  useEffect(() => {
    async function init() {
      try {
        // Log in as seeded demo admin if not authenticated
        let currentUser = null;
        try {
          currentUser = await authApi.getMe();
        } catch {
          const authRes = await authApi.login('admin@abyssinia.et', 'Admin123!');
          currentUser = authRes.user;
        }
        setUser(currentUser);

        // Fetch Ethiopian calendar info
        const cal = await calendarApi.getToday();
        setCalendarInfo(cal);
      } catch (err) {
        console.error('Initialization error:', err);
      }
    }
    init();
  }, []);

  // Fetch content whenever activeTab changes
  useEffect(() => {
    if (!user) return;

    async function loadContent() {
      try {
        if (activeTab === 'my-files') {
          const res = await filesApi.list('PERSONAL');
          setFiles(res);
        } else if (activeTab === 'company') {
          const res = await filesApi.list('COMPANY');
          setFiles(res);
        } else if (activeTab === 'trash') {
          const res = await filesApi.list('TRASH');
          setFiles(res);
        } else if (activeTab === 'letters') {
          const res = await lettersApi.list(undefined, letterSearch || undefined);
          setLetters(res);
        }
      } catch (err) {
        console.error('Failed to load content for tab:', activeTab, err);
      }
    }
    loadContent();
  }, [activeTab, user, letterSearch]);

  const handleCreateFolder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newFolderName.trim()) return;
    try {
      const driveType = activeTab === 'company' ? 'COMPANY' : 'PERSONAL';
      const created = await filesApi.createFolder(newFolderName.trim(), driveType);
      setFiles((prev) => [...prev, created]);
      setNewFolderName('');
      setShowFolderModal(false);
    } catch (err) {
      alert('Failed to create folder');
    }
  };

  const handleCreateLetter = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLetter.reference_number || !newLetter.subject) return;
    try {
      const created = await lettersApi.create(newLetter);
      setLetters((prev) => [created, ...prev]);
      setShowLetterModal(false);
      setNewLetter({
        reference_number: '',
        direction: 'INWARD',
        subject: '',
        sender_entity: '',
        recipient_entity: '',
        notes: '',
      });
    } catch (err) {
      alert('Failed to register letter');
    }
  };

  const switchUser = async (email: string, pass: string) => {
    try {
      const res = await authApi.login(email, pass);
      setUser(res.user);
      setActiveTab('company');
    } catch (err) {
      alert('Failed to switch user');
    }
  };

  return (
    <div className="flex h-screen w-full bg-slate-50 font-sans text-slate-800">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-200 bg-white flex flex-col justify-between">
        <div>
          {/* Tenant & Brand Header */}
          <div className="h-18 flex items-center gap-3 px-5 border-b border-slate-100">
            <div className="w-10 h-10 rounded-xl bg-emerald-600 flex items-center justify-center text-white font-bold text-lg shadow-sm">
              EO
            </div>
            <div className="overflow-hidden">
              <h1 className="font-bold text-slate-900 text-sm truncate">
                {user?.organization?.name || 'EthioOffice Commercial'}
              </h1>
              <p className="text-xs text-emerald-600 font-medium">B2B Enterprise Edition</p>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-3 space-y-1">
            <button
              onClick={() => setActiveTab('company')}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                activeTab === 'company' 
                  ? 'bg-emerald-50 text-emerald-700 font-semibold' 
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <Cloud className="w-4 h-4 text-emerald-600" />
              <span>የድርጅት ማህደር (Company Drive)</span>
            </button>

            <button
              onClick={() => setActiveTab('my-files')}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                activeTab === 'my-files' 
                  ? 'bg-emerald-50 text-emerald-700 font-semibold' 
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <Files className="w-4 h-4 text-blue-600" />
              <span>የግል ማህደር (My Files)</span>
            </button>

            <button
              onClick={() => setActiveTab('letters')}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                activeTab === 'letters' 
                  ? 'bg-emerald-50 text-emerald-700 font-semibold' 
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <div className="flex items-center gap-3">
                <Mail className="w-4 h-4 text-amber-600" />
                <span>የደብዳቤ መዝገብ (Letters)</span>
              </div>
              <span className="text-[10px] uppercase font-bold bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded">
                Ethio B2B
              </span>
            </button>

            <button
              onClick={() => setActiveTab('trash')}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                activeTab === 'trash' 
                  ? 'bg-emerald-50 text-emerald-700 font-semibold' 
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <Trash2 className="w-4 h-4 text-rose-500" />
              <span>የቆሻሻ መጣያ (Recycle Bin)</span>
            </button>
          </nav>
        </div>

        {/* User Account & Switcher */}
        <div className="p-4 border-t border-slate-100 bg-slate-50/50">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-full bg-emerald-700 text-white flex items-center justify-center font-bold text-xs">
                {user?.full_name?.slice(0, 2).toUpperCase() || 'AD'}
              </div>
              <div className="overflow-hidden">
                <p className="text-xs font-semibold text-slate-900 truncate">{user?.full_name}</p>
                <p className="text-[10px] text-slate-500 uppercase">{user?.role}</p>
              </div>
            </div>
          </div>

          {/* Quick Demo Role Switcher */}
          <div className="text-[11px] text-slate-500 space-y-1">
            <p className="font-medium text-slate-700">Quick Test Accounts:</p>
            <div className="flex gap-2">
              <button 
                onClick={() => switchUser('admin@abyssinia.et', 'Admin123!')}
                className={`px-2 py-1 rounded text-[10px] border ${
                  user?.email === 'admin@abyssinia.et' 
                    ? 'bg-emerald-600 text-white border-emerald-600 font-medium' 
                    : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-100'
                }`}
              >
                Admin (Mulugeta)
              </button>
              <button 
                onClick={() => switchUser('abebe@abyssinia.et', 'Staff123!')}
                className={`px-2 py-1 rounded text-[10px] border ${
                  user?.email === 'abebe@abyssinia.et' 
                    ? 'bg-emerald-600 text-white border-emerald-600 font-medium' 
                    : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-100'
                }`}
              >
                Staff (Abebe)
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header with Live Ethiopian Calendar */}
        <header className="h-18 bg-white border-b border-slate-200 px-8 flex items-center justify-between">
          {/* Search Bar */}
          <div className="relative w-96">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input 
              type="text" 
              value={letterSearch}
              onChange={(e) => setLetterSearch(e.target.value)}
              placeholder="Search files, letters, or references (በአማርኛ ይፈልጉ)..." 
              className="w-full pl-9 pr-4 py-2 rounded-lg bg-slate-100 border-none text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          {/* Ethiopian Calendar Widget */}
          <div className="flex items-center gap-4">
            {calendarInfo && (
              <div className="flex items-center gap-3 bg-emerald-50/70 border border-emerald-200/60 rounded-xl px-4 py-2 text-xs">
                <Calendar className="w-4 h-4 text-emerald-700" />
                <div>
                  <p className="font-bold text-emerald-950">
                    {calendarInfo.ethiopian_date.formatted_amharic}
                  </p>
                  <p className="text-[10px] text-emerald-700 font-medium">
                    {calendarInfo.fiscal_year.label}
                  </p>
                </div>
              </div>
            )}

            {/* Action Button */}
            {activeTab === 'letters' ? (
              <button 
                onClick={() => setShowLetterModal(true)}
                className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium px-4 py-2 rounded-lg shadow-xs transition-colors"
              >
                <Plus className="w-4 h-4" />
                <span>ደብዳቤ መዝግብ (Register Letter)</span>
              </button>
            ) : (
              <button 
                onClick={() => setShowFolderModal(true)}
                className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium px-4 py-2 rounded-lg shadow-xs transition-colors"
              >
                <Plus className="w-4 h-4" />
                <span>አዲስ ፎልደር (New Folder)</span>
              </button>
            )}
          </div>
        </header>

        {/* Content Body */}
        <div className="flex-1 p-8 overflow-y-auto">
          {/* Section Heading */}
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h2 className="text-xl font-bold text-slate-900">
                {activeTab === 'company' && 'የድርጅት ማህደር (Company Drive)'}
                {activeTab === 'my-files' && 'የግል ማህደር (Personal Files)'}
                {activeTab === 'letters' && 'የደብዳቤ መዝገብና ክትትል (Official Letter Registry)'}
                {activeTab === 'trash' && 'የቆሻሻ መጣያ (Recycle Bin)'}
              </h2>
              <p className="text-xs text-slate-500 mt-1">
                Connected directly to Supabase PostgreSQL at 10.18.113.252
              </p>
            </div>
          </div>

          {/* Letter Registry View */}
          {activeTab === 'letters' && (
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden shadow-xs">
              <table className="w-full text-left text-sm text-slate-600">
                <thead className="bg-slate-50 text-slate-700 text-xs uppercase font-semibold border-b border-slate-200">
                  <tr>
                    <th className="px-5 py-3.5">የደብዳቤ ቁጥር (Ref)</th>
                    <th className="px-5 py-3.5">አቅጣጫ (Direction)</th>
                    <th className="px-5 py-3.5">ጉዳዩ (Subject)</th>
                    <th className="px-5 py-3.5">ላኪ / ተቀባይ (Parties)</th>
                    <th className="px-5 py-3.5">ቀን በኢ.አ (EC Date)</th>
                    <th className="px-5 py-3.5">ሁኔታ (Status)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {letters.map((l) => (
                    <tr key={l.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="px-5 py-4 font-mono font-bold text-slate-900 text-xs">
                        {l.reference_number}
                      </td>
                      <td className="px-5 py-4">
                        <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold ${
                          l.direction === 'INWARD' 
                            ? 'bg-blue-50 text-blue-700' 
                            : 'bg-emerald-50 text-emerald-700'
                        }`}>
                          {l.direction === 'INWARD' ? <ArrowDownLeft className="w-3 h-3" /> : <ArrowUpRight className="w-3 h-3" />}
                          {l.direction === 'INWARD' ? 'የገባ (Inward)' : 'የወጣ (Outward)'}
                        </span>
                      </td>
                      <td className="px-5 py-4 font-medium text-slate-900 max-w-xs truncate">
                        {l.subject}
                      </td>
                      <td className="px-5 py-4 text-xs text-slate-500">
                        <p><span className="font-semibold text-slate-700">ከ:</span> {l.sender_entity}</p>
                        <p><span className="font-semibold text-slate-700">ለ:</span> {l.recipient_entity}</p>
                      </td>
                      <td className="px-5 py-4 text-xs font-medium text-slate-700 whitespace-nowrap">
                        {l.date_ec}
                      </td>
                      <td className="px-5 py-4">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700">
                          {l.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {letters.length === 0 && (
                    <tr>
                      <td colSpan={6} className="text-center py-10 text-slate-400 text-sm">
                        ምንም የተመዘገበ ደብዳቤ የለም (No letters found)
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* Drive Files/Folders View */}
          {activeTab !== 'letters' && (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {files.map((f) => (
                <div 
                  key={f.id} 
                  className="p-4 rounded-xl border border-slate-200 bg-white hover:border-emerald-300 hover:shadow-xs transition-all flex flex-col justify-between"
                >
                  <div className="flex items-start gap-3">
                    <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center shrink-0">
                      <Folder className="w-5 h-5" />
                    </div>
                    <div className="overflow-hidden">
                      <h3 className="font-semibold text-slate-900 text-sm truncate" title={f.name}>
                        {f.name}
                      </h3>
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        {f.ec_created_at || 'በቅርቡ የተፈጠረ'}
                      </p>
                    </div>
                  </div>
                  <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400">
                    <span>{f.is_folder ? 'ፎልደር' : 'ፋይል'}</span>
                    <span className="text-emerald-600 font-medium hover:underline cursor-pointer">
                      ክፈት (Open)
                    </span>
                  </div>
                </div>
              ))}
              {files.length === 0 && (
                <div className="col-span-full text-center py-12 text-slate-400">
                  <Folder className="w-10 h-10 mx-auto text-slate-300 mb-2" />
                  <p className="text-sm">በዚህ ክፍል ውስጥ ምንም ፋይል የለም (No items in this drive)</p>
                </div>
              )}
            </div>
          )}
        </div>
      </main>

      {/* New Folder Modal */}
      {showFolderModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-100">
            <h3 className="text-lg font-bold text-slate-900 mb-2">አዲስ ፎልደር ፍጠር (Create New Folder)</h3>
            <p className="text-xs text-slate-500 mb-4">
              በ{activeTab === 'company' ? 'የድርጅት ማህደር' : 'የግል ማህደር'} ውስጥ አዲስ ማህደር ይፍጠሩ።
            </p>
            <form onSubmit={handleCreateFolder}>
              <input 
                type="text" 
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                placeholder="የፎልደር ስም ያስገቡ (e.g. የሒሳብ ሰነዶች)..." 
                autoFocus
                className="w-full px-3.5 py-2.5 rounded-lg border border-slate-200 text-sm text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500 mb-4"
              />
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowFolderModal(false)}
                  className="px-4 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-100"
                >
                  ይቅር (Cancel)
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg text-sm font-medium bg-emerald-600 text-white hover:bg-emerald-700"
                >
                  ፍጠር (Create)
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* New Letter Registry Modal */}
      {showLetterModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-lg w-full p-6 shadow-xl border border-slate-100">
            <h3 className="text-lg font-bold text-slate-900 mb-1">ደብዳቤ መዝግብ (Register Official Letter)</h3>
            <p className="text-xs text-slate-500 mb-4">
              ይህ ሰነድ በኢትዮጵያ አቆጣጠር (ዓ.ም) በራስ-ሰር ተመዝግቦ ይቀመጣል።
            </p>
            <form onSubmit={handleCreateLetter} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700 block mb-1">የደብዳቤ ቁጥር (Ref Number)</label>
                  <input 
                    type="text" 
                    required
                    placeholder="e.g. ABYSS/FIN/2019/003"
                    value={newLetter.reference_number}
                    onChange={(e) => setNewLetter({ ...newLetter, reference_number: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:ring-2 focus:ring-emerald-500 outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700 block mb-1">አቅጣጫ (Direction)</label>
                  <select
                    value={newLetter.direction}
                    onChange={(e) => setNewLetter({ ...newLetter, direction: e.target.value as any })}
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:ring-2 focus:ring-emerald-500 outline-none bg-white"
                  >
                    <option value="INWARD">የገባ ደብዳቤ (Inward)</option>
                    <option value="OUTWARD">የወጣ ደብዳቤ (Outward)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">ጉዳዩ (Subject)</label>
                <input 
                  type="text" 
                  required
                  placeholder="የደብዳቤው ዋና ጉዳይ..."
                  value={newLetter.subject}
                  onChange={(e) => setNewLetter({ ...newLetter, subject: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:ring-2 focus:ring-emerald-500 outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-700 block mb-1">ላኪ (Sender)</label>
                  <input 
                    type="text" 
                    required
                    placeholder="ላኪ ድርጅት ወይም ክፍል"
                    value={newLetter.sender_entity}
                    onChange={(e) => setNewLetter({ ...newLetter, sender_entity: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:ring-2 focus:ring-emerald-500 outline-none"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-700 block mb-1">ተቀባይ (Recipient)</label>
                  <input 
                    type="text" 
                    required
                    placeholder="ተቀባይ ድርጅት ወይም ክፍል"
                    value={newLetter.recipient_entity}
                    onChange={(e) => setNewLetter({ ...newLetter, recipient_entity: e.target.value })}
                    className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:ring-2 focus:ring-emerald-500 outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-700 block mb-1">ማስታወሻ (Notes)</label>
                <textarea 
                  rows={2}
                  placeholder="ተጨማሪ ማብራሪያ ካለ..."
                  value={newLetter.notes}
                  onChange={(e) => setNewLetter({ ...newLetter, notes: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg border border-slate-200 text-sm focus:ring-2 focus:ring-emerald-500 outline-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowLetterModal(false)}
                  className="px-4 py-2 rounded-lg text-sm text-slate-600 hover:bg-slate-100"
                >
                  ይቅር (Cancel)
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg text-sm font-medium bg-emerald-600 text-white hover:bg-emerald-700"
                >
                  መዝግብ (Save Letter)
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
