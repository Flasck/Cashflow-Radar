#!/usr/bin/env python3
"""
Cashflow Radar - Integration HTTP Acceptance Test Runner
Tests actual API endpoints, cookie/CSRF protection, M:N memberships, tenant isolation,
transaction edits, decimal arithmetic, CSV/XLSX imports, forecast cutoffs, and gRPC engine.
"""

import argparse
import os
import sys
import time
import unittest
import urllib.error
import urllib.request

# Ensure workspace root is in python path
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from tests.test_api_acceptance import CashflowRadarAcceptanceTest


def check_server_available(base_url: str, timeout: float = 3.0) -> bool:
    """Probes /api/health or root endpoint with short timeout."""
    test_urls = [f"{base_url}/api/health", f"{base_url}/health", base_url]
    for url in test_urls:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status < 500:
                    return True
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            ConnectionRefusedError,
        ):
            continue
    return False


class CompactTestResult(unittest.TextTestResult):
    """Formats test results with compact labels and sanitized error messages."""

    def getDescription(self, test):
        doc = test.shortDescription()
        if doc:
            return doc
        return f"{test.__class__.__name__}.{test._testMethodName}"

    def printErrors(self):
        if self.dots or self.showAll:
            self.stream.writeln()
        self.printErrorList("ERROR", self.errors)
        self.printErrorList("FAIL", self.failures)

    def printErrorList(self, flavour, errors):
        for test, err in errors:
            self.stream.writeln(self.separator1)
            self.stream.writeln(f"{flavour}: {self.getDescription(test)}")
            self.stream.writeln(self.separator2)
            # Print only relevant failure line, not giant traceback
            lines = err.strip().splitlines()
            short_msg = lines[-1] if lines else "Unknown error"
            self.stream.writeln(f"  Reason: {short_msg}")


class CompactTestRunner(unittest.TextTestRunner):
    resultclass = CompactTestResult


def main():
    parser = argparse.ArgumentParser(
        description="Run HTTP acceptance tests against Cashflow Radar backend."
    )
    parser.add_argument(
        "-u",
        "--url",
        default=os.getenv("API_BASE_URL", "http://localhost:8000"),
        help="Backend base URL (default: http://localhost:8000 or $API_BASE_URL)",
    )
    parser.add_argument(
        "-o",
        "--origin",
        default=os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"),
        help="Frontend Origin header (default: http://localhost:3000 or $FRONTEND_ORIGIN)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose full trace output",
    )
    parser.add_argument(
        "-k",
        "--test",
        default=None,
        help="Filter specific test name or pattern (e.g. 'AUTH', 'TENANT', 'IMPORT', 'FORECAST')",
    )
    parser.add_argument(
        "--no-probe",
        action="store_true",
        help="Skip pre-flight server availability probe",
    )

    args = parser.parse_args()
    base_url = args.url.rstrip("/")
    origin = args.origin.rstrip("/")

    CashflowRadarAcceptanceTest.base_url = base_url
    CashflowRadarAcceptanceTest.origin = origin

    run_id = CashflowRadarAcceptanceTest.run_id
    prefix = CashflowRadarAcceptanceTest.prefix

    print("=" * 70)
    print(" Cashflow Radar HTTP Acceptance Test Suite")
    print("=" * 70)
    print(f" Run ID       : {run_id}")
    print(f" Prefix       : {prefix}")
    print(f" Target API   : {base_url}")
    print(f" Origin       : {origin}")
    print("=" * 70)

    if not args.no_probe:
        print(f"[*] Checking connection to {base_url}...")
        if not check_server_available(base_url):
            print(f"[!] Warning: Backend at {base_url} is not responding.")
            print(
                "    Ensure backend server is running (e.g. uvicorn backend.app.main:app --port 8000)."
            )
            print(
                "    Proceeding with tests (requests will report connection errors)..."
            )
        else:
            print("[+] Backend server is reachable.")

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName("tests.test_api_acceptance")

    if args.test:
        filtered = unittest.TestSuite()
        for test_case in suite:
            if isinstance(test_case, unittest.TestSuite):
                for t in test_case:
                    desc = t.shortDescription() or str(t)
                    if (
                        args.test.lower() in desc.lower()
                        or args.test.lower() in str(t).lower()
                    ):
                        filtered.addTest(t)
            else:
                desc = test_case.shortDescription() or str(test_case)
                if (
                    args.test.lower() in desc.lower()
                    or args.test.lower() in str(test_case).lower()
                ):
                    filtered.addTest(test_case)
        suite = filtered

    runner_class = unittest.TextTestRunner if args.verbose else CompactTestRunner
    runner = runner_class(
        stream=sys.stdout,
        verbosity=2,
        failfast=False,
    )

    start_time = time.time()
    result = runner.run(suite)
    elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print(f" Test Summary (Duration: {elapsed:.2f}s)")
    print("=" * 70)
    print(f" Tests run    : {result.testsRun}")
    print(
        f" Passed       : {result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)}"
    )
    print(f" Failures     : {len(result.failures)}")
    print(f" Errors       : {len(result.errors)}")
    print(f" Skipped      : {len(result.skipped)}")
    print(
        f" Cleaned up   : {CashflowRadarAcceptanceTest.cleaned_tx_count} transactions, "
        f"{CashflowRadarAcceptanceTest.cleaned_cat_count} categories"
    )
    print(
        f" Revoked      : {CashflowRadarAcceptanceTest.revoked_inv_count} pending invitations; history retained"
    )
    print(f" Demo Fixture : Retained user/company prefix '{prefix}' (run ID: {run_id})")
    print("=" * 70)

    if result.wasSuccessful():
        print("[+] ALL ACCEPTANCE CHECKS PASSED.")
        sys.exit(0)
    else:
        print("[-] ACCEPTANCE CHECKS FAILED.")
        sys.exit(1)


if __name__ == "__main__":
    main()
