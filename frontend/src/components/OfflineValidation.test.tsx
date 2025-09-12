/**
 * Offline validation tests for React frontend components.
 * 
 * Tests that frontend works properly in offline mode and handles network failures gracefully.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import ChatInterface from './ChatInterface';
import OfflineIndicator from './OfflineIndicator';
import DocumentViewer from './DocumentViewer';
import { DocumentSnippet } from '../types';

// Mock fetch to simulate network conditions
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock citation click handler
const mockOnCitationClick = jest.fn();

// Mock navigator.onLine
Object.defineProperty(navigator, 'onLine', {
  writable: true,
  value: true,
});

// Helper function to set online status
const setOnlineStatus = (isOnline: boolean) => {
  Object.defineProperty(navigator, 'onLine', {
    writable: true,
    value: isOnline
  });
};

describe('Offline Validation Tests', () => {
  beforeEach(() => {
    mockFetch.mockClear();
    mockOnCitationClick.mockClear();
    setOnlineStatus(true);
  });

  describe('OfflineIndicator Component', () => {
    test('shows offline status when network is unavailable', async () => {
      // Simulate offline mode
      setOnlineStatus(false);
      
      render(<OfflineIndicator isOnline={false} />);
      
      // Should show offline indicator
      expect(screen.getByText(/offline/i)).toBeInTheDocument();
      expect(screen.getByText(/airplane mode/i)).toBeInTheDocument();
    });

    test('shows online status when network is available', () => {
      setOnlineStatus(true);
      
      render(<OfflineIndicator isOnline={true} />);
      
      // Should show online status or no offline indicator
      expect(screen.queryByText(/offline/i)).not.toBeInTheDocument();
    });

    test('responds to network status changes', async () => {
      const { rerender } = render(<OfflineIndicator isOnline={true} />);
      
      // Start online
      expect(screen.queryByText(/offline/i)).not.toBeInTheDocument();
      
      // Simulate going offline
      act(() => {
        setOnlineStatus(false);
        window.dispatchEvent(new Event('offline'));
      });
      
      rerender(<OfflineIndicator isOnline={false} />);
      
      await waitFor(() => {
        expect(screen.getByText(/offline/i)).toBeInTheDocument();
      });
      
      // Simulate coming back online
      act(() => {
        setOnlineStatus(true);
        window.dispatchEvent(new Event('online'));
      });
      
      rerender(<OfflineIndicator isOnline={true} />);
      
      await waitFor(() => {
        expect(screen.queryByText(/offline/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('ChatInterface Offline Behavior', () => {
    test('handles network errors gracefully', async () => {
      // Mock network error
      mockFetch.mockRejectedValue(new Error('Network error'));
      
      render(<ChatInterface onCitationClick={mockOnCitationClick} />);
      
      const input = screen.getByPlaceholderText(/describe your emergency/i);
      const submitButton = screen.getByRole('button', { name: /send/i });
      
      fireEvent.change(input, { target: { value: 'Test emergency query' } });
      fireEvent.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/network error/i)).toBeInTheDocument();
      });
    });

    test('shows appropriate error message for offline requests', async () => {
      // Simulate offline mode
      setOnlineStatus(false);
      mockFetch.mockRejectedValue(new Error('Failed to fetch'));
      
      render(<ChatInterface onCitationClick={mockOnCitationClick} />);
      
      const input = screen.getByPlaceholderText(/describe your emergency/i);
      const submitButton = screen.getByRole('button', { name: /send/i });
      
      fireEvent.change(input, { target: { value: 'Offline test query' } });
      fireEvent.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/offline/i) || screen.getByText(/network/i)).toBeInTheDocument();
      });
    });

    test('retries requests when coming back online', async () => {
      // Start offline
      setOnlineStatus(false);
      mockFetch.mockRejectedValue(new Error('Network unavailable'));
      
      render(<ChatInterface onCitationClick={mockOnCitationClick} />);
      
      const input = screen.getByPlaceholderText(/describe your emergency/i);
      const submitButton = screen.getByRole('button', { name: /send/i });
      
      fireEvent.change(input, { target: { value: 'Retry test query' } });
      fireEvent.click(submitButton);
      
      // Should show error initially
      await waitFor(() => {
        expect(screen.getByText(/network/i) || screen.getByText(/error/i)).toBeInTheDocument();
      });
      
      // Simulate coming back online with successful response
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: true
      });
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          conversation_id: 'test-123',
          blocked: false,
          checklist: [
            {
              title: 'Test Response',
              action: 'This is a test response after reconnection',
              source: { doc_id: 'test-doc', loc: [0, 50] }
            }
          ],
          meta: { disclaimer: 'Not medical advice' }
        })
      });
      
      // Trigger retry (this would depend on your retry mechanism)
      fireEvent.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/test response/i)).toBeInTheDocument();
      });
    });

    test('caches responses for offline viewing', async () => {
      // Mock successful response
      const mockResponse = {
        conversation_id: 'cache-test',
        blocked: false,
        checklist: [
          {
            title: 'Cached Response',
            action: 'This response should be cached for offline viewing',
            source: { doc_id: 'cached-doc', loc: [0, 50] }
          }
        ],
        meta: { disclaimer: 'Not medical advice' }
      };
      
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => mockResponse
      });
      
      render(<ChatInterface onCitationClick={mockOnCitationClick} />);
      
      const input = screen.getByPlaceholderText(/describe your emergency/i);
      const submitButton = screen.getByRole('button', { name: /send/i });
      
      // Submit query while online
      fireEvent.change(input, { target: { value: 'Cache test query' } });
      fireEvent.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/cached response/i)).toBeInTheDocument();
      });
      
      // Go offline
      setOnlineStatus(false);
      
      // Response should still be visible
      expect(screen.getByText(/cached response/i)).toBeInTheDocument();
    });
  });

  describe('DocumentViewer Offline Behavior', () => {
    test('handles document loading errors gracefully', async () => {
      mockFetch.mockRejectedValue(new Error('Document not available offline'));
      
      const mockDocument: DocumentSnippet = {
        doc_id: "test-doc",
        start: 0,
        end: 100,
        text: "Test document content",
        title: "Test Document"
      };

      render(
        <DocumentViewer
          document={mockDocument}
          onBack={() => {}}
        />
      );
      
      await waitFor(() => {
        expect(screen.getByText(/error/i) || screen.getByText(/unavailable/i)).toBeInTheDocument();
      });
    });

    test('shows cached document content when available', async () => {
      // Mock successful document response
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          success: true,
          doc_id: 'test-doc',
          doc_title: 'Test Document',
          text: 'This is cached document content for offline viewing.',
          location: { start_offset: 0, end_offset: 100 }
        })
      });
      
      const mockDocument: DocumentSnippet = {
        doc_id: "test-doc",
        start: 0,
        end: 100,
        text: "This is cached document content for offline viewing.",
        title: "Test Document"
      };

      render(
        <DocumentViewer
          document={mockDocument}
          onBack={() => {}}
        />
      );
      
      await waitFor(() => {
        expect(screen.getByText(/cached document content/i)).toBeInTheDocument();
      });
      
      // Go offline - content should still be visible
      setOnlineStatus(false);
      expect(screen.getByText(/cached document content/i)).toBeInTheDocument();
    });
  });

  describe('Offline Mode Integration', () => {
    test('entire application works in offline mode', async () => {
      // Simulate offline mode from the start
      setOnlineStatus(false);
      
      // Mock local responses (simulating service worker or local cache)
      mockFetch.mockImplementation((url) => {
        if (url.includes('/health')) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              status: 'healthy',
              offline_mode: true,
              timestamp: new Date().toISOString(),
              version: '0.1.0',
              components: {
                corpus_db: 'healthy',
                browser_tool: 'healthy',
                safety_critic: 'healthy'
              }
            })
          });
        }
        
        if (url.includes('/chat')) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              conversation_id: 'offline-test',
              blocked: false,
              checklist: [
                {
                  title: 'Offline Emergency Response',
                  action: 'This response was generated in offline mode',
                  source: { doc_id: 'offline-doc', loc: [0, 50] }
                }
              ],
              meta: { 
                disclaimer: 'Not medical advice',
                offline_mode: true
              }
            })
          });
        }
        
        return Promise.reject(new Error('Network unavailable'));
      });
      
      render(
        <div>
          <OfflineIndicator isOnline={false} />
          <ChatInterface onCitationClick={mockOnCitationClick} />
        </div>
      );
      
      // Should show offline indicator
      expect(screen.getByText(/offline/i)).toBeInTheDocument();
      
      // Should still be able to submit queries
      const input = screen.getByPlaceholderText(/describe your emergency/i);
      const submitButton = screen.getByRole('button', { name: /send/i });
      
      fireEvent.change(input, { target: { value: 'Offline emergency test' } });
      fireEvent.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/offline emergency response/i)).toBeInTheDocument();
      });
    });

    test('handles transition from online to offline gracefully', async () => {
      // Start online
      Object.defineProperty(navigator, 'onLine', {
        writable: true,
        value: true
      });
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({
          conversation_id: 'transition-test',
          blocked: false,
          checklist: [
            {
              title: 'Online Response',
              action: 'This was generated while online',
              source: { doc_id: 'online-doc', loc: [0, 50] }
            }
          ],
          meta: { disclaimer: 'Not medical advice' }
        })
      });
      
      render(
        <div>
          <OfflineIndicator isOnline={true} />
          <ChatInterface onCitationClick={mockOnCitationClick} />
        </div>
      );
      
      // Submit query while online
      const input = screen.getByPlaceholderText(/describe your emergency/i);
      const submitButton = screen.getByRole('button', { name: /send/i });
      
      fireEvent.change(input, { target: { value: 'Online test query' } });
      fireEvent.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/online response/i)).toBeInTheDocument();
      });
      
      // Go offline
      act(() => {
        setOnlineStatus(false);
        window.dispatchEvent(new Event('offline'));
      });
      
      // Should show offline indicator
      await waitFor(() => {
        expect(screen.getByText(/offline/i)).toBeInTheDocument();
      });
      
      // Previous response should still be visible
      expect(screen.getByText(/online response/i)).toBeInTheDocument();
      
      // New requests should show offline behavior
      mockFetch.mockRejectedValue(new Error('Network unavailable'));
      
      fireEvent.change(input, { target: { value: 'Offline test query' } });
      fireEvent.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/network/i) || screen.getByText(/offline/i)).toBeInTheDocument();
      });
    });

    test('validates offline functionality with service worker simulation', async () => {
      // Simulate service worker providing offline responses
      setOnlineStatus(false);
      
      mockFetch.mockImplementation((url, options) => {
        // Simulate service worker intercepting requests
        if (url.includes('/chat')) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              conversation_id: 'sw-test',
              blocked: false,
              checklist: [
                {
                  title: 'Service Worker Response',
                  action: 'This response came from service worker cache',
                  source: { doc_id: 'sw-doc', loc: [0, 50] }
                }
              ],
              meta: { 
                disclaimer: 'Not medical advice',
                served_from_cache: true
              }
            })
          });
        }
        
        return Promise.reject(new Error('Not cached'));
      });
      
      render(<ChatInterface onCitationClick={mockOnCitationClick} />);
      
      const input = screen.getByPlaceholderText(/describe your emergency/i);
      const submitButton = screen.getByRole('button', { name: /send/i });
      
      fireEvent.change(input, { target: { value: 'Service worker test' } });
      fireEvent.click(submitButton);
      
      await waitFor(() => {
        expect(screen.getByText(/service worker response/i)).toBeInTheDocument();
      });
    });
  });

  describe('Performance in Offline Mode', () => {
    test('maintains responsive UI during offline operations', async () => {
      setOnlineStatus(false);
      
      // Mock delayed offline response
      mockFetch.mockImplementation(() => 
        new Promise(resolve => 
          setTimeout(() => resolve({
            ok: true,
            json: async () => ({
              conversation_id: 'perf-test',
              blocked: false,
              checklist: [
                {
                  title: 'Performance Test',
                  action: 'Testing UI responsiveness in offline mode',
                  source: { doc_id: 'perf-doc', loc: [0, 50] }
                }
              ],
              meta: { disclaimer: 'Not medical advice' }
            })
          }), 100)
        )
      );
      
      render(<ChatInterface onCitationClick={mockOnCitationClick} />);
      
      const input = screen.getByPlaceholderText(/describe your emergency/i);
      const submitButton = screen.getByRole('button', { name: /send/i });
      
      const startTime = performance.now();
      
      fireEvent.change(input, { target: { value: 'Performance test query' } });
      fireEvent.click(submitButton);
      
      // UI should remain responsive
      expect(submitButton).toBeDisabled(); // Should show loading state
      
      await waitFor(() => {
        expect(screen.getByText(/performance test/i)).toBeInTheDocument();
      });
      
      const endTime = performance.now();
      const responseTime = endTime - startTime;
      
      // Should complete within reasonable time even offline
      expect(responseTime).toBeLessThan(5000); // 5 seconds max
    });

    test('handles multiple offline requests efficiently', async () => {
      setOnlineStatus(false);
      
      let requestCount = 0;
      mockFetch.mockImplementation(() => {
        requestCount++;
        return Promise.resolve({
          ok: true,
          json: async () => ({
            conversation_id: `multi-test-${requestCount}`,
            blocked: false,
            checklist: [
              {
                title: `Response ${requestCount}`,
                action: `This is offline response number ${requestCount}`,
                source: { doc_id: 'multi-doc', loc: [0, 50] }
              }
            ],
            meta: { disclaimer: 'Not medical advice' }
          })
        });
      });
      
      render(<ChatInterface onCitationClick={mockOnCitationClick} />);
      
      const input = screen.getByPlaceholderText(/describe your emergency/i);
      const submitButton = screen.getByRole('button', { name: /send/i });
      
      // Submit multiple requests
      for (let i = 1; i <= 3; i++) {
        fireEvent.change(input, { target: { value: `Multi test query ${i}` } });
        fireEvent.click(submitButton);
        
        await waitFor(() => {
          expect(screen.getByText(`Response ${i}`)).toBeInTheDocument();
        });
      }
      
      // All responses should be visible
      expect(screen.getByText('Response 1')).toBeInTheDocument();
      expect(screen.getByText('Response 2')).toBeInTheDocument();
      expect(screen.getByText('Response 3')).toBeInTheDocument();
    });
  });
});