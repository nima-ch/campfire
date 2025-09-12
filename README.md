# Campfire Emergency Helper

An offline-first emergency helper application built for the OpenAI Open Model Hackathon, demonstrating gpt-oss capabilities with Harmony tools in a safety-critical, offline environment.

## 🎯 Hackathon Categories

### Primary: Best Local Agent
Campfire demonstrates advanced local agent capabilities through:
- **Harmony Tool Integration**: Uses gpt-oss with openai-harmony for structured tool calling
- **Multi-Modal Tool Loops**: Implements search → open → find sequences for precise citation retrieval
- **Local Document Reasoning**: Performs complex multi-hop reasoning over offline document corpus
- **Safety-Critical Decision Making**: Includes Safety Critic component for response validation
- **Offline-First Architecture**: Complete functionality without any internet connectivity

### Secondary: For Humanity
Addresses critical humanitarian needs:
- **Emergency Accessibility**: Provides life-saving guidance when internet is unavailable
- **Authoritative Sources**: Based on IFRC and WHO emergency response guidelines
- **Safety Safeguards**: Built-in escalation for life-threatening situations
- **Educational Impact**: Promotes emergency preparedness and first-aid knowledge
- **Universal Access**: Works on standard hardware without cloud dependencies

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- Git
- 16GB+ RAM (32GB recommended)
- GPU with 8GB+ VRAM (optional but recommended for vLLM)

### One-Command Setup

```bash
git clone https://github.com/nima-ch/campfire.git
cd campfire
make setup && make ingest && make run
```

The application will be available at `http://localhost:8000`

### Backend Options

Campfire supports multiple local LLM backends. Choose based on your hardware:

#### Option 1: vLLM (Recommended - Full Harmony Support)
```bash
# Requires GPU with 8GB+ VRAM
uv add vllm --index https://download.pytorch.org/whl/cu121  # CUDA 12.1
# or
uv add vllm --index https://download.pytorch.org/whl/cu118  # CUDA 11.8

# Configure for vLLM
export CAMPFIRE_LLM_PROVIDER=vllm
make run
```

#### Option 2: Ollama (Default - CPU/GPU Compatible)
```bash
# Install Ollama separately: https://ollama.ai/
ollama pull gpt-oss-20b  # or your preferred gpt-oss model

# Configure for Ollama (default)
export CAMPFIRE_LLM_PROVIDER=ollama
make run
```

#### Option 3: LM Studio (Alternative)
```bash
# Install LM Studio: https://lmstudio.ai/
# Load gpt-oss model in LM Studio and start local server

# Configure for LM Studio
export CAMPFIRE_LLM_PROVIDER=lmstudio
export LMSTUDIO_BASE_URL=http://localhost:1234/v1
make run
```

## 🏗️ Architecture

### Offline-First Design
- **No Internet Required**: Works completely offline (airplane mode)
- **Local Models**: Uses gpt-oss-20b via vLLM, Ollama, or LM Studio
- **Local Corpus**: IFRC 2020 Guidelines + WHO PFA 2011 only
- **Citations Required**: Every response includes source attribution

### Safety-Critical Features
- **Medical Disclaimer**: Always shows "Not medical advice" warnings
- **Emergency Escalation**: Detects critical keywords and shows "Call emergency services" banners
- **Safety Critic**: Gates all responses through citation and scope validation
- **Audit Trail**: Admin interface logs all safety decisions

## 📁 Project Structure

```
campfire/
├── backend/           # FastAPI backend
│   ├── src/campfire/  # Main application code
│   └── tests/         # Backend tests
├── frontend/          # React frontend
│   ├── src/           # Frontend source
│   └── public/        # Static assets
├── corpus/            # Document corpus
│   ├── raw/           # Original documents
│   └── processed/     # Processed for search
├── scripts/           # Utility scripts
├── .kiro/            # Kiro IDE configuration
└── docs/             # Documentation
```

## 🛠️ Development

### Detailed Installation Steps

#### 1. Environment Setup
```bash
# Clone repository
git clone https://github.com/nima-ch/campfire.git
cd campfire

# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh
# or: pip install uv

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\activate  # Windows

# Install all dependencies including optional backends
uv sync --all-extras
```

#### 2. Backend Configuration
```bash
# For vLLM (GPU recommended)
uv add "vllm>=0.2.0" --index https://download.pytorch.org/whl/cu121

# For Ollama (install separately)
# Download from https://ollama.ai/ then:
ollama pull gpt-oss-20b

# For LM Studio (install separately)  
# Download from https://lmstudio.ai/
```

#### 3. Corpus Setup
```bash
# Download and process emergency documents
uv run python scripts/download_documents.py
uv run python scripts/ingest_corpus.py

# Verify corpus integrity
uv run python scripts/verify_corpus.py
```

#### 4. Development Server
```bash
# Start backend (FastAPI)
uv run uvicorn campfire.api.main:app --reload --host 0.0.0.0 --port 8000

# Start frontend (React) - in separate terminal
cd frontend
npm install
npm start
```

### Available Commands

```bash
make help           # Show all available commands
make setup          # Complete environment setup
make dev-install    # Install development dependencies  
make run            # Start development server
make format         # Format code with black and ruff
make lint           # Lint code with ruff and mypy
make test           # Run tests with pytest
make ingest         # Process corpus documents
make clean          # Clean build artifacts
make docker-build   # Build Docker container
make docker-run     # Run in Docker
```

### Testing Offline Mode

