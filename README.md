# Campfire Emergency Helper

An offline-first emergency helper application built for the OpenAI Open Model Hackathon, demonstrating gpt-oss capabilities with Harmony tools in a safety-critical, offline environment.

## 🎯 Hackathon Categories
- **Primary**: Best Local Agent
- **Secondary**: For Humanity

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) package manager
- Git

### Installation

1. Clone the repository:
```bash
git clone https://github.com/nima-ch/campfire.git
cd campfire
```

2. Set up the development environment:
```bash
make setup
```

3. Process the corpus documents:
```bash
make ingest
```

4. Start the development server:
```bash
make run
```

The application will be available at `http://localhost:8000`

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

### Available Commands

```bash
make help           # Show all available commands
make dev-install    # Install development dependencies
make run            # Start development server
make format         # Format code with black and ruff
make lint           # Lint code with ruff and mypy
make test           # Run tests with pytest
make ingest         # Process corpus documents
```

### Testing Offline Mode

To verify offline functionality:
1. Enable airplane mode or disconnect from internet
2. Start the application with `make run`
3. Test emergency scenarios through the web interface
4. Verify all responses include proper citations

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

This project demonstrates gpt-oss capabilities through:
- Local model inference with vLLM/Ollama backends
- Harmony orchestration for tool-based workflows
- Offline document retrieval and citation
- Safety-critical response validation

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

## 🤝 Contributing

This project was built for the OpenAI Open Model Hackathon. For questions or suggestions, please open an issue.

## 📞 Emergency Disclaimer

**⚠️ IMPORTANT: This application is for educational and preparedness purposes only. In a real emergency, always call your local emergency services (911, 112, etc.) immediately.**

---

Built with ❤️ for the OpenAI Open Model Hackathon 2025