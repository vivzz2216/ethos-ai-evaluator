/**
 * ModelTestResults - Displays ethics test results with scores, verdicts, and category breakdowns.
 */
import React, { useState } from 'react';
import type { ProcessingResult, TestRecord, Verdict, RepairStatus } from '../hooks/use-model-testing';
import { Shield, AlertTriangle, CheckCircle, XCircle, ChevronDown, ChevronRight, BarChart3, Clock, Zap, Download, Wrench, Loader2 } from 'lucide-react';

interface ModelTestResultsProps {
  result: ProcessingResult;
  sessionId?: string;
  onPurify?: () => void;
  onApprove?: () => void;
  onReject?: () => void;
  onRepair?: () => void;
  repairStatus?: RepairStatus | null;
  repairLoading?: boolean;
  repairError?: string | null;
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#22c55e',
};

const VERDICT_CONFIG: Record<string, { color: string; bg: string; icon: React.ReactNode; label: string }> = {
  APPROVE: { color: '#22c55e', bg: 'rgba(34,197,94,0.1)', icon: <CheckCircle size={20} />, label: 'APPROVED' },
  APPROVED: { color: '#22c55e', bg: 'rgba(34,197,94,0.1)', icon: <CheckCircle size={20} />, label: 'APPROVED' },
  WARN: { color: '#eab308', bg: 'rgba(234,179,8,0.1)', icon: <AlertTriangle size={20} />, label: 'WARNING' },
  NEEDS_FIX: { color: '#f97316', bg: 'rgba(249,115,22,0.1)', icon: <AlertTriangle size={20} />, label: 'NEEDS FIX' },
  REJECT: { color: '#ef4444', bg: 'rgba(239,68,68,0.1)', icon: <XCircle size={20} />, label: 'REJECTED' },
  REJECTED: { color: '#ef4444', bg: 'rgba(239,68,68,0.1)', icon: <XCircle size={20} />, label: 'REJECTED' },
};

const CATEGORY_LABELS: Record<string, string> = {
  jailbreak: 'Jailbreak Attempts',
  harm: 'Harmful Instructions',
  bias: 'Bias & Discrimination',
  privacy: 'Privacy Violations',
  misinfo: 'Misinformation',
};

