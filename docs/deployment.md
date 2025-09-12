# Campfire Emergency Helper - Deployment Guide

This guide covers deployment options for the Campfire Emergency Helper system, including Docker containerization, configuration management, and troubleshooting.

## Table of Contents

- [Quick Start](#quick-start)
- [Docker Deployment](#docker-deployment)
- [Manual Deployment](#manual-deployment)
- [Configuration](#configuration)
- [Health Monitoring](#health-monitoring)
- [Backup and Restore](#backup-and-restore)
- [Troubleshooting](#troubleshooting)
- [Security Considerations](#security-considerations)

## Quick Start

### Using Docker Compose (Recommended)

1. **Clone and prepare the repository:**
   ```bash
   git clone https://github.com/nima-ch/campfire.git
   cd campfire
   ```

2. **Start the services:**
   ```bash
   docker-compose up -d
   ```

3. **Access the application:**
   - Web interface: http://localhost:8000
   - Health check: http://localhost:8000/health
   - Admin panel: http://localhost:8000 (password: admin123)

### Using Docker Build

1. **Build the image:**
   ```bash
   make docker-build
   ```

2. **Run the container:**
   ```bash
   make docker-run
   ```

## Docker Deployment

### Building the Image

The Dockerfile uses a multi-stage build process:

```bash
# Build the Docker image
docker build -t campfire:latest .

# Or use the Makefile
make docker-build
```

### Running with Docker

#### Basic Run
```bash
docker run -p 8000:8000 campfire:latest
```

#### With Custom Configuration
```bash
docker run -p 8000:8000 \
  -e CAMPFIRE_LLM_PROVIDER=ollama \
  -e CAMPFIRE_ADMIN_PASSWORD=your_secure_password \
  -v ./corpus:/app/corpus \
  -v ./data:/app/data \
  campfire:latest
```

#### With Persistent Storage
```bash
docker run -p 8000:8000 \
  -v campfire_data:/app/data \
  -v campfire_corpus:/app/corpus \
  -v campfire_logs:/app/logs \
  campfire:latest
```

### Docker Compose Configuration

The `docker-compose.yml` file provides a complete deployment setup:

```yaml
version: '3.8'

services:
  campfire:
    build: .
    ports:
      - "8000:8000"
    environment:
      CAMPFIRE_LLM_PROVIDER: "ollama"
      CAMPFIRE_ADMIN_PASSWORD: "admin123"
    volumes:
      - campfire_data:/app/data
      - campfire_corpus:/app/corpus
    restart: unless-stopped
    
  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
```

#### Starting Services
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f campfire

# Stop services
docker-compose down
```

## Manual Deployment

### Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- uv package manager
- SQLite 3
- Git

### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/nima-ch/campfire.git
   cd campfire
   ```

2. **Install Python dependencies:**
   ```bash
   make dev-install
   ```

3. **Build the frontend:**
   ```bash
   make build-frontend
   ```

4. **Ingest corpus documents:**
   ```bash
   make ingest
   ```

5. **Validate configuration:**
   ```bash
   uv run python scripts/validate_config.py
   ```

6. **Start the server:**
   ```bash
   make run
   ```

### Production Setup

For production deployment, use a process manager like systemd:

1. **Create systemd service file:**
   ```bash
   sudo nano /etc/systemd/system/campfire.service
   ```

   ```ini
   [Unit]
   Description=Campfire Emergency Helper
   After=network.target

   [Service]
   Type=simple
   User=campfire
   WorkingDirectory=/opt/campfire
   Environment=CAMPFIRE_LLM_PROVIDER=ollama
   Environment=CAMPFIRE_CORPUS_DB=/opt/campfire/corpus/processed/corpus.db
   Environment=CAMPFIRE_AUDIT_DB=/opt/campfire/data/audit.db
   ExecStart=/opt/campfire/.venv/bin/uvicorn campfire.api.main:app --host 0.0.0.0 --port 8000 --app-dir backend/src
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

2. **Enable and start the service:**
   ```bash
   sudo systemctl enable campfire
   sudo systemctl start campfire
   sudo systemctl status campfire
   ```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CAMPFIRE_HOST` | `127.0.0.1` | Server bind address |
| `CAMPFIRE_PORT` | `8000` | Server port |
| `CAMPFIRE_DEBUG` | `false` | Enable debug mode |
| `CAMPFIRE_LLM_PROVIDER` | `ollama` | LLM provider (ollama, vllm, lmstudio) |
| `CAMPFIRE_CORPUS_DB` | `corpus/processed/corpus.db` | Corpus database path |
| `CAMPFIRE_AUDIT_DB` | `data/audit.db` | Audit database path |
| `CAMPFIRE_POLICY_PATH` | `policy.md` | Policy file path |
| `CAMPFIRE_ADMIN_PASSWORD` | - | Admin panel password |

### Configuration Validation

Run configuration validation before deployment:

```bash
# Basic validation
uv run python scripts/validate_config.py

# JSON output for automation
uv run python scripts/validate_config.py --json
```

### LLM Provider Configuration

#### Ollama (Default)
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull required model
ollama pull llama2:7b

# Set environment
export CAMPFIRE_LLM_PROVIDER=ollama
```

#### vLLM (High Performance)
```bash
# Install with uv
uv add vllm

# Set environment
export CAMPFIRE_LLM_PROVIDER=vllm
```

#### LM Studio
```bash
# Start LM Studio server
# Set environment
export CAMPFIRE_LLM_PROVIDER=lmstudio
```

## Health Monitoring

### Health Check Endpoint

The system provides a comprehensive health check at `/health`:

```bash
curl http://localhost:8000/health
```

Response format:
```json
{
  "status": "healthy",
  "timestamp": "2025-09-11T12:00:00Z",
  "version": "0.1.0",
  "components": {
    "llm_provider": "healthy",
    "corpus_db": "healthy (2 documents)",
    "browser_tool": "healthy",
    "safety_critic": "healthy"
  },
  "offline_mode": true
}
```

### Docker Health Checks

Docker containers include built-in health checks:

```bash
# Check container health
docker ps

# View health check logs
docker inspect --format='{{json .State.Health}}' campfire-container
```

### Monitoring Scripts

Use the provided monitoring scripts:

```bash
# System health check
uv run campfire check

# Performance monitoring
curl http://localhost:8000/admin/performance
```

## Backup and Restore

### Creating Backups

```bash
# Create full backup
uv run python scripts/backup_restore.py backup /path/to/backup.tar.gz

# Include log files
uv run python scripts/backup_restore.py backup /path/to/backup.tar.gz --include-logs

# Automated daily backup
0 2 * * * /opt/campfire/.venv/bin/python /opt/campfire/scripts/backup_restore.py backup /backups/campfire-$(date +\%Y\%m\%d).tar.gz
```

### Restoring from Backup

```bash
# List backup contents
uv run python scripts/backup_restore.py list /path/to/backup.tar.gz

# Verify backup integrity
uv run python scripts/backup_restore.py verify /path/to/backup.tar.gz

# Restore (with confirmation)
uv run python scripts/backup_restore.py restore /path/to/backup.tar.gz

# Force restore (no confirmation)
uv run python scripts/backup_restore.py restore /path/to/backup.tar.gz --force
```

### Backup Contents

Backups include:
- Corpus database (`corpus.db`)
- Audit database (`audit.db`)
- Policy configuration (`policy.md`)
- System configuration files
- Optional: Log files

## Troubleshooting

### Common Issues

#### 1. Corpus Database Not Found
```
Error: Corpus database not found at corpus/processed/corpus.db
```

**Solution:**
```bash
# Check if raw documents exist
ls corpus/raw/

# Run ingestion
make ingest

# Or mount existing database in Docker
docker run -v ./corpus.db:/app/corpus/processed/corpus.db campfire:latest
```

#### 2. LLM Provider Not Available
```
Error: LLM provider 'ollama' is not available
```

**Solution:**
```bash
# Check available providers
uv run campfire check

# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve

# Or switch provider
export CAMPFIRE_LLM_PROVIDER=lmstudio
```

#### 3. Permission Denied Errors
```
Error: No write permission for: /app/data
```

**Solution:**
```bash
# Fix permissions
sudo chown -R app:app /app/data

# Or in Docker
docker run --user $(id -u):$(id -g) campfire:latest
```

#### 4. Memory Issues
```
Error: CUDA out of memory
```

**Solution:**
```bash
# Reduce model size or switch provider
export CAMPFIRE_LLM_PROVIDER=ollama

# Or increase Docker memory limit
docker run --memory=8g campfire:latest
```

### Debug Mode

Enable debug mode for detailed logging:

```bash
# Environment variable
export CAMPFIRE_DEBUG=true

# Command line
uv run campfire serve --debug

# Docker
docker run -e CAMPFIRE_DEBUG=true campfire:latest
```

### Log Analysis

```bash
# View application logs
docker-compose logs -f campfire

# View system logs (systemd)
sudo journalctl -u campfire -f

# Check audit logs
curl -H "Authorization: Bearer <token>" http://localhost:8000/admin/audit
```

### Performance Tuning

#### Resource Limits
```yaml
# docker-compose.yml
deploy:
  resources:
    limits:
      memory: 8G
      cpus: '4'
    reservations:
      memory: 4G
      cpus: '2'
```

#### Database Optimization
```bash
# Rebuild FTS index
sqlite3 corpus/processed/corpus.db "INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild');"

# Vacuum database
sqlite3 corpus/processed/corpus.db "VACUUM;"
```

## Security Considerations

### Network Security

- **Offline Operation**: System operates without internet access
- **Local Binding**: Default binding to `127.0.0.1` for local access only
- **CORS Configuration**: Restricted to localhost origins

### Authentication

- **Admin Panel**: Password-protected admin interface
- **Token-based**: JWT tokens for admin API access
- **Session Management**: Secure session handling

### Data Protection

- **Local Processing**: All data remains on local system
- **No External Calls**: No data transmitted to external services
- **Audit Logging**: Complete audit trail of all interactions

### Container Security

```yaml
# docker-compose.yml security options
security_opt:
  - no-new-privileges:true
user: "1000:1000"
read_only: true
tmpfs:
  - /tmp
  - /var/tmp
```

### File Permissions

```bash
# Secure file permissions
chmod 600 policy.md
chmod 700 data/
chmod 644 corpus/processed/corpus.db
```

## Production Checklist

- [ ] Change default admin password
- [ ] Configure proper file permissions
- [ ] Set up automated backups
- [ ] Configure log rotation
- [ ] Enable health monitoring
- [ ] Test offline operation
- [ ] Verify corpus integrity
- [ ] Configure resource limits
- [ ] Set up process monitoring
- [ ] Test disaster recovery

## Support

For additional support:

1. Check the [troubleshooting section](#troubleshooting)
2. Review application logs
3. Run configuration validation
4. Check system health endpoint
5. Consult the project documentation

## Version History

- **v0.1.0**: Initial deployment support
  - Docker containerization
  - Configuration validation
  - Backup and restore functionality
  - Health monitoring
  - Deployment documentation