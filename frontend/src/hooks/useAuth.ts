import { create } from 'zustand';
import { User, LoginRequest, AuthState } from '@/types';
import { storage } from '@/lib/storage';

interface AuthStore extends AuthState {
  setLoading: (loading: boolean) => void;
  setUserAndToken: (user: User, token: string) => void;
}

// Initial state loaded safely from storage
const initialToken = storage.getToken();
const initialUser = storage.getUser();

export const useAuth = create<AuthStore>((set) => ({
  user: initialUser,
  token: initialToken,
  isAuthenticated: Boolean(initialToken && initialUser),
  isLoading: false,

  setLoading: (loading: boolean) => set({ isLoading: loading }),

  setUserAndToken: (user: User, token: string) => {
    storage.setToken(token);
    storage.setUser(user);
    set({
      user,
      token,
      isAuthenticated: true,
      isLoading: false,
    });
  },

  login: async (_credentials: LoginRequest) => {
    // login will be called via the api abstraction layer
  },

  switchUser: (user: User, token = 'mock-dev-token') => {
    storage.setToken(token);
    storage.setUser(user);
    set({
      user,
      token,
      isAuthenticated: true,
      isLoading: false,
    });
  },

  logout: () => {
    storage.clearAuth();
    set({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,
    });
    // Redirect to login if in browser
    if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
  },
}));
