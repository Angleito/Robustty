#!/usr/bin/env python3
"""
Discord 530 Master Controller - Unified diagnostic workflow.
Orchestrates quick decision tree and comprehensive diagnostics with intelligent workflow.
"""

import os
import sys
import asyncio
import json
import argparse
import subprocess
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Discord530Master:
    """Master controller for Discord 530 diagnostic workflow."""
    
    def __init__(self):
        self.results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "workflow": [],
            "quick_diagnosis": None,
            "comprehensive_analysis": None,
            "final_recommendations": [],
            "resolution_status": "pending"
        }
        self.scripts_dir = Path(__file__).parent
    
    async def run_workflow(self, mode: str = "auto") -> Dict[str, Any]:
        """Run the complete diagnostic workflow."""
        print("🚀 Discord WebSocket 530 Master Diagnostic Controller")
        print("=" * 60)
        print(f"Mode: {mode.title()}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
        workflow_start = datetime.now()
        
        if mode in ["auto", "quick", "guided"]:
            await self._run_quick_diagnosis()
        
        if mode in ["auto", "comprehensive", "full"]:
            await self._run_comprehensive_analysis()
        
        # Generate final recommendations
        await self._generate_final_recommendations()
        
        # Calculate workflow duration
        workflow_duration = (datetime.now() - workflow_start).total_seconds()
        self.results["workflow_duration_seconds"] = workflow_duration
        
        # Print final summary
        self._print_final_summary()
        
        return self.results
    
    async def _run_quick_diagnosis(self):
        """Run the quick decision tree diagnosis."""
        print("\n🔍 PHASE 1: Quick Decision Tree Diagnosis")
        print("-" * 40)
        
        try:
            # Import and run decision tree
            sys.path.append(str(self.scripts_dir))
            module_name = 'discord-530-decision-tree'
            import importlib.util
            spec = importlib.util.spec_from_file_location("decision_tree", self.scripts_dir / "discord-530-decision-tree.py")
            decision_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(decision_module)
            Discord530DecisionTree = decision_module.Discord530DecisionTree
            
            tree = Discord530DecisionTree()
            quick_results = await tree.run_interactive_diagnosis()
            
            self.results["quick_diagnosis"] = quick_results
            self.results["workflow"].append({
                "phase": "quick_diagnosis",
                "status": "completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "found_solution": bool(quick_results.get("recommendations"))
            })
            
            print(f"\n✅ Quick diagnosis completed")
            if quick_results.get("recommendations"):
                print("💡 Immediate recommendations available")
                
        except Exception as e:
            print(f"❌ Quick diagnosis failed: {e}")
            self.results["workflow"].append({
                "phase": "quick_diagnosis",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    async def _run_comprehensive_analysis(self):
        """Run the comprehensive diagnostic analysis."""
        print("\n🔬 PHASE 2: Comprehensive Analysis")
        print("-" * 40)
        
        # Check if quick diagnosis resolved the issue
        quick_solved = (
            self.results.get("quick_diagnosis", {}).get("recommendations") and
            not self._requires_deep_analysis()
        )
        
        if quick_solved:
            print("⏭️  Skipping comprehensive analysis - quick diagnosis provided solution")
            self.results["workflow"].append({
                "phase": "comprehensive_analysis",
                "status": "skipped",
                "reason": "quick_diagnosis_sufficient",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            return
        
        try:
            # Import and run comprehensive diagnostics
            import importlib.util
            spec = importlib.util.spec_from_file_location("comprehensive", self.scripts_dir / "diagnose-discord-530-comprehensive.py")
            comprehensive_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(comprehensive_module)
            DiscordAuthDiagnostics = comprehensive_module.DiscordAuthDiagnostics
            
            diagnostics = DiscordAuthDiagnostics()
            comprehensive_results = await diagnostics.run_all_diagnostics()
            
            self.results["comprehensive_analysis"] = comprehensive_results
            self.results["workflow"].append({
                "phase": "comprehensive_analysis",
                "status": "completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "modules_run": len(comprehensive_results.get("modules", {})),
                "critical_issues": len(comprehensive_results.get("summary", {}).get("critical_issues", []))
            })
            
            print(f"\n✅ Comprehensive analysis completed")
            
        except Exception as e:
            print(f"❌ Comprehensive analysis failed: {e}")
            self.results["workflow"].append({
                "phase": "comprehensive_analysis",
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    def _requires_deep_analysis(self) -> bool:
        """Determine if deep analysis is needed based on quick diagnosis."""
        quick_results = self.results.get("quick_diagnosis", {})
        
        # Always run deep analysis if no quick results
        if not quick_results:
            return True
        
        # Check for complex issues that need deep analysis
        path = quick_results.get("path", [])
        
        # Look for terminal nodes that indicate complex issues
        complex_indicators = [
            "unknown",
            "network_issue", 
            "config_issue",
            "rate_limited"
        ]
        
        last_node = path[-1]["node"] if path else ""
        if any(indicator in last_node for indicator in complex_indicators):
            return True
        
        # Check findings for complexity indicators
        findings = quick_results.get("findings", {})
        
        # Multiple instances or session issues need deep analysis
        if findings.get("multiple_instances", {}).get("python_processes", 0) > 1:
            return True
        
        # Code issues need detailed audit
        if findings.get("code_issues"):
            return True
        
        # Rate limiting needs IP and timing analysis
        if findings.get("rate_limit_status", {}).get("is_rate_limited"):
            return True
        
        return False
    
    async def _generate_final_recommendations(self):
        """Generate final unified recommendations from all analyses."""
        print("\n📋 PHASE 3: Generating Final Recommendations")
        print("-" * 40)
        
        final_recs = []
        priority_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
        
        # Collect recommendations from quick diagnosis
        quick_recs = self.results.get("quick_diagnosis", {}).get("recommendations", [])
        if quick_recs:
            final_recs.append({
                "source": "quick_diagnosis",
                "priority": "HIGH",
                "category": "Immediate Actions",
                "actions": quick_recs
            })
        
        # Collect recommendations from comprehensive analysis
        comp_analysis = self.results.get("comprehensive_analysis", {})
        comp_recs = comp_analysis.get("recommendations", [])
        
        for rec in comp_recs:
            final_recs.append({
                "source": "comprehensive_analysis",
                "priority": rec.get("priority", "MEDIUM"),
                "category": rec.get("category", "General"),
                "actions": rec.get("actions", [])
            })
        
        # Add workflow-specific recommendations
        workflow_recs = self._generate_workflow_recommendations()
        final_recs.extend(workflow_recs)
        
        # Sort by priority
        def priority_score(rec):
            return priority_order.index(rec.get("priority", "LOW"))
        
        final_recs.sort(key=priority_score)
        
        # Remove duplicates and merge similar categories
        final_recs = self._deduplicate_recommendations(final_recs)
        
        self.results["final_recommendations"] = final_recs
        
        print(f"✅ Generated {len(final_recs)} recommendation categories")
    
    def _generate_workflow_recommendations(self) -> List[Dict[str, Any]]:
        """Generate recommendations based on workflow analysis."""
        workflow_recs = []
        
        # Check workflow failures
        failed_phases = [
            w for w in self.results["workflow"] 
            if w.get("status") == "failed"
        ]
        
        if failed_phases:
            workflow_recs.append({
                "source": "workflow_analysis",
                "priority": "MEDIUM",
                "category": "Diagnostic Issues",
                "actions": [
                    "Some diagnostic phases failed - manual investigation may be needed",
                    "Check network connectivity and permissions",
                    "Ensure all required Python packages are installed",
                    "Run individual diagnostic scripts manually if needed"
                ]
            })
        
        # Environment-specific recommendations
        comp_analysis = self.results.get("comprehensive_analysis", {})
        env_type = comp_analysis.get("summary", {}).get("environment_type", "Unknown")
        
        if env_type == "VPS":
            workflow_recs.append({
                "source": "workflow_analysis",
                "priority": "MEDIUM",
                "category": "VPS Optimizations",
                "actions": [
                    "Consider using VPS-specific voice connection settings",
                    "Implement longer retry delays for unstable networks",
                    "Monitor rate limit headers more closely",
                    "Use exponential backoff for connection attempts"
                ]
            })
        
        # Add monitoring recommendations
        workflow_recs.append({
            "source": "workflow_analysis",
            "priority": "LOW",
            "category": "Ongoing Monitoring",
            "actions": [
                "Set up automated health checks for your bot",
                "Monitor Discord status page: https://discordstatus.com",
                "Keep diagnostic scripts handy for future issues",
                "Document any custom fixes for your environment"
            ]
        })
        
        return workflow_recs
    
    def _deduplicate_recommendations(self, recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate recommendations and merge similar categories."""
        seen_actions = set()
        deduplicated = []
        
        for rec in recommendations:
            # Filter out duplicate actions
            unique_actions = []
            for action in rec.get("actions", []):
                action_key = action.lower().strip()
                if action_key not in seen_actions:
                    seen_actions.add(action_key)
                    unique_actions.append(action)
            
            if unique_actions:  # Only keep if there are unique actions
                rec["actions"] = unique_actions
                deduplicated.append(rec)
        
        return deduplicated
    
    def _print_final_summary(self):
        """Print the final summary and recommendations."""
        print("\n" + "=" * 60)
        print("🎯 FINAL DIAGNOSTIC SUMMARY")
        print("=" * 60)
        
        # Workflow status
        print(f"\n📊 Workflow Status:")
        for phase in self.results["workflow"]:
            status_icon = "✅" if phase["status"] == "completed" else "❌" if phase["status"] == "failed" else "⏭️"
            print(f"   {status_icon} {phase['phase'].replace('_', ' ').title()}: {phase['status'].title()}")
        
        # Quick diagnosis summary
        quick_results = self.results.get("quick_diagnosis")
        if quick_results:
            print(f"\n🔍 Quick Diagnosis:")
            findings = quick_results.get("findings", {})
            
            if "token_valid" in findings:
                status = "✅" if findings["token_valid"] else "❌"
                print(f"   {status} Token Status: {'Valid' if findings['token_valid'] else 'Invalid'}")
            
            if "multiple_instances" in findings:
                instances = findings["multiple_instances"]
                python_count = instances.get("python_processes", 0)
                docker_count = instances.get("docker_containers", 0)
                print(f"   🔄 Running Instances: {python_count} Python, {docker_count} Docker")
        
        # Comprehensive analysis summary
        comp_analysis = self.results.get("comprehensive_analysis")
        if comp_analysis:
            summary = comp_analysis.get("summary", {})
            print(f"\n🔬 Comprehensive Analysis:")
            print(f"   🔐 Authentication: {summary.get('authentication_status', 'Unknown')}")
            print(f"   🌍 Environment: {summary.get('environment_type', 'Unknown')}")
            print(f"   🚨 Critical Issues: {len(summary.get('critical_issues', []))}")
            print(f"   ⚠️  Warnings: {len(summary.get('warnings', []))}")
        
        # Final recommendations
        print(f"\n💡 FINAL RECOMMENDATIONS")
        print("-" * 40)
        
        final_recs = self.results.get("final_recommendations", [])
        if not final_recs:
            print("   ℹ️  No specific issues detected")
            print("   ✅ Your bot configuration appears to be correct")
            print("   🔄 Try restarting the bot if issues persist")
        else:
            for i, rec in enumerate(final_recs, 1):
                print(f"\n{i}. [{rec['priority']}] {rec['category']}")
                for j, action in enumerate(rec['actions'], 1):
                    print(f"   {j}. {action}")
        
        # Resolution guidance
        print(f"\n🎯 NEXT STEPS")
        print("-" * 40)
        
        critical_issues = []
        if comp_analysis:
            critical_issues = comp_analysis.get("summary", {}).get("critical_issues", [])
        
        if critical_issues:
            print("   🚨 CRITICAL: Address authentication/token issues first")
            print("   📝 Follow the recommendations in priority order")
            print("   🔄 Restart bot after making changes")
            self.results["resolution_status"] = "action_required"
        else:
            print("   ✅ No critical issues found")
            print("   🔧 Consider implementing the suggested optimizations")
            print("   📊 Monitor bot performance going forward")
            self.results["resolution_status"] = "monitoring_recommended"
        
        # Save comprehensive results
        self._save_results()
    
    def _save_results(self):
        """Save all results to files."""
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        
        # Save master results
        master_file = f"discord-530-master-{timestamp}.json"
        with open(master_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n📁 Master results saved to: {master_file}")
        
        # Save individual results if they exist
        if self.results.get("quick_diagnosis"):
            quick_file = f"discord-530-quick-{timestamp}.json"
            with open(quick_file, 'w') as f:
                json.dump(self.results["quick_diagnosis"], f, indent=2)
            print(f"📁 Quick diagnosis saved to: {quick_file}")
        
        if self.results.get("comprehensive_analysis"):
            comp_file = f"discord-530-comprehensive-{timestamp}.json"
            with open(comp_file, 'w') as f:
                json.dump(self.results["comprehensive_analysis"], f, indent=2)
            print(f"📁 Comprehensive analysis saved to: {comp_file}")


async def main():
    """Main entry point with command line interface."""
    parser = argparse.ArgumentParser(
        description="Discord WebSocket 530 Master Diagnostic Controller",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python discord-530-master.py                    # Auto mode (quick + comprehensive)
  python discord-530-master.py --mode quick       # Quick diagnosis only
  python discord-530-master.py --mode comprehensive # Comprehensive only
  python discord-530-master.py --mode guided      # Interactive guided mode
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['auto', 'quick', 'comprehensive', 'guided', 'full'],
        default='auto',
        help='Diagnostic mode to run (default: auto)'
    )
    
    parser.add_argument(
        '--no-save',
        action='store_true',
        help='Do not save results to files'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    # Set up environment
    if args.verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    
    # Run the master controller
    master = Discord530Master()
    
    try:
        results = await master.run_workflow(mode=args.mode)
        
        # Determine exit code based on results
        resolution_status = results.get("resolution_status", "unknown")
        
        if resolution_status == "action_required":
            print("\n⚠️  Critical issues found - action required")
            return 1
        elif resolution_status == "monitoring_recommended":
            print("\n✅ No critical issues - monitoring recommended")
            return 0
        else:
            print("\n❓ Diagnostic completed with unknown status")
            return 2
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Diagnostic interrupted by user")
        return 130
    except Exception as e:
        print(f"\n❌ Master diagnostic failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 2


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)