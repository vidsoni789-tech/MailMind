import React, { useState, useEffect } from 'react';
import {
  ArrowLeft,
  Archive,
  Trash2,
  Mail,
  MailOpen,
  Star,
  Reply,
  Sparkles,
  ShieldAlert,
  CheckSquare,
  ChevronDown,
  ChevronUp,
  Clock,
  Send,
  Check,
  Copy,
  X,
  ExternalLink,
  FileText,
} from 'lucide-react';
import { Email, ThreadMessage, DraftCardData } from '../types';
import { api } from '../api';
import { DraftCard } from './DraftCard';

interface EmailDetailProps {
  email: Email;
  onBack: () => void;
  onAskAi: (prompt: string, draft?: DraftCardData, actionType?: 'draft' | 'tasks' | 'summary') => void;
  onMarkRead?: (messageId: string, isRead: boolean) => void;
  showAiPanel?: boolean;
  onToggleAiPanel?: () => void;
  isAiStreaming?: boolean;
  aiStreamingAction?: 'draft' | 'tasks' | 'summary' | null;
  activeDraft?: DraftCardData | null;
  aiSummary?: string | null;
  aiTasksResult?: string | null;
  onClearSummary?: () => void;
  onClearTasks?: () => void;
  onViewTasksTab?: () => void;
  onSendDraftClick?: (draft: DraftCardData) => void;
  onSaveDraft?: (draft: DraftCardData) => Promise<void> | void;
  onImproveDraft?: (instruction: string, draft?: DraftCardData) => void;
  onDiscardDraft?: () => void;
}

