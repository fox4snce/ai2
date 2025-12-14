#!/usr/bin/env python3
"""
Setup script for the MVP system.

This script sets up the environment and runs initial tests.
"""

import os
import sys
import subprocess
import sqlite3
from pathlib import Path


def check_python_version():
    """Check Python version."""
    if sys.version_info < (3, 8):
        print("Error: Python 3.8 or higher is required")
        return False
    print(f"OK: Python {sys.version_info.major}.{sys.version_info.minor} detected")
    return True


def install_requirements():
    """Install required packages."""
    print("Installing requirements...")
    try:
        # requirements.txt lives at the repo root; this script is typically run from `mvp/`
        requirements_path = Path(__file__).resolve().parents[1] / "requirements.txt"
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(requirements_path)])
        print("OK: Requirements installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"FAIL: Failed to install requirements: {e}")
        return False


def setup_database():
    """Set up the database."""
    print("Setting up database...")
    try:
        # Create database and run schema
        db_path = "mvp.db"
        conn = sqlite3.connect(db_path)
        
        # Read and execute schema
        with open("db/schema.sql", "r") as f:
            schema_sql = f.read()
        
        # Convert PostgreSQL to SQLite
        schema_sql = schema_sql.replace("VARCHAR(50)", "TEXT")
        schema_sql = schema_sql.replace("VARCHAR(100)", "TEXT")
        schema_sql = schema_sql.replace("VARCHAR(20)", "TEXT")
        schema_sql = schema_sql.replace("JSONB", "TEXT")
        schema_sql = schema_sql.replace("DECIMAL(3,2)", "REAL")
        schema_sql = schema_sql.replace("TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "TEXT DEFAULT CURRENT_TIMESTAMP")
        schema_sql = schema_sql.replace("CHECK (confidence >= 0 AND confidence <= 1)", "")
        schema_sql = schema_sql.replace("CHECK (status IN ('active', 'resolved', 'failed', 'escalated'))", "")
        schema_sql = schema_sql.replace("CHECK (status IN ('running', 'completed', 'failed'))", "")
        schema_sql = schema_sql.replace("CHECK (target_kind IN ('entity', 'relation'))", "")
        
        conn.executescript(schema_sql)
        
        # Load sample data
        with open("db/examples.sql", "r") as f:
            examples_sql = f.read()
        
        # Convert PostgreSQL to SQLite
        examples_sql = examples_sql.replace("CURRENT_TIMESTAMP", "'2024-01-20T15:30:00Z'")
        
        conn.executescript(examples_sql)
        conn.close()
        
        print(f"OK: Database created: {db_path}")
        return True
    except Exception as e:
        print(f"FAIL: Failed to setup database: {e}")
        return False


def run_tests():
    """Run the test suite."""
    print("Running tests...")
    try:
        # Add src to path for tests
        sys.path.insert(0, 'src')
        
        # Run tests
        result = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v"], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("OK: All tests passed")
            return True
        else:
            print("FAIL: Tests failed:")
            print(result.stdout)
            print(result.stderr)
            return False
    except Exception as e:
        print(f"FAIL: Failed to run tests: {e}")
        return False


def run_demo():
    """Run the demo script."""
    print("Running demo...")
    try:
        result = subprocess.run([sys.executable, "demo.py"], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            print("OK: Demo completed successfully")
            print("Demo output:")
            print(result.stdout)
            return True
        else:
            print("FAIL: Demo failed:")
            print(result.stdout)
            print(result.stderr)
            return False
    except Exception as e:
        print(f"FAIL: Failed to run demo: {e}")
        return False


def main():
    """Main setup function."""
    print("=" * 60)
    print(" MVP OBLIGATIONS -> OPERATIONS SETUP")
    print("=" * 60)
    
    success = True
    
    # Check Python version
    if not check_python_version():
        success = False
    
    # Install requirements
    if success and not install_requirements():
        success = False
    
    # Setup database
    if success and not setup_database():
        success = False
    
    # Run tests
    if success and not run_tests():
        success = False
    
    # Run demo
    if success and not run_demo():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("OK: SETUP COMPLETED SUCCESSFULLY!")
        print("\nYou can now:")
        print("  - Run 'python demo.py' to see the system in action")
        print("  - Run 'python -m pytest tests/' to run tests")
        print("  - Import and use the MVPAPI in your own code")
    else:
        print("FAIL: SETUP FAILED!")
        print("Please check the errors above and try again.")
    print("=" * 60)
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
