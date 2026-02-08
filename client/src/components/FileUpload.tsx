import React, { useRef, useState } from 'react';
import { Upload, File, Folder, X, Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import FileTree from './FileTree';

interface FileNode {
  id: string;
  name: string;
  type: 'file' | 'folder';
  content?: string;
  path: string;
  children?: FileNode[];
}

interface FileUploadProps {
  onFilesUploaded: (files: FileNode[]) => void;
  uploadedFiles: FileNode[];
  onFileSelect: (file: FileNode) => void;
  onRunFile: (file: FileNode) => void;
  selectedFile?: FileNode;
}

const FileUpload: React.FC<FileUploadProps> = ({
  onFilesUploaded,
  uploadedFiles,
  onFileSelect,
  onRunFile,
  selectedFile
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isUploading, setIsUploading] = useState(false);

  const handleFileRead = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve(e.target?.result as string);
      reader.onerror = reject;
      reader.readAsText(file);
    });
  };

  // File filtering logic to match backend
  const shouldIncludeFile = (filename: string): boolean => {
    const excludedDirs = ['node_modules', '.git', '__pycache__', '.pytest_cache', '.coverage', 'venv', '.venv', 'env', '.env'];
    const allowedExtensions = ['.py', '.txt', '.json', '.yml', '.yaml', '.ini'];
    
    // Check if it's in an excluded directory
    for (const excludedDir of excludedDirs) {
      if (filename.includes(excludedDir)) {
        return false;
      }
    }
    
    // Special case for requirements.txt
    if (filename.toLowerCase() === 'requirements.txt') {
      return true;
    }
    
    // Check file extension
    const ext = filename.toLowerCase().substring(filename.lastIndexOf('.'));
    return allowedExtensions.includes(ext);
  };

  const processFiles = async (files: FileList): Promise<{ fileNodes: FileNode[], filteredCount: number, totalCount: number }> => {
    const fileMap = new Map<string, FileNode>();
    const MAX_FILES_LIMIT = 1000;
    let filteredCount = 0;
    let totalCount = files.length;
    
    // First pass: filter files and count valid ones
    const validFiles: File[] = [];
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (shouldIncludeFile(file.webkitRelativePath || file.name)) {
        validFiles.push(file);
      }
    }
    
    // Check file count limit
    if (validFiles.length > MAX_FILES_LIMIT) {
      throw new Error(`Too many files. Maximum number of files is ${MAX_FILES_LIMIT}. Found ${validFiles.length} valid files. Please either upload fewer files or split your upload into chunks of ≤${MAX_FILES_LIMIT} files.`);
    }
    
    // Second pass: process valid files
    for (const file of validFiles) {
      try {
        const content = await handleFileRead(file);
        const pathParts = file.webkitRelativePath ? file.webkitRelativePath.split('/') : [file.name];
        
        // Create file node
        const fileNode: FileNode = {
          id: Math.random().toString(36).substr(2, 9),
          name: pathParts[pathParts.length - 1],
          content,
          type: 'file',
          path: file.webkitRelativePath || file.name
        };
        
        // Build folder structure
        let currentPath = '';
        let currentParent: FileNode | undefined;
        
        for (let j = 0; j < pathParts.length - 1; j++) {
          currentPath = currentPath ? `${currentPath}/${pathParts[j]}` : pathParts[j];
          
          if (!fileMap.has(currentPath)) {
            const folderNode: FileNode = {
              id: Math.random().toString(36).substr(2, 9),
              name: pathParts[j],
              type: 'folder',
              path: currentPath,
              children: []
            };
            fileMap.set(currentPath, folderNode);
            
            if (currentParent) {
              currentParent.children!.push(folderNode);
            }
          }
          
          currentParent = fileMap.get(currentPath);
        }
        
        // Add file to its parent folder
        if (currentParent) {
          currentParent.children!.push(fileNode);
        } else {
          fileMap.set(fileNode.path, fileNode);
        }
        
      } catch (error) {
        console.error('Error reading file:', error);
      }
    }
    
    // Return root level files and folders
    const fileNodes = Array.from(fileMap.values()).filter(node => !node.path.includes('/'));
    return { fileNodes, filteredCount: validFiles.length, totalCount };
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      setIsUploading(true);
      try {
        const result = await processFiles(files);
        onFilesUploaded([...uploadedFiles, ...result.fileNodes]);
        
        // Show user feedback about filtering
        if (result.filteredCount < result.totalCount) {
          console.log(`📁 Filtered ${result.totalCount - result.filteredCount} files (excluded junk/system files)`);
        }
        console.log(`✅ Processing ${result.filteredCount} valid files out of ${result.totalCount} total files`);
      } catch (error) {
        console.error('❌ Upload failed:', error);
        alert(error instanceof Error ? error.message : 'Upload failed');
      } finally {
        setIsUploading(false);
      }
    }
  };

  const handleFolderUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files) {
      setIsUploading(true);
      try {
        const result = await processFiles(files);
        onFilesUploaded([...uploadedFiles, ...result.fileNodes]);
        
        // Show user feedback about filtering
        if (result.filteredCount < result.totalCount) {
          console.log(`📁 Filtered ${result.totalCount - result.filteredCount} files (excluded junk/system files)`);
        }
        console.log(`✅ Processing ${result.filteredCount} valid files out of ${result.totalCount} total files`);
      } catch (error) {
        console.error('❌ Upload failed:', error);
        alert(error instanceof Error ? error.message : 'Upload failed');
      } finally {
        setIsUploading(false);
      }
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    
    const files = e.dataTransfer.files;
    if (files) {
      setIsUploading(true);
      try {
        const result = await processFiles(files);
        onFilesUploaded([...uploadedFiles, ...result.fileNodes]);
        
        // Show user feedback about filtering
        if (result.filteredCount < result.totalCount) {
          console.log(`📁 Filtered ${result.totalCount - result.filteredCount} files (excluded junk/system files)`);
        }
        console.log(`✅ Processing ${result.filteredCount} valid files out of ${result.totalCount} total files`);
      } catch (error) {
        console.error('❌ Upload failed:', error);
        alert(error instanceof Error ? error.message : 'Upload failed');
      } finally {
        setIsUploading(false);
      }
    }
  };

  const removeFile = (fileId: string) => {
    const removeFileFromTree = (nodes: FileNode[]): FileNode[] => {
      return nodes.filter(node => {
        if (node.id === fileId) return false;
        if (node.children) {
          node.children = removeFileFromTree(node.children);
        }
        return true;
      });
    };
    
    const updatedFiles = removeFileFromTree(uploadedFiles);
    onFilesUploaded(updatedFiles);
  };

  const downloadFile = (file: FileNode) => {
    const content = file.content || '';
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = file.name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      {/* Upload Area */}
      <div
        className={`relative border-2 border-dashed rounded-xl p-6 text-center transition-all duration-500 ${
          isDragOver
            ? 'border-blue-400 bg-blue-900/20 scale-105 shadow-2xl shadow-blue-500/30'
            : 'border-gray-700 hover:border-gray-600 hover:bg-gray-800/30'
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* Animated background effect */}
        <div className={`absolute inset-0 rounded-xl transition-all duration-500 ${
          isDragOver ? 'bg-gradient-to-br from-blue-500/15 via-purple-500/10 to-pink-500/15 opacity-100' : 'opacity-0'
        }`} />
        
        {/* Animated border glow */}
        <div className={`absolute inset-0 rounded-xl transition-all duration-500 ${
          isDragOver ? 'opacity-100' : 'opacity-0'
        }`}>
          <div className="absolute inset-0 rounded-xl bg-gradient-to-r from-blue-500/30 via-purple-500/20 to-pink-500/30 blur-md animate-pulse" />
        </div>
        
        {/* Floating particles effect */}
        <div className={`absolute inset-0 overflow-hidden rounded-xl transition-opacity duration-500 ${
          isDragOver ? 'opacity-100' : 'opacity-0'
        }`}>
          <div className="absolute top-2 left-4 w-1 h-1 bg-blue-400 rounded-full animate-bounce delay-100" />
          <div className="absolute top-6 right-6 w-1 h-1 bg-purple-400 rounded-full animate-bounce delay-300" />
          <div className="absolute bottom-4 left-8 w-1 h-1 bg-pink-400 rounded-full animate-bounce delay-500" />
          <div className="absolute bottom-2 right-4 w-1 h-1 bg-blue-400 rounded-full animate-bounce delay-700" />
        </div>
        
        <div className="relative z-10">
          {/* Main upload icon with enhanced animation */}
          <div className={`transition-all duration-500 ${isDragOver ? 'scale-125 rotate-12' : 'scale-100 rotate-0'}`}>
            <Upload className={`w-16 h-16 mx-auto mb-4 transition-all duration-500 ${
              isDragOver ? 'text-blue-400 drop-shadow-lg' : 'text-gray-500'
            }`} />
          </div>
          
          {/* Compact text */}
          <p className={`text-xs font-medium mb-4 transition-colors duration-300 ${
            isDragOver ? 'text-blue-300' : 'text-gray-400'
          }`}>
            {isDragOver ? 'Release to upload' : 'Drag & drop or click'}
          </p>
          
          {/* Icon-only buttons */}
          <div className="flex justify-center space-x-4">
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              className={`group relative p-3 rounded-lg transition-all duration-300 ${
                isUploading 
                  ? 'bg-gray-700 cursor-not-allowed' 
                  : 'bg-gray-800 hover:bg-blue-600 hover:scale-110 active:scale-95'
              }`}
              title="Upload Files"
            >
              <File className={`w-5 h-5 transition-colors duration-300 ${
                isUploading ? 'text-gray-500' : 'text-gray-400 group-hover:text-white'
              }`} />
              {isUploading && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                </div>
              )}
            </button>
            
            <button
              onClick={() => folderInputRef.current?.click()}
              disabled={isUploading}
              className={`group relative p-3 rounded-lg transition-all duration-300 ${
                isUploading 
                  ? 'bg-gray-700 cursor-not-allowed' 
                  : 'bg-gray-800 hover:bg-purple-600 hover:scale-110 active:scale-95'
              }`}
              title="Upload Folder"
            >
              <Folder className={`w-5 h-5 transition-colors duration-300 ${
                isUploading ? 'text-gray-500' : 'text-gray-400 group-hover:text-white'
              }`} />
              {isUploading && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-3 h-3 border-2 border-purple-400 border-t-transparent rounded-full animate-spin" />
                </div>
              )}
            </button>
          </div>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".py,.js,.ts,.html,.css,.json,.txt"
          onChange={handleFileUpload}
          className="hidden"
        />
        <input
          ref={folderInputRef}
          type="file"
          multiple
          {...({ webkitdirectory: '' } as any)}
          onChange={handleFolderUpload}
          className="hidden"
        />
      </div>

      {/* File Tree */}
      {uploadedFiles.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold text-gray-300 uppercase tracking-wider">
              Project Files
            </h3>
            <div className="flex items-center space-x-1">
              <div className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
              <span className="text-xs text-gray-500">{uploadedFiles.length}</span>
            </div>
          </div>
          <div className="max-h-96 overflow-y-auto border border-gray-700 rounded-lg bg-gray-900/50 backdrop-blur-sm">
            <div className="p-2">
              <FileTree
                files={uploadedFiles}
                selectedFile={selectedFile}
                onFileSelect={onFileSelect}
                onRunFile={onRunFile}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FileUpload;
