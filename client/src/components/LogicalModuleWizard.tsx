/**
 * LogicalModuleWizard
 * ====================
 * Full 4-step wizard that mirrors the Social Awareness / Ethics Module flow:
 *   Step 1 — Enter HuggingFace model name
 *   Step 2 — Pre-test (how model CURRENTLY responds to logical prompts)
 *            → Download pre-test PDF report
 *   Step 3 — Logical Injection (LoRA fine-tuning for abstention)
 *   Step 4 — Post-test (same prompts after injection)
 *            → Download post-test PDF + comparison PDF
 */
import React, { useState, useCallback, useRef } from 'react';
import {
    Atom, Play, RotateCcw, Download, Loader2,
    CheckCircle, XCircle, AlertTriangle, ChevronRight,
    FlaskConical, Zap, BarChart2, ArrowLeft,
} from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────

interface SignalResult {
    T: number; A: number; S: number; V: number | null; C: number;
}
interface PromptResult {
    id: string; category: string; prompt: string; response: string;
    action: 'ANSWER' | 'HEDGE' | 'ABSTAIN';
    confidence: number; signals: SignalResult;
    expected_action: string; correct_behavior: boolean; explanation: string;
}
interface PhaseResult {
    session_id: string; model_name: string; phase: string;
    evaluated_at: string; results: PromptResult[];
    summary: {
        total: number; pass_rate: number; correct_behavior: number;
        answered: number; hedged: number; abstained: number;
        avg_confidence: number; by_category: Record<string, { total: number; correct: number }>;
    };
}
type WizardStep = 'idle' | 'pre-running' | 'pre-done' | 'injecting' | 'post-done';

// ─── Config ───────────────────────────────────────────────────────────────────

const BASE = 'http://localhost:8000';

const ACTION_CFG = {
    ANSWER: { bg: '#d4edda', text: '#155724', icon: '✅', label: 'ANSWER' },
    HEDGE: { bg: '#fff3cd', text: '#856404', icon: '⚠️', label: 'HEDGE' },
    ABSTAIN: { bg: '#f8d7da', text: '#721c24', icon: '🚫', label: 'ABSTAIN' },
};

const CAT_COLORS: Record<string, string> = {
    tokenisation: '#818cf8',
    pattern_override: '#f472b6',
    reasoning: '#60a5fa',
    spatial: '#34d399',
    hallucination: '#f87171',
    misconception: '#fbbf24',
    logic: '#a78bfa',
};

const STEPS: { key: WizardStep; label: string }[] = [
    { key: 'idle', label: 'Select Model' },
    { key: 'pre-running', label: 'Pre-Test' },
    { key: 'pre-done', label: 'Pre-Test Done' },
    { key: 'injecting', label: 'Injecting' },
    { key: 'post-done', label: 'Post-Test Done' },
];

// ─── Helper components ────────────────────────────────────────────────────────

const Bar: React.FC<{ val: number; label: string }> = ({ val, label }) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 3 }}>
        <span style={{ width: 16, fontSize: 10, fontFamily: 'monospace', fontWeight: 700, color: '#888' }}>{label}</span>
        <div style={{ flex: 1, background: '#2a2a3e', borderRadius: 4, height: 6 }}>
            <div style={{
                width: `${val * 100}%`, height: 6, borderRadius: 4,
                background: val >= 0.85 ? '#22c55e' : val >= 0.5 ? '#eab308' : '#ef4444',
                transition: 'width 0.4s',
            }} />
        </div>
        <span style={{ width: 32, fontSize: 10, fontFamily: 'monospace', color: '#aaa', textAlign: 'right' }}>
            {(val * 100).toFixed(0)}%
        </span>
    </div>
);

const ActionBadge: React.FC<{ action: string; correct: boolean }> = ({ action, correct }) => {
    const cfg = ACTION_CFG[action as keyof typeof ACTION_CFG] ?? ACTION_CFG.HEDGE;
    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 4,
            background: cfg.bg, color: cfg.text,
            padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 700,
        }}>
            {cfg.icon} {cfg.label} {correct ? '✓' : '✗'}
        </span>
    );
};

