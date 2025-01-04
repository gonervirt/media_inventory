import os
import argparse
import hashlib
from pathlib import Path
from collections import defaultdict
import random
import configparser
from typing import List

def setup_parser():
    """Configure command line arguments."""
    parser = argparse.ArgumentParser(description='Find and remove duplicate files')
    parser.add_argument('--dirs', nargs='+',
                       help='Directories to scan for duplicates (optional, will use config.ini if not specified)')
    parser.add_argument('--prod', action='store_true',
                       help='Actually remove files. Without this flag, only simulates deletion')
    return parser

def load_config(config_file='config.ini') -> List[str]:
    """Load directories from configuration file."""
    config = configparser.ConfigParser()
    directories = []
    
    try:
        config.read(config_file)
        if 'Directories' in config and 'scan_dirs' in config['Directories']:
            dirs = [d.strip() for d in config['Directories']['scan_dirs'].split('\n') if d.strip()]
            directories.extend(map(os.path.expanduser, dirs))
    except Exception as e:
        print(f"Warning: Error reading config file: {str(e)}")
    
    return directories

def calculate_quick_hash(file_path, chunk_size=4096):
    """Calculate MD5 hash of first and last chunk of file for quick comparison."""
    hash_md5 = hashlib.md5()
    file_size = os.path.getsize(file_path)
    
    with open(file_path, 'rb') as f:
        # Read first chunk
        data = f.read(chunk_size)
        hash_md5.update(data)
        
        # If file is larger than chunk_size * 2, read last chunk
        if file_size > chunk_size * 2:
            f.seek(-chunk_size, 2)  # Seek from end
            data = f.read(chunk_size)
            hash_md5.update(data)
            
    return hash_md5.hexdigest()

def find_duplicates(directories):
    """Find duplicate files based on size and quick hash."""
    # First pass: Group files by size
    size_groups = defaultdict(list)
    total_files = 0
    
    print("\nScanning directories for files...")
    for directory in directories:
        for root, _, files in os.walk(directory):
            for filename in files:
                filepath = os.path.join(root, filename)
                try:
                    file_size = os.path.getsize(filepath)
                    size_groups[file_size].append(filepath)
                    total_files += 1
                except OSError as e:
                    print(f"Error accessing {filepath}: {e}")
    
    print(f"\nFound {total_files} files")
    
    # Second pass: For files with same size, check hash
    duplicates = []
    groups_to_check = {size: paths for size, paths in size_groups.items() if len(paths) > 1}
    print(f"Found {len(groups_to_check)} groups of files with same size")
    
    for size, file_paths in groups_to_check.items():
        hash_groups = defaultdict(list)
        
        # Calculate quick hash for each file
        for file_path in file_paths:
            try:
                file_hash = calculate_quick_hash(file_path)
                hash_groups[file_hash].append(file_path)
            except OSError as e:
                print(f"Error hashing {file_path}: {e}")
        
        # Add groups with same hash to duplicates
        for files in hash_groups.values():
            if len(files) > 1:
                duplicates.append(files)
    
    return duplicates

def choose_file_to_remove(file_group):
    """Choose which file to remove from a group of duplicates."""
    # Find files with underscore in name
    files_with_underscore = [f for f in file_group if '_' in os.path.basename(f)]
    if files_with_underscore:
        # Sort by number of underscores (prefer files with more underscores)
        files_with_underscore.sort(key=lambda x: os.path.basename(x).count('_'), reverse=True)
        return files_with_underscore[0]  # Return file with most underscores
    
    # If no files with underscore, choose randomly but warn
    chosen = random.choice(file_group)
    print(f"Warning: No underscore pattern found in group, randomly selecting: {chosen}")
    return chosen

def main():
    parser = setup_parser()
    args = parser.parse_args()
    
    print("Duplicate File Remover")
    print("=====================")
    
    # Get directories from command line or config file
    if args.dirs:
        directories = args.dirs
        print("Using directories from command line")
    else:
        directories = load_config()
        if not directories:
            print("Error: No directories specified in config.ini and no --dirs argument provided")
            return
        print("Using directories from config.ini")
    
    # Normalize and validate directories
    directories = [os.path.normpath(d) for d in directories]
    invalid_dirs = [d for d in directories if not os.path.exists(d)]
    if invalid_dirs:
        print("Error: Following directories not found:")
        for d in invalid_dirs:
            print(f"- {d}")
        return
    
    print("\nScanning directories:")
    for directory in directories:
        print(f"- {directory}")
    
    # Find duplicates
    duplicate_groups = find_duplicates(directories)
    
    if not duplicate_groups:
        print("\nNo duplicates found!")
        return
    
    print(f"\nFound {len(duplicate_groups)} groups of duplicate files")
    
    # Process duplicates
    total_space = 0
    for group in duplicate_groups:
        file_to_remove = choose_file_to_remove(group)
        file_size = os.path.getsize(file_to_remove)
        total_space += file_size
        
        print(f"\nDuplicate group (size: {file_size:,} bytes):")
        for f in group:
            status = " [TO REMOVE]" if f == file_to_remove else ""
            print(f"  - {f}{status}")
        
        if args.prod:
            try:
                os.remove(file_to_remove)
                print(f"Removed: {file_to_remove}")
            except OSError as e:
                print(f"Error removing {file_to_remove}: {e}")
    
    print(f"\nSummary:")
    print(f"Total duplicate groups: {len(duplicate_groups)}")
    print(f"Total space that {'was' if args.prod else 'can be'} freed: {total_space:,} bytes "
          f"({total_space / (1024*1024*1024):.2f} GB)")
    if not args.prod:
        print("\nThis was a dry run. Use --prod to actually remove files.")

if __name__ == "__main__":
    main()
