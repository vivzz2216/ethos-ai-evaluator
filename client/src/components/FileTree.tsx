import React, { useState } from 'react';
import { ChevronRight, ChevronDown, File, Folder, FolderOpen, Play, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface FileNode {
  id: string;
  name: string;
  type: 'file' | 'folder';
  content?: string;
  path: string;
  children?: FileNode[];
}

interface FileTreeProps {
  files: FileNode[];
  selectedFile?: FileNode;
  onFileSelect: (file: FileNode) => void;
  onRunFile: (file: FileNode) => void;
}

const FileTreeNode: React.FC<{
  node: FileNode;
  level: number;
  selectedFile?: FileNode;
  onFileSelect: (file: FileNode) => void;
  onRunFile: (file: FileNode) => void;
}> = ({ node, level, selectedFile, onFileSelect, onRunFile }) => {
  const [isExpanded, setIsExpanded] = useState(true);
  const isSelected = selectedFile?.id === node.id;
  const isFolder = node.type === 'folder';

  const handleClick = () => {
    if (isFolder) {
      setIsExpanded(!isExpanded);
    } else {
      onFileSelect(node);
    }
  };

  const handleRunClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    onRunFile(node);
  };

  const getIcon = () => {
    if (isFolder) {
      return isExpanded ? <FolderOpen className="w-4 h-4 text-blue-500" /> : <Folder className="w-4 h-4 text-blue-500" />;
    } else {
      // Different icons for different file types with enhanced colors
      if (node.name.endsWith('.py')) {
        return <FileText className="w-4 h-4 text-green-400 drop-shadow-sm" />;
      } else if (node.name.endsWith('.js') || node.name.endsWith('.ts')) {
        return <FileText className="w-4 h-4 text-yellow-400 drop-shadow-sm" />;
      } else if (node.name.endsWith('.html')) {
        return <FileText className="w-4 h-4 text-orange-400 drop-shadow-sm" />;
      } else if (node.name.endsWith('.css')) {
        return <FileText className="w-4 h-4 text-blue-400 drop-shadow-sm" />;
      } else if (node.name.endsWith('.json')) {
        return <FileText className="w-4 h-4 text-purple-400 drop-shadow-sm" />;
      } else if (node.name.endsWith('.txt') || node.name.endsWith('.md')) {
        return <FileText className="w-4 h-4 text-gray-400 drop-shadow-sm" />;
      } else {
        return <File className="w-4 h-4 text-gray-500 drop-shadow-sm" />;
      }
    }
  };

  return (
    <div>
      <div
        className={`flex items-center space-x-1 py-1.5 px-2 cursor-pointer hover:bg-gray-700/50 rounded transition-all duration-200 group ${
          isSelected ? 'bg-blue-600/20 border-r-2 border-blue-400 shadow-sm' : ''
        }`}
        style={{ paddingLeft: `${level * 16 + 8}px` }}
        onClick={handleClick}
      >
        {isFolder && (
          <div className="w-4 h-4 flex items-center justify-center">
            {isExpanded ? (
              <ChevronDown className="w-3 h-3 text-gray-500" />
            ) : (
              <ChevronRight className="w-3 h-3 text-gray-500" />
            )}
          </div>
        )}
        {!isFolder && <div className="w-4 h-4" />}
        
        <div className="flex items-center space-x-1 flex-1 min-w-0">
          {getIcon()}
            <span className={`text-sm truncate transition-all duration-200 ${
              isSelected ? 'font-medium text-white' : 'text-gray-300 group-hover:text-white'
            }`}>
              {node.name}
            </span>
        </div>

        {!isFolder && node.name.endsWith('.py') && (
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRunClick}
            className="h-6 w-6 p-0 opacity-0 group-hover:opacity-100 hover:bg-green-600 text-green-400 hover:text-white transition-all duration-200 hover:scale-110"
          >
            <Play className="w-3 h-3" />
          </Button>
        )}
      </div>

      {isFolder && isExpanded && node.children && (
        <div>
          {node.children.map((child) => (
            <FileTreeNode
              key={child.id}
              node={child}
              level={level + 1}
              selectedFile={selectedFile}
              onFileSelect={onFileSelect}
              onRunFile={onRunFile}
            />
          ))}
        </div>
      )}
    </div>
  );
};

const FileTree: React.FC<FileTreeProps> = ({ files, selectedFile, onFileSelect, onRunFile }) => {
  return (
    <div className="space-y-1">
      {files.map((file) => (
        <FileTreeNode
          key={file.id}
          node={file}
          level={0}
          selectedFile={selectedFile}
          onFileSelect={onFileSelect}
          onRunFile={onRunFile}
        />
      ))}
    </div>
  );
};

export default FileTree;
