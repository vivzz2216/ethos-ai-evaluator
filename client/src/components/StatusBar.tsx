import React from 'react';
import { GitBranch, AlertCircle, CheckCircle, X } from 'lucide-react';

interface StatusBarProps {
  currentFile?: string;
  language?: string;
  line?: number;
  column?: number;
  errors?: number;
  warnings?: number;
}

const StatusBar: React.FC<StatusBarProps> = ({
  currentFile,
  language = 'python',
  line = 1,
  column = 1,
  errors = 0,
  warnings = 0
}) => {
  return (
    <div className="h-6 bg-blue-600 text-white text-xs flex items-center justify-between px-4">
      <div className="flex items-center space-x-4">
        <div className="flex items-center space-x-1">
          <GitBranch className="w-3 h-3" />
          <span>main</span>
        </div>
        <div className="flex items-center space-x-1">
          <span className="text-blue-200">●</span>
          <span>ETHOS Editor</span>
        </div>
      </div>
      
      <div className="flex items-center space-x-4">
        {currentFile && (
          <span className="text-blue-200">{currentFile}</span>
        )}
        
        <div className="flex items-center space-x-2">
          <span className="uppercase">{language}</span>
          <span className="text-blue-200">Ln {line}, Col {column}</span>
        </div>
        
        {errors > 0 && (
          <div className="flex items-center space-x-1 text-red-300">
            <X className="w-3 h-3" />
            <span>{errors}</span>
          </div>
        )}
        
        {warnings > 0 && (
          <div className="flex items-center space-x-1 text-yellow-300">
            <AlertCircle className="w-3 h-3" />
            <span>{warnings}</span>
          </div>
        )}
        
        {errors === 0 && warnings === 0 && (
          <div className="flex items-center space-x-1 text-green-300">
            <CheckCircle className="w-3 h-3" />
            <span>No Problems</span>
          </div>
        )}
      </div>
    </div>
  );
};

export default StatusBar;