#### Airplane Mode Verification
```bash
# 1. Disconnect from internet or enable airplane mode
# 2. Start the application
make run

# 3. Test emergency scenarios
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Someone is choking, what should I do?"}'

# 4. Verify offline indicator in web UI
open http://localhost:8000
```

#### Comprehensive Testing
```bash
# Run offline validation suite
uv run python backend/tests/test_offline_validation.py

# Test emergency scenarios
uv run python backend/tests/test_emergency_scenarios.py

# Verify citation accuracy
uv run python backend/tests/test_citation_accuracy.py
```

### Troubleshooting

#### Common Issues

**vLLM Installation Problems**
```bash
# CUDA version mismatch
pip uninstall vllm
uv add "vllm>=0.2.0" --index https://download.pytorch.org/whl/cu118

# Memory issues
export VLLM_WORKER_MULTIPROC_METHOD=spawn
export CUDA_VISIBLE_DEVICES=0
```

**Ollama Connection Issues**
```bash
# Check Ollama service
ollama list
ollama serve  # if not running

# Test connection
curl http://localhost:11434/api/generate -d '{"model":"gpt-oss-20b","prompt":"test"}'
```

**Corpus Processing Errors**
```bash
# Re-download documents
rm -rf corpus/raw/*
uv run python scripts/download_documents.py

# Rebuild database
rm corpus/processed/corpus.db
uv run python scripts/ingest_corpus.py
```

**Frontend Build Issues**
```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
npm run build
```

## 📚 Corpus Sources

All knowledge comes from two authoritative sources:

1. **IFRC 2020 Guidelines** - Emergency response procedures and first aid protocols
2. **WHO PFA 2011** - Psychological first aid and mental health support

See [CITATIONS.md](CITATIONS.md) for detailed attribution and [LICENSES.md](LICENSES.md) for licensing information.

## 🔒 Safety Features

- **Scope Limitation**: Only first-aid and emergency preparedness topics
- **Emergency Detection**: Automatic escalation for life-threatening situations
- **Citation Enforcement**: All responses must include source references
- **Medical Disclaimers**: Clear warnings that this is not professional medical advice

## 🤖 gpt-oss Integration

### Core gpt-oss Features Demonstrated

**Harmony Tool Orchestration**
- Uses `openai-harmony` library for structured tool calling with gpt-oss models
- Implements custom "browser" tool for local document search and retrieval
- Supports both token-level parsing (vLLM) and text-based fallback (Ollama)

**Local Model Inference**
- Primary: vLLM with gpt-oss-20b for full Harmony token parsing capabilities
- Fallback: Ollama integration with RAG prefetch when token IDs unavailable
- Alternative: LM Studio compatibility for user convenience

**Tool Loop Architecture**
```python
# Example Harmony tool configuration
{
    "recipient_prefix": "browser",
    "definition": {
        "name": "browser", 
        "methods": [
            {"name": "search", "args": {"q": "string"}},
            {"name": "open", "args": {"doc_id": "string", "start": "int", "end": "int"}},
            {"name": "find", "args": {"doc_id": "string", "pattern": "string", "after": "int"}}
        ]
    }
}
```

**Multi-Hop Reasoning**
1. **Search**: Query local FTS5 index for relevant document chunks
2. **Open**: Retrieve specific text windows with precise offset tracking  
3. **Find**: Pattern search within documents for detailed citation anchoring
4. **Synthesize**: Generate structured checklist with source attribution

**Safety Integration**
- Safety Critic component validates all gpt-oss outputs before user display
- Policy-based filtering ensures responses stay within first-aid scope
- Citation enforcement requires source attribution for every response step

## 🏥 For Humanity Impact

Campfire addresses critical needs in emergency situations:
- **Accessibility**: Works without internet connectivity
- **Reliability**: Based on authoritative medical sources
- **Safety**: Built-in safeguards and emergency escalation
- **Education**: Promotes emergency preparedness knowledge

## 📄 License

- **Application Code**: MIT License
- **Corpus Sources**: CC BY-NC (see LICENSES.md for details)
- **Combined Distribution**: Subject to most restrictive terms

## 🏆 OpenAI Open Model Hackathon 2025

### Repository Setup
This repository demonstrates clean development practices:
- **Commit History**: Incremental development with clear commit messages
- **Documentation**: Comprehensive README, citations, and licensing
- **Code Quality**: Type hints, testing, and linting throughout
- **Reproducibility**: One-command setup with uv dependency management

### Hackathon Submission Details
- **Categories**: Best Local Agent (primary), For Humanity (secondary)
- **gpt-oss Usage**: Local inference with Harmony tool orchestration
- **Demo Video**: [Link to be added after recording]
- **Live Demo**: Fully functional offline emergency guidance system

### Key Innovations
1. **Safety-Critical AI**: First gpt-oss application with built-in safety validation
2. **Offline-First Design**: Complete functionality without internet connectivity
3. **Humanitarian Focus**: Addresses real emergency preparedness needs
4. **Tool Integration**: Advanced multi-hop reasoning with local document corpus

## 🤝 Contributing

This project was built for the OpenAI Open Model Hackathon. For questions or suggestions, please open an issue.

### Development Workflow
```bash
# Fork and clone
git clone https://github.com/your-username/campfire.git
cd campfire

# Set up development environment
make setup

# Make changes and test
make test
make lint

# Submit pull request
git push origin feature-branch
```

## 📞 Emergency Disclaimer

**⚠️ IMPORTANT: This application is for educational and preparedness purposes only. In a real emergency, always call your local emergency services (911, 112, etc.) immediately.**

---

Built with ❤️ for the OpenAI Open Model Hackathon 2025