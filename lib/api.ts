const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Email interface matching our components
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
  assigned_to?: string | null;
  recommended_folder?: string | null;
  folder_is_new?: boolean;
}

export interface EmailsResponse {
  emails: Email[];
  total: number;
  limit?: number;
  offset?: number;
}

export interface EmailSummary {
  total: number;
  work: number;
  noise: number;
  pending: number;
}

export interface AuthResponse {
  authenticated: boolean;
  email?: string;
  name?: string;
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

/**
 * Fetch emails from the API with optional filters
 */
export async function fetchEmails(params?: {
  limit?: number;
  offset?: number;
  status?: string;
  category_min?: number;
  category_max?: number;
}): Promise<EmailsResponse> {
  const queryParams = new URLSearchParams();
  if (params?.limit) queryParams.append('limit', params.limit.toString());
  if (params?.offset) queryParams.append('offset', params.offset.toString());
  if (params?.status) queryParams.append('status', params.status);
  if (params?.category_min) queryParams.append('category_min', params.category_min.toString());
  if (params?.category_max) queryParams.append('category_max', params.category_max.toString());

  const url = `${API_URL}/api/emails${queryParams.toString() ? '?' + queryParams.toString() : ''}`;

  const response = await fetch(url, {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch emails: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch email summary counts
 */
export async function fetchEmailSummary(): Promise<EmailSummary> {
  const response = await fetch(`${API_URL}/api/emails/summary`, {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch email summary: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Trigger a fetch of new emails from Outlook
 */
export async function triggerFetch(): Promise<{ message: string; count: number }> {
  const response = await fetch(`${API_URL}/api/emails/fetch`, {
    method: 'POST',
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to trigger email fetch: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Run the classification pipeline
 */
export async function runPipeline(): Promise<{ message: string; processed: number }> {
  const response = await fetch(`${API_URL}/api/emails/pipeline/run`, {
    method: 'POST',
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to run pipeline: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Check if the user is authenticated
 */
export async function checkAuth(): Promise<AuthResponse> {
  const response = await fetch(`${API_URL}/api/auth/me`, {
    credentials: 'include',
  });

  if (response.status === 401) {
    return { authenticated: false };
  }

  if (!response.ok) {
    throw new Error(`Failed to check auth: ${response.statusText}`);
  }

  const data = await response.json();

  // Transform backend response to our format
  return {
    authenticated: true,
    email: data.email,
    name: data.display_name || data.email,
  };
}

/**
 * Get the login URL
 */
export function getLoginUrl(): string {
  return `${API_URL}/api/auth/login`;
}

/**
 * Update an email's properties
 */
export async function updateEmail(
  emailId: string,
  updates: Partial<Email>
): Promise<Email> {
  const response = await fetch(`${API_URL}/api/emails/${emailId}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(updates),
  });

  if (!response.ok) {
    throw new Error(`Failed to update email: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Fetch work emails (categories 1-5)
 */
export async function fetchWorkEmails(): Promise<EmailsResponse> {
  return fetchEmails({
    status: 'classified',
    category_min: 1,
    category_max: 5,
  });
}

/**
 * Fetch other/noise emails (categories 6-11)
 */
export async function fetchOtherEmails(): Promise<EmailsResponse> {
  return fetchEmails({
    status: 'classified',
    category_min: 6,
    category_max: 11,
  });
}

/**
 * Reclassify an email to a different category (immediate action)
 */
export async function reclassifyEmail(
  emailId: string,
  categoryId: string
): Promise<Email> {
  console.log(`[API] Reclassifying email ${emailId} to category ${categoryId}`);

  const response = await fetch(`${API_URL}/api/emails/${emailId}/reclassify`, {
    method: 'PUT',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ category_id: categoryId }),
  });

  if (!response.ok) {
    throw new Error(`Failed to reclassify email: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Update email due date (batched action)
 *
 * NOTE: Stored locally until Execute All is triggered
 */
export async function updateEmailDueDate(
  emailId: string,
  dueDate: string | null
): Promise<Email> {
  console.log(`[API] Updating email ${emailId} due date to ${dueDate}`);
  console.log('[API] ⚠️  Backend update endpoint not implemented - stored for batch execution');

  // Return mock success - actual update happens on Execute All
  return Promise.resolve({ id: emailId, due_date: dueDate } as Email);
}

/**
 * Update email folder (batched action)
 *
 * NOTE: Stored locally until Execute All is triggered
 */
export async function updateEmailFolder(
  emailId: string,
  folder: string | null
): Promise<Email> {
  console.log(`[API] Updating email ${emailId} folder to ${folder}`);
  console.log('[API] ⚠️  Backend update endpoint not implemented - stored for batch execution');

  // Return mock success - actual update happens on Execute All
  return Promise.resolve({ id: emailId, folder } as Email);
}

/**
 * Approve an email with optional metadata
 */
export async function approveEmail(
  emailId: string,
  metadata?: {
    due_date?: string | null;
    category_id?: number;
    folder?: string | null;
  }
): Promise<Email> {
  const response = await fetch(`${API_URL}/api/emails/${emailId}/approve`, {
    method: 'PUT',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(metadata || {}),
  });

  if (!response.ok) {
    throw new Error(`Failed to approve email: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Unapprove an email (revert to classified status)
 */
export async function unapproveEmail(emailId: string): Promise<Email> {
  const response = await fetch(`${API_URL}/api/emails/${emailId}/unapprove`, {
    method: 'PUT',
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to unapprove email: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Execute all approved Work emails (move to folders, create To-Do tasks)
 */
export async function executeApprovedEmails(): Promise<{
  executed: number;
  folders_moved: number;
  todos_created: number;
  errors: string[];
  message: string;
}> {
  const response = await fetch(`${API_URL}/api/emails/execute`, {
    method: 'POST',
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to execute emails: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Confirm all Other emails (move to default folders)
 */
export async function confirmOtherEmails(): Promise<{
  confirmed: number;
  moved: number;
  errors: string[];
  message: string;
}> {
  const response = await fetch(`${API_URL}/api/emails/confirm-other`, {
    method: 'POST',
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to confirm Other emails: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get Outlook folders from Graph API
 */
export async function fetchOutlookFolders(): Promise<Array<{ id: string; displayName: string }>> {
  const response = await fetch(`${API_URL}/api/emails/folders`, {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch Outlook folders: ${response.statusText}`);
  }

  const data = await response.json();
  return data.folders || [];
}

/**
 * Get list of categories, optionally filtered by master_category
 */
export async function fetchCategories(masterCategory?: 'Work' | 'Other'): Promise<Category[]> {
  const queryParams = new URLSearchParams();
  if (masterCategory) queryParams.append('master_category', masterCategory);

  const url = `${API_URL}/api/categories${queryParams.toString() ? '?' + queryParams.toString() : ''}`;

  const response = await fetch(url, {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch categories: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get list of folders from hierarchy
 */
export async function fetchFolders(): Promise<Folder[]> {
  const response = await fetch(`${API_URL}/api/folders/hierarchy`, {
    credentials: 'include',
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch folders: ${response.statusText}`);
  }

  const data = await response.json();
  // Convert hierarchy response to simple folder list
  // Map displayName to name to match our Folder interface
  return (data.folders || []).map((folder: any) => ({
    id: folder.id,
    name: folder.displayName || folder.name
  }));
}

/**
 * Create a new folder
 */
export async function createFolder(name: string): Promise<Folder> {
  const response = await fetch(`${API_URL}/api/folders`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ name }),
  });

  if (!response.ok) {
    throw new Error(`Failed to create folder: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Batch move all emails in a category to a specific folder
 */
export async function batchMoveToFolder(categoryId: number): Promise<{
  moved: number;
  message: string;
}> {
  const response = await fetch(`${API_URL}/api/emails/batch-move-to-folder`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ category_id: categoryId }),
  });

  if (!response.ok) {
    throw new Error(`Failed to batch move emails: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Batch delete all emails in a category (move to trash)
 */
export async function batchDeleteCategory(categoryId: number): Promise<{
  deleted: number;
  message: string;
}> {
  const response = await fetch(`${API_URL}/api/emails/batch-delete-category`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify({ category_id: categoryId }),
  });

  if (!response.ok) {
    throw new Error(`Failed to batch delete emails: ${response.statusText}`);
  }

  return response.json();
}