const SummaryBar: React.FC<{ label: string; value: string | number; color?: string }> = ({ label, value, color }) => (
    <div style={{ background: '#2a2a3e', borderRadius: 8, padding: '10px 14px', textAlign: 'center' }}>
        <div style={{ fontSize: 22, fontWeight: 800, color: color ?? '#e0e0e0' }}>{value}</div>
        <div style={{ fontSize: 11, color: '#888', marginTop: 2 }}>{label}</div>
    </div>
);

const PhaseCard: React.FC<{
    result: PhaseResult; label: string; onDownload: () => void; downloadLabel: string;
}> = ({ result, label, onDownload, downloadLabel }) => {
    const s = result.summary;
    const passColor = s.pass_rate >= 70 ? '#22c55e' : s.pass_rate >= 40 ? '#eab308' : '#ef4444';
    return (
        <div style={{ background: '#1e1e2e', borderRadius: 10, padding: 16, border: '1px solid #3a3a5e', marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <FlaskConical size={16} color="#8b5cf6" />
                <span style={{ fontWeight: 700, fontSize: 15 }}>{label}</span>
                <span style={{ flex: 1 }} />
                <span style={{ fontSize: 11, color: '#888' }}>
                    Model: {result.model_name}
                </span>
            </div>

            {/* Summary stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginBottom: 14 }}>
                <SummaryBar label="Pass Rate" value={`${s.pass_rate}%`} color={passColor} />
                <SummaryBar label="✅ Answered" value={s.answered} color="#22c55e" />
                <SummaryBar label="⚠️ Hedged" value={s.hedged} color="#eab308" />
                <SummaryBar label="🚫 Abstained" value={s.abstained} color="#ef4444" />
            </div>

            {/* Per-prompt results */}
            <div style={{ maxHeight: 320, overflowY: 'auto' }}>
                {result.results.map((r) => (
                    <div key={r.id} style={{
                        borderRadius: 8, padding: '10px 12px', marginBottom: 8,
                        background: r.correct_behavior ? 'rgba(34,197,94,0.06)' : 'rgba(239,68,68,0.06)',
                        border: `1px solid ${r.correct_behavior ? '#22c55e33' : '#ef444433'}`,
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                            <span style={{
                                fontSize: 10,
                                background: (CAT_COLORS[r.category] ?? '#888') + '22',
                                padding: '1px 6px', borderRadius: 6,
                                color: CAT_COLORS[r.category] ?? '#888',
                                border: `1px solid ${(CAT_COLORS[r.category] ?? '#888')}44`,
                                fontWeight: 600,
                            }}>
                                {r.category}
                            </span>
                            <ActionBadge action={r.action} correct={r.correct_behavior} />
                        </div>
                        <div style={{ fontSize: 12, color: '#ccc', marginBottom: 4 }}>{r.prompt}</div>
                        {/* Before/after response */}
                        <div style={{
                            fontSize: 11, color: '#aaa', background: '#12121f',
                            borderRadius: 6, padding: '6px 8px', fontStyle: 'italic', marginBottom: 6,
                        }}>
                            {r.response || <em>No response</em>}
                        </div>
                        <Bar val={r.signals?.C ?? r.confidence} label="C" />
                        <div style={{ fontSize: 10, color: '#666', marginTop: 2 }}>
                            Expected: <strong style={{ color: '#a78bfa' }}>{r.expected_action}</strong>
                            &nbsp;·&nbsp;{r.explanation?.slice(0, 80)}
                        </div>
                    </div>
                ))}
            </div>

            {/* Download */}
            <button onClick={onDownload} style={{
                marginTop: 12, display: 'flex', alignItems: 'center', gap: 6,
                background: '#1e3a5f', border: '1px solid #3b82f644', borderRadius: 8,
                color: '#60a5fa', padding: '9px 16px', fontSize: 12, fontWeight: 600,
                cursor: 'pointer', width: '100%', justifyContent: 'center',
            }}>
                <Download size={14} /> {downloadLabel}
            </button>
        </div>
    );
};

const ComparisonCard: React.FC<{ pre: PhaseResult; post: PhaseResult; onDownload: () => void }> = ({ pre, post, onDownload }) => {
    const preS = pre.summary; const postS = post.summary;
    const diff = postS.pass_rate - preS.pass_rate;
    return (
        <div style={{ background: '#1e1e2e', borderRadius: 10, padding: 16, border: '1px solid #6366f144', marginBottom: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
                <BarChart2 size={16} color="#6366f1" />
                <span style={{ fontWeight: 700, fontSize: 15 }}>Before vs After Comparison</span>
            </div>

            {/* Delta row */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 14 }}>
                <SummaryBar label="Pass Rate Before" value={`${preS.pass_rate}%`} color="#ef4444" />
                <SummaryBar label="Pass Rate After" value={`${postS.pass_rate}%`} color="#22c55e" />
                <SummaryBar label="Improvement" value={`${diff >= 0 ? '+' : ''}${diff.toFixed(1)}%`}
                    color={diff >= 0 ? '#22c55e' : '#ef4444'} />
            </div>

            {/* Per-prompt before/after comparison — card rows */}
            <div style={{ maxHeight: 480, overflowY: 'auto' }}>
                {pre.results.map((pr, i) => {
                    const po: any = post.results[i] || {};
                    const preResp = pr.response?.trim() || '(no response)';
                    const postResp = (po.response ?? '').trim() || '(no response)';
                    const changed = pr.action !== po.action || pr.correct_behavior !== po.correct_behavior;
                    return (
                        <div key={pr.id} style={{
                            borderRadius: 8, padding: '10px 12px', marginBottom: 8,
                            background: changed ? 'rgba(99,102,241,0.06)' : '#12121f',
                            border: `1px solid ${changed ? '#6366f133' : '#2a2a3e'}`,
                        }}>
                            {/* header row */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, flexWrap: 'wrap' }}>
                                <span style={{ fontSize: 10, color: '#555', fontFamily: 'monospace' }}>{pr.id}</span>
                                <span style={{
                                    fontSize: 10, padding: '1px 6px', borderRadius: 6,
                                    background: (CAT_COLORS[pr.category] ?? '#888') + '22',
                                    color: CAT_COLORS[pr.category] ?? '#888',
                                    border: `1px solid ${(CAT_COLORS[pr.category] ?? '#888')}44`,
                                    fontWeight: 600,
                                }}>{pr.category}</span>
                                {changed && <span style={{ fontSize: 10, color: '#a78bfa', fontWeight: 700 }}>↑ changed</span>}
                            </div>
                            {/* prompt */}
                            <div style={{ fontSize: 12, color: '#ccc', marginBottom: 8, lineHeight: 1.4 }}>
                                {pr.prompt}
                            </div>
                            {/* before / after side by side */}
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                                {/* BEFORE */}
                                <div style={{ background: '#1a1a2e', borderRadius: 6, padding: '8px 10px', borderLeft: '3px solid #ef4444' }}>
                                    <div style={{ fontSize: 10, color: '#ef4444', fontWeight: 700, marginBottom: 4 }}>BEFORE INJECTION</div>
                                    <ActionBadge action={pr.action} correct={pr.correct_behavior} />
                                    <div style={{
                                        fontSize: 11, color: '#aaa', marginTop: 6,
                                        background: '#12121f', borderRadius: 4,
                                        padding: '5px 7px', fontStyle: 'italic',
                                        wordBreak: 'break-word', lineHeight: 1.4,
                                    }}>
                                        {preResp.length > 200 ? preResp.slice(0, 200) + '…' : preResp}
                                    </div>
                                    <div style={{ fontSize: 10, color: '#555', marginTop: 4 }}>
                                        Confidence: <strong style={{ color: '#a78bfa' }}>{((pr.confidence ?? 0) * 100).toFixed(0)}%</strong>
                                    </div>
                                </div>
                                {/* AFTER */}
                                <div style={{ background: '#1a1a2e', borderRadius: 6, padding: '8px 10px', borderLeft: '3px solid #22c55e' }}>
                                    <div style={{ fontSize: 10, color: '#22c55e', fontWeight: 700, marginBottom: 4 }}>AFTER INJECTION</div>
                                    <ActionBadge action={po.action || '?'} correct={po.correct_behavior ?? false} />
                                    <div style={{
                                        fontSize: 11, color: '#aaa', marginTop: 6,
                                        background: '#12121f', borderRadius: 4,
                                        padding: '5px 7px', fontStyle: 'italic',
                                        wordBreak: 'break-word', lineHeight: 1.4,
                                    }}>
                                        {postResp.length > 200 ? postResp.slice(0, 200) + '…' : postResp}
                                    </div>
                                    <div style={{ fontSize: 10, color: '#555', marginTop: 4 }}>
                                        Confidence: <strong style={{ color: '#22c55e' }}>{((po.confidence ?? 0) * 100).toFixed(0)}%</strong>
                                    </div>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            <button onClick={onDownload} style={{
                marginTop: 14, display: 'flex', alignItems: 'center', gap: 6,
                background: '#6366f1', border: 'none', borderRadius: 8,
                color: '#fff', padding: '9px 16px', fontSize: 12, fontWeight: 600,
                cursor: 'pointer', width: '100%', justifyContent: 'center',
            }}>
                <Download size={14} /> Download Comparison Report PDF
            </button>
        </div>
    );
};

// ─── Main wizard ──────────────────────────────────────────────────────────────

export const LogicalModuleWizard: React.FC = () => {
    const [step, setStep] = useState<WizardStep>('idle');
    const [modelName, setModelName] = useState('');
    const [maxPrompts, setMaxPrompts] = useState(36);
    const [error, setError] = useState<string | null>(null);
    const [preResult, setPreResult] = useState<PhaseResult | null>(null);
    const [postResult, setPostResult] = useState<PhaseResult | null>(null);
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [injectProgress, setInjectProgress] = useState<{ stage: string; pct: number }>({ stage: '', pct: 0 });
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // ── download helper ───────────────────────────────────────────────────────
    const download = (url: string, filename: string) => {
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    };

    const mn = modelName.replace(/\//g, '_');

    // ── Step 1 → 2: Run pre-test ──────────────────────────────────────────────
    const handlePreTest = useCallback(async () => {
        if (!modelName.trim()) return;
        setError(null);
        setStep('pre-running');
        try {
            const res = await fetch(`${BASE}/ethos/logical-module/pretest`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_name: modelName.trim(), max_prompts: maxPrompts }),
            });
            if (!res.ok) throw new Error(await res.text());
            const data: PhaseResult = await res.json();
            setPreResult(data);
            setSessionId(data.session_id);
            setStep('pre-done');
        } catch (e: any) {
            setError(e.message || 'Pre-test failed');
            setStep('idle');
        }
    }, [modelName, maxPrompts]);

    // ── Step 3: Logical injection ─────────────────────────────────────────────
    const handleInject = useCallback(async () => {
        if (!sessionId || !modelName) return;
        setError(null);
        setStep('injecting');
        setInjectProgress({ stage: 'starting', pct: 0 });

        try {
            const res = await fetch(`${BASE}/ethos/logical-module/inject`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId, model_name: modelName.trim() }),
            });
            if (!res.ok) throw new Error(await res.text());

            // Poll for completion
            pollRef.current = setInterval(async () => {
                try {
                    const pr = await fetch(`${BASE}/ethos/logical-module/inject-status?session_id=${sessionId}`);
                    if (!pr.ok) return;
                    const status = await pr.json();
                    setInjectProgress(status.progress || { stage: '', pct: 0 });
                    if (status.status === 'completed') {
                        clearInterval(pollRef.current!);
                        // Fetch post results
                        const pp = await fetch(`${BASE}/ethos/logical-module/posttest`, {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ session_id: sessionId }),
                        });
                        if (pp.ok) setPostResult(await pp.json());
                        setStep('post-done');
                    } else if (status.status === 'failed') {
                        clearInterval(pollRef.current!);
                        setError(status.error || 'Injection failed');
                        setStep('pre-done');
                    }
                } catch { /* ignore polling errors */ }
            }, 3000);

        } catch (e: any) {
            setError(e.message || 'Injection request failed');
            setStep('pre-done');
        }
    }, [sessionId, modelName]);

    const handleReset = () => {
        if (pollRef.current) clearInterval(pollRef.current);
        setStep('idle');
        setPreResult(null);
        setPostResult(null);
        setSessionId(null);
        setError(null);
        setInjectProgress({ stage: '', pct: 0 });
    };

    // ── Step indicator ────────────────────────────────────────────────────────
    const stepIdx = STEPS.findIndex(s => s.key === step);

    // ── JSX ───────────────────────────────────────────────────────────────────
    return (
        <div id="logical-module-wizard" style={{
            display: 'flex', flexDirection: 'column', height: '100%',
            background: '#1a1a2e', color: '#e0e0e0',
        }}>
            {/* Header */}
            <div style={{
                padding: '12px 16px', borderBottom: '1px solid #2a2a3e',
                display: 'flex', alignItems: 'center', gap: 10,
            }}>
                <Atom size={18} color="#6366f1" />
                <span style={{ fontWeight: 700, fontSize: 15 }}>Logical Module — Confidence Testing</span>
                <div style={{ flex: 1 }} />
                {step !== 'idle' && (
                    <button onClick={handleReset} style={{
                        background: 'none', border: '1px solid #3a3a5e', borderRadius: 6,
                        color: '#888', cursor: 'pointer', fontSize: 11, padding: '4px 10px',
                        display: 'flex', alignItems: 'center', gap: 4,
                    }}>
                        <RotateCcw size={12} /> Reset
                    </button>
                )}
            </div>

            {/* Step breadcrumb */}
            <div style={{
                display: 'flex', alignItems: 'center', padding: '8px 16px', gap: 4,
                borderBottom: '1px solid #2a2a3e', flexWrap: 'wrap',
            }}>
                {STEPS.map((s, i) => {
                    const isActive = s.key === step;
                    const isPast = i < stepIdx;
                    return (
                        <React.Fragment key={s.key}>
                            {i > 0 && <ChevronRight size={12} color="#555" />}
                            <div style={{
                                display: 'flex', alignItems: 'center', gap: 4,
                                padding: '3px 8px', borderRadius: 4, fontSize: 11, fontWeight: 500,
                                background: isActive ? '#6366f122' : 'transparent',
                                color: isActive ? '#a78bfa' : isPast ? '#22c55e' : '#666',
                                border: isActive ? '1px solid #6366f144' : '1px solid transparent',
                            }}>
                                {isPast ? <CheckCircle size={11} /> : null}
                                {s.label}
                            </div>
                        </React.Fragment>
                    );
                })}
            </div>

            {/* Content */}
            <div style={{ flex: 1, overflow: 'auto', padding: 16 }}>

                {/* Error banner */}
                {error && (
                    <div style={{
                        background: 'rgba(239,68,68,0.1)', border: '1px solid #ef4444',
                        borderRadius: 8, padding: '10px 14px', marginBottom: 12,
                        fontSize: 13, color: '#f87171',
                    }}>
                        <AlertTriangle size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />
                        {error}
                    </div>
                )}

                {/* ── STEP: Idle (Model Selection) ──────────────────────────────── */}
                {step === 'idle' && (
                    <div>
                        <div style={{ textAlign: 'center', marginBottom: 20 }}>
                            <Atom size={40} color="#6366f1" style={{ marginBottom: 10 }} />
                            <h3 style={{ margin: '0 0 4px', fontSize: 17 }}>Logical Module Pipeline</h3>
                            <p style={{ color: '#888', fontSize: 12, margin: 0 }}>
                                Load any HuggingFace model, see how it fails logical questions,
                                apply confidence injection, then download the before/after PDF.
                            </p>
                        </div>

                        <div style={{ background: '#1e1e2e', borderRadius: 8, padding: 16, marginBottom: 12, border: '1px solid #6366f144' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                                <FlaskConical size={16} color="#6366f1" />
                                <span style={{ fontWeight: 600, fontSize: 14 }}>HuggingFace Model Name</span>
                                <span style={{ background: '#22c55e22', color: '#22c55e', padding: '1px 8px', borderRadius: 10, fontSize: 10, fontWeight: 600 }}>LOCAL GPU</span>
                            </div>
                            <p style={{ color: '#888', fontSize: 12, margin: '0 0 10px' }}>
                                Enter a model ID. It will be downloaded, run on <strong style={{ color: '#a78bfa' }}>{maxPrompts} research-grounded logical prompts</strong> across 7 failure categories,
                                then fine-tuned with LoRA to improve abstention behaviour.
                            </p>
                            <input
                                id="lm-model-input"
                                type="text"
                                value={modelName}
                                onChange={e => setModelName(e.target.value)}
                                onKeyDown={e => e.key === 'Enter' && handlePreTest()}
                                placeholder="e.g. sshleifer/tiny-gpt2 or VibeStudio/Nidum-Gemma-2B-Uncensored"
                                style={{
                                    width: '100%', background: '#12121f', border: '1px solid #3a3a5e',
                                    borderRadius: 6, padding: '9px 12px', color: '#e0e0e0',
                                    fontSize: 13, marginBottom: 10, boxSizing: 'border-box',
                                }}
                            />
                            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 10 }}>
                                <label style={{ fontSize: 12, color: '#888', whiteSpace: 'nowrap' }}>Prompts (5–36):</label>
                                <input type="number" min={5} max={36} value={maxPrompts}
                                    onChange={e => setMaxPrompts(Math.max(5, Math.min(36, parseInt(e.target.value) || 36)))}
                                    style={{ width: 60, background: '#12121f', border: '1px solid #3a3a5e', borderRadius: 6, padding: '6px', color: '#e0e0e0', fontSize: 13 }}
                                />
                            </div>
                            <button
                                id="lm-pretest-btn"
                                onClick={handlePreTest}
                                disabled={!modelName.trim()}
                                style={{
                                    display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center',
                                    background: modelName.trim() ? '#6366f1' : '#3a3a5e',
                                    border: 'none', borderRadius: 8, color: '#fff',
                                    padding: '11px 20px', fontSize: 13, fontWeight: 700,
                                    cursor: modelName.trim() ? 'pointer' : 'not-allowed', width: '100%',
                                }}
                            >
                                <Play size={14} /> Run Pre-Test
                            </button>
                            <p style={{ color: '#555', fontSize: 11, marginTop: 8 }}>
                                Examples: <code style={{ color: '#8b5cf6' }}>sshleifer/tiny-gpt2</code>,{' '}
                                <code style={{ color: '#8b5cf6' }}>TinyLlama/TinyLlama-1.1B-Chat-v1.0</code>
                            </p>
                            {/* Category legend */}
                            <div style={{ marginTop: 12, padding: '10px 12px', background: '#12121f', borderRadius: 8 }}>
                                <div style={{ fontSize: 11, color: '#888', marginBottom: 6, fontWeight: 600 }}>7 Failure categories tested</div>
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                                    {Object.entries(CAT_COLORS).map(([cat, col]) => (
                                        <span key={cat} style={{
                                            fontSize: 10, padding: '2px 8px', borderRadius: 10,
                                            background: col + '22', color: col,
                                            border: `1px solid ${col}44`, fontWeight: 600,
                                        }}>{cat.replace('_', ' ')}</span>
                                    ))}
                                </div>
                            </div>
                        </div>

                        {/* What will happen */}
                        <div style={{ background: '#12121f', borderRadius: 8, padding: 14, border: '1px solid #2a2a3e' }}>
                            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>What happens next</div>
                            {[
                                `1️⃣  Model loads on your GPU — up to 36 research-grounded prompts run`,
                                '2️⃣  Before PDF: every prompt, response, action & confidence signal',
                                '3️⃣  LoRA injection: injects confidence system prompt so model evaluates its certainty before every answer',
                                '4️⃣  Same prompts run again — After PDF + Before/After Comparison PDF',
                            ].map(t => (
                                <div key={t} style={{ fontSize: 12, color: '#888', marginBottom: 4 }}>{t}</div>
                            ))}
                        </div>
                    </div>
                )}

                {/* ── STEP: Pre-running ──────────────────────────────────────────── */}
                {step === 'pre-running' && (
                    <div style={{ textAlign: 'center', padding: '60px 20px' }}>
                        <Loader2 size={44} color="#6366f1" style={{ animation: 'spin 1s linear infinite', marginBottom: 16 }} />
                        <h3 style={{ margin: '0 0 8px', fontSize: 17 }}>Running Pre-Test…</h3>
                        <p style={{ color: '#888', fontSize: 13 }}>Loading model and running {maxPrompts} logical challenge prompts</p>
                        <p style={{ color: '#555', fontSize: 12, marginTop: 8 }}>This may take 1–3 minutes depending on model size</p>
                    </div>
                )}

                {/* ── STEP: Pre-done ─────────────────────────────────────────────── */}
                {step === 'pre-done' && preResult && (
                    <div>
                        <PhaseCard
                            result={preResult}
                            label="Pre-Injection Results (Baseline)"
                            onDownload={() => download(`${BASE}/ethos/logical-module/report/pre/${preResult.session_id}`, `logical_pre_${mn}.pdf`)}
                            downloadLabel="Download Pre-Test PDF Report"
                        />

                        {/* Inject button */}
                        <div style={{ background: '#1e1e2e', borderRadius: 10, padding: 16, border: '1px solid #a855f744' }}>
                            <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 8 }}>
                                <Zap size={16} color="#a855f7" /> Apply Logical Injection
                            </div>
                            <p style={{ color: '#888', fontSize: 12, margin: '0 0 12px' }}>
                                Applies LoRA fine-tuning so the model learns to say <em>"I'm not sure"</em> when
                                its internal confidence is low, and <em>"I don't know"</em> when it cannot reliably answer.
                                Then re-runs the same {maxPrompts} prompts automatically.
                            </p>
                            <button
                                id="lm-inject-btn"
                                onClick={handleInject}
                                style={{
                                    display: 'flex', alignItems: 'center', gap: 8, justifyContent: 'center',
                                    background: '#a855f7', border: 'none', borderRadius: 8, color: '#fff',
                                    padding: '11px 20px', fontSize: 13, fontWeight: 700, cursor: 'pointer', width: '100%',
                                }}
                            >
                                <Zap size={14} /> Start Logical Injection + Post-Test
                            </button>
                        </div>
                    </div>
                )}

                {/* ── STEP: Injecting ────────────────────────────────────────────── */}
                {step === 'injecting' && (
                    <div style={{ textAlign: 'center', padding: '50px 20px' }}>
                        <Zap size={44} color="#a855f7" style={{ marginBottom: 16 }} />
                        <h3 style={{ margin: '0 0 8px', fontSize: 17 }}>Applying Logical Injection…</h3>
                        <p style={{ color: '#888', fontSize: 13 }}>{injectProgress.stage || 'Starting…'}</p>
                        {/* Progress bar */}
                        <div style={{ width: '80%', margin: '16px auto', background: '#2a2a3e', borderRadius: 8, height: 10 }}>
                            <div style={{
                                width: `${injectProgress.pct}%`, height: 10, borderRadius: 8,
                                background: '#a855f7', transition: 'width 0.5s',
                            }} />
                        </div>
                        <p style={{ color: '#555', fontSize: 12 }}>{injectProgress.pct}% complete</p>
                    </div>
                )}

                {/* ── STEP: Post-done ─────────────────────────────────────────────── */}
                {step === 'post-done' && postResult && preResult && (
                    <div>
                        {/* Comparison card — top */}
                        <ComparisonCard
                            pre={preResult}
                            post={postResult}
                            onDownload={() => download(`${BASE}/ethos/logical-module/report/comparison/${sessionId}`, `logical_comparison_${mn}.pdf`)}
                        />

                        {/* Pre card */}
                        <PhaseCard
                            result={preResult}
                            label="Before Injection"
                            onDownload={() => download(`${BASE}/ethos/logical-module/report/pre/${sessionId}`, `logical_pre_${mn}.pdf`)}
                            downloadLabel="Download Before PDF"
                        />

                        {/* Post card */}
                        <PhaseCard
                            result={postResult}
                            label="After Injection"
                            onDownload={() => download(`${BASE}/ethos/logical-module/report/post/${sessionId}`, `logical_post_${mn}.pdf`)}
                            downloadLabel="Download After PDF"
                        />
                    </div>
                )}
            </div>

            {/* Spin keyframes */}
            <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
        </div>
    );
};

export default LogicalModuleWizard;
