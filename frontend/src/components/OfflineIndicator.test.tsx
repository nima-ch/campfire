import React from 'react';
import { render, screen } from '@testing-library/react';
import OfflineIndicator from './OfflineIndicator';

describe('OfflineIndicator Component', () => {
  test('shows "Offline" when isOnline is false', () => {
    render(<OfflineIndicator isOnline={false} />);
    
    expect(screen.getByText('Offline')).toBeInTheDocument();
  });

  test('shows "Online" when isOnline is true', () => {
    render(<OfflineIndicator isOnline={true} />);
    
    expect(screen.getByText('Online')).toBeInTheDocument();
  });

  test('applies offline CSS class when offline', () => {
    const { container } = render(<OfflineIndicator isOnline={false} />);
    
    expect(container.querySelector('.offline-indicator.offline')).toBeInTheDocument();
  });

  test('applies online CSS class when online', () => {
    const { container } = render(<OfflineIndicator isOnline={true} />);
    
    expect(container.querySelector('.offline-indicator.online')).toBeInTheDocument();
  });

  test('contains status dot element', () => {
    const { container } = render(<OfflineIndicator isOnline={false} />);
    
    expect(container.querySelector('.status-dot')).toBeInTheDocument();
  });

  test('contains status text element', () => {
    const { container } = render(<OfflineIndicator isOnline={false} />);
    
    expect(container.querySelector('.status-text')).toBeInTheDocument();
  });

  test('has correct structure for offline state', () => {
    const { container } = render(<OfflineIndicator isOnline={false} />);
    
    const indicator = container.querySelector('.offline-indicator');
    expect(indicator).toHaveClass('offline');
    expect(indicator?.querySelector('.status-dot')).toBeInTheDocument();
    expect(indicator?.querySelector('.status-text')).toHaveTextContent('Offline');
  });

  test('has correct structure for online state', () => {
    const { container } = render(<OfflineIndicator isOnline={true} />);
    
    const indicator = container.querySelector('.offline-indicator');
    expect(indicator).toHaveClass('online');
    expect(indicator?.querySelector('.status-dot')).toBeInTheDocument();
    expect(indicator?.querySelector('.status-text')).toHaveTextContent('Online');
  });
});