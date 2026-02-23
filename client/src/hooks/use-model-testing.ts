/**
 * React hooks for the Model Processing Pipeline API.
 * Provides upload, classify, test, purify, and management operations.
 */
import { useState, useCallback, useRef } from 'react';

const API_BASE = 'http://localhost:8000/api';

// ── Types ────────────────────────────────────────────────────────────

export interface ModelClassification {
  model_type: string;
  runner: string | null;
  confidence: number;
  architecture: string | null;
  entrypoint: string | null;
  endpoint: string | null;
  action: string;
  rejection_reason: string | null;
  required_dependencies: string[];
  security_risk: string;
  details: Record<string, any>;
}

export interface ScanResult {
  file_tree: string[];
  extensions: Record<string, number>;
  total_size: number;
  total_size_mb: number;
  file_count: number;
  dir_count: number;
  suspicious_files: string[];
  framework_hints: string[];
  flags: Record<string, any>;
}

export interface ViolationScores {
  harm: number;
  bias: number;
  jailbreak: boolean;
  privacy_violation: boolean;
  misinformation: number;
  severity: string;
  confidence: number;
  refused: boolean;
  explanation: string;
}

export interface TestRecord {
  test_id: string;
  model_id: string;
  timestamp: string;
  category: string;
  prompt: string;
  response: string;
  scores: ViolationScores;
  verdict: string;
}

export interface Verdict {
  verdict: string;
  reason: string;
  total_tests: number;
  pass_count: number;
  pass_rate: number;
  violations: Record<string, number>;
  category_breakdown: Record<string, { total: number; pass: number; warn: number; fail: number }>;
  purified?: boolean;
  fix_rate?: number;
}

export interface ProcessingResult {
  state: string;
  context: {
    session_id: string;
    project_dir: string;
    scan_result: ScanResult | null;
    classification: ModelClassification | null;
    install_result: any;
    test_summary: { total_tests: number; records: TestRecord[] } | null;
    verdict: Verdict | null;
    purification_result: any;
    errors: string[];
    started_at: string;
    completed_at: string | null;
    duration_seconds: number;
  };
  state_log: { from: string; to: string; timestamp: string }[];
}

export interface ModelStatus {
  session_id: string;
  processing_state: string;
  classification: ModelClassification | null;
  verdict: Verdict | null;
  has_results: boolean;
}

export interface ModelListItem {
  session_id: string;
  project_dir: string;
  processing_state: string;
  classification: ModelClassification | null;
  has_results: boolean;
}

// ── Hook: useModelClassification ─────────────────────────────────────

