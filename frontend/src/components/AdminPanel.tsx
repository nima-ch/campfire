import React, { useState, useEffect } from 'react';
import './AdminPanel.css';
import { AuditLog, AdminAuth, AdminStats, SystemHealth, HarmonyDebugData } from '../types';

const AdminPanel: React.FC = () => {
  const [auth, setAuth] = useState<AdminAuth>({ isAuthenticated: false });
  const [password, setPassword] = useState('');
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [systemHealth, setSystemHealth] = useState<SystemHealth[]>([]);
  const [harmonyDebug, setHarmonyDebug] = useState<HarmonyDebugData[]>([]);
  const [activeTab, setActiveTab] = useState<'logs' | 'stats' | 'health' | 'debug'>('logs');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);

  useEffect(() => {
    // Check if already authenticated
    const token = localStorage.getItem('admin_token');
    if (token) {
      setAuth({ isAuthenticated: true, token });
      fetchAllData(token);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);
    setLoading(true);

    try {
      const response = await fetch('/api/admin/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ password }),
      });

      if (!response.ok) {
        throw new Error('Invalid password');
      }

      const data = await response.json();
      const token = data.access_token;
      
      localStorage.setItem('admin_token', token);
      setAuth({ isAuthenticated: true, token });
      setPassword('');
      
      await fetchAllData(token);
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const fetchAuditLogs = async (token: string) => {
    try {
      const response = await fetch('/api/admin/audit', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          handleLogout();
          return;
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setAuditLogs(data.logs || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch audit logs');
    }
  };

  const fetchStats = async (token: string) => {
    try {
      const response = await fetch('/api/admin/stats', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setStats(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch stats');
    }
  };

  const fetchSystemHealth = async (token: string) => {
    try {
      const response = await fetch('/api/admin/health-history?hours=24', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setSystemHealth(data.health_history || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch system health');
    }
  };

  const fetchHarmonyDebug = async (token: string) => {
    try {
      const response = await fetch('/api/admin/harmony-debug?limit=10', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setHarmonyDebug(data.harmony_debug || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch Harmony debug data');
    }
  };

  const fetchAllData = async (token: string) => {
    setLoading(true);
    setError(null);

    try {
      await Promise.all([
        fetchAuditLogs(token),
        fetchStats(token),
        fetchSystemHealth(token),
        fetchHarmonyDebug(token)
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('admin_token');
    setAuth({ isAuthenticated: false });
    setAuditLogs([]);
    setStats(null);
    setSystemHealth([]);
    setHarmonyDebug([]);
    setError(null);
  };

  const handleRefresh = () => {
    if (auth.token) {
      fetchAllData(auth.token);
    }
  };

  if (!auth.isAuthenticated) {
    return (
      <div className="admin-panel">
        <div className="admin-login">
          <div className="login-card">
            <h2 className="login-title">🔐 Admin Access</h2>
            <p className="login-description">
              Enter the admin password to view audit logs and safety critic decisions.
            </p>
            
            <form onSubmit={handleLogin} className="login-form">
              <div className="input-group">
                <label htmlFor="password">Password</label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter admin password"
                  className="password-input"
                  disabled={loading}
                  required
                />
              </div>
              
              {loginError && (
                <div className="login-error">
                  ❌ {loginError}
                </div>
              )}
              
              <button
                type="submit"
                className="login-button"
                disabled={!password || loading}
              >
                {loading ? 'Authenticating...' : 'Login'}
              </button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  const renderTabContent = () => {
    switch (activeTab) {
      case 'logs':
        return (
          <div className="audit-logs">
            {auditLogs.length === 0 ? (
              <div className="no-logs">
                <p>No audit logs available.</p>
                <p>Logs will appear here as users interact with the system.</p>
              </div>
            ) : (
              <div className="logs-list">
                {auditLogs.map((log) => (
                  <div key={log.id} className={`log-entry ${log.response_blocked ? 'blocked' : 'allowed'}`}>
                    <div className="log-header">
                      <div className="log-timestamp">
                        {new Date(log.timestamp).toLocaleString()}
                      </div>
                      <div className={`log-decision ${log.response_blocked ? 'blocked' : 'allowed'}`}>
                        {log.response_blocked ? '🚫 BLOCKED' : '✅ ALLOWED'}
                      </div>
                      {log.response_time_ms && (
                        <div className="log-timing">
                          ⏱️ {log.response_time_ms}ms
                        </div>
                      )}
                    </div>
                    
                    <div className="log-content">
                      <div className="log-query">
                        <strong>Query:</strong> {log.query}
                      </div>
                      
                      {log.critic_decision.reasons.length > 0 && (
                        <div className="log-reasons">
                          <strong>Critic Reasons:</strong>
                          <ul>
                            {log.critic_decision.reasons.map((reason, index) => (
                              <li key={index}>{reason}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      
                      {log.emergency_detected && (
                        <div className="log-emergency">
                          <strong>⚠️ Emergency Keywords Detected</strong>
                        </div>
                      )}
                      
                      <div className="log-metadata">
                        {log.llm_provider && <span>Provider: {log.llm_provider}</span>}
                        {log.harmony_tokens_used && <span>Tokens: {log.harmony_tokens_used}</span>}
                        {log.conversation_id && <span>Conv: {log.conversation_id.slice(0, 8)}</span>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        );

      case 'stats':
        return (
          <div className="admin-stats">
            {stats ? (
              <>
                <div className="stats-overview">
                  <div className="stat-card">
                    <h3>Total Interactions</h3>
                    <div className="stat-value">{stats.total_interactions}</div>
                  </div>
                  <div className="stat-card">
                    <h3>Blocked Responses</h3>
                    <div className="stat-value">{stats.blocked_responses}</div>
                    <div className="stat-detail">{(stats.block_rate * 100).toFixed(1)}% block rate</div>
                  </div>
                  <div className="stat-card">
                    <h3>Emergency Detections</h3>
                    <div className="stat-value">{stats.emergency_detections}</div>
                    <div className="stat-detail">{(stats.emergency_rate * 100).toFixed(1)}% emergency rate</div>
                  </div>
                  <div className="stat-card">
                    <h3>Recent Activity (24h)</h3>
                    <div className="stat-value">{stats.recent_activity_24h}</div>
                  </div>
                </div>

                {stats.provider_usage && stats.provider_usage.length > 0 && (
                  <div className="provider-stats">
                    <h3>LLM Provider Usage</h3>
                    {stats.provider_usage.map((provider, index) => (
                      <div key={index} className="provider-item">
                        <span>{provider.llm_provider}</span>
                        <span>{provider.usage_count} requests</span>
                        <span>{provider.avg_response_time.toFixed(0)}ms avg</span>
                      </div>
                    ))}
                  </div>
                )}

                {stats.performance_metrics && stats.performance_metrics.endpoint_performance && stats.performance_metrics.endpoint_performance.length > 0 && (
                  <div className="performance-stats">
                    <h3>Endpoint Performance</h3>
                    {stats.performance_metrics.endpoint_performance.map((endpoint, index) => (
                      <div key={index} className="endpoint-item">
                        <span>{endpoint.endpoint}</span>
                        <span>{endpoint.request_count} requests</span>
                        <span>{endpoint.avg_response_time.toFixed(0)}ms avg</span>
                        <span>{endpoint.min_response_time}-{endpoint.max_response_time}ms range</span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <div className="loading">Loading stats...</div>
            )}
          </div>
        );

      case 'health':
        return (
          <div className="system-health">
            {systemHealth.length > 0 ? (
              <>
                <div className="health-overview">
                  <h3>System Health (Last 24 hours)</h3>
                  <div className="health-metrics">
                    {systemHealth.slice(0, 1).map((health, index) => (
                      <div key={index} className="health-current">
                        <div className="metric">
                          <span>CPU:</span>
                          <span>{health.cpu_percent?.toFixed(1)}%</span>
                        </div>
                        <div className="metric">
                          <span>Memory:</span>
                          <span>{health.memory_percent?.toFixed(1)}%</span>
                        </div>
                        <div className="metric">
                          <span>Disk:</span>
                          <span>{health.disk_usage_percent?.toFixed(1)}%</span>
                        </div>
                        <div className="metric">
                          <span>LLM:</span>
                          <span className={`status ${health.llm_provider_status}`}>
                            {health.llm_provider_status}
                          </span>
                        </div>
                        <div className="metric">
                          <span>DB:</span>
                          <span className={`status ${health.corpus_db_status}`}>
                            {health.corpus_db_status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                
                <div className="health-history">
                  <h4>Recent Health History</h4>
                  <div className="health-list">
                    {systemHealth.slice(0, 10).map((health, index) => (
                      <div key={index} className="health-entry">
                        <span>{new Date(health.timestamp).toLocaleString()}</span>
                        <span>CPU: {health.cpu_percent?.toFixed(1)}%</span>
                        <span>Mem: {health.memory_percent?.toFixed(1)}%</span>
                        <span>Disk: {health.disk_usage_percent?.toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            ) : (
              <div className="no-data">No health data available</div>
            )}
          </div>
        );

      case 'debug':
        return (
          <div className="harmony-debug">
            {harmonyDebug.length > 0 ? (
              <>
                <div className="debug-overview">
                  <h3>Harmony Debug Data</h3>
                  <p>Recent Harmony engine interactions with token details</p>
                </div>
                
                <div className="debug-list">
                  {harmonyDebug.map((debug, index) => (
                    <div key={index} className="debug-entry">
                      <div className="debug-header">
                        <span>{new Date(debug.timestamp).toLocaleString()}</span>
                        {debug.harmony_tokens_used && (
                          <span>Tokens: {debug.harmony_tokens_used}</span>
                        )}
                      </div>
                      <div className="debug-query">
                        <strong>Query:</strong> {debug.query}
                      </div>
                      <div className="debug-data">
                        <strong>Debug Data:</strong>
                        <pre>{JSON.stringify(debug.harmony_debug_data, null, 2)}</pre>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="no-data">No Harmony debug data available</div>
            )}
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="admin-panel">
      <div className="admin-header">
        <div className="admin-title">
          <h2>🛡️ Admin Dashboard</h2>
          <p>System Monitoring & Audit Logs</p>
        </div>
        <div className="admin-actions">
          <button className="refresh-button" onClick={handleRefresh} disabled={loading}>
            {loading ? '⏳' : '🔄'} Refresh
          </button>
          <button className="logout-button" onClick={handleLogout}>
            🚪 Logout
          </button>
        </div>
      </div>

      {error && (
        <div className="admin-error">
          ❌ {error}
        </div>
      )}

      <div className="admin-tabs">
        <button 
          className={`tab ${activeTab === 'logs' ? 'active' : ''}`}
          onClick={() => setActiveTab('logs')}
        >
          📋 Audit Logs
        </button>
        <button 
          className={`tab ${activeTab === 'stats' ? 'active' : ''}`}
          onClick={() => setActiveTab('stats')}
        >
          📊 Statistics
        </button>
        <button 
          className={`tab ${activeTab === 'health' ? 'active' : ''}`}
          onClick={() => setActiveTab('health')}
        >
          💚 System Health
        </button>
        <button 
          className={`tab ${activeTab === 'debug' ? 'active' : ''}`}
          onClick={() => setActiveTab('debug')}
        >
          🔧 Debug
        </button>
      </div>

      <div className="admin-content">
        {renderTabContent()}
      </div>
    </div>
  );
};

export default AdminPanel;