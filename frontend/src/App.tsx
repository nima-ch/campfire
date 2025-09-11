import React, { useState, useEffect } from 'react';
import './App.css';
import ChatInterface from './components/ChatInterface';
import DocumentViewer from './components/DocumentViewer';
import AdminPanel from './components/AdminPanel';
import OfflineIndicator from './components/OfflineIndicator';
import { DocumentSnippet } from './types';

function App() {
  const [currentView, setCurrentView] = useState<'chat' | 'document' | 'admin'>('chat');
  const [selectedDocument, setSelectedDocument] = useState<DocumentSnippet | null>(null);
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  // Monitor network connectivity
  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const handleCitationClick = (docId: string, start: number, end: number) => {
    setSelectedDocument({ doc_id: docId, start, end });
    setCurrentView('document');
  };

  const handleBackToChat = () => {
    setCurrentView('chat');
    setSelectedDocument(null);
  };

  return (
    <div className="App">
      <header className="app-header">
        <div className="header-content">
          <h1 className="app-title">🔥 Campfire</h1>
          <p className="app-subtitle">Offline Emergency Helper</p>
          <OfflineIndicator isOnline={isOnline} />
        </div>
        <nav className="app-nav">
          <button 
            className={`nav-button ${currentView === 'chat' ? 'active' : ''}`}
            onClick={() => setCurrentView('chat')}
          >
            Chat
          </button>
          <button 
            className={`nav-button ${currentView === 'admin' ? 'active' : ''}`}
            onClick={() => setCurrentView('admin')}
          >
            Admin
          </button>
        </nav>
      </header>

      <main className="app-main">
        {currentView === 'chat' && (
          <ChatInterface onCitationClick={handleCitationClick} />
        )}
        {currentView === 'document' && selectedDocument && (
          <DocumentViewer 
            document={selectedDocument} 
            onBack={handleBackToChat}
          />
        )}
        {currentView === 'admin' && (
          <AdminPanel />
        )}
      </main>

      <footer className="app-footer">
        <p className="disclaimer">
          ⚠️ <strong>Not medical advice.</strong> For emergencies, call local emergency services.
        </p>
      </footer>
    </div>
  );
}

export default App;