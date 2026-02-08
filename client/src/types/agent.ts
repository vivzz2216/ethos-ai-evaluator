/**
 * Types for the AI Agent system.
 */

export interface AgentConfig {
  api_key: string;
  model: string;
  temperature: number;
  max_iterations: number;
  auto_approve_reads: boolean;
  auto_approve_writes: boolean;
  auto_approve_deletes: boolean;
  auto_approve_terminal: boolean;
  max_tokens: number;
  has_key: boolean;
}

export type AgentEventType =
  | 'content'
  | 'status'
  | 'tool_call'
  | 'tool_executing'
  | 'tool_result'
  | 'done'
  | 'error'
  | 'stream_end'
  | 'cancelled';

export interface AgentEvent {
  type: AgentEventType;
  text?: string;
  message?: string;
  tool?: string;
  arguments?: Record<string, any>;
  result?: Record<string, any>;
  tool_call_id?: string;
  needs_approval?: boolean;
  iteration?: number;
  iterations?: number;
  total_tokens?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'tool' | 'status' | 'error';
  content: string;
  timestamp: number;
  toolCalls?: ToolCallInfo[];
  isStreaming?: boolean;
}

export interface ToolCallInfo {
  id: string;
  tool: string;
  arguments: Record<string, any>;
  result?: Record<string, any>;
  status: 'pending' | 'executing' | 'done' | 'error';
  needs_approval?: boolean;
}
