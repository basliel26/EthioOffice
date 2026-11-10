import { useState } from 'react'
import { 
  Folder, 
  Files, 
  Users, 
  Trash2, 
  Cloud, 
  FileText, 
  ShieldCheck, 
  Lock, 
  Search,
  Plus
} from 'lucide-react'

export default function App() {
  const [activeTab, setActiveTab] = useState<'my-files' | 'shared' | 'company' | 'trash'>('my-files')

  return (
    <div className="flex h-screen w-full bg-slate-50 font-sans text-slate-800">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-200 bg-white flex flex-col justify-between">
        <div>
          {/* Logo / Branding */}
          <div className="h-16 flex items-center gap-3 px-6 border-b border-slate-100">
            <div className="w-9 h-9 rounded-lg bg-emerald-600 flex items-center justify-center text-white shadow-sm font-bold text-lg">
              EO
            </div>
            <div>
              <h1 className="font-bold text-slate-900 leading-tight">EthioOffice</h1>
              <p className="text-xs text-slate-400">Collaboration Hub</p>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-4 space-y-1">
            <button
              onClick={() => setActiveTab('my-files')}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                activeTab === 'my-files' 
                  ? 'bg-emerald-50 text-emerald-700 font-semibold' 
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <Files className="w-4 h-4 text-emerald-600" />
              <span>My Files</span>
            </button>

            <button
              onClick={() => setActiveTab('shared')}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                activeTab === 'shared' 
                  ? 'bg-emerald-50 text-emerald-700 font-semibold' 
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <Users className="w-4 h-4 text-blue-600" />
              <span>Shared with Me</span>
            </button>

            <button
              onClick={() => setActiveTab('company')}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                activeTab === 'company' 
                  ? 'bg-emerald-50 text-emerald-700 font-semibold' 
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              <Cloud className="w-4 h-4 text-amber-600" />
              <span>Company Drive</span>
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
              <span>Recycle Bin</span>
            </button>
          </nav>
        </div>

        {/* Euro-Office Status Badge */}
        <div className="p-4 m-4 rounded-xl bg-slate-50 border border-slate-200 text-xs">
          <div className="flex items-center gap-2 text-slate-700 font-medium mb-1">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            Euro-Office Co-Authoring
          </div>
          <p className="text-slate-400">Simultaneous real-time editing connector ready.</p>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header */}
        <header className="h-16 bg-white border-b border-slate-200 px-8 flex items-center justify-between">
          <div className="relative w-96">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input 
              type="text" 
              placeholder="Search files, folders, and document contents..." 
              className="w-full pl-9 pr-4 py-2 rounded-lg bg-slate-100 border-none text-sm text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div className="flex items-center gap-4">
            <button className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium px-4 py-2 rounded-lg shadow-sm transition-colors">
              <Plus className="w-4 h-4" />
              <span>Upload / New</span>
            </button>
            <div className="w-9 h-9 rounded-full bg-slate-200 flex items-center justify-center font-bold text-slate-700 text-sm">
              AD
            </div>
          </div>
        </header>

        {/* Content Body */}
        <div className="flex-1 p-8 overflow-y-auto">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-slate-900 capitalize">
                {activeTab.replace('-', ' ')}
              </h2>
              <p className="text-sm text-slate-500 mt-1">
                Scaffolding completed. Ready for tomorrow's database schema session.
              </p>
            </div>
          </div>

          {/* Cards for Architecture Overview */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6">
            <div className="p-6 rounded-xl border border-slate-200 bg-white shadow-xs">
              <div className="w-10 h-10 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center mb-4">
                <Folder className="w-5 h-5" />
              </div>
              <h3 className="font-semibold text-slate-900 mb-1">Modern File Hub</h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                Replaces network share folders with organized personal, team, and company drives.
              </p>
            </div>

            <div className="p-6 rounded-xl border border-slate-200 bg-white shadow-xs">
              <div className="w-10 h-10 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center mb-4">
                <FileText className="w-5 h-5" />
              </div>
              <h3 className="font-semibold text-slate-900 mb-1">Euro-Office Real-Time</h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                Simultaneous document co-authoring for multiple users with live cursors.
              </p>
            </div>

            <div className="p-6 rounded-xl border border-slate-200 bg-white shadow-xs">
              <div className="w-10 h-10 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center mb-4">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <h3 className="font-semibold text-slate-900 mb-1">Security & Versioning</h3>
              <p className="text-xs text-slate-500 leading-relaxed">
                File locking, version rollback, activity logs, and granular access rights.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}
