import React, { useState, useEffect, useRef } from 'react';
import {
  Mail,
  Plus,
  Search,
  Clock,
  FileText,
  Paperclip,
  ChevronRight,
  Send,
  AlertTriangle,
  RotateCcw,
  ArrowDownLeft,
  ArrowUpRight,
  Building2,
  CheckCircle2,
  Download,
  ExternalLink,
  ShieldAlert,
  ShieldCheck,
  Check,
  Upload,
  CornerUpRight,
  ArrowRight,
} from 'lucide-react';
import { lettersApi, departmentsApi, filesApi } from '../../api/client';
import type {
  LetterRecord,
  LetterDetail,
  LetterAnalyticsSummary,
  DepartmentItem,
} from '../../api/types';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Modal } from '../../components/ui/Modal';
import { Badge } from '../../components/ui/Badge';
import { Tabs } from '../../components/ui/Tabs';

export const LettersPage: React.FC = () => {
  const [letters, setLetters] = useState<LetterRecord[]>([]);
  const [summary, setSummary] = useState<LetterAnalyticsSummary | null>(null);
  const [departments, setDepartments] = useState<DepartmentItem[]>([]);

  // Filtering states
  const [directionTab, setDirectionTab] = useState<'ALL' | 'INWARD' | 'OUTWARD' | 'INTERNAL_MEMO'>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [urgencyFilter, setUrgencyFilter] = useState<string>('ALL');
  const [departmentFilter, setDepartmentFilter] = useState<string>('ALL');
  const [isOverdueOnly, setIsOverdueOnly] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Detail Modal
  const [selectedLetter, setSelectedLetter] = useState<LetterDetail | null>(null);

  // Register Letter Modal
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newLetter, setNewLetter] = useState({
    direction: 'INWARD' as 'INWARD' | 'OUTWARD' | 'INTERNAL_MEMO',
    department_id: '',
    subject: '',
    sender_entity: '',
    sender_contact: '',
    recipient_entity: '',
    recipient_contact: '',
    reference_number: '',
    external_reference_number: '',
    urgency: 'NORMAL',
    confidentiality: 'NORMAL',
    notes: '',
  });

  // Action states
  const [rejectionReason, setRejectionReason] = useState('');
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [showDispatchModal, setShowDispatchModal] = useState(false);
  const [dispatchData, setDispatchData] = useState({
    delivery_method: 'HAND_DELIVERY',
    dispatched_date_gc: '',
  });
  const [showRouteModal, setShowRouteModal] = useState(false);
  const [routeData, setRouteData] = useState({
    to_department_id: '',
    action_required: 'FOR_ACTION',
    priority: 'NORMAL',
    instructions: '',
  });
  const [showCompleteModal, setShowCompleteModal] = useState(false);
  const [completingRoutingId, setCompletingRoutingId] = useState<string | null>(null);
  const [completeResponseNotes, setCompleteResponseNotes] = useState('');
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [isUploadingAttachment, setIsUploadingAttachment] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const loadSummaryAndDepts = async () => {
    try {
      const [sum, depts] = await Promise.all([
        lettersApi.getAnalyticsSummary(),
        departmentsApi.list().catch(() => []),
      ]);
      setSummary(sum);
      setDepartments(depts);
    } catch {
      // ignore
    }
  };

  const loadLetters = async () => {
    setIsLoading(true);
    try {
      const direction = directionTab === 'ALL' ? undefined : directionTab;
      const status = statusFilter === 'ALL' ? undefined : statusFilter;
      const urgency = urgencyFilter === 'ALL' ? undefined : urgencyFilter;
      const department_id = departmentFilter === 'ALL' ? undefined : departmentFilter;
      const is_overdue = isOverdueOnly ? true : undefined;

      const data = await lettersApi.list({
        direction,
        status,
        urgency,
        department_id,
        is_overdue,
        search: searchQuery.trim() || undefined,
      });
      setLetters(data);
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadSummaryAndDepts();
  }, []);

  useEffect(() => {
    loadLetters();
  }, [directionTab, statusFilter, urgencyFilter, departmentFilter, isOverdueOnly, searchQuery]);

  const handleResetFilters = () => {
    setDirectionTab('ALL');
    setStatusFilter('ALL');
    setUrgencyFilter('ALL');
    setDepartmentFilter('ALL');
    setIsOverdueOnly(false);
    setSearchQuery('');
  };

  const isFiltered =
    directionTab !== 'ALL' ||
    statusFilter !== 'ALL' ||
    urgencyFilter !== 'ALL' ||
    departmentFilter !== 'ALL' ||
    isOverdueOnly ||
    searchQuery.trim().length > 0;

  const handleOpenDetail = async (id: string) => {
    try {
      const detail = await lettersApi.getDetail(id);
      setSelectedLetter(detail);
    } catch {
      // ignore
    }
  };

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLetter.subject.trim() || !newLetter.sender_entity.trim() || !newLetter.recipient_entity.trim()) {
      return;
    }

    try {
      await lettersApi.create({
        direction: newLetter.direction,
        department_id: newLetter.department_id || undefined,
        subject: newLetter.subject.trim(),
        sender_entity: newLetter.sender_entity.trim(),
        sender_contact: newLetter.sender_contact.trim() || undefined,
        recipient_entity: newLetter.recipient_entity.trim(),
        recipient_contact: newLetter.recipient_contact.trim() || undefined,
        reference_number: newLetter.reference_number.trim() || undefined,
        external_reference_number: newLetter.external_reference_number.trim() || undefined,
        urgency: newLetter.urgency,
        confidentiality: newLetter.confidentiality,
        notes: newLetter.notes.trim() || undefined,
      });

      setShowCreateModal(false);
      setNewLetter({
        direction: 'INWARD',
        department_id: '',
        subject: '',
        sender_entity: '',
        sender_contact: '',
        recipient_entity: '',
        recipient_contact: '',
        reference_number: '',
        external_reference_number: '',
        urgency: 'NORMAL',
        confidentiality: 'NORMAL',
        notes: '',
      });
      loadLetters();
      loadSummaryAndDepts();
    } catch {
      // ignore
    }
  };

  const handleSubmitForApproval = async () => {
    if (!selectedLetter) return;
    setIsActionLoading(true);
    try {
      await lettersApi.submit(selectedLetter.id);
      const updated = await lettersApi.getDetail(selectedLetter.id);
      setSelectedLetter(updated);
      loadLetters();
      loadSummaryAndDepts();
    } catch {
      // ignore
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!selectedLetter) return;
    setIsActionLoading(true);
    try {
      await lettersApi.approve(selectedLetter.id);
      const updated = await lettersApi.getDetail(selectedLetter.id);
      setSelectedLetter(updated);
      loadLetters();
      loadSummaryAndDepts();
    } catch {
      // ignore
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (!selectedLetter || !rejectionReason.trim()) return;
    setIsActionLoading(true);
    try {
      await lettersApi.reject(selectedLetter.id, rejectionReason.trim());
      const updated = await lettersApi.getDetail(selectedLetter.id);
      setSelectedLetter(updated);
      setShowRejectModal(false);
      setRejectionReason('');
      loadLetters();
      loadSummaryAndDepts();
    } catch {
      // ignore
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleDispatchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLetter) return;
    setIsActionLoading(true);
    try {
      await lettersApi.dispatch(selectedLetter.id, {
        delivery_method: dispatchData.delivery_method,
        dispatched_date_gc: dispatchData.dispatched_date_gc || undefined,
      });
      const updated = await lettersApi.getDetail(selectedLetter.id);
      setSelectedLetter(updated);
      setShowDispatchModal(false);
      loadLetters();
      loadSummaryAndDepts();
    } catch {
      // ignore
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleArchive = async () => {
    if (!selectedLetter) return;
    setIsActionLoading(true);
    try {
      await lettersApi.archive(selectedLetter.id);
      const updated = await lettersApi.getDetail(selectedLetter.id);
      setSelectedLetter(updated);
      loadLetters();
      loadSummaryAndDepts();
    } catch {
      // ignore
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleRouteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLetter || !routeData.to_department_id) return;
    setIsActionLoading(true);
    try {
      await lettersApi.route(selectedLetter.id, {
        to_department_id: routeData.to_department_id,
        action_required: routeData.action_required,
        priority: routeData.priority,
        instructions: routeData.instructions.trim() || undefined,
      });
      const updated = await lettersApi.getDetail(selectedLetter.id);
      setSelectedLetter(updated);
      setShowRouteModal(false);
      setRouteData({
        to_department_id: '',
        action_required: 'FOR_ACTION',
        priority: 'NORMAL',
        instructions: '',
      });
      loadLetters();
      loadSummaryAndDepts();
    } catch {
      // ignore
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleAcknowledgeRouting = async (routingId: string) => {
    if (!selectedLetter) return;
    try {
      await lettersApi.acknowledgeRouting(routingId);
      const updated = await lettersApi.getDetail(selectedLetter.id);
      setSelectedLetter(updated);
      loadLetters();
    } catch {
      // ignore
    }
  };

  const handleCompleteRoutingSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedLetter || !completingRoutingId || !completeResponseNotes.trim()) return;
    try {
      await lettersApi.completeRouting(completingRoutingId, {
        response_notes: completeResponseNotes.trim(),
      });
      const updated = await lettersApi.getDetail(selectedLetter.id);
      setSelectedLetter(updated);
      setShowCompleteModal(false);
      setCompletingRoutingId(null);
      setCompleteResponseNotes('');
      loadLetters();
    } catch {
      // ignore
    }
  };

  const handleDownloadAttachment = async (fileId: string, fileName: string) => {
    try {
      await filesApi.downloadFile(fileId, fileName);
    } catch {
      // ignore
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !selectedLetter) return;
    setIsUploadingAttachment(true);
    try {
      const uploaded = await filesApi.upload(file, 'COMPANY');
      await lettersApi.attachFile(selectedLetter.id, uploaded.id, 'SUPPORTING_DOCUMENT');
      const updated = await lettersApi.getDetail(selectedLetter.id);
      setSelectedLetter(updated);
      loadLetters();
    } catch {
      // ignore
    } finally {
      setIsUploadingAttachment(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const formatBytes = (bytes: number): string => {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  const isOfficeDoc = (filename: string): boolean => {
    const ext = filename.split('.').pop()?.toLowerCase();
    return ext === 'docx' || ext === 'xlsx' || ext === 'pptx';
  };

  const tabs = [
    { id: 'ALL', label: 'All Letters' },
    { id: 'INWARD', label: 'Inward' },
    { id: 'OUTWARD', label: 'Outward' },
    { id: 'INTERNAL_MEMO', label: 'Internal Memos' },
  ];

  const getDirectionBadge = (direction: string) => {
    switch (direction) {
      case 'INWARD':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
            <ArrowDownLeft className="w-3.5 h-3.5 text-slate-500" />
            Inward
          </span>
        );
      case 'OUTWARD':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
            <ArrowUpRight className="w-3.5 h-3.5 text-slate-500" />
            Outward
          </span>
        );
      case 'INTERNAL_MEMO':
        return (
          <span className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-700 bg-slate-100 px-2 py-0.5 rounded">
            <FileText className="w-3.5 h-3.5 text-slate-500" />
            Memo
          </span>
        );
      default:
        return null;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'APPROVED':
        return <Badge variant="success" dot>Approved</Badge>;
      case 'PENDING_APPROVAL':
        return <Badge variant="warning" dot>Pending Approval</Badge>;
      case 'DISPATCHED':
        return <Badge variant="info" dot>Dispatched</Badge>;
      case 'RECEIVED':
        return <Badge variant="default" dot>Received</Badge>;
      case 'ARCHIVED':
        return <Badge variant="neutral">Archived</Badge>;
      case 'REJECTED':
        return <Badge variant="danger" dot>Rejected</Badge>;
      default:
        return <Badge variant="neutral">Draft</Badge>;
    }
  };

  const getConfidentialityBadge = (level: string) => {
    switch (level) {
      case 'STRICTLY_CONFIDENTIAL':
        return (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200/60">
            <ShieldAlert className="w-3.5 h-3.5 text-rose-600" />
            Strictly Confidential
          </span>
        );
      case 'CONFIDENTIAL':
        return (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200/60">
            <ShieldCheck className="w-3.5 h-3.5 text-amber-600" />
            Confidential
          </span>
        );
      default:
        return null;
    }
  };

  const getDeliveryMethodLabel = (method?: string): string => {
    switch (method) {
      case 'HAND_DELIVERY':
        return 'Hand Delivery';
      case 'POSTAL':
        return 'Postal Mail';
      case 'COURIER':
        return 'Courier Service';
      case 'ELECTRONIC_EMAIL':
        return 'Official Email';
      case 'INTERNAL_DISPATCH':
        return 'Internal Dispatch';
      default:
        return method || 'Standard';
    }
  };

  const getRoutingActionLabel = (action: string): string => {
    switch (action) {
      case 'FOR_ACTION':
        return 'For Action';
      case 'FOR_INFORMATION':
        return 'For Information';
      case 'FOR_APPROVAL':
        return 'For Approval';
      case 'FOR_COMMENT':
        return 'For Comment';
      case 'FOR_FILING':
        return 'For Filing';
      default:
        return action;
    }
  };

  return (
    <div className="space-y-6 select-none font-sans">
      {/* Header & New Letter Button */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200">
        <div>
          <h1 className="text-lg font-semibold text-slate-900 tracking-tight">
            Official Letter Registry
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Institutional correspondence registry, approvals, and chain of custody
          </p>
        </div>

        <Button
          variant="primary"
          size="sm"
          leftIcon={<Plus className="w-4 h-4" />}
          onClick={() => setShowCreateModal(true)}
        >
          Register Letter
        </Button>
      </div>

      {/* KPI Ribbon */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        {/* Total Letters */}
        <div
          onClick={() => {
            setDirectionTab('ALL');
            setStatusFilter('ALL');
            setIsOverdueOnly(false);
          }}
          className={`p-4 rounded-xl border transition-all cursor-pointer bg-white ${
            directionTab === 'ALL' && statusFilter === 'ALL' && !isOverdueOnly
              ? 'border-slate-400 shadow-xs'
              : 'border-slate-200 hover:border-slate-300 shadow-2xs'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Total Letters</span>
            <div className="w-8 h-8 rounded-lg bg-slate-100 text-slate-600 flex items-center justify-center">
              <Mail className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-slate-900 tracking-tight mt-1.5">
            {summary?.total_letters ?? 0}
          </div>
          <p className="text-xs text-slate-400 mt-1 truncate">
            Inward: {summary?.inward_count ?? 0} • Outward: {summary?.outward_count ?? 0} • Memos: {summary?.memo_count ?? 0}
          </p>
        </div>

        {/* Pending Approvals */}
        <div
          onClick={() => {
            setStatusFilter(statusFilter === 'PENDING_APPROVAL' ? 'ALL' : 'PENDING_APPROVAL');
            setIsOverdueOnly(false);
          }}
          className={`p-4 rounded-xl border transition-all cursor-pointer bg-white ${
            statusFilter === 'PENDING_APPROVAL'
              ? 'border-slate-400 shadow-xs'
              : 'border-slate-200 hover:border-slate-300 shadow-2xs'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Pending Approvals</span>
            <div className="w-8 h-8 rounded-lg bg-slate-100 text-slate-600 flex items-center justify-center">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-slate-900 tracking-tight mt-1.5">
            {summary?.pending_approval_count ?? 0}
          </div>
          <p className="text-xs text-slate-400 mt-1 truncate">
            {summary?.urgent_open_count ?? 0} urgent reviews pending
          </p>
        </div>

        {/* Dispatched */}
        <div
          onClick={() => {
            setStatusFilter(statusFilter === 'DISPATCHED' ? 'ALL' : 'DISPATCHED');
            setIsOverdueOnly(false);
          }}
          className={`p-4 rounded-xl border transition-all cursor-pointer bg-white ${
            statusFilter === 'DISPATCHED'
              ? 'border-slate-400 shadow-xs'
              : 'border-slate-200 hover:border-slate-300 shadow-2xs'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Dispatched Letters</span>
            <div className="w-8 h-8 rounded-lg bg-slate-100 text-slate-600 flex items-center justify-center">
              <Send className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-slate-900 tracking-tight mt-1.5">
            {summary?.dispatched_count ?? 0}
          </div>
          <p className="text-xs text-slate-400 mt-1 truncate">
            Received: {summary?.received_count ?? 0} • Archived: {summary?.archived_count ?? 0}
          </p>
        </div>

        {/* Overdue SLA */}
        <div
          onClick={() => {
            setIsOverdueOnly(!isOverdueOnly);
            if (!isOverdueOnly) setStatusFilter('ALL');
          }}
          className={`p-4 rounded-xl border transition-all cursor-pointer bg-white ${
            isOverdueOnly
              ? 'border-rose-400 shadow-xs'
              : 'border-slate-200 hover:border-slate-300 shadow-2xs'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-500">Overdue SLA</span>
            <div className="w-8 h-8 rounded-lg bg-slate-100 text-slate-600 flex items-center justify-center">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div
            className={`text-2xl font-bold tracking-tight mt-1.5 ${
              (summary?.overdue_sla_count ?? 0) > 0 ? 'text-rose-600' : 'text-slate-900'
            }`}
          >
            {summary?.overdue_sla_count ?? 0}
          </div>
          <p className="text-xs text-slate-400 mt-1 truncate">
            Working-day SLA deadline exceeded
          </p>
        </div>
      </div>

      {/* Primary Direction Tabs & Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <Tabs
          items={tabs}
          activeId={directionTab}
          onChange={(id) => setDirectionTab(id as any)}
        />

        <div className="w-full sm:w-80">
          <Input
            placeholder="Search reference, subject, sender, or recipient..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            leftIcon={<Search className="w-4 h-4 text-slate-400" />}
          />
        </div>
      </div>

      {/* Secondary Filter Dropdowns & Controls */}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        {/* Status Filter */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Filter by letter status"
          className="text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:border-slate-400"
        >
          <option value="ALL">All Statuses</option>
          <option value="DRAFT">Draft</option>
          <option value="PENDING_APPROVAL">Pending Approval</option>
          <option value="APPROVED">Approved</option>
          <option value="DISPATCHED">Dispatched</option>
          <option value="RECEIVED">Received</option>
          <option value="REJECTED">Rejected</option>
          <option value="ARCHIVED">Archived</option>
        </select>

        {/* Urgency Filter */}
        <select
          value={urgencyFilter}
          onChange={(e) => setUrgencyFilter(e.target.value)}
          aria-label="Filter by letter urgency"
          className="text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:border-slate-400"
        >
          <option value="ALL">All Urgencies</option>
          <option value="NORMAL">Normal (5 Days SLA)</option>
          <option value="URGENT">Urgent (3 Days SLA)</option>
          <option value="VERY_URGENT">Very Urgent (24h SLA)</option>
        </select>

        {/* Department Filter */}
        {departments.length > 0 && (
          <select
            value={departmentFilter}
            onChange={(e) => setDepartmentFilter(e.target.value)}
            aria-label="Filter by department"
            className="text-xs font-medium text-slate-700 bg-white border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none focus:border-slate-400"
          >
            <option value="ALL">All Departments</option>
            {departments.map((dept) => (
              <option key={dept.id} value={dept.id}>
                {dept.name} ({dept.code})
              </option>
            ))}
          </select>
        )}

        {/* Overdue Toggle */}
        <button
          type="button"
          onClick={() => setIsOverdueOnly(!isOverdueOnly)}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
            isOverdueOnly
              ? 'bg-rose-50 text-rose-700 border border-rose-200 font-semibold'
              : 'bg-white text-slate-600 border border-slate-200 hover:bg-slate-50'
          }`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              isOverdueOnly ? 'bg-rose-600' : 'bg-slate-400'
            }`}
          />
          Overdue Only
        </button>

        {/* Reset Filters */}
        {isFiltered && (
          <button
            type="button"
            onClick={handleResetFilters}
            className="px-2.5 py-1.5 text-xs font-medium rounded-lg text-slate-500 hover:text-slate-800 hover:bg-slate-100 transition-colors flex items-center gap-1"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset Filters
          </button>
        )}
      </div>

      {/* Letters List Table */}
      <div className="bg-white rounded-xl shadow-2xs border border-slate-200 overflow-hidden">
        {isLoading ? (
          <div className="py-20 text-center text-xs text-slate-400">Loading correspondence...</div>
        ) : letters.length === 0 ? (
          <div className="py-20 text-center space-y-2">
            <Mail className="w-8 h-8 text-slate-300 mx-auto" />
            <p className="text-sm font-medium text-slate-900">No letters found</p>
            <p className="text-xs text-slate-400">Register a new letter to start tracking correspondence.</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {letters.map((letter) => (
              <div
                key={letter.id}
                onClick={() => handleOpenDetail(letter.id)}
                className="flex items-center justify-between p-4 hover:bg-slate-50/70 transition-colors cursor-pointer group"
              >
                {/* Left: Reference, Badges, Subject, Sender & Recipient */}
                <div className="min-w-0 flex-1 pr-4">
                  <div className="flex flex-wrap items-center gap-2 mb-1.5">
                    <span className="font-mono text-xs font-semibold text-slate-800 bg-slate-100 px-2 py-0.5 rounded">
                      {letter.reference_number}
                    </span>
                    {getDirectionBadge(letter.direction)}
                    {getStatusBadge(letter.status)}
                    {getConfidentialityBadge(letter.confidentiality)}
                    {letter.urgency === 'VERY_URGENT' && (
                      <Badge variant="danger" dot>Very Urgent</Badge>
                    )}
                    {letter.department_name && (
                      <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-500 bg-slate-100 px-2 py-0.5 rounded">
                        <Building2 className="w-3.5 h-3.5 text-slate-400" />
                        {letter.department_name}
                      </span>
                    )}
                  </div>
                  <h4 className="text-sm font-medium text-slate-900 truncate group-hover:text-slate-950">
                    {letter.subject}
                  </h4>
                  <div className="flex items-center gap-3 mt-1.5 text-xs text-slate-500">
                    <span>From: {letter.sender_entity}</span>
                    <span>•</span>
                    <span>To: {letter.recipient_entity}</span>
                    {letter.attachment_file_id && (
                      <>
                        <span>•</span>
                        <span className="inline-flex items-center gap-1 text-slate-500">
                          <Paperclip className="w-3.5 h-3.5" />
                          Attached Document
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {/* Right: Date, Due SLA, Chevron */}
                <div className="flex items-center gap-4 shrink-0 text-right">
                  <div>
                    <span className="text-xs font-medium text-slate-800 block">
                      {letter.date_gc}
                    </span>
                    {letter.days_remaining !== undefined && letter.days_remaining !== null && (
                      <span
                        className={`text-xs ${
                          letter.is_overdue ? 'text-rose-600 font-semibold' : 'text-slate-400'
                        }`}
                      >
                        {letter.is_overdue ? 'Overdue' : `${letter.days_remaining} days left`}
                      </span>
                    )}
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-300 group-hover:text-slate-600 transition-colors" />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 1. Register Letter Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Register Official Letter"
        maxWidth="xl"
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4">
          <div className="grid grid-cols-3 gap-2 p-1 bg-slate-100 rounded-lg text-xs font-medium">
            <button
              type="button"
              onClick={() => setNewLetter({ ...newLetter, direction: 'INWARD' })}
              className={`py-1.5 rounded-md transition-colors flex items-center justify-center gap-1.5 ${
                newLetter.direction === 'INWARD'
                  ? 'bg-white text-slate-900 shadow-2xs font-semibold'
                  : 'text-slate-600'
              }`}
            >
              <ArrowDownLeft className="w-3.5 h-3.5 text-slate-500" />
              Inward Letter
            </button>
            <button
              type="button"
              onClick={() => setNewLetter({ ...newLetter, direction: 'OUTWARD' })}
              className={`py-1.5 rounded-md transition-colors flex items-center justify-center gap-1.5 ${
                newLetter.direction === 'OUTWARD'
                  ? 'bg-white text-slate-900 shadow-2xs font-semibold'
                  : 'text-slate-600'
              }`}
            >
              <ArrowUpRight className="w-3.5 h-3.5 text-slate-500" />
              Outward Letter
            </button>
            <button
              type="button"
              onClick={() => setNewLetter({ ...newLetter, direction: 'INTERNAL_MEMO' })}
              className={`py-1.5 rounded-md transition-colors flex items-center justify-center gap-1.5 ${
                newLetter.direction === 'INTERNAL_MEMO'
                  ? 'bg-white text-slate-900 shadow-2xs font-semibold'
                  : 'text-slate-600'
              }`}
            >
              <FileText className="w-3.5 h-3.5 text-slate-500" />
              Internal Memo
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="sm:col-span-2">
              <Input
                label="Subject / Purpose"
                placeholder="e.g. Annual Financial Audit Report 2026"
                value={newLetter.subject}
                onChange={(e) => setNewLetter({ ...newLetter, subject: e.target.value })}
                required
                autoFocus
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">
                Department
              </label>
              <select
                value={newLetter.department_id}
                onChange={(e) => setNewLetter({ ...newLetter, department_id: e.target.value })}
                className="w-full rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none"
              >
                <option value="">General Registry (Organization Wide)</option>
                {departments.map((dept) => (
                  <option key={dept.id} value={dept.id}>
                    {dept.name} ({dept.code})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div className="space-y-2">
              <Input
                label="Sender Entity"
                placeholder="e.g. Ministry of Finance or Partner Corp"
                value={newLetter.sender_entity}
                onChange={(e) => setNewLetter({ ...newLetter, sender_entity: e.target.value })}
                required
              />
              <Input
                label="Sender Contact (Optional)"
                placeholder="Phone or email"
                value={newLetter.sender_contact}
                onChange={(e) => setNewLetter({ ...newLetter, sender_contact: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Input
                label="Recipient Entity"
                placeholder="e.g. Chief Executive Officer or HR Dept"
                value={newLetter.recipient_entity}
                onChange={(e) => setNewLetter({ ...newLetter, recipient_entity: e.target.value })}
                required
              />
              <Input
                label="Recipient Contact (Optional)"
                placeholder="Phone or email"
                value={newLetter.recipient_contact}
                onChange={(e) => setNewLetter({ ...newLetter, recipient_contact: e.target.value })}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">
                Urgency SLA
              </label>
              <select
                value={newLetter.urgency}
                onChange={(e) => setNewLetter({ ...newLetter, urgency: e.target.value })}
                className="w-full rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none"
              >
                <option value="NORMAL">Normal - 5 Working Days</option>
                <option value="URGENT">Urgent - 3 Working Days</option>
                <option value="VERY_URGENT">Very Urgent - 24 Hours</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">
                Confidentiality Level
              </label>
              <select
                value={newLetter.confidentiality}
                onChange={(e) => setNewLetter({ ...newLetter, confidentiality: e.target.value })}
                className="w-full rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none"
              >
                <option value="NORMAL">Standard / Unclassified</option>
                <option value="CONFIDENTIAL">Confidential</option>
                <option value="STRICTLY_CONFIDENTIAL">Strictly Confidential</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input
              label="Reference Number (Auto-generated if empty)"
              placeholder="e.g. EO/FIN/2026/0042"
              value={newLetter.reference_number}
              onChange={(e) => setNewLetter({ ...newLetter, reference_number: e.target.value })}
            />

            {newLetter.direction === 'INWARD' ? (
              <Input
                label="External Reference Number (Sender's Ref)"
                placeholder="e.g. MOF/04-2026"
                value={newLetter.external_reference_number}
                onChange={(e) =>
                  setNewLetter({ ...newLetter, external_reference_number: e.target.value })
                }
              />
            ) : (
              <Input
                label="Notes / Description"
                placeholder="Additional instructions or notes..."
                value={newLetter.notes}
                onChange={(e) => setNewLetter({ ...newLetter, notes: e.target.value })}
              />
            )}
          </div>

          {newLetter.direction === 'INWARD' && (
            <Input
              label="Notes / Description"
              placeholder="Additional instructions or notes..."
              value={newLetter.notes}
              onChange={(e) => setNewLetter({ ...newLetter, notes: e.target.value })}
            />
          )}

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
            <Button variant="ghost" type="button" onClick={() => setShowCreateModal(false)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit">
              Register Letter
            </Button>
          </div>
        </form>
      </Modal>

      {/* 2. Letter Detail & Workflow Drawer Modal */}
      {selectedLetter && (
        <Modal
          isOpen={!!selectedLetter}
          onClose={() => setSelectedLetter(null)}
          title={selectedLetter.reference_number}
          description={selectedLetter.subject}
          maxWidth="2xl"
        >
          <div className="space-y-5">
            {/* Badges Strip */}
            <div className="flex flex-wrap items-center gap-2 pb-1 border-b border-slate-100">
              {getDirectionBadge(selectedLetter.direction)}
              {getStatusBadge(selectedLetter.status)}
              {getConfidentialityBadge(selectedLetter.confidentiality)}
              {selectedLetter.urgency === 'VERY_URGENT' && (
                <Badge variant="danger" dot>Very Urgent</Badge>
              )}
              {selectedLetter.external_reference_number && (
                <span className="font-mono text-xs text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                  Sender Ref: {selectedLetter.external_reference_number}
                </span>
              )}
            </div>

            {/* Top Metadata Strip */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 p-3 bg-slate-50 rounded-xl text-xs border border-slate-200">
              <div>
                <span className="text-slate-400 block text-xs">Status</span>
                <span className="font-medium text-slate-900 mt-0.5 block">
                  {getStatusBadge(selectedLetter.status)}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-xs">Registered Date</span>
                <span className="font-medium text-slate-900 mt-0.5 block">{selectedLetter.date_gc}</span>
                <span className="text-xs text-slate-400 block">{selectedLetter.date_ec}</span>
              </div>
              <div>
                <span className="text-slate-400 block text-xs">Department</span>
                <span className="font-medium text-slate-900 mt-0.5 block">
                  {selectedLetter.department_name || 'General Registry'}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block text-xs">SLA Due Date</span>
                <span
                  className={`font-medium mt-0.5 block ${
                    selectedLetter.is_overdue ? 'text-rose-600 font-semibold' : 'text-slate-900'
                  }`}
                >
                  {selectedLetter.is_overdue
                    ? 'Overdue'
                    : selectedLetter.days_remaining !== undefined && selectedLetter.days_remaining !== null
                    ? `${selectedLetter.days_remaining} days left`
                    : 'Within SLA'}
                </span>
                {selectedLetter.due_date_gc && (
                  <span className="text-xs text-slate-400 block">Due: {selectedLetter.due_date_gc}</span>
                )}
              </div>
            </div>

            {/* Sender & Recipient Entities */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-3.5 rounded-xl border border-slate-200 bg-white text-xs">
              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Sender Entity
                </span>
                <div className="font-medium text-slate-900 text-sm">{selectedLetter.sender_entity}</div>
                {selectedLetter.sender_contact && (
                  <div className="text-xs text-slate-500">Contact: {selectedLetter.sender_contact}</div>
                )}
              </div>
              <div className="space-y-1">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                  Recipient Entity
                </span>
                <div className="font-medium text-slate-900 text-sm">{selectedLetter.recipient_entity}</div>
                {selectedLetter.recipient_contact && (
                  <div className="text-xs text-slate-500">Contact: {selectedLetter.recipient_contact}</div>
                )}
              </div>
            </div>

            {/* Reviewer Feedback if Rejected */}
            {selectedLetter.status === 'REJECTED' && selectedLetter.rejection_reason && (
              <div className="p-3.5 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-900">
                <div className="font-semibold text-rose-800 flex items-center gap-1.5 mb-1">
                  <ShieldAlert className="w-4 h-4 text-rose-600" />
                  Reviewer Feedback / Reason for Rejection
                </div>
                <p className="text-rose-700 italic">"{selectedLetter.rejection_reason}"</p>
              </div>
            )}

            {/* Dispatched Info Banner if Dispatched */}
            {selectedLetter.status === 'DISPATCHED' && (
              <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Send className="w-4 h-4 text-slate-600" />
                  <div>
                    <span className="font-semibold block">Officially Dispatched</span>
                    <span className="text-slate-600 text-xs">
                      Delivery Method: {getDeliveryMethodLabel(selectedLetter.delivery_method)}
                    </span>
                  </div>
                </div>
                {selectedLetter.dispatched_at_gc && (
                  <span className="font-medium text-slate-700 text-xs">
                    {selectedLetter.dispatched_at_gc}
                  </span>
                )}
              </div>
            )}

            {/* Notes */}
            {selectedLetter.notes && (
              <div className="p-3 bg-slate-50 rounded-xl text-xs">
                <span className="text-slate-400 block text-xs mb-0.5">Notes</span>
                <span className="text-slate-700">{selectedLetter.notes}</span>
              </div>
            )}

            {/* Attached Documents */}
            <div className="rounded-xl border border-slate-200 p-3.5 bg-white space-y-3">
              <div className="flex items-center justify-between">
                <h5 className="text-xs font-semibold text-slate-900 flex items-center gap-1.5">
                  <Paperclip className="w-4 h-4 text-slate-400" />
                  <span>Attached Documents</span>
                  <span className="text-slate-400 font-normal">
                    ({selectedLetter.attachments?.length || 0})
                  </span>
                </h5>

                <div>
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileUpload}
                    className="hidden"
                  />
                  <Button
                    variant="ghost"
                    size="sm"
                    leftIcon={<Upload className="w-3.5 h-3.5 text-slate-500" />}
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isUploadingAttachment}
                  >
                    {isUploadingAttachment ? 'Uploading...' : 'Attach File'}
                  </Button>
                </div>
              </div>

              {selectedLetter.attachments && selectedLetter.attachments.length > 0 ? (
                <div className="divide-y divide-slate-100 rounded-lg border border-slate-100 overflow-hidden">
                  {selectedLetter.attachments.map((att) => (
                    <div
                      key={att.id}
                      className="p-2.5 flex items-center justify-between hover:bg-slate-50 transition-colors text-xs"
                    >
                      <div className="flex items-center gap-2.5 min-w-0">
                        <div className="w-7 h-7 rounded-lg bg-slate-100 text-slate-600 flex items-center justify-center shrink-0">
                          <FileText className="w-3.5 h-3.5" />
                        </div>
                        <div className="min-w-0">
                          <span className="font-medium text-slate-900 truncate block">
                            {att.file_name}
                          </span>
                          <span className="text-xs text-slate-400">
                            {formatBytes(att.size_bytes)} • {att.attachment_type}
                          </span>
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        {isOfficeDoc(att.file_name) && (
                          <a
                            href={`/editor?fileId=${att.file_id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 transition-colors"
                          >
                            <ExternalLink className="w-3 h-3" />
                            Open in Euro-Office
                          </a>
                        )}
                        <button
                          type="button"
                          onClick={() => handleDownloadAttachment(att.file_id, att.file_name)}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 transition-colors"
                        >
                          <Download className="w-3 h-3 text-slate-500" />
                          Download
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 italic py-2 text-center">No documents attached.</p>
              )}
            </div>

            {/* Chain of Custody Routing Trail */}
            <div className="rounded-xl border border-slate-200 p-3.5 bg-white space-y-3">
              <div className="flex items-center justify-between">
                <h5 className="text-xs font-semibold text-slate-900 flex items-center gap-1.5">
                  <Clock className="w-4 h-4 text-slate-400" />
                  <span>Chain of Custody & Department Routing</span>
                  <span className="text-slate-400 font-normal">
                    ({selectedLetter.routings?.length || 0})
                  </span>
                </h5>

                <Button
                  variant="ghost"
                  size="sm"
                  leftIcon={<CornerUpRight className="w-3.5 h-3.5 text-slate-500" />}
                  onClick={() => setShowRouteModal(true)}
                >
                  Route Letter
                </Button>
              </div>

              {selectedLetter.routings && selectedLetter.routings.length > 0 ? (
                <div className="space-y-2.5">
                  {selectedLetter.routings.map((r) => (
                    <div
                      key={r.id}
                      className="p-3 bg-slate-50 rounded-xl text-xs space-y-2 border border-slate-200/60"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5 text-slate-600">
                          <span className="font-medium text-slate-800">
                            {r.from_department_name || 'General Registry'}
                          </span>
                          <ArrowRight className="w-3.5 h-3.5 text-slate-400" />
                          <span className="font-semibold text-slate-900">
                            {r.to_department_name}
                          </span>
                        </div>
                        <span
                          className={`text-xs font-medium px-2 py-0.5 rounded ${
                            r.status === 'COMPLETED'
                              ? 'bg-slate-200 text-slate-800'
                              : r.status === 'ACKNOWLEDGED'
                              ? 'bg-slate-200 text-slate-800'
                              : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          {r.status}
                        </span>
                      </div>

                      {r.instructions && (
                        <p className="text-slate-700 italic text-xs">
                          "{r.instructions}"
                        </p>
                      )}

                      <div className="flex flex-wrap items-center justify-between pt-1 border-t border-slate-200/60 text-xs text-slate-400 gap-2">
                        <span>Action: {getRoutingActionLabel(r.action_required)}</span>

                        {/* Interactive Acknowledge / Complete Buttons */}
                        <div className="flex items-center gap-1.5">
                          {r.status === 'PENDING' && (
                            <button
                              type="button"
                              onClick={() => handleAcknowledgeRouting(r.id)}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium text-slate-700 bg-white hover:bg-slate-100 border border-slate-200"
                            >
                              <Check className="w-3 h-3 text-slate-600" />
                              Acknowledge Receipt
                            </button>
                          )}
                          {(r.status === 'PENDING' || r.status === 'ACKNOWLEDGED') && (
                            <button
                              type="button"
                              onClick={() => {
                                setCompletingRoutingId(r.id);
                                setShowCompleteModal(true);
                              }}
                              className="inline-flex items-center gap-1 px-2.5 py-1 rounded text-xs font-medium text-slate-700 bg-white hover:bg-slate-100 border border-slate-200"
                            >
                              <CheckCircle2 className="w-3 h-3 text-slate-600" />
                              Complete Task
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Display response notes if completed */}
                      {r.response_notes && (
                        <div className="mt-1.5 p-2 bg-slate-100 rounded-lg text-xs text-slate-800">
                          <span className="font-semibold block text-slate-700 mb-0.5">
                            Resolution Note:
                          </span>
                          <span>{r.response_notes}</span>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 italic py-2 text-center">
                  This letter has not been routed to any department yet.
                </p>
              )}
            </div>

            {/* Bottom Workflow Action Bar */}
            <div className="flex flex-wrap items-center justify-between gap-2 pt-4 border-t border-slate-100">
              <Button variant="ghost" size="sm" onClick={() => setSelectedLetter(null)}>
                Close
              </Button>

              <div className="flex flex-wrap items-center gap-2">
                {/* 1. Outward Draft -> Submit for Approval */}
                {selectedLetter.direction === 'OUTWARD' && selectedLetter.status === 'DRAFT' && (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleSubmitForApproval}
                    disabled={isActionLoading}
                  >
                    Submit for Approval
                  </Button>
                )}

                {/* 2. Pending Approval -> Reject or Approve */}
                {selectedLetter.status === 'PENDING_APPROVAL' && (
                  <>
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={() => setShowRejectModal(true)}
                      disabled={isActionLoading}
                    >
                      Reject
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleApprove}
                      disabled={isActionLoading}
                    >
                      Approve Outward Letter
                    </Button>
                  </>
                )}

                {/* 3. Approved Outward -> Dispatch */}
                {selectedLetter.direction === 'OUTWARD' && selectedLetter.status === 'APPROVED' && (
                  <Button
                    variant="primary"
                    size="sm"
                    leftIcon={<Send className="w-3.5 h-3.5" />}
                    onClick={() => setShowDispatchModal(true)}
                    disabled={isActionLoading}
                  >
                    Dispatch Letter
                  </Button>
                )}

                {/* 4. Active Letter -> Archive */}
                {selectedLetter.status !== 'ARCHIVED' &&
                  (selectedLetter.status === 'DISPATCHED' ||
                    selectedLetter.status === 'RECEIVED' ||
                    selectedLetter.status === 'APPROVED') && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleArchive}
                      disabled={isActionLoading}
                    >
                      Archive Letter
                    </Button>
                  )}
              </div>
            </div>
          </div>
        </Modal>
      )}

      {/* 3. Rejection Reason Modal */}
      <Modal
        isOpen={showRejectModal}
        onClose={() => setShowRejectModal(false)}
        title="Reject Letter Draft"
      >
        <div className="space-y-4">
          <Input
            label="Reason for Rejection / Changes Requested"
            placeholder="Enter feedback or explanation for the author..."
            value={rejectionReason}
            onChange={(e) => setRejectionReason(e.target.value)}
            required
            autoFocus
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setShowRejectModal(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleReject} disabled={isActionLoading}>
              Confirm Rejection
            </Button>
          </div>
        </div>
      </Modal>

      {/* 4. Dispatch Modal */}
      <Modal
        isOpen={showDispatchModal}
        onClose={() => setShowDispatchModal(false)}
        title="Dispatch Official Letter"
        maxWidth="md"
      >
        <form onSubmit={handleDispatchSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">
              Delivery Method
            </label>
            <select
              value={dispatchData.delivery_method}
              onChange={(e) => setDispatchData({ ...dispatchData, delivery_method: e.target.value })}
              className="w-full rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none"
            >
              <option value="HAND_DELIVERY">Hand Delivery</option>
              <option value="POSTAL">Postal Mail</option>
              <option value="COURIER">Courier Service</option>
              <option value="ELECTRONIC_EMAIL">Official Email</option>
              <option value="INTERNAL_DISPATCH">Internal Dispatch</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">
              Dispatched Date (Optional override)
            </label>
            <input
              type="date"
              value={dispatchData.dispatched_date_gc}
              onChange={(e) => setDispatchData({ ...dispatchData, dispatched_date_gc: e.target.value })}
              className="w-full rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
            <Button variant="ghost" type="button" onClick={() => setShowDispatchModal(false)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" disabled={isActionLoading}>
              Confirm Dispatch
            </Button>
          </div>
        </form>
      </Modal>

      {/* 5. Inter-Departmental Route / Transfer Modal */}
      <Modal
        isOpen={showRouteModal}
        onClose={() => setShowRouteModal(false)}
        title="Route Letter to Department"
        maxWidth="md"
      >
        <form onSubmit={handleRouteSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">
              Target Department
            </label>
            <select
              value={routeData.to_department_id}
              onChange={(e) => setRouteData({ ...routeData, to_department_id: e.target.value })}
              required
              className="w-full rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none"
            >
              <option value="">Select Destination Department...</option>
              {departments.map((dept) => (
                <option key={dept.id} value={dept.id}>
                  {dept.name} ({dept.code})
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">
                Action Required
              </label>
              <select
                value={routeData.action_required}
                onChange={(e) => setRouteData({ ...routeData, action_required: e.target.value })}
                className="w-full rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none"
              >
                <option value="FOR_ACTION">For Action</option>
                <option value="FOR_INFORMATION">For Information</option>
                <option value="FOR_APPROVAL">For Approval</option>
                <option value="FOR_COMMENT">For Comment</option>
                <option value="FOR_FILING">For Filing</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">
                Priority
              </label>
              <select
                value={routeData.priority}
                onChange={(e) => setRouteData({ ...routeData, priority: e.target.value })}
                className="w-full rounded-lg bg-slate-50 border border-slate-200 px-3 py-2 text-xs text-slate-900 focus:bg-white focus:outline-none"
              >
                <option value="NORMAL">Normal</option>
                <option value="URGENT">Urgent</option>
                <option value="VERY_URGENT">Very Urgent</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">
              Routing Instructions
            </label>
            <textarea
              rows={3}
              placeholder="Enter instructions, notes, or required actions for the department..."
              value={routeData.instructions}
              onChange={(e) => setRouteData({ ...routeData, instructions: e.target.value })}
              className="w-full rounded-lg bg-slate-50 border border-slate-200 p-2.5 text-xs text-slate-900 focus:bg-white focus:outline-none resize-none"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
            <Button variant="ghost" type="button" onClick={() => setShowRouteModal(false)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" disabled={isActionLoading}>
              Route Letter
            </Button>
          </div>
        </form>
      </Modal>

      {/* 6. Complete Routing Task Modal */}
      <Modal
        isOpen={showCompleteModal}
        onClose={() => setShowCompleteModal(false)}
        title="Complete Routing Task"
        maxWidth="md"
      >
        <form onSubmit={handleCompleteRoutingSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">
              Resolution Notes
            </label>
            <textarea
              rows={3}
              placeholder="Describe the action taken or resolution summary..."
              value={completeResponseNotes}
              onChange={(e) => setCompleteResponseNotes(e.target.value)}
              required
              autoFocus
              className="w-full rounded-lg bg-slate-50 border border-slate-200 p-2.5 text-xs text-slate-900 focus:bg-white focus:outline-none resize-none"
            />
          </div>

          <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
            <Button variant="ghost" type="button" onClick={() => setShowCompleteModal(false)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" disabled={isActionLoading}>
              Complete Task
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
