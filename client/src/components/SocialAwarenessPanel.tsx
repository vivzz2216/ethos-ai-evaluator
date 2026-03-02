/**
 * SocialAwarenessPanel — displays style detection, human interaction scores,
 * style transformation, drift report, and response consistency for a model.
 *
 * Usage: <SocialAwarenessPanel />
 * Talks to the backend at POST /social/evaluate, /social/drift, /social/consistency
 */

import React, { useState } from 'react';
import {
    MessageSquare, BarChart2, RefreshCw, Activity, CheckCircle,
    XCircle, AlertTriangle, ChevronDown, ChevronRight, ArrowRight, Cpu
} from 'lucide-react';

const BASE = 'http://localhost:8000';

// ── Types ─────────────────────────────────────────────────────────────────────

interface StyleScores { formal: number; informal: number; human: number; corporate: number; }
interface SyntaxSignals {
    passive_voice_ratio: number; formal_modal_ratio: number;
    noun_phrase_density: number; sentence_length_variance: number; syntax_formality: number;
}
interface HumanScore {
    empathy: number; clarity: number; politeness: number;
    engagement: number; conversational_flow: number; overall: number;
}
interface EvalResult {
    input_text: string; detected_style: string; style_scores: StyleScores;
    is_mixed: boolean; confidence: number; compliance: string;
    required_style: string | null; violations: string[]; syntax_signals: SyntaxSignals;
    human_interaction_score: HumanScore; transformed?: { transformed: string; similarity_score: number; method: string } | null;
}
interface DriftReport {
    style_distribution: Record<string, number>; compliance_rate: number | null;
    style_drift: number | null; policy_status: string; required_style: string | null; total_samples: number;
}
interface ConsistencyResult {
    consistency_score: number; verdict: string; style_sequence: string[];
    style_distribution: Record<string, number>; entropy: number; samples_analyzed: number;
}

// ── Color helpers ─────────────────────────────────────────────────────────────

const STYLE_COLORS: Record<string, string> = {
    FORMAL: '#6366f1', INFORMAL: '#f59e0b', CORPORATE: '#0ea5e9', HUMAN: '#22c55e', HYBRID: '#a855f7',
};
const COMPLIANCE_COLORS: Record<string, string> = {
    COMPLIANT: '#22c55e', PARTIAL: '#eab308', VIOLATION: '#ef4444', NOT_CHECKED: '#64748b',
};
const DRIFT_COLORS: Record<string, string> = {
    COMPLIANT: '#22c55e', MINOR_DRIFT: '#eab308', DRIFT_DETECTED: '#f97316', HIGH_DRIFT: '#ef4444', NOT_CHECKED: '#64748b',
};
const CONSISTENCY_COLORS: Record<string, string> = {
    STABLE: '#22c55e', MOSTLY_STABLE: '#84cc16', INCONSISTENT: '#f59e0b', UNSTABLE: '#ef4444', NO_DATA: '#64748b',
};

// ── Shared sub-components ─────────────────────────────────────────────────────

const Card: React.FC<{ title: string; icon: React.ReactNode; children: React.ReactNode; accent?: string }> =
    ({ title, icon, children, accent = '#6366f1' }) => (
        <div style={{ background: '#1e1e2e', borderRadius: 10, padding: 16, border: `1px solid #2a2a3e` }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14, fontWeight: 600, fontSize: 14, color: '#e0e0e0' }}>
                <span style={{ color: accent }}>{icon}</span>{title}
            </div>
            {children}
        </div>
    );

const ScoreBar: React.FC<{ label: string; value: number; max?: number; color?: string }> =
    ({ label, value, max = 100, color = '#6366f1' }) => (
        <div style={{ marginBottom: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3, color: '#ccc' }}>
                <span>{label}</span><span style={{ color, fontWeight: 600 }}>{Math.round(value * (max === 1 ? 100 : 1))}{max === 1 ? '%' : ''}</span>
            </div>
            <div style={{ height: 6, background: '#2a2a3e', borderRadius: 4, overflow: 'hidden' }}>
                <div style={{ width: `${(value / max) * 100}%`, height: '100%', background: color, borderRadius: 4, transition: 'width 0.4s ease' }} />
            </div>
        </div>
    );

