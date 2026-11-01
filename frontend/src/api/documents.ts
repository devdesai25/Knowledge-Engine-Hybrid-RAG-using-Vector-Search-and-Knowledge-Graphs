import { apiClient } from './client';
import { DocumentItem, UploadResponse } from '@/types';

export const documentsApi = {
  getDocuments: async (): Promise<DocumentItem[]> => {
    return apiClient<DocumentItem[]>('/documents', {
      method: 'GET',
    });
  },

  uploadDocuments: async (files: File[]): Promise<UploadResponse> => {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });

    return apiClient<UploadResponse>('/upload', {
      method: 'POST',
      body: formData,
    });
  },

  deleteDocument: async (id: string): Promise<{ success: boolean; id: string }> => {
    await apiClient<void>(`/documents/${id}`, {
      method: 'DELETE',
    });
    return { success: true, id };
  },
};
