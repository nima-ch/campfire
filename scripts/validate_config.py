#!/usr/bin/env python3
"""
Configuration validation script for Campfire Emergency Helper.
Validates system configuration and dependencies before startup.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add backend source to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))

from campfire.corpus.database import CorpusDatabase
from campfire.llm.factory import get_available_providers
from campfire.critic.policy import PolicyEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


class ConfigValidator:
    """Configuration validator for Campfire system."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.config: Dict[str, Any] = {}
    
    def validate_environment(self) -> bool:
        """Validate environment variables."""
        logger.info("Validating environment configuration...")
        
        # Required environment variables
        required_vars = {
            "CAMPFIRE_CORPUS_DB": "corpus/processed/corpus.db",
            "CAMPFIRE_AUDIT_DB": "data/audit.db",
            "CAMPFIRE_POLICY_PATH": "policy.md",
            "CAMPFIRE_LLM_PROVIDER": "ollama"
        }
        
        for var, default in required_vars.items():
            value = os.getenv(var, default)
            self.config[var] = value
            logger.info(f"  {var}={value}")
        
        # Optional environment variables
        optional_vars = {
            "CAMPFIRE_HOST": "127.0.0.1",
            "CAMPFIRE_PORT": "8000",
            "CAMPFIRE_DEBUG": "false",
            "CAMPFIRE_ADMIN_PASSWORD": None
        }
        
        for var, default in optional_vars.items():
            value = os.getenv(var, default)
            if value:
                self.config[var] = value
        
        return True
    
    def validate_corpus_database(self) -> bool:
        """Validate corpus database."""
        logger.info("Validating corpus database...")
        
        corpus_path = Path(self.config["CAMPFIRE_CORPUS_DB"])
        
        if not corpus_path.exists():
            self.errors.append(f"Corpus database not found: {corpus_path}")
            return False
        
        try:
            # Test database connection
            db = CorpusDatabase(str(corpus_path))
            docs = db.list_documents()
            
            if not docs:
                self.warnings.append("Corpus database is empty")
            else:
                logger.info(f"  Found {len(docs)} documents in corpus")
                for doc in docs:
                    logger.info(f"    - {doc}")
            
            # Test search functionality
            try:
                results = db.search("emergency", limit=1)
                if results:
                    logger.info("  Search functionality verified")
                else:
                    self.warnings.append("No search results for test query")
            except Exception as e:
                self.errors.append(f"Search functionality failed: {e}")
            
            db.close()
            return True
            
        except Exception as e:
            self.errors.append(f"Corpus database error: {e}")
            return False
    
    def validate_policy_file(self) -> bool:
        """Validate policy file."""
        logger.info("Validating policy configuration...")
        
        policy_path = Path(self.config["CAMPFIRE_POLICY_PATH"])
        
        if not policy_path.exists():
            self.warnings.append(f"Policy file not found: {policy_path} (will use defaults)")
            return True
        
        try:
            # Test policy engine
            policy_engine = PolicyEngine(str(policy_path))
            
            # Test emergency keyword detection
            test_keywords = ["unconscious", "chest pain", "bleeding"]
            detected = []
            for keyword in test_keywords:
                if policy_engine.detect_emergency_keywords(f"Patient is {keyword}"):
                    detected.append(keyword)
            
            if detected:
                logger.info(f"  Emergency keyword detection working: {detected}")
            else:
                self.warnings.append("Emergency keyword detection may not be working")
            
            return True
            
        except Exception as e:
            self.errors.append(f"Policy validation error: {e}")
            return False
    
    def validate_llm_providers(self) -> bool:
        """Validate LLM providers."""
        logger.info("Validating LLM providers...")
        
        try:
            providers = get_available_providers()
            available_providers = [p["type"] for p in providers if p["available"]]
            
            if not available_providers:
                self.errors.append("No LLM providers available")
                return False
            
            logger.info(f"  Available providers: {available_providers}")
            
            # Check configured provider
            configured_provider = self.config["CAMPFIRE_LLM_PROVIDER"]
            if configured_provider not in available_providers:
                self.errors.append(
                    f"Configured LLM provider '{configured_provider}' is not available. "
                    f"Available: {available_providers}"
                )
                return False
            
            logger.info(f"  Configured provider '{configured_provider}' is available")
            return True
            
        except Exception as e:
            self.errors.append(f"LLM provider validation error: {e}")
            return False
    
    def validate_dependencies(self) -> bool:
        """Validate Python dependencies."""
        logger.info("Validating Python dependencies...")
        
        required_packages = [
            "fastapi", "uvicorn", "pydantic", "sqlalchemy",
            "openai_harmony", "pdfminer", "rich", "typer",
            "httpx", "python_multipart", "jinja2", "python_jose",
            "passlib", "python_dotenv", "psutil"
        ]
        
        missing_packages = []
        
        for package in required_packages:
            try:
                # Handle package name variations
                import_name = package.replace("-", "_").replace(".", "_")
                if import_name == "python_jose":
                    import_name = "jose"
                elif import_name == "python_multipart":
                    import_name = "multipart"
                elif import_name == "python_dotenv":
                    import_name = "dotenv"
                elif import_name == "pdfminer":
                    import_name = "pdfminer"
                
                __import__(import_name)
                logger.info(f"  ✅ {package}")
            except ImportError:
                missing_packages.append(package)
                logger.error(f"  ❌ {package}")
        
        if missing_packages:
            self.errors.append(f"Missing required packages: {missing_packages}")
            return False
        
        return True
    
    def validate_directories(self) -> bool:
        """Validate required directories."""
        logger.info("Validating directory structure...")
        
        required_dirs = [
            Path(self.config["CAMPFIRE_CORPUS_DB"]).parent,
            Path(self.config["CAMPFIRE_AUDIT_DB"]).parent,
            Path("logs"),
        ]
        
        for dir_path in required_dirs:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"  ✅ {dir_path}")
            except Exception as e:
                self.errors.append(f"Cannot create directory {dir_path}: {e}")
                return False
        
        return True
    
    def validate_permissions(self) -> bool:
        """Validate file permissions."""
        logger.info("Validating file permissions...")
        
        # Check read permissions
        read_files = [
            self.config["CAMPFIRE_CORPUS_DB"],
            self.config.get("CAMPFIRE_POLICY_PATH")
        ]
        
        for file_path in read_files:
            if file_path and Path(file_path).exists():
                if not os.access(file_path, os.R_OK):
                    self.errors.append(f"No read permission for: {file_path}")
                    return False
        
        # Check write permissions for directories
        write_dirs = [
            Path(self.config["CAMPFIRE_AUDIT_DB"]).parent,
            Path("logs")
        ]
        
        for dir_path in write_dirs:
            if dir_path.exists() and not os.access(dir_path, os.W_OK):
                self.errors.append(f"No write permission for: {dir_path}")
                return False
        
        return True
    
    def run_validation(self) -> bool:
        """Run complete validation."""
        logger.info("🔍 Starting Campfire configuration validation...")
        
        validations = [
            self.validate_environment,
            self.validate_directories,
            self.validate_permissions,
            self.validate_dependencies,
            self.validate_corpus_database,
            self.validate_policy_file,
            self.validate_llm_providers,
        ]
        
        success = True
        for validation in validations:
            try:
                if not validation():
                    success = False
            except Exception as e:
                self.errors.append(f"Validation error in {validation.__name__}: {e}")
                success = False
        
        # Report results
        if self.warnings:
            logger.warning("⚠️  Validation warnings:")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")
        
        if self.errors:
            logger.error("❌ Validation errors:")
            for error in self.errors:
                logger.error(f"  - {error}")
            return False
        
        if success:
            logger.info("✅ Configuration validation passed!")
        
        return success
    
    def get_validation_report(self) -> Dict[str, Any]:
        """Get detailed validation report."""
        return {
            "success": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
            "config": self.config
        }


def main():
    """Main validation function."""
    validator = ConfigValidator()
    
    # Run validation
    success = validator.run_validation()
    
    # Output JSON report if requested
    if "--json" in sys.argv:
        report = validator.get_validation_report()
        print(json.dumps(report, indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()