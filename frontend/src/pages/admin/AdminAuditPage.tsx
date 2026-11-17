import React, { useState, useEffect } from 'react';
import {
  FileCheck,
  Download,
  RefreshCw,
} from 'lucide-react';
import { auditApi } from '../../api/client';
import type { AuditLogItem, AuditLedgerVerification } from '../../api/types';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';

export const AdminAuditPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [verification, setVerification] = useState<AuditLedgerVerification | null>(null);
  const [isVerifying, setIsVerifying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const data = await auditApi.listLogs({ limit: 50 });
      setLogs(data);
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyLedger = async () => {
    setIsVerifying(true);
    try {
      const res = await auditApi.verifyLedger();
      setVerification(res);
    } catch {
      // ignore
    } finally {
      setIsVerifying(false);
    }
  };

  useEffect(() => {
    loadData();
    handleVerifyLedger();
  }, []);

  const getActionBadge = (action: string) => {
    switch (action) {
      case 'LOGIN':
      case 'LOGOUT':
        return <Badge variant="info">{action}</Badge>;
      case 'UPLOAD':
      case 'LETTER_REGISTER':
        return <Badge variant="success">{action}</Badge>;
      case 'DELETE':
      case 'USER_LOCK':
        return <Badge variant="danger">{action}</Badge>;
      case 'SHARE':
      case 'LOCK':
        return <Badge variant="warning">{action}</Badge>;
      default:
        return <Badge variant="neutral">{action}</Badge>;
    }
  };

  return (
    <div className="space-y-6 select-none font-sans">
      {/* Top Header & Hash Verification Badge */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-zinc-100">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-lg font-semibold text-zinc-900 tracking-tight">
              የቁጥጥር መዝገብ (Cryptographic Audit Ledger)
            </h1>
            {verification?.is_valid ? (
              <Badge variant="success" dot>
                ያልተበረዘ መዝገብ (Verified Hash Chain)
              </Badge>
            ) : verification ? (
              <Badge variant="danger" dot>
                የተበረዘ መዝገብ (Integrity Alert)
              </Badge>
            ) : null}
          </div>
          <p className="text-xs text-zinc-500 mt-0.5">
            የኢትዮጵያ የህግ እና ኦዲት ደረጃዎችን ያሟላ የማይሻር (Immutable) የደህንነት መዝገብ
          </p>
        </div>

        {/* Verification & Export Buttons */}
        <div className="flex items-center gap-2">
          <Button
            variant="subtle"
            size="sm"
            leftIcon={<RefreshCw className={`w-3.5 h-3.5 ${isVerifying ? 'animate-spin' : ''}`} />}
            onClick={handleVerifyLedger}
            disabled={isVerifying}
          >
            ትክክለኛነቱን አረጋግጥ (Verify Integrity)
          </Button>

          <a
            href="/api/v1/audit/export/excel"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-zinc-900 text-white hover:bg-zinc-800 transition-colors shadow-2xs"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Excel ሪፖርት አውርድ</span>
          </a>
        </div>
      </div>

      {/* Ledger Metrics Summary Card */}
      {verification && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-4 bg-white rounded-2xl border border-zinc-200/60 shadow-xs">
          <div>
            <span className="text-[10px] uppercase font-semibold text-zinc-400 block tracking-wider">
              ጠቅላላ የተረጋገጡ ክንውኖች
            </span>
            <span className="text-lg font-semibold text-zinc-900 mt-0.5 block">
              {verification.total_records} ክንውኖች
            </span>
          </div>
          <div>
            <span className="text-[10px] uppercase font-semibold text-zinc-400 block tracking-wider">
              የመነሻ ብሎክ ሀሽ (Genesis Hash)
            </span>
            <span className="text-xs font-mono text-zinc-600 truncate mt-1 block">
              {verification.genesis_hash ? `${verification.genesis_hash.slice(0, 18)}...` : 'N/A'}
            </span>
          </div>
          <div>
            <span className="text-[10px] uppercase font-semibold text-zinc-400 block tracking-wider">
              የቅርብ ጊዜ ብሎክ ሀሽ (Latest Hash)
            </span>
            <span className="text-xs font-mono text-zinc-600 truncate mt-1 block">
              {verification.latest_hash ? `${verification.latest_hash.slice(0, 18)}...` : 'N/A'}
            </span>
          </div>
        </div>
      )}

      {/* Audit Log Table */}
      <div className="bg-white rounded-2xl shadow-xs border border-zinc-200/60 overflow-hidden">
        {isLoading ? (
          <div className="py-20 text-center text-xs text-zinc-400">የኦዲት መዝገብ እየተጫነ ነው...</div>
        ) : logs.length === 0 ? (
          <div className="py-20 text-center space-y-2">
            <FileCheck className="w-8 h-8 text-zinc-300 mx-auto" />
            <p className="text-sm font-medium text-zinc-900">ምንም የኦዲት መረጃ አልተገኘም</p>
          </div>
        ) : (
          <div className="divide-y divide-zinc-100">
            {logs.map((log) => (
              <div
                key={log.id}
                className="flex items-center justify-between p-4 hover:bg-zinc-50/70 transition-colors"
              >
                {/* Left: Action badge, Target entity, User */}
                <div className="min-w-0 flex-1 pr-4">
                  <div className="flex items-center gap-2 mb-1">
                    {getActionBadge(log.action)}
                    <span className="text-xs font-medium text-zinc-900 truncate">
                      {log.target_name || log.target_type}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-zinc-400">
                    <span>ፈጻሚ፦ {log.user_name || 'System'}</span>
                    <span>•</span>
                    <span>IP፦ {log.client_ip || 'Internal'}</span>
                    {log.entry_hash && (
                      <>
                        <span>•</span>
                        <span className="font-mono text-[10px] text-zinc-400" title={log.entry_hash}>
                          Hash: {log.entry_hash.slice(0, 12)}...
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {/* Right: Date */}
                <div className="text-right text-xs shrink-0">
                  <span className="font-medium text-zinc-800 block">
                    {log.ec_created_at || new Date(log.created_at).toLocaleDateString()}
                  </span>
                  <span className="text-[10px] text-zinc-400 block mt-0.5">
                    {new Date(log.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
