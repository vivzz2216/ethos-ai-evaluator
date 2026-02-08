import React from 'react';
import { Brain, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';

interface ModelOption {
  id: string;
  name: string;
  description: string;
  size: string;
  hfModelName: string;
}

const AVAILABLE_MODELS: ModelOption[] = [
  {
    id: 'tiny-gpt2',
    name: 'Tiny GPT-2',
    description: 'Ultra-lightweight (35MB) - Fast testing',
    size: '35 MB',
    hfModelName: 'sshleifer/tiny-gpt2'
  },
  {
    id: 'gpt2',
    name: 'GPT-2',
    description: 'Standard quality (~500MB) - Good balance',
    size: '~500 MB',
    hfModelName: 'openai-community/gpt2'
  },
  {
    id: 't5-small',
    name: 'T5 Small',
    description: 'Reasoning-focused (~240MB) - Better for ethics',
    size: '~240 MB',
    hfModelName: 'google-t5/t5-small'
  }
];

interface ModelSelectorProps {
  selectedModel: string;
  onModelSelect: (modelId: string) => void;
}

export const ModelSelector: React.FC<ModelSelectorProps> = ({ selectedModel, onModelSelect }) => {
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="w-4 h-4 text-blue-400" />
          <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
            Test Model
          </h3>
        </div>
        {selectedModel && (
          <Badge variant="secondary" className="text-xs">
            Selected
          </Badge>
        )}
      </div>
      
      <div className="space-y-2">
        {AVAILABLE_MODELS.map((model) => {
          const isSelected = selectedModel === model.id;
          
          return (
            <button
              key={model.id}
              onClick={() => onModelSelect(model.id)}
              className={`w-full text-left p-3 rounded-lg border transition-all duration-200 ${
                isSelected
                  ? 'border-blue-500 bg-blue-500/10 shadow-md shadow-blue-500/20'
                  : 'border-gray-700 bg-gray-800/50 hover:border-gray-600 hover:bg-gray-800'
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-sm font-medium ${isSelected ? 'text-blue-300' : 'text-gray-200'}`}>
                      {model.name}
                    </span>
                    {isSelected && (
                      <Check className="w-4 h-4 text-blue-400 flex-shrink-0" />
                    )}
                  </div>
                  <p className="text-xs text-gray-400 mb-1">{model.description}</p>
                  <span className="text-xs text-gray-500">{model.size}</span>
                </div>
              </div>
            </button>
          );
        })}
      </div>
      
      <div className="pt-2 border-t border-gray-700">
        <p className="text-xs text-gray-500">
          Select a model above, then click "Ethical Test" to evaluate it.
        </p>
      </div>
    </div>
  );
};

export const getModelByName = (modelId: string): ModelOption | undefined => {
  return AVAILABLE_MODELS.find(m => m.id === modelId);
};

export const getDefaultModel = (): ModelOption => {
  return AVAILABLE_MODELS[0];
};




