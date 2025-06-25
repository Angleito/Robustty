"""
Status reporting system for fallback methods and platform operations.

This module provides data structures and utilities for tracking and reporting
the status of various platform operations, fallback methods, and error conditions
to provide users with clear visibility into what methods are being used.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class SearchMethod(Enum):
    """Enumeration of search methods available."""
    API_SEARCH = "api_search"
    FALLBACK_SEARCH = "fallback_search"
    DIRECT_URL = "direct_url"
    YTDLP_SEARCH = "ytdlp_search"
    MIRROR_SEARCH = "mirror_search"


class PlatformStatus(Enum):
    """Enumeration of platform status states."""
    HEALTHY = "healthy"
    QUOTA_EXCEEDED = "quota_exceeded"
    API_ERROR = "api_error"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    NO_API_KEY = "no_api_key"
    USING_FALLBACK = "using_fallback"


class OperationResult(Enum):
    """Enumeration of operation results."""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    FALLBACK_SUCCESS = "fallback_success"
    TIMEOUT = "timeout"


@dataclass
class StatusReport:
    """Status report for a platform operation."""
    platform: str
    method: SearchMethod
    status: PlatformStatus
    result: OperationResult
    message: str
    user_message: str
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None
    
    @classmethod
    def create_api_quota_exceeded(cls, platform: str, user_message: str) -> 'StatusReport':
        """Create a status report for API quota exceeded."""
        return cls(
            platform=platform,
            method=SearchMethod.API_SEARCH,
            status=PlatformStatus.QUOTA_EXCEEDED,
            result=OperationResult.FAILURE,
            message=f"{platform} API quota exceeded",
            user_message=user_message,
            timestamp=datetime.utcnow()
        )
    
    @classmethod
    def create_fallback_success(cls, platform: str, method: SearchMethod, user_message: str, details: Optional[Dict[str, Any]] = None) -> 'StatusReport':
        """Create a status report for successful fallback operation."""
        return cls(
            platform=platform,
            method=method,
            status=PlatformStatus.USING_FALLBACK,
            result=OperationResult.FALLBACK_SUCCESS,
            message=f"{platform} using {method.value} fallback",
            user_message=user_message,
            timestamp=datetime.utcnow(),
            details=details
        )
    
    @classmethod
    def create_direct_url_success(cls, platform: str, user_message: str, details: Optional[Dict[str, Any]] = None) -> 'StatusReport':
        """Create a status report for successful direct URL processing."""
        return cls(
            platform=platform,
            method=SearchMethod.DIRECT_URL,
            status=PlatformStatus.HEALTHY,
            result=OperationResult.SUCCESS,
            message=f"{platform} direct URL processing successful",
            user_message=user_message,
            timestamp=datetime.utcnow(),
            details=details
        )
    
    @classmethod
    def create_search_success(cls, platform: str, method: SearchMethod, results_count: int, user_message: str) -> 'StatusReport':
        """Create a status report for successful search operation."""
        return cls(
            platform=platform,
            method=method,
            status=PlatformStatus.HEALTHY,
            result=OperationResult.SUCCESS,
            message=f"{platform} {method.value} returned {results_count} results",
            user_message=user_message,
            timestamp=datetime.utcnow(),
            details={'results_count': results_count}
        )
    
    @classmethod
    def create_no_api_key(cls, platform: str, user_message: str) -> 'StatusReport':
        """Create a status report for missing API key."""
        return cls(
            platform=platform,
            method=SearchMethod.API_SEARCH,
            status=PlatformStatus.NO_API_KEY,
            result=OperationResult.FAILURE,
            message=f"{platform} API key not configured",
            user_message=user_message,
            timestamp=datetime.utcnow()
        )
    
    @classmethod
    def create_platform_error(cls, platform: str, method: SearchMethod, error_msg: str, user_message: str) -> 'StatusReport':
        """Create a status report for platform error."""
        return cls(
            platform=platform,
            method=method,
            status=PlatformStatus.API_ERROR,
            result=OperationResult.FAILURE,
            message=f"{platform} error: {error_msg}",
            user_message=user_message,
            timestamp=datetime.utcnow()
        )


@dataclass
class MultiPlatformStatus:
    """Status report for multi-platform search operations."""
    query: str
    total_platforms: int
    successful_platforms: List[str]
    failed_platforms: List[str]
    platform_reports: Dict[str, StatusReport]
    primary_method: SearchMethod
    fallback_methods_used: List[SearchMethod]
    total_results: int
    timestamp: datetime
    
    def get_user_summary(self) -> str:
        """Get a user-friendly summary of the search operation."""
        if not self.successful_platforms:
            return f"❌ No results found on any platform ({self.total_platforms} searched)"
        
        if len(self.successful_platforms) == self.total_platforms:
            method_info = ""
            if self.fallback_methods_used:
                method_info = f" using fallback methods"
            return f"✅ Found {self.total_results} results from all {self.total_platforms} platforms{method_info}"
        else:
            successful_count = len(self.successful_platforms)
            method_info = ""
            if self.fallback_methods_used:
                method_info = f" (some using fallback methods)"
            return f"⚠️ Found {self.total_results} results from {successful_count}/{self.total_platforms} platforms{method_info}"
    
    def has_fallbacks(self) -> bool:
        """Check if any fallback methods were used."""
        return bool(self.fallback_methods_used)
    
    def get_quota_exceeded_platforms(self) -> List[str]:
        """Get list of platforms that hit quota limits."""
        return [
            platform for platform, report in self.platform_reports.items()
            if report.status == PlatformStatus.QUOTA_EXCEEDED
        ]
    
    def get_fallback_platforms(self) -> List[str]:
        """Get list of platforms using fallback methods."""
        return [
            platform for platform, report in self.platform_reports.items()
            if report.status == PlatformStatus.USING_FALLBACK
        ]


class StatusReporter:
    """Central status reporter for tracking platform operations."""
    
    def __init__(self):
        self.reports: List[StatusReport] = []
        self.max_reports = 100  # Keep last 100 reports for debugging
    
    def add_report(self, report: StatusReport) -> None:
        """Add a status report."""
        self.reports.append(report)
        
        # Keep only recent reports
        if len(self.reports) > self.max_reports:
            self.reports = self.reports[-self.max_reports:]
        
        # Log the report
        if report.result in [OperationResult.SUCCESS, OperationResult.FALLBACK_SUCCESS]:
            logger.info(f"Status Report: {report.message}")
        elif report.result in [OperationResult.PARTIAL_SUCCESS]:
            logger.warning(f"Status Report: {report.message}")
        else:
            logger.error(f"Status Report: {report.message}")
    
    def get_recent_reports(self, platform: Optional[str] = None, limit: int = 10) -> List[StatusReport]:
        """Get recent status reports, optionally filtered by platform."""
        reports = self.reports
        if platform:
            reports = [r for r in reports if r.platform.lower() == platform.lower()]
        
        return reports[-limit:] if reports else []
    
    def get_platform_health(self, platform: str) -> PlatformStatus:
        """Get the current health status of a platform based on recent reports."""
        recent_reports = self.get_recent_reports(platform, limit=5)
        if not recent_reports:
            return PlatformStatus.HEALTHY
        
        # Check most recent report first
        latest_report = recent_reports[-1]
        if latest_report.status in [PlatformStatus.QUOTA_EXCEEDED, PlatformStatus.RATE_LIMITED]:
            return latest_report.status
        
        # Check for patterns in recent reports
        error_count = sum(1 for r in recent_reports if r.result == OperationResult.FAILURE)
        if error_count >= 3:
            return PlatformStatus.API_ERROR
        
        fallback_count = sum(1 for r in recent_reports if r.status == PlatformStatus.USING_FALLBACK)
        if fallback_count >= 2:
            return PlatformStatus.USING_FALLBACK
        
        return PlatformStatus.HEALTHY
    
    def create_multi_platform_status(
        self, 
        query: str, 
        platform_reports: Dict[str, StatusReport], 
        total_results: int
    ) -> MultiPlatformStatus:
        """Create a multi-platform status report."""
        successful_platforms = [
            platform for platform, report in platform_reports.items()
            if report.result in [OperationResult.SUCCESS, OperationResult.FALLBACK_SUCCESS]
        ]
        
        failed_platforms = [
            platform for platform, report in platform_reports.items()
            if report.result not in [OperationResult.SUCCESS, OperationResult.FALLBACK_SUCCESS]
        ]
        
        # Determine primary method and fallback methods used
        methods_used = [report.method for report in platform_reports.values()]
        primary_method = SearchMethod.API_SEARCH  # Default assumption
        fallback_methods = []
        
        for method in methods_used:
            if method != SearchMethod.API_SEARCH:
                fallback_methods.append(method)
                if method == SearchMethod.DIRECT_URL:
                    primary_method = SearchMethod.DIRECT_URL
        
        # Remove duplicates
        fallback_methods = list(set(fallback_methods))
        
        return MultiPlatformStatus(
            query=query,
            total_platforms=len(platform_reports),
            successful_platforms=successful_platforms,
            failed_platforms=failed_platforms,
            platform_reports=platform_reports,
            primary_method=primary_method,
            fallback_methods_used=fallback_methods,
            total_results=total_results,
            timestamp=datetime.utcnow()
        )


# Global status reporter instance
_global_reporter = StatusReporter()


def get_status_reporter() -> StatusReporter:
    """Get the global status reporter instance."""
    return _global_reporter


def report_api_quota_exceeded(platform: str, user_message: str) -> None:
    """Report API quota exceeded."""
    report = StatusReport.create_api_quota_exceeded(platform, user_message)
    _global_reporter.add_report(report)


def report_fallback_success(platform: str, method: SearchMethod, user_message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Report successful fallback operation."""
    report = StatusReport.create_fallback_success(platform, method, user_message, details)
    _global_reporter.add_report(report)


def report_direct_url_success(platform: str, user_message: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Report successful direct URL processing."""
    report = StatusReport.create_direct_url_success(platform, user_message, details)
    _global_reporter.add_report(report)


def report_search_success(platform: str, method: SearchMethod, results_count: int, user_message: str) -> None:
    """Report successful search operation."""
    report = StatusReport.create_search_success(platform, method, results_count, user_message)
    _global_reporter.add_report(report)


def report_no_api_key(platform: str, user_message: str) -> None:
    """Report missing API key."""
    report = StatusReport.create_no_api_key(platform, user_message)
    _global_reporter.add_report(report)


def report_platform_error(platform: str, method: SearchMethod, error_msg: str, user_message: str) -> None:
    """Report platform error."""
    report = StatusReport.create_platform_error(platform, method, error_msg, user_message)
    _global_reporter.add_report(report)