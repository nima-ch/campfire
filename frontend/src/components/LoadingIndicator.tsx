import React from 'react';
import './LoadingIndicator.css';

const LoadingIndicator: React.FC = () => {
  return (
    <div className="loading-indicator">
      <div className="loading-content">
        <div className="loading-spinner">
          <div className="spinner-ring"></div>
          <div className="spinner-ring"></div>
          <div className="spinner-ring"></div>
        </div>
        <div className="loading-text">
          <p className="loading-message">🔥 Campfire is thinking...</p>
          <p className="loading-submessage">Searching emergency guidelines</p>
        </div>
      </div>
    </div>
  );
};

export default LoadingIndicator;