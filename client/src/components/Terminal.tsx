import React, { useRef, useEffect, useState } from 'react';
import { Terminal as TerminalIcon, Play, Square, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface TerminalProps {
  onRunCode?: (code: string, language: string) => Promise<string>;
  isRunning?: boolean;
  output?: string;
  error?: string;
  currentFile?: string;
}

const Terminal: React.FC<TerminalProps> = ({
  onRunCode,
  isRunning = false,
  output = '',
  error = '',
  currentFile = 'main.py'
}) => {
  const [terminalOutput, setTerminalOutput] = useState('');
  const [isExecuting, setIsExecuting] = useState(false);
  const outputRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [terminalOutput, output, error]);

  useEffect(() => {
    if (output) {
      setTerminalOutput(prev => prev + output);
    }
  }, [output]);

  useEffect(() => {
    if (error) {
      setTerminalOutput(prev => prev + `\nError: ${error}`);
    }
  }, [error]);

  const clearTerminal = () => {
    setTerminalOutput('');
  };

  const handleRunCode = async () => {
    if (!onRunCode) return;
    
    setIsExecuting(true);
    setTerminalOutput(prev => prev + `\n$ python ${currentFile}\n`);
    
    try {
      const result = await onRunCode('', 'python');
      // Don't append the result here as it's already handled by the output prop
      // setTerminalOutput(prev => prev + result);
    } catch (err) {
      setTerminalOutput(prev => prev + `\nError: ${err}`);
    } finally {
      setIsExecuting(false);
    }
  };

  return (
    <div className="bg-gray-900 text-green-400 overflow-hidden border-t border-gray-700 h-full flex flex-col">
      {/* Terminal Header */}
      <div className="bg-gray-800 px-4 py-2 flex items-center justify-between border-b border-gray-700 flex-shrink-0">
        <div className="flex items-center space-x-2">
          <TerminalIcon className="w-4 h-4 text-green-400" />
          <span className="text-sm font-medium">Terminal</span>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRunCode}
            disabled={isExecuting || isRunning}
            className="h-6 px-2 text-xs hover:bg-gray-700"
          >
            <Play className="w-3 h-3 mr-1" />
            Run
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={clearTerminal}
            className="h-6 px-2 text-xs hover:bg-gray-700"
          >
            <RotateCcw className="w-3 h-3 mr-1" />
            Clear
          </Button>
        </div>
      </div>

      {/* Terminal Output */}
      <div 
        ref={outputRef}
        className="p-4 flex-1 overflow-y-auto font-mono text-sm leading-relaxed whitespace-pre-wrap"
        style={{ fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace' }}
      >
        {terminalOutput || 'Welcome to ETHOS Terminal\nType your commands here...\n'}
        {output && (
          <div className="text-white">
            {output}
          </div>
        )}
        {error && (
          <div className="text-red-400">
            {error}
          </div>
        )}
        {(isExecuting || isRunning) && (
          <span className="animate-pulse">█</span>
        )}
      </div>
    </div>
  );
};

export default Terminal;
