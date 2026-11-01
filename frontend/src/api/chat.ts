import { API_BASE_URL, ApiError } from './client';
import { Citation } from '@/types';
import { storage } from '@/lib/storage';

export const chatApi = {
  streamChat: async (
    query: string,
    onToken: (token: string) => void,
    onSources: (sources: Citation[]) => void,
    onDone: () => void,
    onError: (err: Error) => void,
    signal?: AbortSignal
  ): Promise<() => void> => {
    const token = storage.getToken();
    const url = `${API_BASE_URL}/chat`;

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'text/event-stream, text/plain, application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ query }),
        signal,
      });

      if (response.status === 401) {
        storage.clearAuth();
        if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
          window.location.href = '/login';
        }
        throw new ApiError(401, 'Session expired. Please sign in again.');
      }

      if (!response.ok) {
        let errorMsg = `Server error (${response.status})`;
        try {
          const data = await response.json();
          if (data?.detail) errorMsg = data.detail;
        } catch {
          // ignore
        }
        throw new ApiError(response.status, errorMsg);
      }

      const contentType = response.headers.get('content-type') || '';

      // Check if response is Server-Sent Events (SSE)
      if (contentType.includes('text/event-stream')) {
        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('Unable to read stream from server.');
        }

        const decoder = new TextDecoder();
        let buffer = '';

        const readStream = async () => {
          try {
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;

              buffer += decoder.decode(value, { stream: true });
              const lines = buffer.split('\n');
              buffer = lines.pop() || '';

              for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed || trimmed.startsWith(':')) continue;

                if (trimmed.startsWith('data:')) {
                  const dataStr = trimmed.slice(5).trim();
                  if (dataStr === '[DONE]') {
                    onDone();
                    return;
                  }

                  try {
                    const parsed = JSON.parse(dataStr);
                    if (parsed.type === 'token' && typeof parsed.token === 'string') {
                      onToken(parsed.token);
                    } else if (parsed.type === 'sources' && Array.isArray(parsed.sources)) {
                      onSources(parsed.sources as Citation[]);
                    } else if (typeof parsed === 'string') {
                      onToken(parsed);
                    }
                  } catch {
                    // Fallback to literal text if not JSON
                    onToken(dataStr);
                  }
                }
              }
            }
            onDone();
          } catch (err: unknown) {
            if ((err as Error)?.name !== 'AbortError') {
              onError(err instanceof Error ? err : new Error(String(err)));
            }
          }
        };

        readStream();
      } else {
        // Plain string or JSON response (current backend behavior)
        let answer = '';
        if (contentType.includes('application/json')) {
          const json = await response.json();
          answer = typeof json === 'string' ? json : json.answer || json.response || JSON.stringify(json);
        } else {
          answer = await response.text();
        }

        // Emit tokens and finish
        onToken(answer);
        onDone();
      }
    } catch (err: unknown) {
      if ((err as Error)?.name !== 'AbortError') {
        onError(err instanceof Error ? err : new Error(String(err)));
      }
    }

    return () => {
      // Abort controller can be triggered externally
    };
  },

  chatPlain: async (query: string): Promise<string> => {
    const token = storage.getToken();
    const response = await fetch(`${API_BASE_URL}/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ query }),
    });

    if (!response.ok) {
      throw new ApiError(response.status, `Failed to send message (${response.status})`);
    }

    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      const data = await response.json();
      return typeof data === 'string' ? data : data.answer || JSON.stringify(data);
    }
    return response.text();
  },
};
