import React from 'react';
import { Search, ShieldAlert, Clock, Reply } from 'lucide-react';
import { Email } from '../types';

interface EmailListProps {
  emails: Email[];
  selectedEmail: Email | null;
  onSelectEmail: (email: Email) => void;
  filterCategory: string;
  setFilterCategory: (category: string) => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  unreadOnly: boolean;
  setUnreadOnly: (unread: boolean) => void;
  needsReplyOnly: boolean;
  setNeedsReplyOnly: (needsReply: boolean) => void;
  loading: boolean;
}

export const EmailList: React.FC<EmailListProps> = ({
  emails,
  selectedEmail,
  onSelectEmail,
  filterCategory,
  setFilterCategory,
  searchQuery,
  setSearchQuery,
  unreadOnly,
  setUnreadOnly,
  needsReplyOnly,
  setNeedsReplyOnly,
  loading,
}) => {
  const categories = ['All', 'Job', 'College', 'Work', 'Personal', 'Newsletter', 'Finance'];

  const getCleanSenderName = (name?: string, email?: string) => {
    if (!name && !email) return 'Unknown Sender';
    const raw = name || email || '';
    // Strip surrounding quotes
    const unquoted = raw.replace(/^["']|["']$/g, '').trim();
    // If name is in the format "First Last <email@domain.com>", extract First Last
    const match = unquoted.match(/^([^<]+)<[^>]+>$/);
    if (match && match[1].trim()) {
      return match[1].trim();
    }
    return unquoted;
  };

  const decodeHtmlEntities = (text?: string) => {
    if (!text) return '';
    return text
      .replace(/&#39;/g, "'")
      .replace(/&quot;/g, '"')
      .replace(/&amp;/g, '&')
      .replace(/&lt;/g, '<')
      .replace(/&gt;/g, '>')
      .replace(/&nbsp;/g, ' ');
  };

  const formatDate = (dateStr: string) => {
    try {
      const d = new Date(dateStr);
      if (isNaN(d.getTime())) return dateStr;
      const now = new Date();
      const isToday =
        d.getDate() === now.getDate() &&
        d.getMonth() === now.getMonth() &&
        d.getFullYear() === now.getFullYear();
      if (isToday) {
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      }
      return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="flex flex-col h-full bg-[#FBFAF7] w-full select-none">
      {/* Search Input Bar */}
      <div className="p-3.5 border-b border-[#E7E4DC] space-y-2.5 flex-shrink-0 bg-white">
        <div className="relative">
          <Search className="w-4 h-4 text-[#74766F] absolute left-3 top-2.5 pointer-events-none" />
          <input
            type="text"
            placeholder="Search emails..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full h-9 bg-white border border-[#E7E4DC] rounded-lg pl-9 pr-3 text-xs text-[#252821] placeholder-[#92938C] focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20 transition"
          />
        </div>

        {/* Filter Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 scrollbar-none">
          <button
            onClick={() => setUnreadOnly(!unreadOnly)}
            className={`h-7 px-2.5 rounded-md text-xs font-medium border transition whitespace-nowrap ${
              unreadOnly
                ? 'bg-[#EAEFFF] text-[#4263EB] border-[#D0DBFF]'
                : 'bg-white text-[#74766F] border-[#E7E4DC] hover:bg-[#F0EEE7] hover:text-[#252821]'
            }`}
          >
            Unread
          </button>
          <button
            onClick={() => setNeedsReplyOnly(!needsReplyOnly)}
            className={`h-7 px-2.5 rounded-md text-xs font-medium border transition whitespace-nowrap ${
              needsReplyOnly
                ? 'bg-[#FEF3C7] text-[#A66A12] border-[#FDE68A]'
                : 'bg-white text-[#74766F] border-[#E7E4DC] hover:bg-[#F0EEE7] hover:text-[#252821]'
            }`}
          >
            Needs Reply
          </button>
          {categories.map((cat) => {
            const isSelected =
              (cat === 'All' && !filterCategory) || filterCategory === cat.toLowerCase();
            return (
              <button
                key={cat}
                onClick={() => setFilterCategory(cat === 'All' ? '' : cat.toLowerCase())}
                className={`h-7 px-2.5 rounded-md text-xs font-medium border transition whitespace-nowrap ${
                  isSelected
                    ? 'bg-[#EAEFFF] text-[#4263EB] border-[#D0DBFF] font-semibold'
                    : 'bg-white text-[#74766F] border-[#E7E4DC] hover:bg-[#F0EEE7] hover:text-[#252821]'
                }`}
              >
                {cat}
              </button>
            );
          })}
        </div>
      </div>

      {/* List Header Count */}
      <div className="px-4 py-2 border-b border-[#E7E4DC] bg-[#F7F5F0] flex items-center justify-between text-[11px] font-medium text-[#74766F] flex-shrink-0">
        <span className="uppercase tracking-wider">Messages</span>
        <span className="font-mono text-[#92938C]">{emails.length} total</span>
      </div>

      {/* Email Feed */}
      <div className="flex-1 overflow-y-auto divide-y divide-[#E7E4DC]">
        {loading ? (
          <div className="p-12 text-center text-[#74766F] text-xs">
            <div className="inline-block animate-spin rounded-full h-5 w-5 border-2 border-[#4263EB] border-t-transparent mb-2" />
            <p>Loading emails...</p>
          </div>
        ) : emails.length === 0 ? (
          <div className="p-12 text-center text-[#74766F] text-xs space-y-1">
            <p className="font-medium text-[#252821]">No emails found</p>
            <p className="text-[#92938C]">Try adjusting filters or sync recent messages.</p>
          </div>
        ) : (
          emails.map((email) => {
            const isSelected = selectedEmail?.message_id === email.message_id;
            const isUnread = email.is_read === 0;
            const isHighPriority =
              email.priority?.toLowerCase() === 'urgent' ||
              email.priority?.toLowerCase() === 'high';
            const isMediumPriority = email.priority?.toLowerCase() === 'medium';

            return (
              <div
                key={email.message_id}
                onClick={() => onSelectEmail(email)}
                className={`px-4 py-3 cursor-pointer transition-colors relative flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-[#E7E4DC] ${
                  isSelected
                    ? 'bg-[#F0F4FF] border-l-2 border-[#4263EB]'
                    : isUnread
                    ? 'bg-white hover:bg-[#F0EEE7] border-l-2 border-[#4263EB]'
                    : 'bg-[#FBFAF7] hover:bg-[#F0EEE7] border-l-2 border-transparent'
                }`}
              >
                {/* Left: Sender & Unread Dot */}
                <div className="flex items-center gap-2.5 w-32 sm:w-36 md:w-40 lg:w-48 flex-shrink-0 min-w-0">
                  <span
                    className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      isUnread ? 'bg-[#4263EB]' : 'bg-transparent'
                    }`}
                    title={isUnread ? 'Unread' : 'Read'}
                  />
                  <span
                    className={`text-xs truncate ${
                      isUnread
                        ? 'font-semibold text-[#252821]'
                        : 'font-medium text-[#74766F]'
                    }`}
                  >
                    {getCleanSenderName(email.from_name, email.from_email)}
                  </span>
                </div>

                {/* Center: Subject, Snippet & Badges */}
                <div className="flex-1 flex items-center gap-2 min-w-0 overflow-hidden">
                  <span
                    className={`text-xs truncate flex-shrink-0 max-w-[85%] sm:max-w-[50%] ${
                      isUnread
                        ? 'font-semibold text-[#252821]'
                        : 'font-medium text-[#52544E]'
                    }`}
                  >
                    {email.subject || '(No subject)'}
                  </span>
                  <span className="text-xs text-[#92938C] hidden xl:inline">-</span>
                  <span className="text-xs text-[#74766F] truncate flex-1 hidden xl:inline">
                    {decodeHtmlEntities(email.snippet)}
                  </span>

                  {/* Desktop Badges */}
                  <div className="hidden lg:flex items-center gap-1.5 flex-shrink-0">
                    {email.category && (
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-white border border-[#E7E4DC] text-[#74766F] uppercase font-mono">
                        {email.category}
                      </span>
                    )}
                    {isHighPriority && (
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#FDF2F2] text-[#C24141] border border-[#F8D7D7] font-medium">
                        High
                      </span>
                    )}
                    {isMediumPriority && (
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#FEF8ED] text-[#A66A12] border border-[#FCE6BE] font-medium">
                        Med
                      </span>
                    )}
                    {email.requires_reply === 1 && (
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#EAEFFF] text-[#4263EB] border border-[#D0DBFF] font-medium flex items-center gap-1">
                        <Reply className="w-2.5 h-2.5" />
                        Reply
                      </span>
                    )}
                    {email.security_risk && email.security_risk !== 'safe' && (
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-[#FDF2F2] text-[#C24141] border border-[#F8D7D7] font-medium flex items-center gap-1">
                        <ShieldAlert className="w-2.5 h-2.5" />
                        {email.security_risk.toUpperCase()}
                      </span>
                    )}
                  </div>
                </div>

                {/* Right: Date / Timestamp & mobile badges */}
                <div className="flex items-center justify-between sm:justify-end gap-2 flex-shrink-0 sm:w-28 text-right">
                  <div className="lg:hidden flex items-center gap-1">
                    {email.category && (
                      <span className="text-[9px] px-1 py-0.2 rounded bg-white border border-[#E7E4DC] text-[#74766F] uppercase font-mono">
                        {email.category}
                      </span>
                    )}
                    {email.requires_reply === 1 && (
                      <span className="text-[9px] px-1 py-0.2 rounded bg-[#EAEFFF] text-[#4263EB] font-medium">
                        Reply
                      </span>
                    )}
                  </div>
                  <span className="text-[11px] font-mono text-[#92938C]">
                    {formatDate(email.date)}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
