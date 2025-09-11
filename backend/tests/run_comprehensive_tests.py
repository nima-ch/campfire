#!/usr/bin/env python3
"""
Comprehensive test runner for Campfire emergency helper.

Runs all test suites including offline validation, emergency scenarios,
citation accuracy, safety critic integration, performance, and end-to-end tests.
"""

import sys
import subprocess
import time
import argparse
from pathlib import Path
from typing import List, Dict, Any


class TestRunner:
    """Comprehensive test runner with reporting."""
    
    def __init__(self, verbose: bool = False, fast: bool = False):
        self.verbose = verbose
        self.fast = fast
        self.results: Dict[str, Any] = {}
        
    def run_test_suite(self, name: str, test_file: str, markers: List[str] = None) -> Dict[str, Any]:
        """Run a specific test suite and return results."""
        print(f"\n{'='*60}")
        print(f"Running {name}")
        print(f"{'='*60}")
        
        cmd = ["python", "-m", "pytest", test_file, "-v"]
        
        if markers:
            for marker in markers:
                cmd.extend(["-m", marker])
        
        if self.fast:
            cmd.extend(["-m", "not slow"])
        
        if self.verbose:
            cmd.append("-s")
        
        # Add coverage reporting
        cmd.extend(["--cov=campfire", "--cov-report=term-missing"])
        
        start_time = time.time()
        
        try:
            # Set working directory to project root
            project_root = Path(__file__).parent.parent.parent
            result = subprocess.run(
                cmd,
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout per test suite
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            success = result.returncode == 0
            
            test_result = {
                "name": name,
                "success": success,
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
            
            if success:
                print(f"✅ {name} PASSED ({duration:.2f}s)")
            else:
                print(f"❌ {name} FAILED ({duration:.2f}s)")
                if self.verbose:
                    print("STDOUT:", result.stdout)
                    print("STDERR:", result.stderr)
            
            return test_result
            
        except subprocess.TimeoutExpired:
            print(f"⏰ {name} TIMEOUT (>300s)")
            return {
                "name": name,
                "success": False,
                "duration": 300,
                "error": "Timeout",
                "returncode": -1
            }
        
        except Exception as e:
            print(f"💥 {name} ERROR: {e}")
            return {
                "name": name,
                "success": False,
                "duration": 0,
                "error": str(e),
                "returncode": -1
            }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all comprehensive test suites."""
        print("🚀 Starting Comprehensive Test Suite for Campfire Emergency Helper")
        print(f"Fast mode: {self.fast}")
        print(f"Verbose: {self.verbose}")
        
        overall_start = time.time()
        
        # Define test suites
        test_suites = [
            {
                "name": "Offline Validation Tests",
                "file": "backend/tests/test_offline_validation.py",
                "description": "Tests airplane mode functionality and network isolation"
            },
            {
                "name": "Emergency Scenario Tests", 
                "file": "backend/tests/test_emergency_scenarios.py",
                "description": "Tests specific emergency scenarios (burns, bleeding, etc.)"
            },
            {
                "name": "Citation Accuracy Tests",
                "file": "backend/tests/test_citation_accuracy.py", 
                "description": "Tests source linking and citation validation"
            },
            {
                "name": "Safety Critic Integration Tests",
                "file": "backend/tests/test_safety_critic_integration.py",
                "description": "Tests safety critic blocking inappropriate responses"
            },
            {
                "name": "Performance Tests",
                "file": "backend/tests/test_performance.py",
                "description": "Tests response time and resource usage",
                "markers": ["not slow"] if self.fast else None
            },
            {
                "name": "End-to-End Tests",
                "file": "backend/tests/test_end_to_end.py",
                "description": "Tests complete user workflows"
            },
            {
                "name": "Existing API Tests",
                "file": "backend/tests/test_api/test_main.py",
                "description": "Existing API integration tests"
            },
            {
                "name": "Existing Corpus Tests", 
                "file": "backend/tests/test_corpus/test_integration.py",
                "description": "Existing corpus system tests"
            },
            {
                "name": "Existing Critic Tests",
                "file": "backend/tests/test_critic/test_integration.py",
                "description": "Existing safety critic tests"
            }
        ]
        
        results = []
        
        for suite in test_suites:
            result = self.run_test_suite(
                suite["name"],
                suite["file"], 
                suite.get("markers")
            )
            results.append(result)
        
        overall_end = time.time()
        overall_duration = overall_end - overall_start
        
        # Generate summary report
        self.generate_summary_report(results, overall_duration)
        
        return {
            "results": results,
            "overall_duration": overall_duration,
            "total_suites": len(results),
            "passed_suites": sum(1 for r in results if r["success"]),
            "failed_suites": sum(1 for r in results if not r["success"])
        }
    
    def generate_summary_report(self, results: List[Dict[str, Any]], overall_duration: float):
        """Generate comprehensive summary report."""
        print(f"\n{'='*80}")
        print("COMPREHENSIVE TEST SUMMARY REPORT")
        print(f"{'='*80}")
        
        passed = [r for r in results if r["success"]]
        failed = [r for r in results if not r["success"]]
        
        print(f"Overall Duration: {overall_duration:.2f} seconds")
        print(f"Total Test Suites: {len(results)}")
        print(f"Passed: {len(passed)} ✅")
        print(f"Failed: {len(failed)} ❌")
        print(f"Success Rate: {len(passed)/len(results)*100:.1f}%")
        
        if passed:
            print(f"\n✅ PASSED SUITES ({len(passed)}):")
            for result in passed:
                print(f"  • {result['name']} ({result['duration']:.2f}s)")
        
        if failed:
            print(f"\n❌ FAILED SUITES ({len(failed)}):")
            for result in failed:
                duration = result.get('duration', 0)
                error = result.get('error', f"Exit code {result.get('returncode', 'unknown')}")
                print(f"  • {result['name']} ({duration:.2f}s) - {error}")
        
        # Performance summary
        print(f"\n⏱️  PERFORMANCE SUMMARY:")
        total_test_time = sum(r['duration'] for r in results)
        avg_suite_time = total_test_time / len(results)
        print(f"  • Total Test Time: {total_test_time:.2f}s")
        print(f"  • Average Suite Time: {avg_suite_time:.2f}s")
        print(f"  • Overhead Time: {overall_duration - total_test_time:.2f}s")
        
        # Requirements coverage
        print(f"\n📋 REQUIREMENTS COVERAGE:")
        print("  • Requirement 2.1-2.4 (Offline Operation): Offline Validation Tests")
        print("  • Requirement 3.1-3.3 (Safety): Safety Critic Integration Tests")
        print("  • Emergency Scenarios: Emergency Scenario Tests")
        print("  • Citation Accuracy: Citation Accuracy Tests")
        print("  • Performance: Performance Tests")
        print("  • Complete Workflows: End-to-End Tests")
        
        if len(failed) == 0:
            print(f"\n🎉 ALL TESTS PASSED! Campfire is ready for deployment.")
        else:
            print(f"\n⚠️  {len(failed)} test suite(s) failed. Review failures before deployment.")
        
        print(f"{'='*80}")
    
    def run_frontend_tests(self) -> Dict[str, Any]:
        """Run frontend tests."""
        print(f"\n{'='*60}")
        print("Running Frontend Tests")
        print(f"{'='*60}")
        
        frontend_dir = Path(__file__).parent.parent.parent / "frontend"
        
        if not frontend_dir.exists():
            print("⚠️  Frontend directory not found, skipping frontend tests")
            return {"success": False, "error": "Frontend directory not found"}
        
        cmd = ["npm", "test", "--", "--coverage", "--watchAll=false"]
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=frontend_dir,
                capture_output=True,
                text=True,
                timeout=180  # 3 minute timeout
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            success = result.returncode == 0
            
            if success:
                print(f"✅ Frontend Tests PASSED ({duration:.2f}s)")
            else:
                print(f"❌ Frontend Tests FAILED ({duration:.2f}s)")
                if self.verbose:
                    print("STDOUT:", result.stdout)
                    print("STDERR:", result.stderr)
            
            return {
                "success": success,
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            
        except subprocess.TimeoutExpired:
            print("⏰ Frontend Tests TIMEOUT (>180s)")
            return {"success": False, "error": "Timeout"}
        
        except Exception as e:
            print(f"💥 Frontend Tests ERROR: {e}")
            return {"success": False, "error": str(e)}


def main():
    """Main test runner entry point."""
    parser = argparse.ArgumentParser(description="Comprehensive test runner for Campfire")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-f", "--fast", action="store_true", help="Skip slow tests")
    parser.add_argument("--frontend", action="store_true", help="Also run frontend tests")
    parser.add_argument("--suite", help="Run specific test suite only")
    
    args = parser.parse_args()
    
    runner = TestRunner(verbose=args.verbose, fast=args.fast)
    
    if args.suite:
        # Run specific suite
        suite_path = args.suite if args.suite.startswith("backend/tests/") else f"backend/tests/{args.suite}"
        result = runner.run_test_suite(args.suite, suite_path)
        sys.exit(0 if result["success"] else 1)
    
    # Run all backend tests
    results = runner.run_all_tests()
    
    # Run frontend tests if requested
    if args.frontend:
        frontend_result = runner.run_frontend_tests()
        results["frontend"] = frontend_result
    
    # Exit with appropriate code
    if results["failed_suites"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()