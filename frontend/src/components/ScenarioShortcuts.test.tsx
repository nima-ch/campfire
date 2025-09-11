import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import ScenarioShortcuts from './ScenarioShortcuts';

describe('ScenarioShortcuts Component', () => {
  const mockOnScenarioClick = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders shortcuts title', () => {
    render(<ScenarioShortcuts onScenarioClick={mockOnScenarioClick} />);
    
    expect(screen.getByText('Quick Emergency Scenarios')).toBeInTheDocument();
  });

  test('renders all scenario buttons', () => {
    render(<ScenarioShortcuts onScenarioClick={mockOnScenarioClick} />);
    
    // Check for some key scenarios
    expect(screen.getByText('Gas Leak')).toBeInTheDocument();
    expect(screen.getByText('Severe Bleeding')).toBeInTheDocument();
    expect(screen.getByText('Burns')).toBeInTheDocument();
    expect(screen.getByText('Choking')).toBeInTheDocument();
    expect(screen.getByText('Unconscious Person')).toBeInTheDocument();
    expect(screen.getByText('Chest Pain')).toBeInTheDocument();
    expect(screen.getByText('Water Emergency')).toBeInTheDocument();
    expect(screen.getByText('Power Outage')).toBeInTheDocument();
  });

  test('renders scenario icons', () => {
    render(<ScenarioShortcuts onScenarioClick={mockOnScenarioClick} />);
    
    // Check for some scenario icons
    expect(screen.getByText('⛽')).toBeInTheDocument(); // Gas leak
    expect(screen.getByText('🩸')).toBeInTheDocument(); // Bleeding
    expect(screen.getByText('🔥')).toBeInTheDocument(); // Burns
    expect(screen.getByText('🫁')).toBeInTheDocument(); // Choking
  });

  test('calls onScenarioClick when scenario button is clicked', () => {
    render(<ScenarioShortcuts onScenarioClick={mockOnScenarioClick} />);
    
    const gasLeakButton = screen.getByText('Gas Leak');
    fireEvent.click(gasLeakButton);
    
    expect(mockOnScenarioClick).toHaveBeenCalledWith({
      id: 'gas-leak',
      label: 'Gas Leak',
      query: 'I smell gas in my house, what should I do?',
      icon: '⛽'
    });
  });

  test('calls onScenarioClick with correct data for different scenarios', () => {
    render(<ScenarioShortcuts onScenarioClick={mockOnScenarioClick} />);
    
    // Test bleeding scenario
    const bleedingButton = screen.getByText('Severe Bleeding');
    fireEvent.click(bleedingButton);
    
    expect(mockOnScenarioClick).toHaveBeenCalledWith({
      id: 'bleeding',
      label: 'Severe Bleeding',
      query: 'Someone is bleeding heavily, how do I stop it?',
      icon: '🩸'
    });

    // Test choking scenario
    const chokingButton = screen.getByText('Choking');
    fireEvent.click(chokingButton);
    
    expect(mockOnScenarioClick).toHaveBeenCalledWith({
      id: 'choking',
      label: 'Choking',
      query: 'Someone is choking and cannot breathe, what do I do?',
      icon: '🫁'
    });
  });

  test('scenario buttons have correct title attributes', () => {
    render(<ScenarioShortcuts onScenarioClick={mockOnScenarioClick} />);
    
    const gasLeakButton = screen.getByTitle('I smell gas in my house, what should I do?');
    expect(gasLeakButton).toBeInTheDocument();
    
    const bleedingButton = screen.getByTitle('Someone is bleeding heavily, how do I stop it?');
    expect(bleedingButton).toBeInTheDocument();
  });

  test('has correct CSS structure', () => {
    const { container } = render(<ScenarioShortcuts onScenarioClick={mockOnScenarioClick} />);
    
    expect(container.querySelector('.scenario-shortcuts')).toBeInTheDocument();
    expect(container.querySelector('.shortcuts-title')).toBeInTheDocument();
    expect(container.querySelector('.shortcuts-grid')).toBeInTheDocument();
    expect(container.querySelectorAll('.scenario-button')).toHaveLength(8);
  });

  test('scenario buttons contain icon and label elements', () => {
    const { container } = render(<ScenarioShortcuts onScenarioClick={mockOnScenarioClick} />);
    
    const scenarioButtons = container.querySelectorAll('.scenario-button');
    scenarioButtons.forEach(button => {
      expect(button.querySelector('.scenario-icon')).toBeInTheDocument();
      expect(button.querySelector('.scenario-label')).toBeInTheDocument();
    });
  });

  test('handles multiple rapid clicks correctly', () => {
    render(<ScenarioShortcuts onScenarioClick={mockOnScenarioClick} />);
    
    const gasLeakButton = screen.getByText('Gas Leak');
    
    // Click multiple times rapidly
    fireEvent.click(gasLeakButton);
    fireEvent.click(gasLeakButton);
    fireEvent.click(gasLeakButton);
    
    expect(mockOnScenarioClick).toHaveBeenCalledTimes(3);
  });
});