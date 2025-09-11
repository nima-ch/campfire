#!/usr/bin/env python3
"""
Corpus integrity verification script for Campfire emergency helper.

This script performs comprehensive verification of the document corpus
including checksums, content validation, and search functionality.
"""

import sys
import json
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import time

# Add the backend source to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend" / "src"))

from campfire.corpus import CorpusDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CorpusVerifier:
    """Comprehensive corpus integrity verification."""
    
    def __init__(self, corpus_dir: Path):
        """Initialize corpus verifier.
        
        Args:
            corpus_dir: Directory containing corpus files
        """
        self.corpus_dir = Path(corpus_dir)
        self.raw_dir = self.corpus_dir / "raw"
        self.processed_dir = self.corpus_dir / "processed"
        self.db_path = self.processed_dir / "corpus.db"
        
        # Expected documents
        self.expected_documents = {
            "ifrc_first_aid_2020": {
                "title_contains": ["IFRC", "First Aid", "2020"],
                "min_chunks": 10,
                "expected_keywords": ["emergency", "first aid", "bleeding", "CPR", "burns"]
            },
            "who_psychological_first_aid_2011": {
                "title_contains": ["WHO", "Psychological", "First Aid"],
                "min_chunks": 5,
                "expected_keywords": ["psychological", "support", "distress", "trauma", "listen"]
            }
        }
    
    def verify_file_checksums(self) -> Dict[str, Any]:
        """Verify checksums of raw document files.
        
        Returns:
            Checksum verification results
        """
        logger.info("🔍 Verifying file checksums...")
        
        results = {
            "verified": True,
            "files": {},
            "issues": []
        }
        
        # Load stored checksums
        checksums_file = self.raw_dir / "document_checksums.json"
        stored_checksums = {}
        
        if checksums_file.exists():
            try:
                with open(checksums_file, 'r') as f:
                    stored_checksums = json.load(f)
            except Exception as e:
                results["issues"].append(f"Could not load checksums file: {e}")
        
        # Check each file in raw directory
        for file_path in self.raw_dir.glob("*.pdf"):
            if file_path.name == "document_checksums.json":
                continue
            
            try:
                # Calculate current checksum
                current_hash = self._calculate_file_hash(file_path)
                
                # Find corresponding stored checksum
                stored_hash = None
                for doc_key, hash_value in stored_checksums.items():
                    # Match by filename pattern
                    if any(keyword in file_path.name.lower() for keyword in doc_key.split("_")):
                        stored_hash = hash_value
                        break
                
                file_result = {
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "current_hash": current_hash,
                    "stored_hash": stored_hash,
                    "verified": stored_hash is None or current_hash == stored_hash
                }
                
                if not file_result["verified"]:
                    results["verified"] = False
                    results["issues"].append(f"Checksum mismatch for {file_path.name}")
                
                results["files"][file_path.name] = file_result
                
            except Exception as e:
                results["verified"] = False
                results["issues"].append(f"Error verifying {file_path.name}: {e}")
        
        logger.info(f"✅ Checksum verification: {len(results['files'])} files checked")
        if results["issues"]:
            for issue in results["issues"]:
                logger.warning(f"⚠️  {issue}")
        
        return results
    
    def verify_database_integrity(self) -> Dict[str, Any]:
        """Verify database structure and content integrity.
        
        Returns:
            Database integrity results
        """
        logger.info("🔍 Verifying database integrity...")
        
        results = {
            "verified": True,
            "database": {},
            "documents": {},
            "issues": []
        }
        
        try:
            if not self.db_path.exists():
                results["verified"] = False
                results["issues"].append(f"Database file not found: {self.db_path}")
                return results
            
            # Connect to database
            db = CorpusDatabase(str(self.db_path))
            
            # Get basic statistics
            stats = db.get_stats()
            results["database"]["stats"] = stats
            
            if stats["documents"] == 0:
                results["verified"] = False
                results["issues"].append("No documents found in database")
            
            if stats["chunks"] == 0:
                results["verified"] = False
                results["issues"].append("No text chunks found in database")
            
            # Verify each document
            documents = db.list_documents()
            
            for doc in documents:
                doc_id = doc["doc_id"]
                doc_result = self._verify_document_integrity(db, doc)
                results["documents"][doc_id] = doc_result
                
                if not doc_result["verified"]:
                    results["verified"] = False
                    results["issues"].extend(doc_result["issues"])
            
            # Test search functionality
            search_test = self._test_search_functionality(db)
            results["search_test"] = search_test
            
            if not search_test["functional"]:
                results["verified"] = False
                results["issues"].append("Search functionality not working")
            
            db.close()
            
        except Exception as e:
            results["verified"] = False
            results["issues"].append(f"Database verification failed: {e}")
        
        logger.info(f"✅ Database integrity: {len(results['documents'])} documents verified")
        if results["issues"]:
            for issue in results["issues"]:
                logger.warning(f"⚠️  {issue}")
        
        return results
    
    def verify_content_quality(self) -> Dict[str, Any]:
        """Verify quality and completeness of ingested content.
        
        Returns:
            Content quality results
        """
        logger.info("🔍 Verifying content quality...")
        
        results = {
            "verified": True,
            "content_analysis": {},
            "coverage": {},
            "issues": []
        }
        
        try:
            db = CorpusDatabase(str(self.db_path))
            
            # Analyze each expected document
            for doc_pattern, expectations in self.expected_documents.items():
                doc_analysis = self._analyze_document_content(db, doc_pattern, expectations)
                results["content_analysis"][doc_pattern] = doc_analysis
                
                if not doc_analysis["meets_expectations"]:
                    results["verified"] = False
                    results["issues"].extend(doc_analysis["issues"])
            
            # Test keyword coverage
            coverage_test = self._test_keyword_coverage(db)
            results["coverage"] = coverage_test
            
            if coverage_test["missing_keywords"]:
                results["verified"] = False
                results["issues"].append(f"Missing expected keywords: {coverage_test['missing_keywords']}")
            
            db.close()
            
        except Exception as e:
            results["verified"] = False
            results["issues"].append(f"Content quality verification failed: {e}")
        
        logger.info(f"✅ Content quality verification completed")
        if results["issues"]:
            for issue in results["issues"]:
                logger.warning(f"⚠️  {issue}")
        
        return results
    
    def verify_search_performance(self) -> Dict[str, Any]:
        """Verify search performance and accuracy.
        
        Returns:
            Search performance results
        """
        logger.info("🔍 Verifying search performance...")
        
        results = {
            "verified": True,
            "performance": {},
            "accuracy": {},
            "issues": []
        }
        
        try:
            db = CorpusDatabase(str(self.db_path))
            
            # Performance test queries
            test_queries = [
                "emergency",
                "first aid",
                "bleeding",
                "burns",
                "CPR",
                "psychological support",
                "wound care",
                "fracture",
                "poisoning",
                "safety"
            ]
            
            search_times = []
            result_counts = []
            
            for query in test_queries:
                start_time = time.time()
                search_results = db.search(query, limit=10)
                search_time = time.time() - start_time
                
                search_times.append(search_time)
                result_counts.append(len(search_results))
                
                # Verify result quality
                for result in search_results:
                    if not self._validate_search_result(result, query):
                        results["issues"].append(f"Invalid search result for query '{query}'")
            
            # Calculate performance metrics
            avg_search_time = sum(search_times) / len(search_times)
            total_results = sum(result_counts)
            
            results["performance"] = {
                "avg_search_time": round(avg_search_time, 3),
                "total_results": total_results,
                "queries_tested": len(test_queries),
                "performance_threshold": 1.0  # 1 second threshold
            }
            
            # Check performance threshold
            if avg_search_time > 1.0:
                results["verified"] = False
                results["issues"].append(f"Search performance too slow: {avg_search_time:.3f}s > 1.0s")
            
            # Test search accuracy with specific scenarios
            accuracy_test = self._test_search_accuracy(db)
            results["accuracy"] = accuracy_test
            
            if not accuracy_test["accurate"]:
                results["verified"] = False
                results["issues"].extend(accuracy_test["issues"])
            
            db.close()
            
        except Exception as e:
            results["verified"] = False
            results["issues"].append(f"Search performance verification failed: {e}")
        
        logger.info(f"✅ Search performance: {results['performance'].get('avg_search_time', 0):.3f}s average")
        if results["issues"]:
            for issue in results["issues"]:
                logger.warning(f"⚠️  {issue}")
        
        return results
    
    def run_full_verification(self) -> Dict[str, Any]:
        """Run complete corpus verification.
        
        Returns:
            Complete verification results
        """
        logger.info("🔥 Starting comprehensive corpus verification")
        logger.info("=" * 60)
        
        verification_results = {
            "timestamp": time.time(),
            "overall_verified": True,
            "checksum_verification": {},
            "database_integrity": {},
            "content_quality": {},
            "search_performance": {},
            "summary": {
                "total_checks": 4,
                "passed_checks": 0,
                "failed_checks": 0
            },
            "all_issues": []
        }
        
        # Run verification steps
        verification_steps = [
            ("checksum_verification", self.verify_file_checksums),
            ("database_integrity", self.verify_database_integrity),
            ("content_quality", self.verify_content_quality),
            ("search_performance", self.verify_search_performance)
        ]
        
        for step_name, step_func in verification_steps:
            try:
                logger.info(f"\n📋 Running {step_name.replace('_', ' ')}...")
                step_result = step_func()
                verification_results[step_name] = step_result
                
                if step_result["verified"]:
                    verification_results["summary"]["passed_checks"] += 1
                    logger.info(f"✅ {step_name}: PASSED")
                else:
                    verification_results["summary"]["failed_checks"] += 1
                    verification_results["overall_verified"] = False
                    logger.error(f"❌ {step_name}: FAILED")
                    
                    # Collect issues
                    step_issues = step_result.get("issues", [])
                    verification_results["all_issues"].extend([f"{step_name}: {issue}" for issue in step_issues])
                
            except Exception as e:
                logger.error(f"❌ {step_name}: ERROR - {e}")
                verification_results["summary"]["failed_checks"] += 1
                verification_results["overall_verified"] = False
                verification_results["all_issues"].append(f"{step_name}: {e}")
        
        # Generate summary
        summary = verification_results["summary"]
        success_rate = (summary["passed_checks"] / summary["total_checks"]) * 100
        
        logger.info("\n" + "=" * 60)
        logger.info("📊 CORPUS VERIFICATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total checks: {summary['total_checks']}")
        logger.info(f"Passed: {summary['passed_checks']}")
        logger.info(f"Failed: {summary['failed_checks']}")
        logger.info(f"Success rate: {success_rate:.1f}%")
        
        if verification_results["overall_verified"]:
            logger.info("\n✅ Corpus verification PASSED! Corpus is ready for use.")
        else:
            logger.error("\n❌ Corpus verification FAILED! Issues found:")
            for issue in verification_results["all_issues"]:
                logger.error(f"  - {issue}")
        
        return verification_results
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def _verify_document_integrity(self, db: CorpusDatabase, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Verify integrity of a single document."""
        doc_id = doc["doc_id"]
        
        result = {
            "verified": True,
            "doc_info": doc,
            "chunks": {},
            "issues": []
        }
        
        try:
            # Get document chunks
            chunks = db.get_document_chunks(doc_id)
            
            if not chunks:
                result["verified"] = False
                result["issues"].append("No chunks found")
                return result
            
            result["chunks"]["count"] = len(chunks)
            result["chunks"]["total_chars"] = sum(len(chunk["text"]) for chunk in chunks)
            
            # Check for gaps in offsets
            sorted_chunks = sorted(chunks, key=lambda x: x["start_offset"])
            gaps = []
            
            for i in range(1, len(sorted_chunks)):
                prev_end = sorted_chunks[i-1]["end_offset"]
                curr_start = sorted_chunks[i]["start_offset"]
                
                if curr_start > prev_end + 100:  # Allow some overlap
                    gaps.append(f"Gap between chunks {i-1} and {i}")
            
            if gaps:
                result["verified"] = False
                result["issues"].extend(gaps)
            
            # Check for empty chunks
            empty_chunks = [c for c in chunks if not c["text"].strip()]
            if empty_chunks:
                result["verified"] = False
                result["issues"].append(f"{len(empty_chunks)} empty chunks found")
            
            # Check chunk text quality
            very_short_chunks = [c for c in chunks if len(c["text"]) < 50]
            if len(very_short_chunks) > len(chunks) * 0.3:  # More than 30% very short
                result["verified"] = False
                result["issues"].append(f"Too many very short chunks: {len(very_short_chunks)}")
            
        except Exception as e:
            result["verified"] = False
            result["issues"].append(f"Error verifying document: {e}")
        
        return result
    
    def _test_search_functionality(self, db: CorpusDatabase) -> Dict[str, Any]:
        """Test basic search functionality."""
        result = {
            "functional": True,
            "test_results": {},
            "issues": []
        }
        
        test_queries = ["emergency", "first aid", "help"]
        
        for query in test_queries:
            try:
                search_results = db.search(query, limit=5)
                result["test_results"][query] = len(search_results)
                
                # Validate result structure
                for search_result in search_results:
                    required_fields = ["doc_id", "text", "page_number"]
                    for field in required_fields:
                        if field not in search_result:
                            result["functional"] = False
                            result["issues"].append(f"Missing field '{field}' in search result")
                            
            except Exception as e:
                result["functional"] = False
                result["issues"].append(f"Search failed for '{query}': {e}")
        
        return result
    
    def _analyze_document_content(self, db: CorpusDatabase, doc_pattern: str, expectations: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze content of a specific document."""
        result = {
            "meets_expectations": True,
            "found_document": None,
            "analysis": {},
            "issues": []
        }
        
        # Find matching document
        documents = db.list_documents()
        matching_docs = []
        
        for doc in documents:
            title_lower = doc["title"].lower()
            if any(keyword.lower() in title_lower for keyword in expectations["title_contains"]):
                matching_docs.append(doc)
        
        if not matching_docs:
            result["meets_expectations"] = False
            result["issues"].append(f"No document found matching pattern: {doc_pattern}")
            return result
        
        # Use first matching document
        doc = matching_docs[0]
        result["found_document"] = doc
        
        # Get chunks and analyze
        chunks = db.get_document_chunks(doc["doc_id"])
        
        if len(chunks) < expectations["min_chunks"]:
            result["meets_expectations"] = False
            result["issues"].append(f"Too few chunks: {len(chunks)} < {expectations['min_chunks']}")
        
        # Check for expected keywords
        all_text = " ".join(chunk["text"].lower() for chunk in chunks)
        missing_keywords = []
        
        for keyword in expectations["expected_keywords"]:
            if keyword.lower() not in all_text:
                missing_keywords.append(keyword)
        
        if missing_keywords:
            result["meets_expectations"] = False
            result["issues"].append(f"Missing keywords: {missing_keywords}")
        
        result["analysis"] = {
            "chunks": len(chunks),
            "total_chars": len(all_text),
            "found_keywords": [kw for kw in expectations["expected_keywords"] if kw.lower() in all_text],
            "missing_keywords": missing_keywords
        }
        
        return result
    
    def _test_keyword_coverage(self, db: CorpusDatabase) -> Dict[str, Any]:
        """Test coverage of important emergency keywords."""
        important_keywords = [
            "emergency", "first aid", "bleeding", "burns", "CPR", "wound", "fracture",
            "poisoning", "unconscious", "breathing", "pulse", "bandage", "pressure",
            "psychological", "support", "trauma", "distress", "listen", "comfort"
        ]
        
        result = {
            "total_keywords": len(important_keywords),
            "found_keywords": [],
            "missing_keywords": [],
            "keyword_results": {}
        }
        
        for keyword in important_keywords:
            search_results = db.search(keyword, limit=1)
            
            if search_results:
                result["found_keywords"].append(keyword)
                result["keyword_results"][keyword] = len(search_results)
            else:
                result["missing_keywords"].append(keyword)
                result["keyword_results"][keyword] = 0
        
        result["coverage_percentage"] = (len(result["found_keywords"]) / len(important_keywords)) * 100
        
        return result
    
    def _test_search_accuracy(self, db: CorpusDatabase) -> Dict[str, Any]:
        """Test search result accuracy and relevance."""
        result = {
            "accurate": True,
            "test_cases": {},
            "issues": []
        }
        
        # Test cases with expected result characteristics
        test_cases = [
            {
                "query": "bleeding",
                "expected_terms": ["blood", "pressure", "wound", "bandage"],
                "min_results": 1
            },
            {
                "query": "burns",
                "expected_terms": ["cool", "water", "skin", "heat"],
                "min_results": 1
            },
            {
                "query": "CPR",
                "expected_terms": ["chest", "compression", "breathing", "rescue"],
                "min_results": 1
            }
        ]
        
        for test_case in test_cases:
            query = test_case["query"]
            search_results = db.search(query, limit=5)
            
            case_result = {
                "results_count": len(search_results),
                "meets_min_results": len(search_results) >= test_case["min_results"],
                "relevant_results": 0
            }
            
            # Check relevance
            for search_result in search_results:
                text_lower = search_result["text"].lower()
                if any(term in text_lower for term in test_case["expected_terms"]):
                    case_result["relevant_results"] += 1
            
            case_result["relevance_rate"] = (case_result["relevant_results"] / max(1, len(search_results))) * 100
            
            if not case_result["meets_min_results"]:
                result["accurate"] = False
                result["issues"].append(f"Query '{query}' returned too few results: {len(search_results)}")
            
            if case_result["relevance_rate"] < 50:  # Less than 50% relevant
                result["accurate"] = False
                result["issues"].append(f"Query '{query}' has low relevance: {case_result['relevance_rate']:.1f}%")
            
            result["test_cases"][query] = case_result
        
        return result
    
    def _validate_search_result(self, result: Dict[str, Any], query: str) -> bool:
        """Validate structure and content of search result."""
        required_fields = ["doc_id", "text", "page_number"]
        
        # Check required fields
        for field in required_fields:
            if field not in result:
                return False
        
        # Check field types and values
        if not isinstance(result["text"], str) or not result["text"].strip():
            return False
        
        if not isinstance(result["page_number"], (int, type(None))):
            return False
        
        return True


def main():
    """Main entry point for corpus verification."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Verify Campfire corpus integrity")
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=Path("corpus"),
        help="Directory containing corpus files (default: corpus)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Save verification results to file"
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
        # Initialize and run verification
        verifier = CorpusVerifier(args.corpus_dir)
        results = verifier.run_full_verification()
        
        # Save results if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info(f"📄 Verification results saved to {args.output}")
        
        # Return appropriate exit code
        if results["overall_verified"]:
            return 0
        else:
            return 1
            
    except Exception as e:
        logger.error(f"Fatal error in corpus verification: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())