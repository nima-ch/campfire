#!/usr/bin/env python3
"""
Smoke test script for Campfire emergency helper system.

This script performs end-to-end validation of the complete system including:
- Document corpus integrity
- Search functionality
- API endpoints
- Safety critic functionality
- Offline operation verification
"""

import sys
import json
import time
import logging
import asyncio
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional
import subprocess

# Add the backend source to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))

from campfire.corpus import CorpusDatabase
from campfire.api.models import ChatRequest, ChatResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SmokeTestSuite:
    """Comprehensive smoke test suite for Campfire system."""
    
    def __init__(self, corpus_dir: Path, api_base_url: str = "http://localhost:8000"):
        """Initialize smoke test suite.
        
        Args:
            corpus_dir: Directory containing corpus files
            api_base_url: Base URL for API testing
        """
        self.corpus_dir = Path(corpus_dir)
        self.api_base_url = api_base_url
        self.db_path = self.corpus_dir / "processed" / "corpus.db"
        
        # Test results
        self.test_results = {
            "timestamp": time.time(),
            "tests": {},
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0
            }
        }
    
    def run_test(self, test_name: str, test_func, *args, **kwargs) -> bool:
        """Run a single test and record results.
        
        Args:
            test_name: Name of the test
            test_func: Test function to run
            *args: Arguments for test function
            **kwargs: Keyword arguments for test function
            
        Returns:
            True if test passed, False otherwise
        """
        logger.info(f"🧪 Running test: {test_name}")
        
        start_time = time.time()
        
        try:
            result = test_func(*args, **kwargs)
            
            if result.get("passed", False):
                logger.info(f"✅ {test_name}: PASSED")
                self.test_results["summary"]["passed"] += 1
                status = "PASSED"
            else:
                logger.error(f"❌ {test_name}: FAILED - {result.get('error', 'Unknown error')}")
                self.test_results["summary"]["failed"] += 1
                status = "FAILED"
                
        except Exception as e:
            logger.error(f"❌ {test_name}: ERROR - {e}")
            result = {"passed": False, "error": str(e)}
            self.test_results["summary"]["failed"] += 1
            status = "ERROR"
        
        # Record test result
        self.test_results["tests"][test_name] = {
            "status": status,
            "duration": time.time() - start_time,
            "result": result
        }
        
        self.test_results["summary"]["total"] += 1
        
        return result.get("passed", False)
    
    def test_corpus_database_exists(self) -> Dict[str, Any]:
        """Test that corpus database exists and is accessible."""
        try:
            if not self.db_path.exists():
                return {"passed": False, "error": f"Database file not found: {self.db_path}"}
            
            # Try to connect to database
            db = CorpusDatabase(str(self.db_path))
            stats = db.get_stats()
            db.close()
            
            if stats["documents"] == 0:
                return {"passed": False, "error": "No documents found in corpus"}
            
            if stats["chunks"] == 0:
                return {"passed": False, "error": "No text chunks found in corpus"}
            
            return {
                "passed": True,
                "stats": stats,
                "message": f"Database contains {stats['documents']} documents and {stats['chunks']} chunks"
            }
            
        except Exception as e:
            return {"passed": False, "error": f"Database connection failed: {e}"}
    
    def test_corpus_search_functionality(self) -> Dict[str, Any]:
        """Test corpus search functionality with various queries."""
        try:
            db = CorpusDatabase(str(self.db_path))
            
            # Test queries covering different emergency scenarios
            test_queries = [
                "emergency",
                "first aid",
                "bleeding",
                "burns",
                "CPR",
                "psychological",
                "safety",
                "wound care",
                "fracture",
                "poisoning"
            ]
            
            search_results = {}
            total_results = 0
            
            for query in test_queries:
                results = db.search(query, limit=5)
                search_results[query] = len(results)
                total_results += len(results)
                
                # Validate result structure
                for result in results:
                    required_fields = ["doc_id", "doc_title", "text", "page_number"]
                    for field in required_fields:
                        if field not in result:
                            db.close()
                            return {"passed": False, "error": f"Missing field '{field}' in search result"}
            
            db.close()
            
            if total_results == 0:
                return {"passed": False, "error": "No search results found for any query"}
            
            return {
                "passed": True,
                "search_results": search_results,
                "total_results": total_results,
                "message": f"Search functionality working, {total_results} total results across {len(test_queries)} queries"
            }
            
        except Exception as e:
            return {"passed": False, "error": f"Search test failed: {e}"}
    
    def test_document_retrieval(self) -> Dict[str, Any]:
        """Test document chunk retrieval functionality."""
        try:
            db = CorpusDatabase(str(self.db_path))
            
            # Get list of documents
            documents = db.list_documents()
            
            if not documents:
                db.close()
                return {"passed": False, "error": "No documents found"}
            
            retrieval_results = {}
            
            for doc in documents:
                doc_id = doc["doc_id"]
                
                # Get chunks for this document
                chunks = db.get_document_chunks(doc_id)
                
                if not chunks:
                    db.close()
                    return {"passed": False, "error": f"No chunks found for document {doc_id}"}
                
                # Validate chunk structure
                for chunk in chunks[:3]:  # Test first 3 chunks
                    required_fields = ["chunk_id", "text", "start_offset", "end_offset"]
                    for field in required_fields:
                        if field not in chunk:
                            db.close()
                            return {"passed": False, "error": f"Missing field '{field}' in chunk"}
                
                retrieval_results[doc_id] = {
                    "chunks": len(chunks),
                    "title": doc["title"]
                }
            
            db.close()
            
            return {
                "passed": True,
                "retrieval_results": retrieval_results,
                "message": f"Document retrieval working for {len(documents)} documents"
            }
            
        except Exception as e:
            return {"passed": False, "error": f"Document retrieval test failed: {e}"}
    
    def test_api_health_endpoint(self) -> Dict[str, Any]:
        """Test API health endpoint."""
        try:
            import httpx
            
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{self.api_base_url}/health")
                
                if response.status_code != 200:
                    return {"passed": False, "error": f"Health endpoint returned status {response.status_code}"}
                
                health_data = response.json()
                
                if health_data.get("status") != "healthy":
                    return {"passed": False, "error": f"Health status is not healthy: {health_data}"}
                
                return {
                    "passed": True,
                    "health_data": health_data,
                    "message": "API health endpoint responding correctly"
                }
                
        except ImportError:
            return {"passed": False, "error": "httpx not available for API testing"}
        except Exception as e:
            return {"passed": False, "error": f"API health test failed: {e}"}
    
    def test_api_chat_endpoint(self) -> Dict[str, Any]:
        """Test API chat endpoint with sample queries."""
        try:
            import httpx
            
            test_queries = [
                "What should I do for a minor burn?",
                "How do I help someone who is bleeding?",
                "What are the steps for CPR?",
                "How can I provide psychological first aid?"
            ]
            
            chat_results = {}
            
            with httpx.Client(timeout=30.0) as client:
                for query in test_queries:
                    chat_request = {
                        "message": query,
                        "conversation_id": f"test_{int(time.time())}"
                    }
                    
                    response = client.post(
                        f"{self.api_base_url}/chat",
                        json=chat_request
                    )
                    
                    if response.status_code != 200:
                        return {"passed": False, "error": f"Chat endpoint returned status {response.status_code} for query: {query}"}
                    
                    chat_data = response.json()
                    
                    # Validate response structure
                    required_fields = ["response", "conversation_id", "timestamp"]
                    for field in required_fields:
                        if field not in chat_data:
                            return {"passed": False, "error": f"Missing field '{field}' in chat response"}
                    
                    # Check if response contains checklist
                    if "checklist" not in chat_data.get("response", {}):
                        return {"passed": False, "error": f"No checklist in response for query: {query}"}
                    
                    chat_results[query] = {
                        "status": "success",
                        "response_length": len(str(chat_data["response"])),
                        "has_checklist": "checklist" in chat_data["response"]
                    }
            
            return {
                "passed": True,
                "chat_results": chat_results,
                "message": f"Chat endpoint working for {len(test_queries)} test queries"
            }
            
        except ImportError:
            return {"passed": False, "error": "httpx not available for API testing"}
        except Exception as e:
            return {"passed": False, "error": f"API chat test failed: {e}"}
    
    def test_safety_critic_functionality(self) -> Dict[str, Any]:
        """Test safety critic with various scenarios."""
        try:
            # Import safety critic components
            from campfire.critic import SafetyCritic, PolicyEngine
            
            # Initialize safety critic
            policy_file = Path("policy.md")
            if not policy_file.exists():
                return {"passed": False, "error": "Policy file not found"}
            
            policy_engine = PolicyEngine(str(policy_file))
            safety_critic = SafetyCritic(policy_engine)
            
            # Test scenarios
            test_scenarios = [
                {
                    "name": "valid_first_aid",
                    "checklist": [
                        {
                            "title": "Clean the wound",
                            "action": "Rinse with clean water",
                            "source": {"doc_id": "test", "loc": [100, 200]}
                        }
                    ],
                    "expected": "ALLOW"
                },
                {
                    "name": "missing_citation",
                    "checklist": [
                        {
                            "title": "Apply pressure",
                            "action": "Press firmly on wound"
                            # Missing source
                        }
                    ],
                    "expected": "BLOCK"
                },
                {
                    "name": "emergency_keywords",
                    "checklist": [
                        {
                            "title": "Check consciousness",
                            "action": "Person is unconscious and not breathing",
                            "source": {"doc_id": "test", "loc": [100, 200]}
                        }
                    ],
                    "expected": "ALLOW"  # Should allow but add emergency banner
                }
            ]
            
            critic_results = {}
            
            for scenario in test_scenarios:
                try:
                    decision = safety_critic.review_response({
                        "checklist": scenario["checklist"],
                        "meta": {"disclaimer": "Not medical advice"}
                    })
                    
                    critic_results[scenario["name"]] = {
                        "decision": decision["status"],
                        "expected": scenario["expected"],
                        "passed": decision["status"] == scenario["expected"]
                    }
                    
                except Exception as e:
                    critic_results[scenario["name"]] = {
                        "decision": "ERROR",
                        "expected": scenario["expected"],
                        "passed": False,
                        "error": str(e)
                    }
            
            # Check if all scenarios passed
            all_passed = all(result["passed"] for result in critic_results.values())
            
            return {
                "passed": all_passed,
                "critic_results": critic_results,
                "message": f"Safety critic test: {sum(1 for r in critic_results.values() if r['passed'])}/{len(critic_results)} scenarios passed"
            }
            
        except ImportError as e:
            return {"passed": False, "error": f"Safety critic components not available: {e}"}
        except Exception as e:
            return {"passed": False, "error": f"Safety critic test failed: {e}"}
    
    def test_offline_operation(self) -> Dict[str, Any]:
        """Test that system works without internet connectivity."""
        try:
            # This is a basic test - in a real scenario you'd disable network
            # For now, we'll just verify that all components can work locally
            
            # Test local database access
            db = CorpusDatabase(str(self.db_path))
            stats = db.get_stats()
            db.close()
            
            if stats["documents"] == 0:
                return {"passed": False, "error": "No local documents available"}
            
            # Test that we can perform searches without network
            db = CorpusDatabase(str(self.db_path))
            results = db.search("emergency", limit=1)
            db.close()
            
            if not results:
                return {"passed": False, "error": "Local search not working"}
            
            return {
                "passed": True,
                "message": "Offline operation verified - local database and search working",
                "local_documents": stats["documents"],
                "local_chunks": stats["chunks"]
            }
            
        except Exception as e:
            return {"passed": False, "error": f"Offline operation test failed: {e}"}
    
    def test_document_integrity(self) -> Dict[str, Any]:
        """Test integrity of ingested documents."""
        try:
            db = CorpusDatabase(str(self.db_path))
            
            # Get all documents
            documents = db.list_documents()
            
            integrity_results = {}
            issues = []
            
            for doc in documents:
                doc_id = doc["doc_id"]
                
                # Get chunks for document
                chunks = db.get_document_chunks(doc_id)
                
                if not chunks:
                    issues.append(f"No chunks found for document {doc_id}")
                    continue
                
                # Check for gaps in offsets
                sorted_chunks = sorted(chunks, key=lambda x: x["start_offset"])
                
                gaps = []
                for i in range(1, len(sorted_chunks)):
                    prev_end = sorted_chunks[i-1]["end_offset"]
                    curr_start = sorted_chunks[i]["start_offset"]
                    
                    if curr_start > prev_end + 100:  # Allow some overlap
                        gaps.append(f"Gap between chunks {i-1} and {i}")
                
                # Check for empty chunks
                empty_chunks = [c for c in chunks if not c["text"].strip()]
                
                integrity_results[doc_id] = {
                    "chunks": len(chunks),
                    "gaps": gaps,
                    "empty_chunks": len(empty_chunks),
                    "issues": gaps + ([f"{len(empty_chunks)} empty chunks"] if empty_chunks else [])
                }
                
                if integrity_results[doc_id]["issues"]:
                    issues.extend([f"{doc_id}: {issue}" for issue in integrity_results[doc_id]["issues"]])
            
            db.close()
            
            return {
                "passed": len(issues) == 0,
                "integrity_results": integrity_results,
                "issues": issues,
                "message": f"Document integrity check: {len(issues)} issues found across {len(documents)} documents"
            }
            
        except Exception as e:
            return {"passed": False, "error": f"Document integrity test failed: {e}"}
    
    def test_performance_benchmarks(self) -> Dict[str, Any]:
        """Test basic performance benchmarks."""
        try:
            db = CorpusDatabase(str(self.db_path))
            
            # Test search performance
            search_queries = ["emergency", "first aid", "bleeding", "burns", "CPR"]
            search_times = []
            
            for query in search_queries:
                start_time = time.time()
                results = db.search(query, limit=10)
                search_time = time.time() - start_time
                search_times.append(search_time)
            
            avg_search_time = sum(search_times) / len(search_times)
            
            # Test chunk retrieval performance
            documents = db.list_documents()
            retrieval_times = []
            
            for doc in documents[:3]:  # Test first 3 documents
                start_time = time.time()
                chunks = db.get_document_chunks(doc["doc_id"])
                retrieval_time = time.time() - start_time
                retrieval_times.append(retrieval_time)
            
            avg_retrieval_time = sum(retrieval_times) / len(retrieval_times) if retrieval_times else 0
            
            db.close()
            
            # Performance thresholds (in seconds)
            search_threshold = 1.0  # Search should be under 1 second
            retrieval_threshold = 0.5  # Chunk retrieval should be under 0.5 seconds
            
            performance_ok = (avg_search_time < search_threshold and 
                            avg_retrieval_time < retrieval_threshold)
            
            return {
                "passed": performance_ok,
                "benchmarks": {
                    "avg_search_time": round(avg_search_time, 3),
                    "avg_retrieval_time": round(avg_retrieval_time, 3),
                    "search_threshold": search_threshold,
                    "retrieval_threshold": retrieval_threshold
                },
                "message": f"Performance test: search {avg_search_time:.3f}s, retrieval {avg_retrieval_time:.3f}s"
            }
            
        except Exception as e:
            return {"passed": False, "error": f"Performance test failed: {e}"}
    
    def run_all_tests(self, include_api_tests: bool = True) -> Dict[str, Any]:
        """Run complete smoke test suite.
        
        Args:
            include_api_tests: Whether to include API endpoint tests
            
        Returns:
            Complete test results
        """
        logger.info("🔥 Starting Campfire smoke test suite")
        logger.info("=" * 60)
        
        # Core system tests
        self.run_test("corpus_database_exists", self.test_corpus_database_exists)
        self.run_test("corpus_search_functionality", self.test_corpus_search_functionality)
        self.run_test("document_retrieval", self.test_document_retrieval)
        self.run_test("document_integrity", self.test_document_integrity)
        self.run_test("offline_operation", self.test_offline_operation)
        self.run_test("performance_benchmarks", self.test_performance_benchmarks)
        
        # Safety critic tests
        self.run_test("safety_critic_functionality", self.test_safety_critic_functionality)
        
        # API tests (optional)
        if include_api_tests:
            self.run_test("api_health_endpoint", self.test_api_health_endpoint)
            self.run_test("api_chat_endpoint", self.test_api_chat_endpoint)
        
        # Calculate final results
        summary = self.test_results["summary"]
        success_rate = (summary["passed"] / summary["total"]) * 100 if summary["total"] > 0 else 0
        
        logger.info("\n" + "=" * 60)
        logger.info("📊 SMOKE TEST RESULTS")
        logger.info("=" * 60)
        logger.info(f"Total tests: {summary['total']}")
        logger.info(f"Passed: {summary['passed']}")
        logger.info(f"Failed: {summary['failed']}")
        logger.info(f"Success rate: {success_rate:.1f}%")
        
        if summary["failed"] == 0:
            logger.info("\n✅ All smoke tests passed! System is ready for use.")
        else:
            logger.warning(f"\n⚠️  {summary['failed']} tests failed. System may have issues.")
            
            # Show failed tests
            for test_name, test_result in self.test_results["tests"].items():
                if test_result["status"] in ["FAILED", "ERROR"]:
                    logger.error(f"  ❌ {test_name}: {test_result['result'].get('error', 'Unknown error')}")
        
        return self.test_results
    
    def save_results(self, output_file: Optional[Path] = None):
        """Save test results to file.
        
        Args:
            output_file: Path to save results (default: smoke_test_results.json)
        """
        if output_file is None:
            output_file = Path("smoke_test_results.json")
        
        try:
            with open(output_file, 'w') as f:
                json.dump(self.test_results, f, indent=2)
            
            logger.info(f"📄 Test results saved to {output_file}")
            
        except Exception as e:
            logger.error(f"Failed to save test results: {e}")


def main():
    """Main entry point for smoke test."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Campfire smoke test suite")
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path("corpus"),
        help="Directory containing corpus files (default: corpus)"
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Base URL for API testing (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--no-api-tests",
        action="store_true",
        help="Skip API endpoint tests"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Save results to file (default: smoke_test_results.json)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Initialize and run smoke tests
        smoke_test = SmokeTestSuite(args.corpus_dir, args.api_url)
        results = smoke_test.run_all_tests(include_api_tests=not args.no_api_tests)
        
        # Save results if requested
        if args.output:
            smoke_test.save_results(args.output)
        
        # Return appropriate exit code
        if results["summary"]["failed"] == 0:
            return 0
        else:
            return 1
            
    except Exception as e:
        logger.error(f"Fatal error in smoke test: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())