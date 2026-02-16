#!/usr/bin/env python3
"""
CHANGELOG Generator for lbf-ham-radio

Parses git log for conventional commits and generates CHANGELOG.md
grouped by version tags.

Supports conventional commit format:
- feat: New features
- fix: Bug fixes  
- docs: Documentation changes
- chore: Build/maintenance tasks
- ci: CI/CD changes
- refactor: Code refactoring
- style: Code style/formatting
- test: Test additions/changes
- perf: Performance improvements
- build: Build system changes

Usage:
    python scripts/generate-changelog.py
"""

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple


class ChangelogGenerator:
    def __init__(self, repo_path: str = "."):
        self.repo_path = Path(repo_path)
        self.commit_types = {
            "feat": ("✨ Features", "🚀"),
            "fix": ("🐛 Bug Fixes", "🔧"),
            "docs": ("📚 Documentation", "📝"),
            "chore": ("🛠️ Maintenance", "⚙️"),
            "ci": ("🔄 CI/CD", "🚀"),
            "refactor": ("♻️ Code Refactoring", "🔄"),
            "style": ("💎 Style", "✨"),
            "test": ("🧪 Tests", "✅"),
            "perf": ("⚡ Performance", "🚀"),
            "build": ("📦 Build System", "🔧"),
        }
        
    def run_git_command(self, cmd: List[str]) -> str:
        """Run a git command and return the output."""
        try:
            result = subprocess.run(
                cmd, 
                cwd=self.repo_path,
                capture_output=True, 
                text=True, 
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Git command failed: {' '.join(cmd)}")
            print(f"Error: {e.stderr}")
            return ""
    
    def get_tags(self) -> List[Tuple[str, str]]:
        """Get all tags with their commit dates, sorted by semver."""
        tags_output = self.run_git_command([
            "git", "tag", "--list", "--sort=-version:refname", 
            "--format=%(refname:short) %(creatordate:short)"
        ])
        
        if not tags_output:
            return []
            
        tags = []
        for line in tags_output.split('\n'):
            parts = line.split()
            if len(parts) >= 2:
                tag_name = parts[0]
                tag_date = parts[1]
                tags.append((tag_name, tag_date))
        
        # Sort by version (reverse chronological, latest first)
        return tags
    
    def get_commits_between_tags(self, start_tag: str = None, end_tag: str = None) -> List[Dict]:
        """Get commits between two tags (or from tag to HEAD if end_tag is None)."""
        if start_tag and end_tag:
            commit_range = f"{end_tag}..{start_tag}"
        elif start_tag:
            commit_range = f"{start_tag}"
        else:
            commit_range = "HEAD"
            
        # Get commit log with format: hash|subject|date
        log_output = self.run_git_command([
            "git", "log", commit_range, 
            "--pretty=format:%H|%s|%ci", 
            "--no-merges"
        ])
        
        if not log_output:
            return []
            
        commits = []
        for line in log_output.split('\n'):
            parts = line.split('|', 2)
            if len(parts) == 3:
                hash_val, subject, date = parts
                commits.append({
                    'hash': hash_val[:8],  # Short hash
                    'subject': subject,
                    'date': date[:10],     # YYYY-MM-DD
                })
        
        return commits
    
    def parse_conventional_commit(self, subject: str) -> Tuple[str, str, str]:
        """Parse conventional commit format: type(scope): description"""
        # Match: type(optional-scope): description
        pattern = r'^(\w+)(?:\(([^)]+)\))?:\s*(.+)$'
        match = re.match(pattern, subject)
        
        if match:
            commit_type = match.group(1).lower()
            scope = match.group(2) or ""
            description = match.group(3)
            return commit_type, scope, description
        else:
            # Not a conventional commit, treat as misc
            return "misc", "", subject
    
    def group_commits_by_type(self, commits: List[Dict]) -> Dict[str, List[Dict]]:
        """Group commits by their conventional commit type."""
        grouped = {}
        
        for commit in commits:
            commit_type, scope, description = self.parse_conventional_commit(commit['subject'])
            
            if commit_type not in grouped:
                grouped[commit_type] = []
                
            grouped[commit_type].append({
                **commit,
                'type': commit_type,
                'scope': scope,
                'description': description,
            })
        
        return grouped
    
    def format_changelog_section(self, version: str, date: str, commits_by_type: Dict[str, List[Dict]]) -> str:
        """Format a changelog section for a specific version."""
        lines = []
        lines.append(f"## [{version}] - {date}")
        lines.append("")
        
        # Order commit types by importance
        type_order = [
            "feat", "fix", "perf", "refactor", 
            "docs", "ci", "build", "test", "chore", "style", "misc"
        ]
        
        for commit_type in type_order:
            if commit_type in commits_by_type:
                commits = commits_by_type[commit_type]
                
                # Get type info
                if commit_type in self.commit_types:
                    type_title, type_emoji = self.commit_types[commit_type]
                else:
                    type_title = "📝 Miscellaneous"
                    type_emoji = "📝"
                
                lines.append(f"### {type_title}")
                lines.append("")
                
                for commit in commits:
                    # Format: - description (scope) [hash]
                    scope_text = f" ({commit['scope']})" if commit['scope'] else ""
                    lines.append(f"- {commit['description']}{scope_text} [`{commit['hash']}`]")
                
                lines.append("")
        
        lines.append("---")
        lines.append("")
        
        return "\n".join(lines)
    
    def get_project_info(self) -> Dict[str, str]:
        """Get project information from git and files."""
        try:
            # Get project name from directory or pyproject.toml
            project_name = self.repo_path.name
            
            # Try to get a better name from pyproject.toml
            pyproject_path = self.repo_path / "pyproject.toml"
            if pyproject_path.exists():
                with open(pyproject_path) as f:
                    content = f.read()
                    name_match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
                    if name_match:
                        project_name = name_match.group(1)
            
            # Get remote URL
            remote_url = self.run_git_command(["git", "remote", "get-url", "origin"])
            
            return {
                "name": project_name,
                "remote_url": remote_url,
            }
        except Exception:
            return {
                "name": "Project",
                "remote_url": "",
            }
    
    def generate_changelog_header(self, project_info: Dict[str, str]) -> str:
        """Generate changelog header."""
        lines = []
        lines.append("# Changelog")
        lines.append("")
        lines.append(f"All notable changes to **{project_info['name']}** will be documented in this file.")
        lines.append("")
        lines.append("The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),")
        lines.append("and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).")
        lines.append("")
        lines.append("*Generated automatically by `scripts/generate-changelog.py`*")
        lines.append("")
        
        return "\n".join(lines)
    
    def generate_changelog_footer(self, project_info: Dict[str, str]) -> str:
        """Generate changelog footer."""
        lines = []
        
        if "github.com" in project_info['remote_url']:
            # Extract GitHub repo info
            github_match = re.search(r'github\.com[:/]([^/]+)/([^/.]+)', project_info['remote_url'])
            if github_match:
                owner = github_match.group(1)
                repo = github_match.group(2)
                
                lines.append("## Links")
                lines.append("")
                lines.append(f"- 📖 [Repository](https://github.com/{owner}/{repo})")
                lines.append(f"- 🐛 [Issues](https://github.com/{owner}/{repo}/issues)")
                lines.append(f"- 🚀 [Releases](https://github.com/{owner}/{repo}/releases)")
                lines.append("")
        
        lines.append("---")
        lines.append("")
        lines.append("*Generated with ❤️ by the changelog automation system*")
        lines.append("")
        
        return "\n".join(lines)
    
    def generate(self, output_path: str = "CHANGELOG.md") -> bool:
        """Generate the complete changelog."""
        print("🚀 Generating changelog...")
        
        # Get project info
        project_info = self.get_project_info()
        print(f"📦 Project: {project_info['name']}")
        
        # Get all tags
        tags = self.get_tags()
        if not tags:
            print("❌ No tags found in repository")
            return False
            
        print(f"🏷️  Found {len(tags)} tags: {[t[0] for t in tags]}")
        
        # Start building changelog
        changelog_lines = []
        
        # Add header
        changelog_lines.append(self.generate_changelog_header(project_info))
        
        # Process each version
        for i, (tag, tag_date) in enumerate(tags):
            print(f"📝 Processing {tag} ({tag_date})...")
            
            # Get commits for this version
            # For the latest tag, get commits since previous tag
            # For older tags, get commits between this tag and the next one
            if i == 0:
                # Latest tag: from previous tag to this tag
                prev_tag = tags[1][0] if len(tags) > 1 else None
                commits = self.get_commits_between_tags(tag, prev_tag)
            else:
                # Older tags: from this tag to previous tag
                prev_tag = tags[i-1][0]
                commits = self.get_commits_between_tags(prev_tag, tag)
            
            if not commits:
                print(f"   ⚠️  No commits found for {tag}")
                continue
                
            print(f"   📊 Found {len(commits)} commits")
            
            # Group commits by type
            commits_by_type = self.group_commits_by_type(commits)
            
            # Format section
            section = self.format_changelog_section(tag, tag_date, commits_by_type)
            changelog_lines.append(section)
        
        # Add footer
        changelog_lines.append(self.generate_changelog_footer(project_info))
        
        # Write to file
        output_file = self.repo_path / output_path
        with open(output_file, 'w') as f:
            f.write('\n'.join(changelog_lines))
        
        print(f"✅ Changelog generated: {output_file}")
        print(f"📄 Total lines: {sum(content.count('\\n') for content in changelog_lines)}")
        
        return True


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        repo_path = sys.argv[1]
    else:
        repo_path = "."
    
    generator = ChangelogGenerator(repo_path)
    
    try:
        success = generator.generate()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()