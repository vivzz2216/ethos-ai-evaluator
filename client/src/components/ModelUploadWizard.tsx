/**
 * ModelUploadWizard - Multi-step wizard for model upload, classification, testing, and verdict.
 * Supports two upload modes:
 *   1. Link Local Path — backend copies files directly from disk (for large models 1GB+)
 *   2. Browser Upload — standard drag-and-drop via file explorer (for small files)
 */
import React, { useState, useCallback } from 'react';
import {
  Upload, Search, FlaskConical, Shield, CheckCircle, XCircle,
  AlertTriangle, Loader2, ChevronRight, ArrowLeft, Play, RotateCcw,
  FolderOpen, Link, HardDrive,
} from 'lucide-react';
import {
  useModelClassification, useModelScan, useModelTesting,
  useLocalLink, useSessionCreate, useModelRepair,
  type LinkResult,
} from '../hooks/use-model-testing';
import { ModelTestResults } from './ModelTestResults';

interface ModelUploadWizardProps {
  sessionId: string | null;
  onSessionCreated?: (sid: string) => void;
  onClose?: () => void;
}

type WizardStep = 'idle' | 'linking' | 'scanning' | 'classified' | 'testing' | 'results';

const STEP_CONFIG: Record<WizardStep, { label: string; icon: React.ReactNode; color: string }> = {
  idle: { label: 'Load Model', icon: <Upload size={16} />, color: '#888' },
  linking: { label: 'Linking', icon: <Link size={16} />, color: '#06b6d4' },
  scanning: { label: 'Scanning', icon: <Search size={16} />, color: '#3b82f6' },
  classified: { label: 'Classified', icon: <Shield size={16} />, color: '#8b5cf6' },
  testing: { label: 'Testing', icon: <FlaskConical size={16} />, color: '#f97316' },
  results: { label: 'Results', icon: <CheckCircle size={16} />, color: '#22c55e' },
};

const STEPS: WizardStep[] = ['idle', 'linking', 'scanning', 'classified', 'testing', 'results'];

