import React, { useState } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';

// ─── Types ──────────────────────────────────────────────────────────────────

interface SignalResult {
    T: number;
    A: number;
    S: number;
    V: number | null;
    C: number;
}

interface ItemResult {
    prompt: string;
    original_response: string;
    action: 'ANSWER' | 'HEDGE' | 'ABSTAIN';
    confidence: number;
    signals: SignalResult;
    final_response: string;
    explanation: string;
    domain: string;
}

interface AnalyzeResponse {
    model_name: string;
    evaluated_at: string;
    items: ItemResult[];
    summary: {
        total: number;
        answered: number;
        hedged: number;
        abstained: number;
        avg_confidence: number;
        avg_T: number;
        avg_A: number;
        avg_S: number;
    };
}

// ─── Helper UI pieces ────────────────────────────────────────────────────────

const ACTION_CONFIG = {
    ANSWER: { bg: 'bg-emerald-100 dark:bg-emerald-900/40', text: 'text-emerald-800 dark:text-emerald-300', border: 'border-emerald-300', icon: '✅', label: 'Answer Normally' },
    HEDGE: { bg: 'bg-amber-100 dark:bg-amber-900/40', text: 'text-amber-800 dark:text-amber-300', border: 'border-amber-300', icon: '⚠️', label: 'Hedge (Express Uncertainty)' },
    ABSTAIN: { bg: 'bg-red-100 dark:bg-red-900/40', text: 'text-red-800 dark:text-red-300', border: 'border-red-300', icon: '🚫', label: 'Abstain (Refuse)' },
};

const SignalBar: React.FC<{ label: string; value: number; tooltip: string }> = ({ label, value, tooltip }) => (
    <div className="flex items-center gap-2 group relative" title={tooltip}>
        <span className="text-xs text-gray-500 dark:text-gray-400 w-4 font-mono font-bold">{label}</span>
        <div className="flex-1 bg-gray-200 dark:bg-gray-700 rounded-full h-2">
            <div
                className={`h-2 rounded-full transition-all ${value >= 0.85 ? 'bg-emerald-500' : value >= 0.50 ? 'bg-amber-500' : 'bg-red-500'}`}
                style={{ width: `${value * 100}%` }}
            />
        </div>
        <span className="text-xs font-mono text-gray-600 dark:text-gray-300 w-8 text-right">{(value * 100).toFixed(0)}%</span>
    </div>
);