export const EmailDetail: React.FC<EmailDetailProps> = ({
  email,
  onBack,
  onAskAi,
  onMarkRead,
  isAiStreaming = false,
  aiStreamingAction = null,
  activeDraft = null,
  aiSummary = null,
  aiTasksResult = null,
  onClearSummary,
  onClearTasks,
  onViewTasksTab,
  onSendDraftClick,
  onSaveDraft,
  onImproveDraft,
  onDiscardDraft,
}) => {
  const [threadMessages, setThreadMessages] = useState<ThreadMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [isStarred, setIsStarred] = useState(false);
  const [isReadState, setIsReadState] = useState(email.is_read === 1);
  const [expandedMessages, setExpandedMessages] = useState<Record<string, boolean>>({});
  const [showDetails, setShowDetails] = useState<Record<string, boolean>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [summaryCopied, setSummaryCopied] = useState(false);

  // Quick reply prompt state
  const [quickReplyText, setQuickReplyText] = useState('');
  const [showReplyBox, setShowReplyBox] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const fetchThread = async () => {
      setLoading(true);
      try {
        if (email.thread_id) {
          const res = await api.getThread(email.thread_id);
          if (isMounted) {
            const msgs = res.messages && res.messages.length > 0 ? res.messages : [];
            setThreadMessages(msgs);
            if (msgs.length > 0) {
              const lastId = msgs[msgs.length - 1].message_id || msgs[msgs.length - 1].id || '0';
              setExpandedMessages({ [lastId]: true });
            }
          }
        } else {
          const single = await api.getEmail(email.message_id);
          if (isMounted) {
            setThreadMessages([single as any]);
            setExpandedMessages({ [single.message_id]: true });
          }
        }
      } catch (e) {
        console.error('Failed to load thread messages:', e);
        if (isMounted) {
          setThreadMessages([
            {
              message_id: email.message_id,
              thread_id: email.thread_id,
              subject: email.subject,
              snippet: email.snippet,
              from_email: email.from_email,
              from_name: email.from_name,
              to_emails: email.to_emails || 'me',
              date: email.date,
              body: email.body || email.snippet,
              category: email.category,
              priority: email.priority,
            },
          ]);
          setExpandedMessages({ [email.message_id]: true });
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchThread();
    return () => {
      isMounted = false;
    };
  }, [email.message_id, email.thread_id]);

  const handleToggleRead = async () => {
    const nextRead = !isReadState;
    setIsReadState(nextRead);
    if (onMarkRead) {
      onMarkRead(email.message_id, nextRead);
    }
    try {
      await api.markRead(email.message_id, nextRead);
    } catch (e) {
      console.error(e);
    }
  };

  const toggleExpand = (msgId: string) => {
    setExpandedMessages((prev) => ({
      ...prev,
      [msgId]: !prev[msgId],
    }));
  };

  const handleCopyBody = (text: string, msgId: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(msgId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleCopySummary = (text: string) => {
    navigator.clipboard.writeText(text);
    setSummaryCopied(true);
    setTimeout(() => setSummaryCopied(false), 2000);
  };

  const renderFormattedAiText = (rawText: string) => {
    const lines = rawText.split('\n');
    return (
      <div className="space-y-1.5 text-xs leading-relaxed text-[#252821] select-text">
        {lines.map((line, idx) => {
          const trimmed = line.trim();
          if (!trimmed) return <div key={idx} className="h-1" />;

          const isHeader =
            trimmed.startsWith('#') ||
            trimmed.includes('**Executive Summary') ||
            trimmed.includes('**Decisions') ||
            trimmed.includes('**Key Dates') ||
            trimmed.includes('**Next Steps') ||
            trimmed.includes('**Requests') ||
            trimmed.includes('**Extracted');

          const isBullet =
            trimmed.startsWith('•') || trimmed.startsWith('- ') || trimmed.startsWith('* ');
          const cleanLine = isBullet ? trimmed.replace(/^[•\-\*]\s*/, '') : trimmed;

          // Parse **bold** parts
          const parts = cleanLine.split(/(\*\*[^*]+\*\*)/g);
          const renderedParts = parts.map((part, pIdx) => {
            if (part.startsWith('**') && part.endsWith('**')) {
              return (
                <strong key={pIdx} className="font-semibold text-[#181916]">
                  {part.slice(2, -2)}
                </strong>
              );
            }
            return part;
          });

          if (isBullet) {
            return (
              <div key={idx} className="flex items-start gap-2 pl-1">
                <span className="text-[#4263EB] font-bold mt-0.5">•</span>
                <span className="flex-1">{renderedParts}</span>
              </div>
            );
          }

          return (
            <div
              key={idx}
              className={isHeader ? 'font-semibold text-[#181916] pt-1.5 pb-0.5' : ''}
            >
              {renderedParts}
            </div>
          );
        })}
      </div>
    );
  };

  const getInitials = (name?: string, emailStr?: string) => {
    const source = (name || emailStr || 'U').trim();
    const parts = source.split(' ').filter(Boolean);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return source.slice(0, 2).toUpperCase();
  };

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;
      return d.toLocaleString([], {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#F7F5F0] min-w-0 select-none">
      {/* Top Action Toolbar */}
      <div className="h-14 border-b border-[#E7E4DC] bg-white px-4 sm:px-6 flex items-center justify-between flex-shrink-0 z-10">
        <div className="flex items-center space-x-1 sm:space-x-2">
          {/* Back button */}
          <button
            onClick={onBack}
            className="h-8 px-2.5 rounded-lg text-[#74766F] hover:text-[#252821] hover:bg-[#F0EEE7] flex items-center gap-1.5 text-xs font-medium transition"
            title="Return to inbox"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Back</span>
          </button>

          <div className="h-4 w-px bg-[#E7E4DC] mx-1" />

          {/* Mark Read/Unread */}
          <button
            onClick={handleToggleRead}
            className="h-8 w-8 rounded-lg text-[#74766F] hover:text-[#252821] hover:bg-[#F0EEE7] flex items-center justify-center transition"
            title={isReadState ? 'Mark unread' : 'Mark read'}
          >
            {isReadState ? <Mail className="w-4 h-4" /> : <MailOpen className="w-4 h-4 text-[#4263EB]" />}
          </button>

          {/* Star */}
          <button
            onClick={() => setIsStarred(!isStarred)}
            className={`h-8 w-8 rounded-lg flex items-center justify-center transition hover:bg-[#F0EEE7] ${
              isStarred ? 'text-[#A66A12]' : 'text-[#74766F] hover:text-[#252821]'
            }`}
            title={isStarred ? 'Starred' : 'Star'}
          >
            <Star className={`w-4 h-4 ${isStarred ? 'fill-[#A66A12]' : ''}`} />
          </button>

          {/* Archive */}
          <button
            onClick={onBack}
            className="h-8 w-8 rounded-lg text-[#74766F] hover:text-[#252821] hover:bg-[#F0EEE7] flex items-center justify-center transition"
            title="Archive"
          >
            <Archive className="w-4 h-4" />
          </button>

          {/* Delete */}
          <button
            onClick={onBack}
            className="h-8 w-8 rounded-lg text-[#74766F] hover:text-[#C24141] hover:bg-[#FDF2F2] flex items-center justify-center transition"
            title="Delete"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>

        {/* AI Quick Reply Action */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() =>
              onAskAi(
                `Please compose a professional, friendly reply to: "${email.subject}". Keep it concise and clear.`,
                undefined,
                'draft'
              )
            }
            disabled={isAiStreaming}
            className="h-8 px-3 rounded-lg bg-white hover:bg-[#F0EEE7] border border-[#E7E4DC] text-[#252821] text-xs font-medium flex items-center gap-1.5 transition disabled:opacity-50 shadow-sm"
          >
            <Sparkles className="w-3.5 h-3.5 text-[#4263EB]" />
            <span>Draft with AI</span>
          </button>
        </div>
      </div>

      {/* Main Conversation Scrollable Surface */}
      <div className="flex-1 overflow-y-auto px-5 py-6 sm:px-8 space-y-6 max-w-4xl w-full mx-auto">
        {/* Subject & Metadata Header */}
        <div className="border-b border-[#E7E4DC] pb-4 space-y-2">
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
            <h1 className="text-xl sm:text-2xl font-semibold text-[#252821] tracking-tight leading-snug">
              {email.subject || '(No Subject)'}
            </h1>

            {/* Badges */}
            <div className="flex items-center gap-1.5 flex-wrap flex-shrink-0">
              {email.category && (
                <span className="text-xs px-2 py-0.5 rounded bg-white border border-[#E7E4DC] text-[#74766F] uppercase font-mono">
                  {email.category}
                </span>
              )}

              {email.priority && (
                <span
                  className={`text-xs px-2 py-0.5 rounded font-medium border ${
                    email.priority === 'urgent' || email.priority === 'high'
                      ? 'bg-[#FDF2F2] text-[#C24141] border-[#F8D7D7]'
                      : email.priority === 'medium'
                      ? 'bg-[#FEF8ED] text-[#A66A12] border-[#FCE6BE]'
                      : 'bg-[#F0FDF4] text-[#23845B] border-[#DCFCE7]'
                  }`}
                >
                  {email.priority.toUpperCase()} Priority
                </span>
              )}

              {email.requires_reply === 1 && (
                <span className="text-xs px-2 py-0.5 rounded bg-[#EAEFFF] text-[#4263EB] border border-[#D0DBFF] flex items-center gap-1 font-medium">
                  <Reply className="w-3 h-3" />
                  Reply Needed
                </span>
              )}
            </div>
          </div>

          {/* Security alert if caution/danger */}
          {email.security_risk && email.security_risk !== 'safe' && (
            <div className="p-3 rounded-lg bg-[#FDF2F2] border border-[#F8D7D7] flex items-start space-x-2.5 text-[#C24141] text-xs">
              <ShieldAlert className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <div>
                <span className="font-semibold mr-1">Security Alert ({email.security_risk.toUpperCase()}):</span>
                This email was flagged for suspicious content. Avoid downloading unverified links or attachments.
              </div>
            </div>
          )}

          {/* AI Context note */}
          {email.triage_reason && (
            <div className="p-2.5 rounded-lg bg-white border border-[#E7E4DC] flex items-center space-x-2 text-[#74766F] text-xs shadow-card">
              <Sparkles className="w-3.5 h-3.5 text-[#4263EB] flex-shrink-0" />
              <span>
                <span className="font-medium text-[#252821] mr-1">Triage Note:</span>
                {email.triage_reason}
              </span>
            </div>
          )}
        </div>

        {/* Thread Messages */}
        {loading ? (
          <div className="py-12 text-center text-[#74766F] text-xs">
            <div className="inline-block animate-spin rounded-full h-5 w-5 border-2 border-[#4263EB] border-t-transparent mb-2" />
            <p>Loading conversation thread...</p>
          </div>
        ) : (
          <div className="space-y-4">
            {threadMessages.map((msg, index) => {
              const msgId = msg.message_id || msg.id || String(index);
              const isExpanded = !!expandedMessages[msgId];
              const senderName = msg.from_name || msg.from_email || msg.from || 'Unknown';
              const senderEmail = msg.from_email || msg.from || '';
              const recipient = msg.to_emails || msg.to || 'me';
              const bodyText = msg.body || msg.snippet || '';
              const detailsOpen = !!showDetails[msgId];

              return (
                <div
                  key={msgId}
                  className="rounded-xl border border-[#E7E4DC] bg-white overflow-hidden shadow-card"
                >
                  {/* Message Header Row */}
                  <div
                    onClick={() => toggleExpand(msgId)}
                    className="p-4 flex items-start justify-between gap-3 cursor-pointer hover:bg-[#F0EEE7]/50 transition"
                  >
                    <div className="flex items-center space-x-3 min-w-0">
                      <div className="w-8 h-8 rounded-full bg-[#F0EEE7] border border-[#E7E4DC] text-[#252821] font-semibold text-xs flex items-center justify-center flex-shrink-0">
                        {getInitials(senderName, senderEmail)}
                      </div>

                      <div className="min-w-0">
                        <div className="flex items-center space-x-2">
                          <span className="text-sm font-semibold text-[#252821] truncate">
                            {senderName}
                          </span>
                          {senderEmail && (
                            <span className="text-xs text-[#74766F] hidden sm:inline truncate">
                              &lt;{senderEmail}&gt;
                            </span>
                          )}
                        </div>

                        <div className="text-xs text-[#74766F] flex items-center gap-1.5 mt-0.5">
                          <span>to {recipient === 'me' ? 'me' : recipient}</span>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              setShowDetails((prev) => ({ ...prev, [msgId]: !prev[msgId] }));
                            }}
                            className="p-0.5 rounded hover:bg-[#F0EEE7] text-[#74766F]"
                            title="Details"
                          >
                            {detailsOpen ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                          </button>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center space-x-2 flex-shrink-0 text-right">
                      <span className="text-xs text-[#92938C] font-mono">
                        {formatDate(msg.date)}
                      </span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleExpand(msgId);
                        }}
                        className="text-[#74766F] hover:text-[#252821] p-0.5"
                      >
                        {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>

                  {/* Header Details Breakdown */}
                  {detailsOpen && (
                    <div className="mx-4 mb-3 p-3 rounded-lg bg-[#FBFAF7] border border-[#E7E4DC] text-xs text-[#74766F] space-y-1 font-mono">
                      <div className="flex">
                        <span className="w-16 text-[#92938C]">From:</span>
                        <span className="text-[#252821]">{senderName} &lt;{senderEmail}&gt;</span>
                      </div>
                      <div className="flex">
                        <span className="w-16 text-[#92938C]">To:</span>
                        <span className="text-[#252821]">{recipient}</span>
                      </div>
                      <div className="flex">
                        <span className="w-16 text-[#92938C]">Date:</span>
                        <span className="text-[#252821]">{formatDate(msg.date)}</span>
                      </div>
                    </div>
                  )}

                  {/* Message Body */}
                  {isExpanded && (
                    <div className="px-5 pb-5 pt-1 border-t border-[#E7E4DC] space-y-4">
                      <div className="text-sm text-[#252821] leading-relaxed whitespace-pre-wrap font-sans pt-2 select-text">
                        {bodyText}
                      </div>

                      <div className="pt-3 border-t border-[#E7E4DC]/60 flex items-center justify-end text-xs text-[#74766F]">
                        <button
                          onClick={() => handleCopyBody(bodyText, msgId)}
                          className="flex items-center space-x-1 text-[#74766F] hover:text-[#252821] transition"
                          title="Copy email body"
                        >
                          {copiedId === msgId ? (
                            <>
                              <Check className="w-3.5 h-3.5 text-[#23845B]" />
                              <span className="text-[#23845B] text-[11px]">Copied</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3.5 h-3.5" />
                              <span className="text-[11px]">Copy text</span>
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* AI Streaming Indicator */}
        {isAiStreaming && (
          <div className="p-4 rounded-xl bg-[#F0F4FF] border border-[#D0DBFF] flex items-center space-x-3 text-xs text-[#4263EB] shadow-card animate-pulse">
            <Sparkles className="w-4 h-4 animate-spin text-[#4263EB] flex-shrink-0" />
            <div className="flex-1">
              <span className="font-semibold">
                {aiStreamingAction === 'summary'
                  ? 'Generating Executive Summary...'
                  : aiStreamingAction === 'tasks'
                  ? 'Extracting Action Items & Deadlines...'
                  : aiStreamingAction === 'draft'
                  ? 'Drafting tone-matched reply with AI...'
                  : 'AI Assistant is processing your request...'}
              </span>
              <p className="text-[11px] text-[#5C7CFA] mt-0.5">
                Analyzing email context and synthesizing response...
              </p>
            </div>
          </div>
        )}

        {/* AI Executive Summary Card */}
        {aiSummary && (
          <div className="rounded-xl border border-[#D0DBFF] bg-white overflow-hidden shadow-card">
            <div className="px-4 py-3 bg-[#F0F4FF] border-b border-[#D0DBFF] flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <FileText className="w-4 h-4 text-[#4263EB]" />
                <span className="text-xs font-semibold text-[#252821]">Executive Summary</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-white text-[#4263EB] border border-[#D0DBFF] font-medium">
                  AI Generated
                </span>
              </div>
              <div className="flex items-center space-x-1.5">
                <button
                  onClick={() => handleCopySummary(aiSummary)}
                  className="h-7 px-2.5 rounded-md bg-white hover:bg-[#EAEFFF] border border-[#D0DBFF] text-xs text-[#4263EB] font-medium flex items-center gap-1 transition shadow-sm"
                  title="Copy summary"
                >
                  {summaryCopied ? (
                    <>
                      <Check className="w-3 h-3 text-[#23845B]" />
                      <span className="text-[11px] text-[#23845B]">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3 h-3" />
                      <span className="text-[11px]">Copy</span>
                    </>
                  )}
                </button>
                {onClearSummary && (
                  <button
                    onClick={onClearSummary}
                    className="h-7 w-7 rounded-md hover:bg-[#EAEFFF] text-[#74766F] hover:text-[#252821] flex items-center justify-center transition"
                    title="Dismiss summary"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
            <div className="p-4 bg-white text-xs text-[#252821] leading-relaxed select-text">
              {renderFormattedAiText(aiSummary)}
            </div>
          </div>
        )}

        {/* AI Extracted Tasks Card */}
        {aiTasksResult && (
          <div className="rounded-xl border border-[#DCFCE7] bg-white overflow-hidden shadow-card">
            <div className="px-4 py-3 bg-[#F0FDF4] border-b border-[#DCFCE7] flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <CheckSquare className="w-4 h-4 text-[#23845B]" />
                <span className="text-xs font-semibold text-[#252821]">Action Items & Tasks</span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-white text-[#23845B] border border-[#DCFCE7] font-medium">
                  Synced to Tasks
                </span>
              </div>
              <div className="flex items-center space-x-1.5">
                {onViewTasksTab && (
                  <button
                    onClick={onViewTasksTab}
                    className="h-7 px-2.5 rounded-md bg-[#23845B] hover:bg-[#1E724E] text-white text-xs font-medium flex items-center gap-1 transition shadow-sm"
                    title="View in Tasks tab"
                  >
                    <span>View in Tasks Tab</span>
                    <ExternalLink className="w-3 h-3" />
                  </button>
                )}
                {onClearTasks && (
                  <button
                    onClick={onClearTasks}
                    className="h-7 w-7 rounded-md hover:bg-[#DCFCE7] text-[#74766F] hover:text-[#252821] flex items-center justify-center transition"
                    title="Dismiss tasks card"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
            <div className="p-4 bg-white text-xs text-[#252821] leading-relaxed select-text">
              {renderFormattedAiText(aiTasksResult)}
            </div>
          </div>
        )}

        {/* AI Draft Proposal & Composer Surface */}
        {activeDraft && (
          <div className="pt-2">
            <DraftCard
              draft={activeDraft}
              onSendClick={onSendDraftClick || (() => {})}
              onSaveDraft={onSaveDraft || (() => {})}
              onImprove={onImproveDraft || ((instruction, draft) => onAskAi(instruction, draft, 'draft'))}
              onDiscard={onDiscardDraft}
            />
          </div>
        )}

        {/* AI Quick Actions & Reply Section */}
        <div className="pt-4 border-t border-[#E7E4DC] space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-[#74766F] uppercase tracking-wider">
              AI Assistant Actions
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            <button
              onClick={() =>
                onAskAi(
                  `Please compose a professional, friendly reply to: "${email.subject}". Keep it concise and clear.`,
                  undefined,
                  'draft'
                )
              }
              disabled={isAiStreaming}
              className="p-3.5 rounded-xl bg-white hover:bg-[#F0EEE7] border border-[#E7E4DC] text-left transition group disabled:opacity-50 shadow-card"
            >
              <div className="flex items-center space-x-2 text-xs font-semibold text-[#252821] mb-1">
                <Sparkles className="w-3.5 h-3.5 text-[#4263EB]" />
                <span>Draft Reply</span>
              </div>
              <p className="text-[11px] text-[#74766F] leading-normal">
                Generate a personalized, tone-matched response.
              </p>
            </button>

            <button
              onClick={() =>
                onAskAi(
                  `Extract any deadlines, meetings, or action items from email "${email.subject}". Add them as tasks.`,
                  undefined,
                  'tasks'
                )
              }
              disabled={isAiStreaming}
              className="p-3.5 rounded-xl bg-white hover:bg-[#F0EEE7] border border-[#E7E4DC] text-left transition group disabled:opacity-50 shadow-card"
            >
              <div className="flex items-center space-x-2 text-xs font-semibold text-[#252821] mb-1">
                <CheckSquare className="w-3.5 h-3.5 text-[#4263EB]" />
                <span>Extract Tasks</span>
              </div>
              <p className="text-[11px] text-[#74766F] leading-normal">
                Identify commitments and create actionable tasks.
              </p>
            </button>

            <button
              onClick={() =>
                onAskAi(
                  `Summarize what is inside this email ("${email.subject}"). Give me key points, dates, and discussion notes.`,
                  undefined,
                  'summary'
                )
              }
              disabled={isAiStreaming}
              className="p-3.5 rounded-xl bg-white hover:bg-[#F0EEE7] border border-[#E7E4DC] text-left transition group disabled:opacity-50 shadow-card"
            >
              <div className="flex items-center space-x-2 text-xs font-semibold text-[#252821] mb-1">
                <Clock className="w-3.5 h-3.5 text-[#23845B]" />
                <span>Summarize</span>
              </div>
              <p className="text-[11px] text-[#74766F] leading-normal">
                Get an executive summary of key discussion points.
              </p>
            </button>
          </div>

          {/* Custom Reply Prompt Area */}
          {showReplyBox ? (
            <div className="p-4 rounded-xl bg-white border border-[#E7E4DC] space-y-3 shadow-card">
              <div className="flex items-center justify-between text-xs text-[#74766F]">
                <span className="font-medium text-[#252821] flex items-center gap-1.5">
                  <Reply className="w-3.5 h-3.5 text-[#4263EB]" />
                  Reply to {email.from_name || email.from_email}
                </span>
                <button
                  onClick={() => {
                    setQuickReplyText('');
                    setShowReplyBox(false);
                  }}
                  className="text-[#74766F] hover:text-[#252821] text-xs transition"
                >
                  Cancel
                </button>
              </div>

              <textarea
                value={quickReplyText}
                onChange={(e) => setQuickReplyText(e.target.value)}
                placeholder="Give AI instructions (e.g. 'Politely decline and suggest next week', 'Accept meeting with enthusiasm')..."
                rows={3}
                className="w-full bg-[#FBFAF7] border border-[#E7E4DC] rounded-lg p-3 text-xs text-[#252821] placeholder-[#92938C] focus:bg-white focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20 transition resize-none leading-relaxed"
              />

              <div className="flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={() => {
                    const prompt = quickReplyText.trim()
                      ? `Please compose a reply to ${email.from_name || email.from_email} regarding "${email.subject}". Incorporate this guidance: "${quickReplyText}".`
                      : `Please compose a professional, friendly reply to: "${email.subject}". Keep it concise and clear.`;
                    onAskAi(prompt, undefined, 'draft');
                  }}
                  disabled={isAiStreaming}
                  className="h-9 px-3.5 rounded-lg bg-white hover:bg-[#F0EEE7] border border-[#E7E4DC] text-[#252821] text-xs font-medium flex items-center gap-1.5 transition disabled:opacity-50 shadow-sm"
                >
                  <Sparkles className="w-3.5 h-3.5 text-[#4263EB]" />
                  <span>Draft with AI</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    if (!quickReplyText.trim()) return;
                    onAskAi(`Send this reply to ${email.from_email}: "${quickReplyText}"`);
                  }}
                  disabled={!quickReplyText.trim() || isAiStreaming}
                  className="h-9 px-4 rounded-lg bg-[#4263EB] hover:bg-[#3451D1] text-white text-xs font-medium flex items-center gap-1.5 transition disabled:opacity-50 shadow-sm"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>Send</span>
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowReplyBox(true)}
              className="h-9 px-3.5 rounded-lg bg-white hover:bg-[#F0EEE7] border border-[#E7E4DC] text-xs text-[#74766F] hover:text-[#252821] transition flex items-center gap-1.5 shadow-sm"
            >
              <Reply className="w-3.5 h-3.5 text-[#4263EB]" />
              <span>Write custom instructions or prompt...</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
