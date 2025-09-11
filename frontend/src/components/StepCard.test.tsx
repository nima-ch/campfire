import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import StepCard from './StepCard';
import { ChecklistStep } from '../types';

describe('StepCard Component', () => {
  const mockOnCitationClick = jest.fn();

  const mockStep: ChecklistStep = {
    title: 'Test Step',
    action: 'This is a test action to perform',
    source: {
      doc_id: 'IFRC-2020',
      loc: [100, 200]
    }
  };

  const mockStepWithCaution: ChecklistStep = {
    ...mockStep,
    caution: 'Be careful when performing this action'
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders step number and title', () => {
    render(<StepCard step={mockStep} stepNumber={1} onCitationClick={mockOnCitationClick} />);
    
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('Test Step')).toBeInTheDocument();
  });

  test('renders step action', () => {
    render(<StepCard step={mockStep} stepNumber={1} onCitationClick={mockOnCitationClick} />);
    
    expect(screen.getByText('This is a test action to perform')).toBeInTheDocument();
  });

  test('renders citation button with document ID', () => {
    render(<StepCard step={mockStep} stepNumber={1} onCitationClick={mockOnCitationClick} />);
    
    expect(screen.getByText(/Source: IFRC-2020/)).toBeInTheDocument();
  });

  test('calls onCitationClick when citation button is clicked', () => {
    render(<StepCard step={mockStep} stepNumber={1} onCitationClick={mockOnCitationClick} />);
    
    const citationButton = screen.getByText(/Source: IFRC-2020/);
    fireEvent.click(citationButton);
    
    expect(mockOnCitationClick).toHaveBeenCalledWith('IFRC-2020', 100, 200);
  });

  test('renders caution when provided', () => {
    render(<StepCard step={mockStepWithCaution} stepNumber={2} onCitationClick={mockOnCitationClick} />);
    
    expect(screen.getByText('⚠️')).toBeInTheDocument();
    expect(screen.getByText('Be careful when performing this action')).toBeInTheDocument();
  });

  test('does not render caution when not provided', () => {
    render(<StepCard step={mockStep} stepNumber={1} onCitationClick={mockOnCitationClick} />);
    
    expect(screen.queryByText('⚠️')).not.toBeInTheDocument();
  });

  test('applies correct step number', () => {
    render(<StepCard step={mockStep} stepNumber={5} onCitationClick={mockOnCitationClick} />);
    
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  test('citation button has correct title attribute', () => {
    render(<StepCard step={mockStep} stepNumber={1} onCitationClick={mockOnCitationClick} />);
    
    const citationButton = screen.getByTitle('View source document');
    expect(citationButton).toBeInTheDocument();
  });

  test('step card has correct CSS classes', () => {
    const { container } = render(<StepCard step={mockStep} stepNumber={1} onCitationClick={mockOnCitationClick} />);
    
    expect(container.querySelector('.step-card')).toBeInTheDocument();
    expect(container.querySelector('.step-header')).toBeInTheDocument();
    expect(container.querySelector('.step-number')).toBeInTheDocument();
    expect(container.querySelector('.step-title')).toBeInTheDocument();
    expect(container.querySelector('.step-content')).toBeInTheDocument();
    expect(container.querySelector('.step-action')).toBeInTheDocument();
    expect(container.querySelector('.citation-button')).toBeInTheDocument();
  });

  test('caution section has correct CSS classes when present', () => {
    const { container } = render(<StepCard step={mockStepWithCaution} stepNumber={1} onCitationClick={mockOnCitationClick} />);
    
    expect(container.querySelector('.step-caution')).toBeInTheDocument();
    expect(container.querySelector('.caution-icon')).toBeInTheDocument();
    expect(container.querySelector('.caution-text')).toBeInTheDocument();
  });
});