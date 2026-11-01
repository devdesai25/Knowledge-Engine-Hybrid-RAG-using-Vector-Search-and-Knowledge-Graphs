import { apiClient } from './client';
import { AdminUser, InviteUserRequest, Role } from '@/types';

export const adminApi = {
  getUsers: async (): Promise<AdminUser[]> => {
    return apiClient<AdminUser[]>('/admin/users', {
      method: 'GET',
    });
  },

  inviteUser: async (email: string, role: Role): Promise<AdminUser> => {
    const payload: InviteUserRequest = { email, role };
    return apiClient<AdminUser>('/admin/users/invite', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
};
