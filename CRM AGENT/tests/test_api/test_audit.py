"""
Integration tests for audit trail API endpoints.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.services.audit_trail import AuditEventType
from app.schemas.compliance import ComplianceStatus, ComplianceAuditEntry


class TestAuditAPI:
    """Test audit trail API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def sample_audit_entries(self):
        """Sample audit entries for testing."""
        base_time = datetime.now(timezone.utc)
        return [
            ComplianceAuditEntry(
                entry_id="entry_1",
                prospect_id="prospect_1",
                action_type="compliance_validation",
                action_details={"validation": "passed"},
                performed_by="user_1",
                performed_at=base_time - timedelta(hours=1),
                compliance_status=ComplianceStatus.APPROVED
            ),
            ComplianceAuditEntry(
                entry_id="entry_2",
                prospect_id="prospect_2",
                action_type="call_initiated",
                action_details={"call": "started"},
                performed_by="user_2",
                performed_at=base_time - timedelta(hours=2),
                compliance_status=ComplianceStatus.VIOLATION
            ),
            ComplianceAuditEntry(
                entry_id="entry_3",
                prospect_id="prospect_1",
                action_type="approval_decision",
                action_details={"decision": "approved"},
                performed_by="user_1",
                performed_at=base_time - timedelta(hours=3),
                compliance_status=ComplianceStatus.APPROVED
            )
        ]
    
    def test_search_audit_entries_get(self, client, sample_audit_entries):
        """Test searching audit entries using GET request."""
        with patch('app.services.audit_trail.audit_trail_service.search_audit_entries') as mock_search:
            mock_search.return_value = sample_audit_entries[:2]  # Return first 2 entries
            
            response = client.get(
                "/api/v1/audit/entries",
                params={
                    "event_types": "compliance_validation,call_initiated",
                    "limit": 10,
                    "offset": 0
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["entry_id"] == "entry_1"
            assert data[1]["entry_id"] == "entry_2"
    
    def test_search_audit_entries_get_with_filters(self, client, sample_audit_entries):
        """Test searching audit entries with various filters."""
        with patch('app.services.audit_trail.audit_trail_service.search_audit_entries') as mock_search:
            mock_search.return_value = [sample_audit_entries[0]]  # Return only first entry
            
            response = client.get(
                "/api/v1/audit/entries",
                params={
                    "prospect_id": "prospect_1",
                    "user_id": "user_1",
                    "compliance_status": "approved",
                    "limit": 5
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["prospect_id"] == "prospect_1"
            assert data[0]["performed_by"] == "user_1"
            assert data[0]["compliance_status"] == "approved"
    
    def test_search_audit_entries_get_invalid_event_type(self, client):
        """Test searching with invalid event type."""
        response = client.get(
            "/api/v1/audit/entries",
            params={"event_types": "invalid_event_type"}
        )
        
        assert response.status_code == 400
        assert "Invalid event type" in response.json()["detail"]
    
    def test_search_audit_entries_get_invalid_compliance_status(self, client):
        """Test searching with invalid compliance status."""
        response = client.get(
            "/api/v1/audit/entries",
            params={"compliance_status": "invalid_status"}
        )
        
        assert response.status_code == 400
        assert "Invalid compliance status" in response.json()["detail"]
    
    def test_search_audit_entries_post(self, client, sample_audit_entries):
        """Test searching audit entries using POST request."""
        search_request = {
            "event_types": ["compliance_validation", "approval_decision"],
            "prospect_id": "prospect_1",
            "limit": 10,
            "offset": 0
        }
        
        with patch('app.services.audit_trail.audit_trail_service.search_audit_entries') as mock_search:
            mock_search.return_value = [sample_audit_entries[0], sample_audit_entries[2]]
            
            response = client.post("/api/v1/audit/entries/search", json=search_request)
            
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["entry_id"] == "entry_1"
            assert data[1]["entry_id"] == "entry_3"
    
    def test_get_audit_entry_by_id(self, client, sample_audit_entries):
        """Test getting specific audit entry by ID."""
        with patch('app.services.audit_trail.audit_trail_service.search_audit_entries') as mock_search:
            mock_search.return_value = sample_audit_entries
            
            response = client.get("/api/v1/audit/entries/entry_2")
            
            assert response.status_code == 200
            data = response.json()
            assert data["entry_id"] == "entry_2"
            assert data["action_type"] == "call_initiated"
    
    def test_get_audit_entry_not_found(self, client):
        """Test getting non-existent audit entry."""
        with patch('app.services.audit_trail.audit_trail_service.search_audit_entries') as mock_search:
            mock_search.return_value = []
            
            response = client.get("/api/v1/audit/entries/non_existent_entry")
            
            assert response.status_code == 404
            assert "Audit entry not found" in response.json()["detail"]
    
    def test_generate_compliance_report(self, client):
        """Test generating compliance report."""
        report_request = {
            "report_type": "summary",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-01-31T23:59:59Z",
            "include_details": False
        }
        
        mock_report = {
            "report_type": "summary",
            "period": {
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-01-31T23:59:59Z"
            },
            "metrics": {
                "total_entries": 100,
                "compliance_rate": 95.0,
                "violation_count": 5
            },
            "summary": {
                "risk_level": "Low"
            }
        }
        
        with patch('app.services.audit_trail.audit_trail_service.generate_compliance_report') as mock_generate:
            mock_generate.return_value = mock_report
            
            response = client.post("/api/v1/audit/reports/compliance", json=report_request)
            
            assert response.status_code == 200
            data = response.json()
            assert data["report_type"] == "summary"
            assert data["metrics"]["total_entries"] == 100
            assert data["metrics"]["compliance_rate"] == 95.0
    
    def test_generate_compliance_report_invalid_type(self, client):
        """Test generating compliance report with invalid type."""
        report_request = {
            "report_type": "invalid_type",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-01-31T23:59:59Z"
        }
        
        response = client.post("/api/v1/audit/reports/compliance", json=report_request)
        
        assert response.status_code == 400
        assert "Invalid report type" in response.json()["detail"]
    
    def test_generate_compliance_report_invalid_dates(self, client):
        """Test generating compliance report with invalid date range."""
        report_request = {
            "report_type": "summary",
            "start_date": "2024-01-31T00:00:00Z",
            "end_date": "2024-01-01T23:59:59Z"  # End before start
        }
        
        response = client.post("/api/v1/audit/reports/compliance", json=report_request)
        
        assert response.status_code == 400
        assert "Start date must be before end date" in response.json()["detail"]
    
    def test_get_compliance_summary(self, client):
        """Test getting compliance summary."""
        mock_report = {
            "report_type": "summary",
            "metrics": {
                "total_entries": 50,
                "compliance_rate": 92.0,
                "violation_count": 4
            },
            "summary": {
                "risk_level": "Medium"
            }
        }
        
        with patch('app.services.audit_trail.audit_trail_service.generate_compliance_report') as mock_generate:
            mock_generate.return_value = mock_report
            
            response = client.get("/api/v1/audit/reports/compliance/summary?days=14")
            
            assert response.status_code == 200
            data = response.json()
            assert data["metrics"]["total_entries"] == 50
            assert data["metrics"]["compliance_rate"] == 92.0
    
    def test_get_compliance_summary_invalid_days(self, client):
        """Test getting compliance summary with invalid days parameter."""
        response = client.get("/api/v1/audit/reports/compliance/summary?days=400")
        
        assert response.status_code == 400
        assert "Days must be between 1 and 365" in response.json()["detail"]
    
    def test_get_compliance_violations(self, client):
        """Test getting compliance violations."""
        mock_violations = [
            {
                "audit_entry_id": "violation_1",
                "violation_type": "security_violation",
                "severity": "high",
                "detected_at": datetime.now(timezone.utc),
                "resolved": False
            },
            {
                "audit_entry_id": "violation_2",
                "violation_type": "policy_violation",
                "severity": "medium",
                "detected_at": datetime.now(timezone.utc) - timedelta(hours=1),
                "resolved": True
            }
        ]
        
        with patch('app.services.audit_trail.audit_trail_service.compliance_violations', mock_violations):
            response = client.get("/api/v1/audit/violations")
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_count"] == 2
            assert len(data["violations"]) == 2
    
    def test_get_compliance_violations_filtered(self, client):
        """Test getting compliance violations with filters."""
        mock_violations = [
            {
                "audit_entry_id": "violation_1",
                "violation_type": "security_violation",
                "severity": "high",
                "detected_at": datetime.now(timezone.utc),
                "resolved": False
            },
            {
                "audit_entry_id": "violation_2",
                "violation_type": "policy_violation",
                "severity": "high",
                "detected_at": datetime.now(timezone.utc) - timedelta(hours=1),
                "resolved": True
            }
        ]
        
        with patch('app.services.audit_trail.audit_trail_service.compliance_violations', mock_violations):
            response = client.get("/api/v1/audit/violations?resolved=false&severity=high")
            
            assert response.status_code == 200
            data = response.json()
            assert data["total_count"] == 1
            assert data["violations"][0]["resolved"] is False
            assert data["violations"][0]["severity"] == "high"
    
    def test_resolve_compliance_violation(self, client):
        """Test resolving a compliance violation."""
        mock_violations = [
            {
                "audit_entry_id": "violation_1",
                "violation_type": "security_violation",
                "severity": "high",
                "resolved": False
            }
        ]
        
        with patch('app.services.audit_trail.audit_trail_service.compliance_violations', mock_violations):
            with patch('app.services.audit_trail.audit_trail_service.log_audit_event') as mock_log:
                response = client.put(
                    "/api/v1/audit/violations/violation_1/resolve",
                    params={"resolution_notes": "Issue fixed by updating security settings"}
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "success"
                assert data["violation_id"] == "violation_1"
                
                # Verify violation was marked as resolved
                assert mock_violations[0]["resolved"] is True
                assert "resolved_at" in mock_violations[0]
                
                # Verify audit event was logged
                mock_log.assert_called_once()
    
    def test_resolve_compliance_violation_not_found(self, client):
        """Test resolving non-existent compliance violation."""
        with patch('app.services.audit_trail.audit_trail_service.compliance_violations', []):
            response = client.put("/api/v1/audit/violations/non_existent/resolve")
            
            assert response.status_code == 404
            assert "Compliance violation not found" in response.json()["detail"]
    
    def test_apply_data_retention_policy(self, client):
        """Test applying data retention policy."""
        mock_results = {
            "entries_reviewed": 100,
            "entries_archived": 20,
            "entries_deleted": 5,
            "entries_requiring_approval": 2,
            "errors": []
        }
        
        with patch('app.services.audit_trail.audit_trail_service.apply_data_retention_policy') as mock_apply:
            mock_apply.return_value = mock_results
            
            response = client.post("/api/v1/audit/retention/apply")
            
            assert response.status_code == 200
            data = response.json()
            assert data["entries_reviewed"] == 100
            assert data["entries_archived"] == 20
            assert data["entries_deleted"] == 5
    
    def test_get_retention_rules(self, client):
        """Test getting retention rules."""
        response = client.get("/api/v1/audit/retention/rules")
        
        assert response.status_code == 200
        data = response.json()
        assert "retention_rules" in data
        assert "total_rules" in data
        assert data["total_rules"] > 0
        
        # Check that some expected rules are present
        rules = data["retention_rules"]
        assert "compliance_validation" in rules
        assert "dnc_list_addition" in rules
        assert "system_error" in rules
    
    def test_get_audit_dashboard_metrics(self, client):
        """Test getting audit dashboard metrics."""
        mock_report = {
            "metrics": {
                "total_entries": 200,
                "compliance_rate": 94.5,
                "violation_count": 11
            }
        }
        
        mock_violations = [
            {"severity": "high", "resolved": False, "detected_at": datetime.now(timezone.utc)},
            {"severity": "medium", "resolved": True, "detected_at": datetime.now(timezone.utc)}
        ]
        
        mock_entries = [
            MagicMock(performed_at=datetime.now(timezone.utc), performed_by="user1", action_type="compliance_validation"),
            MagicMock(performed_at=datetime.now(timezone.utc), performed_by="user2", action_type="call_initiated")
        ]
        
        with patch('app.services.audit_trail.audit_trail_service.generate_compliance_report') as mock_generate:
            with patch('app.services.audit_trail.audit_trail_service.compliance_violations', mock_violations):
                with patch('app.services.audit_trail.audit_trail_service.audit_entries', mock_entries):
                    mock_generate.return_value = mock_report
                    
                    response = client.get("/api/v1/audit/metrics/dashboard?days=30")
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert "period" in data
                    assert "compliance" in data
                    assert "violations" in data
                    assert "activity" in data
                    assert "system_health" in data
                    
                    assert data["period"]["days"] == 30
                    assert data["compliance"]["total_entries"] == 200
                    assert data["violations"]["total_recent"] == 2
    
    def test_get_audit_dashboard_metrics_invalid_days(self, client):
        """Test getting dashboard metrics with invalid days parameter."""
        response = client.get("/api/v1/audit/metrics/dashboard?days=500")
        
        assert response.status_code == 400
        assert "Days must be between 1 and 365" in response.json()["detail"]
    
    def test_export_audit_data_json(self, client, sample_audit_entries):
        """Test exporting audit data in JSON format."""
        with patch('app.services.audit_trail.audit_trail_service.search_audit_entries') as mock_search:
            with patch('app.services.audit_trail.audit_trail_service.log_audit_event') as mock_log:
                mock_search.return_value = sample_audit_entries
                
                response = client.get(
                    "/api/v1/audit/export",
                    params={
                        "format": "json",
                        "event_types": "compliance_validation,call_initiated"
                    }
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["format"] == "json"
                assert data["entries_count"] == 3
                assert "entries" in data
                assert len(data["entries"]) == 3
                
                # Verify export was logged
                mock_log.assert_called_once()
    
    def test_export_audit_data_csv(self, client, sample_audit_entries):
        """Test exporting audit data in CSV format."""
        with patch('app.services.audit_trail.audit_trail_service.search_audit_entries') as mock_search:
            with patch('app.services.audit_trail.audit_trail_service.log_audit_event') as mock_log:
                mock_search.return_value = sample_audit_entries
                
                response = client.get(
                    "/api/v1/audit/export",
                    params={"format": "csv"}
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["format"] == "csv"
                assert data["entries_count"] == 3
                assert "csv_data" in data
                assert len(data["csv_data"]) == 3
                
                # Check CSV data structure
                csv_entry = data["csv_data"][0]
                assert "entry_id" in csv_entry
                assert "timestamp" in csv_entry
                assert "event_type" in csv_entry
                assert "performed_by" in csv_entry
    
    def test_export_audit_data_invalid_format(self, client):
        """Test exporting audit data with invalid format."""
        response = client.get("/api/v1/audit/export", params={"format": "xml"})
        
        assert response.status_code == 400
        assert "Format must be 'json' or 'csv'" in response.json()["detail"]
    
    def test_export_audit_data_invalid_event_types(self, client):
        """Test exporting audit data with invalid event types."""
        response = client.get(
            "/api/v1/audit/export",
            params={
                "format": "json",
                "event_types": "invalid_event_type"
            }
        )
        
        assert response.status_code == 400
        assert "Invalid event type" in response.json()["detail"]