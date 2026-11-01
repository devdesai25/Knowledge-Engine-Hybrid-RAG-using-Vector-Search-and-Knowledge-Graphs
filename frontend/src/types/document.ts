export type DocumentStatus = 'processing' | 'ready' | 'failed';

export interface DocumentItem {
  id: string;
  filename: string;
  status: DocumentStatus;
  uploaded_by: string;
  created_at: string;
  chunks?: number;
  error?: string;
  tenant_id?: string;
}

export interface UploadDetail {
  filename: string;
  status: 'success' | 'failed';
  chunks?: number;
  error?: string;
}

export interface UploadResponse {
  uploaded: number;
  failed: number;
  details: UploadDetail[];
}

export const SUPPORTED_FILE_EXTENSIONS = [
  '.pdf',
  '.docx',
  '.xlsx',
  '.pptx',
  '.txt',
  '.md',
  '.html',
  '.csv',
  '.json',
  '.epub',
  '.eml',
] as const;

export type SupportedFileExtension = (typeof SUPPORTED_FILE_EXTENSIONS)[number];
