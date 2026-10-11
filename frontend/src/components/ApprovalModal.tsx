import React, { useState } from 'react';
import { ShieldCheck, AlertCircle, X, Send, ShieldAlert, AlertTriangle, Paperclip } from 'lucide-react';
import { DraftCardData } from '../types';

interface ApprovalModalProps {
  draft: DraftCardData;
  isOpen: boolean;
  onClose: () => void;
  onApproveAndSend: (draft: DraftCardData) => Promise<void>;
}

export const ApprovalModal: React.FC<ApprovalModalProps> = ({
  draft,
  isOpen,
  onClose,
  onApproveAndSend,
}) => {
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const isBlocked =
    draft.quality_check?.status === 'BLOCK' ||
    !draft.to_email?.trim() ||
    !draft.body?.trim();

  const handleSend = async () => {
    if (isBlocked) {
      setError('Cannot dispatch email: draft contains blocking quality issues.');
      return;
    }
    setIsSending(true);
    setError(null);
    try {
      await onApproveAndSend(draft);
      onClose();
    } catch (err: any) {
      const msg = err.message || 'Failed to send email';
      setError(msg);
    } finally {
      setIsSending(false);
    }
  };

  const formatErrorMessage = (raw: string) => {
    if (raw.includes('Quota exceeded') || raw.includes('rateLimitExceeded')) {
      return 'Gmail API quota limit reached. Please wait a few moments before attempting to send again.';
    }
    if (raw.includes('invalid_grant')) {
      return 'Gmail authorization expired. Please re-authenticate your Gmail connection.';
    }
    return raw;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm select-none">
      <div className="w-full max-w-lg bg-white border border-[#E7E4DC] rounded-xl shadow-dropdown overflow-hidden flex flex-col max-h-[90vh]">
        {/* Modal Header */}
        <div className="px-5 py-4 border-b border-[#E7E4DC] flex items-center justify-between bg-[#FBFAF7]">
          <div className="flex items-center space-x-2.5">
            <ShieldCheck className="w-4 h-4 text-[#4263EB]" />
            <h2 className="text-sm font-semibold text-[#252821]">
              Review and Approve Email Dispatch
            </h2>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-lg text-[#74766F] hover:text-[#252821] hover:bg-[#F0EEE7] transition"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-5 space-y-4 text-xs text-[#74766F] overflow-y-auto flex-1">
          <div className="p-3 rounded-lg bg-[#FBFAF7] border border-[#E7E4DC] text-[#74766F] leading-relaxed">
            This email will be dispatched immediately via your connected Gmail account. Please review recipient, subject, and content below.
          </div>

          <div className="space-y-3">
            <div>
              <span className="text-[#74766F] font-medium block mb-0.5">Recipient:</span>
              <p className="text-[#252821] font-medium text-xs">
                {draft.to_email || '(Missing recipient)'}
              </p>
            </div>

            <div>
              <span className="text-[#74766F] font-medium block mb-0.5">Subject:</span>
              <p className="text-[#252821] font-medium text-xs">
                {draft.subject || '(No subject)'}
              </p>
            </div>

            <div>
              <span className="text-[#74766F] font-medium block mb-0.5">Message Body:</span>
              <div className="p-3.5 rounded-lg bg-[#FBFAF7] border border-[#E7E4DC] max-h-48 overflow-y-auto whitespace-pre-wrap font-sans text-[#252821] leading-relaxed text-xs select-text">
                {draft.body}
              </div>
            </div>

            {draft.selected_attachments && draft.selected_attachments.length > 0 && (
              <div>
                <span className="text-[#74766F] font-medium block mb-1">
                  Approved Attachments ({draft.selected_attachments.length}):
                </span>
                <div className="flex flex-wrap gap-1.5">
                  {draft.selected_attachments.map((att, i) => (
                    <div
                      key={i}
                      className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-white border border-[#E7E4DC] text-[#252821] text-xs shadow-sm"
                    >
                      <Paperclip className="w-3.5 h-3.5 text-[#74766F]" />
                      <span className="truncate max-w-[200px]">{att.filename}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Quality check alerts */}
          {draft.quality_check && Array.isArray(draft.quality_check.checks) && draft.quality_check.checks.length > 0 && (
            <div className="space-y-1.5 pt-1">
              {draft.quality_check.checks.map((chk, i) => (
                <div
                  key={i}
                  className={`flex items-start space-x-2 p-2.5 rounded-lg text-xs ${
                    chk.severity === 'BLOCK'
                      ? 'bg-[#FDF2F2] border border-[#F8D7D7] text-[#C24141]'
                      : chk.severity === 'WARNING'
                      ? 'bg-[#FEF8ED] border border-[#FCE6BE] text-[#A66A12]'
                      : 'bg-white border border-[#E7E4DC] text-[#74766F]'
                  }`}
                >
                  {chk.severity === 'BLOCK' ? (
                    <ShieldAlert className="w-4 h-4 text-[#C24141] flex-shrink-0 mt-0.5" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 text-[#A66A12] flex-shrink-0 mt-0.5" />
                  )}
                  <span>{chk.message}</span>
                </div>
              ))}
            </div>
          )}

          {error && (
            <div className="flex items-start space-x-2.5 p-3 rounded-lg bg-[#FDF2F2] border border-[#F8D7D7] text-[#C24141] text-xs break-words">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <span className="font-semibold block mb-0.5">Send Failed</span>
                <p className="leading-relaxed">{formatErrorMessage(error)}</p>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer Actions */}
        <div className="px-5 py-3.5 border-t border-[#E7E4DC] bg-[#FBFAF7] flex items-center justify-end space-x-2">
          <button
            onClick={onClose}
            disabled={isSending}
            className="h-9 px-3.5 rounded-lg text-xs font-medium text-[#74766F] hover:text-[#252821] hover:bg-[#F0EEE7] border border-[#E7E4DC] bg-white transition disabled:opacity-50 shadow-sm"
          >
            Cancel / Edit
          </button>
          <button
            onClick={handleSend}
            disabled={isSending || isBlocked}
            className={`h-9 px-4 rounded-lg text-xs font-medium flex items-center gap-2 transition shadow-sm ${
              isBlocked
                ? 'bg-[#F0EEE7] text-[#92938C] border border-[#E7E4DC] cursor-not-allowed opacity-50'
                : 'bg-[#4263EB] hover:bg-[#3451D1] text-white'
            }`}
          >
            <Send className="w-3.5 h-3.5" />
            <span>{isSending ? 'Sending...' : 'Approve & Send Now'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
