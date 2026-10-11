import React from 'react';
import {
  Mail,
  Star,
  CheckSquare,
  Paperclip,
  Clock,
  Settings,
  RefreshCw,
  Sparkles,
} from 'lucide-react';
import { InboxMetrics } from '../types';

interface HeaderProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  authenticated: boolean;
  metrics: InboxMetrics;
  syncing: boolean;
  onSync: () => void;
  showAssistant?: boolean;
  onToggleAssistant?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  authenticated,
  metrics,
  syncing,
  onSync,
  showAssistant = false,
  onToggleAssistant,
}) => {
  const tabs = [
    { id: 'inbox', label: 'Inbox', icon: Mail, count: metrics.unread },
    { id: 'important', label: 'Important', icon: Star, count: metrics.high_priority },
    { id: 'tasks', label: 'Tasks', icon: CheckSquare },
    { id: 'files', label: 'Files', icon: Paperclip },
    { id: 'history', label: 'History', icon: Clock },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <header className="h-14 border-b border-[#E7E4DC] bg-white px-4 lg:px-6 flex items-center justify-between flex-shrink-0 z-30 select-none">
      {/* Brand & Left Section */}
      <div className="flex items-center space-x-6 min-w-0">
        <div className="flex items-center space-x-2.5 flex-shrink-0">
          <div className="w-7 h-7 rounded-md bg-[#4263EB] text-white flex items-center justify-center font-bold text-xs tracking-tight shadow-sm">
            PM
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold tracking-tight text-[#252821]">
              PersonalMail
            </span>
            <span className="text-[10px] font-medium tracking-wide uppercase px-1.5 py-0.5 rounded bg-[#F0EEE7] border border-[#E7E4DC] text-[#74766F]">
              Assistant
            </span>
          </div>
        </div>

        {/* Primary Navigation Tabs */}
        <nav className="hidden sm:flex items-center space-x-1 overflow-x-auto scrollbar-none">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`h-8 px-3 rounded-lg text-xs font-medium flex items-center gap-2 transition-colors whitespace-nowrap ${
                  isActive
                    ? 'bg-[#EAEFFF] text-[#4263EB]'
                    : 'text-[#74766F] hover:text-[#252821] hover:bg-[#F0EEE7]'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-[#4263EB]' : 'text-[#74766F]'}`} />
                <span>{tab.label}</span>
                {tab.count !== undefined && tab.count > 0 && (
                  <span
                    className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono font-medium ${
                      isActive
                        ? 'bg-[#4263EB]/15 text-[#4263EB]'
                        : 'bg-[#F0EEE7] text-[#74766F]'
                    }`}
                  >
                    {tab.count}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Right Controls: Gmail Status & Sync Button */}
      <div className="flex items-center space-x-2.5 flex-shrink-0">
        {/* Mobile dropdown if narrow */}
        <div className="sm:hidden flex items-center">
          <select
            value={activeTab}
            onChange={(e) => setActiveTab(e.target.value)}
            className="h-8 bg-white border border-[#E7E4DC] rounded-lg text-xs text-[#252821] px-2 focus:outline-none focus:border-[#4263EB]"
          >
            {tabs.map((tab) => (
              <option key={tab.id} value={tab.id}>
                {tab.label}
              </option>
            ))}
          </select>
        </div>

        {/* Connection Status Indicator */}
        <div className="hidden md:flex items-center gap-2 px-2.5 py-1 rounded-lg bg-[#FBFAF7] border border-[#E7E4DC] text-xs text-[#74766F]">
          <span
            className={`w-2 h-2 rounded-full ${
              authenticated ? 'bg-[#23845B]' : 'bg-[#A66A12]'
            }`}
          />
          <span className="font-medium text-[11px] text-[#74766F]">
            {authenticated ? 'Gmail Connected' : 'OAuth Setup Required'}
          </span>
        </div>

        {/* AI Assistant Toggle Button */}
        {onToggleAssistant && (
          <button
            onClick={onToggleAssistant}
            className={`h-8 px-3 rounded-lg text-xs font-medium border flex items-center gap-1.5 transition-colors whitespace-nowrap shadow-sm ${
              showAssistant
                ? 'bg-[#EAEFFF] text-[#4263EB] border-[#D0DBFF] font-semibold'
                : 'bg-white hover:bg-[#F0EEE7] text-[#252821] border-[#E7E4DC]'
            }`}
            title="Toggle AI Assistant drawer"
          >
            <Sparkles className={`w-3.5 h-3.5 ${showAssistant ? 'text-[#4263EB]' : 'text-[#74766F]'}`} />
            <span className="hidden sm:inline">AI Assistant</span>
          </button>
        )}

        {/* Sync Button */}
        <button
          onClick={onSync}
          disabled={syncing}
          className="h-8 px-3 rounded-lg text-xs font-medium bg-white hover:bg-[#F0EEE7] text-[#252821] border border-[#E7E4DC] flex items-center gap-1.5 transition-colors disabled:opacity-50 whitespace-nowrap shadow-sm"
          title="Sync recent emails from Gmail"
        >
          <RefreshCw
            className={`w-3.5 h-3.5 text-[#74766F] ${
              syncing ? 'animate-spin text-[#4263EB]' : ''
            }`}
          />
          <span className="hidden sm:inline">{syncing ? 'Syncing...' : 'Sync'}</span>
        </button>
      </div>
    </header>
  );
};
