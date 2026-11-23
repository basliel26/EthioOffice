import React, { useState, useEffect } from 'react';
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
} from 'lucide-react';
import { lettersApi, departmentsApi } from '../../api/client';
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

  // Detail Modal & Routing
  const [selectedLetter, setSelectedLetter] = useState<LetterDetail | null>(null);

  // New Letter Modal
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

  const handleApprove = async () => {
    if (!selectedLetter) return;
    try {
      const updated = await lettersApi.approve(selectedLetter.id);
      setSelectedLetter(updated);
      loadLetters();
      loadSummaryAndDepts();
    } catch {
      // ignore
    }
  };

  const handleReject = async () => {
    if (!selectedLetter || !rejectionReason.trim()) return;
    try {
      const updated = await lettersApi.reject(selectedLetter.id, rejectionReason.trim());
      setSelectedLetter(updated);
      setShowRejectModal(false);
      setRejectionReason('');
      loadLetters();
      loadSummaryAndDepts();
    } catch {
      // ignore
    }
  };

  const tabs = [
    { id: 'ALL', label: 'ሁሉም (All Letters)' },
    { id: 'INWARD', label: 'ገቢ ደብዳቤዎች (Inward)' },
    { id: 'OUTWARD', label: 'ወጪ ደብዳቤዎች (Outward)' },
    { id: 'INTERNAL_MEMO', label: 'የውስጥ ማስታወሻ (Internal Memos)' },
  ];

  const getDirectionBadge = (direction: string) => {
    switch (direction) {
      case 'INWARD':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-blue-700 bg-blue-50/90 px-2 py-0.5 rounded-md">
            <ArrowDownLeft className="w-3 h-3 text-blue-600" />
            ገቢ (Inward)
          </span>
        );
      case 'OUTWARD':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 bg-emerald-50/90 px-2 py-0.5 rounded-md">
            <ArrowUpRight className="w-3 h-3 text-emerald-600" />
            ወጪ (Outward)
          </span>
        );
      case 'INTERNAL_MEMO':
        return (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-purple-700 bg-purple-50/90 px-2 py-0.5 rounded-md">
            <FileText className="w-3 h-3 text-purple-600" />
            ማስታወሻ (Memo)
          </span>
        );
      default:
        return null;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'APPROVED':
        return <Badge variant="success" dot>የጸደቀ (Approved)</Badge>;
      case 'PENDING_APPROVAL':
        return <Badge variant="warning" dot>ይሁንታ የሚጠብቅ (Pending)</Badge>;
      case 'DISPATCHED':
        return <Badge variant="info" dot>የተላከ (Dispatched)</Badge>;
      case 'RECEIVED':
        return <Badge variant="default" dot>የደረሰ (Received)</Badge>;
      case 'ARCHIVED':
        return <Badge variant="neutral">የተመዘገበ (Archived)</Badge>;
      case 'REJECTED':
        return <Badge variant="danger" dot>ተመላሽ የተደረገ (Rejected)</Badge>;
      default:
        return <Badge variant="neutral">ረቂቅ (Draft)</Badge>;
    }
  };

  return (
    <div className="space-y-6 select-none font-sans">
      {/* Top Header & Registration Action */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-zinc-100">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900 tracking-tight">
            የደብዳቤዎች መዝገብ ቤት (Official Letter Registry)
          </h1>
          <p className="text-xs text-zinc-500 mt-0.5">
            የገቢ፣ ወጪ እና የውስጥ ደብዳቤዎች ዲጂታል ምዝገባ እና የስራ እንቅስቃሴዎች
          </p>
        </div>

        <Button
          variant="primary"
          size="sm"
          leftIcon={<Plus className="w-4 h-4" />}
          onClick={() => setShowCreateModal(true)}
        >
          አዲስ ደብዳቤ መዝግብ (Register Letter)
        </Button>
      </div>

      {/* Executive KPI Ribbon */}
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
              ? 'border-blue-400/80 shadow-xs ring-1 ring-blue-100'
              : 'border-zinc-200/60 hover:border-zinc-300 shadow-2xs'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-500">ጠቅላላ መዝገብ (Total)</span>
            <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
              <Mail className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-zinc-900 tracking-tight mt-1.5">
            {summary?.total_letters ?? 0}
          </div>
          <p className="text-[11px] text-zinc-400 mt-1 truncate">
            ገቢ {summary?.inward_count ?? 0} • ወጪ {summary?.outward_count ?? 0} • ማስታወሻ {summary?.memo_count ?? 0}
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
              ? 'border-amber-400 shadow-xs ring-1 ring-amber-100 bg-amber-50/20'
              : 'border-zinc-200/60 hover:border-zinc-300 shadow-2xs'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-500">ይሁንታ የሚጠብቁ (Pending)</span>
            <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-zinc-900 tracking-tight mt-1.5">
            {summary?.pending_approval_count ?? 0}
          </div>
          <p className="text-[11px] text-amber-600 font-medium mt-1 truncate">
            {summary?.urgent_open_count ?? 0} አስቸኳይ ይሁንታ የሚጠብቁ
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
              ? 'border-emerald-400 shadow-xs ring-1 ring-emerald-100 bg-emerald-50/20'
              : 'border-zinc-200/60 hover:border-zinc-300 shadow-2xs'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-500">የተላኩ / የወጡ (Dispatched)</span>
            <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <Send className="w-4 h-4" />
            </div>
          </div>
          <div className="text-2xl font-bold text-zinc-900 tracking-tight mt-1.5">
            {summary?.dispatched_count ?? 0}
          </div>
          <p className="text-[11px] text-zinc-400 mt-1 truncate">
            የደረሱ {summary?.received_count ?? 0} • የተመዘገቡ {summary?.archived_count ?? 0}
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
              ? 'border-rose-400 shadow-xs ring-1 ring-rose-100 bg-rose-50/20'
              : 'border-zinc-200/60 hover:border-zinc-300 shadow-2xs'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-zinc-500">የጊዜ ገደብ ያለፈባቸው (Overdue)</span>
            <div className="w-8 h-8 rounded-lg bg-rose-50 text-rose-600 flex items-center justify-center">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div
            className={`text-2xl font-bold tracking-tight mt-1.5 ${
              (summary?.overdue_sla_count ?? 0) > 0 ? 'text-rose-600' : 'text-zinc-900'
            }`}
          >
            {summary?.overdue_sla_count ?? 0}
          </div>
          <p className="text-[11px] text-zinc-400 mt-1 truncate">
            የኢትዮጵያ የስራ ቀናት SLA
          </p>
        </div>
      </div>

      {/* Filter Tabs & Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <Tabs
          items={tabs}
          activeId={directionTab}
          onChange={(id) => setDirectionTab(id as any)}
        />

        <div className="w-full sm:w-72">
          <Input
            placeholder="በቁጥር፣ ርዕስ፣ ላኪ ወይም ተቀባይ ፈልግ..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            leftIcon={<Search className="w-3.5 h-3.5" />}
          />
        </div>
      </div>

      {/* Secondary Filter Dropdowns & SLA Controls */}
      <div className="flex flex-wrap items-center gap-2 pt-1">
        {/* Status Filter */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Filter by letter status"
          className="text-xs font-medium text-zinc-700 bg-white border border-zinc-200/80 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-zinc-400"
        >
          <option value="ALL">ሁሉም ሁኔታዎች (All Statuses)</option>
          <option value="DRAFT">ረቂቅ (Draft)</option>
          <option value="PENDING_APPROVAL">ይሁንታ የሚጠብቅ (Pending Approval)</option>
          <option value="APPROVED">የጸደቀ (Approved)</option>
          <option value="DISPATCHED">የተላከ (Dispatched)</option>
          <option value="RECEIVED">የደረሰ (Received)</option>
          <option value="ARCHIVED">በመዝገብ የገባ (Archived)</option>
        </select>

        {/* Urgency Filter */}
        <select
          value={urgencyFilter}
          onChange={(e) => setUrgencyFilter(e.target.value)}
          aria-label="Filter by letter urgency"
          className="text-xs font-medium text-zinc-700 bg-white border border-zinc-200/80 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-zinc-400"
        >
          <option value="ALL">ሁሉም አጣዳፊነት (All Urgencies)</option>
          <option value="NORMAL">መደበኛ - 5 ቀናት (Normal)</option>
          <option value="URGENT">አስቸኳይ - 3 ቀናት (Urgent)</option>
          <option value="VERY_URGENT">በጣም አስቸኳይ - 24 ሰዓት (Very Urgent)</option>
        </select>

        {/* Department Filter */}
        {departments.length > 0 && (
          <select
            value={departmentFilter}
            onChange={(e) => setDepartmentFilter(e.target.value)}
            aria-label="Filter by department"
            className="text-xs font-medium text-zinc-700 bg-white border border-zinc-200/80 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-zinc-400"
          >
            <option value="ALL">ሁሉም የስራ ክፍሎች (All Departments)</option>
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
          className={`px-2.5 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 ${
            isOverdueOnly
              ? 'bg-rose-50 text-rose-700 border border-rose-200'
              : 'bg-white text-zinc-600 border border-zinc-200/80 hover:bg-zinc-50'
          }`}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              isOverdueOnly ? 'bg-rose-600 animate-pulse' : 'bg-zinc-400'
            }`}
          />
          የጊዜ ገደብ ያለፈባቸው (Overdue Only)
        </button>

        {/* Reset Filters Button */}
        {isFiltered && (
          <button
            type="button"
            onClick={handleResetFilters}
            className="px-2.5 py-1.5 text-xs font-medium rounded-lg text-zinc-500 hover:text-zinc-800 hover:bg-zinc-100 transition-colors flex items-center gap-1"
          >
            <RotateCcw className="w-3 h-3" />
            ዳግም ጀምር (Clear Filters)
          </button>
        )}
      </div>

      {/* Letters Data Table */}
      <div className="bg-white rounded-2xl shadow-xs border border-zinc-200/60 overflow-hidden">
        {isLoading ? (
          <div className="py-20 text-center text-xs text-zinc-400">ደብዳቤዎች እየተጫኑ ነው...</div>
        ) : letters.length === 0 ? (
          <div className="py-20 text-center space-y-2">
            <Mail className="w-8 h-8 text-zinc-300 mx-auto" />
            <p className="text-sm font-medium text-zinc-900">ምንም ደብዳቤ አልተመዘገበም (No letters found)</p>
            <p className="text-xs text-zinc-400">አዲስ ደብዳቤ በመመዝገብ ስራዎን ይጀምሩ።</p>
          </div>
        ) : (
          <div className="divide-y divide-zinc-100">
            {letters.map((letter) => (
              <div
                key={letter.id}
                onClick={() => handleOpenDetail(letter.id)}
                className="flex items-center justify-between p-4 hover:bg-zinc-50/70 transition-colors cursor-pointer group"
              >
                {/* Left: Ref number, Subject, Direction, Tags */}
                <div className="min-w-0 flex-1 pr-4">
                  <div className="flex flex-wrap items-center gap-2 mb-1.5">
                    <span className="font-mono text-xs font-semibold text-zinc-900 bg-zinc-100 px-2 py-0.5 rounded">
                      {letter.reference_number}
                    </span>
                    {getDirectionBadge(letter.direction)}
                    {getStatusBadge(letter.status)}
                    {letter.urgency === 'VERY_URGENT' && (
                      <Badge variant="danger">አስቸኳይ</Badge>
                    )}
                    {letter.department_name && (
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-zinc-500 bg-zinc-100/70 px-2 py-0.5 rounded">
                        <Building2 className="w-3 h-3 text-zinc-400" />
                        {letter.department_name}
                      </span>
                    )}
                  </div>
                  <h4 className="text-xs font-medium text-zinc-900 truncate group-hover:text-zinc-950">
                    {letter.subject}
                  </h4>
                  <div className="flex items-center gap-3 mt-1.5 text-[11px] text-zinc-400">
                    <span>ላኪ፦ {letter.sender_entity}</span>
                    <span>•</span>
                    <span>ተቀባይ፦ {letter.recipient_entity}</span>
                    {letter.attachment_file_id && (
                      <>
                        <span>•</span>
                        <span className="inline-flex items-center gap-1 text-zinc-500">
                          <Paperclip className="w-3 h-3" />
                          ተያያዥ ሰነድ
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {/* Right: Date, Due SLA, Arrow */}
                <div className="flex items-center gap-4 shrink-0 text-right">
                  <div>
                    <span className="text-xs font-medium text-zinc-800 block">
                      {letter.date_ec}
                    </span>
                    {letter.days_remaining !== undefined && letter.days_remaining !== null && (
                      <span
                        className={`text-[10px] ${
                          letter.is_overdue ? 'text-red-500 font-semibold' : 'text-zinc-400'
                        }`}
                      >
                        {letter.is_overdue ? 'የጊዜ ገደብ አልፏል' : `ቀሪ ${letter.days_remaining} ቀናት`}
                      </span>
                    )}
                  </div>
                  <ChevronRight className="w-4 h-4 text-zinc-300 group-hover:text-zinc-600 transition-colors" />
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
        title="አዲስ ደብዳቤ መዝግብ (Register Official Letter)"
        maxWidth="xl"
      >
        <form onSubmit={handleCreateSubmit} className="space-y-4">
          <div className="grid grid-cols-3 gap-2 p-1 bg-zinc-100/80 rounded-lg text-xs font-medium">
            <button
              type="button"
              onClick={() => setNewLetter({ ...newLetter, direction: 'INWARD' })}
              className={`py-1.5 rounded-md transition-colors flex items-center justify-center gap-1.5 ${
                newLetter.direction === 'INWARD'
                  ? 'bg-white text-zinc-900 shadow-2xs font-semibold'
                  : 'text-zinc-600'
              }`}
            >
              <ArrowDownLeft className="w-3.5 h-3.5 text-blue-600" />
              ገቢ (Inward)
            </button>
            <button
              type="button"
              onClick={() => setNewLetter({ ...newLetter, direction: 'OUTWARD' })}
              className={`py-1.5 rounded-md transition-colors flex items-center justify-center gap-1.5 ${
                newLetter.direction === 'OUTWARD'
                  ? 'bg-white text-zinc-900 shadow-2xs font-semibold'
                  : 'text-zinc-600'
              }`}
            >
              <ArrowUpRight className="w-3.5 h-3.5 text-emerald-600" />
              ወጪ (Outward)
            </button>
            <button
              type="button"
              onClick={() => setNewLetter({ ...newLetter, direction: 'INTERNAL_MEMO' })}
              className={`py-1.5 rounded-md transition-colors flex items-center justify-center gap-1.5 ${
                newLetter.direction === 'INTERNAL_MEMO'
                  ? 'bg-white text-zinc-900 shadow-2xs font-semibold'
                  : 'text-zinc-600'
              }`}
            >
              <FileText className="w-3.5 h-3.5 text-purple-600" />
              ማስታወሻ (Memo)
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="sm:col-span-2">
              <Input
                label="የደብዳቤው ርዕስ ወይም ጉዳይ (Subject)"
                placeholder="ለምሳሌ፡ የ2018 ዓ.ም የፋይናንስ ኦዲት ሪፖርት"
                value={newLetter.subject}
                onChange={(e) => setNewLetter({ ...newLetter, subject: e.target.value })}
                required
                autoFocus
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-1.5">
                የስራ ክፍል (Department)
              </label>
              <select
                value={newLetter.department_id}
                onChange={(e) => setNewLetter({ ...newLetter, department_id: e.target.value })}
                className="w-full rounded-lg bg-zinc-50/80 border border-zinc-200/80 px-3 py-2 text-xs text-zinc-900 focus:bg-white focus:outline-none"
              >
                <option value="">ጠቅላላ መዝገብ ቤት (Org Wide)</option>
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
                label="ላኪ ተቋም / ክፍል (Sender Entity)"
                placeholder="ለምሳሌ፡ የገንዘብ ሚኒስቴር ወይም ዳይሬክቶሬት"
                value={newLetter.sender_entity}
                onChange={(e) => setNewLetter({ ...newLetter, sender_entity: e.target.value })}
                required
              />
              <Input
                label="የላኪ አድራሻ / ስልክ (Sender Contact)"
                placeholder="ስልክ ወይም ኢሜይል (አማራጭ)"
                value={newLetter.sender_contact}
                onChange={(e) => setNewLetter({ ...newLetter, sender_contact: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Input
                label="ተቀባይ ተቋም / ክፍል (Recipient Entity)"
                placeholder="ለምሳሌ፡ ዋና ስራ አስፈፃሚ ወይም የሰው ኃይል"
                value={newLetter.recipient_entity}
                onChange={(e) => setNewLetter({ ...newLetter, recipient_entity: e.target.value })}
                required
              />
              <Input
                label="የተቀባይ አድራሻ / ስልክ (Recipient Contact)"
                placeholder="ስልክ ወይም ኢሜይል (አማራጭ)"
                value={newLetter.recipient_contact}
                onChange={(e) => setNewLetter({ ...newLetter, recipient_contact: e.target.value })}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-1.5">
                አስቸኳይነት (Urgency & SLA)
              </label>
              <select
                value={newLetter.urgency}
                onChange={(e) => setNewLetter({ ...newLetter, urgency: e.target.value })}
                className="w-full rounded-lg bg-zinc-50/80 border border-zinc-200/80 px-3 py-2 text-xs text-zinc-900 focus:bg-white focus:outline-none"
              >
                <option value="NORMAL">መደበኛ - 5 የስራ ቀናት (Normal - 5 Days SLA)</option>
                <option value="URGENT">አስቸኳይ - 3 የስራ ቀናት (Urgent - 3 Days SLA)</option>
                <option value="VERY_URGENT">በጣም አስቸኳይ - 24 ሰዓት (Very Urgent - 24h SLA)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-zinc-600 mb-1.5">
                የደህንነት ደረጃ (Confidentiality)
              </label>
              <select
                value={newLetter.confidentiality}
                onChange={(e) => setNewLetter({ ...newLetter, confidentiality: e.target.value })}
                className="w-full rounded-lg bg-zinc-50/80 border border-zinc-200/80 px-3 py-2 text-xs text-zinc-900 focus:bg-white focus:outline-none"
              >
                <option value="NORMAL">መደበኛ (Standard / Public)</option>
                <option value="CONFIDENTIAL">ሚስጥራዊ (Confidential)</option>
                <option value="STRICTLY_CONFIDENTIAL">በጣም ሚስጥራዊ (Strictly Confidential)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <Input
              label={
                newLetter.direction === 'INWARD'
                  ? 'የውስጥ መዝገብ ቁጥር (ከተፈለገ በራስ-ሰር ይዘጋጃል)'
                  : 'የደብዳቤ ቁጥር (ከተፈለገ በራስ-ሰር ይዘጋጃል)'
              }
              placeholder="ለምሳሌ፡ EO/FIN/2018/0042"
              value={newLetter.reference_number}
              onChange={(e) => setNewLetter({ ...newLetter, reference_number: e.target.value })}
            />

            {newLetter.direction === 'INWARD' ? (
              <Input
                label="የላኪው ተቋም ደብዳቤ ቁጥር (External Ref Number)"
                placeholder="ለምሳሌ፡ ገ/ሚ/04-2018"
                value={newLetter.external_reference_number}
                onChange={(e) =>
                  setNewLetter({ ...newLetter, external_reference_number: e.target.value })
                }
              />
            ) : (
              <Input
                label="ተጨማሪ ማስታወሻ (Notes)"
                placeholder="ተያያዥ ማብራሪያ ካለ..."
                value={newLetter.notes}
                onChange={(e) => setNewLetter({ ...newLetter, notes: e.target.value })}
              />
            )}
          </div>

          {newLetter.direction === 'INWARD' && (
            <Input
              label="ተጨማሪ ማስታወሻ (Notes)"
              placeholder="ተያያዥ ማብራሪያ ካለ..."
              value={newLetter.notes}
              onChange={(e) => setNewLetter({ ...newLetter, notes: e.target.value })}
            />
          )}

          <div className="flex justify-end gap-2 pt-3 border-t border-zinc-100">
            <Button variant="ghost" type="button" onClick={() => setShowCreateModal(false)}>
              ተመለስ (Cancel)
            </Button>
            <Button variant="primary" type="submit">
              መዝግብ (Save Letter)
            </Button>
          </div>
        </form>
      </Modal>

      {/* 2. Letter Detail & Routing Trail Modal */}
      {selectedLetter && (
        <Modal
          isOpen={!!selectedLetter}
          onClose={() => setSelectedLetter(null)}
          title={selectedLetter.reference_number}
          description={selectedLetter.subject}
          maxWidth="2xl"
        >
          <div className="space-y-6">
            {/* Top metadata cards */}
            <div className="grid grid-cols-3 gap-3 p-3.5 bg-zinc-50 rounded-xl text-xs">
              <div>
                <span className="text-zinc-400 block text-[10px]">ሁኔታ (Status)</span>
                <span className="font-medium text-zinc-900 mt-0.5 block">{getStatusBadge(selectedLetter.status)}</span>
              </div>
              <div>
                <span className="text-zinc-400 block text-[10px]">የተመዘገበበት ቀን (EC Date)</span>
                <span className="font-medium text-zinc-900 mt-0.5 block">{selectedLetter.date_ec}</span>
              </div>
              <div>
                <span className="text-zinc-400 block text-[10px]">የስራ ክፍል (Department)</span>
                <span className="font-medium text-zinc-900 mt-0.5 block">{selectedLetter.department_name || 'ጠቅላላ መዝገብ'}</span>
              </div>
            </div>

            {/* Inward/Outward Details */}
            <div className="text-xs space-y-2 border-b border-zinc-100 pb-4">
              <div className="flex justify-between">
                <span className="text-zinc-500">ላኪ (Sender):</span>
                <span className="font-medium text-zinc-900">{selectedLetter.sender_entity}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">ተቀባይ (Recipient):</span>
                <span className="font-medium text-zinc-900">{selectedLetter.recipient_entity}</span>
              </div>
              {selectedLetter.notes && (
                <div className="flex justify-between">
                  <span className="text-zinc-500">ማስታወሻ (Notes):</span>
                  <span className="text-zinc-700">{selectedLetter.notes}</span>
                </div>
              )}
            </div>

            {/* Attached Drive Files */}
            <div>
              <h5 className="text-xs font-semibold text-zinc-900 mb-2 flex items-center gap-1.5">
                <Paperclip className="w-3.5 h-3.5 text-zinc-400" />
                <span>ተያያዥ ሰነዶች (Attached Documents)</span>
              </h5>
              {selectedLetter.attachments && selectedLetter.attachments.length > 0 ? (
                <div className="divide-y divide-zinc-100 rounded-lg border border-zinc-200/60 p-2">
                  {selectedLetter.attachments.map((att) => (
                    <div key={att.id} className="py-1.5 flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2 min-w-0">
                        <FileText className="w-3.5 h-3.5 text-zinc-400 shrink-0" />
                        <span className="font-medium text-zinc-900 truncate">{att.file_name}</span>
                        <span className="text-[10px] text-zinc-400">({att.attachment_type})</span>
                      </div>
                      <a
                        href={`/api/v1/files/${att.file_id}/download`}
                        className="text-xs text-zinc-600 hover:text-zinc-900 ml-2"
                      >
                        አውርድ
                      </a>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-zinc-400 italic">ምንም ተያያዥ ሰነድ የለም።</p>
              )}
            </div>

            {/* Chain of Custody Routing Trail */}
            <div>
              <h5 className="text-xs font-semibold text-zinc-900 mb-2 flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-zinc-400" />
                <span>የደብዳቤው የስራ እንቅስቃሴ (Chain of Custody Trail)</span>
              </h5>
              {selectedLetter.routings && selectedLetter.routings.length > 0 ? (
                <div className="space-y-2">
                  {selectedLetter.routings.map((r) => (
                    <div key={r.id} className="p-3 bg-zinc-50 rounded-xl text-xs space-y-1">
                      <div className="flex items-center justify-between text-[11px] text-zinc-500">
                        <span>ከ፦ {r.from_user_name || 'ሰራተኛ'} ({r.from_department_name || 'መምሪያ'})</span>
                        <span className="font-semibold text-zinc-900">ወደ፦ {r.to_department_name}</span>
                      </div>
                      {r.instructions && (
                        <p className="text-zinc-700 italic">" {r.instructions} "</p>
                      )}
                      <div className="flex justify-between items-center pt-1 text-[10px] text-zinc-400">
                        <span>ተግባር፦ {r.action_required}</span>
                        <span className="font-medium text-emerald-700">{r.status}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-zinc-400 italic">ይህ ደብዳቤ እስካሁን ወደ ሌላ ክፍል አልተመራም።</p>
              )}
            </div>

            {/* Approval Controls for Outward Drafts */}
            {selectedLetter.direction === 'OUTWARD' && selectedLetter.status === 'PENDING_APPROVAL' && (
              <div className="flex justify-end gap-2 pt-4 border-t border-zinc-100">
                <Button variant="danger" size="sm" onClick={() => setShowRejectModal(true)}>
                  መልስ / አትፍቀድ (Reject)
                </Button>
                <Button variant="primary" size="sm" onClick={handleApprove}>
                  አጽድቅ (Approve Outward Letter)
                </Button>
              </div>
            )}
          </div>
        </Modal>
      )}

      {/* 3. Rejection Reason Modal */}
      <Modal
        isOpen={showRejectModal}
        onClose={() => setShowRejectModal(false)}
        title="ደብዳቤውን ያለማጽደቂያ ምክንያት (Rejection Feedback)"
      >
        <div className="space-y-4">
          <Input
            placeholder="ምክንያቱን እዚህ ይግለጹ..."
            value={rejectionReason}
            onChange={(e) => setRejectionReason(e.target.value)}
            required
            autoFocus
          />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setShowRejectModal(false)}>
              ተመለስ (Cancel)
            </Button>
            <Button variant="danger" onClick={handleReject}>
              አትፍቀድ (Confirm Rejection)
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