export const ModelTestResults: React.FC<ModelTestResultsProps> = ({ result, sessionId, onPurify, onApprove, onReject, onRepair, repairStatus, repairLoading, repairError }) => {
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null);
  const [showAllRecords, setShowAllRecords] = useState(false);

  const ctx = result.context;
  const verdict = ctx.verdict;
  const classification = ctx.classification;
  const records = ctx.test_summary?.records || [];

  const verdictKey = verdict?.verdict || result.state;
  const vConfig = VERDICT_CONFIG[verdictKey] || VERDICT_CONFIG['WARN'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: 16, color: '#e0e0e0' }}>

      {/* ── Verdict Banner ─────────────────────────────────────── */}
      <div style={{
        background: vConfig.bg,
        border: `1px solid ${vConfig.color}`,
        borderRadius: 8,
        padding: '16px 20px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}>
        <div style={{ color: vConfig.color }}>{vConfig.icon}</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 18, color: vConfig.color }}>{vConfig.label}</div>
          <div style={{ fontSize: 13, color: '#aaa', marginTop: 2 }}>{verdict?.reason || 'Processing...'}</div>
        </div>
        {verdict?.pass_rate !== undefined && (
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 24, fontWeight: 700, color: vConfig.color }}>{verdict.pass_rate}%</div>
            <div style={{ fontSize: 11, color: '#888' }}>Pass Rate</div>
          </div>
        )}
      </div>

      {/* ── Quick Stats ────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10 }}>
        <StatCard icon={<BarChart3 size={16} />} label="Tests Run" value={verdict?.total_tests ?? 0} />
        <StatCard icon={<CheckCircle size={16} />} label="Passed" value={verdict?.pass_count ?? 0} color="#22c55e" />
        <StatCard icon={<Clock size={16} />} label="Duration" value={ctx.duration_seconds != null ? `${ctx.duration_seconds.toFixed(1)}s` : 'N/A'} />
        <StatCard icon={<Zap size={16} />} label="Model Type" value={classification?.model_type || 'N/A'} />
      </div>

      {/* ── Classification Info ─────────────────────────────────── */}
      {classification && (
        <div style={{ background: '#1e1e2e', borderRadius: 8, padding: 14 }}>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
            <Shield size={14} /> Model Classification
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 12 }}>
            <InfoRow label="Type" value={classification.model_type} />
            <InfoRow label="Runner" value={classification.runner || 'N/A'} />
            <InfoRow label="Confidence" value={`${(classification.confidence * 100).toFixed(0)}%`} />
            <InfoRow label="Security Risk" value={classification.security_risk} color={classification.security_risk === 'high' ? '#ef4444' : classification.security_risk === 'medium' ? '#eab308' : '#22c55e'} />
            {classification.architecture && <InfoRow label="Architecture" value={classification.architecture} />}
            {classification.entrypoint && <InfoRow label="Entrypoint" value={classification.entrypoint} />}
          </div>
        </div>
      )}

      {/* ── Violation Breakdown ─────────────────────────────────── */}
      {verdict?.violations && (
        <div style={{ background: '#1e1e2e', borderRadius: 8, padding: 14 }}>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 10 }}>Violation Severity</div>
          <div style={{ display: 'flex', gap: 10 }}>
            {Object.entries(verdict.violations).map(([sev, count]) => (
              <div key={sev} style={{
                flex: 1,
                background: '#2a2a3e',
                borderRadius: 6,
                padding: '8px 12px',
                textAlign: 'center',
                borderLeft: `3px solid ${SEVERITY_COLORS[sev] || '#666'}`,
              }}>
                <div style={{ fontSize: 20, fontWeight: 700, color: SEVERITY_COLORS[sev] || '#888' }}>{count}</div>
                <div style={{ fontSize: 11, color: '#888', textTransform: 'capitalize' }}>{sev}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Category Breakdown ─────────────────────────────────── */}
      {verdict?.category_breakdown && (
        <div style={{ background: '#1e1e2e', borderRadius: 8, padding: 14 }}>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 10 }}>Category Results</div>
          {Object.entries(verdict.category_breakdown).map(([cat, stats]) => {
            const passRate = stats.total > 0 ? (stats.pass / stats.total * 100) : 0;
            const isExpanded = expandedCategory === cat;
            const catRecords = records.filter(r => r.category === cat);

            return (
              <div key={cat} style={{ marginBottom: 6 }}>
                <div
                  onClick={() => setExpandedCategory(isExpanded ? null : cat)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '8px 10px', background: '#2a2a3e', borderRadius: 6,
                    cursor: 'pointer', fontSize: 13,
                  }}
                >
                  {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                  <span style={{ flex: 1, fontWeight: 500 }}>{CATEGORY_LABELS[cat] || cat}</span>
                  <span style={{ color: '#22c55e', fontSize: 12 }}>{stats.pass} pass</span>
                  <span style={{ color: '#eab308', fontSize: 12 }}>{stats.warn} warn</span>
                  <span style={{ color: '#ef4444', fontSize: 12 }}>{stats.fail} fail</span>
                  <div style={{
                    width: 60, height: 6, background: '#3a3a4e', borderRadius: 3, overflow: 'hidden',
                  }}>
                    <div style={{
                      width: `${passRate}%`, height: '100%',
                      background: passRate > 80 ? '#22c55e' : passRate > 50 ? '#eab308' : '#ef4444',
                      borderRadius: 3,
                    }} />
                  </div>
                </div>
                {isExpanded && catRecords.length > 0 && (
                  <div style={{ padding: '6px 0 6px 24px' }}>
                    {catRecords.map((rec, i) => (
                      <div key={i} style={{
                        fontSize: 11, padding: '6px 8px', marginBottom: 4,
                        background: '#252535', borderRadius: 4,
                        borderLeft: `2px solid ${rec.verdict === 'PASS' ? '#22c55e' : rec.verdict === 'WARN' ? '#eab308' : '#ef4444'}`,
                      }}>
                        <div style={{ color: '#ccc', marginBottom: 2 }}>
                          <strong>Prompt:</strong> {rec.prompt.slice(0, 80)}...
                        </div>
                        <div style={{ color: '#999' }}>
                          <strong>Response:</strong> {rec.response.slice(0, 100)}...
                        </div>
                        <div style={{ display: 'flex', gap: 8, marginTop: 4, color: '#888' }}>
                          <span>Harm: {rec.scores.harm.toFixed(2)}</span>
                          <span>Bias: {rec.scores.bias.toFixed(2)}</span>
                          <span>Refused: {rec.scores.refused ? '✓' : '✗'}</span>
                          <span style={{ color: SEVERITY_COLORS[rec.scores.severity] }}>{rec.scores.severity}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Purification Result ─────────────────────────────────── */}
      {ctx.purification_result && (
        <div style={{ background: '#1e1e2e', borderRadius: 8, padding: 14 }}>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 8 }}>Purification Result</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 12 }}>
            <InfoRow label="Retested" value={ctx.purification_result.total_retested} />
            <InfoRow label="Fixed" value={ctx.purification_result.fixed} />
            <InfoRow label="Still Failing" value={ctx.purification_result.still_failing} />
            <InfoRow label="Fix Rate" value={`${ctx.purification_result.fix_rate}%`} color={ctx.purification_result.passed ? '#22c55e' : '#ef4444'} />
          </div>
        </div>
      )}

      {/* ── Errors ─────────────────────────────────────────────── */}
      {ctx.errors.length > 0 && (
        <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid #ef4444', borderRadius: 8, padding: 14 }}>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 6, color: '#ef4444' }}>Errors</div>
          {ctx.errors.map((err, i) => (
            <div key={i} style={{ fontSize: 12, color: '#f87171', marginBottom: 4 }}>{err}</div>
          ))}
        </div>
      )}

      {/* ── LoRA Repair Progress ───────────────────────────────── */}
      {repairStatus && repairStatus.status !== 'idle' && (
        <div style={{
          background: repairStatus.status === 'completed'
            ? 'rgba(34,197,94,0.08)'
            : repairStatus.status === 'failed'
              ? 'rgba(239,68,68,0.08)'
              : 'rgba(99,102,241,0.08)',
          border: `1px solid ${repairStatus.status === 'completed' ? '#22c55e' : repairStatus.status === 'failed' ? '#ef4444' : '#6366f1'}`,
          borderRadius: 8,
          padding: 16,
        }}>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
            {(repairStatus.status === 'running' || repairStatus.status === 'in_progress') && <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />}
            {repairStatus.status === 'completed' && <CheckCircle size={16} color="#22c55e" />}
            {repairStatus.status === 'failed' && <XCircle size={16} color="#ef4444" />}
            <span>
              {(repairStatus.status === 'running' || repairStatus.status === 'in_progress')
                ? `LoRA Training — Round ${repairStatus.progress?.round ?? 1} / Stage: ${repairStatus.progress?.stage ?? '...'}`
                : repairStatus.status === 'completed'
                  ? `LoRA Repair Complete (${repairStatus.result?.rounds_completed ?? 1} round${(repairStatus.result?.rounds_completed ?? 1) > 1 ? 's' : ''})`
                  : 'LoRA Repair Failed'}
            </span>
          </div>

          {(repairStatus.status === 'running' || repairStatus.status === 'in_progress') && repairStatus.progress && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 8 }}>
              <div style={{ background: '#2a2a3e', borderRadius: 6, padding: '8px 12px', textAlign: 'center' }}>
                <div style={{ fontSize: 18, fontWeight: 700, color: '#6366f1' }}>{repairStatus.progress.round || 0}</div>
                <div style={{ fontSize: 11, color: '#888' }}>Round</div>
              </div>
              <div style={{ background: '#2a2a3e', borderRadius: 6, padding: '8px 12px', textAlign: 'center' }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#a5b4fc' }}>{repairStatus.progress.status || repairStatus.progress.stage || 'starting'}</div>
                <div style={{ fontSize: 11, color: '#888' }}>Stage</div>
              </div>
              <div style={{ background: '#2a2a3e', borderRadius: 6, padding: '8px 12px', textAlign: 'center' }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#c4b5fd' }}>
                  {repairStatus.progress.status === 'training' ? 'Training...' : 'Processing...'}
                </div>
                <div style={{ fontSize: 11, color: '#888' }}>Status</div>
              </div>
            </div>
          )}

          {repairStatus.status === 'completed' && repairStatus.result && (
            <div>
              {/* ── Summary Stats ── */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 12 }}>
                <div style={{ background: '#2a2a3e', borderRadius: 6, padding: '8px 12px', textAlign: 'center' }}>
                  <div style={{ fontSize: 18, fontWeight: 700, color: repairStatus.result.outcome === 'ACCEPTED' ? '#22c55e' : '#ef4444' }}>
                    {repairStatus.result.outcome}
                  </div>
                  <div style={{ fontSize: 11, color: '#888' }}>Outcome</div>
                </div>
                <div style={{ background: '#2a2a3e', borderRadius: 6, padding: '8px 12px', textAlign: 'center' }}>
                  <div style={{ fontSize: 18, fontWeight: 700, color: '#22c55e' }}>{repairStatus.result.final_pass_rate}%</div>
                  <div style={{ fontSize: 11, color: '#888' }}>Final Pass Rate</div>
                </div>
                <div style={{ background: '#2a2a3e', borderRadius: 6, padding: '8px 12px', textAlign: 'center' }}>
                  <div style={{ fontSize: 18, fontWeight: 700, color: '#6366f1' }}>{repairStatus.result.rounds_completed}</div>
                  <div style={{ fontSize: 11, color: '#888' }}>Rounds</div>
                </div>
              </div>

              {/* ── Per-Round History Table ── */}
              {repairStatus.result.round_history && repairStatus.result.round_history.length > 0 && (
                <div style={{ background: '#1a1a2e', borderRadius: 6, overflow: 'hidden' }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '60px 1fr 1fr 1fr 90px', fontSize: 11, color: '#666', padding: '6px 10px', borderBottom: '1px solid #2a2a3e' }}>
                    <span>Round</span><span>Passed</span><span>Failed</span><span>Pass Rate</span><span>Verdict</span>
                  </div>
                  {repairStatus.result.round_history.map((row: any, idx: number) => {
                    const isBest = row.pass_rate === repairStatus.result!.final_pass_rate && idx === repairStatus.result!.round_history.length - 1;
                    const vColor = row.verdict === 'APPROVE' || row.verdict === 'WARN' ? '#22c55e' : '#ef4444';
                    return (
                      <div key={idx} style={{
                        display: 'grid', gridTemplateColumns: '60px 1fr 1fr 1fr 90px',
                        fontSize: 12, padding: '7px 10px',
                        background: isBest ? 'rgba(99,102,241,0.12)' : 'transparent',
                        borderBottom: '1px solid #1e1e2e',
                        alignItems: 'center',
                      }}>
                        <span style={{ color: '#a5b4fc', fontWeight: 600 }}>#{row.round}{isBest ? ' ★' : ''}</span>
                        <span style={{ color: '#22c55e' }}>{row.pass_count}</span>
                        <span style={{ color: '#ef4444' }}>{row.fail_count}</span>
                        <span style={{ color: row.pass_rate >= 80 ? '#22c55e' : row.pass_rate >= 60 ? '#eab308' : '#ef4444', fontWeight: 600 }}>{row.pass_rate}%</span>
                        <span style={{ color: vColor, fontSize: 10, fontWeight: 700 }}>{row.verdict ?? '—'}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {repairStatus.status === 'failed' && repairStatus.error && (
            <div style={{ fontSize: 12, color: '#f87171', marginTop: 4 }}>{repairStatus.error}</div>
          )}
        </div>
      )}

      {repairError && !repairStatus && (
        <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid #ef4444', borderRadius: 8, padding: 12, fontSize: 13, color: '#f87171' }}>
          {repairError}
        </div>
      )}

      {/* ── Action Buttons ─────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
        {sessionId && (
          <button
            onClick={() => {
              const url = `http://localhost:8000/api/model/${sessionId}/report`;
              const a = document.createElement('a');
              a.href = url;
              a.download = `ethos_report_${sessionId.slice(0, 8)}.pdf`;
              document.body.appendChild(a);
              a.click();
              document.body.removeChild(a);
            }}
            style={{ ...btnStyle('#6366f1'), display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <Download size={14} /> Download Report
          </button>
        )}
        {(verdictKey === 'REJECT' || verdictKey === 'REJECTED' || verdictKey === 'NEEDS_FIX') && onRepair && (
          <button
            onClick={onRepair}
            disabled={repairLoading}
            style={{
              ...btnStyle('#f97316'),
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              opacity: repairLoading ? 0.6 : 1,
              cursor: repairLoading ? 'not-allowed' : 'pointer',
            }}
          >
            {repairLoading ? <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} /> : <Wrench size={14} />}
            {repairLoading ? 'Training...' : 'Train & Fix Model'}
          </button>
        )}
        {verdictKey === 'NEEDS_FIX' && onPurify && (
          <button onClick={onPurify} style={btnStyle('#8b5cf6')}>Purify Model</button>
        )}
        {onApprove && (
          <button onClick={onApprove} style={btnStyle('#22c55e')}>Approve</button>
        )}
        {onReject && (
          <button onClick={onReject} style={btnStyle('#ef4444')}>Reject</button>
        )}
      </div>

      <style>{`@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>

      {/* ── State Log ──────────────────────────────────────────── */}
      {result.state_log.length > 0 && (
        <div style={{ fontSize: 11, color: '#666' }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Pipeline States:</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {result.state_log.map((entry, i) => (
              <span key={i} style={{ background: '#2a2a3e', padding: '2px 6px', borderRadius: 3 }}>
                {entry.from} → {entry.to}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

// ── Helper Components ────────────────────────────────────────────────

const StatCard: React.FC<{ icon: React.ReactNode; label: string; value: string | number; color?: string }> = ({ icon, label, value, color }) => (
  <div style={{ background: '#1e1e2e', borderRadius: 8, padding: '10px 12px', textAlign: 'center' }}>
    <div style={{ color: color || '#888', marginBottom: 4 }}>{icon}</div>
    <div style={{ fontSize: 18, fontWeight: 700, color: color || '#e0e0e0' }}>{value}</div>
    <div style={{ fontSize: 11, color: '#888' }}>{label}</div>
  </div>
);

const InfoRow: React.FC<{ label: string; value: string | number; color?: string }> = ({ label, value, color }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0' }}>
    <span style={{ color: '#888' }}>{label}</span>
    <span style={{ color: color || '#ccc', fontWeight: 500 }}>{value}</span>
  </div>
);

const btnStyle = (color: string): React.CSSProperties => ({
  background: color,
  color: '#fff',
  border: 'none',
  borderRadius: 6,
  padding: '8px 16px',
  fontSize: 13,
  fontWeight: 600,
  cursor: 'pointer',
});

export default ModelTestResults;
