import { useState } from 'react';
import Editor, { DiffEditor } from '@monaco-editor/react';
import { X, Check, XCircle } from 'lucide-react';

export default function CodePanel({ isVisible, onClose, fileData, onApprove, onReject }) {
  if (!isVisible) return <div className="code-panel-hidden" />;

  const isDiffMode = fileData?.isDiff;

  return (
    <div className="code-panel-container">
      <div className="code-panel-header">
        <div style={{ color: '#aaa', fontSize: '13px', fontFamily: 'var(--font-mono)' }}>
          {fileData?.path || "Untitled"}
        </div>
        
        <div style={{ display: 'flex', gap: '8px' }}>
          {isDiffMode && (
            <>
              <button 
                onClick={onReject}
                style={{
                  display: 'flex', alignItems: 'center', gap: '4px',
                  backgroundColor: 'rgba(255,64,64,0.1)', color: '#ff4444',
                  border: '1px solid #ff4444', borderRadius: '4px', padding: '4px 8px'
                }}
              >
                <XCircle size={14} /> Reddet
              </button>
              <button 
                onClick={onApprove}
                style={{
                  display: 'flex', alignItems: 'center', gap: '4px',
                  backgroundColor: 'rgba(0,255,204,0.1)', color: 'var(--accent-color)',
                  border: '1px solid var(--accent-color)', borderRadius: '4px', padding: '4px 8px'
                }}
              >
                <Check size={14} /> Onayla
              </button>
            </>
          )}
          <button 
            onClick={onClose} 
            style={{ backgroundColor: 'transparent', color: '#888', marginLeft: '8px' }}
          >
            <X size={18} />
          </button>
        </div>
      </div>

      <div className="code-panel-body">
        {isDiffMode ? (
          <DiffEditor
            height="100%"
            language={fileData?.language || "python"}
            theme="vs-dark"
            original={fileData?.originalContent || ""}
            modified={fileData?.modifiedContent || ""}
            options={{
              renderSideBySide: true,
              minimap: { enabled: false },
              readOnly: true,
              scrollBeyondLastLine: false,
              fontFamily: "var(--font-mono)"
            }}
          />
        ) : (
          <Editor
            height="100%"
            language={fileData?.language || "python"}
            theme="vs-dark"
            value={fileData?.content || ""}
            options={{
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              fontFamily: "var(--font-mono)"
            }}
          />
        )}
      </div>
    </div>
  );
}
