import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  FileText,
  Download,
  Lock,
  Clock,
  ShieldCheck,
  AlertCircle,
  Loader2,
  Folder,
} from 'lucide-react';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { publicApi } from '../../api/client';
import type { PublicLinkMetadataResponse } from '../../api/types';

export const PublicSharePage: React.FC = () => {
  const { token } = useParams<{ token: string }>();

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [metadata, setMetadata] = useState<PublicLinkMetadataResponse | null>(null);

  // Password verification state
  const [isPasswordRequired, setIsPasswordRequired] = useState(false);
  const [password, setPassword] = useState('');
  const [isVerifying, setIsVerifying] = useState(false);
  const [isUnlocked, setIsUnlocked] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);

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
      const msg = err instanceof Error ? err.message : 'ይህ አገናኝ አልተገኘም ወይም ጊዜው አልፏል (Link expired or invalid)';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token || !password) return;

    setIsVerifying(true);
    setPasswordError(null);

    try {
      await publicApi.verifyPassword(token, password);
      setIsUnlocked(true);
      setIsPasswordRequired(false);
    } catch {
      setPasswordError('የተሳሳተ የይለፍ ቃል ነው (Incorrect password. Please try again.)');
    } finally {
      setIsVerifying(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-zinc-50/50 flex flex-col items-center justify-center p-6 text-xs text-zinc-500">
        <Loader2 className="w-5 h-5 animate-spin text-zinc-700 mb-3" />
        <span>የሰነድ መረጃ እየተጫነ ነው...</span>
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
          <h2 className="text-base font-semibold text-zinc-900 mb-1">አገናኙ ሊከፈት አልቻለም</h2>
          <p className="text-xs text-zinc-500 mb-6">
            ይህ የሰነድ አገናኝ ጊዜው አልፏል፣ የወረደበት ገደብ አልቋል፣ ወይም በባለቤቱ ተሰርዟል።
          </p>
          <div className="pt-2 text-[11px] text-zinc-400 border-t border-zinc-100">
            EthioOffice Enterprise Secure Document Exchange
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-50/50 flex flex-col items-center justify-center p-4 md:p-6 font-sans select-none">
      {/* Brand Watermark */}
      <div className="mb-6 text-center">
        <h1 className="text-sm font-semibold tracking-tight text-zinc-900">
          EthioOffice
        </h1>
        <p className="text-[11px] text-zinc-400">ደህንነቱ የተጠበቀ የሰነድ ማጋሪያ (Secure Document Portal)</p>
      </div>

      <div className="w-full max-w-md bg-white border border-zinc-200/60 rounded-2xl p-6 md:p-8 shadow-xs">
        {isPasswordRequired && !isUnlocked ? (
          /* Password Prompt */
          <form onSubmit={handleVerifyPassword} className="space-y-4">
            <div className="w-10 h-10 rounded-full bg-zinc-100 flex items-center justify-center text-zinc-700 mx-auto mb-2">
              <Lock className="w-5 h-5" />
            </div>

            <div className="text-center space-y-1">
              <h2 className="text-sm font-semibold text-zinc-900">ይህ ሰነድ በይለፍ ቃል የተጠበቀ ነው</h2>
              <p className="text-xs text-zinc-500">
                ሰነዱን ለማየት ወይም ለማውረድ እባክዎ በላኪው የተሰጠውን የይለፍ ቃል ያስገቡ።
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
              isLoading={isVerifying}
              leftIcon={<ShieldCheck className="w-4 h-4" />}
            >
              ክፈት (Unlock File)
            </Button>
          </form>
        ) : (
          /* Document Metadata & Download Card */
          <div className="space-y-6">
            <div className="flex items-start gap-3.5">
              <div className="w-11 h-11 rounded-xl bg-zinc-100 flex items-center justify-center text-zinc-600 shrink-0">
                {metadata.is_folder ? (
                  <Folder className="w-6 h-6" />
                ) : (
                  <FileText className="w-6 h-6" />
                )}
              </div>

              <div className="min-w-0 flex-1">
                <h2 className="text-sm font-semibold text-zinc-900 truncate" title={metadata.file_name}>
                  {metadata.file_name}
                </h2>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="neutral" className="text-[10px]">
                    {metadata.access_type === 'ALLOW_DOWNLOAD' ? 'ማውረድ ይፈቀዳል' : 'ማየት ብቻ'}
                  </Badge>
                  <span className="text-xs text-zinc-400">
                    {formatFileSize(metadata.size_bytes)}
                  </span>
                </div>
              </div>
            </div>

            {/* Sharing Metadata Details */}
            <div className="p-3 bg-zinc-50/70 rounded-xl space-y-2 text-xs border border-zinc-100">
              <div className="flex items-center justify-between text-zinc-600">
                <span className="text-zinc-400">የተጋራበት ቀን (Date):</span>
                <span>{metadata.ec_created_at || new Date(metadata.created_at).toLocaleDateString()}</span>
              </div>

              {metadata.expires_at && (
                <div className="flex items-center justify-between text-zinc-600">
                  <span className="text-zinc-400 flex items-center gap-1">
                    <Clock className="w-3 h-3" /> የሚያበቃበት:
                  </span>
                  <span>{new Date(metadata.expires_at).toLocaleDateString()}</span>
                </div>
              )}
            </div>

            {/* Action Button */}
            {metadata.access_type === 'UPLOAD_DROPBOX' ? (
              <Link to={`/dropbox/${token}`} className="block">
                <Button variant="primary" size="md" className="w-full">
                  ወደ ድሮፕ ቦክስ ሂድ (Open Dropbox)
                </Button>
              </Link>
            ) : metadata.access_type === 'ALLOW_DOWNLOAD' ? (
              <a
                href={publicApi.getDownloadUrl(metadata.token, password || undefined)}
                download={metadata.file_name}
                className="block"
              >
                <Button
                  variant="primary"
                  size="md"
                  className="w-full"
                  leftIcon={<Download className="w-4 h-4" />}
                >
                  ሰነዱን አውርድ (Download File)
                </Button>
              </a>
            ) : (
              <div className="p-3 bg-zinc-50 text-center text-xs text-zinc-600 rounded-lg">
                ይህ ሰነድ ለማየት ብቻ የተፈቀደ ነው (View only permission)
              </div>
            )}
          </div>
        )}

        <div className="mt-8 pt-4 border-t border-zinc-100 flex items-center justify-between text-[11px] text-zinc-400">
          <span>EthioOffice Enterprise</span>
          <span>አዲስ አበባ, ኢትዮጵያ</span>
        </div>
      </div>
    </div>
  );
};
