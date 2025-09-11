import React from 'react';
import './OfflineIndicator.css';

interface OfflineIndicatorProps {
  isOnline: boolean;
}

const OfflineIndicator: React.FC<OfflineIndicatorProps> = ({ isOnline }) => {
  return (
    <div className={`offline-indicator ${isOnline ? 'online' : 'offline'}`}>
      <div className="status-dot"></div>
      <span className="status-text">
        {isOnline ? 'Online' : 'Offline'}
      </span>
    </div>
  );
};

export default OfflineIndicator;