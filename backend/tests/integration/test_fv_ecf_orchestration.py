# ============================================================================
# Orchestration Integration Tests for FV ECF Phase 4 (Task 7)
# ============================================================================
"""
Integration tests for RuntimeMetricsOrchestrationService Phase 4 (FV ECF).
Tests the complete orchestration flow with FV ECF as Phase 4.
"""

import pytest
import asyncio
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
import sys

sys.path.insert(0, '/home/ubuntu/cissa')
from backend.app.services.runtime_metrics_orchestration_service import RuntimeMetricsOrchestrationService


class TestOrchestrationWithFVECF:
    """Task 7: Test orchestration integration with Phase 4 FV ECF"""
    
    @pytest.mark.asyncio
    async def test_orchestration_phases_1_through_4_success(self):
        """Test complete orchestration with all 4 phases succeeding"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = RuntimeMetricsOrchestrationService(mock_session)
        dataset_id = uuid4()
        param_set_id = uuid4()
        parameter_id = uuid4()
        
        # Mock parameter resolution
        with patch.object(service, '_resolve_parameter_id', return_value=parameter_id):
            # Mock Phase 1: Beta Rounding
            with patch.object(
                service, '_orchestrate_beta_rounding',
                return_value={
                    'status': 'success',
                    'results_count': 11000,
                    'message': 'Beta rounding successful',
                    'time_seconds': 15.0
                }
            ):
                # Mock Phase 2: Risk-Free Rate
                with patch.object(
                    service, '_orchestrate_risk_free_rate',
                    return_value={
                        'status': 'success',
                        'results_count': 11000,
                        'message': 'Risk-free rate successful',
                        'time_seconds': 14.5
                    }
                ):
                    # Mock Phase 3: Cost of Equity
                    with patch.object(
                        service, '_orchestrate_cost_of_equity',
                        return_value={
                            'status': 'success',
                            'records_inserted': 11000,
                            'message': 'Cost of equity successful',
                            'time_seconds': 15.2
                        }
                    ):
                        # Mock Phase 4: FV ECF
                        with patch.object(
                            service, '_orchestrate_fv_ecf',
                            return_value={
                                'status': 'success',
                                'total_inserted': 3600,
                                'intervals_summary': {
                                    '1Y': 1000,
                                    '3Y': 800,
                                    '5Y': 600,
                                    '10Y': 200
                                },
                                'message': 'FV ECF successful',
                                'duration_seconds': 18.5
                            }
                        ):
                            # Execute
                            result = await service.orchestrate_runtime_metrics(
                                dataset_id=dataset_id,
                                param_set_id=param_set_id,
                                parameter_id=parameter_id
                            )
                            
                            # Verify
                            assert result['success'] is True
                            assert result['execution_time_seconds'] > 0
                            assert str(dataset_id) == result['dataset_id']
                            assert str(param_set_id) == result['param_set_id']
                            assert str(parameter_id) == result['parameter_id']
                            
                            # Check all phases in response
                            metrics = result['metrics_completed']
                            assert 'beta_rounding' in metrics
                            assert 'risk_free_rate' in metrics
                            assert 'cost_of_equity' in metrics
                            assert 'fv_ecf' in metrics
                            
                            # Verify Phase 4 data
                            assert metrics['fv_ecf']['status'] == 'success'
                            assert metrics['fv_ecf']['records_inserted'] == 3600
                            assert metrics['fv_ecf']['intervals_summary']['1Y'] == 1000
                            assert metrics['fv_ecf']['intervals_summary']['3Y'] == 800
                            assert metrics['fv_ecf']['intervals_summary']['5Y'] == 600
                            assert metrics['fv_ecf']['intervals_summary']['10Y'] == 200
    
    @pytest.mark.asyncio
    async def test_orchestration_phase_4_failure_does_not_fail_orchestration(self):
        """Test that Phase 4 (FV ECF) failure doesn't fail orchestration (FAIL-SOFT)"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = RuntimeMetricsOrchestrationService(mock_session)
        dataset_id = uuid4()
        param_set_id = uuid4()
        parameter_id = uuid4()
        
        with patch.object(service, '_resolve_parameter_id', return_value=parameter_id):
            with patch.object(
                service, '_orchestrate_beta_rounding',
                return_value={'status': 'success', 'results_count': 11000, 'time_seconds': 15.0}
            ):
                with patch.object(
                    service, '_orchestrate_risk_free_rate',
                    return_value={'status': 'success', 'results_count': 11000, 'time_seconds': 14.5}
                ):
                    with patch.object(
                        service, '_orchestrate_cost_of_equity',
                        return_value={'status': 'success', 'records_inserted': 11000, 'time_seconds': 15.2}
                    ):
                        # Mock Phase 4 failure
                        with patch.object(
                            service, '_orchestrate_fv_ecf',
                            return_value={
                                'status': 'error',
                                'total_inserted': 0,
                                'intervals_summary': {'1Y': 0, '3Y': 0, '5Y': 0, '10Y': 0},
                                'message': 'Database connection error',
                                'duration_seconds': 2.5
                            }
                        ):
                            # Execute
                            result = await service.orchestrate_runtime_metrics(
                                dataset_id=dataset_id,
                                param_set_id=param_set_id,
                                parameter_id=parameter_id
                            )
                            
                            # Verify: orchestration still succeeds (FAIL-SOFT)
                            assert result['success'] is True
                            
                            # Verify Phase 4 error is captured
                            metrics = result['metrics_completed']
                            assert metrics['fv_ecf']['status'] == 'error'
                            assert 'Database connection error' in metrics['fv_ecf']['message']
    
    @pytest.mark.asyncio
    async def test_orchestration_phase_3_failure_still_fails_orchestration(self):
        """Test that Phase 3 (Cost of Equity) failure DOES fail orchestration (FAIL-FAST)"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = RuntimeMetricsOrchestrationService(mock_session)
        dataset_id = uuid4()
        param_set_id = uuid4()
        parameter_id = uuid4()
        
        with patch.object(service, '_resolve_parameter_id', return_value=parameter_id):
            with patch.object(
                service, '_orchestrate_beta_rounding',
                return_value={'status': 'success', 'results_count': 11000, 'time_seconds': 15.0}
            ):
                with patch.object(
                    service, '_orchestrate_risk_free_rate',
                    return_value={'status': 'success', 'results_count': 11000, 'time_seconds': 14.5}
                ):
                    # Mock Phase 3 failure
                    with patch.object(
                        service, '_orchestrate_cost_of_equity',
                        return_value={
                            'status': 'error',
                            'records_inserted': 0,
                            'message': 'Cost of equity calculation failed',
                            'time_seconds': 2.0
                        }
                    ):
                        # Execute (Phase 4 should not be called)
                        result = await service.orchestrate_runtime_metrics(
                            dataset_id=dataset_id,
                            param_set_id=param_set_id,
                            parameter_id=parameter_id
                        )
                        
                        # Verify: orchestration fails
                        assert result['success'] is False
                        assert 'Cost of equity calculation failed' in result['error']
    
    @pytest.mark.asyncio
    async def test_orchestration_phase_4_receives_param_set_id(self):
        """Test that Phase 4 receives correct param_set_id for runtime calculation"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = RuntimeMetricsOrchestrationService(mock_session)
        dataset_id = uuid4()
        param_set_id = uuid4()
        parameter_id = uuid4()
        
        phase_4_call_args = None
        
        async def capture_phase_4_call(*args, **kwargs):
            nonlocal phase_4_call_args
            phase_4_call_args = (args, kwargs)
            return {
                'status': 'success',
                'total_inserted': 3600,
                'intervals_summary': {'1Y': 1000, '3Y': 800, '5Y': 600, '10Y': 200},
                'message': 'Success',
                'duration_seconds': 18.5
            }
        
        with patch.object(service, '_resolve_parameter_id', return_value=parameter_id):
            with patch.object(
                service, '_orchestrate_beta_rounding',
                return_value={'status': 'success', 'results_count': 11000, 'time_seconds': 15.0}
            ):
                with patch.object(
                    service, '_orchestrate_risk_free_rate',
                    return_value={'status': 'success', 'results_count': 11000, 'time_seconds': 14.5}
                ):
                    with patch.object(
                        service, '_orchestrate_cost_of_equity',
                        return_value={'status': 'success', 'records_inserted': 11000, 'time_seconds': 15.2}
                    ):
                        with patch.object(
                            service, '_orchestrate_fv_ecf',
                            side_effect=capture_phase_4_call
                        ):
                            result = await service.orchestrate_runtime_metrics(
                                dataset_id=dataset_id,
                                param_set_id=param_set_id,
                                parameter_id=parameter_id
                            )
                            
                            # Verify Phase 4 was called with correct arguments
                            args, kwargs = phase_4_call_args
                            assert str(dataset_id) == str(args[0])
                            assert str(param_set_id) == str(args[1])
                            assert str(parameter_id) == str(args[2])
    
    @pytest.mark.asyncio
    async def test_orchestration_execution_time_includes_all_phases(self):
        """Test that total execution time tracks reported phase times"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = RuntimeMetricsOrchestrationService(mock_session)
        dataset_id = uuid4()
        param_set_id = uuid4()
        parameter_id = uuid4()
        
        with patch.object(service, '_resolve_parameter_id', return_value=parameter_id):
            with patch.object(
                service, '_orchestrate_beta_rounding',
                return_value={'status': 'success', 'results_count': 11000, 'time_seconds': 15.0}
            ):
                with patch.object(
                    service, '_orchestrate_risk_free_rate',
                    return_value={'status': 'success', 'results_count': 11000, 'time_seconds': 14.5}
                ):
                    with patch.object(
                        service, '_orchestrate_cost_of_equity',
                        return_value={'status': 'success', 'records_inserted': 11000, 'time_seconds': 15.2}
                    ):
                        with patch.object(
                            service, '_orchestrate_fv_ecf',
                            return_value={
                                'status': 'success',
                                'total_inserted': 3600,
                                'intervals_summary': {'1Y': 1000, '3Y': 800, '5Y': 600, '10Y': 200},
                                'message': 'Success',
                                'duration_seconds': 18.5
                            }
                        ):
                            result = await service.orchestrate_runtime_metrics(
                                dataset_id=dataset_id,
                                param_set_id=param_set_id,
                                parameter_id=parameter_id
                            )
                            
                            # Verify all phases have time_seconds recorded
                            metrics = result['metrics_completed']
                            assert metrics['beta_rounding']['time_seconds'] > 0
                            assert metrics['risk_free_rate']['time_seconds'] > 0
                            assert metrics['cost_of_equity']['time_seconds'] > 0
                            assert metrics['fv_ecf']['time_seconds'] > 0
                            
                            # Verify total execution time is recorded
                            assert result['execution_time_seconds'] > 0
    
    @pytest.mark.asyncio
    async def test_orchestration_response_includes_timestamp(self):
        """Test that orchestration response includes ISO timestamp"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = RuntimeMetricsOrchestrationService(mock_session)
        dataset_id = uuid4()
        param_set_id = uuid4()
        parameter_id = uuid4()
        
        with patch.object(service, '_resolve_parameter_id', return_value=parameter_id):
            with patch.object(
                service, '_orchestrate_beta_rounding',
                return_value={'status': 'success', 'results_count': 11000, 'time_seconds': 15.0}
            ):
                with patch.object(
                    service, '_orchestrate_risk_free_rate',
                    return_value={'status': 'success', 'results_count': 11000, 'time_seconds': 14.5}
                ):
                    with patch.object(
                        service, '_orchestrate_cost_of_equity',
                        return_value={'status': 'success', 'records_inserted': 11000, 'time_seconds': 15.2}
                    ):
                        with patch.object(
                            service, '_orchestrate_fv_ecf',
                            return_value={
                                'status': 'success',
                                'total_inserted': 3600,
                                'intervals_summary': {'1Y': 1000, '3Y': 800, '5Y': 600, '10Y': 200},
                                'message': 'Success',
                                'duration_seconds': 18.5
                            }
                        ):
                            result = await service.orchestrate_runtime_metrics(
                                dataset_id=dataset_id,
                                param_set_id=param_set_id,
                                parameter_id=parameter_id
                            )
                            
                            # Verify timestamp
                            assert 'timestamp' in result
                            assert result['timestamp']  # Not empty
                            # ISO format check (basic)
                            assert 'T' in result['timestamp']  # ISO format includes T
    
    @pytest.mark.asyncio
    async def test_fv_ecf_intervals_summary_in_response(self):
        """Test that FV_ECF intervals_summary is properly included in response"""
        mock_session = AsyncMock(spec=AsyncSession)
        service = RuntimeMetricsOrchestrationService(mock_session)
        dataset_id = uuid4()
        param_set_id = uuid4()
        parameter_id = uuid4()
        
        intervals_data = {
            '1Y': 1500,
            '3Y': 1200,
            '5Y': 900,
            '10Y': 300
        }
        
        with patch.object(service, '_resolve_parameter_id', return_value=parameter_id):
            with patch.object(
                service, '_orchestrate_beta_rounding',
                return_value={'status': 'success', 'results_count': 11000, 'time_seconds': 15.0}
            ):
                with patch.object(
                    service, '_orchestrate_risk_free_rate',
                    return_value={'status': 'success', 'results_count': 11000, 'time_seconds': 14.5}
                ):
                    with patch.object(
                        service, '_orchestrate_cost_of_equity',
                        return_value={'status': 'success', 'records_inserted': 11000, 'time_seconds': 15.2}
                    ):
                        with patch.object(
                            service, '_orchestrate_fv_ecf',
                            return_value={
                                'status': 'success',
                                'total_inserted': 3900,
                                'intervals_summary': intervals_data,
                                'message': 'Success',
                                'duration_seconds': 18.5
                            }
                        ):
                            result = await service.orchestrate_runtime_metrics(
                                dataset_id=dataset_id,
                                param_set_id=param_set_id,
                                parameter_id=parameter_id
                            )
                            
                            # Verify intervals_summary
                            fv_ecf_data = result['metrics_completed']['fv_ecf']
                            assert 'intervals_summary' in fv_ecf_data
                            assert fv_ecf_data['intervals_summary'] == intervals_data
                            assert fv_ecf_data['records_inserted'] == 3900
