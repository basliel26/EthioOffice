import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import {
  UploadCloud,
  FileCheck,
  Lock,
  Clock,
  ShieldCheck,
  AlertCircle,
  Loader2,
  FolderDown,
} from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { publicApi } from '../../api/client';
import type { PublicLinkMetadataResponse, FileItem } from '../../api/types';

export const PublicDropboxPage: React.FC = () => {
  const { token } = useParams<{ token: string }>();

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [metadata, setMetadata] = useState<PublicLinkMetadataResponse | null>(null);

  // Password verification
  const [isPasswordRequired, setIsPasswordRequired] = useState(false);
  const [password, setPassword] = useState('');
  const [isUnlocked, setIsUnlocked] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  // Deposit upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedReceipt, setUploadedReceipt] = useState<FileItem | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!token) return;
    loadMetadata();
  }, [token]);

  const loadMetadata = async () => {
    if (!token) return;
    setIsLoading(true);
    setError(null);

    try {
      const data = await publicApi.getMetadata(token);
      setMetadata(data);
      if (data.is_password_protected) {
        setIsPasswordRequired(true);
      } else {
        setIsUnlocked(true);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'ይህ ድሮፕ ቦክስ አልተገኘም ወይም ጊዜው አልፏል';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !password) return;

    setIsLoading(true);
    setPasswordError(null);

    try {
      await publicApi.verifyPassword(token, password);
      setIsUnlocked(true);
      setIsPasswordRequired(false);
    } catch {
      setPasswordError('የተሳሳተ የይለፍ ቃል ነው (Incorrect password. Please try again.)');
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setUploadError(null);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
      setUploadError(null);
    }
  };

  const handleUploadDeposit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !selectedFile) return;

    setIsUploading(true);
    setUploadError(null);

    try {
      const receipt = await publicApi.uploadToDropbox(token, selectedFile, password || undefined);
      setUploadedReceipt(receipt);
      setSelectedFile(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'ፋይሉን ማስቀመጥ አልተቻለም (Failed to deposit file)';
      setUploadError(msg);
    } finally {
      setIsUploading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-zinc-50/50 flex flex-col items-center justify-center p-6 text-xs text-zinc-500">
        <Loader2 className="w-5 h-5 animate-spin text-zinc-700 mb-3" />
        <span>ድሮፕ ቦክስ እየተጫነ ነው...</span>
      </div>
    );
  }

  if (error || !metadata) {
    return (
      <div className="min-h-screen bg-zinc-50/50 flex flex-col items-center justify-center p-6 font-sans">
        <div className="w-full max-w-md bg-white border border-zinc-200/60 rounded-2xl p-8 text-center shadow-xs">
          <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center text-red-600 mx-auto mb-4">
            <AlertCircle className="w-6 h-6" />
          </div>
          <h2 className="text-base font-semibold text-zinc-900 mb-1">ድሮፕ ቦክስ ሊከፈት አልቻለም</h2>
          <p className="text-xs text-zinc-500 mb-6">
            ይህ የመሰብሰቢያ አገናኝ ጊዜው አልፏል ወይም በድርጅቱ አስተዳዳሪ ተዘግቷል።
          </p>
          <div className="pt-2 text-[11px] text-zinc-400 border-t border-zinc-100">
            EthioOffice Enterprise Secure Deposit Box
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-50/50 flex flex-col items-center justify-center p-4 md:p-6 font-sans select-none">
      {/* Brand Header */}
      <div className="mb-6 text-center">
        <h1 className="text-sm font-semibold tracking-tight text-zinc-900">
          EthioOffice
        </h1>
        <p className="text-[11px] text-zinc-400">ደህንነቱ የተጠበቀ ሰነድ ማስቀመጫ ድሮፕ ቦክስ (Client Document Deposit)</p>
      </div>

      <div className="w-full max-w-lg bg-white border border-zinc-200/60 rounded-2xl p-6 md:p-8 shadow-xs">
        {isPasswordRequired && !isUnlocked ? (
          /* Password Prompt */
          <form onSubmit={handleVerifyPassword} className="space-y-4">
            <div className="w-10 h-10 rounded-full bg-zinc-100 flex items-center justify-center text-zinc-700 mx-auto mb-2">
              <Lock className="w-5 h-5" />
            </div>

            <div className="text-center space-y-1">
              <h2 className="text-sm font-semibold text-zinc-900">ይህ ድሮፕ ቦክስ በይለፍ ቃል የተጠበቀ ነው</h2>
              <p className="text-xs text-zinc-500">
                ፋይሎችን ለማስቀመጥ እባክዎ በድርጅቱ የተሰጠውን የይለፍ ቃል ያስገቡ።
              </p>
            </div>

            {passwordError && (
              <div className="p-2.5 bg-red-50 text-red-700 text-xs rounded-lg flex items-center gap-2">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span>{passwordError}</span>
              </div>
            )}

            <Input
              type="password"
              placeholder="የይለፍ ቃል (Password)..."
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoFocus
              required
            />

            <Button
              type="submit"
              variant="primary"
              size="md"
              className="w-full"
              leftIcon={<ShieldCheck className="w-4 h-4" />}
            >
              ይለፍ ቃል አረጋግጥ (Verify Password)
            </Button>
          </form>
        ) : uploadedReceipt ? (
          /* Success Receipt State */
          <div className="space-y-6 text-center">
            <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mx-auto">
              <FileCheck className="w-6 h-6" />
            </div>

            <div className="space-y-1">
              <h2 className="text-sm font-semibold text-zinc-900">ፋይሉ በተሳካ ሁኔታ ተቀምጧል</h2>
              <p className="text-xs text-zinc-500">
                ሰነድዎ ወደ ድርጅቱ ማህደር ገብቶ ደህንነቱ በተጠበቀ ሁኔታ ተመዝግቧል።
              </p>
            </div>

            <div className="p-4 bg-zinc-50/70 rounded-xl space-y-2 text-xs text-left border border-zinc-100">
              <div className="flex justify-between">
                <span className="text-zinc-400">የፋይል ስም:</span>
                <span className="font-medium text-zinc-800">{uploadedReceipt.name}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">መጠን:</span>
                <span className="text-zinc-600">{Math.round(uploadedReceipt.size_bytes / 1024)} KB</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">የተመዘገበበት ቀን (ዓ.ም):</span>
                <span className="text-zinc-600">{uploadedReceipt.ec_created_at || 'ዛሬ'}</span>
              </div>
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setUploadedReceipt(null);
                setSelectedFile(null);
              }}
            >
              ሌላ ፋይል አስቀምጥ (Deposit Another File)
            </Button>
          </div>
        ) : (
          /* Deposit Zone */
          <form onSubmit={handleUploadDeposit} className="space-y-6">
            <div className="flex items-center gap-3 pb-4 border-b border-zinc-100">
              <div className="w-10 h-10 rounded-xl bg-zinc-100 flex items-center justify-center text-zinc-700 shrink-0">
                <FolderDown className="w-5 h-5" />
              </div>
              <div className="min-w-0 flex-1">
                <h2 className="text-xs font-semibold text-zinc-900 truncate">
                  የተቀባይ ማህደር: {metadata.file_name}
                </h2>
                <p className="text-[11px] text-zinc-400">
                  ደህንነቱ የተጠበቀ የሰነድ ማስቀመጫ በር
                </p>
              </div>
            </div>

            {uploadError && (
              <div className="p-2.5 bg-red-50 text-red-700 text-xs rounded-lg flex items-center gap-2">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span>{uploadError}</span>
              </div>
            )}

            {/* Drag & Drop Area */}
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
              className="border border-dashed border-zinc-300 hover:border-zinc-500 bg-zinc-50/50 hover:bg-zinc-50 transition-colors rounded-xl p-8 text-center cursor-pointer space-y-3"
            >
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                onChange={handleFileSelect}
              />

              <div className="w-10 h-10 rounded-full bg-white shadow-xs border border-zinc-200/80 flex items-center justify-center text-zinc-600 mx-auto">
                <UploadCloud className="w-5 h-5" />
              </div>

              {selectedFile ? (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-zinc-900">{selectedFile.name}</p>
                  <p className="text-[10px] text-zinc-400">
                    {Math.round(selectedFile.size / 1024)} KB — ለመቀየር ጠቅ ያድርጉ
                  </p>
                </div>
              ) : (
                <div className="space-y-1">
                  <p className="text-xs font-medium text-zinc-800">
                    ፋይል እዚህ ይጎትቱ ወይም ለመምረጥ ጠቅ ያድርጉ
                  </p>
                  <p className="text-[10px] text-zinc-400">
                    PDF, Word, Excel, ምስሎች እና ሌሎች ቅርጸቶች ይደገፋሉ
                  </p>
                </div>
              )}
            </div>

            {metadata.expires_at && (
              <div className="flex items-center justify-between text-xs text-zinc-400">
                <span className="flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5" /> የሚያበቃበት ቀን:
                </span>
                <span>{new Date(metadata.expires_at).toLocaleDateString()}</span>
              </div>
            )}

            <Button
              type="submit"
              variant="primary"
              size="md"
              className="w-full"
              isLoading={isUploading}
              disabled={!selectedFile}
              leftIcon={<UploadCloud className="w-4 h-4" />}
            >
              ፋይሉን አስቀምጥ (Submit Document)
            </Button>
          </form>
        )}

        <div className="mt-8 pt-4 border-t border-zinc-100 flex items-center justify-between text-[11px] text-zinc-400">
          <span>EthioOffice Enterprise Dropbox</span>
          <span>አዲስ አበባ, ኢትዮጵያ</span>
        </div>
      </div>
    </div>
  );
};
