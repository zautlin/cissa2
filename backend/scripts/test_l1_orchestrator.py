#!/usr/bin/env python3
"""
Test script for L1 Metrics Orchestrator API

This script tests the orchestrator endpoint and measures performance.

Usage:
    python test_l1_orchestrator.py --dataset-id <uuid> --param-set-id <uuid> [--api-url http://localhost:8000]

Example:
    python test_l1_orchestrator.py \
      --dataset-id 523eeffd-9220-4d27-927b-e418f9c21d8a \
      --param-set-id 71a0caa6-b52c-4c5e-b550-1048b7329719
"""

import requests
import json
import argparse
import sys
import time
from datetime import datetime


def print_header(text):
    """Print a formatted header"""
    print(f"\n{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}")


def print_phase_result(phase_name, phase_data):
    """Print results for a single phase"""
    print(f"\n{phase_name}:")
    print(f"  Status:        {phase_data.get('status', 'unknown').upper()}")
    print(f"  Metrics:       {phase_data.get('successful', 0)}/{phase_data.get('metrics', 0)} successful")
    print(f"  Time:          {phase_data.get('time_seconds', 0):.1f}s")
    print(f"  Records:       {phase_data.get('records_inserted', 0):,}")
    if phase_data.get('failed', 0) > 0:
        print(f"  Failed:        {phase_data.get('failed', 0)} metrics")


def test_orchestrator(dataset_id, param_set_id, api_url="http://localhost:8000"):
    """Test the L1 metrics orchestrator endpoint"""
    
    print_header("L1 Metrics Orchestrator API Test")
    print(f"Timestamp:     {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"API URL:       {api_url}")
    print(f"Dataset ID:    {dataset_id}")
    print(f"Param Set ID:  {param_set_id}")
    
    # Prepare request
    endpoint = f"{api_url}/api/v1/metrics/calculate-l1"
    payload = {
        "dataset_id": dataset_id,
        "param_set_id": param_set_id,
        "concurrency": 4,
        "max_retries": 3,
    }
    
    print(f"\nSending POST request to: {endpoint}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    # Make request
    print_header("Waiting for orchestrator...")
    start_time = time.time()
    
    try:
        response = requests.post(
            endpoint,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=600  # 10 minute timeout
        )
        
        request_time = time.time() - start_time
        
        if response.status_code != 200:
            print(f"\n❌ ERROR: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        result = response.json()
        
        print_header("Orchestration Results")
        
        print(f"\nOverall Status:        {'✓ SUCCESS' if result.get('success') else '✗ FAILED'}")
        print(f"Total Execution Time:  {result.get('execution_time_seconds', 0):.1f}s")
        print(f"Request Round-Trip:    {request_time:.1f}s")
        print(f"Timestamp:             {result.get('timestamp', 'N/A')}")
        
        print(f"\nMetrics Summary:")
        print(f"  Total Successful:      {result.get('total_successful', 0)}/17")
        print(f"  Total Failed:          {result.get('total_failed', 0)}/17")
        print(f"  Total Records:         {result.get('total_records_inserted', 0):,}")
        
        # Phase breakdown
        print_header("Phase Breakdown")
        phases = result.get('phases', {})
        print_phase_result("Phase 1: Basic Metrics (12 metrics, parallelized)", phases.get('phase_1', {}))
        print_phase_result("Phase 2: Beta (1 metric, sequential)", phases.get('phase_2', {}))
        print_phase_result("Phase 3: Cost of Equity (1 metric, depends on Phase 2)", phases.get('phase_3', {}))
        print_phase_result("Phase 4: Risk-Free Rate (1 metric, sequential)", phases.get('phase_4', {}))
        
        # Errors
        errors = result.get('errors', [])
        if errors:
            print_header("Errors")
            for i, error in enumerate(errors, 1):
                print(f"  {i}. {error}")
        
        # Performance analysis
        print_header("Performance Analysis")
        total_time = result.get('execution_time_seconds', 0)
        phase_1_time = phases.get('phase_1', {}).get('time_seconds', 0)
        phase_2_time = phases.get('phase_2', {}).get('time_seconds', 0)
        phase_3_time = phases.get('phase_3', {}).get('time_seconds', 0)
        phase_4_time = phases.get('phase_4', {}).get('time_seconds', 0)
        
        print(f"Phase 1 (parallelized):  {phase_1_time:.1f}s ({phase_1_time/total_time*100:.0f}%)")
        print(f"Phase 2 (sequential):    {phase_2_time:.1f}s ({phase_2_time/total_time*100:.0f}%)")
        print(f"Phase 3 (sequential):    {phase_3_time:.1f}s ({phase_3_time/total_time*100:.0f}%)")
        print(f"Phase 4 (sequential):    {phase_4_time:.1f}s ({phase_4_time/total_time*100:.0f}%)")
        print(f"Total:                   {total_time:.1f}s")
        
        # Target analysis
        print_header("Performance Target")
        print(f"Target Execution Time:   <60 seconds")
        print(f"Actual Execution Time:   {total_time:.1f}s")
        if total_time < 60:
            print(f"Status:                  ✓ PASSED (within target)")
        else:
            print(f"Status:                  ⚠ EXCEEDED (outside target)")
        
        print_header("Test Complete")
        
        return result.get('success', False)
    
    except requests.exceptions.Timeout:
        print(f"\n❌ ERROR: Request timeout (10 minutes)")
        return False
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ ERROR: Connection failed: {e}")
        print(f"Make sure the API is running at {api_url}")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Test L1 Metrics Orchestrator API endpoint",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with default API URL
  python test_l1_orchestrator.py \
    --dataset-id 523eeffd-9220-4d27-927b-e418f9c21d8a \
    --param-set-id 71a0caa6-b52c-4c5e-b550-1048b7329719

  # Test with custom API URL
  python test_l1_orchestrator.py \
    --dataset-id 523eeffd-9220-4d27-927b-e418f9c21d8a \
    --param-set-id 71a0caa6-b52c-4c5e-b550-1048b7329719 \
    --api-url http://localhost:8000
        """
    )
    
    parser.add_argument(
        "--dataset-id",
        required=True,
        help="Dataset ID (UUID)",
    )
    parser.add_argument(
        "--param-set-id",
        required=True,
        help="Parameter Set ID (UUID)",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="Base API URL (default: http://localhost:8000)",
    )
    
    args = parser.parse_args()
    
    success = test_orchestrator(
        dataset_id=args.dataset_id,
        param_set_id=args.param_set_id,
        api_url=args.api_url,
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
