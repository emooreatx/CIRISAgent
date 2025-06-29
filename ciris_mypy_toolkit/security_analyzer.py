"""
Security Analysis Module - Ensures 100% security compliance in CIRIS codebase
"""

import ast
import re
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
import logging

logger = logging.getLogger(__name__)

class SecurityAnalyzer:
    """
    Comprehensive security analysis for CIRIS Agent codebase.
    Enforces cryptographic requirements, secrets handling, and security protocols.
    """
    
    def __init__(self, target_dir: str = "ciris_engine"):
        self.target_dir = Path(target_dir)
        self.security_violations = []
        self.crypto_requirements = self._load_crypto_requirements()
        
    def _load_crypto_requirements(self) -> Dict[str, Any]:
        """Load cryptographic and security requirements."""
        return {
            'required_encryption': 'AES-256-GCM',
            'required_hash': 'SHA-256',
            'required_signature': 'RSA-2048',
            'forbidden_patterns': [
                r'md5\(',
                r'sha1\(',
                r'DES\(',
                r'RC4\(',
                r'password\s*=\s*["\'][^"\']*["\']',  # Hardcoded passwords
                r'api_key\s*=\s*["\'][^"\']*["\']',   # Hardcoded API keys
                r'secret\s*=\s*["\'][^"\']*["\']',    # Hardcoded secrets
            ],
            'required_imports': {
                'cryptography',
                'secrets',
                'hashlib'
            }
        }
    
    def analyze_security_compliance(self, file_path: str) -> Dict[str, Any]:
        """Comprehensive security analysis of a Python file."""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            violations = []
            
            # Check for forbidden security patterns
            violations.extend(self._check_forbidden_patterns(content, file_path))
            
            # Check cryptographic compliance
            violations.extend(self._check_crypto_compliance(content, file_path))
            
            # Check secrets handling
            violations.extend(self._check_secrets_handling(content, file_path))
            
            # Check for security imports
            violations.extend(self._check_security_imports(content, file_path))
            
            # AST-based security checks
            try:
                tree = ast.parse(content)
                violations.extend(self._ast_security_checks(tree, file_path))
            except SyntaxError:
                violations.append({
                    'type': 'syntax_error',
                    'file': file_path,
                    'line': 0,
                    'severity': 'HIGH',
                    'message': 'Cannot parse file for security analysis',
                    'recommendation': 'Fix syntax errors first'
                })
            
            return {
                'file': file_path,
                'security_compliant': len(violations) == 0,
                'violations': violations,
                'total_violations': len(violations),
                'severity_breakdown': self._categorize_by_severity(violations)
            }
            
        except Exception as e:
            return {
                'file': file_path,
                'security_compliant': False,
                'violations': [{
                    'type': 'analysis_error',
                    'file': file_path,
                    'line': 0,
                    'severity': 'HIGH',
                    'message': f'Security analysis failed: {e}',
                    'recommendation': 'Fix file access or format issues'
                }],
                'total_violations': 1,
                'severity_breakdown': {'HIGH': 1}
            }
    
    def _check_forbidden_patterns(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Check for forbidden security patterns."""
        violations = []
        
        for pattern in self.crypto_requirements['forbidden_patterns']:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                violations.append({
                    'type': 'forbidden_pattern',
                    'file': file_path,
                    'line': line_num,
                    'severity': 'CRITICAL',
                    'message': f'Forbidden security pattern: {match.group()}',
                    'recommendation': 'Use approved cryptographic methods from ciris_engine.secrets'
                })
        
        return violations
    
    def _check_crypto_compliance(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Check cryptographic implementation compliance."""
        violations = []
        
        # Check for proper encryption usage
        if 'encrypt' in content.lower() or 'cipher' in content.lower():
            if 'AES' not in content and 'ciris_engine.secrets' not in content:
                violations.append({
                    'type': 'crypto_compliance',
                    'file': file_path,
                    'line': 0,
                    'severity': 'HIGH',
                    'message': 'Encryption usage without AES-256-GCM compliance',
                    'recommendation': 'Use ciris_engine.secrets.encryption module'
                })
        
        # Check for hash usage
        hash_patterns = ['hashlib.md5', 'hashlib.sha1']
        for pattern in hash_patterns:
            if pattern in content:
                line_num = content.find(pattern)
                line_num = content[:line_num].count('\n') + 1 if line_num != -1 else 0
                violations.append({
                    'type': 'weak_hash',
                    'file': file_path,
                    'line': line_num,
                    'severity': 'HIGH',
                    'message': f'Weak hash algorithm: {pattern}',
                    'recommendation': 'Use SHA-256 or stronger'
                })
        
        return violations
    
    def _check_secrets_handling(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Check proper secrets handling."""
        violations = []
        
        # Check for environment variable usage for secrets
        env_patterns = [
            r'os\.environ\[[\'"](.*SECRET.*|.*KEY.*|.*PASSWORD.*)[\'\"]\]',
            r'os\.getenv\([\'"](.*SECRET.*|.*KEY.*|.*PASSWORD.*)[\'\"]\)'
        ]
        
        for pattern in env_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                # This is GOOD practice, but check if it's in secrets module
                if 'ciris_engine/secrets/' not in file_path:
                    line_num = content[:match.start()].count('\n') + 1
                    violations.append({
                        'type': 'secrets_handling',
                        'file': file_path,
                        'line': line_num,
                        'severity': 'MEDIUM',
                        'message': 'Direct environment variable access for secrets',
                        'recommendation': 'Use ciris_engine.secrets.service for centralized secrets management'
                    })
        
        # Check for potential secret logging
        log_patterns = [
            r'log.*\.(debug|info|warning|error).*\b(password|secret|key|token)\b',
            r'print.*\b(password|secret|key|token)\b'
        ]
        
        for pattern in log_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                violations.append({
                    'type': 'secret_exposure',
                    'file': file_path,
                    'line': line_num,
                    'severity': 'CRITICAL',
                    'message': 'Potential secret logging detected',
                    'recommendation': 'Remove secret information from logs'
                })
        
        return violations
    
    def _check_security_imports(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Check for required security imports in relevant files."""
        violations = []
        
        # Files that handle encryption/security should import proper modules
        security_keywords = ['encrypt', 'decrypt', 'hash', 'sign', 'verify', 'secret']
        uses_security = any(keyword in content.lower() for keyword in security_keywords)
        
        if uses_security and 'ciris_engine/secrets/' not in file_path:
            has_ciris_secrets = 'from ciris_engine.secrets' in content or 'import ciris_engine.secrets' in content
            if not has_ciris_secrets:
                violations.append({
                    'type': 'missing_security_import',
                    'file': file_path,
                    'line': 0,
                    'severity': 'MEDIUM',
                    'message': 'Uses security operations without importing ciris_engine.secrets',
                    'recommendation': 'Import and use ciris_engine.secrets for security operations'
                })
        
        return violations
    
    def _ast_security_checks(self, tree: ast.AST, file_path: str) -> List[Dict[str, Any]]:
        """AST-based security analysis."""
        violations = []
        
        for node in ast.walk(tree):
            # Check for eval() usage
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'eval':
                violations.append({
                    'type': 'dangerous_function',
                    'file': file_path,
                    'line': node.lineno,
                    'severity': 'CRITICAL',
                    'message': 'Use of eval() function detected',
                    'recommendation': 'Avoid eval() - use safe alternatives'
                })
            
            # Check for exec() usage
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'exec':
                violations.append({
                    'type': 'dangerous_function',
                    'file': file_path,
                    'line': node.lineno,
                    'severity': 'CRITICAL',
                    'message': 'Use of exec() function detected',
                    'recommendation': 'Avoid exec() - use safe alternatives'
                })
            
            # Check for subprocess without shell=False
            if (isinstance(node, ast.Call) and 
                isinstance(node.func, ast.Attribute) and 
                node.func.attr in ['call', 'run', 'Popen']):
                
                # Check if shell=True is used
                for keyword in node.keywords:
                    if keyword.arg == 'shell' and isinstance(keyword.value, ast.Constant) and keyword.value.value:
                        violations.append({
                            'type': 'shell_injection_risk',
                            'file': file_path,
                            'line': node.lineno,
                            'severity': 'HIGH',
                            'message': 'subprocess call with shell=True',
                            'recommendation': 'Use shell=False and pass command as list'
                        })
        
        return violations
    
    def _categorize_by_severity(self, violations: List[Dict[str, Any]]) -> Dict[str, int]:
        """Categorize violations by severity."""
        severity_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
        for violation in violations:
            severity = violation.get('severity', 'LOW')
            severity_counts[severity] += 1
        return severity_counts
    
    def analyze_all_files(self) -> Dict[str, Any]:
        """Analyze all Python files in the target directory."""
        all_violations = []
        file_results = {}
        
        for py_file in self.target_dir.rglob("*.py"):
            if py_file.name.startswith('.'):
                continue
                
            result = self.analyze_security_compliance(str(py_file))
            file_results[str(py_file)] = result
            all_violations.extend(result['violations'])
        
        return {
            'total_files_analyzed': len(file_results),
            'total_violations': len(all_violations),
            'security_compliant_files': sum(1 for r in file_results.values() if r['security_compliant']),
            'overall_security_score': self._calculate_security_score(file_results),
            'severity_breakdown': self._categorize_by_severity(all_violations),
            'file_results': file_results,
            'critical_files': self._identify_critical_files(file_results)
        }
    
    def _calculate_security_score(self, file_results: Dict[str, Any]) -> float:
        """Calculate overall security compliance score (0-100)."""
        if not file_results:
            return 100.0
        
        total_files = len(file_results)
        compliant_files = sum(1 for r in file_results.values() if r['security_compliant'])
        
        return (compliant_files / total_files) * 100
    
    def _identify_critical_files(self, file_results: Dict[str, Any]) -> List[str]:
        """Identify files with critical security violations."""
        critical_files = []
        
        for file_path, result in file_results.items():
            has_critical = any(v['severity'] == 'CRITICAL' for v in result['violations'])
            if has_critical:
                critical_files.append(file_path)
        
        return critical_files
    
    def generate_security_report(self) -> str:
        """Generate a comprehensive security report."""
        analysis = self.analyze_all_files()
        
        report = [
            "🔒 CIRIS Security Analysis Report",
            "=" * 50,
            f"📊 Overall Security Score: {analysis['overall_security_score']:.1f}%",
            f"📁 Files Analyzed: {analysis['total_files_analyzed']}",
            f"✅ Security Compliant: {analysis['security_compliant_files']}",
            f"⚠️  Total Violations: {analysis['total_violations']}",
            "",
            "🚨 Severity Breakdown:",
        ]
        
        for severity, count in analysis['severity_breakdown'].items():
            if count > 0:
                report.append(f"   {severity}: {count}")
        
        if analysis['critical_files']:
            report.extend([
                "",
                "🔥 Critical Security Issues:",
                *[f"   • {file}" for file in analysis['critical_files']]
            ])
        
        return "\n".join(report)
