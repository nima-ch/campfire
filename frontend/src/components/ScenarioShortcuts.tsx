import React from 'react';
import './ScenarioShortcuts.css';
import { ScenarioShortcut } from '../types';

interface ScenarioShortcutsProps {
  onScenarioClick: (scenario: ScenarioShortcut) => void;
}

const scenarios: ScenarioShortcut[] = [
  {
    id: 'gas-leak',
    label: 'Gas Leak',
    query: 'I smell gas in my house, what should I do?',
    icon: '⛽'
  },
  {
    id: 'bleeding',
    label: 'Severe Bleeding',
    query: 'Someone is bleeding heavily, how do I stop it?',
    icon: '🩸'
  },
  {
    id: 'burns',
    label: 'Burns',
    query: 'Someone has been burned, what first aid should I provide?',
    icon: '🔥'
  },
  {
    id: 'choking',
    label: 'Choking',
    query: 'Someone is choking and cannot breathe, what do I do?',
    icon: '🫁'
  },
  {
    id: 'unconscious',
    label: 'Unconscious Person',
    query: 'I found someone unconscious, what should I check and do?',
    icon: '😵'
  },
  {
    id: 'chest-pain',
    label: 'Chest Pain',
    query: 'Someone is having severe chest pain, what should I do?',
    icon: '💔'
  },
  {
    id: 'boil-water',
    label: 'Water Emergency',
    query: 'There is a boil water advisory, what precautions should I take?',
    icon: '💧'
  },
  {
    id: 'power-outage',
    label: 'Power Outage',
    query: 'The power is out during a storm, what safety steps should I follow?',
    icon: '⚡'
  }
];

const ScenarioShortcuts: React.FC<ScenarioShortcutsProps> = ({ onScenarioClick }) => {
  return (
    <div className="scenario-shortcuts">
      <h3 className="shortcuts-title">Quick Emergency Scenarios</h3>
      <div className="shortcuts-grid">
        {scenarios.map((scenario) => (
          <button
            key={scenario.id}
            className="scenario-button"
            onClick={() => onScenarioClick(scenario)}
            title={scenario.query}
          >
            <span className="scenario-icon">{scenario.icon}</span>
            <span className="scenario-label">{scenario.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
};

export default ScenarioShortcuts;