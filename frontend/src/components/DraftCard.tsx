import React, { useState, useEffect } from 'react';
import {
  Edit3,
  Sparkles,
  Send,
  Save,
  CheckCircle2,
  AlertTriangle,
  ChevronDown,
  ShieldAlert,
  Info,
  RefreshCw,
  Paperclip,
  FileText,
  Check,
  X,
} from 'lucide-react';
import { DraftCardData, QualityCheckResult, AttachmentSuggestion } from '../types';
import { api } from '../api';

interface DraftCardProps {
  draft: DraftCardData;
  onSendClick: (draft: DraftCardData) => void;
  onSaveDraft: (draft: DraftCardData) => Promise<void> | void;
  onImprove: (instruction: string, draft?: DraftCardData) => void;
  onDiscard?: () => void;
}

export const DraftCard: React.FC<DraftCardProps> = ({
  draft,
  onSendClick,
  onSaveDraft,
  onImprove,
  onDiscard,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [justChecked, setJustChecked] = useState(false);
  const [checkFeedback, setCheckFeedback] = useState<{
    status: 'PASS' | 'WARNING' | 'BLOCK' | 'ERROR';
    message: string;
    timestamp: string;
  } | null>(null);
  const [isSaved, setIsSaved] = useState(false);
  const [toEmail, setToEmail] = useState(draft.to_email || '');
  const [subjectText, setSubjectText] = useState(draft.subject || '');
  const [bodyText, setBodyText] = useState(draft.body || '');
  const [showImproveMenu, setShowImproveMenu] = useState(false);
  const [qualityCheck, setQualityCheck] = useState<QualityCheckResult | undefined>(
    draft.quality_check
  );
  const [learnedBanner, setLearnedBanner] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<AttachmentSuggestion[]>(
    draft.attachment_suggestions || []
  );
  const [selectedAttachments, setSelectedAttachments] = useState<AttachmentSuggestion[]>(
    Array.isArray(draft.selected_attachments)
      ? draft.selected_attachments
      : (draft.attachment_suggestions || []).filter((s) => s.is_selected)
  );

  useEffect(() => {
    setToEmail(draft.to_email || '');
    setSubjectText(draft.subject || '');
    setBodyText(draft.body || '');
    setQualityCheck(draft.quality_check);
    setSuggestions(draft.attachment_suggestions || []);

    const initialSelected = Array.isArray(draft.selected_attachments)
      ? draft.selected_attachments
      : (draft.attachment_suggestions || []).filter((s) => s.is_selected);
    setSelectedAttachments(initialSelected);
    draft.selected_attachments = initialSelected;

    if (!draft.attachment_suggestions || draft.attachment_suggestions.length === 0) {
      if (draft.body || draft.subject) {
        api.suggestAttachments(draft.body, draft.subject)
          .then((res) => {
            if (res && res.suggestions && res.suggestions.length > 0) {
              setSuggestions(res.suggestions);
              if (!Array.isArray(draft.selected_attachments)) {
                const autoSelected = res.suggestions.filter((s) => s.is_selected);
                setSelectedAttachments(autoSelected);
                draft.selected_attachments = autoSelected;
              }
            }
          })
          .catch(() => {});
      }
    }
  }, [draft.id, draft.body, draft.to_email, draft.subject]);

  const handleToggleAttachment = (sug: AttachmentSuggestion) => {
    let next: AttachmentSuggestion[];
    const isAlready = selectedAttachments.some((a) => a.file_id === sug.file_id);
    if (isAlready) {
      next = selectedAttachments.filter((a) => a.file_id !== sug.file_id);
      sug.is_selected = false;
    } else {
      next = [...selectedAttachments, sug];
      sug.is_selected = true;
    }
    setSelectedAttachments(next);
    draft.selected_attachments = next;

    setSuggestions((prev) =>
      prev.map((item) =>
        item.file_id === sug.file_id ? { ...item, is_selected: !isAlready } : item
      )
    );

    if (draft.attachment_suggestions) {
      draft.attachment_suggestions = draft.attachment_suggestions.map((item) =>
        item.file_id === sug.file_id ? { ...item, is_selected: !isAlready } : item
      );
    }

    runQualityCheck(
      toEmail.trim(),
      subjectText.trim(),
      bodyText.trim(),
      next.map((a) => a.file_path)
    );
  };

  const improveOptions = [
    { label: 'Make concise', prompt: 'Make this reply more concise and to the point.' },
    { label: 'Make formal', prompt: 'Rewrite this with a more formal, professional tone.' },
    { label: 'Make friendly', prompt: 'Make this tone warmer and more approachable.' },
    { label: 'Fix grammar & polish', prompt: 'Polish grammar and improve vocabulary clarity.' },
  ];

  const runQualityCheck = async (
    email: string,
    subj: string,
    body: string,
    attachments?: string[]
  ) => {
    setIsValidating(true);
    setCheckFeedback(null);
    const minDelay = new Promise((resolve) => setTimeout(resolve, 350));
    try {
      const attachedFiles = attachments || selectedAttachments.map((a) => a.file_path);
      const [qc] = await Promise.all([
        api.validateDraft({
          to_email: email,
          subject: subj,
          body: body,
          thread_id: draft.thread_id,
          attached_files: attachedFiles,
        }),
        minDelay,
      ]);

      if (qc && Array.isArray(qc.checks)) {
        setQualityCheck(qc);
        draft.quality_check = qc;
        draft.warnings = qc.checks
          .filter((c) => c && (c.severity === 'WARNING' || c.severity === 'BLOCK'))
          .map((c) => c.message);

        const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        setJustChecked(true);
        setTimeout(() => setJustChecked(false), 3000);

        if (qc.status === 'PASS') {
          setCheckFeedback({
            status: 'PASS',
            message: `Quality checks passed (0 issues detected)`,
            timestamp: now,
          });
        } else if (qc.status === 'WARNING') {
          const warnCount = qc.checks.filter((c) => c.severity === 'WARNING').length;
          setCheckFeedback({
            status: 'WARNING',
            message: `Quality check warning (${warnCount} recommendation${warnCount > 1 ? 's' : ''})`,
            timestamp: now,
          });
        } else if (qc.status === 'BLOCK') {
          const blockCount = qc.checks.filter((c) => c.severity === 'BLOCK').length;
          setCheckFeedback({
            status: 'BLOCK',
            message: `Blocking issue detected (${blockCount} critical issue${blockCount > 1 ? 's' : ''})`,
            timestamp: now,
          });
        }
      }
    } catch (e: any) {
      console.error('Validation error:', e);
      setCheckFeedback({
        status: 'ERROR',
        message: `Validation service error: ${e.message || 'unknown'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      });
    } finally {
      setIsValidating(false);
    }
  };

  const handleSaveEdit = async () => {
    draft.to_email = toEmail.trim();
    draft.subject = subjectText.trim();
    draft.body = bodyText.trim();
    draft.selected_attachments = selectedAttachments;

    if (draft.id) {
      try {
        await api.updateDraft(draft.id, {
          body: draft.body,
          subject: draft.subject,
        });
        setLearnedBanner('Edit recorded: personalization engine learned your preferred style.');
        setTimeout(() => setLearnedBanner(null), 5000);
      } catch (err) {
        console.error('Failed to update draft:', err);
      }
    }

    setIsEditing(false);
    runQualityCheck(draft.to_email, draft.subject, draft.body);
  };

  const handleSaveClick = async () => {
    setIsSaving(true);
    try {
      const updatedDraft: DraftCardData = {
        ...draft,
        to_email: toEmail.trim(),
        subject: subjectText.trim(),
        body: bodyText.trim(),
        selected_attachments: selectedAttachments,
        quality_check: qualityCheck,
      };
      await onSaveDraft(updatedDraft);
      setIsSaved(true);
      setTimeout(() => setIsSaved(false), 3000);
    } catch (e) {
      console.error(e);
    } finally {
      setIsSaving(false);
    }
  };

  const isBlocked =
    qualityCheck?.status === 'BLOCK' ||
    !toEmail.trim() ||
    !bodyText.trim();

  const renderStatusBadge = () => {
    const status = qualityCheck?.status;
    if (status === 'BLOCK') {
      return (
        <span className="text-[11px] px-2 py-0.5 rounded bg-[#FDF2F2] text-[#C24141] border border-[#F8D7D7] flex items-center gap-1 font-medium">
          <ShieldAlert className="w-3 h-3" />
          Blocked
        </span>
      );
    }
    if (status === 'WARNING') {
      return (
        <span className="text-[11px] px-2 py-0.5 rounded bg-[#FEF8ED] text-[#A66A12] border border-[#FCE6BE] flex items-center gap-1 font-medium">
          <AlertTriangle className="w-3 h-3" />
          Review Recommended
        </span>
      );
    }
    return (
      <span className="text-[11px] px-2 py-0.5 rounded bg-[#F0FDF4] text-[#23845B] border border-[#DCFCE7] flex items-center gap-1 font-medium">
        <CheckCircle2 className="w-3 h-3" />
        Quality Passed
      </span>
    );
  };

  return (
    <div className="my-4 rounded-xl bg-white border border-[#E7E4DC] p-5 space-y-4 shadow-card select-none">
      {/* Draft Header & Meta */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#E7E4DC] pb-3">
        <div className="flex items-center space-x-2.5">
          <span className="text-xs font-semibold text-[#252821] tracking-tight">
            Email Draft
          </span>
          {renderStatusBadge()}
        </div>

        <div className="flex items-center space-x-3">
          {!isEditing && (
            <div className="text-xs text-[#74766F] flex items-center gap-1.5">
              <span>To:</span>
              <span
                className={`font-medium ${
                  toEmail ? 'text-[#252821]' : 'text-[#C24141] font-semibold'
                }`}
              >
                {toEmail || 'Missing recipient (click Edit)'}
              </span>
            </div>
          )}

          {onDiscard && (
            <button
              onClick={onDiscard}
              className="p-1 rounded-md text-[#74766F] hover:text-[#C24141] hover:bg-[#FDF2F2] transition"
              title="Discard this draft"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Style Learning Feedback Banner */}
      {learnedBanner && (
        <div className="p-2.5 rounded-lg bg-[#EAEFFF] border border-[#D0DBFF] text-[#4263EB] text-xs flex items-center gap-2">
          <Sparkles className="w-3.5 h-3.5 flex-shrink-0" />
          <span>{learnedBanner}</span>
        </div>
      )}

      {/* Draft Content: Editing Mode vs Display Mode */}
      {isEditing ? (
        <div className="space-y-3">
          <div>
            <label className="text-[11px] text-[#74766F] uppercase tracking-wider block mb-1 font-medium">
              Recipient:
            </label>
            <input
              type="email"
              value={toEmail}
              onChange={(e) => setToEmail(e.target.value)}
              placeholder="recipient@example.com"
              className="w-full h-9 bg-white border border-[#E7E4DC] rounded-lg px-3 text-xs text-[#252821] focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20"
            />
          </div>
          <div>
            <label className="text-[11px] text-[#74766F] uppercase tracking-wider block mb-1 font-medium">
              Subject:
            </label>
            <input
              type="text"
              value={subjectText}
              onChange={(e) => setSubjectText(e.target.value)}
              placeholder="Email subject..."
              className="w-full h-9 bg-white border border-[#E7E4DC] rounded-lg px-3 text-xs text-[#252821] focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20"
            />
          </div>
          <div>
            <label className="text-[11px] text-[#74766F] uppercase tracking-wider block mb-1 font-medium">
              Body:
            </label>
            <textarea
              value={bodyText}
              onChange={(e) => setBodyText(e.target.value)}
              rows={6}
              className="w-full bg-white border border-[#E7E4DC] rounded-lg p-3 text-xs text-[#252821] focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20 resize-y leading-relaxed font-sans"
            />
          </div>
          <div className="flex justify-end space-x-2 pt-1">
            <button
              onClick={() => {
                setToEmail(draft.to_email || '');
                setSubjectText(draft.subject || '');
                setBodyText(draft.body || '');
                setIsEditing(false);
              }}
              className="h-8 px-3 text-xs rounded-lg bg-white border border-[#E7E4DC] text-[#74766F] hover:text-[#252821] hover:bg-[#F0EEE7]"
            >
              Cancel
            </button>
            <button
              onClick={handleSaveEdit}
              className="h-8 px-3 text-xs rounded-lg bg-[#4263EB] text-white font-medium hover:bg-[#3451D1] transition shadow-sm"
            >
              Done Editing
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {/* Subject Line */}
          <div className="text-xs">
            <span className="text-[#74766F]">Subject: </span>
            <span className="font-semibold text-[#252821]">
              {subjectText || <span className="text-[#A66A12] italic">(No subject)</span>}
            </span>
          </div>

          {/* Email Body Draft Surface */}
          <div className="p-4 rounded-lg bg-[#FBFAF7] border border-[#E7E4DC] text-xs text-[#252821] whitespace-pre-wrap leading-relaxed font-sans select-text">
            {bodyText}
          </div>
        </div>
      )}

      {/* Suggested Attachments Section */}
      {suggestions.length > 0 && (
        <div className="p-3.5 rounded-lg bg-[#FBFAF7] border border-[#E7E4DC] space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Paperclip className="w-3.5 h-3.5 text-[#74766F]" />
              <span className="text-xs font-semibold text-[#252821]">
                Suggested attachments
              </span>
            </div>
            {selectedAttachments.length > 0 && (
              <span className="text-[10px] font-mono text-[#23845B] bg-[#F0FDF4] border border-[#DCFCE7] px-2 py-0.5 rounded font-medium">
                {selectedAttachments.length} selected
              </span>
            )}
          </div>

          <p className="text-[11px] text-[#74766F] leading-normal">
            Attachments require your approval before sending. Only checked files will be attached:
          </p>

          <div className="space-y-1.5 pt-0.5">
            {suggestions.map((sug) => {
              const isSelected = selectedAttachments.some((a) => a.file_id === sug.file_id);
              return (
                <div
                  key={sug.file_id}
                  onClick={() => handleToggleAttachment(sug)}
                  className={`flex items-center justify-between p-2.5 rounded-lg border text-xs cursor-pointer transition select-none ${
                    isSelected
                      ? 'bg-[#EAEFFF] border-[#D0DBFF] text-[#252821]'
                      : 'bg-white border-[#E7E4DC] text-[#74766F] hover:border-[#D6D2C4] hover:bg-[#F0EEE7]'
                  }`}
                >
                  <div className="flex items-center space-x-3 min-w-0">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => {}}
                      className="w-3.5 h-3.5 rounded bg-white border-[#E7E4DC] text-[#4263EB] focus:ring-0 cursor-pointer pointer-events-none"
                    />
                    <FileText
                      className={`w-4 h-4 flex-shrink-0 ${
                        isSelected ? 'text-[#4263EB]' : 'text-[#74766F]'
                      }`}
                    />
                    <div className="truncate min-w-0">
                      <span
                        className="font-medium text-xs truncate block text-[#252821]"
                        title={sug.filename}
                      >
                        {sug.filename}
                      </span>
                      {sug.reason && (
                        <span className="text-[10px] text-[#74766F] truncate block">
                          {sug.reason}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Quality Checks / Warnings */}
      {qualityCheck && Array.isArray(qualityCheck.checks) && qualityCheck.checks.length > 0 && (
        <div className="space-y-1.5">
          {qualityCheck.checks.map((check, idx) => {
            if (check.severity === 'BLOCK') {
              return (
                <div
                  key={idx}
                  className="flex items-start space-x-2 p-2.5 rounded-lg bg-[#FDF2F2] border border-[#F8D7D7] text-[#C24141] text-xs"
                >
                  <ShieldAlert className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <span className="font-semibold uppercase text-[10px] mr-1.5">
                      Blocking:
                    </span>
                    <span>{check.message}</span>
                  </div>
                </div>
              );
            }
            if (check.severity === 'WARNING') {
              return (
                <div
                  key={idx}
                  className="flex items-start space-x-2 p-2.5 rounded-lg bg-[#FEF8ED] border border-[#FCE6BE] text-[#A66A12] text-xs"
                >
                  <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <span className="font-semibold uppercase text-[10px] mr-1.5">
                      Notice:
                    </span>
                    <span>{check.message}</span>
                    {check.code === 'UNRESOLVED_PLACEHOLDER' && !isEditing && (
                      <button
                        onClick={() => setIsEditing(true)}
                        className="ml-2 underline font-medium hover:text-[#252821]"
                      >
                        Edit to fix
                      </button>
                    )}
                  </div>
                </div>
              );
            }
            return (
              <div
                key={idx}
                className="flex items-start space-x-2 p-2 rounded-lg bg-[#FBFAF7] border border-[#E7E4DC] text-[#74766F] text-xs"
              >
                <Info className="w-3.5 h-3.5 flex-shrink-0 mt-0.5 text-[#74766F]" />
                <div className="flex-1">
                  <span>{check.message}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Re-check Status Notice Banner */}
      {checkFeedback && (
        <div
          className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs border transition ${
            checkFeedback.status === 'PASS'
              ? 'bg-[#F0FDF4] border-[#DCFCE7] text-[#23845B]'
              : checkFeedback.status === 'WARNING'
              ? 'bg-[#FEF8ED] border-[#FCE6BE] text-[#A66A12]'
              : 'bg-[#FDF2F2] border-[#F8D7D7] text-[#C24141]'
          }`}
        >
          <div className="flex items-center space-x-2">
            {checkFeedback.status === 'PASS' ? (
              <CheckCircle2 className="w-3.5 h-3.5 flex-shrink-0" />
            ) : checkFeedback.status === 'WARNING' ? (
              <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
            ) : (
              <ShieldAlert className="w-3.5 h-3.5 flex-shrink-0" />
            )}
            <span>{checkFeedback.message}</span>
          </div>
          <span className="text-[10px] font-mono text-[#74766F] ml-2 flex-shrink-0">
            {checkFeedback.timestamp}
          </span>
        </div>
      )}

      {/* Actions Toolbar */}
      <div className="pt-3 border-t border-[#E7E4DC] flex items-center justify-between flex-wrap gap-2">
        {/* Left Secondary Actions */}
        <div className="flex items-center gap-1.5 flex-wrap relative">
          {/* Edit */}
          <button
            onClick={() => setIsEditing(!isEditing)}
            className="h-9 px-3 rounded-lg text-xs font-medium bg-white hover:bg-[#F0EEE7] border border-[#E7E4DC] text-[#252821] flex items-center gap-1.5 transition whitespace-nowrap shadow-sm"
          >
            <Edit3 className="w-3.5 h-3.5 text-[#74766F]" />
            <span>{isEditing ? 'Close Edit' : 'Edit'}</span>
          </button>

          {/* Re-check */}
          <button
            onClick={() => runQualityCheck(toEmail.trim(), subjectText.trim(), bodyText.trim())}
            disabled={isValidating}
            className={`h-9 px-3 rounded-lg text-xs font-medium border flex items-center gap-1.5 transition whitespace-nowrap shadow-sm ${
              justChecked
                ? 'bg-[#F0FDF4] border-[#DCFCE7] text-[#23845B]'
                : 'bg-white hover:bg-[#F0EEE7] border-[#E7E4DC] text-[#252821]'
            }`}
            title="Re-run automated quality & safety checks"
          >
            {justChecked ? (
              <Check className="w-3.5 h-3.5 text-[#23845B]" />
            ) : (
              <RefreshCw
                className={`w-3.5 h-3.5 text-[#74766F] ${isValidating ? 'animate-spin' : ''}`}
              />
            )}
            <span>{isValidating ? 'Checking...' : justChecked ? 'Checked' : 'Re-check'}</span>
          </button>

          {/* Improve Dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowImproveMenu(!showImproveMenu)}
              className="h-9 px-3 rounded-lg text-xs font-medium bg-white hover:bg-[#F0EEE7] border border-[#E7E4DC] text-[#252821] flex items-center gap-1.5 transition whitespace-nowrap shadow-sm"
            >
              <Sparkles className="w-3.5 h-3.5 text-[#4263EB]" />
              <span>Improve</span>
              <ChevronDown className="w-3 h-3 text-[#74766F] ml-0.5" />
            </button>

            {showImproveMenu && (
              <div className="absolute left-0 bottom-full mb-1.5 w-48 bg-white border border-[#E7E4DC] rounded-lg shadow-dropdown py-1 z-30">
                {improveOptions.map((opt) => (
                  <button
                    key={opt.label}
                    onClick={() => {
                      setShowImproveMenu(false);
                      onImprove(opt.prompt, {
                        ...draft,
                        to_email: toEmail.trim(),
                        subject: subjectText.trim(),
                        body: bodyText.trim(),
                      });
                    }}
                    className="w-full text-left px-3 py-2 text-xs text-[#74766F] hover:text-[#252821] hover:bg-[#F0EEE7] transition whitespace-nowrap"
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Save Draft */}
          <button
            onClick={handleSaveClick}
            disabled={isSaving}
            className={`h-9 px-3 rounded-lg text-xs font-medium border flex items-center gap-1.5 transition whitespace-nowrap shadow-sm ${
              isSaved
                ? 'bg-[#F0FDF4] border-[#DCFCE7] text-[#23845B]'
                : 'bg-white hover:bg-[#F0EEE7] border-[#E7E4DC] text-[#252821]'
            }`}
          >
            {isSaved ? (
              <>
                <Check className="w-3.5 h-3.5 text-[#23845B]" />
                <span>Saved</span>
              </>
            ) : isSaving ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#74766F]" />
                <span>Saving...</span>
              </>
            ) : (
              <>
                <Save className="w-3.5 h-3.5 text-[#74766F]" />
                <span>Save Draft</span>
              </>
            )}
          </button>
        </div>

        {/* Right Primary Action: Send */}
        <div className="flex items-center space-x-2">
          {isBlocked && (
            <span className="text-[11px] text-[#C24141] hidden sm:inline">
              Resolve blocking issues before sending
            </span>
          )}
          <button
            onClick={() =>
              !isBlocked &&
              onSendClick({
                ...draft,
                to_email: toEmail.trim(),
                subject: subjectText.trim(),
                body: bodyText.trim(),
                quality_check: qualityCheck,
                selected_attachments: selectedAttachments,
              })
            }
            disabled={isBlocked}
            className={`h-9 px-4 rounded-lg text-xs font-semibold flex items-center gap-2 transition whitespace-nowrap ${
              isBlocked
                ? 'bg-[#F0EEE7] text-[#92938C] border border-[#E7E4DC] cursor-not-allowed opacity-60'
                : 'bg-[#4263EB] hover:bg-[#3451D1] text-white shadow-sm'
            }`}
          >
            <Send className="w-3.5 h-3.5" />
            <span>Send</span>
          </button>
        </div>
      </div>
    </div>
  );
};