const Badge: React.FC<{ label: string; color: string }> = ({ label, color }) => (
    <span style={{
        display: 'inline-block', padding: '3px 10px', borderRadius: 20,
        background: `${color}22`, border: `1px solid ${color}`,
        color, fontSize: 11, fontWeight: 700, letterSpacing: 0.5,
    }}>{label}</span>
);

// ── Main Component ────────────────────────────────────────────────────────────

const SocialAwarenessPanel: React.FC = () => {
    const [activeTab, setActiveTab] = useState<'evaluate' | 'drift' | 'consistency' | 'transform'>('evaluate');

    // ── Evaluate state
    const [evalText, setEvalText] = useState('Sure! I\'ll help ya out. Don\'t worry, it\'s super easy!');
    const [evalStyle, setEvalStyle] = useState('formal');
    const [evalTransform, setEvalTransform] = useState(false);
    const [evalResult, setEvalResult] = useState<EvalResult | null>(null);
    const [evalLoading, setEvalLoading] = useState(false);
    const [evalError, setEvalError] = useState<string | null>(null);
    const [expandSyntax, setExpandSyntax] = useState(false);

    // ── Drift state
    const [driftTexts, setDriftTexts] = useState(
        'Sure! I can help ya out.\nCertainly. I will assist you accordingly.\nHey don\'t worry about it, we got you!\nThe requested documentation shall be provided.\nYeah totally happy to help!'
    );
    const [driftStyle, setDriftStyle] = useState('formal');
    const [driftResult, setDriftResult] = useState<DriftReport | null>(null);
    const [driftPerItem, setDriftPerItem] = useState<string[]>([]);
    const [driftLoading, setDriftLoading] = useState(false);
    const [driftError, setDriftError] = useState<string | null>(null);

    // ── Consistency state
    const [consistTexts, setConsistTexts] = useState(
        'I will assist you with this matter.\nSure! Happy to help!\nCertainly, the matter shall be addressed.\nNo problem! Let me sort this out.\nI am pleased to assist with your request.'
    );
    const [consistResult, setConsistResult] = useState<ConsistencyResult | null>(null);
    const [consistLoading, setConsistLoading] = useState(false);
    const [consistError, setConsistError] = useState<string | null>(null);

    // ── Transform state
    const [txTexts, setTxTexts] = useState(
        "Sure! I'll send ya the docs asap.\nDon't worry, we'll get this sorted!"
    );
    const [txStyle, setTxStyle] = useState('formal');
    const [txResults, setTxResults] = useState<any[]>([]);
    const [txLoading, setTxLoading] = useState(false);
    const [txError, setTxError] = useState<string | null>(null);

    // ── API calls ─────────────────────────────────────────────────────────────

    const runEvaluate = async () => {
        if (!evalText.trim()) return;
        setEvalLoading(true); setEvalError(null); setEvalResult(null);
        try {
            const res = await fetch(`${BASE}/social/evaluate`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ texts: [evalText], required_style: evalStyle || null, transform_on_violation: evalTransform }),
            });
            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();
            setEvalResult(data.results?.[0] || null);
        } catch (e: any) { setEvalError(e.message || 'Request failed'); }
        finally { setEvalLoading(false); }
    };

    const runDrift = async () => {
        const texts = driftTexts.split('\n').filter(t => t.trim());
        if (!texts.length || !driftStyle) return;
        setDriftLoading(true); setDriftError(null); setDriftResult(null);
        try {
            const res = await fetch(`${BASE}/social/drift`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ texts, required_style: driftStyle }),
            });
            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();
            setDriftResult(data.drift_report);
            setDriftPerItem(data.per_item_style || []);
        } catch (e: any) { setDriftError(e.message || 'Request failed'); }
        finally { setDriftLoading(false); }
    };

    const runConsistency = async () => {
        const texts = consistTexts.split('\n').filter(t => t.trim());
        if (!texts.length) return;
        setConsistLoading(true); setConsistError(null); setConsistResult(null);
        try {
            const res = await fetch(`${BASE}/social/consistency`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ texts }),
            });
            if (!res.ok) throw new Error(await res.text());
            setConsistResult(await res.json());
        } catch (e: any) { setConsistError(e.message || 'Request failed'); }
        finally { setConsistLoading(false); }
    };

    const runTransform = async () => {
        const texts = txTexts.split('\n').filter(t => t.trim());
        if (!texts.length) return;
        setTxLoading(true); setTxError(null); setTxResults([]);
        try {
            const res = await fetch(`${BASE}/social/transform`, {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ texts, target_style: txStyle }),
            });
            if (!res.ok) throw new Error(await res.text());
            const data = await res.json();
            setTxResults(data.results || []);
        } catch (e: any) { setTxError(e.message || 'Request failed'); }
        finally { setTxLoading(false); }
    };

    // ── Tabs ──────────────────────────────────────────────────────────────────

    const tabs = [
        { id: 'evaluate', label: 'Evaluate', icon: <MessageSquare size={14} /> },
        { id: 'drift', label: 'Style Drift', icon: <BarChart2 size={14} /> },
        { id: 'consistency', label: 'Consistency', icon: <Activity size={14} /> },
        { id: 'transform', label: 'Transform', icon: <RefreshCw size={14} /> },
    ] as const;

    const styleOptions = ['formal', 'informal', 'corporate', 'human'];
    const inputStyle: React.CSSProperties = {
        width: '100%', background: '#12121f', border: '1px solid #2a2a3e', borderRadius: 6,
        color: '#e0e0e0', padding: '8px 10px', fontSize: 13, boxSizing: 'border-box',
    };
    const btnStyle = (color: string, disabled?: boolean): React.CSSProperties => ({
        background: disabled ? '#2a2a3e' : color, color: disabled ? '#666' : '#fff',
        border: 'none', borderRadius: 6, padding: '9px 18px', fontSize: 13,
        fontWeight: 600, cursor: disabled ? 'not-allowed' : 'pointer',
        display: 'inline-flex', alignItems: 'center', gap: 6,
    });
    const selectStyle: React.CSSProperties = {
        ...inputStyle, padding: '7px 10px', cursor: 'pointer',
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, color: '#e0e0e0', fontFamily: 'Inter, system-ui, sans-serif' }}>

            {/* ── Header ─────────────────────────────────────────────────── */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ background: 'rgba(99,102,241,0.15)', borderRadius: 8, padding: 8 }}>
                    <MessageSquare size={20} color="#6366f1" />
                </div>
                <div>
                    <div style={{ fontWeight: 700, fontSize: 18 }}>Social Awareness Module</div>
                    <div style={{ fontSize: 12, color: '#888' }}>Communication style detection, policy enforcement & tone transformation</div>
                </div>
            </div>

            {/* ── Tab bar ────────────────────────────────────────────────── */}
            <div style={{ display: 'flex', gap: 4, background: '#12121f', borderRadius: 8, padding: 4 }}>
                {tabs.map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        style={{
                            flex: 1, border: 'none', borderRadius: 6, padding: '7px 10px',
                            background: activeTab === tab.id ? '#6366f1' : 'transparent',
                            color: activeTab === tab.id ? '#fff' : '#888', fontWeight: 600, fontSize: 12,
                            cursor: 'pointer', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5,
                        }}
                    >
                        {tab.icon}{tab.label}
                    </button>
                ))}
            </div>

            {/* ══════════════════════════════════════════════════════════════
          TAB 1 — EVALUATE
      ═══════════════════════════════════════════════════════════════ */}
            {activeTab === 'evaluate' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <Card title="Input & Policy" icon={<MessageSquare size={14} />} accent="#6366f1">
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                            <textarea
                                rows={4}
                                value={evalText}
                                onChange={e => setEvalText(e.target.value)}
                                placeholder="Enter text to analyze..."
                                style={{ ...inputStyle, resize: 'vertical' }}
                            />
                            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                                <div style={{ flex: 1, minWidth: 140 }}>
                                    <div style={{ fontSize: 11, color: '#888', marginBottom: 4 }}>Required Style Policy</div>
                                    <select value={evalStyle} onChange={e => setEvalStyle(e.target.value)} style={selectStyle}>
                                        <option value="">— No policy —</option>
                                        {styleOptions.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
                                    </select>
                                </div>
                                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#ccc', cursor: 'pointer', marginTop: 12 }}>
                                    <input type="checkbox" checked={evalTransform} onChange={e => setEvalTransform(e.target.checked)} />
                                    Auto-transform on violation
                                </label>
                                <button
                                    onClick={runEvaluate}
                                    disabled={evalLoading}
                                    style={{ ...btnStyle('#6366f1', evalLoading), marginTop: 12 }}
                                >
                                    {evalLoading ? <><RefreshCw size={13} style={{ animation: 'spin 1s linear infinite' }} /> Analyzing...</> : 'Analyze'}
                                </button>
                            </div>
                        </div>
                    </Card>

                    {evalError && (
                        <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid #ef4444', borderRadius: 8, padding: 12, fontSize: 13, color: '#f87171' }}>
                            {evalError}
                        </div>
                    )}

                    {evalResult && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

                            {/* Style Detection */}
                            <Card title="Style Detection" icon={<BarChart2 size={14} />} accent="#6366f1">
                                <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
                                    <Badge label={evalResult.detected_style} color={STYLE_COLORS[evalResult.detected_style] || '#888'} />
                                    {evalResult.is_mixed && <Badge label="MIXED" color="#a855f7" />}
                                    <span style={{ fontSize: 11, color: '#888' }}>Confidence: {(evalResult.confidence * 100).toFixed(0)}%</span>
                                    {evalResult.compliance !== 'NOT_CHECKED' && (
                                        <Badge label={evalResult.compliance} color={COMPLIANCE_COLORS[evalResult.compliance]} />
                                    )}
                                </div>
                                <ScoreBar label="Formal" value={evalResult.style_scores.formal} max={1} color="#6366f1" />
                                <ScoreBar label="Informal" value={evalResult.style_scores.informal} max={1} color="#f59e0b" />
                                <ScoreBar label="Human / Empathetic" value={evalResult.style_scores.human} max={1} color="#22c55e" />
                                <ScoreBar label="Corporate" value={evalResult.style_scores.corporate} max={1} color="#0ea5e9" />
                            </Card>

                            {/* Syntax Signals */}
                            {evalResult.syntax_signals && Object.keys(evalResult.syntax_signals).length > 0 && (
                                <Card title="Syntax Formality Signals" icon={<Cpu size={14} />} accent="#0ea5e9">
                                    <button
                                        onClick={() => setExpandSyntax(!expandSyntax)}
                                        style={{ background: 'none', border: 'none', color: '#888', fontSize: 12, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, padding: 0, marginBottom: 8 }}
                                    >
                                        {expandSyntax ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                                        {expandSyntax ? 'Hide signals' : 'Show signals'}
                                    </button>
                                    {expandSyntax && (
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 12 }}>
                                            {[
                                                { label: 'Passive Voice Ratio', val: evalResult.syntax_signals.passive_voice_ratio },
                                                { label: 'Formal Modal Ratio', val: evalResult.syntax_signals.formal_modal_ratio },
                                                { label: 'Noun Phrase Density', val: evalResult.syntax_signals.noun_phrase_density },
                                                { label: 'Syntax Formality', val: evalResult.syntax_signals.syntax_formality },
                                            ].map(({ label, val }) => (
                                                <div key={label} style={{ background: '#12121f', borderRadius: 6, padding: '8px 10px' }}>
                                                    <div style={{ color: '#888', marginBottom: 2 }}>{label}</div>
                                                    <div style={{ color: '#a5b4fc', fontWeight: 600 }}>{(val * 100).toFixed(1)}%</div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </Card>
                            )}

                            {/* Violations */}
                            {evalResult.violations.length > 0 && (
                                <Card title="Policy Violations" icon={<AlertTriangle size={14} />} accent="#ef4444">
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                                        {evalResult.violations.map(v => (
                                            <Badge key={v} label={v.replace(/_/g, ' ')} color="#ef4444" />
                                        ))}
                                    </div>
                                </Card>
                            )}

                            {/* Human Interaction Score */}
                            <Card title="Human Interaction Score" icon={<Activity size={14} />} accent="#22c55e">
                                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 14 }}>
                                    {(['empathy', 'clarity', 'politeness', 'engagement', 'conversational_flow'] as const).map(dim => (
                                        <div key={dim} style={{ background: '#12121f', borderRadius: 8, padding: '10px 12px', textAlign: 'center' }}>
                                            <div style={{ fontSize: 20, fontWeight: 700, color: evalResult.human_interaction_score[dim] >= 70 ? '#22c55e' : evalResult.human_interaction_score[dim] >= 40 ? '#eab308' : '#ef4444' }}>
                                                {evalResult.human_interaction_score[dim]}
                                            </div>
                                            <div style={{ fontSize: 10, color: '#888', textTransform: 'capitalize' }}>{dim.replace('_', ' ')}</div>
                                        </div>
                                    ))}
                                    <div style={{ background: 'rgba(34,197,94,0.1)', borderRadius: 8, padding: '10px 12px', textAlign: 'center', border: '1px solid #22c55e' }}>
                                        <div style={{ fontSize: 24, fontWeight: 800, color: '#22c55e' }}>{evalResult.human_interaction_score.overall}</div>
                                        <div style={{ fontSize: 10, color: '#22c55e', fontWeight: 600 }}>OVERALL</div>
                                    </div>
                                </div>
                                <div style={{ fontSize: 11, color: '#666' }}>
                                    Overall = 0.25×Empathy + 0.25×Clarity + 0.20×Politeness + 0.15×Engagement + 0.15×Flow
                                </div>
                            </Card>

                            {/* Transformed output */}
                            {evalResult.transformed && (
                                <Card title="Auto-Transformed Output" icon={<RefreshCw size={14} />} accent="#a855f7">
                                    <div style={{ display: 'flex', gap: 6, marginBottom: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                                        <Badge label={evalResult.transformed.method} color="#a855f7" />
                                        <span style={{ fontSize: 11, color: '#888' }}>
                                            Similarity: {(evalResult.transformed.similarity_score * 100).toFixed(0)}%
                                        </span>
                                        {evalResult.transformed.similarity_score >= 0.75
                                            ? <CheckCircle size={14} color="#22c55e" />
                                            : <AlertTriangle size={14} color="#f59e0b" />}
                                    </div>
                                    <div style={{ background: '#12121f', borderRadius: 6, padding: 12, fontSize: 13, color: '#e0e0e0', lineHeight: 1.6, borderLeft: '3px solid #a855f7' }}>
                                        {evalResult.transformed.transformed}
                                    </div>
                                </Card>
                            )}
                        </div>
                    )}
                </div>
            )}

            {/* ══════════════════════════════════════════════════════════════
          TAB 2 — STYLE DRIFT
      ═══════════════════════════════════════════════════════════════ */}
            {activeTab === 'drift' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <Card title="Style Drift Detection" icon={<BarChart2 size={14} />} accent="#f59e0b">
                        <div style={{ fontSize: 12, color: '#888', marginBottom: 10 }}>
                            Enter one response per line. The engine measures what % match the required style.
                        </div>
                        <textarea
                            rows={7}
                            value={driftTexts}
                            onChange={e => setDriftTexts(e.target.value)}
                            placeholder="One response per line..."
                            style={{ ...inputStyle, resize: 'vertical', marginBottom: 10 }}
                        />
                        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
                            <div style={{ flex: 1 }}>
                                <div style={{ fontSize: 11, color: '#888', marginBottom: 4 }}>Required Style Policy</div>
                                <select value={driftStyle} onChange={e => setDriftStyle(e.target.value)} style={selectStyle}>
                                    {styleOptions.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
                                </select>
                            </div>
                            <button onClick={runDrift} disabled={driftLoading} style={btnStyle('#f59e0b', driftLoading)}>
                                {driftLoading ? <><RefreshCw size={13} style={{ animation: 'spin 1s linear infinite' }} /> Running...</> : 'Detect Drift'}
                            </button>
                        </div>
                    </Card>

                    {driftError && (
                        <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid #ef4444', borderRadius: 8, padding: 12, fontSize: 13, color: '#f87171' }}>{driftError}</div>
                    )}

                    {driftResult && (
                        <>
                            {/* Status badge */}
                            <div style={{ display: 'flex', gap: 12, alignItems: 'center', background: '#1e1e2e', borderRadius: 8, padding: 14 }}>
                                <Badge label={driftResult.policy_status} color={DRIFT_COLORS[driftResult.policy_status] || '#888'} />
                                <span style={{ fontSize: 13, color: '#ccc' }}>
                                    Compliance rate: <strong style={{ color: '#e0e0e0' }}>{driftResult.compliance_rate != null ? (driftResult.compliance_rate * 100).toFixed(0) : 'N/A'}%</strong>
                                </span>
                                {driftResult.style_drift != null && (
                                    <span style={{ fontSize: 13, color: '#ccc' }}>
                                        Style drift: <strong style={{ color: driftResult.style_drift > 0.3 ? '#ef4444' : '#22c55e' }}>
                                            {(driftResult.style_drift * 100).toFixed(0)}%
                                        </strong>
                                    </span>
                                )}
                            </div>

                            {/* Style distribution */}
                            <Card title="Style Distribution" icon={<BarChart2 size={14} />} accent="#f59e0b">
                                {Object.entries(driftResult.style_distribution).map(([label, pct]) => (
                                    <ScoreBar key={label} label={label} value={pct} max={100}
                                        color={STYLE_COLORS[label] || '#888'}
                                    />
                                ))}
                            </Card>

                            {/* Per-item sequence */}
                            {driftPerItem.length > 0 && (
                                <Card title="Response Style Sequence" icon={<Activity size={14} />} accent="#0ea5e9">
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                                        {driftPerItem.map((label, i) => (
                                            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                                <span style={{ fontSize: 10, color: '#666' }}>#{i + 1}</span>
                                                <Badge label={label} color={STYLE_COLORS[label] || '#888'} />
                                            </div>
                                        ))}
                                    </div>
                                </Card>
                            )}
                        </>
                    )}
                </div>
            )}

            {/* ══════════════════════════════════════════════════════════════
          TAB 3 — CONSISTENCY
      ═══════════════════════════════════════════════════════════════ */}
            {activeTab === 'consistency' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <Card title="Response Style Consistency" icon={<Activity size={14} />} accent="#22c55e">
                        <div style={{ fontSize: 12, color: '#888', marginBottom: 10 }}>
                            Enter multiple responses to the same prompt (one per line) to measure style instability.
                        </div>
                        <textarea
                            rows={7}
                            value={consistTexts}
                            onChange={e => setConsistTexts(e.target.value)}
                            placeholder="One response per line (same prompt, different model runs)..."
                            style={{ ...inputStyle, resize: 'vertical', marginBottom: 10 }}
                        />
                        <button onClick={runConsistency} disabled={consistLoading} style={btnStyle('#22c55e', consistLoading)}>
                            {consistLoading ? <><RefreshCw size={13} style={{ animation: 'spin 1s linear infinite' }} /> Measuring...</> : 'Measure Consistency'}
                        </button>
                    </Card>

                    {consistError && (
                        <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid #ef4444', borderRadius: 8, padding: 12, fontSize: 13, color: '#f87171' }}>{consistError}</div>
                    )}

                    {consistResult && (
                        <>
                            {/* Score meter */}
                            <div style={{ background: '#1e1e2e', borderRadius: 10, padding: 16, display: 'flex', alignItems: 'center', gap: 16 }}>
                                <div style={{ textAlign: 'center' }}>
                                    <div style={{ fontSize: 42, fontWeight: 800, color: CONSISTENCY_COLORS[consistResult.verdict] }}>
                                        {Math.round(consistResult.consistency_score * 100)}
                                    </div>
                                    <div style={{ fontSize: 10, color: '#888' }}>/ 100</div>
                                </div>
                                <div>
                                    <Badge label={consistResult.verdict} color={CONSISTENCY_COLORS[consistResult.verdict]} />
                                    <div style={{ fontSize: 12, color: '#888', marginTop: 6 }}>
                                        Shannon Entropy: {consistResult.entropy.toFixed(3)} bits — {consistResult.samples_analyzed} samples
                                    </div>
                                </div>
                            </div>

                            {/* Style sequence */}
                            <Card title="Style Sequence" icon={<Activity size={14} />} accent="#22c55e">
                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                                    {consistResult.style_sequence.map((label, i) => (
                                        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                            <span style={{ fontSize: 10, color: '#666' }}>#{i + 1}</span>
                                            <Badge label={label} color={STYLE_COLORS[label] || '#888'} />
                                            {i < consistResult.style_sequence.length - 1 && <ArrowRight size={10} color="#444" />}
                                        </div>
                                    ))}
                                </div>
                            </Card>

                            {/* Distribution */}
                            <Card title="Style Distribution" icon={<BarChart2 size={14} />} accent="#22c55e">
                                {Object.entries(consistResult.style_distribution).map(([label, count]) => (
                                    <ScoreBar key={label} label={`${label} (${count}x)`}
                                        value={count / consistResult.samples_analyzed}
                                        max={1} color={STYLE_COLORS[label] || '#888'}
                                    />
                                ))}
                            </Card>
                        </>
                    )}
                </div>
            )}

            {/* ══════════════════════════════════════════════════════════════
          TAB 4 — TRANSFORM
      ═══════════════════════════════════════════════════════════════ */}
            {activeTab === 'transform' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <Card title="Batch Style Transformer" icon={<RefreshCw size={14} />} accent="#a855f7">
                        <div style={{ fontSize: 12, color: '#888', marginBottom: 10 }}>
                            Enter one or more texts (one per line) and choose a target style. Semantic similarity is checked to prevent meaning drift.
                        </div>
                        <textarea
                            rows={5}
                            value={txTexts}
                            onChange={e => setTxTexts(e.target.value)}
                            placeholder="One text per line..."
                            style={{ ...inputStyle, resize: 'vertical', marginBottom: 10 }}
                        />
                        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
                            <div style={{ flex: 1 }}>
                                <div style={{ fontSize: 11, color: '#888', marginBottom: 4 }}>Target Style</div>
                                <select value={txStyle} onChange={e => setTxStyle(e.target.value)} style={selectStyle}>
                                    {styleOptions.map(s => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
                                </select>
                            </div>
                            <button onClick={runTransform} disabled={txLoading} style={btnStyle('#a855f7', txLoading)}>
                                {txLoading ? <><RefreshCw size={13} style={{ animation: 'spin 1s linear infinite' }} /> Transforming...</> : 'Transform'}
                            </button>
                        </div>
                    </Card>

                    {txError && (
                        <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid #ef4444', borderRadius: 8, padding: 12, fontSize: 13, color: '#f87171' }}>{txError}</div>
                    )}

                    {txResults.map((r, i) => (
                        <Card key={i} title={`Result #${i + 1}`} icon={<ArrowRight size={14} />} accent="#a855f7">
                            <div style={{ display: 'flex', gap: 6, marginBottom: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                                <Badge label={r.method} color="#a855f7" />
                                <span style={{ fontSize: 11, color: '#888' }}>Similarity: {(r.similarity_score * 100).toFixed(0)}%</span>
                                {r.meaning_preserved
                                    ? <CheckCircle size={13} color="#22c55e" />
                                    : <XCircle size={13} color="#ef4444" />}
                                <span style={{ fontSize: 11, color: r.meaning_preserved ? '#22c55e' : '#ef4444' }}>
                                    {r.meaning_preserved ? 'Meaning preserved' : 'Possible meaning shift'}
                                </span>
                            </div>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, fontSize: 12 }}>
                                <div>
                                    <div style={{ color: '#888', marginBottom: 4 }}>Original</div>
                                    <div style={{ background: '#12121f', borderRadius: 6, padding: 10, color: '#ccc', lineHeight: 1.6 }}>{r.original}</div>
                                </div>
                                <div>
                                    <div style={{ color: '#888', marginBottom: 4 }}>Transformed → <strong style={{ color: '#a855f7' }}>{r.target_style}</strong></div>
                                    <div style={{ background: '#12121f', borderRadius: 6, padding: 10, color: '#e0e0e0', lineHeight: 1.6, borderLeft: '3px solid #a855f7' }}>{r.transformed}</div>
                                </div>
                            </div>
                        </Card>
                    ))}
                </div>
            )}

            <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
        </div>
    );
};

export default SocialAwarenessPanel;
