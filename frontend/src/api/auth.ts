import { apiClient } from './client';
import { LoginRequest, LoginResponse, User } from '@/types';
import { storage } from '@/lib/storage';

export const authApi = {
  login: async (credentials: LoginRequest): Promise<LoginResponse> => {
    // Note: If backend expects OAuth2 form data vs JSON:
    // User requested: POST /auth/login { email, password } -> { access_token, user }
    const response = await apiClient<LoginResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify(credentials),
      requiresAuth: false,
    });
    if (response.access_token) {
      storage.setToken(response.access_token);
      storage.setUser(response.user);
    }
    return response;
  },

  getMe: async (): Promise<User> => {
    return apiClient<User>('/me', {
      method: 'GET',
    });
  },

  logout: (): void => {
    storage.clearAuth();
  },
};
