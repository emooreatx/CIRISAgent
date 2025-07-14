"""
Monitor and analyze consolidation state.
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from collections import defaultdict

from .base import BaseDBTool, ReportFormatter


class ConsolidationMonitor(BaseDBTool):
    """Monitor consolidation progress and health."""
    
    def get_consolidation_gaps(self) -> Dict[str, Any]:
        """Find gaps in consolidation coverage."""
        gaps = {
            "basic_gaps": [],
            "extensive_gaps": [],
            "profound_gaps": [],
            "expected_vs_actual": {},
            "recommendations": []
        }
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Find the data range
            cursor.execute("""
                SELECT 
                    MIN(created_at) as oldest,
                    MAX(created_at) as newest
                FROM graph_nodes
                WHERE node_type IN ('tsdb_data', 'audit_entry', 'concept', 'observation')
            """)
            
            row = cursor.fetchone()
            if not row or not row["oldest"]:
                return gaps
            
            oldest = self.parse_timestamp(row["oldest"])
            newest = self.parse_timestamp(row["newest"])
            
            # Calculate expected consolidations
            data_age = (newest - oldest).total_seconds() / 3600  # Hours
            
            # Basic (6-hour)
            expected_basic = int(data_age / 6)
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM graph_nodes
                WHERE node_type = 'tsdb_summary'
                  AND json_extract(attributes_json, '$.consolidation_level') = 'basic'
            """)
            actual_basic = cursor.fetchone()["count"]
            
            gaps["expected_vs_actual"]["basic"] = {
                "expected": expected_basic,
                "actual": actual_basic,
                "coverage": (actual_basic / expected_basic * 100) if expected_basic > 0 else 0
            }
            
            # Find specific gaps in basic consolidation
            self._find_basic_gaps(cursor, oldest, newest, gaps)
            
            # Extensive (daily)
            if data_age >= 168:  # 7 days
                expected_extensive = int(data_age / 24)
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM graph_nodes
                    WHERE node_type = 'tsdb_summary'
                      AND json_extract(attributes_json, '$.consolidation_level') = 'extensive'
                """)
                actual_extensive = cursor.fetchone()["count"]
                
                gaps["expected_vs_actual"]["extensive"] = {
                    "expected": expected_extensive,
                    "actual": actual_extensive,
                    "coverage": (actual_extensive / expected_extensive * 100) if expected_extensive > 0 else 0
                }
            
            # Generate recommendations
            self._generate_gap_recommendations(gaps)
            
        return gaps
    
    def _find_basic_gaps(self, cursor, oldest: datetime, newest: datetime, gaps: Dict):
        """Find specific gaps in basic consolidation."""
        # Get all basic consolidation periods
        cursor.execute("""
            SELECT 
                json_extract(attributes_json, '$.period_start') as period_start,
                json_extract(attributes_json, '$.period_end') as period_end
            FROM graph_nodes
            WHERE node_type = 'tsdb_summary'
              AND json_extract(attributes_json, '$.consolidation_level') = 'basic'
            ORDER BY period_start
        """)
        
        consolidated_periods = []
        for row in cursor:
            if row["period_start"] and row["period_end"]:
                start = self.parse_timestamp(row["period_start"])
                end = self.parse_timestamp(row["period_end"])
                consolidated_periods.append((start, end))
        
        # Find gaps
        current = oldest.replace(hour=(oldest.hour // 6) * 6, minute=0, second=0, microsecond=0)
        cutoff = newest - timedelta(hours=30)  # Don't report gaps in last 30 hours
        
        while current < cutoff:
            period_end = current + timedelta(hours=6)
            
            # Check if this period is consolidated
            is_consolidated = any(
                start <= current < end for start, end in consolidated_periods
            )
            
            if not is_consolidated:
                # Check if there's data in this period
                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM graph_nodes
                    WHERE node_type IN ('tsdb_data', 'audit_entry', 'concept')
                      AND datetime(created_at) >= datetime(?)
                      AND datetime(created_at) < datetime(?)
                """, (current.isoformat(), period_end.isoformat()))
                
                if cursor.fetchone()["count"] > 0:
                    gaps["basic_gaps"].append({
                        "period_start": current.isoformat(),
                        "period_end": period_end.isoformat(),
                        "age": self.format_timedelta(datetime.now(timezone.utc) - current)
                    })
            
            current = period_end
    
    def _generate_gap_recommendations(self, gaps: Dict):
        """Generate recommendations based on gaps."""
        if gaps["basic_gaps"]:
            gaps["recommendations"].append({
                "severity": "HIGH",
                "issue": f"{len(gaps['basic_gaps'])} missing basic consolidation periods",
                "action": "Run catch-up consolidation for missed periods"
            })
        
        basic_coverage = gaps["expected_vs_actual"].get("basic", {}).get("coverage", 100)
        if basic_coverage < 80:
            gaps["recommendations"].append({
                "severity": "MEDIUM",
                "issue": f"Basic consolidation coverage only {basic_coverage:.1f}%",
                "action": "Check consolidation service health and scheduling"
            })
    
    def get_retention_analysis(self) -> Dict[str, Any]:
        """Analyze data retention and cleanup effectiveness."""
        analysis = {
            "raw_data": {
                "total": 0,
                "should_be_cleaned": 0,
                "oldest": None
            },
            "basic_summaries": {
                "total": 0,
                "should_be_consolidated": 0,
                "oldest": None
            },
            "storage_estimate": {
                "current_size_mb": 0,
                "optimal_size_mb": 0,
                "savings_potential_mb": 0
            }
        }
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Raw data analysis
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN datetime(created_at) < datetime('now', '-24 hours') THEN 1 END) as old_count,
                    MIN(created_at) as oldest
                FROM graph_nodes
                WHERE node_type = 'tsdb_data'
            """)
            
            row = cursor.fetchone()
            if row:
                analysis["raw_data"]["total"] = row["total"]
                analysis["raw_data"]["should_be_cleaned"] = row["old_count"]
                analysis["raw_data"]["oldest"] = row["oldest"]
            
            # Basic summaries analysis
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN datetime(created_at) < datetime('now', '-7 days') THEN 1 END) as old_count,
                    MIN(created_at) as oldest
                FROM graph_nodes
                WHERE node_type = 'tsdb_summary'
                  AND json_extract(attributes_json, '$.consolidation_level') = 'basic'
            """)
            
            row = cursor.fetchone()
            if row:
                analysis["basic_summaries"]["total"] = row["total"]
                analysis["basic_summaries"]["should_be_consolidated"] = row["old_count"]
                analysis["basic_summaries"]["oldest"] = row["oldest"]
            
            # Storage estimate (rough)
            # Assume each node is ~1KB on average
            total_nodes = analysis["raw_data"]["total"] + analysis["basic_summaries"]["total"]
            deletable_nodes = analysis["raw_data"]["should_be_cleaned"] + analysis["basic_summaries"]["should_be_consolidated"]
            
            analysis["storage_estimate"]["current_size_mb"] = (total_nodes * 1024) / (1024 * 1024)
            analysis["storage_estimate"]["optimal_size_mb"] = ((total_nodes - deletable_nodes) * 1024) / (1024 * 1024)
            analysis["storage_estimate"]["savings_potential_mb"] = (
                analysis["storage_estimate"]["current_size_mb"] - 
                analysis["storage_estimate"]["optimal_size_mb"]
            )
            
        return analysis
    
    def print_consolidation_health_report(self):
        """Print comprehensive consolidation health report."""
        formatter = ReportFormatter()
        formatter.print_section("CONSOLIDATION HEALTH REPORT")
        
        # Gaps analysis
        gaps = self.get_consolidation_gaps()
        
        formatter.print_subsection("Consolidation Coverage")
        for level, stats in gaps["expected_vs_actual"].items():
            print(f"\n{level.capitalize()} Consolidation:")
            print(f"  Expected: {stats['expected']}")
            print(f"  Actual: {stats['actual']}")
            print(f"  Coverage: {stats['coverage']:.1f}%")
        
        if gaps["basic_gaps"]:
            formatter.print_subsection("Missing Basic Consolidation Periods")
            print(f"Found {len(gaps['basic_gaps'])} gaps:")
            for gap in gaps["basic_gaps"][:5]:
                start = self.parse_timestamp(gap["period_start"])
                print(f"  {start.strftime('%Y-%m-%d %H:%M')} - Age: {gap['age']}")
            if len(gaps["basic_gaps"]) > 5:
                print(f"  ... and {len(gaps['basic_gaps']) - 5} more")
        
        # Retention analysis
        retention = self.get_retention_analysis()
        
        formatter.print_subsection("Data Retention Status")
        
        if retention["raw_data"]["oldest"]:
            oldest = self.parse_timestamp(retention["raw_data"]["oldest"])
            age = datetime.now(timezone.utc) - oldest
            print(f"\nRaw TSDB Data:")
            print(f"  Total Nodes: {retention['raw_data']['total']:,}")
            print(f"  Should Be Cleaned: {retention['raw_data']['should_be_cleaned']:,}")
            print(f"  Oldest: {oldest.strftime('%Y-%m-%d %H:%M')} ({self.format_timedelta(age)} ago)")
        
        if retention["basic_summaries"]["oldest"]:
            oldest = self.parse_timestamp(retention["basic_summaries"]["oldest"])
            age = datetime.now(timezone.utc) - oldest
            print(f"\nBasic Summaries:")
            print(f"  Total: {retention['basic_summaries']['total']:,}")
            print(f"  Should Be Consolidated: {retention['basic_summaries']['should_be_consolidated']:,}")
            print(f"  Oldest: {oldest.strftime('%Y-%m-%d %H:%M')} ({self.format_timedelta(age)} ago)")
        
        print(f"\nStorage Estimate:")
        print(f"  Current Size: {retention['storage_estimate']['current_size_mb']:.1f} MB")
        print(f"  Optimal Size: {retention['storage_estimate']['optimal_size_mb']:.1f} MB")
        print(f"  Potential Savings: {retention['storage_estimate']['savings_potential_mb']:.1f} MB")
        
        # Recommendations
        if gaps["recommendations"]:
            formatter.print_subsection("Recommendations")
            for rec in gaps["recommendations"]:
                print(f"\n[{rec['severity']}] {rec['issue']}")
                print(f"  Action: {rec['action']}")