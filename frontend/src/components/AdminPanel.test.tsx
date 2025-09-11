import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import AdminPanel from './AdminPanel';

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

// Mock localStorage
const mockLocalStorage = {
  getItem: jest.fn(),
  setItem: jest.fn(),
  removeItem: jest.fn(),
};
Object.defineProperty(window, 'localStorage', {
  value: mockLocalStorage,
});

describe('AdminPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockLocalStorage.getItem.mockReturnValue(null);
  });

  describe('Authentication', () => {
    it('shows login form when not authenticated', () => {
      act(() => {
        render(<AdminPanel />);
      });
      
      expect(screen.getByText('🔐 Admin Access')).toBeInTheDocument();
      expect(screen.getByLabelText('Password')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument();
    });

    it('handles successful login', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          access_token: 'test-token',
          token_type: 'bearer',
          expires_in: 3600,
        }),
      });

      // Mock subsequent data fetching calls
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ logs: [], total_count: 0, page: 1, page_size: 50 }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            total_interactions: 0,
            blocked_responses: 0,
            emergency_detections: 0,
            recent_activity_24h: 0,
            block_rate: 0,
            emergency_rate: 0,
            query_patterns: [],
            provider_usage: [],
            recent_system_health: {},
            performance_metrics: { endpoint_performance: [], status_code_distribution: [] },
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ health_history: [] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ harmony_debug: [] }),
        });

      render(<AdminPanel />);
      
      const passwordInput = screen.getByLabelText('Password');
      const loginButton = screen.getByRole('button', { name: /login/i });

      fireEvent.change(passwordInput, { target: { value: 'test-password' } });
      fireEvent.click(loginButton);

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith('/api/admin/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ password: 'test-password' }),
        });
      });

      await waitFor(() => {
        expect(screen.getByText('🛡️ Admin Dashboard')).toBeInTheDocument();
      });

      expect(mockLocalStorage.setItem).toHaveBeenCalledWith('admin_token', 'test-token');
    });

    it('handles login failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
      });

      render(<AdminPanel />);
      
      const passwordInput = screen.getByLabelText('Password');
      const loginButton = screen.getByRole('button', { name: /login/i });

      fireEvent.change(passwordInput, { target: { value: 'wrong-password' } });
      fireEvent.click(loginButton);

      await waitFor(() => {
        expect(screen.getByText(/❌ Invalid password/)).toBeInTheDocument();
      });
    });

    it('auto-authenticates with stored token', async () => {
      mockLocalStorage.getItem.mockReturnValue('stored-token');

      // Mock data fetching calls
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ logs: [], total_count: 0, page: 1, page_size: 50 }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            total_interactions: 0,
            blocked_responses: 0,
            emergency_detections: 0,
            recent_activity_24h: 0,
            block_rate: 0,
            emergency_rate: 0,
            query_patterns: [],
            provider_usage: [],
            recent_system_health: {},
            performance_metrics: { endpoint_performance: [], status_code_distribution: [] },
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ health_history: [] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ harmony_debug: [] }),
        });

      await act(async () => {
        render(<AdminPanel />);
      });

      await waitFor(() => {
        expect(screen.getByText('🛡️ Admin Dashboard')).toBeInTheDocument();
      });
    });
  });

  describe('Dashboard Tabs', () => {
    beforeEach(async () => {
      // Setup authenticated state
      mockLocalStorage.getItem.mockReturnValue('test-token');
      
      // Mock all data fetching calls
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ logs: [], total_count: 0, page: 1, page_size: 50 }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            total_interactions: 100,
            blocked_responses: 10,
            emergency_detections: 5,
            recent_activity_24h: 25,
            block_rate: 0.1,
            emergency_rate: 0.05,
            query_patterns: [],
            provider_usage: [],
            recent_system_health: {},
            performance_metrics: { endpoint_performance: [], status_code_distribution: [] },
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ health_history: [] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ harmony_debug: [] }),
        });
    });

    it('shows all tab options', async () => {
      await act(async () => {
        render(<AdminPanel />);
      });

      await waitFor(() => {
        expect(screen.getByText('📋 Audit Logs')).toBeInTheDocument();
        expect(screen.getByText('📊 Statistics')).toBeInTheDocument();
        expect(screen.getByText('💚 System Health')).toBeInTheDocument();
        expect(screen.getByText('🔧 Debug')).toBeInTheDocument();
      });
    });

    it('switches between tabs', async () => {
      await act(async () => {
        render(<AdminPanel />);
      });

      await waitFor(() => {
        expect(screen.getByText('📋 Audit Logs')).toBeInTheDocument();
      });

      // Click on Statistics tab
      await act(async () => {
        fireEvent.click(screen.getByText('📊 Statistics'));
      });
      
      await waitFor(() => {
        expect(screen.getByText('Total Interactions')).toBeInTheDocument();
      });

      // Click on System Health tab
      await act(async () => {
        fireEvent.click(screen.getByText('💚 System Health'));
      });
      
      await waitFor(() => {
        // When there's no health data, it shows "No health data available"
        expect(screen.getByText('No health data available')).toBeInTheDocument();
      });

      // Click on Debug tab
      await act(async () => {
        fireEvent.click(screen.getByText('🔧 Debug'));
      });
      
      await waitFor(() => {
        // When there's no debug data, it shows "No Harmony debug data available"
        expect(screen.getByText('No Harmony debug data available')).toBeInTheDocument();
      });
    });
  });

  describe('Audit Logs Tab', () => {
    it('displays audit logs correctly', async () => {
      mockLocalStorage.getItem.mockReturnValue('test-token');
      
      const mockLogs = [
        {
          id: '1',
          timestamp: '2025-01-01T12:00:00Z',
          query: 'How to treat a cut?',
          response_blocked: false,
          critic_decision: {
            status: 'ALLOW',
            reasons: ['Valid response'],
            emergency_detected: false,
          },
          emergency_detected: false,
          conversation_id: 'test-123',
          response_time_ms: 1200,
          llm_provider: 'OllamaProvider',
          harmony_tokens_used: 150,
        },
        {
          id: '2',
          timestamp: '2025-01-01T11:00:00Z',
          query: 'How to perform surgery?',
          response_blocked: true,
          critic_decision: {
            status: 'BLOCK',
            reasons: ['Inappropriate medical advice', 'Missing citations'],
            emergency_detected: true,
          },
          emergency_detected: true,
          conversation_id: 'test-456',
          response_time_ms: 800,
        },
      ];

      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ logs: mockLogs, total_count: 2, page: 1, page_size: 50 }),
        })
        .mockResolvedValue({
          ok: true,
          json: async () => ({}),
        });

      await act(async () => {
        render(<AdminPanel />);
      });

      await waitFor(() => {
        expect(screen.getByText('How to treat a cut?')).toBeInTheDocument();
        expect(screen.getByText('How to perform surgery?')).toBeInTheDocument();
        expect(screen.getByText('✅ ALLOWED')).toBeInTheDocument();
        expect(screen.getByText('🚫 BLOCKED')).toBeInTheDocument();
        expect(screen.getByText('⏱️ 1200ms')).toBeInTheDocument();
        expect(screen.getByText('⚠️ Emergency Keywords Detected')).toBeInTheDocument();
      });
    });

    it('shows no logs message when empty', async () => {
      mockLocalStorage.getItem.mockReturnValue('test-token');
      
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ logs: [], total_count: 0, page: 1, page_size: 50 }),
      });

      await act(async () => {
        render(<AdminPanel />);
      });

      await waitFor(() => {
        expect(screen.getByText('No audit logs available.')).toBeInTheDocument();
      });
    });
  });

  describe('Statistics Tab', () => {
    it('displays statistics correctly', async () => {
      mockLocalStorage.getItem.mockReturnValue('test-token');
      
      const mockStats = {
        total_interactions: 150,
        blocked_responses: 15,
        emergency_detections: 8,
        recent_activity_24h: 30,
        block_rate: 0.1,
        emergency_rate: 0.053,
        query_patterns: [],
        provider_usage: [
          {
            llm_provider: 'OllamaProvider',
            usage_count: 100,
            avg_response_time: 1250.5,
          },
          {
            llm_provider: 'VLLMProvider',
            usage_count: 50,
            avg_response_time: 980.2,
          },
        ],
        recent_system_health: {},
        performance_metrics: {
          endpoint_performance: [
            {
              endpoint: '/chat',
              request_count: 140,
              avg_response_time: 1150.3,
              min_response_time: 500,
              max_response_time: 3000,
            },
          ],
          status_code_distribution: [
            { status_code: 200, count: 135 },
            { status_code: 500, count: 5 },
          ],
        },
      };

      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ logs: [], total_count: 0, page: 1, page_size: 50 }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockStats,
        })
        .mockResolvedValue({
          ok: true,
          json: async () => ({}),
        });

      await act(async () => {
        render(<AdminPanel />);
      });

      // Switch to Statistics tab
      await act(async () => {
        fireEvent.click(screen.getByText('📊 Statistics'));
      });

      await waitFor(() => {
        expect(screen.getByText('150')).toBeInTheDocument(); // Total interactions
        expect(screen.getByText('15')).toBeInTheDocument(); // Blocked responses
        expect(screen.getByText('8')).toBeInTheDocument(); // Emergency detections
        expect(screen.getByText('30')).toBeInTheDocument(); // Recent activity
        expect(screen.getByText('10.0% block rate')).toBeInTheDocument();
        expect(screen.getByText('5.3% emergency rate')).toBeInTheDocument();
      });

      // Check provider usage
      await waitFor(() => {
        expect(screen.getByText('OllamaProvider')).toBeInTheDocument();
        expect(screen.getByText('VLLMProvider')).toBeInTheDocument();
        expect(screen.getByText('100 requests')).toBeInTheDocument();
        expect(screen.getByText('50 requests')).toBeInTheDocument();
      });

      // Check endpoint performance
      await waitFor(() => {
        expect(screen.getByText('/chat')).toBeInTheDocument();
        expect(screen.getByText('140 requests')).toBeInTheDocument();
        expect(screen.getByText('1150ms avg')).toBeInTheDocument();
      });
    });
  });

  describe('System Health Tab', () => {
    it('displays system health data correctly', async () => {
      mockLocalStorage.getItem.mockReturnValue('test-token');
      
      const mockHealthData = [
        {
          timestamp: '2025-01-01T12:00:00Z',
          cpu_percent: 45.2,
          memory_percent: 67.8,
          memory_used_mb: 2048.5,
          disk_usage_percent: 23.1,
          llm_provider_status: 'healthy',
          corpus_db_status: 'healthy',
        },
        {
          timestamp: '2025-01-01T11:00:00Z',
          cpu_percent: 52.1,
          memory_percent: 71.2,
          memory_used_mb: 2156.3,
          disk_usage_percent: 23.2,
          llm_provider_status: 'healthy',
          corpus_db_status: 'unavailable',
        },
      ];

      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ logs: [], total_count: 0, page: 1, page_size: 50 }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({}),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ health_history: mockHealthData }),
        })
        .mockResolvedValue({
          ok: true,
          json: async () => ({}),
        });

      await act(async () => {
        render(<AdminPanel />);
      });

      // Switch to System Health tab
      await act(async () => {
        fireEvent.click(screen.getByText('💚 System Health'));
      });

      await waitFor(() => {
        expect(screen.getByText('System Health (Last 24 hours)')).toBeInTheDocument();
        expect(screen.getByText('45.2%')).toBeInTheDocument(); // CPU
        expect(screen.getByText('67.8%')).toBeInTheDocument(); // Memory
        expect(screen.getByText('23.1%')).toBeInTheDocument(); // Disk
      });

      // Check health history
      await waitFor(() => {
        expect(screen.getByText('Recent Health History')).toBeInTheDocument();
        expect(screen.getByText('CPU: 45.2%')).toBeInTheDocument();
        expect(screen.getByText('Mem: 67.8%')).toBeInTheDocument();
        expect(screen.getByText('Disk: 23.1%')).toBeInTheDocument();
      });
    });

    it('shows no data message when health history is empty', async () => {
      mockLocalStorage.getItem.mockReturnValue('test-token');
      
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ logs: [], total_count: 0, page: 1, page_size: 50 }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({}),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ health_history: [] }),
        })
        .mockResolvedValue({
          ok: true,
          json: async () => ({}),
        });

      await act(async () => {
        render(<AdminPanel />);
      });

      // Switch to System Health tab
      await act(async () => {
        fireEvent.click(screen.getByText('💚 System Health'));
      });

      await waitFor(() => {
        expect(screen.getByText('No health data available')).toBeInTheDocument();
      });
    });
  });

  describe('Debug Tab', () => {
    it('displays Harmony debug data correctly', async () => {
      mockLocalStorage.getItem.mockReturnValue('test-token');
      
      const mockDebugData = [
        {
          timestamp: '2025-01-01T12:00:00Z',
          query: 'How to treat burns?',
          harmony_debug_data: {
            prefill_tokens: 150,
            completion_tokens: 200,
            tool_calls: [
              { name: 'search', args: { q: 'burn treatment' } },
              { name: 'open', args: { doc_id: 'ifrc-2020', start: 100, end: 200 } },
            ],
          },
          harmony_tokens_used: 350,
        },
      ];

      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ logs: [], total_count: 0, page: 1, page_size: 50 }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({}),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ health_history: [] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ harmony_debug: mockDebugData }),
        });

      await act(async () => {
        render(<AdminPanel />);
      });

      // Switch to Debug tab
      await act(async () => {
        fireEvent.click(screen.getByText('🔧 Debug'));
      });

      await waitFor(() => {
        expect(screen.getByText('Harmony Debug Data')).toBeInTheDocument();
        expect(screen.getByText('How to treat burns?')).toBeInTheDocument();
        expect(screen.getByText('Tokens: 350')).toBeInTheDocument();
      });

      // Check that debug data is displayed as JSON
      await waitFor(() => {
        expect(screen.getByText(/"prefill_tokens": 150/)).toBeInTheDocument();
        expect(screen.getByText(/"completion_tokens": 200/)).toBeInTheDocument();
      });
    });

    it('shows no data message when debug data is empty', async () => {
      mockLocalStorage.getItem.mockReturnValue('test-token');
      
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ logs: [], total_count: 0, page: 1, page_size: 50 }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({}),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ health_history: [] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ harmony_debug: [] }),
        });

      await act(async () => {
        render(<AdminPanel />);
      });

      // Switch to Debug tab
      await act(async () => {
        fireEvent.click(screen.getByText('🔧 Debug'));
      });

      await waitFor(() => {
        expect(screen.getByText('No Harmony debug data available')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('handles API errors gracefully', async () => {
      mockLocalStorage.getItem.mockReturnValue('test-token');
      
      mockFetch.mockRejectedValue(new Error('Network error'));

      await act(async () => {
        render(<AdminPanel />);
      });

      await waitFor(() => {
        expect(screen.getByText(/❌ Network error/)).toBeInTheDocument();
      });
    });

    it('handles 401 errors by logging out', async () => {
      mockLocalStorage.getItem.mockReturnValue('test-token');
      
      mockFetch.mockResolvedValue({
        ok: false,
        status: 401,
      });

      await act(async () => {
        render(<AdminPanel />);
      });

      await waitFor(() => {
        expect(screen.getByText('🔐 Admin Access')).toBeInTheDocument();
      });

      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('admin_token');
    });
  });

  describe('Refresh Functionality', () => {
    it('refreshes all data when refresh button is clicked', async () => {
      mockLocalStorage.getItem.mockReturnValue('test-token');
      
      // Mock initial data fetching calls
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ logs: [], total_count: 0, page: 1, page_size: 50 }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            total_interactions: 0,
            blocked_responses: 0,
            emergency_detections: 0,
            recent_activity_24h: 0,
            block_rate: 0,
            emergency_rate: 0,
            query_patterns: [],
            provider_usage: [],
            recent_system_health: {},
            performance_metrics: { endpoint_performance: [], status_code_distribution: [] },
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ health_history: [] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ harmony_debug: [] }),
        });

      await act(async () => {
        render(<AdminPanel />);
      });

      await waitFor(() => {
        expect(screen.getByText('🛡️ Admin Dashboard')).toBeInTheDocument();
      });

      // Clear previous calls and setup refresh calls
      mockFetch.mockClear();
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ logs: [], total_count: 0, page: 1, page_size: 50 }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            total_interactions: 0,
            blocked_responses: 0,
            emergency_detections: 0,
            recent_activity_24h: 0,
            block_rate: 0,
            emergency_rate: 0,
            query_patterns: [],
            provider_usage: [],
            recent_system_health: {},
            performance_metrics: { endpoint_performance: [], status_code_distribution: [] },
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ health_history: [] }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ harmony_debug: [] }),
        });
      
      // Click refresh button
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /refresh/i }));
      });

      await waitFor(() => {
        // Should make calls to all data endpoints
        expect(mockFetch).toHaveBeenCalledWith('/api/admin/audit', {
          headers: { Authorization: 'Bearer test-token' },
        });
        expect(mockFetch).toHaveBeenCalledWith('/api/admin/stats', {
          headers: { Authorization: 'Bearer test-token' },
        });
        expect(mockFetch).toHaveBeenCalledWith('/api/admin/health-history?hours=24', {
          headers: { Authorization: 'Bearer test-token' },
        });
        expect(mockFetch).toHaveBeenCalledWith('/api/admin/harmony-debug?limit=10', {
          headers: { Authorization: 'Bearer test-token' },
        });
      });
    });
  });

  describe('Logout Functionality', () => {
    it('logs out and clears data when logout button is clicked', async () => {
      mockLocalStorage.getItem.mockReturnValue('test-token');
      
      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({}),
      });

      await act(async () => {
        render(<AdminPanel />);
      });

      await waitFor(() => {
        expect(screen.getByText('🛡️ Admin Dashboard')).toBeInTheDocument();
      });

      // Click logout button
      await act(async () => {
        fireEvent.click(screen.getByText(/🚪 Logout/));
      });

      await waitFor(() => {
        expect(screen.getByText('🔐 Admin Access')).toBeInTheDocument();
      });

      expect(mockLocalStorage.removeItem).toHaveBeenCalledWith('admin_token');
    });
  });
});