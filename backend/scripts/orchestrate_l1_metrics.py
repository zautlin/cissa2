#!/usr/bin/env python3
"""
L1 Metrics Orchestrator - Parallelized Metric Calculation
========================================================

Orchestrates L1 metric calculations across 4 phases with:
- Phase 1: Basic metrics (12 metrics) - parallelized in 4 groups
- Phase 2: Beta calculation (1 metric) - sequential
- Phase 3: Cost of Equity (2 metrics) - sequential (depends on Beta)
- Phase 4: Risk-Free Rate (2 metrics) - sequential

Uses asyncio with semaphore-limited concurrency (max 4 parallel requests).
Includes retry logic (exponential backoff, max 3 attempts) and error aggregation.

Usage:
    python orchestrate_l1_metrics.py --dataset-id <uuid> --param-set-id <uuid>

Example:
    python orchestrate_l1_metrics.py \
      --dataset-id 523eeffd-9220-4d27-927b-e418f9c21d8a \
      --param-set-id 71a0caa6-b52c-4c5e-b550-1048b7329719
"""

import asyncio
import httpx
import json
import argparse
import sys
import time
from datetime import datetime
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass


@dataclass
class PhaseResult:
    """Result of a single phase execution"""
    phase_name: str
    status: str  # "success", "partial", "failed"
    metrics: List[str]
    successful_metrics: List[str]
    failed_metrics: Dict[str, str]  # metric_name -> error message
    time_seconds: float
    records_inserted: int


