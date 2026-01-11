#!/usr/bin/env python3
"""
CPG RAG Assistant Frontend Runner
Simple script to start the application
"""

import subprocess
import sys
import os
from pathlib import Path

def create_directories():
    """Create necessary directories."""
    Path("templates").mkdir(exist_ok=True)
    Path("static").mkdir(exist_ok=True)
    print("✅ Directories created")

def install_requirements():
    """Install requirements from requirements.txt."""
    print("📦 Installing requirements...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Requirements installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install requirements: {e}")
        print("Trying individual packages...")
        
        packages = ["fastapi==0.104.1", "uvicorn[standard]==0.24.0", "jinja2==3.1.2", "python-multipart==0.0.6"]
        for package in packages:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                print(f"✅ Installed {package}")
            except subprocess.CalledProcessError:
                print(f"❌ Failed to install {package}")

def main():
    """Main runner function."""
    print("🏥 CPG RAG Assistant Frontend")
    print("=" * 40)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Setup
    create_directories()
    install_requirements()
    
    print("\n" + "=" * 40)
    print("🚀 Starting CPG RAG Assistant...")
    print("📍 Server will be available at: http://localhost:8000")
    print("🔄 Press Ctrl+C to stop the server")
    print("=" * 40)
    
    # Start server
    try:
        import uvicorn
        uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    except ImportError:
        print("❌ Failed to import uvicorn. Please check installation.")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()