const ConfidencePill: React.FC<{ action: 'ANSWER' | 'HEDGE' | 'ABSTAIN'; confidence: number }> = ({ action, confidence }) => {
    const cfg = ACTION_CONFIG[action];
    return (
        <div className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-semibold ${cfg.bg} ${cfg.text} ${cfg.border}`}>
            <span>{cfg.icon}</span>
            <span>{cfg.label}</span>
            <span className="opacity-70">· {(confidence * 100).toFixed(1)}%</span>
        </div>
    );
};

// ─── Main Panel ──────────────────────────────────────────────────────────────

export const LogicalModulePanel: React.FC = () => {
    const [results, setResults] = useState<AnalyzeResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [pdfLoading, setPdfLoading] = useState(false);
    const [activeTab, setActiveTab] = useState<'all' | 'answer' | 'hedge' | 'abstain'>('all');

    // ── Load demo results ────────────────────────────────────────────────────
    const loadDemo = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch('http://localhost:8000/ethos/logical-module/demo');
            if (!res.ok) throw new Error(`Server error: ${res.status}`);
            setResults(await res.json());
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load demo');
        } finally {
            setLoading(false);
        }
    };

    // ── Download PDF report ──────────────────────────────────────────────────
    const downloadPdf = async () => {
        if (!results) return;
        setPdfLoading(true);
        try {
            // Re-run analysis with same pairs to get the report
            const pairs = results.items.map(item => ({
                prompt: item.prompt,
                response: item.original_response,
                domain: item.domain,
                sampled_responses: null,
                token_logprobs: null,
            }));

            const res = await fetch('http://localhost:8000/ethos/logical-module/report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pairs, model_name: results.model_name }),
            });

            if (!res.ok) throw new Error(`Report error: ${res.status}`);

            const contentType = res.headers.get('Content-Type') || '';
            const blob = await res.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = contentType.includes('pdf')
                ? `logical_module_report_${new Date().toISOString().slice(0, 10)}.pdf`
                : `logical_module_report_${new Date().toISOString().slice(0, 10)}.txt`;
            a.click();
            URL.revokeObjectURL(url);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to download report');
        } finally {
            setPdfLoading(false);
        }
    };

    // ── Filter items ─────────────────────────────────────────────────────────
    const filteredItems = results?.items.filter(item =>
        activeTab === 'all' ? true :
            activeTab === 'answer' ? item.action === 'ANSWER' :
                activeTab === 'hedge' ? item.action === 'HEDGE' :
                    item.action === 'ABSTAIN'
    ) ?? [];

    // ── Empty / loading states ───────────────────────────────────────────────
    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-full gap-4 p-8">
                <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                <p className="text-sm text-gray-500 dark:text-gray-400">Running Logical Module pipeline…</p>
            </div>
        );
    }

    return (
        <ScrollArea className="h-[calc(100vh-8rem)]">
            <div className="p-4 space-y-5">

                {/* ── Header ── */}
                <div className="flex items-start justify-between gap-3">
                    <div>
                        <h2 className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                            <span className="text-indigo-500">🧠</span> Logical Module
                        </h2>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                            Confidence-based abstention &middot; Bayesian fusion &middot; Before vs. After
                        </p>
                    </div>
                    <div className="flex gap-2 flex-shrink-0">
                        <button
                            id="logical-module-demo-btn"
                            onClick={loadDemo}
                            disabled={loading}
                            className="px-3 py-1.5 text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white rounded-md transition-colors disabled:opacity-50"
                        >
                            ▶ Run Demo
                        </button>
                        {results && (
                            <button
                                id="logical-module-pdf-btn"
                                onClick={downloadPdf}
                                disabled={pdfLoading}
                                className="px-3 py-1.5 text-xs font-semibold bg-gray-800 hover:bg-gray-700 dark:bg-gray-700 dark:hover:bg-gray-600 text-white rounded-md transition-colors disabled:opacity-50 flex items-center gap-1"
                            >
                                {pdfLoading ? '⏳' : '⬇'} PDF Report
                            </button>
                        )}
                    </div>
                </div>

                {/* ── Error ── */}
                {error && (
                    <div className="bg-red-50 dark:bg-red-900/30 border border-red-300 dark:border-red-700 rounded-lg p-3 text-sm text-red-700 dark:text-red-300">
                        ⚠️ {error}
                    </div>
                )}

                {/* ── Info card (no results yet) ── */}
                {!results && !error && (
                    <div className="rounded-xl border border-dashed border-indigo-300 dark:border-indigo-700 bg-indigo-50 dark:bg-indigo-950/30 p-6 space-y-3">
                        <p className="text-sm font-semibold text-indigo-700 dark:text-indigo-300">What the Logical Module does</p>
                        <ul className="text-xs text-gray-600 dark:text-gray-400 space-y-1.5 list-inside">
                            {[
                                '🔬 Computes T · A · S · V confidence signals per response',
                                '⚖️  Fuses them via Bayesian log-odds (not simple averaging)',
                                '🎯 Applies domain-aware Expected Utility to decide ANSWER / HEDGE / ABSTAIN',
                                '📄 Generates a downloadable PDF report with before/after comparison',
                            ].map(txt => <li key={txt}>{txt}</li>)}
                        </ul>
                        <button
                            onClick={loadDemo}
                            className="mt-2 text-xs font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
                        >
                            Click "Run Demo" to see it in action →
                        </button>
                    </div>
                )}

                {/* ── Results ── */}
                {results && (
                    <>
                        {/* Summary bar */}
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                            {[
                                { label: 'Evaluated', value: results.summary.total, color: 'text-gray-700 dark:text-gray-200' },
                                { label: '✅ Answered', value: results.summary.answered, color: 'text-emerald-600 dark:text-emerald-400' },
                                { label: '⚠️ Hedged', value: results.summary.hedged, color: 'text-amber-600 dark:text-amber-400' },
                                { label: '🚫 Abstained', value: results.summary.abstained, color: 'text-red-600 dark:text-red-400' },
                            ].map(({ label, value, color }) => (
                                <div key={label} className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-3 text-center">
                                    <div className={`text-2xl font-bold ${color}`}>{value}</div>
                                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{label}</div>
                                </div>
                            ))}
                        </div>

                        {/* Avg signal scores */}
                        <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-2">
                            <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">Average Signals</p>
                            <SignalBar label="T" value={results.summary.avg_T} tooltip="Token-level attention-weighted confidence" />
                            <SignalBar label="A" value={results.summary.avg_A} tooltip="Self-consistency cluster agreement" />
                            <SignalBar label="S" value={results.summary.avg_S} tooltip="Outlier-penalised semantic coherence" />
                            <SignalBar label="C" value={results.summary.avg_confidence} tooltip="Fused Bayesian confidence" />
                        </div>

                        {/* Filter tabs */}
                        <div className="flex gap-1 border-b border-gray-200 dark:border-gray-700 text-xs">
                            {(['all', 'answer', 'hedge', 'abstain'] as const).map(tab => (
                                <button
                                    key={tab}
                                    onClick={() => setActiveTab(tab)}
                                    className={`px-3 py-1.5 font-medium capitalize transition-colors border-b-2 -mb-px ${activeTab === tab
                                            ? 'border-indigo-500 text-indigo-600 dark:text-indigo-400'
                                            : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
                                        }`}
                                >
                                    {tab === 'all' ? `All (${results.items.length})` :
                                        tab === 'answer' ? `✅ Answered (${results.summary.answered})` :
                                            tab === 'hedge' ? `⚠️ Hedged (${results.summary.hedged})` :
                                                `🚫 Abstained (${results.summary.abstained})`}
                                </button>
                            ))}
                        </div>

                        {/* Per-item cards */}
                        <div className="space-y-4">
                            {filteredItems.map((item, idx) => (
                                <div
                                    key={idx}
                                    className={`rounded-xl border p-4 space-y-3 ${ACTION_CONFIG[item.action].bg} ${ACTION_CONFIG[item.action].border}`}
                                >
                                    {/* Header row */}
                                    <div className="flex items-center justify-between gap-2 flex-wrap">
                                        <ConfidencePill action={item.action} confidence={item.confidence} />
                                        <span className="text-xs px-2 py-0.5 rounded-full bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300 font-mono">
                                            domain: {item.domain}
                                        </span>
                                    </div>

                                    {/* Prompt */}
                                    <div>
                                        <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase mb-1">Prompt</p>
                                        <p className="text-sm text-gray-800 dark:text-gray-200 bg-white/60 dark:bg-gray-900/40 rounded p-2">
                                            {item.prompt}
                                        </p>
                                    </div>

                                    {/* Before / After */}
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                        <div>
                                            <p className="text-xs font-semibold text-gray-400 uppercase mb-1">❌ Before (Baseline)</p>
                                            <p className="text-xs text-gray-700 dark:text-gray-300 bg-gray-100 dark:bg-gray-800 rounded p-2 whitespace-pre-wrap">
                                                {item.original_response}
                                            </p>
                                        </div>
                                        <div>
                                            <p className="text-xs font-semibold text-gray-400 uppercase mb-1">✨ After (Logical Module)</p>
                                            <p className="text-xs text-gray-800 dark:text-gray-100 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded p-2 whitespace-pre-wrap">
                                                {item.final_response}
                                            </p>
                                        </div>
                                    </div>

                                    {/* Signal bars */}
                                    <div className="space-y-1.5">
                                        <p className="text-xs font-semibold text-gray-500 dark:text-gray-400 uppercase">Confidence Signals</p>
                                        <SignalBar label="T" value={item.signals.T} tooltip="Token entropy confidence" />
                                        <SignalBar label="A" value={item.signals.A} tooltip="Cluster agreement" />
                                        <SignalBar label="S" value={item.signals.S} tooltip="Semantic coherence" />
                                        {item.signals.V !== null && (
                                            <SignalBar label="V" value={item.signals.V} tooltip="Self-verification score" />
                                        )}
                                        <SignalBar label="C" value={item.signals.C} tooltip="Fused Bayesian confidence" />
                                    </div>

                                    {/* Explanation */}
                                    <p className="text-xs text-gray-500 dark:text-gray-400 italic">{item.explanation}</p>
                                </div>
                            ))}
                        </div>

                        <p className="text-center text-xs text-gray-400 dark:text-gray-600 pb-2">
                            Model: {results.model_name} · {results.evaluated_at}
                        </p>
                    </>
                )}
            </div>
        </ScrollArea>
    );
};

export default LogicalModulePanel;
