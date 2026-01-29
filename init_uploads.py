# init_uploads.py - Run this to initialize uploads directory
import os
from pathlib import Path

def init_uploads_directory():
    """Initialize the uploads directory structure"""
    current_dir = Path(__file__).parent
    uploads_dir = current_dir / "uploads"
    
    # Create main directories
    directories = [
        uploads_dir,
        uploads_dir / "temp",
        uploads_dir / "trash",
        uploads_dir / "system",
    ]
    
    for directory in directories:
        directory.mkdir(exist_ok=True)
        print(f"✓ Created: {directory.relative_to(current_dir)}")
        
        # Add .gitkeep file
        gitkeep = directory / ".gitkeep"
        gitkeep.touch(exist_ok=True)
    
    # Create README
    readme_content = """# Uploads Directory

This directory contains user-uploaded documents for AgroScheme AI.

## Structure
- `uploads/farmer_<farmer_id>/` - Individual farmer folders (created automatically)
- `uploads/user_<user_id>/` - Fallback user folders
- `uploads/temp/` - Temporary uploads
- `uploads/trash/` - Soft-deleted files
- `uploads/system/` - System files

## Security Notes
1. User folders are created automatically when users upload documents
2. Never commit actual user files to git repository
3. .gitkeep files maintain directory structure in git
4. Files are served via /uploads/ URL path

## File Naming
- Files are stored with UUID names for security
- Original filenames are stored in database
- Folder names use farmer_id when available
"""
    
    readme = uploads_dir / "README.md"
    readme.write_text(readme_content)
    
    # Create .gitignore for uploads
    gitignore_content = """# Ignore all user uploads
/*
!.gitkeep
!README.md

# Except system directories
!/temp/
!/trash/
!/system/
"""
    
    gitignore = uploads_dir / ".gitignore"
    gitignore.write_text(gitignore_content)
    
    print("\n✅ Uploads directory initialized successfully!")
    print(f"   Path: {uploads_dir.absolute()}")
    print(f"   Total size: {sum(f.stat().st_size for f in uploads_dir.rglob('*') if f.is_file())} bytes")

if __name__ == "__main__":
    init_uploads_directory()
