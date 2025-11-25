import os
import shutil
import pandas as pd
import argparse

def setup_parser():
    """Set up command-line arguments."""
    parser = argparse.ArgumentParser(description="Copy files based on an Excel file with source and destination columns.")
    parser.add_argument('--excel', type=str, required=True, help="Path to the Excel file (e.g., planned_moves.xlsx).")
    parser.add_argument('--prod', action='store_true', help="Execute the actual file copy. Without this, only simulates the process.")
    return parser

def copy_files_from_excel(excel_path, prod=False):
    """Copy files based on the Excel file."""
    try:
        # Load the Excel file
        df = pd.read_excel(excel_path)
        
        # Ensure required columns exist
        if 'Source' not in df.columns or 'Destination' not in df.columns:
            print("Error: The Excel file must contain 'Source' and 'Destination' columns.")
            return
        
        total_files = len(df)
        print(f"Found {total_files} file(s) to process.")
        
        for idx, row in df.iterrows():
            source = row['Source']
            destination = row['Destination']
            
            if not os.path.exists(source):
                print(f"Warning: Source file does not exist: {source}")
                continue
            
            destination_dir = os.path.dirname(destination)
            
            if not prod:
                print(f"Would copy: {source} -> {destination}")
            else:
                try:
                    os.makedirs(destination_dir, exist_ok=True)
                    shutil.copy2(source, destination)
                    print(f"Copied: {source} -> {destination}")
                except Exception as e:
                    print(f"Error copying {source} to {destination}: {e}")
        
        print("\nProcess completed.")
        if not prod:
            print("Dry run mode: No files were actually copied. Use --prod to execute the copy.")
    
    except Exception as e:
        print(f"Error processing the Excel file: {e}")

def main():
    parser = setup_parser()
    args = parser.parse_args()
    
    excel_path = os.path.normpath(args.excel)
    if not os.path.exists(excel_path):
        print(f"Error: Excel file '{excel_path}' does not exist.")
        return
    
    print(f"Processing Excel file: {excel_path}")
    copy_files_from_excel(excel_path, prod=args.prod)

if __name__ == "__main__":
    main()
