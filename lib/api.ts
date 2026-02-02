const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export interface Email {
  id: string;
  subject: string;
  sender_name: string;
  sender_email: string;
  received_datetime: string;
  importance: string;
  body_preview: string;
  has_attachments: boolean;
}

export interface EmailsResponse {
  emails: Email[];
  total: number;
  limit: number;
  offset: number;
}

export interface AuthResponse {
  authenticated: boolean;
  email?: string;
}

/**
 * Fetch emails from the API
 */
export async function fetchEmails(limit = 50, offset = 0): Promise<EmailsResponse> {
  const response = await fetch(
    `${API_URL}/api/emails?limit=${limit}&offset=${offset}`,
    {
      credentials: 'include', // Include cookies for authentication
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to fetch emails: ${response.statusText}`);
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

  return response.json();
}

/**
 * Get the login URL
 */
export function getLoginUrl(): string {
  return `${API_URL}/api/auth/login`;
}
