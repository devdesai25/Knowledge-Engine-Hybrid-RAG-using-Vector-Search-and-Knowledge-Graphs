import { mockApi } from './mocks/mockApi';
import { authApi } from './auth';
import { documentsApi } from './documents';
import { chatApi } from './chat';
import { adminApi } from './admin';
import {
  LoginRequest,
  LoginResponse,
  User,
  DocumentItem,
  UploadResponse,
  Citation,
  AdminUser,
  Role,
} from '@/types';

export const isMockMode = import.meta.env.VITE_USE_MOCKS === 'true';

export const api = {
  auth: {
    login: async (credentials: LoginRequest): Promise<LoginResponse> => {
      if (isMockMode) {
        return mockApi.login(credentials);
      }
      return authApi.login(credentials);
    },
    getMe: async (): Promise<User> => {
      if (isMockMode) {
        return mockApi.getMe();
      }
      return authApi.getMe();
    },
    logout: (): void => {
      authApi.logout();
    },
  },

  documents: {
    getDocuments: async (): Promise<DocumentItem[]> => {
      if (isMockMode) {
        return mockApi.getDocuments();
      }
      return documentsApi.getDocuments();
    },
    uploadDocuments: async (files: File[]): Promise<UploadResponse> => {
      if (isMockMode) {
        return mockApi.uploadDocuments(files);
      }
      return documentsApi.uploadDocuments(files);
    },
    deleteDocument: async (id: string): Promise<{ success: boolean; id: string }> => {
      if (isMockMode) {
        return mockApi.deleteDocument(id);
      }
      return documentsApi.deleteDocument(id);
    },
  },

  chat: {
    streamChat: async (
      query: string,
      onToken: (token: string) => void,
      onSources: (sources: Citation[]) => void,
      onDone: () => void,
      onError: (err: Error) => void,
      signal?: AbortSignal
    ): Promise<() => void> => {
      if (isMockMode) {
        return mockApi.streamChat(query, onToken, onSources, onDone, onError, signal);
      }
      return chatApi.streamChat(query, onToken, onSources, onDone, onError, signal);
    },
    chatPlain: async (query: string): Promise<string> => {
      if (isMockMode) {
        return mockApi.chatPlain(query);
      }
      return chatApi.chatPlain(query);
    },
  },

  admin: {
    getUsers: async (): Promise<AdminUser[]> => {
      if (isMockMode) {
        return mockApi.getAdminUsers();
      }
      return adminApi.getUsers();
    },
    inviteUser: async (email: string, role: Role): Promise<AdminUser> => {
      if (isMockMode) {
        return mockApi.inviteUser(email, role);
      }
      return adminApi.inviteUser(email, role);
    },
  },
};

export { ApiError } from './client';
export { SEEDED_USERS } from './mocks/seedData';
export { mockStore } from './mocks/mockStore';
