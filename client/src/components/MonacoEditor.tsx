import React, { useRef, useEffect, useState } from 'react';
import * as monaco from 'monaco-editor';

interface MonacoEditorProps {
  value: string;
  onChange: (value: string) => void;
  language?: string;
  theme?: string;
  readOnly?: boolean;
  height?: string;
}

const MonacoEditor: React.FC<MonacoEditorProps> = ({
  value,
  onChange,
  language = 'python',
  theme = 'vs-dark',
  readOnly = false,
  height = '400px'
}) => {
  const editorRef = useRef<HTMLDivElement>(null);
  const monacoEditorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);

  useEffect(() => {
    if (editorRef.current && !monacoEditorRef.current) {
      monacoEditorRef.current = monaco.editor.create(editorRef.current, {
        value,
        language,
        theme,
        readOnly,
        automaticLayout: true,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        fontSize: 14,
        lineNumbers: 'on',
        roundedSelection: false,
        scrollbar: {
          verticalScrollbarSize: 8,
          horizontalScrollbarSize: 8,
        },
        suggestOnTriggerCharacters: true,
        wordBasedSuggestions: 'off',
        quickSuggestions: {
          other: true,
          comments: false,
          strings: false,
        },
      });

      monacoEditorRef.current.onDidChangeModelContent(() => {
        if (monacoEditorRef.current) {
          const newValue = monacoEditorRef.current.getValue();
          onChange(newValue);
        }
      });
    }

    return () => {
      if (monacoEditorRef.current) {
        monacoEditorRef.current.dispose();
        monacoEditorRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (monacoEditorRef.current && monacoEditorRef.current.getValue() !== value) {
      monacoEditorRef.current.setValue(value);
    }
  }, [value]);

  useEffect(() => {
    if (monacoEditorRef.current) {
      monaco.editor.setTheme(theme);
    }
  }, [theme]);

  useEffect(() => {
    if (monacoEditorRef.current) {
      const model = monacoEditorRef.current.getModel();
      if (model) {
        monaco.editor.setModelLanguage(model, language);
      }
    }
  }, [language]);

  return (
    <div 
      ref={editorRef} 
      style={{ height, width: '100%' }}
      className="border border-gray-300 dark:border-gray-600 rounded-lg overflow-hidden"
    />
  );
};

export default MonacoEditor;
