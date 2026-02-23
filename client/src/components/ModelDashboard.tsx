/**
 * ModelDashboard - Admin panel showing all uploaded models with status, test results, and actions.
 */
import React, { useEffect, useState, useCallback } from 'react';
import {
  Shield, RefreshCw, CheckCircle, XCircle, AlertTriangle,
  Clock, Search, Loader2, ChevronDown, ChevronRight, Trash2,
} from 'lucide-react';
import { useModelManagement, useModelTesting, type ModelListItem } from '../hooks/use-model-testing';
import { ModelTestResults } from './ModelTestResults';

interface ModelDashboardProps {
  onSelectSession?: (sessionId: string) => void;
}

const STATE_BADGES: Record<string, { color: string; bg: string; label: string }> = {
  IDLE: { color: '#888', bg: '#2a2a3e', label: 'Idle' },
  UPLOADED: { color: '#3b82f6', bg: 'rgba(59,130,246,0.1)', label: 'Uploaded' },
  SCANNING: { color: '#3b82f6', bg: 'rgba(59,130,246,0.1)', label: 'Scanning' },
  CLASSIFIED: { color: '#8b5cf6', bg: 'rgba(139,92,246,0.1)', label: 'Classified' },
  INSTALLING: { color: '#f97316', bg: 'rgba(249,115,22,0.1)', label: 'Installing' },
  READY: { color: '#06b6d4', bg: 'rgba(6,182,212,0.1)', label: 'Ready' },
  TESTING: { color: '#f97316', bg: 'rgba(249,115,22,0.1)', label: 'Testing' },
  SCORED: { color: '#eab308', bg: 'rgba(234,179,8,0.1)', label: 'Scored' },
  FIXING: { color: '#f97316', bg: 'rgba(249,115,22,0.1)', label: 'Fixing' },
  APPROVED: { color: '#22c55e', bg: 'rgba(34,197,94,0.1)', label: 'Approved' },
  REJECTED: { color: '#ef4444', bg: 'rgba(239,68,68,0.1)', label: 'Rejected' },
  ERROR: { color: '#ef4444', bg: 'rgba(239,68,68,0.1)', label: 'Error' },
};

