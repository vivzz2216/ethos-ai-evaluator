import React, { useState, useMemo } from 'react';
import { Search, Check, Sparkles, Zap, Brain, Cpu, Star, ChevronRight } from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────
export interface AIModel {
  id: string;
  name: string;
  provider: string;
  description: string;
  badge?: string;
  icon: 'sparkles' | 'zap' | 'brain' | 'cpu' | 'star';
  color: string;
  capabilities: string[];
}

interface IDEModelSidebarProps {
  selectedModelId: string;
  onModelSelect: (modelId: string) => void;
}

// ── Pre-loaded Models ──────────────────────────────────────────────
export const AI_MODELS: AIModel[] = [
  {
    id: 'claude-opus-4.5',
    name: 'Claude Opus 4.5',
    provider: 'Anthropic',
    description: 'Best for complex tasks requiring deep reasoning and analysis',
    badge: 'Most Capable',
    icon: 'sparkles',
    color: '#d97706',
    capabilities: ['Complex reasoning', 'Long context', 'Code generation', 'Analysis'],
  },
  {
    id: 'claude-sonnet-4.5',
    name: 'Claude Sonnet 4.5',
    provider: 'Anthropic',
    description: 'Balanced performance — recommended for most tasks',
    badge: 'Recommended',
    icon: 'star',
    color: '#7c3aed',
    capabilities: ['Fast responses', 'Code generation', 'General tasks', 'Balanced'],
  },
  {
    id: 'claude-haiku-4.5',
    name: 'Claude Haiku 4.5',
    provider: 'Anthropic',
    description: 'Fast and efficient for quick tasks and simple queries',
    icon: 'zap',
    color: '#059669',
    capabilities: ['Ultra fast', 'Cost effective', 'Simple tasks', 'Chat'],
  },
  {
    id: 'gpt-4-turbo',
    name: 'GPT-4 Turbo',
    provider: 'OpenAI',
    description: 'Alternative high-performance model with broad capabilities',
    icon: 'brain',
    color: '#2563eb',
    capabilities: ['Broad knowledge', 'Code generation', 'Creative writing', 'Analysis'],
  },
  {
    id: 'gpt-4o',
    name: 'GPT-4o',
    provider: 'OpenAI',
    description: 'Multimodal capabilities with vision and audio support',
    icon: 'cpu',
    color: '#dc2626',
    capabilities: ['Multimodal', 'Vision', 'Audio', 'Fast inference'],
  },
];

// ── Icon Map ───────────────────────────────────────────────────────
const ICON_MAP = {
  sparkles: Sparkles,
  zap: Zap,
  brain: Brain,
  cpu: Cpu,
  star: Star,
};

// ── Model Card ─────────────────────────────────────────────────────
const ModelCard: React.FC<{
  model: AIModel;
  isSelected: boolean;
  onSelect: () => void;
}> = ({ model, isSelected, onSelect }) => {
  const [hovered, setHovered] = useState(false);
  const Icon = ICON_MAP[model.icon];

  return (
    <button
      onClick={onSelect}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={`w-full text-left rounded-md border transition-all duration-200 ${
        isSelected
          ? 'border-[#007acc] bg-[#094771]/60 shadow-[0_0_0_1px_rgba(0,122,204,0.3)]'
          : 'border-[#3e3e42] bg-[#2d2d2d] hover:border-[#555] hover:bg-[#333]'
      }`}
    >
      <div className="p-3">
        {/* Top row: icon + name + badge */}
        <div className="flex items-center gap-2 mb-1.5">
          <div
            className="w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0 transition-transform duration-200"
            style={{
              backgroundColor: `${model.color}20`,
              transform: hovered ? 'scale(1.1)' : 'scale(1)',
            }}
          >
            <Icon className="w-4 h-4" style={{ color: model.color }} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1.5">
              <span className={`text-[13px] font-medium truncate ${isSelected ? 'text-white' : 'text-[#cccccc]'}`}>
                {model.name}
              </span>
              {isSelected && <Check className="w-3.5 h-3.5 text-[#007acc] flex-shrink-0" />}
            </div>
            <span className="text-[10px] text-[#888]">{model.provider}</span>
          </div>
          {model.badge && (
            <span
              className="text-[9px] font-semibold px-1.5 py-0.5 rounded-full flex-shrink-0 uppercase tracking-wider"
              style={{
                backgroundColor: `${model.color}20`,
                color: model.color,
              }}
            >
              {model.badge}
            </span>
          )}
        </div>

        {/* Description */}
        <p className="text-[11px] text-[#999] leading-relaxed mb-2">{model.description}</p>

        {/* Capability tags */}
        <div className="flex flex-wrap gap-1">
          {model.capabilities.map(cap => (
            <span
              key={cap}
              className="text-[9px] px-1.5 py-0.5 rounded bg-[#3c3c3c] text-[#aaa]"
            >
              {cap}
            </span>
          ))}
        </div>
      </div>
    </button>
  );
};

// ── Main Component ─────────────────────────────────────────────────
const IDEModelSidebar: React.FC<IDEModelSidebarProps> = ({ selectedModelId, onModelSelect }) => {
  const [search, setSearch] = useState('');

  const filtered = useMemo(() => {
    if (!search.trim()) return AI_MODELS;
    const q = search.toLowerCase();
    return AI_MODELS.filter(
      m =>
        m.name.toLowerCase().includes(q) ||
        m.provider.toLowerCase().includes(q) ||
        m.description.toLowerCase().includes(q) ||
        m.capabilities.some(c => c.toLowerCase().includes(q))
    );
  }, [search]);

  const selectedModel = AI_MODELS.find(m => m.id === selectedModelId);

  return (
    <div className="h-full flex flex-col bg-[#252526] select-none">
      {/* Header */}
      <div className="flex items-center justify-between px-3 h-[35px] flex-shrink-0 border-b border-[#3e3e42]">
        <span className="text-[11px] font-semibold tracking-wider text-[#bbbbbb] uppercase">AI Models</span>
        {selectedModel && (
          <span className="text-[10px] text-[#007acc] truncate max-w-[100px]">{selectedModel.name}</span>
        )}
      </div>

      {/* Search */}
      <div className="px-2 py-1.5 border-b border-[#3e3e42]">
        <div className="flex items-center bg-[#3c3c3c] rounded px-2 h-[24px]">
          <Search className="w-3.5 h-3.5 text-[#848484] flex-shrink-0" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search models..."
            className="bg-transparent text-[12px] text-[#cccccc] placeholder-[#848484] outline-none w-full ml-1.5"
          />
        </div>
      </div>

      {/* Model List */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-2">
        {filtered.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-[12px] text-[#666]">No models match your search</p>
          </div>
        ) : (
          filtered.map(model => (
            <ModelCard
              key={model.id}
              model={model}
              isSelected={selectedModelId === model.id}
              onSelect={() => onModelSelect(model.id)}
            />
          ))
        )}
      </div>

      {/* Footer info */}
      <div className="px-3 py-2 border-t border-[#3e3e42]">
        <div className="flex items-center gap-1.5 text-[10px] text-[#666]">
          <ChevronRight className="w-3 h-3" />
          <span>
            {selectedModel
              ? `Active: ${selectedModel.name}`
              : 'Select a model to begin'}
          </span>
        </div>
      </div>
    </div>
  );
};

export default IDEModelSidebar;

export const getSelectedModel = (id: string) => AI_MODELS.find(m => m.id === id);
export const getDefaultModelId = () => 'claude-sonnet-4.5';
