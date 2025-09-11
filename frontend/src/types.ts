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
  query_hash?: string;
  response?: ChatResponse;
  critic_decision: {
    status: 'ALLOW' | 'BLOCK';
    reasons: string[];
    fixes?: string[];
    emergency_detected: boolean;
    requires_emergency_banner?: boolean;
  };
  response_blocked: boolean;
  emergency_detected: boolean;
  conversation_id?: string;
  response_time_ms?: number;
  llm_provider?: string;
  harmony_tokens_used?: number;
  system_metrics?: {
    cpu_percent?: number;
    memory_percent?: number;
    memory_used_mb?: number;
    disk_usage_percent?: number;
  };
}

export interface SystemHealth {
  timestamp: Date;
  cpu_percent?: number;
  memory_percent?: number;
  memory_used_mb?: number;
  disk_usage_percent?: number;
  llm_provider_status: string;
  corpus_db_status: string;
}

export interface PerformanceMetric {
  timestamp: Date;
  endpoint: string;
  response_time_ms: number;
  status_code: number;
  error_message?: string;
}

export interface HarmonyDebugData {
  timestamp: Date;
  query: string;
  harmony_debug_data: any;
  harmony_tokens_used?: number;
}

export interface AdminStats {
  total_interactions: number;
  blocked_responses: number;
  emergency_detections: number;
  recent_activity_24h: number;
  block_rate: number;
  emergency_rate: number;
  query_patterns: Array<{
    query_hash: string;
    frequency: number;
    last_seen: string;
    avg_response_time: number;
  }>;
  provider_usage: Array<{
    llm_provider: string;
    usage_count: number;
    avg_response_time: number;
  }>;
  recent_system_health: {
    avg_cpu?: number;
    avg_memory?: number;
    avg_disk?: number;
  };
  performance_metrics: {
    endpoint_performance: Array<{
      endpoint: string;
      avg_response_time: number;
      min_response_time: number;
      max_response_time: number;
      request_count: number;
    }>;
    status_code_distribution: Array<{
      status_code: number;
      count: number;
    }>;
  };
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