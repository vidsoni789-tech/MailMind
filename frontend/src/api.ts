import { Email, ThreadMessage, Task, DraftCardData, UserProfile, StylePreference, AuditLog, InboxMetrics, QualityCheckResult, IndexedFile, AttachmentSuggestion, ConnectedDirectory } from './types';

const API_BASE = '/api';


export const api = {
  // Health & Auth
  getHealth: async (): Promise<{ status: string; app: string; authenticated: boolean; metrics: InboxMetrics }> => {
    const res = await fetch(`${API_BASE}/health`);
    return res.json();
  },

  getAuthStatus: async (): Promise<{ authenticated: boolean; model: string; message: string }> => {
    const res = await fetch(`${API_BASE}/auth/status`);
    return res.json();
  },

  getMetrics: async (): Promise<InboxMetrics> => {
    const res = await fetch(`${API_BASE}/metrics`);
    return res.json();
  },

  // Emails
  getEmails: async (params?: {
    unread_only?: boolean;
    category?: string;
    priority?: string;
    requires_reply?: boolean;
    search?: string;
  }): Promise<{ emails: Email[]; count: number }> => {
    const query = new URLSearchParams();
    if (params?.unread_only) query.set('unread_only', 'true');
    if (params?.category) query.set('category', params.category);
    if (params?.priority) query.set('priority', params.priority);
    if (params?.requires_reply) query.set('requires_reply', 'true');
    if (params?.search) query.set('search', params.search);

    const res = await fetch(`${API_BASE}/emails?${query.toString()}`);
    return res.json();
  },

  getThread: async (threadId: string): Promise<{ thread_id: string; messages: ThreadMessage[] }> => {
    const res = await fetch(`${API_BASE}/threads/${threadId}`);
    if (!res.ok) {
      throw new Error(`Failed to load thread (${res.status})`);
    }
    return res.json();
  },

  getEmail: async (messageId: string): Promise<Email> => {
    const res = await fetch(`${API_BASE}/emails/${messageId}`);
    if (!res.ok) {
      throw new Error(`Failed to load email (${res.status})`);
    }
    return res.json();
  },

  markRead: async (messageId: string, isRead = true): Promise<any> => {
    const res = await fetch(`${API_BASE}/emails/${messageId}/read?is_read=${isRead}`, {
      method: 'PATCH',
    });
    return res.json();
  },

  triggerSync: async (incremental = true): Promise<any> => {
    const res = await fetch(`${API_BASE}/emails/sync`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ incremental }),
    });
    return res.json();
  },

  // Tasks
  getTasks: async (params?: {
    status?: string;
    priority?: string;
    search?: string;
  }): Promise<{ tasks: Task[]; count: number }> => {
    const q = new URLSearchParams();
    if (params?.status && params.status !== 'all') q.append('status', params.status);
    if (params?.priority && params.priority !== 'all') q.append('priority', params.priority);
    if (params?.search) q.append('search', params.search);
    const query = q.toString() ? `?${q.toString()}` : '';
    const res = await fetch(`${API_BASE}/tasks${query}`);
    return res.json();
  },

  createTask: async (data: {
    title: string;
    deadline?: string;
    priority?: string;
    source_from?: string;
    source_text?: string;
    thread_id?: string;
  }): Promise<Task> => {
    const res = await fetch(`${API_BASE}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return res.json();
  },

  updateTaskStatus: async (taskId: string, status: 'pending' | 'completed'): Promise<Task> => {
    const res = await fetch(`${API_BASE}/tasks/${taskId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status }),
    });
    return res.json();
  },

  deleteTask: async (taskId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/tasks/${taskId}`, { method: 'DELETE' });
    return res.json();
  },

  // Drafts & Actions
  saveDraft: async (data: {
    to_email: string;
    subject: string;
    body: string;
    thread_id?: string;
    draft_id?: string;
  }): Promise<any> => {
    const res = await fetch(`${API_BASE}/drafts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return res.json();
  },

  updateDraft: async (
    draftId: string,
    data: { body?: string; subject?: string; status?: string }
  ): Promise<any> => {
    const res = await fetch(`${API_BASE}/drafts/${draftId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return res.json();
  },


  validateDraft: async (data: {
    to_email?: string;
    subject?: string;
    body: string;
    thread_id?: string;
    attached_files?: string[];
  }): Promise<QualityCheckResult> => {
    const res = await fetch(`${API_BASE}/drafts/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Validation request failed (${res.status})`);
    }
    return res.json();
  },

  sendEmailAction: async (data: {
    to_email: string;
    subject: string;
    body: string;
    thread_id?: string;
    draft_id?: string;
    user_approved: boolean;
    attachments?: string[];
  }): Promise<any> => {
    const res = await fetch(`${API_BASE}/actions/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Failed to send email');
    }
    return res.json();
  },

  // Profile & Preferences
  getProfile: async (): Promise<UserProfile> => {
    const res = await fetch(`${API_BASE}/profile`);
    return res.json();
  },

  updateProfile: async (data: Partial<UserProfile>): Promise<UserProfile> => {
    const res = await fetch(`${API_BASE}/profile`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return res.json();
  },

  getPreferences: async (contactEmail?: string): Promise<{ preferences: StylePreference[] }> => {
    const query = contactEmail ? `?contact_email=${encodeURIComponent(contactEmail)}` : '';
    const res = await fetch(`${API_BASE}/profile/preferences${query}`);
    return res.json();
  },

  addPreference: async (data: {
    pref_type: string;
    value: string;
    contact_email?: string;
    confidence?: number;
  }): Promise<StylePreference> => {
    const res = await fetch(`${API_BASE}/profile/preferences`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return res.json();
  },

  updatePreference: async (
    prefId: string,
    data: { value?: string; confidence?: number; pref_type?: string }
  ): Promise<StylePreference> => {
    const res = await fetch(`${API_BASE}/profile/preferences/${prefId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return res.json();
  },

  deletePreference: async (prefId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/profile/preferences/${prefId}`, { method: 'DELETE' });
    return res.json();
  },

  getDraftEdits: async (draftId: string): Promise<{ draft_id: string; edits: any[] }> => {
    const res = await fetch(`${API_BASE}/drafts/${draftId}/edits`);
    return res.json();
  },


  // History & Audit
  getHistory: async (): Promise<{ history: AuditLog[] }> => {
    const res = await fetch(`${API_BASE}/history`);
    return res.json();
  },

  // Chat
  sendChat: async (
    message: string,
    selectedThreadId?: string,
    selectedMessageId?: string,
    activeDraft?: DraftCardData,
    history?: Array<{
      role: string;
      content: string;
      draftCard?: {
        to_email?: string;
        subject?: string;
        body?: string;
      };
    }>
  ): Promise<{
    reply: string;
    draft_card?: DraftCardData;
    latency_ms?: number;
    intent?: string;
  }> => {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        selected_thread_id: selectedThreadId,
        selected_message_id: selectedMessageId,
        active_draft: activeDraft,
        history,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Server error (${res.status})`);
    }
    return res.json();
  },
  // Attachments & Document Indexing
  getDirectories: async (): Promise<{ directories: ConnectedDirectory[]; count: number }> => {
    const res = await fetch(`${API_BASE}/directories`);
    return res.json();
  },

  connectDirectory: async (dirPath: string, label?: string): Promise<{ directory: ConnectedDirectory; directories: ConnectedDirectory[]; files: IndexedFile[]; total_files: number }> => {
    const res = await fetch(`${API_BASE}/directories`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dir_path: dirPath, label }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to connect directory');
    }
    return res.json();
  },

  disconnectDirectory: async (dirId: string, unindexFiles: boolean = true): Promise<{ directories: ConnectedDirectory[]; files: IndexedFile[]; total_files: number }> => {
    const res = await fetch(`${API_BASE}/directories/${dirId}?unindex_files=${unindexFiles}`, {
      method: 'DELETE',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to disconnect directory');
    }
    return res.json();
  },

  scanDirectoryById: async (dirId: string): Promise<{ newly_indexed: number; directory: ConnectedDirectory; directories: ConnectedDirectory[]; files: IndexedFile[]; total_files: number }> => {
    const res = await fetch(`${API_BASE}/directories/${dirId}/scan`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to scan directory');
    }
    return res.json();
  },

  scanAllDirectories: async (): Promise<{ directories_scanned: number; newly_indexed: number; total_files: number; directories: ConnectedDirectory[]; files: IndexedFile[] }> => {
    const res = await fetch(`${API_BASE}/directories/scan-all`, {
      method: 'POST',
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to scan all directories');
    }
    return res.json();
  },

  getFiles: async (directoryPath?: string): Promise<{ files: IndexedFile[]; count: number }> => {
    const url = directoryPath
      ? `${API_BASE}/files?directory_path=${encodeURIComponent(directoryPath)}`
      : `${API_BASE}/files`;
    const res = await fetch(url);
    return res.json();
  },

  scanFiles: async (dirPath?: string): Promise<{ newly_indexed: number; total_files: number; files: IndexedFile[] }> => {
    const res = await fetch(`${API_BASE}/files/scan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dir_path: dirPath }),
    });
    return res.json();
  },

  uploadFile: async (file: File, tags?: string): Promise<IndexedFile> => {
    const formData = new FormData();
    formData.append('file', file);
    if (tags) formData.append('tags', tags);

    const res = await fetch(`${API_BASE}/files/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to upload document');
    }
    return res.json();
  },

  deleteFile: async (fileId: string): Promise<any> => {
    const res = await fetch(`${API_BASE}/files/${fileId}`, { method: 'DELETE' });
    return res.json();
  },

  suggestAttachments: async (text: string, threadContext?: string, directoryPath?: string): Promise<{ requested_files: string[]; suggestions: AttachmentSuggestion[] }> => {
    const res = await fetch(`${API_BASE}/attachments/suggest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, thread_context: threadContext, directory_path: directoryPath }),
    });
    return res.json();
  },


  // Background Sync Worker
  getSyncWorkerStatus: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/sync/status`);
    return res.json();
  },

  startSyncWorker: async (interval_seconds?: number): Promise<any> => {
    const res = await fetch(`${API_BASE}/sync/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ interval_seconds: interval_seconds || 120 }),
    });
    return res.json();
  },

  stopSyncWorker: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/sync/stop`, { method: 'POST' });
    return res.json();
  },

  triggerSyncWorker: async (): Promise<any> => {
    const res = await fetch(`${API_BASE}/sync/trigger`, { method: 'POST' });
    return res.json();
  },
};
