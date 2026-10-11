export interface Email {
  message_id: string;
  thread_id: string;
  subject: string;
  snippet: string;
  from_email: string;
  from_name: string;
  to_emails?: string;
  cc_emails?: string;
  date: string;
  is_read: number;
  category: string;
  priority: 'urgent' | 'high' | 'medium' | 'low';
  requires_reply: number;
  security_risk: 'safe' | 'caution' | 'danger';
  triage_reason?: string;
  body?: string;
  has_attachment?: number | boolean;
}

export interface ThreadMessage {
  message_id: string;
  id?: string;
  thread_id: string;
  subject?: string;
  snippet?: string;
  from_email?: string;
  from_name?: string;
  from?: string;
  to_emails?: string;
  to?: string;
  date: string;
  body?: string;
  is_read?: number;
  category?: string;
  priority?: string;
  requires_reply?: number;
  security_risk?: string;
  triage_reason?: string;
  has_attachment?: boolean | number;
}

export interface Task {
  id: string;
  thread_id: string;
  message_id?: string;
  title: string;
  deadline?: string;
  priority: 'high' | 'medium' | 'low';
  status: 'pending' | 'completed';
  source_from?: string;
  source_text?: string;
  created_at: string;
}

export interface QualityCheckItem {
  code: string;
  severity: 'INFO' | 'WARNING' | 'BLOCK';
  message: string;
}

export interface QualityCheckResult {
  status: 'PASS' | 'INFO' | 'WARNING' | 'BLOCK';
  checks: QualityCheckItem[];
}

export interface ConnectedDirectory {
  id: string;
  dir_path: string;
  label: string;
  is_active: number;
  last_scanned_at?: string;
  file_count: number;
  created_at: string;
  indexed_now?: number;
}

export interface AttachmentSuggestion {
  file_id: string;
  filename: string;
  file_path: string;
  directory_path?: string;
  size_bytes?: number;
  mime_type?: string;
  confidence: number;
  reason: string;
  is_selected?: boolean;
}

export interface IndexedFile {
  id: string;
  file_path: string;
  filename: string;
  directory_path?: string;
  mime_type?: string;
  size_bytes?: number;
  modified_at?: string;
  tags?: string;
  is_current?: number;
}


export interface DraftCardData {
  id?: string;
  to_email: string;
  subject: string;
  body: string;
  thread_id?: string;
  status?: string;
  warnings?: string[];
  quality_check?: QualityCheckResult;
  attachment_suggestions?: AttachmentSuggestion[];
  selected_attachments?: AttachmentSuggestion[];
  detected_attachment_requests?: string[];
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  draftCard?: DraftCardData;
  timestamp: string;
}

export interface UserProfile {
  id: number;
  role: string;
  organization: string;
  college: string;
  bio: string;
  signature: string;
  preferred_language: string;
  default_tone: string;
  default_reply_length: string;
}

export interface StylePreference {
  id: string;
  contact_email?: string;
  type: string;
  value: string;
  confidence: number;
  evidence_count: number;
  source: string;
}

export interface AuditLog {
  id: string;
  action: string;
  target_type: string;
  target_id?: string;
  approval_status: string;
  result?: string;
  created_at: string;
}

export interface InboxMetrics {
  total: number;
  unread: number;
  needs_reply: number;
  high_priority: number;
  security_alerts: number;
}
