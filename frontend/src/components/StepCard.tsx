import React from 'react';
import './StepCard.css';
import { ChecklistStep } from '../types';

interface StepCardProps {
  step: ChecklistStep;
  stepNumber: number;
  onCitationClick: (docId: string, start: number, end: number) => void;
}

const StepCard: React.FC<StepCardProps> = ({ step, stepNumber, onCitationClick }) => {
  const handleCitationClick = () => {
    onCitationClick(step.source.doc_id, step.source.loc[0], step.source.loc[1]);
  };

  return (
    <div className="step-card">
      <div className="step-header">
        <div className="step-number">{stepNumber}</div>
        <h3 className="step-title">{step.title}</h3>
      </div>
      
      <div className="step-content">
        <p className="step-action">{step.action}</p>
        
        {step.caution && (
          <div className="step-caution">
            <span className="caution-icon">⚠️</span>
            <span className="caution-text">{step.caution}</span>
          </div>
        )}
        
        <button 
          className="citation-button"
          onClick={handleCitationClick}
          title="View source document"
        >
          📖 Source: {step.source.doc_id}
        </button>
      </div>
    </div>
  );
};

export default StepCard;