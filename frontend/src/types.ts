export interface ChecklistStep {
  title: string;
  action: string;
  source: {
    doc_id: string;
    loc: [number, number];
  };
  caution?: string;
}

export interface ChatResponse {
  checklist: ChecklistStep[];
  meta: {
    disclaimer: string;
    when_to_call_emergency?: string;
  };
  emergency_banner?: string;
}

export interface DocumentSnippet {
  doc_id: string;
  start: number;
  end: number;
  text?: string;
  title?: string;
  page?: number;
}

export interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  response?: ChatResponse;
  timestamp: Date;
}

export interface AuditLog {
  id: string;
  timestamp: Date;
  query: string;
  response?: ChatResponse;
  critic_decision: 'ALLOW' | 'BLOCK';
  critic_reasons: string[];
  blocked_content?: string;
}

export interface AdminAuth {
  isAuthenticated: boolean;
  token?: string;
}

export interface ScenarioShortcut {
  id: string;
  label: string;
  query: string;
  icon: string;
}