export const ModelUploadWizard: React.FC<ModelUploadWizardProps> = ({ sessionId: propSessionId, onSessionCreated, onClose }) => {
  const [step, setStep] = useState<WizardStep>('idle');
  const [localPath, setLocalPath] = useState('');
  const [maxPrompts, setMaxPrompts] = useState(25);
  const [hfModelName, setHfModelName] = useState('');
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(propSessionId);
  const [linkInfo, setLinkInfo] = useState<LinkResult | null>(null);
  const [globalError, setGlobalError] = useState<string | null>(null);

  // Keep in sync with parent
  const sid = currentSessionId || propSessionId;

  const { scanResult, scan, loading: scanLoading, error: scanError } = useModelScan();
  const { classification, classify, loading: classifyLoading, error: classifyError } = useModelClassification();
  const { result: testResult, runTests, loading: testLoading, error: testError } = useModelTesting();
  const { linkLocal, loading: linkLoading, error: linkError } = useLocalLink();
  const { createSession, loading: sessionLoading } = useSessionCreate();
  const { repairStatus, startRepair, stopPolling: stopRepairPolling, loading: repairLoading, error: repairError } = useModelRepair();

  const isLoading = scanLoading || classifyLoading || testLoading || linkLoading || sessionLoading;
  const error = globalError || scanError || classifyError || testError || linkError;

  // ── Ensure session exists ──────────────────────────────────────────
  const ensureSession = useCallback(async (): Promise<string | null> => {
    if (sid) return sid;
    setGlobalError(null);
    const res = await createSession();
    if (!res) {
      setGlobalError('Failed to create backend session. Is the backend running?');
      return null;
    }
    setCurrentSessionId(res.session_id);
    onSessionCreated?.(res.session_id);
    return res.session_id;
  }, [sid, createSession, onSessionCreated]);

  // ── Link local model directory ─────────────────────────────────────
  const handleLinkLocal = useCallback(async () => {
    if (!localPath.trim()) return;
    setGlobalError(null);
    setStep('linking');

    const sessionId = await ensureSession();
    if (!sessionId) { setStep('idle'); return; }

    const res = await linkLocal(sessionId, localPath.trim());
    if (!res) { setStep('idle'); return; }

    setLinkInfo(res);
    console.log(`[link-local] Linked ${res.file_count} files (${res.total_size_mb} MB) from ${res.source_path}`);

    // Auto-proceed to scan & classify
    setStep('scanning');
    const scanRes = await scan(sessionId);
    if (!scanRes) { setStep('idle'); return; }

    const classRes = await classify(sessionId);
    if (classRes) {
      setStep('classified');
    } else {
      setStep('idle');
    }
  }, [localPath, ensureSession, linkLocal, scan, classify]);

  // ── Scan existing session files ────────────────────────────────────
  const handleScanAndClassify = useCallback(async () => {
    const sessionId = await ensureSession();
    if (!sessionId) return;
    setGlobalError(null);
    setStep('scanning');

    const scanRes = await scan(sessionId);
    if (!scanRes) { setStep('idle'); return; }

    const classRes = await classify(sessionId);
    if (classRes) {
      setStep('classified');
    } else {
      setStep('idle');
    }
  }, [ensureSession, scan, classify]);

  // ── Direct HuggingFace model test (cloud GPU) ────────────────────
  const handleHfDirect = useCallback(async () => {
    if (!hfModelName.trim()) return;
    setGlobalError(null);

    const sessionId = await ensureSession();
    if (!sessionId) return;

    setStep('testing');
    const res = await runTests(sessionId, maxPrompts, hfModelName.trim());
    if (res) {
      setStep('results');
    } else {
      setStep('idle');
    }
  }, [hfModelName, maxPrompts, ensureSession, runTests]);

  const handleRunTests = useCallback(async () => {
    if (!sid) return;
    setStep('testing');
    const res = await runTests(sid, maxPrompts, hfModelName || undefined);
    if (res) {
      setStep('results');
    } else {
      setStep('classified');
    }
  }, [sid, runTests, maxPrompts, hfModelName]);

  const handleReset = useCallback(() => {
    setStep('idle');
    setGlobalError(null);
    setLinkInfo(null);
  }, []);

  // ── Render ─────────────────────────────────────────────────────────
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      background: '#1a1a2e', color: '#e0e0e0',
    }}>
      {/* Header */}
      <div style={{
        padding: '12px 16px', borderBottom: '1px solid #2a2a3e',
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <Shield size={18} color="#8b5cf6" />
        <span style={{ fontWeight: 700, fontSize: 15 }}>ETHOS Model Testing</span>
        <div style={{ flex: 1 }} />
        {sid && <span style={{ fontSize: 10, color: '#555', fontFamily: 'monospace' }}>{sid.slice(0, 8)}</span>}
        {onClose && (
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer', fontSize: 18 }}>×</button>
        )}
      </div>

      {/* Step Indicator */}
      <div style={{
        display: 'flex', alignItems: 'center', padding: '10px 16px',
        gap: 4, borderBottom: '1px solid #2a2a3e', flexWrap: 'wrap',
      }}>
        {STEPS.map((s, i) => {
          const cfg = STEP_CONFIG[s];
          const isActive = s === step;
          const isPast = STEPS.indexOf(step) > i;
          return (
            <React.Fragment key={s}>
              {i > 0 && <ChevronRight size={12} color="#555" />}
              <div style={{
                display: 'flex', alignItems: 'center', gap: 4,
                padding: '4px 8px', borderRadius: 4, fontSize: 11, fontWeight: 500,
                background: isActive ? `${cfg.color}22` : 'transparent',
                color: isActive ? cfg.color : isPast ? '#22c55e' : '#666',
                border: isActive ? `1px solid ${cfg.color}44` : '1px solid transparent',
              }}>
                {isPast ? <CheckCircle size={12} /> : cfg.icon}
                {cfg.label}
              </div>
            </React.Fragment>
          );
        })}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>
        {/* Error Banner */}
        {error && (
          <div style={{
            background: 'rgba(239,68,68,0.1)', border: '1px solid #ef4444',
            borderRadius: 8, padding: '10px 14px', marginBottom: 12,
            fontSize: 13, color: '#f87171', wordBreak: 'break-word',
          }}>
            <AlertTriangle size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
            {error}
          </div>
        )}

        {/* Step: Idle — Link Local Model */}
        {step === 'idle' && (
          <div>
            <div style={{ textAlign: 'center', marginBottom: 20 }}>
              <Shield size={40} color="#8b5cf6" style={{ marginBottom: 10 }} />
              <h3 style={{ margin: '0 0 4px', fontSize: 17 }}>AI Model Ethics Testing</h3>
              <p style={{ color: '#888', fontSize: 12, margin: 0 }}>
                Point to your local model directory and run adversarial tests.
              </p>
            </div>

            {/* Primary: HuggingFace Model Name (Local GPU) */}
            <div style={{
              background: '#1e1e2e', borderRadius: 8, padding: 16, marginBottom: 12,
              border: '1px solid #8b5cf644',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <FlaskConical size={16} color="#8b5cf6" />
                <span style={{ fontWeight: 600, fontSize: 14 }}>HuggingFace Model Name</span>
                <span style={{
                  background: '#22c55e22', color: '#22c55e', padding: '1px 8px',
                  borderRadius: 10, fontSize: 10, fontWeight: 600,
                }}>LOCAL GPU</span>
              </div>
              <p style={{ color: '#888', fontSize: 12, margin: '0 0 10px' }}>
                Enter a HuggingFace model name. The model will be downloaded and loaded
                on your local RTX GPU automatically.
              </p>
              <input
                type="text"
                value={hfModelName}
                onChange={e => setHfModelName(e.target.value)}
                placeholder="e.g. VibeStudio/Nidum-Gemma-2B-Uncensored"
                onKeyDown={e => e.key === 'Enter' && handleHfDirect()}
                style={{ ...inputStyle, marginBottom: 12 }}
              />
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={handleHfDirect}
                  disabled={isLoading || !hfModelName.trim()}
                  style={{
                    ...primaryBtnStyle,
                    flex: 1, justifyContent: 'center',
                    padding: '10px 16px', fontSize: 13,
                    opacity: (!hfModelName.trim() || isLoading) ? 0.5 : 1,
                  }}
                >
                  {isLoading ? <Loader2 size={14} className="spin" /> : <Play size={14} />}
                  Test Model
                </button>
                <button
                  onClick={() => {
                    if (!hfModelName.trim()) return;
                    (async () => {
                      setGlobalError(null);
                      const sessionId = await ensureSession();
                      if (!sessionId) return;
                      setStep('testing');
                      const res = await runTests(sessionId, maxPrompts, hfModelName.trim());
                      if (res) {
                        setStep('results');
                        // Auto-start repair after test completes
                        startRepair(sessionId);
                      } else {
                        setStep('idle');
                      }
                    })();
                  }}
                  disabled={isLoading || !hfModelName.trim()}
                  style={{
                    ...secondaryBtnStyle,
                    flex: 1, justifyContent: 'center',
                    background: '#1e3a5f', border: '1px solid #3b82f644',
                    color: '#60a5fa', padding: '10px 16px', fontSize: 13,
                    opacity: (!hfModelName.trim() || isLoading) ? 0.5 : 1,
                  }}
                >
                  {isLoading ? <Loader2 size={14} className="spin" /> : <RotateCcw size={14} />}
                  Train & Fix Model
                </button>
              </div>
              <div style={{ display: 'flex', gap: 16, marginTop: 10, fontSize: 11, color: '#666' }}>
                <div style={{ flex: 1 }}>
                  <strong style={{ color: '#8b5cf6' }}>Test Model:</strong> Runs 25 ethical prompts → shows score + PDF → you decide to train
                </div>
                <div style={{ flex: 1 }}>
                  <strong style={{ color: '#60a5fa' }}>Train & Fix:</strong> Tests + automatically starts training to fix ethical violations
                </div>
              </div>
              <p style={{ color: '#666', fontSize: 11, margin: '8px 0 0' }}>
                Examples: <code style={{ color: '#8b5cf6' }}>VibeStudio/Nidum-Gemma-2B-Uncensored</code>, <code style={{ color: '#8b5cf6' }}>TinyLlama/TinyLlama-1.1B-Chat-v1.0</code>
              </p>
            </div>

            {/* Secondary: Link Local Path */}
            <div style={{
              background: '#1e1e2e', borderRadius: 8, padding: 16, marginBottom: 12,
              border: '1px solid #3a3a4e',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <FolderOpen size={16} color="#888" />
                <span style={{ fontWeight: 600, fontSize: 14, color: '#aaa' }}>Link Local Model</span>
              </div>
              <p style={{ color: '#666', fontSize: 12, margin: '0 0 10px' }}>
                Or paste a local model folder path. Files are scanned and classified locally.
              </p>
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  type="text"
                  value={localPath}
                  onChange={e => setLocalPath(e.target.value)}
                  placeholder="C:\\Users\\...\\Llama-3-8B-Lexi-Uncensored"
                  onKeyDown={e => e.key === 'Enter' && handleLinkLocal()}
                  style={{ ...inputStyle, flex: 1 }}
                />
                <button
                  onClick={handleLinkLocal}
                  disabled={isLoading || !localPath.trim()}
                  style={{
                    ...secondaryBtnStyle,
                    padding: '8px 16px', fontSize: 13,
                    opacity: (!localPath.trim() || isLoading) ? 0.5 : 1,
                  }}
                >
                  {isLoading ? <Loader2 size={14} className="spin" /> : <HardDrive size={14} />}
                  Link & Scan
                </button>
              </div>
            </div>

            {/* Tertiary: Scan already-uploaded files */}
            {sid && (
              <div style={{
                background: '#1e1e2e', borderRadius: 8, padding: 14,
                border: '1px solid #2a2a3e', marginBottom: 12,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                  <Upload size={14} color="#888" />
                  <span style={{ fontWeight: 500, fontSize: 13, color: '#aaa' }}>Already uploaded via File Explorer?</span>
                </div>
                <button onClick={handleScanAndClassify} disabled={isLoading} style={{ ...secondaryBtnStyle, width: '100%', justifyContent: 'center' }}>
                  {isLoading ? <Loader2 size={14} className="spin" /> : <Search size={14} />}
                  Scan Existing Session Files
                </button>
              </div>
            )}
          </div>
        )}

        {/* Step: Linking */}
        {step === 'linking' && (
          <div style={{ textAlign: 'center', padding: '40px 20px' }}>
            <Loader2 size={40} color="#06b6d4" style={{ animation: 'spin 1s linear infinite', marginBottom: 16 }} />
            <h3 style={{ margin: '0 0 8px', fontSize: 16 }}>Copying model files...</h3>
            <p style={{ color: '#888', fontSize: 13 }}>Linking from: <code>{localPath}</code></p>
            <p style={{ color: '#666', fontSize: 12 }}>Large models may take a moment to copy.</p>
          </div>
        )}

        {/* Step: Scanning */}
        {(step === 'scanning') && isLoading && (
          <div style={{ textAlign: 'center', padding: '40px 20px' }}>
            <Loader2 size={40} color="#3b82f6" style={{ animation: 'spin 1s linear infinite', marginBottom: 16 }} />
            <h3 style={{ margin: '0 0 8px', fontSize: 16 }}>Scanning & Classifying...</h3>
            <p style={{ color: '#888', fontSize: 13 }}>Analyzing file structure, detecting model type...</p>
            {linkInfo && (
              <p style={{ color: '#22c55e', fontSize: 12, marginTop: 8 }}>
                Linked {linkInfo.file_count} files ({linkInfo.total_size_mb} MB)
              </p>
            )}
          </div>
        )}

        {/* Step: Classified */}
        {step === 'classified' && classification && (
          <div>
            {/* Link Summary */}
            {linkInfo && (
              <div style={{
                background: 'rgba(34,197,94,0.08)', border: '1px solid #22c55e44',
                borderRadius: 8, padding: '10px 14px', marginBottom: 12, fontSize: 12,
                display: 'flex', alignItems: 'center', gap: 8,
              }}>
                <CheckCircle size={14} color="#22c55e" />
                <span>Linked <strong>{linkInfo.file_count}</strong> files ({linkInfo.total_size_mb} MB) from <code>{linkInfo.source_path}</code></span>
              </div>
            )}

            {/* Classification Card */}
            <div style={{
              background: '#1e1e2e', borderRadius: 8, padding: 16, marginBottom: 16,
              border: `1px solid ${classification.action === 'REJECT' ? '#ef4444' : '#8b5cf6'}44`,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <Shield size={18} color="#8b5cf6" />
                <span style={{ fontWeight: 700, fontSize: 15 }}>Classification Result</span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 13 }}>
                <div style={infoCardStyle}>
                  <div style={{ color: '#888', fontSize: 11 }}>Model Type</div>
                  <div style={{ fontWeight: 700, fontSize: 16, textTransform: 'uppercase', color: '#8b5cf6' }}>
                    {classification.model_type}
                  </div>
                </div>
                <div style={infoCardStyle}>
                  <div style={{ color: '#888', fontSize: 11 }}>Confidence</div>
                  <div style={{ fontWeight: 700, fontSize: 16, color: classification.confidence > 0.7 ? '#22c55e' : '#eab308' }}>
                    {(classification.confidence * 100).toFixed(0)}%
                  </div>
                </div>
                <div style={infoCardStyle}>
                  <div style={{ color: '#888', fontSize: 11 }}>Runner</div>
                  <div style={{ fontWeight: 500 }}>{classification.runner || 'N/A'}</div>
                </div>
                <div style={infoCardStyle}>
                  <div style={{ color: '#888', fontSize: 11 }}>Security Risk</div>
                  <div style={{
                    fontWeight: 500,
                    color: classification.security_risk === 'high' ? '#ef4444' : classification.security_risk === 'medium' ? '#eab308' : '#22c55e',
                  }}>
                    {classification.security_risk.toUpperCase()}
                  </div>
                </div>
              </div>

              {classification.required_dependencies.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <div style={{ color: '#888', fontSize: 11, marginBottom: 4 }}>Dependencies</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {classification.required_dependencies.map((dep, i) => (
                      <span key={i} style={{
                        background: '#2a2a3e', padding: '2px 8px', borderRadius: 4, fontSize: 11,
                      }}>{dep}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Scan Summary */}
            {scanResult && (
              <div style={{ background: '#1e1e2e', borderRadius: 8, padding: 14, marginBottom: 16, fontSize: 12 }}>
                <div style={{ fontWeight: 600, marginBottom: 8 }}>Scan Summary</div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6 }}>
                  <div style={{ color: '#888' }}>Files: <span style={{ color: '#ccc' }}>{scanResult.file_count}</span></div>
                  <div style={{ color: '#888' }}>Size: <span style={{ color: '#ccc' }}>{scanResult.total_size_mb} MB</span></div>
                  <div style={{ color: '#888' }}>Dirs: <span style={{ color: '#ccc' }}>{scanResult.dir_count}</span></div>
                </div>
                {scanResult.framework_hints.length > 0 && (
                  <div style={{ marginTop: 6, color: '#888' }}>
                    Frameworks: {scanResult.framework_hints.map((h, i) => (
                      <span key={i} style={{ color: '#8b5cf6', marginLeft: 4 }}>{h}</span>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Test Configuration */}
            {classification.action !== 'REJECT' && (
              <div style={{ background: '#1e1e2e', borderRadius: 8, padding: 14, marginBottom: 16 }}>
                <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 10 }}>Test Configuration</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div>
                    <label style={{ fontSize: 12, color: '#888', display: 'block', marginBottom: 4 }}>
                      Max Test Prompts (5-125)
                    </label>
                    <input
                      type="number" min={5} max={125} value={maxPrompts}
                      onChange={e => setMaxPrompts(Math.max(5, Math.min(125, parseInt(e.target.value) || 25)))}
                      style={inputStyle}
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: 12, color: '#888', display: 'block', marginBottom: 4 }}>
                      HuggingFace Model Name (optional, for fallback inference)
                    </label>
                    <input
                      type="text" value={hfModelName}
                      onChange={e => setHfModelName(e.target.value)}
                      placeholder="e.g. sshleifer/tiny-gpt2"
                      style={inputStyle}
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={handleReset} style={secondaryBtnStyle}>
                <ArrowLeft size={14} /> Back
              </button>
              {classification.action !== 'REJECT' ? (
                <button onClick={handleRunTests} disabled={isLoading} style={primaryBtnStyle}>
                  {isLoading ? <Loader2 size={16} className="spin" /> : <Play size={16} />}
                  Run Ethics Tests ({maxPrompts} prompts)
                </button>
              ) : (
                <div style={{ color: '#ef4444', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <XCircle size={16} /> Model rejected: {classification.rejection_reason}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Step: Testing */}
        {step === 'testing' && isLoading && (
          <div style={{ textAlign: 'center', padding: '40px 20px' }}>
            <Loader2 size={40} color="#f97316" style={{ animation: 'spin 1s linear infinite', marginBottom: 16 }} />
            <h3 style={{ margin: '0 0 8px', fontSize: 16 }}>Running Ethics Tests...</h3>
            <p style={{ color: '#888', fontSize: 13 }}>
              Testing {maxPrompts} adversarial prompts across 5 categories...
            </p>
            <p style={{ color: '#666', fontSize: 12, marginTop: 8 }}>
              This may take a few minutes depending on model size.
            </p>
          </div>
        )}

        {/* Step: Results */}
        {step === 'results' && testResult && (
          <div>
            <ModelTestResults
              result={testResult}
              sessionId={sid ?? undefined}
              onRepair={() => { if (sid) startRepair(sid); }}
              repairStatus={repairStatus}
              repairLoading={repairLoading}
              repairError={repairError}
            />
            <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
              <button onClick={handleReset} style={secondaryBtnStyle}>
                <RotateCcw size={14} /> Test Again
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Spinner CSS */}
      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .spin { animation: spin 1s linear infinite; }
      `}</style>
    </div>
  );
};

// ── Styles ───────────────────────────────────────────────────────────

const primaryBtnStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 8,
  background: '#8b5cf6', color: '#fff', border: 'none',
  borderRadius: 8, padding: '10px 20px', fontSize: 14,
  fontWeight: 600, cursor: 'pointer',
};

const secondaryBtnStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6,
  background: '#2a2a3e', color: '#ccc', border: '1px solid #3a3a4e',
  borderRadius: 8, padding: '8px 16px', fontSize: 13,
  fontWeight: 500, cursor: 'pointer',
};

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 12px', fontSize: 13,
  background: '#2a2a3e', border: '1px solid #3a3a4e',
  borderRadius: 6, color: '#e0e0e0', outline: 'none',
  fontFamily: 'monospace',
};

const infoCardStyle: React.CSSProperties = {
  background: '#2a2a3e', borderRadius: 6, padding: '8px 12px',
};

export default ModelUploadWizard;
