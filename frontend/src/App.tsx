import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { EmailList } from './components/EmailList';
import { EmailDetail } from './components/EmailDetail';
import { ChatPanel } from './components/ChatPanel';
import { TasksView } from './components/TasksView';
import { HistoryView } from './components/HistoryView';
import { SettingsView } from './components/SettingsView';
import { FilesView } from './components/FilesView';
import { ApprovalModal } from './components/ApprovalModal';
import { Email, Task, DraftCardData, ChatMessage, InboxMetrics, AuditLog } from './types';
import { api } from './api';

export function App() {
  const [activeTab, setActiveTab] = useState('inbox');
  const [emails, setEmails] = useState<Email[]>([]);
  const [selectedEmail, setSelectedEmail] = useState<Email | null>(null);
  const [metrics, setMetrics] = useState<InboxMetrics>({
    total: 0,
    unread: 0,
    needs_reply: 0,
    high_priority: 0,
    security_alerts: 0,
  });
  const [authenticated, setAuthenticated] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [loadingEmails, setLoadingEmails] = useState(false);

  // Filters
  const [filterCategory, setFilterCategory] = useState('');
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [needsReplyOnly, setNeedsReplyOnly] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');

  // Mobile view pane switcher
  const [mobileTab, setMobileTab] = useState<'emails' | 'assistant'>('emails');

  // Tasks & History
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [historyLogs, setHistoryLogs] = useState<AuditLog[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Chat State
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        'Welcome to PersonalMail. I am your personalized email assistant. Ask me to triage unread emails, extract deadlines, or draft tone-matched replies.',
      timestamp: 'Just now',
    },
  ]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  // AI Action Results per email/thread
  const [aiSummary, setAiSummary] = useState<{ threadId: string; content: string } | null>(null);
  const [aiTasksResult, setAiTasksResult] = useState<{ threadId: string; content: string } | null>(null);
  const [aiStreamingAction, setAiStreamingAction] = useState<'draft' | 'tasks' | 'summary' | null>(null);
  const [draftsByThread, setDraftsByThread] = useState<Record<string, DraftCardData | null>>({});
  const [showAssistant, setShowAssistant] = useState(false);

  // Human-in-the-Loop approval modal
  const [approvalDraft, setApprovalDraft] = useState<DraftCardData | null>(null);

  // Initial load
  useEffect(() => {
    checkAuthAndHealth();
    loadEmails();
  }, [filterCategory, unreadOnly, needsReplyOnly, searchQuery, activeTab]);

  const checkAuthAndHealth = async () => {
    try {
      const auth = await api.getAuthStatus();
      setAuthenticated(auth.authenticated);
      const met = await api.getMetrics();
      setMetrics(met);
    } catch (e) {
      console.error(e);
    }
  };

  const loadEmails = async () => {
    if (activeTab !== 'inbox' && activeTab !== 'important') return;
    setLoadingEmails(true);
    try {
      const res = await api.getEmails({
        unread_only: unreadOnly || activeTab === 'important',
        priority: activeTab === 'important' ? 'high' : undefined,
        category: filterCategory,
        requires_reply: needsReplyOnly,
        search: searchQuery,
      });
      setEmails(res.emails || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingEmails(false);
    }
  };

  const loadTasks = async () => {
    setLoadingTasks(true);
    try {
      const res = await api.getTasks();
      setTasks(res.tasks || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingTasks(false);
    }
  };

  const loadHistory = async () => {
    setLoadingHistory(true);
    try {
      const res = await api.getHistory();
      setHistoryLogs(res.history || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'tasks') loadTasks();
    if (activeTab === 'history') loadHistory();
  }, [activeTab]);

  const handleSync = async () => {
    setSyncing(true);
    try {
      await api.triggerSync(true);
      await loadEmails();
      await checkAuthAndHealth();
    } catch (e) {
      console.error(e);
    } finally {
      setSyncing(false);
    }
  };

  const handleSelectEmail = (email: Email) => {
    setSelectedEmail(email);
    setMobileTab('emails');
  };

  const handleBackToList = () => {
    setSelectedEmail(null);
  };

  const handleMarkRead = (messageId: string, isRead: boolean) => {
    setEmails((prev) =>
      prev.map((e) => (e.message_id === messageId ? { ...e, is_read: isRead ? 1 : 0 } : e))
    );
    setMetrics((prev) => ({
      ...prev,
      unread: Math.max(0, prev.unread + (isRead ? -1 : 1)),
    }));
  };

  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
    if (tab === 'inbox' || tab === 'important') {
      setSelectedEmail(null);
    }
  };

  // Chat handling
  const handleSendMessage = async (
    userText: string,
    activeDraftParam?: DraftCardData,
    actionType?: 'draft' | 'tasks' | 'summary'
  ) => {
    let detectedAction = actionType;
    if (!detectedAction) {
      const lower = userText.toLowerCase();
      if (lower.includes('summar')) detectedAction = 'summary';
      else if (lower.includes('task') || lower.includes('action item') || lower.includes('deadline')) detectedAction = 'tasks';
      else if (lower.includes('reply') || lower.includes('draft') || lower.includes('compose')) detectedAction = 'draft';
    }
    setAiStreamingAction(detectedAction || null);

    const userMsg: ChatMessage = {
      id: String(Date.now()),
      role: 'user',
      content: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsStreaming(true);
    setStatusMessage(
      detectedAction === 'summary'
        ? 'Generating executive summary...'
        : detectedAction === 'tasks'
        ? 'Extracting action items and deadlines...'
        : detectedAction === 'draft'
        ? 'Composing tone-matched draft reply...'
        : 'Analyzing conversation...'
    );

    try {
      const targetDraft = activeDraftParam || [...messages].reverse().find((m) => m.draftCard)?.draftCard;

      const history = messages.slice(-10).map((m) => ({
        role: m.role,
        content: m.content,
        draftCard: m.draftCard ? {
          to_email: m.draftCard.to_email,
          subject: m.draftCard.subject,
          body: m.draftCard.body,
        } : undefined,
      }));

      const res = await api.sendChat(
        userText,
        selectedEmail?.thread_id,
        selectedEmail?.message_id,
        targetDraft,
        history
      );

      let replyText = '';
      if (typeof res.reply === 'string' && res.reply.trim()) {
        replyText = res.reply;
      } else if (Array.isArray(res.reply)) {
        replyText = (res.reply as any[])
          .map((item) => (typeof item === 'string' ? item : item?.text || JSON.stringify(item)))
          .join('\n');
      } else {
        replyText = 'Processed your request successfully.';
      }

      const currentThreadId = selectedEmail?.thread_id || res.draft_card?.thread_id || '';

      if (res.draft_card) {
        const threadIdToStore = selectedEmail?.thread_id || res.draft_card.thread_id;
        if (threadIdToStore) {
          const cardData: DraftCardData = res.draft_card;
          setDraftsByThread((prev) => ({
            ...prev,
            [threadIdToStore]: cardData,
          }));
        }
      }

      if (detectedAction === 'summary' || (res as any).intent === 'summarize') {
        if (currentThreadId) {
          setAiSummary({ threadId: currentThreadId, content: replyText });
        }
      } else if (detectedAction === 'tasks' || (res as any).intent === 'tasks') {
        if (currentThreadId) {
          setAiTasksResult({ threadId: currentThreadId, content: replyText });
        }
        loadTasks();
      }

      const aiMsg: ChatMessage = {
        id: String(Date.now() + 1),
        role: 'assistant',
        content: replyText,
        draftCard: res.draft_card,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, aiMsg]);
    } catch (e: any) {
      const errMsg: ChatMessage = {
        id: String(Date.now() + 1),
        role: 'assistant',
        content: `Error communicating with agent: ${e.message}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errMsg]);
    } finally {
      setIsStreaming(false);
      setStatusMessage(null);
      setAiStreamingAction(null);
    }
  };

  const handleSaveDraft = async (draft: DraftCardData) => {
    try {
      if (draft.id) {
        await api.updateDraft(draft.id, {
          body: draft.body,
          subject: draft.subject,
        });
      } else {
        await api.saveDraft({
          to_email: draft.to_email,
          subject: draft.subject,
          body: draft.body,
          thread_id: draft.thread_id,
          draft_id: draft.id,
        });
      }

      setMessages((prev) => [
        ...prev,
        {
          id: String(Date.now()),
          role: 'assistant',
          content: 'Draft saved successfully. It is saved in your local database and synced directly to your Gmail Drafts folder.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    } catch (e: any) {
      console.error(e);
      setMessages((prev) => [
        ...prev,
        {
          id: String(Date.now()),
          role: 'assistant',
          content: `Failed to save draft: ${e.message || 'Unknown error'}`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
    }
  };

  const handleApproveAndSend = async (draft: DraftCardData) => {
    const attachmentPaths = draft.selected_attachments?.map((a) => a.file_path) || [];
    await api.sendEmailAction({
      to_email: draft.to_email,
      subject: draft.subject,
      body: draft.body,
      thread_id: draft.thread_id,
      draft_id: draft.id,
      user_approved: true,
      attachments: attachmentPaths.length > 0 ? attachmentPaths : undefined,
    });

    const draftThreadId = draft.thread_id;
    if (draftThreadId) {
      setDraftsByThread((prev) => ({
        ...prev,
        [draftThreadId]: null,
      }));
    }

    const attNote = attachmentPaths.length > 0 ? ` with ${attachmentPaths.length} attachment(s)` : '';
    setMessages((prev) => [
      ...prev,
      {
        id: String(Date.now()),
        role: 'system',
        content: `Email successfully sent to ${draft.to_email}${attNote} via Gmail.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      },
    ]);
  };

  const handleToggleTaskStatus = async (taskId: string, currentStatus: 'pending' | 'completed') => {
    const nextStatus = currentStatus === 'pending' ? 'completed' : 'pending';
    try {
      await api.updateTaskStatus(taskId, nextStatus);
      setTasks((prev) =>
        prev.map((t) => (t.id === taskId ? { ...t, status: nextStatus } : t))
      );
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteTask = async (taskId: string) => {
    try {
      await api.deleteTask(taskId);
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
    } catch (e) {
      console.error(e);
    }
  };

  const handleCreateTask = async (data: {
    title: string;
    deadline?: string;
    priority: string;
    source_from?: string;
  }) => {
    try {
      const created = await api.createTask(data);
      setTasks((prev) => [created, ...prev]);
    } catch (e) {
      console.error(e);
    }
  };

  const handleNavigateToTaskEmail = async (threadId: string, emailFrom?: string) => {
    let match = emails.find((e) => e.thread_id === threadId);
    if (!match && emailFrom) {
      match = emails.find((e) => e.from_email.toLowerCase() === emailFrom.toLowerCase());
    }
    if (match) {
      setSelectedEmail(match);
      setActiveTab('inbox');
    } else {
      setActiveTab('inbox');
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-[#F7F5F0] text-[#252821] overflow-hidden font-sans select-none">
      {/* Top Header */}
      <Header
        activeTab={activeTab}
        setActiveTab={handleTabChange}
        authenticated={authenticated}
        metrics={metrics}
        syncing={syncing}
        onSync={handleSync}
        showAssistant={showAssistant}
        onToggleAssistant={() => setShowAssistant(!showAssistant)}
      />

      {/* Main Content Workspace */}
      <main className="flex-1 flex overflow-hidden relative">
        {activeTab === 'inbox' || activeTab === 'important' ? (
          <>
            {/* Primary View Area (Email section: 40% when AI assistant is open, 100% when closed) */}
            <div
              className={`h-full min-w-0 flex flex-col overflow-hidden transition-all duration-200 ${
                showAssistant ? 'w-full md:w-[40%] flex-shrink-0' : 'w-full flex-1'
              }`}
            >
              {selectedEmail ? (
                <EmailDetail
                  email={selectedEmail}
                  onBack={handleBackToList}
                  onAskAi={(prompt, draft, actionType) => handleSendMessage(prompt, draft, actionType)}
                  onMarkRead={handleMarkRead}
                  isAiStreaming={isStreaming}
                  aiStreamingAction={aiStreamingAction}
                  activeDraft={
                    selectedEmail?.thread_id
                      ? (draftsByThread[selectedEmail.thread_id] || null)
                      : null
                  }
                  onDiscardDraft={() => {
                    if (selectedEmail?.thread_id) {
                      setDraftsByThread((prev) => ({
                        ...prev,
                        [selectedEmail.thread_id]: null,
                      }));
                    }
                  }}
                  aiSummary={
                    aiSummary && aiSummary.threadId === selectedEmail.thread_id
                      ? aiSummary.content
                      : null
                  }
                  aiTasksResult={
                    aiTasksResult && aiTasksResult.threadId === selectedEmail.thread_id
                      ? aiTasksResult.content
                      : null
                  }
                  onClearSummary={() => setAiSummary(null)}
                  onClearTasks={() => setAiTasksResult(null)}
                  onViewTasksTab={() => {
                    setActiveTab('tasks');
                    loadTasks();
                  }}
                  onSendDraftClick={(draft) => setApprovalDraft(draft)}
                  onSaveDraft={handleSaveDraft}
                  onImproveDraft={(instruction, draft) => handleSendMessage(instruction, draft, 'draft')}
                />
              ) : (
                <EmailList
                  emails={emails}
                  selectedEmail={selectedEmail}
                  onSelectEmail={handleSelectEmail}
                  filterCategory={filterCategory}
                  setFilterCategory={setFilterCategory}
                  searchQuery={searchQuery}
                  setSearchQuery={setSearchQuery}
                  unreadOnly={unreadOnly}
                  setUnreadOnly={setUnreadOnly}
                  needsReplyOnly={needsReplyOnly}
                  setNeedsReplyOnly={setNeedsReplyOnly}
                  loading={loadingEmails}
                />
              )}
            </div>

            {/* AI Assistant Section (60% width when open) */}
            {showAssistant && (
              <div className="w-full md:w-[60%] flex-shrink-0 h-full border-l border-[#E7E4DC] bg-white z-20 shadow-lg md:shadow-none flex flex-col absolute md:relative right-0 top-0 bottom-0 transition-all duration-200">
                <ChatPanel
                  messages={messages}
                  selectedEmail={selectedEmail}
                  onClearSelectedEmail={() => setSelectedEmail(null)}
                  onSendMessage={handleSendMessage}
                  onSendDraftClick={(draft) => setApprovalDraft(draft)}
                  onSaveDraft={handleSaveDraft}
                  isStreaming={isStreaming}
                  statusMessage={statusMessage}
                  onClose={() => setShowAssistant(false)}
                />
              </div>
            )}
          </>
        ) : activeTab === 'tasks' ? (
          <div className="w-full h-full overflow-y-auto">
            <TasksView
              tasks={tasks}
              onToggleStatus={handleToggleTaskStatus}
              onDeleteTask={handleDeleteTask}
              onCreateTask={handleCreateTask}
              onNavigateToEmail={handleNavigateToTaskEmail}
              loading={loadingTasks}
            />
          </div>
        ) : activeTab === 'history' ? (
          <div className="w-full h-full overflow-y-auto">
            <HistoryView logs={historyLogs} loading={loadingHistory} />
          </div>
        ) : activeTab === 'files' ? (
          <div className="w-full h-full overflow-y-auto">
            <FilesView />
          </div>
        ) : (
          <div className="w-full h-full overflow-y-auto">
            <SettingsView />
          </div>
        )}
      </main>

      {/* Human-in-the-Loop Approval Modal */}
      {approvalDraft && (
        <ApprovalModal
          draft={approvalDraft}
          isOpen={!!approvalDraft}
          onClose={() => setApprovalDraft(null)}
          onApproveAndSend={handleApproveAndSend}
        />
      )}
    </div>
  );
}

export default App;
