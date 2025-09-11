import React, { useState, useEffect } from 'react';
import './AdminPanel.css';
import { AuditLog, AdminAuth } from '../types';

const AdminPanel: React.FC = () => {
  const [auth, setAuth] = useState<AdminAuth>({ isAuthenticated: false });
  const [password, setPassword] = useState('');
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);

  useEffect(() => {
    // Check if already authenticated
    const token = localStorage.getItem('admin_token');
    if (token) {
      setAuth({ isAuthenticated: true, token });
      fetchAuditLogs(token);
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
      const token = data.token;
      
      localStorage.setItem('admin_token', token);
      setAuth({ isAuthenticated: true, token });
      setPassword('');
      
      await fetchAuditLogs(token);
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const fetchAuditLogs = async (token: string) => {
    setLoading(true);
    setError(null);

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
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('admin_token');
    setAuth({ isAuthenticated: false });
    setAuditLogs([]);
    setError(null);
  };

  const handleRefresh = () => {
    if (auth.token) {
      fetchAuditLogs(auth.token);
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

  return (
    <div className="admin-panel">
      <div className="admin-header">
        <div className="admin-title">
          <h2>🛡️ Admin Dashboard</h2>
          <p>Safety Critic Audit Logs</p>
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

      <div className="audit-logs">
        {auditLogs.length === 0 ? (
          <div className="no-logs">
            <p>No audit logs available.</p>
            <p>Logs will appear here as users interact with the system.</p>
          </div>
        ) : (
          <div className="logs-list">
            {auditLogs.map((log) => (
              <div key={log.id} className={`log-entry ${log.critic_decision.toLowerCase()}`}>
                <div className="log-header">
                  <div className="log-timestamp">
                    {new Date(log.timestamp).toLocaleString()}
                  </div>
                  <div className={`log-decision ${log.critic_decision.toLowerCase()}`}>
                    {log.critic_decision === 'ALLOW' ? '✅' : '🚫'} {log.critic_decision}
                  </div>
                </div>
                
                <div className="log-content">
                  <div className="log-query">
                    <strong>Query:</strong> {log.query}
                  </div>
                  
                  {log.critic_reasons.length > 0 && (
                    <div className="log-reasons">
                      <strong>Critic Reasons:</strong>
                      <ul>
                        {log.critic_reasons.map((reason, index) => (
                          <li key={index}>{reason}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  {log.blocked_content && (
                    <div className="log-blocked">
                      <strong>Blocked Content:</strong>
                      <pre>{log.blocked_content}</pre>
                    </div>
                  )}
                  
                  {log.response && (
                    <div className="log-response">
                      <strong>Response Steps:</strong> {log.response.checklist.length}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default AdminPanel;