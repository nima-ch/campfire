import React, { useState, useRef, useEffect } from 'react';
import './ChatInterface.css';
import { ChatMessage, ChatResponse, ScenarioShortcut } from '../types';
import MessageCard from './MessageCard';
import ScenarioShortcuts from './ScenarioShortcuts';
import LoadingIndicator from './LoadingIndicator';

interface ChatInterfaceProps {
  onCitationClick: (docId: string, start: number, end: number) => void;
}

const ChatInterface: React.FC<ChatInterfaceProps> = ({ onCitationClick }) => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    if (messagesEndRef.current && typeof messagesEndRef.current.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (query: string) => {
    if (!query.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: query,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data: ChatResponse = await response.json();

      const assistantMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: 'Emergency guidance provided',
        response: data,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMessage]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get response');
    } finally {
      setIsLoading(false);
    }
  };

  const handleInputSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSubmit(inputValue);
  };

  const handleScenarioClick = (scenario: ScenarioShortcut) => {
    handleSubmit(scenario.query);
  };

  return (
    <div className="chat-interface">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="welcome-message">
            <h2>🚨 Emergency Guidance</h2>
            <p>Ask about emergency situations, first aid, or preparedness. All responses are based on IFRC and WHO guidelines.</p>
            <ScenarioShortcuts onScenarioClick={handleScenarioClick} />
          </div>
        )}
        
        {messages.map((message) => (
          <MessageCard
            key={message.id}
            message={message}
            onCitationClick={onCitationClick}
          />
        ))}
        
        {isLoading && <LoadingIndicator />}
        
        {error && (
          <div className="error-message">
            <p>❌ Error: {error}</p>
            <p>Please try again or check your connection.</p>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      <form className="chat-input-form" onSubmit={handleInputSubmit}>
        <div className="input-container">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Describe your emergency situation..."
            className="chat-input"
            disabled={isLoading}
            maxLength={500}
          />
          <button
            type="submit"
            className="send-button"
            disabled={!inputValue.trim() || isLoading}
          >
            {isLoading ? '⏳' : '➤'}
          </button>
        </div>
        <div className="input-help">
          <span className="char-count">{inputValue.length}/500</span>
          <span className="help-text">Press Enter to send</span>
        </div>
      </form>
    </div>
  );
};

export default ChatInterface;