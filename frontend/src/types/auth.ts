export type Role = 'admin' | 'member';

export interface Tenant {
  id: string;
  name: string;
}

export interface User {
  id: string;
  email: string;
  role: Role;
  tenant: Tenant;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  user: User;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginRequest) => Promise<void>;
  switchUser: (user: User, token?: string) => void;
  logout: () => void;
}
