import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import App from './App';

// Mock the child components
jest.mock('./components/ChatInterface', () => {
  return function MockChatInterface({ onCitationClick }: any) {
    return (
      <div data-testid="chat-interface">
        <button onClick={() => onCitationClick('test-doc', 0, 100)}>
          Test Citation
        </button>
      </div>
    );
  };
});

jest.mock('./components/DocumentViewer', () => {
  return function MockDocumentViewer({ onBack }: any) {
    return (
      <div data-testid="document-viewer">
        <button onClick={onBack}>Back</button>
      </div>
    );
  };
});

jest.mock('./components/AdminPanel', () => {
  return function MockAdminPanel() {
    return <div data-testid="admin-panel">Admin Panel</div>;
  };
});

jest.mock('./components/OfflineIndicator', () => {
  return function MockOfflineIndicator({ isOnline }: any) {
    return <div data-testid="offline-indicator">{isOnline ? 'Online' : 'Offline'}</div>;
  };
});

describe('App Component', () => {
  beforeEach(() => {
    // Mock navigator.onLine
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      value: true,
    });
  });

  test('renders app title and subtitle', () => {
    render(<App />);
    expect(screen.getByText('🔥 Campfire')).toBeInTheDocument();
    expect(screen.getByText('Offline Emergency Helper')).toBeInTheDocument();
  });

  test('renders offline indicator', () => {
    render(<App />);
    expect(screen.getByTestId('offline-indicator')).toBeInTheDocument();
  });

  test('renders disclaimer in footer', () => {
    render(<App />);
    expect(screen.getByText(/Not medical advice/)).toBeInTheDocument();
    expect(screen.getByText(/call local emergency services/)).toBeInTheDocument();
  });

  test('shows chat interface by default', () => {
    render(<App />);
    expect(screen.getByTestId('chat-interface')).toBeInTheDocument();
    expect(screen.queryByTestId('document-viewer')).not.toBeInTheDocument();
    expect(screen.queryByTestId('admin-panel')).not.toBeInTheDocument();
  });

  test('switches to admin panel when admin button clicked', () => {
    render(<App />);
    
    const adminButton = screen.getByText('Admin');
    fireEvent.click(adminButton);
    
    expect(screen.getByTestId('admin-panel')).toBeInTheDocument();
    expect(screen.queryByTestId('chat-interface')).not.toBeInTheDocument();
  });

  test('switches to document viewer when citation clicked', () => {
    render(<App />);
    
    const citationButton = screen.getByText('Test Citation');
    fireEvent.click(citationButton);
    
    expect(screen.getByTestId('document-viewer')).toBeInTheDocument();
    expect(screen.queryByTestId('chat-interface')).not.toBeInTheDocument();
  });

  test('returns to chat from document viewer', () => {
    render(<App />);
    
    // Go to document viewer
    const citationButton = screen.getByText('Test Citation');
    fireEvent.click(citationButton);
    
    // Return to chat
    const backButton = screen.getByText('Back');
    fireEvent.click(backButton);
    
    expect(screen.getByTestId('chat-interface')).toBeInTheDocument();
    expect(screen.queryByTestId('document-viewer')).not.toBeInTheDocument();
  });

  test('nav buttons show active state correctly', () => {
    render(<App />);
    
    const chatButton = screen.getByText('Chat');
    const adminButton = screen.getByText('Admin');
    
    // Chat should be active by default
    expect(chatButton).toHaveClass('active');
    expect(adminButton).not.toHaveClass('active');
    
    // Switch to admin
    fireEvent.click(adminButton);
    expect(adminButton).toHaveClass('active');
    expect(chatButton).not.toHaveClass('active');
  });
});