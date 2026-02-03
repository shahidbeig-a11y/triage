// Shared type definitions for TRIAGE components

export interface Email {
  id: string;
  message_id: string;
  from_address: string;
  from_name: string;
  subject: string;
  body_preview: string;
  received_at: string;
  importance: string;
  conversation_id: string;
  has_attachments: boolean;
  category_id: string | null;
  confidence: number;
  urgency_score: number;
  due_date: string | null;
  folder: string | null;
  status: string;
  floor_override: boolean;
  stale_days: number;
  todo_task_id: string | null;
  assigned_to: string | null;
  recommended_folder?: string | null;
  folder_is_new?: boolean;
  aiDraft?: {
    tone: string;
    text: string;
    citations?: Array<{ text: string; highlight: string }>;
  };
}

export interface Category {
  id: string;
  number: number;
  label: string;
  master_category: string;
  description: string | null;
  is_system: boolean;
  icon: string;
  color: string;
}

export interface Folder {
  id: string;
  name: string;
}
