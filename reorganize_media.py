import pandas as pd
import os
from pathlib import Path
import argparse
import shutil
from datetime import datetime

def setup_parser():
    """Configure command line arguments."""
    parser = argparse.ArgumentParser(description='Reorganize media files based on inventory')
    parser.add_argument('--prod', action='store_true', 
                       help='Execute the actual file moves. Without this, only shows planned moves')
    parser.add_argument('--root', type=str, default='organized_media',
                       help='Root directory for organized files (default: organized_media)')
    parser.add_argument('--inventory', type=str, default='media_inventory.xlsx',
                       help='Path to the media inventory Excel file (default: media_inventory.xlsx)')
    return parser

def load_inventory(file_path):
    """Load and validate the media inventory Excel file."""
    try:
        df = pd.read_excel(file_path)
        required_columns = ['File Path', 'Photo Date', 'Duplicate Status']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            raise ValueError(f"Missing required columns: {', '.join(missing_columns)}")
        
        # Ensure Country and City columns exist, if not, add them with NaN values
        for col in ['Country', 'City']:
            if col not in df.columns:
                df[col] = pd.NA
        
        return df
    except Exception as e:
        print(f"Error loading inventory file: {e}")
        return None

def plan_file_moves(df, root_dir):
    """Plan file moves based on dates, location, and duplicate status."""
    moves = []
    errors = []
    status_counts = {'ok': 0, 'duplicate': 0, 'error': 0}
    
    for _, row in df.iterrows():
        try:
            source_path = row['File Path']
            duplicate_status = row['Duplicate Status'].lower()
            status_counts[duplicate_status] = status_counts.get(duplicate_status, 0) + 1
            
            # Skip files marked as duplicates
            if duplicate_status == 'duplicate':
                continue
                
            if not os.path.exists(source_path):
                errors.append(f"Source file not found: {source_path}")
                continue
            
            # Convert date to required format
            photo_date = pd.to_datetime(row['Photo Date']).date()
            year = str(photo_date.year)
            date_str = photo_date.strftime('%Y-%m-%d')
            
            # Add location information to date directory if available
            if pd.notna(row['City']):
                if pd.notna(row['Country']) and row['Country'].strip().lower() != 'france':
                    date_str = f"{date_str}_{row['Country'].strip()}_{row['City'].strip()}"
                else:
                    date_str = f"{date_str}_{row['City'].strip()}"
            
            # Create target path (only 2 levels: year/date_location)
            target_dir = os.path.join(root_dir, year, date_str)
            filename = os.path.basename(source_path)
            
            # For files marked as 'error', add '_dup' suffix before extension
            if duplicate_status == 'error':
                base_name, ext = os.path.splitext(filename)
                filename = f"{base_name}_dup{ext}"
            
            target_path = os.path.join(target_dir, filename)
            
            # Handle filename collisions
            counter = 1
            base_name, ext = os.path.splitext(filename)
            while os.path.exists(target_path):
                new_filename = f"{base_name}_{counter}{ext}"
                target_path = os.path.join(target_dir, new_filename)
                counter += 1
            
            moves.append((source_path, target_path, duplicate_status))
            
        except Exception as e:
            errors.append(f"Error processing {row['File Path']}: {str(e)}")
    
    return moves, errors, status_counts

def execute_moves(moves, dry_run=True):
    """Execute or simulate file moves."""
    results = {
        'successful': 0,
        'failed': 0,
        'errors': [],
        'moves_df': pd.DataFrame([(s, d, st) for s, d, st in moves], 
                               columns=['Source', 'Destination', 'Status'])
    }
    
    for source, target, status in moves:
        try:
            target_dir = os.path.dirname(target)
            
            if dry_run:
                print(f"Would move ({status}):\n  From: {source}\n  To: {target}")
            else:
                os.makedirs(target_dir, exist_ok=True)
                print(f"Moving ({status}):\n  From: {source}\n  To: {target}")
                shutil.move(source, target)
                results['successful'] += 1
                
        except Exception as e:
            error_msg = f"Error moving {source}: {str(e)}"
            results['errors'].append(error_msg)
            results['failed'] += 1
            print(error_msg)
    
    return results

def save_moves_to_excel(moves_df, output_path="planned_moves.xlsx"):
    """Save the planned moves to an Excel file."""
    try:
        moves_df.to_excel(output_path, index=False)
        print(f"\nPlanned moves saved to: {output_path}")
    except Exception as e:
        print(f"Error saving moves to Excel: {e}")

def main():
    parser = setup_parser()
    args = parser.parse_args()
    
    print("Media File Reorganizer")
    print("=====================")
    
    # Load inventory
    print(f"\nLoading inventory from {args.inventory}...")
    df = load_inventory(args.inventory)
    if df is None:
        return
    
    # Plan moves
    print("\nPlanning file organization...")
    moves, errors, status_counts = plan_file_moves(df, args.root)
    
    if errors:
        print("\nErrors during planning:")
        for error in errors:
            print(f"  - {error}")
    
    # Execute or simulate moves
    print(f"\n{'Executing' if args.prod else 'Simulating'} file moves...")
    results = execute_moves(moves, dry_run=not args.prod)
    
    # Save dry run results to Excel
    if not args.prod:
        save_moves_to_excel(results['moves_df'])
    
    # Print summary
    print("\nSummary:")
    print(f"  Total files in inventory: {len(df)}")
    print(f"  Files marked as OK: {status_counts.get('ok', 0)}")
    print(f"  Files marked as duplicate (skipped): {status_counts.get('duplicate', 0)}")
    print(f"  Files marked for rename: {status_counts.get('error', 0)}")
    print(f"  Total files to process: {len(moves)}")
    if args.prod:
        print(f"  Successfully moved: {results['successful']}")
        print(f"  Failed moves: {results['failed']}")
    else:
        print("  Dry run completed - no files were actually moved")
    
    if results['errors']:
        print("\nErrors during execution:")
        for error in results['errors']:
            print(f"  - {error}")

if __name__ == "__main__":
    main()
