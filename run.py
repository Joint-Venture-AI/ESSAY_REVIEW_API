#!/usr/bin/env python3
"""
Essay Analyzer Application Launcher
"""
import os
import sys

def check_requirements():
    """Check if required packages are installed"""
    required_packages = [
        'flask',
        'flask_cors', 
        'google.generativeai',
        'docx',
        'dotenv'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("Missing required packages:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\nPlease install them using:")
        print("pip install -r requirements.txt")
        return False
    
    return True

def check_env_file():
    """Check if .env file exists and has API key"""
    if not os.path.exists('.env'):
        print("Warning: .env file not found!")
        print("Create a .env file with your GEMINI_API_KEY")
        return False
    
    with open('.env', 'r') as f:
        content = f.read()
        if 'GEMINI_API_KEY' not in content or 'your_gemini_api_key_here' in content:
            print("Warning: Please set your GEMINI_API_KEY in the .env file")
            return False
    
    return True

def main():
    """Main launcher function"""
    print("🚀 Starting Essay Analyzer Application...")
    print("=" * 50)
    
    # Check requirements
    if not check_requirements():
        sys.exit(1)
    
    # Check environment
    env_ok = check_env_file()
    if not env_ok:
        print("⚠️  AI features may be limited without proper API key")
    
    # Import and run the app
    try:
        from app import app
        print("✅ All checks passed!")
        print("🌐 Starting server at http://localhost:5000")
        print("📝 Open your browser and navigate to the URL above")
        print("=" * 50)
        app.run(debug=True, host='0.0.0.0', port=5000)
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
