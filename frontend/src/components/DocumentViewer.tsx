import React, { useState, useEffect } from 'react';
import './DocumentViewer.css';
import { DocumentSnippet } from '../types';

interface DocumentViewerProps {
  document: DocumentSnippet;
  onBack: () => void;
}

const DocumentViewer: React.FC<DocumentViewerProps> = ({ document, onBack }) => {
  const [documentData, setDocumentData] = useState<DocumentSnippet | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDocument = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const response = await fetch(`/api/document/${document.doc_id}?start=${document.start}&end=${document.end}`);
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        setDocumentData(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load document');
      } finally {
        setLoading(false);
      }
    };

    fetchDocument();
  }, [document]);

  const highlightText = (text: string, start: number, end: number) => {
    if (!text) return '';
    
    const beforeHighlight = text.substring(0, start);
    const highlighted = text.substring(start, end);
    const afterHighlight = text.substring(end);
    
    return (
      <>
        {beforeHighlight}
        <mark className="highlighted-text">{highlighted}</mark>
        {afterHighlight}
      </>
    );
  };

  if (loading) {
    return (
      <div className="document-viewer">
        <div className="document-header">
          <button className="back-button" onClick={onBack}>
            ← Back to Chat
          </button>
          <h2>Loading Document...</h2>
        </div>
        <div className="document-loading">
          <div className="loading-spinner"></div>
          <p>Loading document content...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="document-viewer">
        <div className="document-header">
          <button className="back-button" onClick={onBack}>
            ← Back to Chat
          </button>
          <h2>Error Loading Document</h2>
        </div>
        <div className="document-error">
          <p>❌ {error}</p>
          <button className="retry-button" onClick={() => window.location.reload()}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="document-viewer">
      <div className="document-header">
        <button className="back-button" onClick={onBack}>
          ← Back to Chat
        </button>
        <div className="document-info">
          <h2 className="document-title">
            📖 {documentData?.title || document.doc_id}
          </h2>
          {documentData?.page && (
            <p className="document-meta">Page {documentData.page}</p>
          )}
        </div>
      </div>

      <div className="document-content">
        <div className="document-text">
          {documentData?.text ? (
            <p>
              {highlightText(documentData.text, 0, document.end - document.start)}
            </p>
          ) : (
            <p>No content available for this section.</p>
          )}
        </div>
        
        <div className="document-citation">
          <h4>Citation Information</h4>
          <ul>
            <li><strong>Document:</strong> {document.doc_id}</li>
            <li><strong>Location:</strong> Characters {document.start} - {document.end}</li>
            {documentData?.page && (
              <li><strong>Page:</strong> {documentData.page}</li>
            )}
          </ul>
        </div>
      </div>
    </div>
  );
};

export default DocumentViewer;