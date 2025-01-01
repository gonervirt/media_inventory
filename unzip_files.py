import os
import zipfile
import argparse
from pathlib import Path
import shutil
import getpass

def setup_parser():
    """Configure command line arguments."""
    parser = argparse.ArgumentParser(description='Unzip files from source directory recursively')
    parser.add_argument('--source', type=str, required=True,
                       help='Source directory containing zip files')
    parser.add_argument('--dest', type=str, required=True,
                       help='Destination directory for unzipped files')
    parser.add_argument('--clean', action='store_true',
                       help='Remove zip files after successful extraction')
    return parser

def unzip_file(zip_path, extract_path, remove_after=False, max_password_attempts=3):
    """Extract a single zip file."""
    try:
        print(f"Extracting: {zip_path}")  # Restore progress display
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Check if any file in the archive is encrypted
            encrypted_files = [f.filename for f in zip_ref.filelist if f.flag_bits & 0x1]
            if encrypted_files:
                print(f"\nPassword protected files found in: {zip_path}")
                print(f"First encrypted file: {encrypted_files[0]}")
                
                for attempt in range(max_password_attempts):
                    try:
                        password = getpass.getpass(f"Enter password (attempt {attempt + 1}/{max_password_attempts}, or Enter to skip): ")
                        if not password:
                            print("Skipping password-protected file")
                            stats['skipped'] += 1
                            return False
                        
                        print(f"Extracting with password...")  # Add extraction status
                        zip_ref.extractall(extract_path, pwd=password.encode())
                        print("Successfully extracted with password")
                        break
                    except RuntimeError as e:
                        if "Bad password" in str(e):
                            print("Incorrect password")
                            if attempt == max_password_attempts - 1:
                                print(f"Maximum attempts ({max_password_attempts}) reached. Skipping file.")
                                stats['skipped'] += 1
                                return False
                        else:
                            print(f"Error: {str(e)}")
                            return False
            else:
                # No encryption, extract normally
                zip_ref.extractall(extract_path)
            
            if remove_after:
                print(f"Removing: {zip_path}")
                os.remove(zip_path)
            return True
            
    except zipfile.BadZipFile:
        print(f"Error: {zip_path} is not a valid zip file")
        return False
    except Exception as e:
        print(f"Error extracting {zip_path}: {str(e)}")
        return False

def process_directory(source_dir, dest_dir, clean=False):
    """Process all zip files in source directory and its subdirectories."""
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir)

    global stats  # Make stats global so unzip_file can update it
    stats = {
        'processed': 0,
        'failed': 0,
        'skipped': 0
    }

    # Walk through directory tree
    for root, _, files in os.walk(source_dir):
        for file in files:
            if file.lower().endswith('.zip'):
                zip_path = os.path.join(root, file)
                
                # Create subdirectory in destination matching source structure
                rel_path = os.path.relpath(root, source_dir)
                extract_path = os.path.join(dest_dir, rel_path)
                
                if not os.path.exists(extract_path):
                    os.makedirs(extract_path)
                
                # Extract the zip file
                if unzip_file(zip_path, extract_path, clean):
                    stats['processed'] += 1
                else:
                    stats['failed'] += 1

    return stats

def main():
    parser = setup_parser()
    args = parser.parse_args()
    
    print("Zip File Extractor")
    print("=================")
    
    # Normalize paths
    source_dir = os.path.normpath(args.source)
    dest_dir = os.path.normpath(args.dest)
    
    if not os.path.exists(source_dir):
        print(f"Error: Source directory '{source_dir}' does not exist")
        return
    
    print(f"Source directory: {source_dir}")
    print(f"Destination directory: {dest_dir}")
    print(f"Clean mode: {'enabled' if args.clean else 'disabled'}")
    print("\nStarting extraction...")
    
    stats = process_directory(source_dir, dest_dir, args.clean)
    
    print("\nExtraction completed!")
    print(f"Files processed successfully: {stats['processed']}")
    print(f"Files failed: {stats['failed']}")
    print(f"Files skipped: {stats['skipped']}")

if __name__ == "__main__":
    main()
