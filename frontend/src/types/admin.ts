import { Role } from './auth';

export interface AdminUser {
  id: string;
  email: string;
  role: Role;
  created_at: string;
  tenant_id: string;
}

export interface InviteUserRequest {
  email: string;
  role: Role;
}
