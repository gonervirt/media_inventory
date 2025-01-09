import os
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import shutil

def setup_parser():
    """Configure command line arguments."""
    parser = argparse.ArgumentParser(description='Reorganize media files in subfolders')
    parser.add_argument('--source', type=str, required=True,
                       help='Source directory containing media files')
    parser.add_argument('--dry-run', action='store_true', default=True,
                       help='Perform a dry run without moving files (default: True)')
    parser.add_argument('--output', type=str, default='planned_moves.xlsx',
                       help='Output Excel file for planned moves (default: planned_moves.xlsx)')
    return parser

def parse_directory_name(directory_name):
    """Parse directory name to extract date and location."""
    parts = directory_name.split('_', 1)
    if len(parts) == 2:
        try:
            date = datetime.strptime(parts[0], '%Y-%m-%d')
            location = parts[1]
            return date, location
        except ValueError:
            return None, None
    return None, None

def find_subfolders_to_merge(source_dir):
    """Find subfolders to merge based on date and location."""
    subfolders = {}
    for root, dirs, files in os.walk(source_dir):
        print(f"Processing directory: {root}")  # Debugging information
        for dir_name in dirs:
            date, location = parse_directory_name(dir_name)
            if date and location:
                key = date
                subfolders.setdefault(key, []).append(os.path.join(root, dir_name))
                print(f"Found subfolder: {os.path.join(root, dir_name)} with key: {key}")  # Debugging information
    return subfolders

def plan_moves(subfolders):
    """Plan moves to merge subfolders."""
    moves = []
    for date, folders in subfolders.items():
        if len(folders) > 1:
            # Select the target folder with a location
            target_folder = next((folder for folder in folders if '_' in os.path.basename(folder)), folders[0])
            for folder in folders:
                if folder != target_folder:
                    for root, _, files in os.walk(folder):
                        for file in files:
                            source_path = os.path.join(root, file)
                            target_path = os.path.join(target_folder, file)
                            moves.append((source_path, target_path, target_folder))
                            print(f"Planned move: {source_path} -> {target_path}")  # Debugging information
        else:
            print(f"Skipping date {date} with only one folder")  # Debugging information
    return moves

def execute_moves(moves, dry_run=True):
    """Execute or simulate file moves."""
    total_moves = len(moves)
    for idx, (source, target, target_folder) in enumerate(moves, 1):
        if dry_run:
            print(f"Would move: {source} -> {target}")
        else:
            os.makedirs(target_folder, exist_ok=True)
            shutil.move(source, target)
            print(f"Moved: {source} -> {target}")
        print(f"Progress: {idx}/{total_moves} ({(idx / total_moves) * 100:.2f}%)")

def save_moves_to_excel(moves, output_path):
    """Save the planned moves to an Excel file."""
    df = pd.DataFrame(moves, columns=['Source', 'Destination', 'Target Folder'])
    df.to_excel(output_path, index=False)
    print(f"\nPlanned moves saved to: {output_path}")

def main():
    parser = setup_parser()
    args = parser.parse_args()
    
    source_dir = os.path.normpath(args.source)
    if not os.path.exists(source_dir):
        print(f"Error: Source directory '{source_dir}' does not exist")
        return
    
    print("Reorganizing Media Files")
    print("========================")
    print(f"Source directory: {source_dir}")
    print(f"Dry run mode: {'enabled' if args.dry_run else 'disabled'}")
    
    subfolders = find_subfolders_to_merge(source_dir)
    #print(f"Subfolders found: {subfolders}")  # Debugging information
    moves = plan_moves(subfolders)
    
    if not moves:
        print("\nNo moves planned.")
        return
    
    execute_moves(moves, dry_run=args.dry_run)
    save_moves_to_excel(moves, args.output)
    
    print("\nReorganization completed!")

if __name__ == "__main__":
    main()
