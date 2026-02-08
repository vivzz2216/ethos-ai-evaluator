import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Terminal as TerminalIcon, Play, Square, RotateCcw, Send, Globe, Server } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface WebFrameworkTerminalProps {
  onRunCode?: (code: string, language: string) => Promise<string>;
  isRunning?: boolean;
  output?: string;
  error?: string;
  currentFile?: string;
  sessionId?: string;
  framework?: string;
  serverPort?: number;
  isServerRunning?: boolean;
}

interface Command {
  id: string;
  command: string;
  output: string;
  timestamp: Date;
}

const WebFrameworkTerminal: React.FC<WebFrameworkTerminalProps> = ({
  onRunCode,
  isRunning = false,
  output = '',
  error = '',
  currentFile = 'main.py',
  sessionId,
  framework,
  serverPort = 5000,
  isServerRunning = false
}) => {
  const [terminalOutput, setTerminalOutput] = useState('');
  const [isExecuting, setIsExecuting] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const [commandHistory, setCommandHistory] = useState<Command[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [isInstalling, setIsInstalling] = useState(false);
  const [venvActivated, setVenvActivated] = useState(false);
  const [realTerminalMode, setRealTerminalMode] = useState(false);
  const [terminalStarted, setTerminalStarted] = useState(false);
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

  // Check virtual environment status
  useEffect(() => {
    const checkVenvStatus = async () => {
      if (sessionId) {
        console.log('Terminal: Session ID received:', sessionId);
        try {
          const response = await fetch(`http://localhost:8000/api/session/${sessionId}/status`);
          if (response.ok) {
            const result = await response.json();
            setVenvActivated(result.venv_activated || false);
            console.log('Terminal: Session status checked successfully');
          }
        } catch (error) {
          console.error('Failed to check venv status:', error);
        }
      } else {
        console.log('Terminal: No session ID available');
      }
    };
    
    checkVenvStatus();
  }, [sessionId]);

  const executeCommand = useCallback(async (command: string) => {
    if (!command.trim()) return;

    const newCommand: Command = {
      id: Date.now().toString(),
      command,
      output: '',
      timestamp: new Date()
    };

    setCommandHistory(prev => [...prev, newCommand]);
    setHistoryIndex(-1);

    setTerminalOutput(prev => prev + `\n$ ${command}\n`);

    try {
      // Special terminal commands
      if (command === 'clear') {
        setTerminalOutput('');
        newCommand.output = 'Terminal cleared';
      } else if (command === 'help') {
        handleHelp();
      } else if (command === 'exit') {
        handleExit();
      } else if (command === 'list-files') {
        await handleListFiles();
      } else if (command === 'transfer-files') {
        await handleTransferFiles();
      } else if (command === 'create-flask-app') {
        await handleCreateFlaskApp();
      } else if (command === 'upload-files') {
        await handleUploadFiles();
      } else {
        // Execute real commands through backend
        await executeRealCommand(command);
      }
    } catch (err) {
      const errorMsg = `Error executing command: ${err}`;
      setTerminalOutput(prev => prev + errorMsg);
      newCommand.output = errorMsg;
    }

    setCommandHistory(prev => 
      prev.map(cmd => cmd.id === newCommand.id ? newCommand : cmd)
    );
  }, [sessionId]);


  const transferFilesToSession = async (targetSessionId: string) => {
    if (!sessionId) {
      setTerminalOutput(prev => prev + '❌ Error: No source session to transfer from.\n');
      return;
    }

    try {
      setTerminalOutput(prev => prev + `🔄 Transferring files to session ${targetSessionId}...\n`);
      
      // Get files from current session
      const sourceResponse = await fetch(`http://localhost:8000/api/session/${sessionId}/debug/files`);
      if (!sourceResponse.ok) {
        throw new Error('Failed to get source files');
      }
      
      const sourceData = await sourceResponse.json();
      
      // Transfer each file to the target session
      for (const file of sourceData.files) {
        if (file.name.endsWith('.py') || file.name === 'requirements.txt' || file.name.endsWith('.txt')) {
          try {
            // Read file content
            const fileResponse = await fetch(`http://localhost:8000/api/session/${sessionId}/file/${file.name}`);
            if (fileResponse.ok) {
              const content = await fileResponse.text();
              
              // Create file in target session
              const formData = new FormData();
              const blob = new Blob([content], { type: 'text/plain' });
              formData.append('files', blob, file.name);
              
              const uploadResponse = await fetch(`http://localhost:8000/api/session/${targetSessionId}/upload`, {
                method: 'POST',
                body: formData
              });
              
              if (uploadResponse.ok) {
                setTerminalOutput(prev => prev + `✅ Transferred: ${file.name}\n`);
              }
            }
          } catch (error) {
            setTerminalOutput(prev => prev + `⚠️  Could not transfer: ${file.name}\n`);
          }
        }
      }
      
      setTerminalOutput(prev => prev + '✅ File transfer completed!\n');
    } catch (error) {
      setTerminalOutput(prev => prev + `❌ Failed to transfer files: ${error}\n`);
    }
  };

  const startRealTerminal = async () => {
    if (!sessionId) {
      setTerminalOutput(prev => prev + '❌ Error: No active session.\n');
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/api/session/${sessionId}/terminal/start`, {
        method: 'POST'
      });

      if (response.ok) {
        setTerminalStarted(true);
        setRealTerminalMode(true);
        setTerminalOutput(prev => prev + '🚀 Real terminal started! You can now use actual shell commands.\n');
      } else {
        const result = await response.json();
        setTerminalOutput(prev => prev + `❌ Error starting terminal: ${result.detail}\n`);
      }
    } catch (error) {
      setTerminalOutput(prev => prev + `❌ Error: Failed to start terminal - ${error}\n`);
    }
  };

  const executeRealCommand = async (command: string) => {
    console.log('executeRealCommand called with sessionId:', sessionId);
    if (!sessionId) {
      setTerminalOutput(prev => prev + '❌ Error: No active session.\n🔄 Please wait for session to be created or check if backend is running.\n📡 Backend should be running at: http://localhost:8000\n');
      return;
    }

    setIsExecuting(true);
    try {
      setTerminalOutput(prev => prev + `🔄 Executing: ${command}\n`);
      
      let response;
      if (realTerminalMode && terminalStarted) {
        // Use real terminal API
        response = await fetch(`http://localhost:8000/api/session/${sessionId}/terminal/execute`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
          },
          body: `command=${encodeURIComponent(command)}`
        });
      } else {
        // Use regular command API
        response = await fetch(`http://localhost:8000/api/session/${sessionId}/execute-command`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `command=${encodeURIComponent(command)}`
      });
      }

      const result = await response.json();
      
      if (response.ok) {
        // Display command output
        if (result.stdout) {
          setTerminalOutput(prev => prev + result.stdout);
        }
        if (result.stderr) {
          setTerminalOutput(prev => prev + result.stderr);
        }
        if (!result.success && !result.stdout && !result.stderr) {
          setTerminalOutput(prev => prev + `❌ Command failed with exit code ${result.returncode}\n`);
        }
        if (result.success && !result.stdout && !result.stderr) {
          setTerminalOutput(prev => prev + `✅ Command executed successfully\n`);
        }
        
        // Update virtual environment status if activation command was successful
        if (command.includes('activate') && result.success) {
          setVenvActivated(true);
        }
      } else {
        setTerminalOutput(prev => prev + `❌ Error: ${result.detail}\n`);
      }
    } catch (error) {
      setTerminalOutput(prev => prev + `❌ Error: Failed to execute command - ${error}\n🔍 Check if backend is running at http://localhost:8000\n`);
    } finally {
      setIsExecuting(false);
    }
  };

  const handleStartServer = async () => {
    if (!sessionId) {
      setTerminalOutput(prev => prev + 'Error: No active session. Please upload files first.\n');
      return;
    }

    setIsExecuting(true);
    try {
      const response = await fetch(`http://localhost:8000/api/session/${sessionId}/run-server`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `port=${serverPort}`
      });

      const result = await response.json();
      
      if (response.ok) {
        const successMsg = `${result.message}\nServer running at: ${result.url}\nFramework: ${result.framework}\nPort: ${result.port}\n`;
        setTerminalOutput(prev => prev + successMsg);
      } else {
        setTerminalOutput(prev => prev + `Error: ${result.detail}\n`);
      }
    } catch (error) {
      setTerminalOutput(prev => prev + `Error: Failed to start server - ${error}\n`);
    } finally {
      setIsExecuting(false);
    }
  };

  const handleStopServer = async () => {
    if (!sessionId) {
      setTerminalOutput(prev => prev + 'Error: No active session.\n');
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/api/session/${sessionId}/stop-server`, {
        method: 'POST'
      });

      const result = await response.json();
      setTerminalOutput(prev => prev + `${result.message}\n`);
    } catch (error) {
      setTerminalOutput(prev => prev + `Error: Failed to stop server - ${error}\n`);
    }
  };

  const handleInstallDependencies = async () => {
    if (!sessionId) {
      setTerminalOutput(prev => prev + 'Error: No active session.\n');
      return;
    }

    setIsInstalling(true);
    try {
      setTerminalOutput(prev => prev + 'Installing dependencies from requirements.txt...\n');
      
      // Simulate installation process
      const installMsg = 'Installing packages...\n';
      setTerminalOutput(prev => prev + installMsg);
      
      // In a real implementation, this would call the backend
      setTimeout(() => {
        const successMsg = 'Dependencies installed successfully!\n';
        setTerminalOutput(prev => prev + successMsg);
        setIsInstalling(false);
      }, 2000);
    } catch (error) {
      setTerminalOutput(prev => prev + `Error: Failed to install dependencies - ${error}\n`);
      setIsInstalling(false);
    }
  };

  const handleInstallPackage = async (packageName: string) => {
    if (!sessionId) {
      setTerminalOutput(prev => prev + 'Error: No active session.\n');
      return;
    }

    setIsInstalling(true);
    try {
      const response = await fetch(`http://localhost:8000/api/session/${sessionId}/install`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `package=${packageName}`
      });

      const result = await response.json();
      
      if (response.ok && result.success) {
        setTerminalOutput(prev => prev + `Package ${packageName} installed successfully!\n`);
      } else {
        setTerminalOutput(prev => prev + `Error installing ${packageName}: ${result.stderr}\n`);
      }
    } catch (error) {
      setTerminalOutput(prev => prev + `Error: Failed to install package - ${error}\n`);
    } finally {
      setIsInstalling(false);
    }
  };

  const handleServerStatus = async () => {
    if (!sessionId) {
      setTerminalOutput(prev => prev + 'Error: No active session.\n');
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/api/session/${sessionId}/status`);
      const result = await response.json();
      
      if (response.ok) {
        const statusMsg = `Session Status:
Framework: ${result.framework || 'None detected'}
Main File: ${result.main_file || 'None'}
Server Running: ${result.is_running ? 'Yes' : 'No'}
Port: ${result.port || 'N/A'}
URL: ${result.url || 'N/A'}
Installed Packages: ${result.installed_packages?.length || 0}
Files: ${result.files?.length || 0}\n`;
        setTerminalOutput(prev => prev + statusMsg);
      }
    } catch (error) {
      setTerminalOutput(prev => prev + `Error: Failed to get status - ${error}\n`);
    }
  };

  const handleFrameworkInfo = () => {
    const info = `Web Framework Support:
- Flask: Run with 'run-server' or 'start-server'
- FastAPI: Run with 'run-server' or 'start-server'  
- Django: Run with 'run-server' or 'start-server'

Commands:
- run-server: Start the web server
- stop-server: Stop the web server
- install-deps: Install requirements.txt
- server-status: Check server status
- framework-info: Show this info\n`;
    
    setTerminalOutput(prev => prev + info);
  };

  const handlePythonExecution = async (command: string) => {
    setIsExecuting(true);
    try {
      if (onRunCode) {
        const result = await onRunCode('', 'python');
        setTerminalOutput(prev => prev + result);
      } else {
        const mockOutput = `Running ${currentFile}...\nPython execution completed successfully!\n\nOutput:\nCode executed without output\n\nExecution time: 0.001s\nMemory usage: 2.5MB`;
        setTerminalOutput(prev => prev + mockOutput);
      }
    } catch (err) {
      const errorMsg = `Error: ${err}`;
      setTerminalOutput(prev => prev + errorMsg);
    } finally {
      setIsExecuting(false);
    }
  };

  const handleHelp = () => {
    const helpText = `ETHOS Terminal - Real Command Execution
===========================================

Basic Commands:
  ls, dir          - List directory contents
  pwd              - Show current directory
  cd [path]        - Change directory
  mkdir [name]     - Create directory
  cat [file]       - Display file contents

Python Environment:
  python -m venv venv     - Create virtual environment
  venv\\Scripts\\activate - Activate virtual environment (Windows)
  .venv\\Scripts\\activate - Activate virtual environment (Windows alternative)
  source venv/bin/activate - Activate virtual environment (Linux/Mac)
  pip install [package]  - Install Python package
  pip install -r requirements.txt - Install from requirements file
  python [script.py]     - Run Python script

Web Frameworks:
  python -m flask run    - Run Flask app
  uvicorn main:app --reload - Run FastAPI app
  python manage.py runserver - Run Django app

System Commands:
  clear             - Clear terminal
  help              - Show this help
  exit              - Exit terminal

Debug Commands:
  list-files        - List all files in session directory
  session-info      - Show session information
  transfer-files    - Transfer files to current session
  create-flask-app  - Create a basic Flask app.py file
  upload-files      - Upload your project files to current session

Note: All commands execute in real-time on the backend server!
`;
    
    setTerminalOutput(prev => prev + helpText);
  };

  const handleListFiles = async () => {
    if (!sessionId) {
      setTerminalOutput(prev => prev + '❌ Error: No active session.\n');
      return;
    }

    try {
      const response = await fetch(`http://localhost:8000/api/session/${sessionId}/debug/files`);
      if (response.ok) {
        const result = await response.json();
        let output = `📁 Files in session directory (${result.temp_dir}):\n\n`;
        
        if (result.files.length === 0) {
          output += 'No files found.\n';
        } else {
          result.files.forEach((file: any) => {
            output += `  ${file.name} (${file.size} bytes) - ${file.path}\n`;
          });
        }
        
        setTerminalOutput(prev => prev + output);
      } else {
        const error = await response.json();
        setTerminalOutput(prev => prev + `❌ Error: ${error.detail}\n`);
      }
    } catch (error) {
      setTerminalOutput(prev => prev + `❌ Error: Failed to list files - ${error}\n`);
    }
  };

  const handleTransferFiles = async () => {
    if (!sessionId) {
      setTerminalOutput(prev => prev + '❌ Error: No active session.\n');
      return;
    }

    try {
      setTerminalOutput(prev => prev + '🔄 Looking for files to transfer...\n');
      
      // Get all active sessions
      const sessionsResponse = await fetch('http://localhost:8000/api/debug/sessions');
      if (!sessionsResponse.ok) {
        throw new Error('Failed to get session list');
      }
      
      const sessionsData = await sessionsResponse.json();
      const otherSessions = sessionsData.active_sessions.filter((id: string) => id !== sessionId);
      
      if (otherSessions.length === 0) {
        setTerminalOutput(prev => prev + 'ℹ️  No other sessions found to transfer from.\n');
        return;
      }
      
      // Find a session with files
      let sourceSessionId = null;
      for (const otherSessionId of otherSessions) {
        const filesResponse = await fetch(`http://localhost:8000/api/session/${otherSessionId}/debug/files`);
        if (filesResponse.ok) {
          const filesData = await filesResponse.json();
          if (filesData.files.length > 0) {
            sourceSessionId = otherSessionId;
            break;
          }
        }
      }
      
      if (!sourceSessionId) {
        setTerminalOutput(prev => prev + 'ℹ️  No other sessions with files found.\n');
        return;
      }
      
      setTerminalOutput(prev => prev + `📦 Found files in session ${sourceSessionId}\n`);
      await transferFilesToSession(sourceSessionId);
      
    } catch (error) {
      setTerminalOutput(prev => prev + `❌ Error: Failed to transfer files - ${error}\n`);
    }
  };

  const handleCreateFlaskApp = async () => {
    if (!sessionId) {
      setTerminalOutput(prev => prev + '❌ Error: No active session.\n');
      return;
    }

    try {
      setTerminalOutput(prev => prev + '🔄 Creating Flask app.py...\n');
      
      const flaskAppContent = `from flask import Flask, render_template, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return '''
    <h1>Welcome to ETHOS Flask App!</h1>
    <p>Your Flask application is running successfully.</p>
    <p>Try these endpoints:</p>
    <ul>
        <li><a href="/api/hello">/api/hello</a> - JSON API</li>
        <li><a href="/api/status">/api/status</a> - Status check</li>
    </ul>
    '''

@app.route('/api/hello')
def api_hello():
    return jsonify({
        'message': 'Hello from ETHOS Flask!',
        'status': 'success',
        'framework': 'Flask'
    })

@app.route('/api/status')
def api_status():
    return jsonify({
        'status': 'running',
        'framework': 'Flask',
        'version': '1.0.0'
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
`;

      // Create the file using the backend
      const formData = new FormData();
      const blob = new Blob([flaskAppContent], { type: 'text/plain' });
      formData.append('files', blob, 'app.py');
      
      const response = await fetch(`http://localhost:8000/api/session/${sessionId}/upload`, {
        method: 'POST',
        body: formData
      });
      
      if (response.ok) {
        setTerminalOutput(prev => prev + '✅ Flask app.py created successfully!\n');
        setTerminalOutput(prev => prev + '🚀 You can now run: flask run --host=0.0.0.0 --port=5000\n');
      } else {
        const error = await response.json();
        setTerminalOutput(prev => prev + `❌ Error creating app.py: ${error.detail}\n`);
      }
    } catch (error) {
      setTerminalOutput(prev => prev + `❌ Error: Failed to create Flask app - ${error}\n`);
    }
  };

  const handleUploadFiles = async () => {
    try {
      setTerminalOutput(prev => prev + '📁 Please upload your project files using the file upload area above.\n');
      setTerminalOutput(prev => prev + '💡 Session will be created automatically when files are uploaded.\n');
      setTerminalOutput(prev => prev + '🚀 Then simply run: flask run\n');
      setTerminalOutput(prev => prev + '✨ Flask will auto-detect your app.py file!\n');
    } catch (error) {
      setTerminalOutput(prev => prev + `❌ Error: ${error}\n`);
    }
  };


  const handlePwd = () => {
    setTerminalOutput(prev => prev + '/workspace');
  };

  const handleExit = () => {
    setTerminalOutput(prev => prev + 'Goodbye!');
  };

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

  const startServer = async () => {
    await executeCommand('run-server');
  };

  return (
    <div className="bg-gray-900 text-green-400 overflow-hidden border-t border-gray-700 h-full flex flex-col">
      {/* Terminal Header */}
      <div className="bg-gray-800 px-4 py-2 flex items-center justify-between border-b border-gray-700 flex-shrink-0">
        <div className="flex items-center space-x-2">
          <TerminalIcon className="w-4 h-4 text-green-400" />
          <span className="text-sm font-medium">Terminal</span>
          {framework && (
            <span className="text-xs px-2 py-1 bg-blue-600 rounded text-white">
              {framework.toUpperCase()}
            </span>
          )}
          {isServerRunning && (
            <span className="text-xs px-2 py-1 bg-green-600 rounded text-white flex items-center">
              <Server className="w-3 h-3 mr-1" />
              RUNNING
            </span>
          )}
        </div>
        <div className="flex items-center space-x-2">
          {!realTerminalMode && sessionId && (
            <Button
              variant="ghost"
              size="sm"
              onClick={startRealTerminal}
              disabled={isExecuting}
              className="h-6 px-2 text-xs hover:bg-gray-700 text-purple-400 hover:text-white"
              title="Start Real Terminal"
            >
              <TerminalIcon className="w-3 h-3 mr-1" />
              Real Terminal
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={runPythonFile}
            disabled={isExecuting || isRunning}
            className="h-6 px-2 text-xs hover:bg-gray-700 text-green-400 hover:text-white"
            title="Run Python File"
          >
            <Play className="w-3 h-3 mr-1" />
            Run
          </Button>
          {framework && (
            <Button
              variant="ghost"
              size="sm"
              onClick={startServer}
              disabled={isExecuting || isServerRunning}
              className="h-6 px-2 text-xs hover:bg-gray-700 text-blue-400 hover:text-white"
              title="Start Server"
            >
              <Globe className="w-3 h-3 mr-1" />
              {isServerRunning ? 'Stop' : 'Start'}
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={clearTerminal}
            className="h-6 px-2 text-xs hover:bg-gray-700 text-gray-400 hover:text-white"
          >
            <RotateCcw className="w-3 h-3" />
          </Button>
        </div>
      </div>

      {/* Terminal Output */}
      <div 
        ref={outputRef}
        className="p-4 flex-1 overflow-y-auto font-mono text-sm leading-relaxed whitespace-pre-wrap cursor-text"
        style={{ fontFamily: 'Monaco, Menlo, "Ubuntu Mono", monospace' }}
        onClick={() => inputRef.current?.focus()}
      >
        {terminalOutput || `Welcome to ETHOS Terminal - Real Command Execution
================================================

${sessionId ? `✅ Session Active: ${sessionId}` : '📁 Upload files to create a session'}

This is a REAL terminal that executes commands on the backend server.

Quick Start:
1. Upload your project files using the file upload area above
2. Session will be created automatically when files are uploaded
3. Create virtual environment: python -m venv venv
4. Activate it: venv\\Scripts\\activate (Windows) or source venv/bin/activate (Linux/Mac)
5. Install dependencies: pip install -r requirements.txt
6. Run your Flask app: flask run (auto-detects app.py!)

✨ Flask Auto-Detection: Just run 'flask run' and it will find your app.py!

Type "help" for all available commands.

${!sessionId ? '📁 Upload files above to get started!' : ''}
`}
        {(isExecuting || isRunning || isInstalling) && (
          <span className="animate-pulse">█</span>
        )}
      </div>

      {/* Terminal Input */}
      <div className="flex items-center bg-gray-800 border-t border-gray-700 px-4 py-2 flex-shrink-0">
        <span className="text-green-400 mr-2">
          {venvActivated ? '(venv) $' : '$'}
        </span>
        <input
          ref={inputRef}
          type="text"
          className="flex-1 bg-transparent outline-none text-white font-mono text-sm"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isExecuting || isInstalling || !sessionId}
          placeholder={!sessionId ? "Waiting for session..." : "Enter command..."}
          autoFocus
        />
        <Button
          variant="ghost"
          size="sm"
          onClick={() => executeCommand(inputValue)}
          disabled={isExecuting || isInstalling || !inputValue.trim() || !sessionId}
          className="text-gray-300 hover:text-white hover:bg-gray-700 ml-2"
        >
          <Send className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
};

export default WebFrameworkTerminal;
