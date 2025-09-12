# Installation Verification Guide

This guide helps verify that Campfire is properly installed and configured for the OpenAI Open Model Hackathon demonstration.

## Quick Verification Script

```bash
#!/bin/bash
# Save as verify_installation.sh and run: chmod +x verify_installation.sh && ./verify_installation.sh

echo "🔥 Campfire Installation Verification"
echo "===================================="

# Check Python version
echo "📋 Checking Python version..."
python3 --version
if [ $? -ne 0 ]; then
    echo "❌ Python 3.11+ required"
    exit 1
fi

# Check uv installation
echo "📋 Checking uv package manager..."
uv --version
if [ $? -ne 0 ]; then
    echo "❌ uv not installed. Install from: https://docs.astral.sh/uv/"
    exit 1
fi

# Check virtual environment
echo "📋 Checking virtual environment..."
if [ ! -d ".venv" ]; then
    echo "⚠️  Virtual environment not found. Running: uv venv"
    uv venv
fi

# Check dependencies
echo "📋 Checking dependencies..."
source .venv/bin/activate
uv sync --all-extras
if [ $? -ne 0 ]; then
    echo "❌ Dependency installation failed"
    exit 1
fi

# Check corpus files
echo "📋 Checking corpus files..."
if [ ! -f "corpus/raw/IFRC_First_Aid_Guidelines_2020.pdf" ]; then
    echo "⚠️  IFRC document missing. Running download script..."
    uv run python scripts/download_documents.py
fi

if [ ! -f "corpus/raw/WHO_Psychological_First_Aid_2011.pdf" ]; then
    echo "⚠️  WHO document missing. Running download script..."
    uv run python scripts/download_documents.py
fi

# Check processed corpus
echo "📋 Checking processed corpus..."
if [ ! -f "corpus/processed/corpus.db" ]; then
    echo "⚠️  Corpus database missing. Running ingestion..."
    uv run python scripts/ingest_corpus.py
fi

# Verify corpus integrity
echo "📋 Verifying corpus integrity..."
uv run python scripts/verify_corpus.py
if [ $? -ne 0 ]; then
    echo "❌ Corpus verification failed"
    exit 1
fi

# Check LLM backend
echo "📋 Checking LLM backend configuration..."
if command -v ollama &> /dev/null; then
    echo "✅ Ollama found"
    ollama list | grep -q "gpt-oss" && echo "✅ gpt-oss model available" || echo "⚠️  gpt-oss model not found. Run: ollama pull gpt-oss-20b"
else
    echo "⚠️  Ollama not found. Install from: https://ollama.ai/"
fi

# Test backend startup
echo "📋 Testing backend startup..."
timeout 10s uv run uvicorn campfire.api.main:app --host 127.0.0.1 --port 8001 &
BACKEND_PID=$!
sleep 5

# Test health endpoint
curl -s http://127.0.0.1:8001/health > /dev/null
if [ $? -eq 0 ]; then
    echo "✅ Backend health check passed"
else
    echo "❌ Backend health check failed"
fi

# Cleanup
kill $BACKEND_PID 2>/dev/null

# Test frontend build
echo "📋 Testing frontend build..."
cd frontend
if [ -f "package.json" ]; then
    npm install --silent
    npm run build --silent
    if [ $? -eq 0 ]; then
        echo "✅ Frontend build successful"
    else
        echo "❌ Frontend build failed"
    fi
else
    echo "⚠️  Frontend package.json not found"
fi
cd ..

echo ""
echo "🎯 Installation Verification Complete!"
echo "======================================"
echo ""
echo "✅ Ready for hackathon demo!"
echo "🚀 Start with: make run"
echo "🌐 Access at: http://localhost:8000"
echo "✈️  Test offline: Enable airplane mode first"
echo ""
```

## Manual Verification Steps

### 1. Environment Check
```bash
# Verify Python version (3.11+)
python3 --version

# Verify uv installation
uv --version

# Check virtual environment
ls -la .venv/
```

