import React from 'react';
import { Settings, ToggleLeft, ToggleRight, ChevronRight } from 'lucide-react';
import type { TerminalConfig } from './IDETerminal';

interface IDESettingsProps {
  config: TerminalConfig;
  onConfigChange: (config: TerminalConfig) => void;
}

// ── Toggle Switch ──────────────────────────────────────────────────
const Toggle: React.FC<{
  enabled: boolean;
  onChange: (val: boolean) => void;
  label: string;
  description?: string;
}> = ({ enabled, onChange, label, description }) => (
  <div
    className="flex items-center justify-between py-2.5 px-1 cursor-pointer group"
    onClick={() => onChange(!enabled)}
  >
    <div className="flex-1 min-w-0 mr-3">
      <div className="text-[13px] text-[#cccccc] group-hover:text-white transition-colors">{label}</div>
      {description && <div className="text-[11px] text-[#888] mt-0.5">{description}</div>}
    </div>
    {enabled ? (
      <ToggleRight className="w-5 h-5 text-[#007acc] flex-shrink-0" />
    ) : (
      <ToggleLeft className="w-5 h-5 text-[#555] flex-shrink-0" />
    )}
  </div>
);

// ── Select ─────────────────────────────────────────────────────────
const Select: React.FC<{
  value: string;
  options: { value: string; label: string }[];
  onChange: (val: string) => void;
  label: string;
  description?: string;
}> = ({ value, options, onChange, label, description }) => (
  <div className="py-2.5 px-1">
    <div className="text-[13px] text-[#cccccc] mb-1">{label}</div>
    {description && <div className="text-[11px] text-[#888] mb-2">{description}</div>}
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="w-full bg-[#3c3c3c] text-[#cccccc] text-[12px] px-2 py-1.5 rounded border border-[#3e3e42] outline-none focus:border-[#007acc] transition-colors"
    >
      {options.map(opt => (
        <option key={opt.value} value={opt.value}>{opt.label}</option>
      ))}
    </select>
  </div>
);

// ── Main Settings Panel ────────────────────────────────────────────
const IDESettings: React.FC<IDESettingsProps> = ({ config, onConfigChange }) => {
  const update = (partial: Partial<TerminalConfig>) => {
    onConfigChange({ ...config, ...partial });
  };

  return (
    <div className="h-full flex flex-col bg-[#252526] select-none">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 h-[35px] flex-shrink-0 border-b border-[#3e3e42]">
        <Settings className="w-4 h-4 text-[#bbbbbb]" />
        <span className="text-[11px] font-semibold tracking-wider text-[#bbbbbb] uppercase">Settings</span>
      </div>

      {/* Settings List */}
      <div className="flex-1 overflow-y-auto px-3 py-2">
        {/* Section: Virtual Environment */}
        <div className="mb-4">
          <div className="text-[10px] font-semibold tracking-wider text-[#888] uppercase mb-1 flex items-center gap-1">
            <ChevronRight className="w-3 h-3" /> Virtual Environment
          </div>
          <div className="border-b border-[#3e3e42]">
            <Toggle
              enabled={config.autoCreateVenv}
              onChange={val => update({ autoCreateVenv: val })}
              label="Auto-create venv"
              description="Automatically create a virtual environment for Python projects"
            />
          </div>
          <div className="border-b border-[#3e3e42]">
            <Toggle
              enabled={config.autoActivateVenv}
              onChange={val => update({ autoActivateVenv: val })}
              label="Auto-activate venv"
              description="Automatically activate the virtual environment on terminal open"
            />
          </div>
          <div className="border-b border-[#3e3e42]">
            <Select
              value={config.autoInstallDeps}
              options={[
                { value: 'ask', label: 'Ask before installing' },
                { value: 'always', label: 'Always install automatically' },
                { value: 'never', label: 'Never auto-install' },
              ]}
              onChange={val => update({ autoInstallDeps: val as 'ask' | 'always' | 'never' })}
              label="Auto-install dependencies"
              description="How to handle requirements.txt when detected"
            />
          </div>
        </div>

        {/* Section: Python */}
        <div className="mb-4">
          <div className="text-[10px] font-semibold tracking-wider text-[#888] uppercase mb-1 flex items-center gap-1">
            <ChevronRight className="w-3 h-3" /> Python
          </div>
          <div className="border-b border-[#3e3e42]">
            <Select
              value={config.preferredPython}
              options={[
                { value: 'python', label: 'python' },
                { value: 'python3', label: 'python3' },
              ]}
              onChange={val => update({ preferredPython: val })}
              label="Preferred Python command"
              description="Which Python command to use for venv creation"
            />
          </div>
        </div>

        {/* Section: File Tree */}
        <div className="mb-4">
          <div className="text-[10px] font-semibold tracking-wider text-[#888] uppercase mb-1 flex items-center gap-1">
            <ChevronRight className="w-3 h-3" /> File Tree
          </div>
          <div className="border-b border-[#3e3e42]">
            <Toggle
              enabled={config.showVenvInTree}
              onChange={val => update({ showVenvInTree: val })}
              label="Show venv in file tree"
              description="Display the virtual environment folder in the file explorer"
            />
          </div>
        </div>

        {/* Info */}
        <div className="mt-4 p-3 rounded bg-[#1e1e1e] border border-[#3e3e42]">
          <div className="text-[11px] text-[#888] leading-relaxed">
            <p className="mb-2"><strong className="text-[#ccc]">Terminal Modes:</strong></p>
            <p className="mb-1">
              <span className="inline-flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" /> <strong>pty</strong>
              </span>
              {' '}— Real terminal via node-pty (requires terminal server)
            </p>
            <p className="mb-2">
              <span className="inline-flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-orange-400 inline-block" /> <strong>http</strong>
              </span>
              {' '}— HTTP fallback via Python backend
            </p>
            <p className="text-[10px] text-[#666]">
              Start the terminal server: <code className="bg-[#333] px-1 rounded">node server/terminal-server.js</code>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default IDESettings;