export const ModelDashboard: React.FC<ModelDashboardProps> = ({ onSelectSession }) => {
  const { models, fetchModels, approveModel, rejectModel, loading } = useModelManagement();
  const { result: selectedResult, getResults } = useModelTesting();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [loadingResults, setLoadingResults] = useState(false);

  useEffect(() => {
    fetchModels();
    const interval = setInterval(fetchModels, 10000);
    return () => clearInterval(interval);
  }, [fetchModels]);

  const handleSelect = useCallback(async (sid: string) => {
    if (selectedId === sid) {
      setSelectedId(null);
      return;
    }
    setSelectedId(sid);
    setLoadingResults(true);
    await getResults(sid);
    setLoadingResults(false);
  }, [selectedId, getResults]);

  const handleApprove = useCallback(async (sid: string) => {
    await approveModel(sid);
  }, [approveModel]);

  const handleReject = useCallback(async (sid: string) => {
    await rejectModel(sid, 'Manual rejection from dashboard');
  }, [rejectModel]);

  const filteredModels = models.filter(m => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      m.session_id.toLowerCase().includes(q) ||
      m.processing_state.toLowerCase().includes(q) ||
      (m.classification?.model_type || '').toLowerCase().includes(q)
    );
  });

  // Stats
  const totalModels = models.length;
  const approved = models.filter(m => m.processing_state === 'APPROVED').length;
  const rejected = models.filter(m => m.processing_state === 'REJECTED').length;
  const pending = models.filter(m => !['APPROVED', 'REJECTED', 'ERROR'].includes(m.processing_state)).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#1a1a2e', color: '#e0e0e0' }}>
      {/* Header */}
      <div style={{
        padding: '12px 16px', borderBottom: '1px solid #2a2a3e',
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <Shield size={18} color="#8b5cf6" />
        <span style={{ fontWeight: 700, fontSize: 15 }}>Model Dashboard</span>
        <div style={{ flex: 1 }} />
        <button onClick={() => fetchModels()} disabled={loading} style={{
          background: 'none', border: '1px solid #3a3a4e', borderRadius: 6,
          padding: '4px 10px', color: '#888', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4, fontSize: 12,
        }}>
          <RefreshCw size={12} className={loading ? 'spin' : ''} /> Refresh
        </button>
      </div>

      {/* Stats Bar */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8,
        padding: '10px 16px', borderBottom: '1px solid #2a2a3e',
      }}>
        <MiniStat label="Total" value={totalModels} color="#8b5cf6" />
        <MiniStat label="Approved" value={approved} color="#22c55e" />
        <MiniStat label="Rejected" value={rejected} color="#ef4444" />
        <MiniStat label="Pending" value={pending} color="#eab308" />
      </div>

      {/* Search */}
      <div style={{ padding: '8px 16px', borderBottom: '1px solid #2a2a3e' }}>
        <div style={{ position: 'relative' }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: 9, color: '#666' }} />
          <input
            type="text" placeholder="Search models..."
            value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
            style={{
              width: '100%', padding: '7px 10px 7px 30px', fontSize: 12,
              background: '#2a2a3e', border: '1px solid #3a3a4e',
              borderRadius: 6, color: '#e0e0e0', outline: 'none',
            }}
          />
        </div>
      </div>

      {/* Model List */}
      <div style={{ flex: 1, overflow: 'auto', padding: '8px 16px' }}>
        {filteredModels.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 20px', color: '#666' }}>
            {models.length === 0 ? 'No models uploaded yet.' : 'No models match your search.'}
          </div>
        ) : (
          filteredModels.map(model => {
            const isSelected = selectedId === model.session_id;
            const badge = STATE_BADGES[model.processing_state] || STATE_BADGES['IDLE'];

            return (
              <div key={model.session_id} style={{ marginBottom: 8 }}>
                {/* Model Row */}
                <div
                  onClick={() => handleSelect(model.session_id)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '10px 12px', background: isSelected ? '#252540' : '#1e1e2e',
                    borderRadius: 8, cursor: 'pointer', fontSize: 13,
                    border: isSelected ? '1px solid #3a3a5e' : '1px solid transparent',
                    transition: 'all 0.15s',
                  }}
                >
                  {isSelected ? <ChevronDown size={14} /> : <ChevronRight size={14} />}

                  {/* Type Badge */}
                  <div style={{
                    background: '#2a2a3e', padding: '2px 8px', borderRadius: 4,
                    fontSize: 11, fontWeight: 600, textTransform: 'uppercase',
                    color: '#8b5cf6', minWidth: 70, textAlign: 'center',
                  }}>
                    {model.classification?.model_type || '—'}
                  </div>

                  {/* Session ID */}
                  <div style={{ flex: 1, fontFamily: 'monospace', fontSize: 11, color: '#aaa' }}>
                    {model.session_id.slice(0, 8)}...
                  </div>

                  {/* State Badge */}
                  <div style={{
                    background: badge.bg, color: badge.color,
                    padding: '2px 10px', borderRadius: 12, fontSize: 11, fontWeight: 600,
                  }}>
                    {badge.label}
                  </div>

                  {/* Actions */}
                  {model.processing_state !== 'APPROVED' && model.processing_state !== 'REJECTED' && (
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button onClick={e => { e.stopPropagation(); handleApprove(model.session_id); }}
                        title="Approve" style={iconBtnStyle('#22c55e')}>
                        <CheckCircle size={14} />
                      </button>
                      <button onClick={e => { e.stopPropagation(); handleReject(model.session_id); }}
                        title="Reject" style={iconBtnStyle('#ef4444')}>
                        <XCircle size={14} />
                      </button>
                    </div>
                  )}
                </div>

                {/* Expanded Details */}
                {isSelected && (
                  <div style={{ padding: '8px 0 8px 28px' }}>
                    {loadingResults ? (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#888', fontSize: 12, padding: 12 }}>
                        <Loader2 size={14} className="spin" /> Loading results...
                      </div>
                    ) : selectedResult ? (
                      <ModelTestResults
                        result={selectedResult}
                        sessionId={model.session_id}
                        onApprove={() => handleApprove(model.session_id)}
                        onReject={() => handleReject(model.session_id)}
                      />
                    ) : (
                      <div style={{ color: '#888', fontSize: 12, padding: 12 }}>
                        No test results available. Run tests from the Model Testing panel.
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .spin { animation: spin 1s linear infinite; }
      `}</style>
    </div>
  );
};

// ── Helper Components ────────────────────────────────────────────────

const MiniStat: React.FC<{ label: string; value: number; color: string }> = ({ label, value, color }) => (
  <div style={{ textAlign: 'center' }}>
    <div style={{ fontSize: 18, fontWeight: 700, color }}>{value}</div>
    <div style={{ fontSize: 10, color: '#888' }}>{label}</div>
  </div>
);

const iconBtnStyle = (color: string): React.CSSProperties => ({
  background: 'none', border: 'none', color, cursor: 'pointer',
  padding: 4, borderRadius: 4, display: 'flex', alignItems: 'center',
});

export default ModelDashboard;
