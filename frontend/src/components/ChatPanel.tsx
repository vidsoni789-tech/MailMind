import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, Sparkles, X, Mail, RefreshCw } from 'lucide-react';
import { ChatMessage, DraftCardData, Email } from '../types';
import { DraftCard } from './DraftCard';

interface ChatPanelProps {
  messages: ChatMessage[];
  selectedEmail: Email | null;
  onClearSelectedEmail: () => void;
  onSendMessage: (message: string, activeDraft?: DraftCardData) => void;
  onSendDraftClick: (draft: DraftCardData) => void;
  onSaveDraft: (draft: DraftCardData) => Promise<void> | void;
  isStreaming: boolean;
  statusMessage: string | null;
  onClose?: () => void;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({
  messages,
  selectedEmail,
  onClearSelectedEmail,
  onSendMessage,
  onSendDraftClick,
  onSaveDraft,
  isStreaming,
  statusMessage,
  onClose,
}) => {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming, statusMessage]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    onSendMessage(input);
    setInput('');
  };

  const quickPrompts = [
    'Summarize my important emails',
    'Which emails need a reply?',
    selectedEmail ? `Reply to this email` : 'Extract deadlines and tasks',
  ];

  return (
    <div className="flex flex-col h-full bg-[#F7F5F0] relative select-none">
      {/* Top Header / Context Banner */}
      <div className="h-14 border-b border-[#E7E4DC] bg-white px-4 sm:px-6 flex items-center justify-between flex-shrink-0 z-10">
        <div className="flex items-center space-x-2.5">
          <div className="w-6 h-6 rounded-md bg-[#EAEFFF] flex items-center justify-center text-[#4263EB]">
            <Bot className="w-3.5 h-3.5" />
          </div>
          <span className="text-xs font-semibold text-[#252821] tracking-tight">
            AI Assistant
          </span>
        </div>

        {/* Right Header Area: Context Chip & Close Button */}
        <div className="flex items-center space-x-2">
          {selectedEmail ? (
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-lg bg-[#FBFAF7] border border-[#E7E4DC] text-[#252821] text-xs">
              <Mail className="w-3.5 h-3.5 text-[#74766F]" />
              <span className="truncate max-w-[150px] sm:max-w-[200px] text-[11px] font-medium">
                {selectedEmail.subject || selectedEmail.from_name}
              </span>
              <button
                onClick={onClearSelectedEmail}
                className="p-0.5 rounded text-[#74766F] hover:text-[#252821] hover:bg-[#F0EEE7]"
                title="Clear email context"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          ) : (
            <span className="text-[11px] text-[#74766F] font-medium hidden sm:inline">
              General Inbox Mode
            </span>
          )}

          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-[#74766F] hover:text-[#252821] hover:bg-[#F0EEE7] transition"
              title="Close Assistant"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Message Stream */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
        <div className="w-full max-w-4xl mx-auto space-y-4">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex items-start space-x-3 ${
                msg.role === 'user' ? 'justify-end' : 'justify-start'
              }`}
            >
              {msg.role !== 'user' && (
                <div className="w-7 h-7 rounded-lg bg-[#EAEFFF] text-[#4263EB] flex items-center justify-center flex-shrink-0 mt-0.5">
                  <Sparkles className="w-3.5 h-3.5" />
                </div>
              )}

              <div
                className={`${
                  msg.draftCard ? 'w-full' : 'max-w-[85%]'
                } rounded-xl p-4 text-xs leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-[#4263EB] text-white shadow-sm'
                    : 'bg-white border border-[#E7E4DC] text-[#252821] shadow-card'
                }`}
              >
                <div className="whitespace-pre-wrap select-text">{msg.content}</div>

                {/* Embed draft proposal card if present */}
                {msg.draftCard && (
                  <DraftCard
                    draft={msg.draftCard}
                    onSendClick={onSendDraftClick}
                    onSaveDraft={onSaveDraft}
                    onImprove={(prompt, draft) => onSendMessage(prompt, draft)}
                  />
                )}

                <div
                  className={`text-[10px] mt-2.5 text-right font-mono ${
                    msg.role === 'user' ? 'text-white/80' : 'text-[#92938C]'
                  }`}
                >
                  {msg.timestamp}
                </div>
              </div>
            </div>
          ))}

          {/* Live streaming status pill */}
          {isStreaming && (
            <div className="flex items-center space-x-2 text-xs text-[#74766F] bg-white border border-[#E7E4DC] rounded-lg px-3 py-2 w-fit shadow-sm">
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-[#4263EB]" />
              <span>{statusMessage || 'Analyzing conversation...'}</span>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Quick Prompts Bar */}
      <div className="px-4 py-2.5 border-t border-[#E7E4DC] bg-white/70 backdrop-blur-sm flex items-center gap-2 overflow-x-auto scrollbar-none flex-shrink-0">
        <div className="max-w-3xl mx-auto w-full flex items-center gap-2 overflow-x-auto scrollbar-none">
          <span className="text-[11px] text-[#92938C] font-medium whitespace-nowrap hidden sm:inline">
            Suggestions:
          </span>
          {quickPrompts.map((prompt) => (
            <button
              key={prompt}
              onClick={() => onSendMessage(prompt)}
              disabled={isStreaming}
              className="h-8 px-3 rounded-lg bg-white hover:bg-[#F0EEE7] border border-[#E7E4DC] text-[#252821] text-xs font-medium transition whitespace-nowrap disabled:opacity-50 shadow-sm"
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>

      {/* Input Bar */}
      <form
        onSubmit={handleSubmit}
        className="p-3.5 sm:p-4 border-t border-[#E7E4DC] bg-white flex items-center gap-2.5 flex-shrink-0 shadow-[0_-2px_10px_rgba(0,0,0,0.02)]"
      >
        <div className="max-w-3xl mx-auto w-full flex items-center gap-2.5">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              selectedEmail
                ? "Instruct AI (e.g. 'Draft polite reply', 'Extract deadlines')..."
                : "Ask AI (e.g. 'Summarize unread emails', 'What needs reply?')..."
            }
            disabled={isStreaming}
            className="flex-1 h-10 bg-white border border-[#E7E4DC] rounded-lg px-3.5 text-xs text-[#252821] placeholder-[#92938C] focus:outline-none focus:border-[#4263EB] focus:ring-1 focus:ring-[#4263EB]/20 transition disabled:opacity-50"
          />

          <button
            type="submit"
            disabled={!input.trim() || isStreaming}
            className="h-10 px-4 rounded-lg bg-[#4263EB] hover:bg-[#3451D1] text-white text-xs font-medium flex items-center gap-1.5 transition disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap shadow-sm"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Send</span>
          </button>
        </div>
      </form>
    </div>
  );
};
