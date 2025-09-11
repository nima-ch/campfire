import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ChatInterface from './ChatInterface';

// Mock fetch
global.fetch = jest.fn();

// Mock child components
jest.mock('./MessageCard', () => {
  return function MockMessageCard({ message, onCitationClick }: any) {
    return (
      <div data-testid={`message-${message.id}`}>
        {message.content}
        {message.response && (
          <button onClick={() => onCitationClick('test-doc', 0, 100)}>
            Citation
          </button>
        )}
      </div>
    );
  };
});

jest.mock('./ScenarioShortcuts', () => {
  return function MockScenarioShortcuts({ onScenarioClick }: any) {
    return (
      <div data-testid="scenario-shortcuts">
        <button onClick={() => onScenarioClick({ id: 'test', query: 'test query' })}>
          Test Scenario
        </button>
      </div>
    );
  };
});

jest.mock('./LoadingIndicator', () => {
  return function MockLoadingIndicator() {
    return <div data-testid="loading-indicator">Loading...</div>;
  };
});

describe('ChatInterface Component', () => {
  const mockOnCitationClick = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (fetch as jest.Mock).mockClear();
  });

  test('renders welcome message initially', () => {
    render(<ChatInterface onCitationClick={mockOnCitationClick} />);
    
    expect(screen.getByText('🚨 Emergency Guidance')).toBeInTheDocument();
    expect(screen.getByTestId('scenario-shortcuts')).toBeInTheDocument();
  });

  test('renders input form', () => {
    render(<ChatInterface onCitationClick={mockOnCitationClick} />);
    
    expect(screen.getByPlaceholderText('Describe your emergency situation...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /➤/ })).toBeInTheDocument();
  });

  test('handles text input', () => {
    render(<ChatInterface onCitationClick={mockOnCitationClick} />);
    
    const input = screen.getByPlaceholderText('Describe your emergency situation...');
    fireEvent.change(input, { target: { value: 'test query' } });
    
    expect(input).toHaveValue('test query');
  });

  test('shows character count', () => {
    render(<ChatInterface onCitationClick={mockOnCitationClick} />);
    
    const input = screen.getByPlaceholderText('Describe your emergency situation...');
    fireEvent.change(input, { target: { value: 'test' } });
    
    expect(screen.getByText('4/500')).toBeInTheDocument();
  });

  test('disables send button when input is empty', () => {
    render(<ChatInterface onCitationClick={mockOnCitationClick} />);
    
    const sendButton = screen.getByRole('button', { name: /➤/ });
    expect(sendButton).toBeDisabled();
  });

  test('enables send button when input has text', () => {
    render(<ChatInterface onCitationClick={mockOnCitationClick} />);
    
    const input = screen.getByPlaceholderText('Describe your emergency situation...');
    const sendButton = screen.getByRole('button', { name: /➤/ });
    
    fireEvent.change(input, { target: { value: 'test query' } });
    expect(sendButton).not.toBeDisabled();
  });

  test('submits message on form submit', async () => {
    const mockResponse = {
      checklist: [{ title: 'Test', action: 'Test action', source: { doc_id: 'test', loc: [0, 100] } }],
      meta: { disclaimer: 'Test disclaimer' }
    };

    (fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    render(<ChatInterface onCitationClick={mockOnCitationClick} />);
    
    const input = screen.getByPlaceholderText('Describe your emergency situation...');
    const form = input.closest('form')!;
    
    fireEvent.change(input, { target: { value: 'test query' } });
    fireEvent.submit(form);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: 'test query' }),
      });
    });
  });

  test('shows loading indicator during request', async () => {
    (fetch as jest.Mock).mockImplementation(() => new Promise(resolve => setTimeout(resolve, 100)));

    render(<ChatInterface onCitationClick={mockOnCitationClick} />);
    
    const input = screen.getByPlaceholderText('Describe your emergency situation...');
    const form = input.closest('form')!;
    
    fireEvent.change(input, { target: { value: 'test query' } });
    fireEvent.submit(form);

    expect(screen.getByTestId('loading-indicator')).toBeInTheDocument();
  });

  test('handles API error', async () => {
    (fetch as jest.Mock).mockRejectedValueOnce(new Error('Network error'));

    render(<ChatInterface onCitationClick={mockOnCitationClick} />);
    
    const input = screen.getByPlaceholderText('Describe your emergency situation...');
    const form = input.closest('form')!;
    
    fireEvent.change(input, { target: { value: 'test query' } });
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByText(/Error: Network error/)).toBeInTheDocument();
    });
  });

  test('handles scenario shortcut click', async () => {
    const mockResponse = {
      checklist: [{ title: 'Test', action: 'Test action', source: { doc_id: 'test', loc: [0, 100] } }],
      meta: { disclaimer: 'Test disclaimer' }
    };

    (fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    render(<ChatInterface onCitationClick={mockOnCitationClick} />);
    
    const scenarioButton = screen.getByText('Test Scenario');
    fireEvent.click(scenarioButton);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: 'test query' }),
      });
    });
  });

  test('clears input after successful submission', async () => {
    const mockResponse = {
      checklist: [{ title: 'Test', action: 'Test action', source: { doc_id: 'test', loc: [0, 100] } }],
      meta: { disclaimer: 'Test disclaimer' }
    };

    (fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => mockResponse,
    });

    render(<ChatInterface onCitationClick={mockOnCitationClick} />);
    
    const input = screen.getByPlaceholderText('Describe your emergency situation...');
    const form = input.closest('form')!;
    
    fireEvent.change(input, { target: { value: 'test query' } });
    fireEvent.submit(form);

    await waitFor(() => {
      expect(input).toHaveValue('');
    });
  });
});