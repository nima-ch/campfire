# Licenses

This document outlines the licensing information for the Campfire Emergency Helper application and its dependencies.

## Application License

### Campfire Emergency Helper
- **License**: MIT License
- **Copyright**: 2025 nima-ch
- **File**: LICENSE

## Corpus Source Licenses

### IFRC 2020 Guidelines
- **License**: Creative Commons Attribution-NonCommercial-NoDerivs 3.0 IGO License (CC BY-NC-ND 3.0 IGO)
- **Rights Holder**: International Federation of Red Cross and Red Crescent Societies
- **Permissions**: 
  - Share — copy and redistribute the material in any medium or format
  - Attribution required
- **Restrictions**:
  - NonCommercial — not for commercial purposes
  - NoDerivatives — no remixing, transforming, or building upon the material
- **URL**: https://creativecommons.org/licenses/by-nc-nd/3.0/igo/

### WHO Psychological First Aid Guide (PFA 2011)
- **License**: Creative Commons Attribution-NonCommercial-ShareAlike 3.0 IGO (CC BY-NC-SA 3.0 IGO)
- **Rights Holder**: World Health Organization
- **Permissions**:
  - Share — copy and redistribute the material in any medium or format
  - Adapt — remix, transform, and build upon the material
  - Attribution required
- **Restrictions**:
  - NonCommercial — not for commercial purposes
  - ShareAlike — distribute contributions under the same license
- **URL**: https://creativecommons.org/licenses/by-nc-sa/3.0/igo/

## Third-Party Dependencies

### Python Dependencies
All Python dependencies are listed in `pyproject.toml` with their respective licenses:

#### Core Dependencies
- **FastAPI**: MIT License
- **Uvicorn**: BSD License
- **Pydantic**: MIT License
- **SQLAlchemy**: MIT License
- **OpenAI Harmony**: MIT License (assumed)

#### Development Dependencies
- **pytest**: MIT License
- **black**: MIT License
- **ruff**: MIT License
- **mypy**: MIT License

#### Optional Dependencies
- **vLLM**: Apache License 2.0
- **Ollama**: MIT License
- **PyTorch**: BSD License

### Frontend Dependencies
Frontend dependencies will be documented in `frontend/package.json` when implemented.

## Model Licenses

### gpt-oss Models
- **License**: Apache License 2.0
- **Provider**: Various (to be specified based on actual model used)
- **Usage**: Local inference only, no external API calls

## Compliance Requirements

### Attribution
All uses of corpus materials must include:
1. Clear attribution to source organization (IFRC/WHO)
2. License information
3. Link to original source when possible
4. "Not medical advice" disclaimer

### Non-Commercial Use
- The corpus sources are licensed for non-commercial use only
- The Campfire application is provided for educational and emergency preparedness purposes
- Commercial deployment would require separate licensing agreements

### Distribution
- Source code: MIT License allows commercial and non-commercial use
- Corpus data: Must maintain CC license restrictions
- Combined application: Subject to most restrictive license terms (CC BY-NC)

## License Compatibility Matrix

| Component | License | Commercial Use | Modification | Distribution |
|-----------|---------|----------------|--------------|--------------|
| Campfire Code | MIT | ✅ | ✅ | ✅ |
| IFRC Guidelines | CC BY-NC-ND 3.0 IGO | ❌ | ❌ | ✅ |
| WHO PFA Guide | CC BY-NC-SA 3.0 IGO | ❌ | ✅ | ✅ |
| Combined App | CC BY-NC | ❌ | Limited | ✅ |

## Contact

For licensing questions or permissions beyond those granted by the licenses above, please contact:
- **Application**: nima.ch@gmail.com
- **IFRC Materials**: https://www.ifrc.org/
- **WHO Materials**: https://www.who.int/

Last Updated: September 2025