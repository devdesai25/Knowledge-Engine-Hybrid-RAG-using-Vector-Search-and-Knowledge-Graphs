import { storage } from '@/lib/storage';

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export class ApiError extends Error {
  status: number;
  detail?: string;

  constructor(status: number, message: string, detail?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

interface RequestOptions extends RequestInit {
  requiresAuth?: boolean;
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { requiresAuth = true, headers = {}, ...restOptions } = options;

  const url = endpoint.startsWith('http')
    ? endpoint
    : `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;

  const requestHeaders = new Headers(headers);

  if (requiresAuth) {
    const token = storage.getToken();
    if (token) {
      requestHeaders.set('Authorization', `Bearer ${token}`);
    }
  }

  // Set default JSON Content-Type if not sending FormData
  if (!(restOptions.body instanceof FormData) && !requestHeaders.has('Content-Type')) {
    requestHeaders.set('Content-Type', 'application/json');
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...restOptions,
      headers: requestHeaders,
    });
  } catch {
    throw new ApiError(0, 'Unable to connect to backend server. Please verify your connection.');
  }

  if (response.status === 401) {
    storage.clearAuth();
    if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
    throw new ApiError(401, 'Session expired. Please sign in again.');
  }

  if (response.status === 403) {
    let errorDetail = 'You do not have permission to perform this action.';
    try {
      const data = await response.json();
      if (data?.detail) errorDetail = data.detail;
    } catch {
      // Keep default message
    }
    throw new ApiError(403, errorDetail);
  }

  if (!response.ok) {
    let errorMessage = `Request failed with status ${response.status}`;
    let errorDetail: string | undefined;
    try {
      const data = await response.json();
      if (data?.detail) {
        const detailStr = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
        errorDetail = detailStr;
        errorMessage = detailStr;
      } else if (data?.message) {
        errorMessage = data.message;
      }
    } catch {
      // Non-JSON error body
    }
    throw new ApiError(response.status, errorMessage, errorDetail);
  }

  // Return empty object for 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    return (await response.json()) as T;
  }

  return (await response.text()) as unknown as T;
}
