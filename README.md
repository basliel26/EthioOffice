# EthioOffice 🇪🇹

EthioOffice is a self-hosted, secure, web-based file sharing and collaboration platform designed for Ethiopian offices and businesses to replace local network shared folders (SMB) with a modern Google Drive / Nextcloud-style workspace and real-time Euro-Office co-authoring.

---

## 🌟 Key Features

- **Intuitive Web File Explorer**:
  - **📁 My Files**: Personal private employee documents.
  - **👥 Shared with Me**: Items shared directly with users or departments with fine-grained permissions (Viewer vs. Editor).
  - **🏢 Company Drive**: Public company spaces and restricted department spaces.
  - **🗑️ Recycle Bin**: Soft delete with restore capabilities.
- **Euro-Office Live Co-Editing**:
  - Simultaneous multi-user editing for Word (`.docx`), Excel (`.xlsx`), and PowerPoint (`.pptx`) documents.
  - Real-time colored cursors, co-author presence, and instant sync.
- **Enterprise Collaboration & Security**:
  - File Locking (Check-in / Check-out).
  - Version History & Rollback.
  - In-browser document & PDF previews.
  - Full audit logging & activity trail.
  - Full-text & metadata search.
  - Migration tool to import existing office network shares.

---

## 🏗️ Architecture & Project Structure

```
EthioOffice/
├── backend/                  # FastAPI (Python 3.11+) Backend
│   ├── app/
│   │   ├── api/v1/           # API routes (Auth, Files, Euro-Office, Shares)
│   │   ├── core/             # Configuration & security settings
│   │   ├── models/           # Database models (PostgreSQL) - Scheduled for review
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Storage, indexing, and Euro-Office services
│   │   └── main.py           # Application entrypoint
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                 # React 18+ (Vite + TypeScript + Tailwind)
│   ├── src/
│   │   ├── components/       # Explorer, Viewer, Share Modals
│   │   ├── pages/            # My Files, Shared, Company, Trash
│   │   └── services/         # API client & Euro-Office loader
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml        # Orchestration (Backend + Frontend + Postgres + Euro-Office)
└── README.md
```

---

## 🚀 Quickstart (Local Development)

### 1. Backend (FastAPI)
```bash
cd backend
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
- API Docs: `http://localhost:8000/api/v1/docs`
- Health check: `http://localhost:8000/api/v1/health`

### 2. Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev
```
- Web UI: `http://localhost:5173`

### 3. Full Stack via Docker
```bash
docker compose up -d
```
Runs the Backend, Frontend, PostgreSQL database, and Euro-Office Document Server together.
