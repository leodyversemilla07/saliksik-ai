#!/usr/bin/env python
"""
Setup script for Saliksik AI development environment.
Run this script after installing requirements to set up additional dependencies.
"""

import subprocess
import sys
import os


def run_command(command, description):
    """Run a command and handle errors."""
    print(f"\n🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed")
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        return False


def main():
    print("🚀 Setting up Saliksik AI development environment...")
    
    # Check if we're in a virtual environment
    if not (hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)):
        print("⚠️  Warning: You don't appear to be in a virtual environment.")
        print("   It's recommended to create and activate a virtual environment first:")
        print("   python -m venv venv")
        print("   venv\\Scripts\\activate  # On Windows")
        print("   source venv/bin/activate  # On macOS/Linux")
        response = input("\nContinue anyway? (y/N): ")
        if response.lower() != 'y':
            return
    
    success_count = 0
    total_tasks = 4
    
    # 1. Download spaCy language model
    if run_command("python -m spacy download en_core_web_sm", "Downloading spaCy English model"):
        success_count += 1
    
    # 2. Download NLTK data
    if run_command('python -c "import nltk; nltk.download(\'punkt\')"', "Downloading NLTK punkt tokenizer"):
        success_count += 1
    
    # 3. Run Django migrations
    if run_command("python manage.py migrate", "Running Django migrations"):
        success_count += 1
    
    # 4. Run basic tests
    if run_command("python manage.py test pre_review.tests.ModelTests", "Running basic tests"):
        success_count += 1
    
    print(f"\n📊 Setup completed: {success_count}/{total_tasks} tasks successful")
    
    if success_count == total_tasks:
        print("\n🎉 Setup completed successfully!")
        print("\n📋 Next steps:")
        print("1. Create a superuser: python manage.py createsuperuser")
        print("2. Start the development server: python manage.py runserver")
        print("3. Visit http://127.0.0.1:8000/admin/ to access the admin interface")
        print("4. Test the API at http://127.0.0.1:8000/pre_review/")
    else:
        print("\n⚠️  Some setup tasks failed. Please check the errors above.")
        print("   You may need to install additional dependencies manually.")
    
    # Java installation check
    try:
        subprocess.run("java -version", shell=True, check=True, capture_output=True)
        print("\n✅ Java is installed - LanguageTool grammar checking will be available")
    except subprocess.CalledProcessError:
        print("\n⚠️  Java is not installed - grammar checking will be disabled")
        print("   To enable grammar checking, install Java:")
        print("   - Windows: Download from https://www.oracle.com/java/technologies/downloads/")
        print("   - macOS: brew install openjdk")
        print("   - Ubuntu: sudo apt install default-jdk")


if __name__ == "__main__":
    main()
