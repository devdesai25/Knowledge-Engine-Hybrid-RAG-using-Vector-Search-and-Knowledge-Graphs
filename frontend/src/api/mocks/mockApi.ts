import {
  User,
  LoginRequest,
  LoginResponse,
  DocumentItem,
  UploadResponse,
  Citation,
  AdminUser,
  Role,
} from '@/types';
import { mockStore } from './mockStore';
import { SEEDED_USERS, MOCK_TENANT_CHAT_RESPONSES } from './seedData';
import { storage } from '@/lib/storage';

// Helper for realistic async network delay
const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

class MockForbiddenError extends Error {
  status = 403;
  constructor(message = 'Access denied. Administrator privileges are required.') {
    super(message);
    this.name = 'ForbiddenError';
  }
}

class MockUnauthorizedError extends Error {
  status = 401;
  constructor(message = 'Invalid email or password.') {
    super(message);
    this.name = 'UnauthorizedError';
  }
}

export const mockApi = {
  // --- AUTH ---
  async login(credentials: LoginRequest): Promise<LoginResponse> {
    await delay(350);
    const emailLower = credentials.email.trim().toLowerCase();

    // Check seeded users
    const matchedSeedKey = Object.keys(SEEDED_USERS).find(
      (k) => SEEDED_USERS[k].email.toLowerCase() === emailLower
    );

    let user: User;
    if (matchedSeedKey) {
      user = SEEDED_USERS[matchedSeedKey];
    } else if (emailLower.includes('globex')) {
      user = {
        id: `user-${Date.now()}`,
        email: credentials.email,
        role: emailLower.includes('admin') ? 'admin' : 'member',
        tenant: { id: 'tenant-globex', name: 'Globex Corporation' },
      };
    } else {
      user = {
        id: `user-${Date.now()}`,
        email: credentials.email,
        role: emailLower.includes('admin') ? 'admin' : 'member',
        tenant: { id: 'tenant-acme', name: 'Acme Corp' },
      };
    }

    const token = `mock-jwt-token-${user.id}-${Date.now()}`;
    storage.setToken(token);
    storage.setUser(user);

    return {
      access_token: token,
      user,
    };
  },

  async getMe(): Promise<User> {
    await delay(150);
    const user = storage.getUser();
    if (!user) {
      throw new MockUnauthorizedError('Session expired. Please log in again.');
    }
    return user;
  },

  // --- DOCUMENTS ---
  async getDocuments(): Promise<DocumentItem[]> {
    await delay(300);
    const user = mockStore.getCurrentUser();
    return mockStore.getDocumentsForTenant(user.tenant.id);
  },

  async uploadDocuments(files: File[]): Promise<UploadResponse> {
    await delay(600);
    const user = mockStore.getCurrentUser();
    if (user.role !== 'admin') {
      throw new MockForbiddenError('Only administrators can upload documents.');
    }

    const filenames = files.map((f) => f.name);
    const result = mockStore.addDocuments(user.tenant.id, user.email, filenames);

    return {
      uploaded: result.uploaded,
      failed: result.failed,
      details: result.details.map((d) => ({
        filename: d.filename,
        status: d.status === 'failed' ? 'failed' : 'success',
        chunks: d.chunks,
        error: d.error,
      })),
    };
  },

  async deleteDocument(id: string): Promise<{ success: boolean; id: string }> {
    await delay(300);
    const user = mockStore.getCurrentUser();
    if (user.role !== 'admin') {
      throw new MockForbiddenError('Only administrators can delete documents.');
    }

    const deleted = mockStore.deleteDocument(user.tenant.id, id);
    if (!deleted) {
      throw new Error('Document not found or does not belong to your organization.');
    }

    return { success: true, id };
  },

  // --- CHAT (STREAMING & PLAIN) ---
  async streamChat(
    query: string,
    onToken: (token: string) => void,
    onSources: (sources: Citation[]) => void,
    onDone: () => void,
    onError: (err: Error) => void,
    signal?: AbortSignal
  ): Promise<() => void> {
    const user = mockStore.getCurrentUser();
    const tenantId = user.tenant.id;
    const config = MOCK_TENANT_CHAT_RESPONSES[tenantId] || MOCK_TENANT_CHAT_RESPONSES['tenant-acme'];

    const fullResponse = config.answerTemplate(query);
    const words = fullResponse.split(/(\s+)/); // Keep whitespace chunks

    let isAborted = false;
    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    if (signal) {
      signal.addEventListener('abort', () => {
        isAborted = true;
        if (timeoutId) clearTimeout(timeoutId);
      });
    }

    let currentIndex = 0;

    const pump = () => {
      try {
        if (isAborted || signal?.aborted) {
          return;
        }

        if (currentIndex < words.length) {
          const chunk = words[currentIndex];
          currentIndex++;
          onToken(chunk);
          // Realistic token streaming delay: 18-35ms
          timeoutId = setTimeout(pump, Math.floor(Math.random() * 20) + 15);
        } else {
          // Stream completed; emit sources then done
          timeoutId = setTimeout(() => {
            if (!isAborted && !signal?.aborted) {
              onSources(config.citations);
              onDone();
            }
          }, 120);
        }
      } catch (err: unknown) {
        onError(err instanceof Error ? err : new Error(String(err)));
      }
    };

    // Initial slight lag before first token
    timeoutId = setTimeout(pump, 250);

    return () => {
      isAborted = true;
      if (timeoutId) clearTimeout(timeoutId);
    };
  },

  async chatPlain(query: string): Promise<string> {
    await delay(500);
    const user = mockStore.getCurrentUser();
    const tenantId = user.tenant.id;
    const config = MOCK_TENANT_CHAT_RESPONSES[tenantId] || MOCK_TENANT_CHAT_RESPONSES['tenant-acme'];
    return config.answerTemplate(query);
  },

  // --- ADMIN ---
  async getAdminUsers(): Promise<AdminUser[]> {
    await delay(250);
    const user = mockStore.getCurrentUser();
    if (user.role !== 'admin') {
      throw new MockForbiddenError('Administrator access required.');
    }
    return mockStore.getAdminUsersForTenant(user.tenant.id);
  },

  async inviteUser(email: string, role: Role): Promise<AdminUser> {
    await delay(400);
    const user = mockStore.getCurrentUser();
    if (user.role !== 'admin') {
      throw new MockForbiddenError('Administrator access required to invite team members.');
    }
    return mockStore.inviteUser(user.tenant.id, email, role);
  },
};
