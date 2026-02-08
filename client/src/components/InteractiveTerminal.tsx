import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Terminal as TerminalIcon, Play, Square, RotateCcw, Send } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface InteractiveTerminalProps {
  onRunCode?: (code: string, language: string) => Promise<string>;
  isRunning?: boolean;
  output?: string;
  error?: string;
  currentFile?: string;
}

interface Command {
  id: string;
  command: string;
  output: string;
  timestamp: Date;
}

const InteractiveTerminal: React.FC<InteractiveTerminalProps> = ({
  onRunCode,
  isRunning = false,
  output = '',
  error = '',
  currentFile = 'main.py'
}) => {
  const [terminalOutput, setTerminalOutput] = useState('');
  const [isExecuting, setIsExecuting] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [commandHistory, setCommandHistory] = useState<Command[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const outputRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

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

  const executeCommand = useCallback(async (command: string) => {
    if (!command.trim()) return;

    // Add command to history
    const newCommand: Command = {
      id: Date.now().toString(),
      command,
      output: '',
      timestamp: new Date()
    };

    setCommandHistory(prev => [...prev, newCommand]);
    setHistoryIndex(-1);

    // Show command in terminal
    setTerminalOutput(prev => prev + `\n$ ${command}\n`);

    // Handle different commands
    if (command.startsWith('python ') || command === 'python') {
      setIsExecuting(true);
      try {
        if (onRunCode) {
          const result = await onRunCode('', 'python');
          setTerminalOutput(prev => prev + result);
          newCommand.output = result;
        } else {
          const mockOutput = `Running ${currentFile}...\nPython execution completed successfully!\n\nOutput:\nCode executed without output\n\nExecution time: 0.001s\nMemory usage: 2.5MB`;
          setTerminalOutput(prev => prev + mockOutput);
          newCommand.output = mockOutput;
        }
      } catch (err) {
        const errorMsg = `Error: ${err}`;
        setTerminalOutput(prev => prev + errorMsg);
        newCommand.output = errorMsg;
      } finally {
        setIsExecuting(false);
      }
    } else if (command === 'clear') {
      setTerminalOutput('');
      newCommand.output = 'Terminal cleared';
    } else if (command === 'help') {
      const helpText = `Available commands:
  python [file]  - Run Python code
  clear          - Clear terminal
  help           - Show this help
  ls             - List files (mock)
  pwd            - Show current directory (mock)
  exit           - Exit terminal (mock)`;
      setTerminalOutput(prev => prev + helpText);
      newCommand.output = helpText;
    } else if (command === 'ls') {
      const lsOutput = `Directory listing (mock):
  abc.py
  def.py
  main.py
  requirements.txt`;
      setTerminalOutput(prev => prev + lsOutput);
      newCommand.output = lsOutput;
    } else if (command === 'pwd') {
      const pwdOutput = `/workspace`;
      setTerminalOutput(prev => prev + pwdOutput);
      newCommand.output = pwdOutput;
    } else if (command === 'exit') {
      const exitOutput = `Goodbye!`;
      setTerminalOutput(prev => prev + exitOutput);
      newCommand.output = exitOutput;
    } else {
      const unknownOutput = `Command not found: ${command}. Type 'help' for available commands.`;
      setTerminalOutput(prev => prev + unknownOutput);
      newCommand.output = unknownOutput;
    }

    // Update the command in history
    setCommandHistory(prev => 
      prev.map(cmd => cmd.id === newCommand.id ? newCommand : cmd)
    );
  }, [onRunCode, currentFile]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim()) {
      executeCommand(inputValue.trim());
      setInputValue('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (historyIndex < commandHistory.length - 1) {
        const newIndex = historyIndex + 1;
        setHistoryIndex(newIndex);
        setInputValue(commandHistory[commandHistory.length - 1 - newIndex].command);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (historyIndex > 0) {
        const newIndex = historyIndex - 1;
        setHistoryIndex(newIndex);
        setInputValue(commandHistory[commandHistory.length - 1 - newIndex].command);
      } else if (historyIndex === 0) {
        setHistoryIndex(-1);
        setInputValue('');
      }
    }
  };

  const clearTerminal = () => {
    setTerminalOutput('');
    setCommandHistory([]);
    setHistoryIndex(-1);
  };

  const runPythonFile = async () => {
    await executeCommand(`python ${currentFile}`);
  };

  useEffect(() => {
    // Focus input when terminal is clicked
    const handleClick = () => {
      if (inputRef.current) {
        inputRef.current.focus();
      }
    };

    const terminalElement = outputRef.current?.parentElement;
    if (terminalElement) {
      terminalElement.addEventListener('click', handleClick);
      return () => terminalElement.removeEventListener('click', handleClick);
    }
  }, []);

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
            onClick={runPythonFile}
            disabled={isExecuting || isRunning}
            className="h-6 px-2 text-xs hover:bg-gray-700 text-green-400 hover:text-white"
          >
            <Play className="w-3 h-3 mr-1" />
            Run Python
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={clearTerminal}
            className="h-6 px-2 text-xs hover:bg-gray-700 text-gray-400 hover:text-white"
          >
            <RotateCcw className="w-3 h-3 mr-1" />
            Clear
          </Button>
        </div>
      </div>

      {/* Terminal Output */}
      <div 
        ref={outputRef}
        className="flex-1 overflow-y-auto font-mono text-sm leading-relaxed whitespace-pre-wrap p-4 cursor-text"
        style={{ fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace' }}
      >
        {terminalOutput || 'Welcome to ETHOS Interactive Terminal\nType your commands here...\n\n$ '}
        {(isExecuting || isRunning) && (
          <span className="animate-pulse">█</span>
        )}
      </div>

      {/* Terminal Input */}
      <div className="border-t border-gray-700 p-2 flex-shrink-0">
        <form onSubmit={handleSubmit} className="flex items-center space-x-2">
          <span className="text-green-400 font-mono">$</span>
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 bg-transparent text-green-400 font-mono text-sm outline-none border-none"
            placeholder="Enter command..."
            disabled={isExecuting || isRunning}
          />
          <Button
            type="submit"
            variant="ghost"
            size="sm"
            disabled={!inputValue.trim() || isExecuting || isRunning}
            className="h-6 w-6 p-0 hover:bg-gray-700 text-green-400 hover:text-white"
          >
            <Send className="w-3 h-3" />
          </Button>
        </form>
      </div>
    </div>
  );
};

export default InteractiveTerminal;
