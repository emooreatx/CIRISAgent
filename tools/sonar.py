#!/usr/bin/env python3
"""
SonarCloud Issue Management Tool

Simple CLI for managing SonarCloud issues for the CIRIS project.
Uses token from ~/.sonartoken for authentication.

Usage:
    python tools/sonar.py list [--severity CRITICAL] [--limit 10]
    python tools/sonar.py mark-fp ISSUE_KEY [--comment "Reason"]
    python tools/sonar.py mark-wontfix ISSUE_KEY [--comment "Reason"]
    python tools/sonar.py reopen ISSUE_KEY
    python tools/sonar.py stats
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any
import requests
from datetime import datetime

# Configuration
SONAR_TOKEN_FILE = Path.home() / ".sonartoken"
SONAR_API_BASE = "https://sonarcloud.io/api"
PROJECT_KEY = "CIRISAI_CIRISAgent"


class SonarClient:
    """Simple SonarCloud API client."""
    
    def __init__(self, token: str):
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}"
        })
    
    def search_issues(self, severity: Optional[str] = None, 
                     resolved: bool = False, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for issues in the project."""
        params = {
            "componentKeys": PROJECT_KEY,
            "resolved": str(resolved).lower(),
            "ps": limit
        }
        if severity:
            params["severities"] = severity.upper()
        
        response = self.session.get(f"{SONAR_API_BASE}/issues/search", params=params)
        response.raise_for_status()
        return response.json()["issues"]
    
    def transition_issue(self, issue_key: str, transition: str, comment: Optional[str] = None) -> Dict[str, Any]:
        """Transition an issue (mark as false positive, won't fix, etc)."""
        data = {
            "issue": issue_key,
            "transition": transition
        }
        if comment:
            data["comment"] = comment
        
        response = self.session.post(
            f"{SONAR_API_BASE}/issues/do_transition",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()
        return response.json()
    
    def add_comment(self, issue_key: str, comment: str) -> Dict[str, Any]:
        """Add a comment to an issue."""
        data = {
            "issue": issue_key,
            "text": comment
        }
        
        response = self.session.post(
            f"{SONAR_API_BASE}/issues/add_comment",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()
        return response.json()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get issue statistics for the project."""
        response = self.session.get(
            f"{SONAR_API_BASE}/issues/search",
            params={
                "componentKeys": PROJECT_KEY,
                "resolved": "false",
                "facets": "severities,types,rules",
                "ps": 1
            }
        )
        response.raise_for_status()
        data = response.json()
        
        stats = {
            "total": data["total"],
            "by_severity": {},
            "by_type": {},
            "top_rules": []
        }
        
        for facet in data["facets"]:
            if facet["property"] == "severities":
                stats["by_severity"] = {v["val"]: v["count"] for v in facet["values"]}
            elif facet["property"] == "types":
                stats["by_type"] = {v["val"]: v["count"] for v in facet["values"]}
            elif facet["property"] == "rules":
                stats["top_rules"] = [(v["val"], v["count"]) for v in facet["values"][:5]]
        
        return stats


def format_issue(issue: Dict[str, Any]) -> str:
    """Format an issue for display."""
    file_path = issue["component"].split(":")[-1]
    created = datetime.fromisoformat(issue["creationDate"].replace("Z", "+00:00"))
    created_str = created.strftime("%Y-%m-%d")
    
    return (
        f"[{issue['severity']}] {issue['key']} - {issue['rule']}\n"
        f"  File: {file_path}:{issue.get('line', '?')}\n"
        f"  Message: {issue['message']}\n"
        f"  Created: {created_str}\n"
    )


def main():
    parser = argparse.ArgumentParser(description="SonarCloud Issue Management Tool")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List issues")
    list_parser.add_argument("--severity", choices=["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"],
                           help="Filter by severity")
    list_parser.add_argument("--limit", type=int, default=20, help="Number of issues to show")
    list_parser.add_argument("--resolved", action="store_true", help="Show resolved issues")
    
    # Mark false positive
    fp_parser = subparsers.add_parser("mark-fp", help="Mark issue as false positive")
    fp_parser.add_argument("issue_key", help="Issue key to mark")
    fp_parser.add_argument("--comment", help="Comment explaining why it's a false positive")
    
    # Mark won't fix
    wf_parser = subparsers.add_parser("mark-wontfix", help="Mark issue as won't fix")
    wf_parser.add_argument("issue_key", help="Issue key to mark")
    wf_parser.add_argument("--comment", help="Comment explaining why it won't be fixed")
    
    # Reopen
    reopen_parser = subparsers.add_parser("reopen", help="Reopen a resolved issue")
    reopen_parser.add_argument("issue_key", help="Issue key to reopen")
    
    # Stats
    stats_parser = subparsers.add_parser("stats", help="Show issue statistics")
    
    # Comment
    comment_parser = subparsers.add_parser("comment", help="Add comment to an issue")
    comment_parser.add_argument("issue_key", help="Issue key to comment on")
    comment_parser.add_argument("comment", help="Comment text")
    
    args = parser.parse_args()
    
    # Load token
    if not SONAR_TOKEN_FILE.exists():
        print(f"Error: Token file not found at {SONAR_TOKEN_FILE}")
        print("Please save your SonarCloud token to ~/.sonartoken")
        sys.exit(1)
    
    token = SONAR_TOKEN_FILE.read_text().strip()
    client = SonarClient(token)
    
    try:
        if args.command == "list":
            issues = client.search_issues(
                severity=args.severity,
                resolved=args.resolved,
                limit=args.limit
            )
            
            if not issues:
                print("No issues found matching criteria.")
            else:
                print(f"\nFound {len(issues)} issues:\n")
                for issue in issues:
                    print(format_issue(issue))
        
        elif args.command == "mark-fp":
            if args.comment:
                # Add comment first
                client.add_comment(args.issue_key, f"Marking as false positive: {args.comment}")
            
            result = client.transition_issue(args.issue_key, "falsepositive")
            print(f"✓ Marked {args.issue_key} as false positive")
            print(f"  Status: {result['issue']['issueStatus']}")
        
        elif args.command == "mark-wontfix":
            if args.comment:
                # Add comment first
                client.add_comment(args.issue_key, f"Marking as won't fix: {args.comment}")
            
            result = client.transition_issue(args.issue_key, "wontfix")
            print(f"✓ Marked {args.issue_key} as won't fix")
            print(f"  Status: {result['issue']['issueStatus']}")
        
        elif args.command == "reopen":
            result = client.transition_issue(args.issue_key, "reopen")
            print(f"✓ Reopened {args.issue_key}")
            print(f"  Status: {result['issue']['status']}")
        
        elif args.command == "comment":
            client.add_comment(args.issue_key, args.comment)
            print(f"✓ Added comment to {args.issue_key}")
        
        elif args.command == "stats":
            stats = client.get_stats()
            print(f"\nSonarCloud Statistics for {PROJECT_KEY}")
            print("=" * 50)
            print(f"Total Open Issues: {stats['total']}")
            
            print("\nBy Severity:")
            for severity in ["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"]:
                count = stats["by_severity"].get(severity, 0)
                if count > 0:
                    print(f"  {severity}: {count}")
            
            print("\nBy Type:")
            for issue_type, count in stats["by_type"].items():
                print(f"  {issue_type}: {count}")
            
            print("\nTop 5 Rules:")
            for rule, count in stats["top_rules"]:
                print(f"  {rule}: {count} issues")
        
        else:
            parser.print_help()
    
    except requests.exceptions.HTTPError as e:
        print(f"Error: {e}")
        if e.response.status_code == 401:
            print("Authentication failed. Check your token in ~/.sonartoken")
        elif e.response.status_code == 403:
            print("Permission denied. You may not have access to perform this action.")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()