export function useModelClassification() {
  const [classification, setClassification] = useState<ModelClassification | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const classify = useCallback(async (sessionId: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/model/${sessionId}/classify`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      const data: ModelClassification = await res.json();
      setClassification(data);
      return data;
    } catch (e: any) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { classification, classify, loading, error };
}

// ── Hook: useModelScan ───────────────────────────────────────────────

export function useModelScan() {
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const scan = useCallback(async (sessionId: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/model/${sessionId}/scan`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      const data: ScanResult = await res.json();
      setScanResult(data);
      return data;
    } catch (e: any) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { scanResult, scan, loading, error };
}

// ── Hook: useSessionCreate ───────────────────────────────────────────

export function useSessionCreate() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createSession = useCallback(async (): Promise<{ session_id: string; project_dir: string } | null> => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/session/create`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      return await res.json();
    } catch (e: any) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { createSession, loading, error };
}

// ── Hook: useLocalLink ──────────────────────────────────────────────

export interface LinkResult {
  message: string;
  source_path: string;
  linked_files: string[];
  file_count: number;
  total_size_mb: number;
  project_dir: string;
}

export function useLocalLink() {
  const [linkResult, setLinkResult] = useState<LinkResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const linkLocal = useCallback(async (sessionId: string, localPath: string) => {
    setLoading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('local_path', localPath);
      const res = await fetch(`${API_BASE}/session/${sessionId}/link-local`, {
        method: 'POST',
        body: form,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      const data: LinkResult = await res.json();
      setLinkResult(data);
      return data;
    } catch (e: any) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { linkResult, linkLocal, loading, error };
}

// ── Hook: useModelTesting ────────────────────────────────────────────

export function useModelTesting() {
  const [result, setResult] = useState<ProcessingResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runTests = useCallback(async (
    sessionId: string,
    maxPrompts: number = 25,
    hfModelName?: string,
  ) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ max_prompts: String(maxPrompts) });
      if (hfModelName) params.set('hf_model_name', hfModelName);
      const res = await fetch(`${API_BASE}/model/${sessionId}/test?${params}`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      const data: ProcessingResult = await res.json();
      setResult(data);
      return data;
    } catch (e: any) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const getResults = useCallback(async (sessionId: string) => {
    try {
      const res = await fetch(`${API_BASE}/model/${sessionId}/test-results`);
      if (!res.ok) return null;
      const data: ProcessingResult = await res.json();
      setResult(data);
      return data;
    } catch {
      return null;
    }
  }, []);

  return { result, runTests, getResults, loading, error };
}

// ── Hook: useModelStatus ─────────────────────────────────────────────

export function useModelStatus() {
  const [status, setStatus] = useState<ModelStatus | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = useCallback(async (sessionId: string) => {
    try {
      const res = await fetch(`${API_BASE}/model/${sessionId}/status`);
      if (!res.ok) return null;
      const data: ModelStatus = await res.json();
      setStatus(data);
      return data;
    } catch {
      return null;
    }
  }, []);

  const startPolling = useCallback((sessionId: string, intervalMs: number = 2000) => {
    stopPolling();
    pollingRef.current = setInterval(() => fetchStatus(sessionId), intervalMs);
  }, [fetchStatus]);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  return { status, fetchStatus, startPolling, stopPolling };
}

// ── Hook: useModelManagement ─────────────────────────────────────────

export function useModelManagement() {
  const [models, setModels] = useState<ModelListItem[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchModels = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/models`);
      if (!res.ok) return;
      const data = await res.json();
      setModels(data.models || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  const approveModel = useCallback(async (sessionId: string) => {
    const res = await fetch(`${API_BASE}/model/${sessionId}/approve`, { method: 'POST' });
    if (res.ok) await fetchModels();
    return res.ok;
  }, [fetchModels]);

  const rejectModel = useCallback(async (sessionId: string, reason?: string) => {
    const params = reason ? `?reason=${encodeURIComponent(reason)}` : '';
    const res = await fetch(`${API_BASE}/model/${sessionId}/reject${params}`, { method: 'POST' });
    if (res.ok) await fetchModels();
    return res.ok;
  }, [fetchModels]);

  const purifyModel = useCallback(async (sessionId: string) => {
    const res = await fetch(`${API_BASE}/model/${sessionId}/purify`, { method: 'POST' });
    return res.ok ? await res.json() : null;
  }, []);

  return { models, fetchModels, approveModel, rejectModel, purifyModel, loading };
}

// ── Hook: useModelRepair (LoRA Training) ─────────────────────────────

export interface RepairStatus {
  status: 'idle' | 'running' | 'in_progress' | 'completed' | 'failed';
  progress: {
    status?: string;
    stage?: string;
    round?: number;
    model?: string;
    current?: number;
    total?: number;
  };
  result: {
    outcome: string;
    reason?: string;
    final_pass_rate: number;
    best_pass_rate?: number;
    best_round?: number;
    rounds_completed: number;
    round_history: any[];
    total_duration_seconds?: number;
    balanced_patches_generated?: number;
    train_jsonl_path?: string;
  } | null;
  error: string | null;
}

export function useModelRepair() {
  const [repairStatus, setRepairStatus] = useState<RepairStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startRepair = useCallback(async (sessionId: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/model/${sessionId}/repair`, { method: 'POST' });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(errData.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setRepairStatus({ status: 'running', progress: { stage: 'starting', round: 0 }, result: null, error: null });

      // Start polling
      pollingRef.current = setInterval(async () => {
        try {
          const pollRes = await fetch(`${API_BASE}/model/${sessionId}/repair-status`);
          if (pollRes.ok) {
            const status: RepairStatus = await pollRes.json();
            setRepairStatus(status);
            if (status.status === 'completed' || status.status === 'failed') {
              stopPolling();
              setLoading(false);
            }
          }
        } catch {
          // ignore polling errors
        }
      }, 3000);

      return data;
    } catch (e: any) {
      setError(e.message);
      setLoading(false);
      return null;
    }
  }, []);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const fetchRepairStatus = useCallback(async (sessionId: string) => {
    try {
      const res = await fetch(`${API_BASE}/model/${sessionId}/repair-status`);
      if (!res.ok) return null;
      const data: RepairStatus = await res.json();
      setRepairStatus(data);
      return data;
    } catch {
      return null;
    }
  }, []);

  return { repairStatus, startRepair, fetchRepairStatus, stopPolling, loading, error };
}

// ── Hook: useAdversarialPrompts ──────────────────────────────────────

export function useAdversarialPrompts() {
  const [prompts, setPrompts] = useState<{ id: string; category: string; prompt: string }[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});

  const fetchPrompts = useCallback(async (category?: string) => {
    try {
      const url = category
        ? `${API_BASE}/prompts/adversarial?category=${category}`
        : `${API_BASE}/prompts/adversarial`;
      const res = await fetch(url);
      if (!res.ok) return;
      const data = await res.json();
      setPrompts(data.prompts || []);
      if (data.counts) setCounts(data.counts);
    } catch {
      // ignore
    }
  }, []);

  return { prompts, counts, fetchPrompts };
}
