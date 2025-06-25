"""
Tests for Platform Fallback Manager service

This test suite focuses on the fallback manager's core functionality,
including strategy selection, activation/deactivation, and monitoring.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from src.services.platform_fallback_manager import (
    PlatformFallbackManager,
    FallbackMode,
    FallbackStrategy,
)


@pytest.fixture
def fallback_config():
    """Standard fallback manager configuration"""
    return {
        "enable_fallbacks": True,
        "max_fallback_duration_hours": 24,
        "retry_interval_minutes": 30,
    }


@pytest.fixture
def fallback_manager(fallback_config):
    """Platform fallback manager instance"""
    return PlatformFallbackManager(fallback_config)


@pytest.fixture
def custom_strategy():
    """Custom fallback strategy for testing"""
    return FallbackStrategy(
        mode=FallbackMode.LIMITED_SEARCH,
        description="Custom test strategy",
        limitations=["Test limitation 1", "Test limitation 2"],
        priority=1
    )


class TestFallbackManagerBasics:
    """Test basic fallback manager functionality"""

    def test_initialization(self, fallback_manager):
        """Test fallback manager initializes correctly"""
        assert fallback_manager.enable_fallbacks is True
        assert fallback_manager.max_fallback_duration == 24
        assert fallback_manager.retry_interval == 30
        
        # Check default strategies are loaded
        assert "youtube" in fallback_manager.fallback_strategies
        assert "rumble" in fallback_manager.fallback_strategies
        assert "odysee" in fallback_manager.fallback_strategies
        assert "peertube" in fallback_manager.fallback_strategies

    def test_disabled_fallbacks(self):
        """Test behavior when fallbacks are disabled"""
        config = {"enable_fallbacks": False}
        manager = PlatformFallbackManager(config)
        
        result = manager.activate_fallback("youtube", "Test reason")
        assert result is None
        assert not manager.is_platform_in_fallback("youtube")

    def test_default_strategy_structure(self, fallback_manager):
        """Test default strategies have correct structure"""
        youtube_strategies = fallback_manager.fallback_strategies["youtube"]
        
        assert len(youtube_strategies) > 0
        
        for strategy in youtube_strategies:
            assert isinstance(strategy, FallbackStrategy)
            assert isinstance(strategy.mode, FallbackMode)
            assert isinstance(strategy.description, str)
            assert isinstance(strategy.limitations, list)
            assert isinstance(strategy.priority, int)
            assert isinstance(strategy.enabled, bool)


class TestFallbackActivationDeactivation:
    """Test fallback activation and deactivation"""

    def test_activate_fallback_success(self, fallback_manager):
        """Test successful fallback activation"""
        strategy = fallback_manager.activate_fallback("youtube", "Test activation")
        
        assert strategy is not None
        assert strategy.mode == FallbackMode.API_ONLY  # Should be highest priority
        assert fallback_manager.is_platform_in_fallback("youtube")
        assert "youtube" in fallback_manager.active_fallbacks

    def test_activate_fallback_unknown_platform(self, fallback_manager):
        """Test activation for unknown platform"""
        strategy = fallback_manager.activate_fallback("unknown_platform", "Test")
        
        assert strategy is None
        assert not fallback_manager.is_platform_in_fallback("unknown_platform")

    def test_activate_fallback_priority_selection(self, fallback_manager):
        """Test that highest priority strategy is selected"""
        # Disable highest priority strategy
        youtube_strategies = fallback_manager.fallback_strategies["youtube"]
        api_only_strategy = next(s for s in youtube_strategies if s.mode == FallbackMode.API_ONLY)
        api_only_strategy.enabled = False
        
        strategy = fallback_manager.activate_fallback("youtube", "Priority test")
        
        assert strategy is not None
        assert strategy.mode == FallbackMode.LIMITED_SEARCH  # Should be next priority

    def test_deactivate_fallback_success(self, fallback_manager):
        """Test successful fallback deactivation"""
        # First activate
        fallback_manager.activate_fallback("youtube", "Test activation")
        assert fallback_manager.is_platform_in_fallback("youtube")
        
        # Then deactivate
        success = fallback_manager.deactivate_fallback("youtube", "Test recovery")
        
        assert success is True
        assert not fallback_manager.is_platform_in_fallback("youtube")
        assert "youtube" not in fallback_manager.active_fallbacks

    def test_deactivate_fallback_not_active(self, fallback_manager):
        """Test deactivation when no fallback is active"""
        success = fallback_manager.deactivate_fallback("youtube", "Test")
        
        assert success is False

    def test_fallback_history_tracking(self, fallback_manager):
        """Test fallback history is properly tracked"""
        # Activate
        fallback_manager.activate_fallback("youtube", "Initial failure")
        
        # Deactivate
        fallback_manager.deactivate_fallback("youtube", "Recovery")
        
        # Re-activate
        fallback_manager.activate_fallback("youtube", "Second failure")
        
        history = fallback_manager.fallback_history["youtube"]
        assert len(history) == 3
        
        actions = [record["action"] for record in history]
        assert actions == ["activated", "deactivated", "activated"]
        
        reasons = [record["reason"] for record in history]
        assert "Initial failure" in reasons
        assert "Recovery" in reasons
        assert "Second failure" in reasons


class TestFallbackOperationRestrictions:
    """Test operation restrictions during fallback modes"""

    def test_disabled_mode_restrictions(self, fallback_manager):
        """Test all operations are restricted in disabled mode"""
        fallback_manager.active_fallbacks["youtube"] = FallbackStrategy(
            mode=FallbackMode.DISABLED,
            description="Platform disabled",
            limitations=["All functionality disabled"]
        )
        
        should_fallback, reason = fallback_manager.should_use_fallback_for_operation("youtube", "search")
        assert should_fallback is True
        assert "disabled" in reason.lower()

    def test_read_only_mode_restrictions(self, fallback_manager):
        """Test write operations are restricted in read-only mode"""
        fallback_manager.active_fallbacks["youtube"] = FallbackStrategy(
            mode=FallbackMode.READ_ONLY,
            description="Read-only mode",
            limitations=["No write operations"]
        )
        
        # Write operations should be restricted
        for operation in ["upload", "comment", "like", "subscribe"]:
            should_fallback, reason = fallback_manager.should_use_fallback_for_operation("youtube", operation)
            assert should_fallback is True
            assert "read-only" in reason.lower()
        
        # Read operations should be allowed
        should_fallback, reason = fallback_manager.should_use_fallback_for_operation("youtube", "search")
        assert should_fallback is False

    def test_limited_search_restrictions(self, fallback_manager):
        """Test advanced search operations are restricted in limited search mode"""
        fallback_manager.active_fallbacks["youtube"] = FallbackStrategy(
            mode=FallbackMode.LIMITED_SEARCH,
            description="Limited search",
            limitations=["Advanced search disabled"]
        )
        
        # Advanced search should be restricted
        restricted_ops = ["advanced_search", "personalized_search", "trending"]
        for operation in restricted_ops:
            should_fallback, reason = fallback_manager.should_use_fallback_for_operation("youtube", operation)
            assert should_fallback is True
            assert "Advanced search features disabled" in reason
        
        # Basic search should be allowed
        should_fallback, reason = fallback_manager.should_use_fallback_for_operation("youtube", "basic_search")
        assert should_fallback is False

    def test_public_only_restrictions(self, fallback_manager):
        """Test private content restrictions in public-only mode"""
        fallback_manager.active_fallbacks["youtube"] = FallbackStrategy(
            mode=FallbackMode.PUBLIC_ONLY,
            description="Public content only",
            limitations=["No private content"]
        )
        
        # Private content should be restricted
        private_ops = ["private_content", "authenticated_content", "user_playlists"]
        for operation in private_ops:
            should_fallback, reason = fallback_manager.should_use_fallback_for_operation("youtube", operation)
            assert should_fallback is True
            assert "public-only mode" in reason.lower()

    def test_api_only_restrictions(self, fallback_manager):
        """Test stream extraction restrictions in API-only mode"""
        fallback_manager.active_fallbacks["youtube"] = FallbackStrategy(
            mode=FallbackMode.API_ONLY,
            description="API only",
            limitations=["Limited stream extraction"]
        )
        
        # Stream operations may be limited
        stream_ops = ["stream_extraction", "download"]
        for operation in stream_ops:
            should_fallback, reason = fallback_manager.should_use_fallback_for_operation("youtube", operation)
            assert should_fallback is True
            assert "API-only mode" in reason.lower()


class TestUserFacingRecommendations:
    """Test user-facing recommendations during fallback"""

    def test_disabled_mode_recommendations(self, fallback_manager):
        """Test recommendations for disabled mode"""
        fallback_manager.active_fallbacks["youtube"] = FallbackStrategy(
            mode=FallbackMode.DISABLED,
            description="Platform disabled",
            limitations=["All functionality disabled"]
        )
        
        recommendations = fallback_manager.get_fallback_recommendations("youtube")
        
        assert len(recommendations) > 0
        assert any("temporarily disabled" in rec for rec in recommendations)
        assert any("alternative platforms" in rec for rec in recommendations)

    def test_limited_search_recommendations(self, fallback_manager):
        """Test recommendations for limited search mode"""
        fallback_manager.active_fallbacks["youtube"] = FallbackStrategy(
            mode=FallbackMode.LIMITED_SEARCH,
            description="Limited search",
            limitations=["Reduced search capabilities"]
        )
        
        recommendations = fallback_manager.get_fallback_recommendations("youtube")
        
        assert len(recommendations) > 0
        assert any("limited search" in rec for rec in recommendations)
        assert any("simpler search terms" in rec for rec in recommendations)

    def test_no_recommendations_when_not_in_fallback(self, fallback_manager):
        """Test no recommendations when platform is not in fallback"""
        recommendations = fallback_manager.get_fallback_recommendations("youtube")
        assert len(recommendations) == 0


class TestFallbackMonitoring:
    """Test fallback monitoring and duration tracking"""

    @pytest.mark.asyncio
    async def test_fallback_manager_start_stop(self, fallback_manager):
        """Test fallback manager start and stop"""
        await fallback_manager.start()
        assert fallback_manager._monitor_task is not None
        
        await fallback_manager.stop()
        assert fallback_manager._stop_event.is_set()

    def test_fallback_duration_calculation(self, fallback_manager):
        """Test fallback duration calculation"""
        # Activate fallback
        fallback_manager.activate_fallback("youtube", "Duration test")
        
        # Check duration is calculated
        duration = fallback_manager._get_fallback_duration("youtube")
        assert duration is not None
        assert duration >= 0

    def test_fallback_duration_after_deactivation(self, fallback_manager):
        """Test duration calculation after deactivation"""
        # Activate and deactivate
        fallback_manager.activate_fallback("youtube", "Duration test")
        fallback_manager.deactivate_fallback("youtube", "Recovery")
        
        # Duration should be None after deactivation
        duration = fallback_manager._get_fallback_duration("youtube")
        assert duration is None

    def test_fallback_duration_no_history(self, fallback_manager):
        """Test duration calculation with no history"""
        duration = fallback_manager._get_fallback_duration("nonexistent")
        assert duration is None


class TestFallbackReporting:
    """Test fallback status reporting"""

    def test_comprehensive_fallback_report(self, fallback_manager):
        """Test comprehensive fallback report generation"""
        # Activate some fallbacks
        fallback_manager.activate_fallback("youtube", "Report test")
        fallback_manager.activate_fallback("rumble", "Report test")
        
        report = fallback_manager.get_fallback_report()
        
        # Check report structure
        assert "timestamp" in report
        assert "enabled" in report
        assert "summary" in report
        assert "active_fallbacks" in report
        assert "platform_strategies" in report
        assert "history_summary" in report
        
        # Check summary data
        summary = report["summary"]
        assert summary["active_fallbacks"] == 2
        assert summary["total_platforms"] > 0
        assert summary["fallback_rate"] > 0
        
        # Check active fallbacks
        active = report["active_fallbacks"]
        assert "youtube" in active
        assert "rumble" in active
        
        for platform, details in active.items():
            assert "mode" in details
            assert "description" in details
            assert "limitations" in details
            assert "duration_hours" in details

    def test_empty_fallback_report(self, fallback_manager):
        """Test report generation with no active fallbacks"""
        report = fallback_manager.get_fallback_report()
        
        assert report["summary"]["active_fallbacks"] == 0
        assert report["summary"]["fallback_rate"] == 0
        assert len(report["active_fallbacks"]) == 0

    def test_fallback_history_summary(self, fallback_manager):
        """Test fallback history summary in report"""
        # Create some history
        fallback_manager.activate_fallback("youtube", "History test 1")
        fallback_manager.deactivate_fallback("youtube", "Recovery 1")
        fallback_manager.activate_fallback("youtube", "History test 2")
        
        report = fallback_manager.get_fallback_report()
        history_summary = report["history_summary"]
        
        assert "youtube" in history_summary
        assert history_summary["youtube"] == 3  # 2 activations + 1 deactivation


class TestCustomStrategyConfiguration:
    """Test custom strategy configuration"""

    def test_configure_custom_strategies(self, fallback_manager, custom_strategy):
        """Test configuring custom strategies for a platform"""
        custom_strategies = [custom_strategy]
        
        fallback_manager.configure_platform_strategies("youtube", custom_strategies)
        
        assert fallback_manager.fallback_strategies["youtube"] == custom_strategies

    def test_configure_empty_strategies(self, fallback_manager):
        """Test configuring empty strategy list"""
        original_strategies = fallback_manager.fallback_strategies["youtube"].copy()
        
        fallback_manager.configure_platform_strategies("youtube", [])
        
        # Should remain unchanged
        assert fallback_manager.fallback_strategies["youtube"] == original_strategies

    def test_reconfigure_active_fallback(self, fallback_manager, custom_strategy):
        """Test reconfiguring strategies while fallback is active"""
        # Activate fallback
        fallback_manager.activate_fallback("youtube", "Initial activation")
        assert fallback_manager.is_platform_in_fallback("youtube")
        
        # Reconfigure strategies
        custom_strategies = [custom_strategy]
        fallback_manager.configure_platform_strategies("youtube", custom_strategies)
        
        # Should have been reactivated with new strategy
        assert fallback_manager.is_platform_in_fallback("youtube")
        active_strategy = fallback_manager.active_fallbacks["youtube"]
        assert active_strategy.mode == FallbackMode.LIMITED_SEARCH


class TestFallbackHistoryManagement:
    """Test fallback history management"""

    def test_clear_platform_history(self, fallback_manager):
        """Test clearing history for specific platform"""
        # Create history
        fallback_manager.activate_fallback("youtube", "History test")
        fallback_manager.deactivate_fallback("youtube", "Recovery")
        
        assert len(fallback_manager.fallback_history["youtube"]) == 2
        
        # Clear specific platform history
        fallback_manager.clear_fallback_history("youtube")
        
        assert len(fallback_manager.fallback_history["youtube"]) == 0

    def test_clear_all_history(self, fallback_manager):
        """Test clearing all fallback history"""
        # Create history for multiple platforms
        fallback_manager.activate_fallback("youtube", "History test")
        fallback_manager.activate_fallback("rumble", "History test")
        
        assert len(fallback_manager.fallback_history) > 0
        
        # Clear all history
        fallback_manager.clear_fallback_history()
        
        assert len(fallback_manager.fallback_history) == 0

    def test_clear_nonexistent_platform_history(self, fallback_manager):
        """Test clearing history for nonexistent platform"""
        # Should not raise error
        fallback_manager.clear_fallback_history("nonexistent_platform")


class TestFallbackStrategyDataStructure:
    """Test FallbackStrategy data structure"""

    def test_strategy_to_dict(self, custom_strategy):
        """Test strategy conversion to dictionary"""
        strategy_dict = custom_strategy.to_dict()
        
        expected_keys = ["mode", "description", "limitations", "enabled", "priority"]
        for key in expected_keys:
            assert key in strategy_dict
        
        assert strategy_dict["mode"] == "limited_search"
        assert strategy_dict["description"] == "Custom test strategy"
        assert strategy_dict["limitations"] == ["Test limitation 1", "Test limitation 2"]
        assert strategy_dict["enabled"] is True
        assert strategy_dict["priority"] == 1

    def test_strategy_defaults(self):
        """Test strategy default values"""
        strategy = FallbackStrategy(
            mode=FallbackMode.API_ONLY,
            description="Test strategy",
            limitations=["Test limitation"]
        )
        
        assert strategy.enabled is True
        assert strategy.priority == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])