### 2. Dependencies Check
```bash
# Install all dependencies
uv sync --all-extras

# Verify key packages
uv pip list | grep -E "(fastapi|uvicorn|openai-harmony|vllm|ollama)"
```

### 3. Corpus Verification
```bash
# Check raw documents
ls -la corpus/raw/
file corpus/raw/*.pdf

# Check processed database
ls -la corpus/processed/
sqlite3 corpus/processed/corpus.db ".tables"

# Verify document count
sqlite3 corpus/processed/corpus.db "SELECT COUNT(*) FROM docs;"
sqlite3 corpus/processed/corpus.db "SELECT COUNT(*) FROM chunks;"
```

### 4. Backend Testing
```bash
# Start backend
uv run uvicorn campfire.api.main:app --reload --port 8000 &

# Test health endpoint
curl http://localhost:8000/health

# Test chat endpoint (basic)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "test query"}'

# Stop backend
pkill -f uvicorn
```

### 5. Frontend Testing
```bash
cd frontend

# Install dependencies
npm install

# Build for production
npm run build

# Test development server
npm start &
sleep 5
curl http://localhost:3000
pkill -f "react-scripts"

cd ..
```

### 6. Offline Mode Testing
```bash
# Enable airplane mode or disconnect internet
# Then run full system test

make run &
sleep 10

# Test offline functionality
curl http://localhost:8000/health
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "someone is choking"}'

# Verify no external network calls
# (Use network monitoring tools if available)
```

## Common Issues and Solutions

### uv Installation Issues
```bash
# Install uv via pip if curl method fails
pip install uv

# Or use homebrew on macOS
brew install uv
```

### Virtual Environment Problems
```bash
# Remove and recreate virtual environment
rm -rf .venv
uv venv
source .venv/bin/activate
uv sync --all-extras
```

### Corpus Download Failures
```bash
# Manual download if scripts fail
wget -O corpus/raw/IFRC_First_Aid_Guidelines_2020.pdf \
  "https://www.ifrc.org/sites/default/files/2021-04/IFRC-First-Aid-Guidelines-2020_0.pdf"

wget -O corpus/raw/WHO_Psychological_First_Aid_2011.pdf \
  "https://www.who.int/publications/i/item/9789241548205/download"
```

### LLM Backend Issues
```bash
# Ollama installation
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve &
ollama pull gpt-oss-20b

# vLLM installation (GPU required)
uv add "vllm>=0.2.0" --index https://download.pytorch.org/whl/cu121

# LM Studio (manual installation)
# Download from https://lmstudio.ai/
```

### Port Conflicts
```bash
# Check what's using port 8000
lsof -i :8000

# Use different port
export CAMPFIRE_PORT=8001
uv run uvicorn campfire.api.main:app --port $CAMPFIRE_PORT
```

## Pre-Demo Checklist

### System Ready
- [ ] All dependencies installed via uv
- [ ] Corpus documents downloaded and processed
- [ ] LLM backend configured and tested
- [ ] Frontend built successfully
- [ ] Health endpoints responding

### Offline Verification
- [ ] Internet disconnected/airplane mode enabled
- [ ] Backend starts without external connections
- [ ] Chat functionality works offline
- [ ] Citations display correctly
- [ ] Admin panel accessible

### Demo Scenarios Tested
- [ ] "Someone is choking" - returns Heimlich maneuver steps
- [ ] "Severe bleeding" - returns pressure/elevation guidance
- [ ] "Panic attack" - returns psychological first aid steps
- [ ] Citations link to correct document sections
- [ ] Emergency banners appear for critical situations

### Performance Verified
- [ ] Response time under 10 seconds
- [ ] Memory usage acceptable
- [ ] No error messages in logs
- [ ] UI responsive and functional

**Ready for OpenAI Open Model Hackathon demonstration! 🏆**