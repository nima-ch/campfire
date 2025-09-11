import React from 'react';
import './MessageCard.css';
import { ChatMessage } from '../types';
import StepCard from './StepCard';

interface MessageCardProps {
  message: ChatMessage;
  onCitationClick: (docId: string, start: number, end: number) => void;
}

const MessageCard: React.FC<MessageCardProps> = ({ message, onCitationClick }) => {
  if (message.type === 'user') {
    return (
      <div className="message-card user-message">
        <div className="message-header">
          <span className="message-icon">👤</span>
          <span className="message-label">You</span>
          <span className="message-time">
            {message.timestamp.toLocaleTimeString()}
          </span>
        </div>
        <div className="message-content">
          <p>{message.content}</p>
        </div>
      </div>
    );
  }

  if (message.type === 'assistant' && message.response) {
    const { response } = message;
    
    return (
      <div className="message-card assistant-message">
        <div className="message-header">
          <span className="message-icon">🔥</span>
          <span className="message-label">Campfire</span>
          <span className="message-time">
            {message.timestamp.toLocaleTimeString()}
          </span>
        </div>

        {response.emergency_banner && (
          <div className="emergency-banner">
            <div className="emergency-icon">🚨</div>
            <div className="emergency-text">
              <strong>EMERGENCY</strong>
              <p>{response.emergency_banner}</p>
            </div>
          </div>
        )}

        <div className="message-content">
          <div className="response-steps">
            {response.checklist.map((step, index) => (
              <StepCard
                key={index}
                step={step}
                stepNumber={index + 1}
                onCitationClick={onCitationClick}
              />
            ))}
          </div>

          {response.meta.when_to_call_emergency && (
            <div className="emergency-info">
              <h4>⚠️ When to Call Emergency Services:</h4>
              <p>{response.meta.when_to_call_emergency}</p>
            </div>
          )}

          <div className="response-disclaimer">
            <p>{response.meta.disclaimer}</p>
          </div>
        </div>
      </div>
    );
  }

  return null;
};

export default MessageCard;