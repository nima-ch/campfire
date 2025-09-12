#!/usr/bin/env python3
"""
Startup health check script for Campfire Emergency Helper.
Performs comprehensive system validation before allowing the service to start.
"""

import os
import sys
import time
import json
import logging
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add backend source to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class StartupHealthChecker:
    """Comprehensive startup health checker for Campfire system."""
    
    def __init__(self):
        self.checks_passed = 0
        self.checks_failed = 0
        self.warnings = []
        self.errors = []
        self.start_time = time.time()
    
    def log_check(self, name: str, success: bool, message: str = "", warning: bool = False):
        """Log the result of a health check."""
        if success:
            self.checks_passed += 1
            logger.info(f"✅ {name}: {message}")
        elif warning:
            self.warnings.append(f"{name}: {message}")
            logger.warning(f"⚠️  {name}: {message}")
        else:
            self.checks_failed += 1
            self.errors.append(f"{name}: {message}")
            logger.error(f"❌ {name}: {message}")
    
    def check_environment_variables(self) -> bool:
        """Check required environment variables."""
        logger.info("Checking environment variables...")
        
        required_vars = {
            "CAMPFIRE_CORPUS_DB": "corpus/processed/corpus.db",
            "CAMPFIRE_AUDIT_DB": "data/audit.db",
            "CAMPFIRE_POLICY_PATH": "policy.md",
            "CAMPFIRE_LLM_PROVIDER": "ollama"
        }
        
        all_good = True
        
        for var, default in required_vars.items():
            value = os.getenv(var, default)
            if value:
                self.log_check(f"Environment variable {var}", True, f"'{value}'")
            else:
                self.log_check(f"Environment variable {var}", False, "Not set")
                all_good = False
        
        return all_good
    
    def check_file_system(self) -> bool:
        """Check file system permissions and required directories."""
        logger.info("Checking file system...")
        
        # Check required directories
        required_dirs = [
            Path(os.getenv("CAMPFIRE_CORPUS_DB", "corpus/processed/corpus.db")).parent,
            Path(os.getenv("CAMPFIRE_AUDIT_DB", "data/audit.db")).parent,
            Path("logs")
        ]
        
        all_good = True
        
        for dir_path in required_dirs:
            try:
                dir_path.mkdir(parents=True, exist_ok=True)
                
                # Test write permissions
                test_file = dir_path / ".write_test"
                test_file.touch()
                test_file.unlink()
                
                self.log_check(f"Directory {dir_path}", True, "Accessible and writable")
            except Exception as e:
                self.log_check(f"Directory {dir_path}", False, f"Error: {e}")
                all_good = False
        
        return all_good
    
    def check_corpus_database(self) -> bool:
        """Check corpus database availability and integrity."""
        logger.info("Checking corpus database...")
        
        corpus_path = Path(os.getenv("CAMPFIRE_CORPUS_DB", "corpus/processed/corpus.db"))
        
        if not corpus_path.exists():
            self.log_check("Corpus database", False, f"Not found at {corpus_path}")
            return False
        
        try:
            # Test database connection
            conn = sqlite3.connect(str(corpus_path))
            cursor = conn.cursor()
            
            # Check tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = ["docs", "chunks", "chunks_fts"]
            missing_tables = [t for t in required_tables if t not in tables]
            
            if missing_tables:
                self.log_check("Corpus database schema", False, f"Missing tables: {missing_tables}")
                conn.close()
                return False
            
            # Check document count
            cursor.execute("SELECT COUNT(*) FROM docs")
            doc_count = cursor.fetchone()[0]
            
            if doc_count == 0:
                self.log_check("Corpus documents", False, "No documents found in corpus")
                conn.close()
                return False
            
            # Test FTS search
            cursor.execute("SELECT COUNT(*) FROM chunks_fts WHERE chunks_fts MATCH 'emergency' LIMIT 1")
            search_result = cursor.fetchone()[0]
            
            conn.close()
            
            self.log_check("Corpus database", True, f"{doc_count} documents, search functional")
            return True
            
        except Exception as e:
            self.log_check("Corpus database", False, f"Database error: {e}")
            return False
    
    def check_python_dependencies(self) -> bool:
        """Check Python dependencies are available."""
        logger.info("Checking Python dependencies...")
        
        required_packages = [
            ("fastapi", "FastAPI web framework"),
            ("uvicorn", "ASGI server"),
            ("pydantic", "Data validation"),
            ("sqlalchemy", "Database ORM"),
            ("openai_harmony", "Harmony integration"),
            ("pdfminer", "PDF processing"),
            ("rich", "Rich text output"),
            ("typer", "CLI framework"),
            ("httpx", "HTTP client"),
            ("jose", "JWT handling"),
            ("passlib", "Password hashing"),
            ("psutil", "System utilities")
        ]
        
        all_good = True
        
        for package, description in required_packages:
            try:
                # Handle package name variations
                import_name = package.replace("-", "_")
                if import_name == "jose":
                    import_name = "jose"
                elif import_name == "pdfminer":
                    import_name = "pdfminer"
                
                __import__(import_name)
                self.log_check(f"Package {package}", True, description)
            except ImportError:
                self.log_check(f"Package {package}", False, f"Not available: {description}")
                all_good = False
        
        return all_good
    
    def check_llm_providers(self) -> bool:
        """Check LLM provider availability."""
        logger.info("Checking LLM providers...")
        
        try:
            from campfire.llm.factory import get_available_providers
            
            providers = get_available_providers()
            available_providers = [p["type"] for p in providers if p["available"]]
            
            if not available_providers:
                self.log_check("LLM providers", False, "No providers available")
                return False
            
            # Check configured provider
            configured_provider = os.getenv("CAMPFIRE_LLM_PROVIDER", "ollama")
            
            if configured_provider in available_providers:
                self.log_check("LLM provider", True, f"'{configured_provider}' is available")
                return True
            else:
                self.log_check("LLM provider", False, 
                             f"Configured provider '{configured_provider}' not available. "
                             f"Available: {available_providers}")
                return False
                
        except Exception as e:
            self.log_check("LLM providers", False, f"Error checking providers: {e}")
            return False
    
    def check_policy_configuration(self) -> bool:
        """Check policy file and safety critic configuration."""
        logger.info("Checking policy configuration...")
        
        policy_path = Path(os.getenv("CAMPFIRE_POLICY_PATH", "policy.md"))
        
        if not policy_path.exists():
            self.log_check("Policy file", True, f"Not found at {policy_path} (will use defaults)", warning=True)
            return True
        
        try:
            # Test policy loading
            from campfire.critic.policy import PolicyEngine
            
            policy_engine = PolicyEngine(str(policy_path))
            
            # Test emergency keyword detection
            test_text = "Patient is unconscious and not breathing"
            emergency_detected = policy_engine.detect_emergency_keywords(test_text)
            
            if emergency_detected:
                self.log_check("Policy configuration", True, "Emergency detection working")
            else:
                self.log_check("Policy configuration", True, "Loaded successfully", warning=True)
            
            return True
            
        except Exception as e:
            self.log_check("Policy configuration", False, f"Error loading policy: {e}")
            return False
    
    def check_network_isolation(self) -> bool:
        """Verify system can operate offline."""
        logger.info("Checking offline operation capability...")
        
        try:
            import socket
            
            # Try to connect to common external services (should fail in offline mode)
            test_hosts = [
                ("8.8.8.8", 53),      # Google DNS
                ("1.1.1.1", 53),      # Cloudflare DNS
                ("google.com", 80),   # Google HTTP
            ]
            
            external_connections = 0
            
            for host, port in test_hosts:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)  # 1 second timeout
                    result = sock.connect_ex((host, port))
                    sock.close()
                    
                    if result == 0:
                        external_connections += 1
                
                except Exception:
                    pass  # Connection failed, which is expected in offline mode
            
            if external_connections == 0:
                self.log_check("Network isolation", True, "No external connections detected (offline mode)")
            else:
                self.log_check("Network isolation", True, 
                             f"External connections possible ({external_connections} hosts reachable)", 
                             warning=True)
            
            return True
            
        except Exception as e:
            self.log_check("Network isolation", False, f"Error checking network: {e}")
            return False
    
    def check_system_resources(self) -> bool:
        """Check system resource availability."""
        logger.info("Checking system resources...")
        
        try:
            import psutil
            
            # Check memory
            memory = psutil.virtual_memory()
            memory_gb = memory.total / (1024**3)
            
            if memory_gb < 4:
                self.log_check("System memory", False, f"Only {memory_gb:.1f}GB available (minimum 4GB recommended)")
                return False
            elif memory_gb < 8:
                self.log_check("System memory", True, f"{memory_gb:.1f}GB available (8GB+ recommended for optimal performance)", warning=True)
            else:
                self.log_check("System memory", True, f"{memory_gb:.1f}GB available")
            
            # Check disk space
            disk = psutil.disk_usage('.')
            disk_gb = disk.free / (1024**3)
            
            if disk_gb < 2:
                self.log_check("Disk space", False, f"Only {disk_gb:.1f}GB free (minimum 2GB required)")
                return False
            elif disk_gb < 5:
                self.log_check("Disk space", True, f"{disk_gb:.1f}GB free (5GB+ recommended)", warning=True)
            else:
                self.log_check("Disk space", True, f"{disk_gb:.1f}GB free")
            
            # Check CPU
            cpu_count = psutil.cpu_count()
            self.log_check("CPU cores", True, f"{cpu_count} cores available")
            
            return True
            
        except Exception as e:
            self.log_check("System resources", False, f"Error checking resources: {e}")
            return False
    
    def run_comprehensive_check(self) -> bool:
        """Run all health checks."""
        logger.info("🔥 Starting Campfire startup health check...")
        logger.info("=" * 60)
        
        checks = [
            ("Environment Variables", self.check_environment_variables),
            ("File System", self.check_file_system),
            ("Python Dependencies", self.check_python_dependencies),
            ("Corpus Database", self.check_corpus_database),
            ("LLM Providers", self.check_llm_providers),
            ("Policy Configuration", self.check_policy_configuration),
            ("Network Isolation", self.check_network_isolation),
            ("System Resources", self.check_system_resources),
        ]
        
        for check_name, check_func in checks:
            logger.info(f"\n--- {check_name} ---")
            try:
                check_func()
            except Exception as e:
                self.log_check(check_name, False, f"Unexpected error: {e}")
        
        # Summary
        elapsed_time = time.time() - self.start_time
        logger.info("\n" + "=" * 60)
        logger.info("🏥 Health Check Summary")
        logger.info(f"⏱️  Time elapsed: {elapsed_time:.2f} seconds")
        logger.info(f"✅ Checks passed: {self.checks_passed}")
        logger.info(f"⚠️  Warnings: {len(self.warnings)}")
        logger.info(f"❌ Checks failed: {self.checks_failed}")
        
        if self.warnings:
            logger.info("\nWarnings:")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")
        
        if self.errors:
            logger.info("\nErrors:")
            for error in self.errors:
                logger.error(f"  - {error}")
        
        success = self.checks_failed == 0
        
        if success:
            logger.info("\n🎉 All critical health checks passed! System ready to start.")
        else:
            logger.error(f"\n💥 {self.checks_failed} critical health checks failed. System not ready.")
        
        return success
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get detailed health report."""
        return {
            "success": self.checks_failed == 0,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "warnings": self.warnings,
            "errors": self.errors,
            "elapsed_time": time.time() - self.start_time
        }


def main():
    """Main health check function."""
    checker = StartupHealthChecker()
    
    # Run comprehensive check
    success = checker.run_comprehensive_check()
    
    # Output JSON report if requested
    if "--json" in sys.argv:
        report = checker.get_health_report()
        print(json.dumps(report, indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()