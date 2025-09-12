# Campfire Emergency Helper - Troubleshooting Guide

This guide helps diagnose and resolve common issues with the Campfire Emergency Helper system.

## Table of Contents

- [Quick Diagnostics](#quick-diagnostics)
- [Common Issues](#common-issues)
- [System Health](#system-health)
- [Performance Issues](#performance-issues)
- [Configuration Problems](#configuration-problems)
- [Docker Issues](#docker-issues)
- [LLM Provider Issues](#llm-provider-issues)
- [Database Issues](#database-issues)
- [Network and Connectivity](#network-and-connectivity)
- [Debug Mode](#debug-mode)
- [Log Analysis](#log-analysis)
- [Recovery Procedures](#recovery-procedures)

## Quick Diagnostics

### System Health Check

Run the built-in health check to quickly identify issues:

```bash
# Command line health check
uv run campfire check

# HTTP health endpoint
curl http://localhost:8000/health

# Configuration validation
uv run python scripts/validate_config.py
```

### Docker Health Check

```bash
# Check container status
docker ps

# View container health
docker inspect --format='{{json .State.Health}}' campfire-container

# Check logs
docker logs campfire-container --tail 50
```

## Common Issues

### 1. Server Won't Start

#### Symptoms
- Server fails to start
- Port binding errors
- Import errors

#### Diagnosis
```bash
# Check if port is in use
netstat -tlnp | grep 8000
lsof -i :8000

# Check Python path and imports
uv run python -c "import campfire; print('OK')"

# Validate configuration
uv run python scripts/validate_config.py
```

#### Solutions
```bash
# Kill process using port
sudo kill -9 $(lsof -t -i:8000)

# Use different port
export CAMPFIRE_PORT=8001
uv run campfire serve --port 8001

# Fix Python path
export PYTHONPATH="/app/backend/src:$PYTHONPATH"

# Reinstall dependencies
uv sync --reinstall
```

### 2. Corpus Database Issues

#### Symptoms
- "Corpus database not found" error
- Empty search results
- Database corruption errors

#### Diagnosis
```bash
# Check if database exists
ls -la corpus/processed/corpus.db

# Check database integrity
sqlite3 corpus/processed/corpus.db "PRAGMA integrity_check;"

# Check document count
sqlite3 corpus/processed/corpus.db "SELECT COUNT(*) FROM docs;"

# Test search functionality
uv run python -c "
from campfire.corpus.database import CorpusDatabase
db = CorpusDatabase('corpus/processed/corpus.db')
print(f'Documents: {len(db.list_documents())}')
print(f'Search test: {len(db.search(\"emergency\", limit=1))}')
db.close()
"
```

#### Solutions
```bash
# Rebuild corpus database
rm -f corpus/processed/corpus.db
make ingest

# Repair database
sqlite3 corpus/processed/corpus.db "VACUUM;"

# Rebuild FTS index
sqlite3 corpus/processed/corpus.db "INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild');"

# Restore from backup
uv run python scripts/backup_restore.py restore backup.tar.gz
```

### 3. LLM Provider Not Available

#### Symptoms
- "LLM provider not available" error
- Model loading failures
- Connection timeouts

#### Diagnosis
```bash
# Check available providers
uv run python -c "
from campfire.llm.factory import get_available_providers
print(get_available_providers())
"

# Test Ollama connection
curl http://localhost:11434/api/tags

# Check vLLM installation
uv run python -c "import vllm; print('vLLM available')"

# Check LM Studio connection
curl http://localhost:1234/v1/models
```

#### Solutions

**For Ollama:**
```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve

# Pull required model
ollama pull llama2:7b

# Test model
ollama run llama2:7b "Hello"
```

**For vLLM:**
```bash
# Install vLLM with uv
uv add vllm torch

# Test installation
uv run python -c "import vllm; print('vLLM installed')"
```

**For LM Studio:**
```bash
# Start LM Studio server
# Load a model in LM Studio
# Test connection
curl http://localhost:1234/v1/models
```

### 4. Safety Critic Blocking Everything

#### Symptoms
- All responses are blocked
- "Response blocked for safety reasons" messages
- Empty checklist responses

#### Diagnosis
```bash
# Check policy file
cat policy.md

# Test safety critic
uv run python -c "
from campfire.critic.critic import SafetyCritic
critic = SafetyCritic('policy.md')
test_response = {'checklist': [{'title': 'Test', 'action': 'Test action', 'source': {'doc_id': 'test', 'loc': [0, 100]}}]}
decision = critic.review_response(test_response)
print(f'Decision: {decision.status.value}')
print(f'Reasons: {decision.reasons}')
"

# Check admin logs
curl -H "Authorization: Bearer <token>" http://localhost:8000/admin/audit?blocked_only=true
```

#### Solutions
```bash
# Check policy configuration
nano policy.md

# Disable strict citation checking temporarily
export CAMPFIRE_POLICY_PATH=""

# Review blocked responses in admin panel
# Access http://localhost:8000/admin

# Reset policy to defaults
cp policy.md policy.md.backup
# Edit policy.md to be less restrictive
```

### 5. Frontend Not Loading

#### Symptoms
- Blank page or loading errors
- 404 errors for static files
- CORS errors

#### Diagnosis
```bash
# Check if frontend is built
ls -la frontend/build/

# Check server logs for CORS errors
docker logs campfire-container | grep CORS

# Test API directly
curl http://localhost:8000/health
```

#### Solutions
```bash
# Rebuild frontend
cd frontend
npm install
npm run build

# Check CORS configuration in main.py
# Ensure frontend URL is in allowed origins

# Serve frontend separately for development
cd frontend
npm start
```

## System Health

### Memory Issues

#### Symptoms
- Out of memory errors
- Slow response times
- Container restarts

#### Diagnosis
```bash
# Check memory usage
free -h
docker stats

# Check process memory
ps aux | grep campfire | head -5

# Monitor memory during operation
watch -n 1 'free -h && echo "---" && docker stats --no-stream'
```

#### Solutions
```bash
# Increase Docker memory limit
docker run --memory=8g campfire:latest

# Use smaller model
export CAMPFIRE_LLM_PROVIDER=ollama
ollama pull llama2:7b  # Instead of larger models

# Optimize Python memory
export PYTHONMALLOC=malloc
export MALLOC_TRIM_THRESHOLD_=100000
```

### CPU Performance

#### Symptoms
- High CPU usage
- Slow response times
- Timeouts

#### Diagnosis
```bash
# Check CPU usage
top -p $(pgrep -f campfire)
htop

# Monitor during requests
curl -w "@curl-format.txt" http://localhost:8000/health
```

#### Solutions
```bash
# Limit CPU usage
docker run --cpus="2.0" campfire:latest

# Use CPU-optimized model
export CAMPFIRE_LLM_PROVIDER=ollama

# Optimize uvicorn workers
uv run uvicorn campfire.api.main:app --workers 2
```

## Configuration Problems

### Environment Variables

#### Common Issues
```bash
# Check all environment variables
env | grep CAMPFIRE

# Validate required variables
uv run python scripts/validate_config.py

# Test configuration loading
uv run python -c "
import os
print('Corpus DB:', os.getenv('CAMPFIRE_CORPUS_DB', 'NOT SET'))
print('LLM Provider:', os.getenv('CAMPFIRE_LLM_PROVIDER', 'NOT SET'))
"
```

### File Permissions

#### Diagnosis
```bash
# Check file permissions
ls -la corpus/processed/corpus.db
ls -la data/
ls -la policy.md

# Test write permissions
touch data/test_write && rm data/test_write
```

#### Solutions
```bash
# Fix permissions
chmod 644 corpus/processed/corpus.db
chmod 755 data/
chmod 644 policy.md

# Fix ownership
chown -R app:app /app/data
chown -R app:app /app/corpus
```

## Docker Issues

### Container Won't Start

#### Diagnosis
```bash
# Check Docker logs
docker logs campfire-container

# Check container status
docker ps -a

# Inspect container configuration
docker inspect campfire-container
```

#### Solutions
```bash
# Rebuild image
docker build --no-cache -t campfire:latest .

# Check Dockerfile syntax
docker build --dry-run -t campfire:latest .

# Run with different user
docker run --user root campfire:latest

# Mount debug volume
docker run -v $(pwd):/debug campfire:latest
```

### Volume Mount Issues

#### Diagnosis
```bash
# Check volume mounts
docker inspect campfire-container | grep Mounts -A 20

# Test volume access
docker exec campfire-container ls -la /app/data
docker exec campfire-container touch /app/data/test
```

#### Solutions
```bash
# Fix volume permissions
sudo chown -R 1000:1000 ./data
sudo chmod -R 755 ./data

# Use bind mounts instead of volumes
docker run -v $(pwd)/data:/app/data campfire:latest
```

## LLM Provider Issues

### Ollama Connection Problems

#### Diagnosis
```bash
# Check Ollama service
systemctl status ollama
curl http://localhost:11434/api/tags

# Check model availability
ollama list

# Test model inference
ollama run llama2:7b "Test prompt"
```

#### Solutions
```bash
# Restart Ollama
sudo systemctl restart ollama

# Pull model again
ollama pull llama2:7b

# Check Ollama logs
journalctl -u ollama -f
```

### vLLM Issues

#### Diagnosis
```bash
# Check vLLM installation
uv run python -c "import vllm; print(vllm.__version__)"

# Check CUDA availability
uv run python -c "import torch; print(torch.cuda.is_available())"

# Test vLLM server
uv run python -m vllm.entrypoints.api_server --model llama2-7b
```

#### Solutions
```bash
# Reinstall vLLM
uv remove vllm
uv add vllm

# Use CPU-only mode
export CUDA_VISIBLE_DEVICES=""

# Reduce model size
# Use smaller model or quantized version
```

## Database Issues

### SQLite Corruption

#### Diagnosis
```bash
# Check database integrity
sqlite3 corpus/processed/corpus.db "PRAGMA integrity_check;"

# Check FTS index
sqlite3 corpus/processed/corpus.db "INSERT INTO chunks_fts(chunks_fts) VALUES('integrity-check');"

# Dump database schema
sqlite3 corpus/processed/corpus.db ".schema"
```

#### Solutions
```bash
# Repair database
sqlite3 corpus/processed/corpus.db "VACUUM;"

# Rebuild FTS index
sqlite3 corpus/processed/corpus.db "DROP TABLE chunks_fts;"
sqlite3 corpus/processed/corpus.db "CREATE VIRTUAL TABLE chunks_fts USING fts5(text, content='chunks', content_rowid='rowid');"
sqlite3 corpus/processed/corpus.db "INSERT INTO chunks_fts(rowid, text) SELECT rowid, text FROM chunks;"

# Restore from backup
uv run python scripts/backup_restore.py restore backup.tar.gz
```

### Audit Database Issues

#### Diagnosis
```bash
# Check audit database
sqlite3 data/audit.db ".tables"
sqlite3 data/audit.db "SELECT COUNT(*) FROM interactions;"

# Test audit logging
curl -X POST http://localhost:8000/chat -d '{"query": "test"}' -H "Content-Type: application/json"
sqlite3 data/audit.db "SELECT * FROM interactions ORDER BY timestamp DESC LIMIT 1;"
```

#### Solutions
```bash
# Recreate audit database
rm data/audit.db
# Restart server to recreate

# Fix permissions
chmod 644 data/audit.db
chown app:app data/audit.db
```

## Network and Connectivity

### Offline Mode Verification

#### Test Complete Offline Operation
```bash
# Disconnect network
sudo ip route del default

# Test system functionality
curl http://localhost:8000/health
curl -X POST http://localhost:8000/chat -d '{"query": "emergency"}' -H "Content-Type: application/json"

# Reconnect network
sudo dhclient
```

### Port Conflicts

#### Diagnosis
```bash
# Check port usage
netstat -tlnp | grep 8000
lsof -i :8000

# Test port availability
nc -zv localhost 8000
```

#### Solutions
```bash
# Kill conflicting process
sudo kill -9 $(lsof -t -i:8000)

# Use different port
export CAMPFIRE_PORT=8001
docker run -p 8001:8001 -e CAMPFIRE_PORT=8001 campfire:latest
```

## Debug Mode

### Enable Debug Logging

```bash
# Environment variable
export CAMPFIRE_DEBUG=true

# Command line
uv run campfire serve --debug

# Docker
docker run -e CAMPFIRE_DEBUG=true campfire:latest
```

### Debug Output Analysis

```bash
# View debug logs
docker logs campfire-container | grep DEBUG

# Filter specific components
docker logs campfire-container | grep "harmony\|critic\|browser"

# Monitor real-time
docker logs -f campfire-container
```

## Log Analysis

### Application Logs

```bash
# View recent logs
tail -f logs/campfire.log

# Search for errors
grep -i error logs/campfire.log

# Filter by component
grep "SafetyCritic" logs/campfire.log
```

### System Logs

```bash
# Docker logs
docker logs campfire-container --since 1h

# System service logs
sudo journalctl -u campfire -f

# Container resource usage
docker stats campfire-container
```

### Audit Logs

```bash
# Recent interactions
sqlite3 data/audit.db "SELECT timestamp, query, response_blocked FROM interactions ORDER BY timestamp DESC LIMIT 10;"

# Blocked responses
sqlite3 data/audit.db "SELECT timestamp, query, critic_decision FROM interactions WHERE response_blocked = 1;"

# Performance metrics
sqlite3 data/audit.db "SELECT AVG(response_time_ms), MAX(response_time_ms) FROM interactions WHERE timestamp > datetime('now', '-1 hour');"
```

## Recovery Procedures

### Complete System Reset

```bash
# Stop services
docker-compose down

# Remove all data (CAUTION: This deletes everything)
docker volume rm campfire_data campfire_corpus campfire_logs

# Rebuild and restart
docker-compose build --no-cache
docker-compose up -d

# Re-ingest corpus
docker-compose exec campfire make ingest
```

### Partial Recovery

```bash
# Reset only audit database
rm data/audit.db
docker-compose restart campfire

# Reset only corpus (keep audit logs)
rm corpus/processed/corpus.db
docker-compose exec campfire make ingest

# Reset configuration
cp policy.md.backup policy.md
docker-compose restart campfire
```

### Backup Recovery

```bash
# List available backups
ls -la backups/

# Verify backup integrity
uv run python scripts/backup_restore.py verify backups/latest.tar.gz

# Restore from backup
uv run python scripts/backup_restore.py restore backups/latest.tar.gz

# Restart services
docker-compose restart campfire
```

## Getting Help

### Diagnostic Information Collection

When reporting issues, collect this information:

```bash
# System information
uname -a
docker --version
python --version

# Configuration validation
uv run python scripts/validate_config.py --json > diagnostic.json

# Health check
curl http://localhost:8000/health > health.json

# Recent logs
docker logs campfire-container --tail 100 > logs.txt

# Resource usage
docker stats --no-stream > stats.txt
```

### Support Checklist

Before seeking help:

- [ ] Run configuration validation
- [ ] Check system health endpoint
- [ ] Review application logs
- [ ] Test in debug mode
- [ ] Verify offline operation
- [ ] Check resource usage
- [ ] Try basic recovery procedures

### Emergency Procedures

If the system is completely broken:

1. **Stop all services:**
   ```bash
   docker-compose down
   ```

2. **Backup current state:**
   ```bash
   tar -czf emergency-backup-$(date +%Y%m%d).tar.gz data/ corpus/ logs/
   ```

3. **Reset to known good state:**
   ```bash
   git checkout main
   docker-compose build --no-cache
   docker-compose up -d
   ```

4. **Restore data if needed:**
   ```bash
   uv run python scripts/backup_restore.py restore latest-backup.tar.gz
   ```

Remember: The system is designed for emergency situations, so having a recovery plan is critical!