"""
Package management for generated tools.

Provides metadata tracking, status management, and package lifecycle.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolPackage:
    """Metadata for a generated tool package."""
    name: str
    owner: str = "system"
    created_at: str = ""
    created_from_trace: Optional[str] = None
    tests: List[str] = None  # List of test file paths
    status: str = "experimental"  # experimental, stable, deprecated
    version: str = "1.0.0"
    description: str = ""
    contract_path: str = ""
    implementation_path: str = ""
    dependencies: List[str] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if self.tests is None:
            self.tests = []
        if self.dependencies is None:
            self.dependencies = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolPackage":
        """Create from dictionary."""
        return cls(**data)
    
    def save(self, path: Path):
        """Save package metadata to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> Optional["ToolPackage"]:
        """Load package metadata from JSON file."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception as e:
            logger.warning(f"Failed to load package metadata from {path}: {e}")
            return None


class PackageManager:
    """Manages tool packages and their metadata."""
    
    def __init__(self, packages_dir: Path = None):
        """Initialize package manager.
        
        Args:
            packages_dir: Directory where package metadata is stored.
                          Defaults to mvp/.packages/
        """
        if packages_dir is None:
            # Default to mvp/.packages/
            base_dir = Path(__file__).resolve().parents[2]
            packages_dir = base_dir / ".packages"
        self.packages_dir = Path(packages_dir)
        self.packages_dir.mkdir(parents=True, exist_ok=True)
    
    def create_package(
        self,
        name: str,
        owner: str = "system",
        created_from_trace: Optional[str] = None,
        tests: List[str] = None,
        status: str = "experimental",
        contract_path: str = "",
        implementation_path: str = "",
        description: str = "",
        version: str = "1.0.0",
        dependencies: List[str] = None
    ) -> ToolPackage:
        """Create a new tool package."""
        package = ToolPackage(
            name=name,
            owner=owner,
            created_from_trace=created_from_trace,
            tests=tests or [],
            status=status,
            contract_path=contract_path,
            implementation_path=implementation_path,
            description=description,
            version=version,
            dependencies=dependencies or []
        )
        
        # Save metadata
        metadata_path = self.packages_dir / f"{name}.json"
        package.save(metadata_path)
        
        logger.info(f"Created package {name} with status {status}")
        return package
    
    def get_package(self, name: str) -> Optional[ToolPackage]:
        """Get package metadata by name."""
        metadata_path = self.packages_dir / f"{name}.json"
        return ToolPackage.load(metadata_path)
    
    def list_packages(self, status: Optional[str] = None) -> List[ToolPackage]:
        """List all packages, optionally filtered by status."""
        packages = []
        for metadata_path in self.packages_dir.glob("*.json"):
            package = ToolPackage.load(metadata_path)
            if package:
                if status is None or package.status == status:
                    packages.append(package)
        return sorted(packages, key=lambda p: p.created_at, reverse=True)
    
    def update_package_status(self, name: str, status: str) -> bool:
        """Update package status.
        
        Args:
            name: Package name
            status: New status (experimental, stable, deprecated)
        
        Returns:
            True if updated, False if package not found
        """
        package = self.get_package(name)
        if not package:
            return False
        
        if status not in ("experimental", "stable", "deprecated"):
            raise ValueError(f"Invalid status: {status}. Must be experimental, stable, or deprecated")
        
        package.status = status
        metadata_path = self.packages_dir / f"{name}.json"
        package.save(metadata_path)
        logger.info(f"Updated package {name} status to {status}")
        return True
    
    def promote_to_stable(self, name: str) -> bool:
        """Promote a package from experimental to stable."""
        return self.update_package_status(name, "stable")
    
    def deprecate(self, name: str) -> bool:
        """Deprecate a package."""
        return self.update_package_status(name, "deprecated")
    
    def delete_package(self, name: str) -> bool:
        """Delete package metadata (does not delete tool files)."""
        metadata_path = self.packages_dir / f"{name}.json"
        if metadata_path.exists():
            metadata_path.unlink()
            logger.info(f"Deleted package metadata for {name}")
            return True
        return False
