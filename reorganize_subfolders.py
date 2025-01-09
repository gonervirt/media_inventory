import os
import argparse
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import shutil
from collections import defaultdict

def setup_parser():
    """Configure command line arguments."""
    parser = argparse.ArgumentParser(description='Reorganize media files in subfolders')
    parser.add_argument('--source', type=str, required=True,
                       help='Source directory containing media files')
    parser.add_argument('--prod', action='store_true',
                       help='Execute the actual file moves and directory deletions. Without this, only shows planned moves')
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
    preferred_locations = ["Royan", "Niort", "Le Mont-Saint-Michel", "Tinténiac", "Saint-Malo", "Brest", "Barbatre", "Champagnole", "Geneve", "Jullouville", "Betton"]
    moves = []
    empty_dirs = set()  # Use a set to ensure uniqueness
    for date, folders in subfolders.items():
        if len(folders) > 1:
            # Select the target folder with a preferred location in order
            target_folder = None
            for loc in preferred_locations:
                target_folder = next((folder for folder in folders if loc in os.path.basename(folder)), None)
                if target_folder:
                    break
            if not target_folder:
                # If no preferred location, select any folder with a location
                target_folder = next((folder for folder in folders if '_' in os.path.basename(folder)), folders[0])
            for folder in folders:
                if folder != target_folder:
                    for root, _, files in os.walk(folder):
                        for file in files:
                            source_path = os.path.join(root, file)
                            target_path = os.path.join(target_folder, file)
                            moves.append((source_path, target_path, target_folder))
                            print(f"Planned move: {source_path} -> {target_path}")  # Debugging information
                    empty_dirs.add(folder)
        else:
            print(f"Skipping date {date} with only one folder")  # Debugging information
    return moves, empty_dirs

def reorganize_by_location(moves, empty_dirs):
    """Reorganize directories by merging those with the same location."""
    location_groups = defaultdict(list)
    for _, target_path, _ in moves:
        target_dir = os.path.dirname(target_path)
        date, location = parse_directory_name(os.path.basename(target_dir))
        if location:
            location_groups[location].append((date, target_dir))
    
    additional_moves = []
    for location, dirs in location_groups.items():
        # Sort directories by date
        dirs.sort()
        target_folder = dirs[0][1]
        for i in range(1, len(dirs)):
            current_date, current_folder = dirs[i]
            previous_date, previous_folder = dirs[i - 1]
            if (current_date - previous_date).days <= 14:
                for root, _, files in os.walk(current_folder):
                    for file in files:
                        source_path = os.path.join(root, file)
                        target_path = os.path.join(target_folder, file)
                        if os.path.normpath(source_path) != os.path.normpath(target_path):
                            additional_moves.append((source_path, target_path, target_folder))
                            print(f"Additional planned move: {source_path} -> {target_path}")  # Debugging information
                empty_dirs.add(current_folder)
            else:
                target_folder = current_folder
    return additional_moves

def execute_moves(moves, prod=False):
    """Execute or simulate file moves."""
    total_moves = len(moves)
    for idx, (source, target, target_folder) in enumerate(moves, 1):
        if not prod:
            print(f"Would move: {source} -> {target}")
        else:
            if os.path.exists(source):
                os.makedirs(target_folder, exist_ok=True)
                shutil.move(source, target)
                print(f"Moved: {source} -> {target}")
            else:
                print(f"Error: Source file not found: {source}")
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
    print(f"Dry run mode: {'disabled' if args.prod else 'enabled'}")
    
    subfolders = find_subfolders_to_merge(source_dir)
    #print(f"Subfolders found: {subfolders}")  # Debugging information
    moves, empty_dirs = plan_moves(subfolders)
    
    if not moves:
        print("\nNo moves planned.")
        return
    
    # Execute initial moves
    execute_moves(moves, prod=args.prod)
    
    # Plan additional moves based on location
    additional_moves = reorganize_by_location(moves, empty_dirs)
    if additional_moves:
        execute_moves(additional_moves, prod=args.prod)
        moves.extend(additional_moves)
    
    save_moves_to_excel(moves, args.output)
    
    if empty_dirs:
        print("\nDirectories that will be empty and need to be removed:")
        for dir in empty_dirs:
            print(f"- {dir}")
            if args.prod:
                try:
                    shutil.rmtree(dir)
                    print(f"Removed directory: {dir}")
                except OSError as e:
                    print(f"Error removing directory {dir}: {e}")
    
    print("\nReorganization completed!")

if __name__ == "__main__":
    main()