class L1MetricsOrchestrator:
    """Orchestrates L1 metric calculations with parallelization and retry logic"""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        max_concurrency: int = 4,
        max_retries: int = 3,
        request_timeout: int = 300,
    ):
        self.base_url = base_url
        self.max_concurrency = max_concurrency
        self.max_retries = max_retries
        self.request_timeout = request_timeout
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def call_metric_api(
        self,
        endpoint: str,
        dataset_id: str,
        param_set_id: str,
        metric_name: str = None,
    ) -> Dict[str, Any]:
        """Call metric API endpoint with semaphore-limited concurrency"""
        url = f"{self.base_url}{endpoint}"
        payload = {
            "dataset_id": dataset_id,
            "param_set_id": param_set_id,
        }
        if metric_name:
            payload["metric_name"] = metric_name

        async with self.semaphore:
            for attempt in range(1, self.max_retries + 1):
                try:
                    async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                        response = await client.post(
                            url,
                            json=payload,
                            headers={"Content-Type": "application/json"},
                        )
                        response.raise_for_status()
                        return response.json()
                except Exception as e:
                    if attempt == self.max_retries:
                        raise
                    wait_time = 2 ** (attempt - 1)  # 1s, 2s, 4s
                    print(f"  ⚠ Retry attempt {attempt}/{self.max_retries - 1} in {wait_time}s...")
                    await asyncio.sleep(wait_time)

    async def run_phase_1_parallelized(
        self,
        dataset_id: str,
        param_set_id: str,
    ) -> PhaseResult:
        """
        Phase 1: Basic Metrics (12 metrics total)
        Parallelized in 4 groups of 3-4 metrics each
        """
        phase_start = time.time()
        print(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [PHASE 1] Starting basic metrics (12 metrics, 4 concurrent groups)...")

        # Group 1: Simple metrics (MC, Assets, OA)
        group_1_metrics = ["Calc MC", "Calc Assets", "Calc OA"]

        # Group 2: Operating costs (Op Cost, Non Op Cost, Tax Cost)
        group_2_metrics = ["Calc Op Cost", "Calc Non Op Cost", "Calc Tax Cost"]

        # Group 3: XO Cost and temporal metrics (XO Cost, ECF, Non Div ECF)
        group_3_metrics = ["Calc XO Cost", "Calc ECF", "Non Div ECF"]

        # Group 4: Equity and return metrics (EE, FY TSR, FY TSR PREL)
        group_4_metrics = ["Calc EE", "Calc FY TSR", "Calc FY TSR PREL"]

        groups = [group_1_metrics, group_2_metrics, group_3_metrics, group_4_metrics]

        successful_metrics = []
        failed_metrics = {}
        records_inserted = 0

        for group_idx, group_metrics in enumerate(groups, 1):
            group_start = time.time()
            metric_names = ", ".join(group_metrics)
            print(f"  Group {group_idx}/4 - Calculating {metric_names}...")

            tasks = [
                self.call_metric_api(
                    "/api/v1/metrics/calculate",
                    dataset_id,
                    param_set_id,
                    metric_name=metric_name,
                )
                for metric_name in group_metrics
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for metric_name, result in zip(group_metrics, results):
                if isinstance(result, Exception):
                    failed_metrics[metric_name] = str(result)
                    print(f"    ✗ {metric_name} - Failed: {str(result)[:60]}")
                elif isinstance(result, dict):
                    if result.get("status") == "error":
                        failed_metrics[metric_name] = result.get("message", "Unknown error")
                        print(
                            f"    ✗ {metric_name} - API Error: {result.get('message', 'Unknown')[:60]}"
                        )
                    else:
                        successful_metrics.append(metric_name)
                        count = result.get("results_count", 0)
                        records_inserted += count
                        print(f"    ✓ {metric_name} ({count} records)")
                else:
                    failed_metrics[metric_name] = "Invalid response format"
                    print(f"    ✗ {metric_name} - Invalid response format")

            group_time = time.time() - group_start
            print(f"  Group {group_idx}/4 - Completed in {group_time:.1f}s")

        phase_time = time.time() - phase_start
        all_metrics = [m for group in groups for m in group]
        status = "success" if len(failed_metrics) == 0 else ("partial" if len(successful_metrics) > 0 else "failed")

        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [PHASE 1] Completed in {phase_time:.1f}s - {len(successful_metrics)}/{len(all_metrics)} metrics successful")

        return PhaseResult(
            phase_name="Phase 1: Basic Metrics",
            status=status,
            metrics=all_metrics,
            successful_metrics=successful_metrics,
            failed_metrics=failed_metrics,
            time_seconds=phase_time,
            records_inserted=records_inserted,
        )

    async def run_phase_2_sequential(
        self,
        dataset_id: str,
        param_set_id: str,
    ) -> PhaseResult:
        """
        Phase 2: Beta Calculation (1 metric)
        Sequential only (single metric)
        """
        phase_start = time.time()
        print(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [PHASE 2] Starting beta calculation...")

        try:
            result = await self.call_metric_api(
                "/api/v1/metrics/beta/calculate",
                dataset_id,
                param_set_id,
            )

            if result.get("status") == "error":
                failed_metrics = {"Calc Beta": result.get("message", "Unknown error")}
                print(f"  ✗ Calc Beta - API Error: {result.get('message', 'Unknown')[:60]}")
                status = "failed"
                successful_metrics = []
                records_inserted = 0
            else:
                successful_metrics = ["Calc Beta"]
                failed_metrics = {}
                records_inserted = result.get("results_count", 0)
                print(f"  ✓ Calc Beta ({records_inserted} records)")
                status = "success"

        except Exception as e:
            failed_metrics = {"Calc Beta": str(e)}
            print(f"  ✗ Calc Beta - Failed: {str(e)[:60]}")
            status = "failed"
            successful_metrics = []
            records_inserted = 0

        phase_time = time.time() - phase_start
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [PHASE 2] Completed in {phase_time:.1f}s")

        return PhaseResult(
            phase_name="Phase 2: Beta",
            status=status,
            metrics=["Calc Beta"],
            successful_metrics=successful_metrics,
            failed_metrics=failed_metrics,
            time_seconds=phase_time,
            records_inserted=records_inserted,
        )

    async def run_phase_3_sequential(
        self,
        dataset_id: str,
        param_set_id: str,
        phase_2_result: PhaseResult,
    ) -> PhaseResult:
        """
        Phase 3: Cost of Equity (depends on Phase 2 Beta)
        Sequential only
        """
        phase_start = time.time()
        print(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [PHASE 3] Starting cost of equity calculation...")

        # Check Phase 2 dependency
        if "Calc Beta" not in phase_2_result.successful_metrics:
            print(f"  ⚠ Skipping Phase 3: Beta not available from Phase 2")
            return PhaseResult(
                phase_name="Phase 3: Cost of Equity",
                status="skipped",
                metrics=["Calc KE"],
                successful_metrics=[],
                failed_metrics={"Calc KE": "Phase 2 Beta dependency not met"},
                time_seconds=0,
                records_inserted=0,
            )

        try:
            result = await self.call_metric_api(
                "/api/v1/metrics/cost-of-equity/calculate",
                dataset_id,
                param_set_id,
            )

            if result.get("status") == "error":
                failed_metrics = {"Calc KE": result.get("message", "Unknown error")}
                print(f"  ✗ Calc KE - API Error: {result.get('message', 'Unknown')[:60]}")
                status = "failed"
                successful_metrics = []
                records_inserted = 0
            else:
                successful_metrics = ["Calc KE"]
                failed_metrics = {}
                records_inserted = result.get("results_count", 0)
                print(f"  ✓ Calc KE ({records_inserted} records)")
                status = "success"

        except Exception as e:
            failed_metrics = {"Calc KE": str(e)}
            print(f"  ✗ Calc KE - Failed: {str(e)[:60]}")
            status = "failed"
            successful_metrics = []
            records_inserted = 0

        phase_time = time.time() - phase_start
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [PHASE 3] Completed in {phase_time:.1f}s")

        return PhaseResult(
            phase_name="Phase 3: Cost of Equity",
            status=status,
            metrics=["Calc KE"],
            successful_metrics=successful_metrics,
            failed_metrics=failed_metrics,
            time_seconds=phase_time,
            records_inserted=records_inserted,
        )

    async def run_phase_4_sequential(
        self,
        dataset_id: str,
        param_set_id: str,
    ) -> PhaseResult:
        """
        Phase 4: Risk-Free Rate (2 metrics)
        Sequential only
        """
        phase_start = time.time()
        print(f"\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [PHASE 4] Starting risk-free rate calculation...")

        try:
            result = await self.call_metric_api(
                "/api/v1/metrics/rates/calculate",
                dataset_id,
                param_set_id,
            )

            if result.get("status") == "error":
                failed_metrics = {"Calc Rf": result.get("message", "Unknown error")}
                print(f"  ✗ Calc Rf - API Error: {result.get('message', 'Unknown')[:60]}")
                status = "failed"
                successful_metrics = []
                records_inserted = 0
            else:
                successful_metrics = ["Calc Rf"]
                failed_metrics = {}
                records_inserted = result.get("results_count", 0)
                print(f"  ✓ Calc Rf ({records_inserted} records)")
                status = "success"

        except Exception as e:
            failed_metrics = {"Calc Rf": str(e)}
            print(f"  ✗ Calc Rf - Failed: {str(e)[:60]}")
            status = "failed"
            successful_metrics = []
            records_inserted = 0

        phase_time = time.time() - phase_start
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [PHASE 4] Completed in {phase_time:.1f}s")

        return PhaseResult(
            phase_name="Phase 4: Risk-Free Rate",
            status=status,
            metrics=["Calc Rf"],
            successful_metrics=successful_metrics,
            failed_metrics=failed_metrics,
            time_seconds=phase_time,
            records_inserted=records_inserted,
        )

    async def orchestrate(
        self,
        dataset_id: str,
        param_set_id: str,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Orchestrate all 4 phases with proper sequencing
        Returns (success: bool, results: dict)
        """
        orchestration_start = time.time()

        print("\n" + "=" * 70)
        print("L1 Metrics Orchestrator - Full Execution")
        print("=" * 70)
        print(f"Dataset ID:    {dataset_id}")
        print(f"Param Set ID:  {param_set_id}")
        print(f"Concurrency:   {self.max_concurrency} parallel requests")
        print(f"Max Retries:   {self.max_retries} attempts per metric")
        print("=" * 70)

        results = {}

        # Phase 1: Parallelized basic metrics
        phase_1_result = await self.run_phase_1_parallelized(dataset_id, param_set_id)
        results["phase_1"] = phase_1_result

        # Phase 2: Sequential beta
        phase_2_result = await self.run_phase_2_sequential(dataset_id, param_set_id)
        results["phase_2"] = phase_2_result

        # Phase 3: Sequential cost of equity (depends on Phase 2)
        phase_3_result = await self.run_phase_3_sequential(dataset_id, param_set_id, phase_2_result)
        results["phase_3"] = phase_3_result

        # Phase 4: Sequential risk-free rate
        phase_4_result = await self.run_phase_4_sequential(dataset_id, param_set_id)
        results["phase_4"] = phase_4_result

        # Summary and final stats
        total_time = time.time() - orchestration_start
        total_successful = sum(len(r.successful_metrics) for r in results.values())
        total_failed = sum(len(r.failed_metrics) for r in results.values())
        total_records = sum(r.records_inserted for r in results.values())

        print("\n" + "=" * 70)
        print("Orchestration Summary")
        print("=" * 70)
        print(f"Total Execution Time:  {total_time:.1f}s")
        print(f"Phases Completed:      4/4")
        print(f"Metrics Successful:    {total_successful}/17")
        print(f"Metrics Failed:        {total_failed}/17")
        print(f"Records Inserted:      {total_records:,}")
        print("=" * 70)

        # Phase breakdown
        for phase_name, result in results.items():
            print(f"\n{result.phase_name}:")
            print(f"  Status:            {result.status.upper()}")
            print(f"  Metrics:           {len(result.successful_metrics)}/{len(result.metrics)} successful")
            print(f"  Time:              {result.time_seconds:.1f}s")
            print(f"  Records:           {result.records_inserted:,}")
            if result.failed_metrics:
                print(f"  Failed Metrics:")
                for metric, error in result.failed_metrics.items():
                    print(f"    - {metric}: {error[:50]}")

        print("\n" + "=" * 70)

        # Overall success: all phases completed (even if some metrics failed)
        overall_success = total_failed == 0
        if overall_success:
            print("✓ SUCCESS: All metrics calculated successfully!")
        else:
            print(f"⚠ PARTIAL: {total_failed} metrics failed. See details above.")

        print("=" * 70 + "\n")

        return overall_success, {
            "total_time_seconds": total_time,
            "total_successful": total_successful,
            "total_failed": total_failed,
            "total_records_inserted": total_records,
            "phases": results,
        }


async def main():
    parser = argparse.ArgumentParser(
        description="L1 Metrics Orchestrator - Parallelized metric calculation"
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
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Maximum concurrent requests (default: 4)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum retry attempts per metric (default: 3)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Request timeout in seconds (default: 300)",
    )

    args = parser.parse_args()

    orchestrator = L1MetricsOrchestrator(
        base_url=args.api_url,
        max_concurrency=args.concurrency,
        max_retries=args.max_retries,
        request_timeout=args.timeout,
    )

    success, results = await orchestrator.orchestrate(args.dataset_id, args.param_set_id)

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
