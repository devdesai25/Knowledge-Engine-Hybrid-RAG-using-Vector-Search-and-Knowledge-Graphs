export interface Citation {
  document_id: string;
  filename: string;
  page_no?: number;
  headings?: string[];
  text: string;
  score?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  timestamp: number;
  isStreaming?: boolean;
  error?: string;
}

export interface ChatRequest {
  query: string;
}

export type ChatStreamEvent =
  | { type: 'token'; token: string }
  | { type: 'sources'; sources: Citation[] }
  | { type: 'done' }
  | { type: 'error'; message: string };
