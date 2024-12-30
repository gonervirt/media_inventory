import os
import pandas as pd
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import magic
import time
import argparse
import re
from datetime import datetime
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from functools import lru_cache
import math
from time import sleep

try:
    from moviepy.editor import VideoFileClip
    MOVIEPY_AVAILABLE = True
except ImportError:
    MOVIEPY_AVAILABLE = False
    print("Warning: moviepy not available. Video resolution information will be limited.")

def convert_to_degrees(value):
    """Helper function to convert GPS coordinates to degrees."""
    try:
        if isinstance(value, tuple):
            # If it's already a tuple of rationals
            d = float(value[0].numerator) / float(value[0].denominator) if value[0].denominator != 0 else 0
            m = float(value[1].numerator) / float(value[1].denominator) if value[1].denominator != 0 else 0
            s = float(value[2].numerator) / float(value[2].denominator) if value[2].denominator != 0 else 0
            return d + (m / 60.0) + (s / 3600.0)
        elif hasattr(value, 'numerator') and hasattr(value, 'denominator'):
            # If it's a single rational
            return float(value.numerator) / float(value.denominator) if value.denominator != 0 else 0
        else:
            return float(value)
    except (ZeroDivisionError, TypeError, ValueError) as e:
        print(f"Warning: Error converting GPS value {value}: {str(e)}")
        return 0

def get_image_metadata(file_path):
    """Extract resolution, GPS coordinates, and date from image file."""
    try:
        with Image.open(file_path) as img:
            # Get resolution
            width, height = img.size
            resolution = f"{width}x{height}"
            
            # Initialize metadata variables
            gps_coords = None
            date_taken = None
            
            if hasattr(img, '_getexif') and img._getexif() is not None:
                exif = {TAGS.get(key, key): value for key, value in img._getexif().items()}
                
                # Get GPS coordinates
                if 'GPSInfo' in exif:
                    try:
                        gps_info = {GPSTAGS.get(key, key): value for key, value in exif['GPSInfo'].items()}
                        
                        if all(k in gps_info for k in ['GPSLatitude', 'GPSLongitude', 'GPSLatitudeRef', 'GPSLongitudeRef']):
                            lat = convert_to_degrees(gps_info['GPSLatitude'])
                            lon = convert_to_degrees(gps_info['GPSLongitude'])
                            lat_ref = gps_info['GPSLatitudeRef']
                            lon_ref = gps_info['GPSLongitudeRef']
                            
                            if lat_ref == 'S': lat = -lat
                            if lon_ref == 'W': lon = -lon
                            
                            gps_coords = f"{lat:.6f}, {lon:.6f}"
                    except Exception as e:
                        print(f"GPS extraction error for {file_path}: {str(e)}")
                
                # Try to get date from EXIF
                for date_field in ['DateTimeOriginal', 'CreateDate', 'DateTimeDigitized', 'DateTime']:
                    if date_field in exif and exif[date_field]:
                        try:
                            date_str = str(exif[date_field])
                            date_taken = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S').date()
                            break
                        except (ValueError, TypeError):
                            continue
            
            return resolution, gps_coords, date_taken
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")
        pass
    return None, None, None

def extract_date_from_filename(filename):
    """Try to extract date from filename using common patterns."""
    # Common date patterns in filenames (add more patterns as needed)
    patterns = [
        r'(\d{4}[-_]?\d{2}[-_]?\d{2})',  # YYYY-MM-DD or YYYYMMDD
        r'(\d{2}[-_]?\d{2}[-_]?\d{4})',  # DD-MM-YYYY or DDMMYYYY
        r'IMG[-_]?(\d{8})',  # IMG_YYYYMMDD
        r'(\d{8})[-_]\d+',   # YYYYMMDD_sequence
        r'VID[-_]?(\d{8})',  # VID_YYYYMMDD
        r'VIDEO[-_]?(\d{8})' # VIDEO_YYYYMMDD
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename)
        if match:
            date_str = match.group(1).replace('_', '').replace('-', '')
            try:
                # Try different date formats
                for fmt in ('%Y%m%d', '%d%m%Y'):
                    try:
                        return datetime.strptime(date_str, fmt).date()
                    except ValueError:
                        continue
            except ValueError:
                continue
    return None

def get_video_metadata(file_path):
    """Extract resolution from video file."""
    try:
        if MOVIEPY_AVAILABLE:
            with VideoFileClip(file_path) as clip:
                width, height = clip.size
                resolution = f"{width}x{height}"
                return resolution
        else:
            return "Resolution unavailable (moviepy not installed)"
    except:
        pass
    return None

def get_file_type(file_path):
    """Determine if the file is a photo or video based on extension and content."""
    # Files to ignore
    system_files = {'desktop.ini', 'thumbs.db', '.ds_store'}
    if os.path.basename(file_path).lower() in system_files:
        return None
        
    photo_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp'}
    video_extensions = {'.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm'}
    
    ext = Path(file_path).suffix.lower()
    
    # First check extension
    if ext not in photo_extensions and ext not in video_extensions:
        return None
    
    try:
        # Then check mime type
        mime = magic.from_file(file_path, mime=True)
        if mime.startswith('image/') and ext in photo_extensions:
            return 'Photo'
        elif mime.startswith('video/') and ext in video_extensions:
            return 'Video'
        # If mime type check fails, fall back to extension only
        if ext in photo_extensions:
            return 'Photo'
        elif ext in video_extensions:
            return 'Video'
    except:
        return None
    return None

def save_checkpoint(media_files, processed_files, checkpoint_file, count):
    """Save current progress to files."""
    try:
        # Create a backup of the previous checkpoint file if it exists
        if os.path.exists(checkpoint_file):
            backup_file = f"{checkpoint_file}.bak"
            os.replace(checkpoint_file, backup_file)

        # Save processed files list first
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            for processed_file in processed_files:
                f.write(f"{processed_file}\n")

        # Save partial results to Excel with timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        excel_file = f'media_inventory_checkpoint_{count}_{timestamp}.xlsx'
        export_to_excel(media_files, excel_file)
        
        # Create a status file to track the latest checkpoint
        status_file = 'inventory_status.txt'
        with open(status_file, 'w', encoding='utf-8') as f:
            f.write(f"Last checkpoint: {count}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"Excel file: {excel_file}\n")
            f.write(f"Total files processed: {len(processed_files)}\n")
            f.write(f"Total media files found: {len(media_files)}\n")

        # Remove old backup file if everything succeeded
        if os.path.exists(f"{checkpoint_file}.bak"):
            os.remove(f"{checkpoint_file}.bak")
        
    except Exception as e:
        print(f"Error during checkpoint save: {str(e)}")
        # Restore backup if something went wrong
        if os.path.exists(f"{checkpoint_file}.bak"):
            os.replace(f"{checkpoint_file}.bak", checkpoint_file)
        raise

def export_to_excel(media_files, output_file='media_inventory.xlsx'):
    """Export the media files information to an Excel file."""
    if media_files:
        # Clean the data by removing or replacing problematic characters
        cleaned_media_files = []
        for file_info in media_files:
            cleaned_info = {}
            for key, value in file_info.items():
                if isinstance(value, str):
                    # Replace zero-width space with empty string
                    cleaned_value = value.replace('\u200b', '')
                    # Replace other potentially problematic characters if needed
                    cleaned_info[key] = cleaned_value
                else:
                    cleaned_info[key] = value
            cleaned_media_files.append(cleaned_info)

        df = pd.DataFrame(cleaned_media_files)
        try:
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            print(f"\nResults exported to {output_file}")
        except Exception as e:
            print(f"Error exporting to Excel: {str(e)}")

# Initialize the geocoder
geolocator = Nominatim(user_agent="media_inventory_scanner")

@lru_cache(maxsize=1000)
def get_location_info(lat, lon):
    """Get country and city from coordinates using caching to avoid duplicate requests."""
    try:
        # Round coordinates to 3 decimal places (about 100m accuracy)
        # This helps with caching nearby locations
        lat = round(float(lat), 3)
        lon = round(float(lon), 3)
        
        # Add a small delay to respect rate limits
        sleep(1)
        
        location = geolocator.reverse(f"{lat}, {lon}", language="en")
        if location and location.raw.get('address'):
            address = location.raw['address']
            country = address.get('country', '')
            # Try different fields for city name
            city = (address.get('city') or 
                   address.get('town') or 
                   address.get('village') or 
                   address.get('suburb') or 
                   address.get('municipality') or
                   '')
            return country, city
    except (GeocoderTimedOut, Exception) as e:
        print(f"Geocoding error for coordinates ({lat}, {lon}): {str(e)}")
    return '', ''

def process_gps_batch(media_files, batch_size=50):
    """Process GPS coordinates in batches to update location information."""
    batch = []
    locations_cache = {}
    
    for file_info in media_files:
        if 'GPS Coordinates' in file_info and file_info['GPS Coordinates']:
            try:
                # Parse the GPS string
                lat, lon = map(float, file_info['GPS Coordinates'].split(','))
                batch.append((file_info, lat, lon))
                
                if len(batch) >= batch_size:
                    process_location_batch(batch, locations_cache)
                    batch = []
            except Exception as e:
                print(f"Error parsing GPS coordinates for {file_info['File Name']}: {str(e)}")
    
    # Process remaining items
    if batch:
        process_location_batch(batch, locations_cache)

def process_location_batch(batch, locations_cache):
    """Process a batch of locations and update the media files with country and city."""
    for file_info, lat, lon in batch:
        # Check if we have cached the location
        cache_key = f"{round(lat, 3)},{round(lon, 3)}"
        if cache_key in locations_cache:
            country, city = locations_cache[cache_key]
        else:
            country, city = get_location_info(lat, lon)
            locations_cache[cache_key] = (country, city)
        
        file_info['Country'] = country
        file_info['City'] = city

def scan_directories(root_dirs, max_workers=None, test_limit=None):
    """Scan directories recursively for media files."""
    print("\n=== Photo Inventory Process Started ===")
    print("Initializing...")
    
    if test_limit:
        print(f"Test mode: Will process maximum {test_limit} files")
    
    media_files = []
    processed_files = set()
    checkpoint_file = 'processed_files.txt'
    files_processed = 0
    
    # Load previously processed files
    if os.path.exists(checkpoint_file):
        print("Loading previously processed files...")
        with open(checkpoint_file, 'r', encoding='utf-8') as f:
            processed_files = set(line.strip() for line in f)
        print(f"Found {len(processed_files)} previously processed files")
    
    # Scan for media files
    print("\nScanning directories for files...")
    files_to_process = []
    
    # Files to ignore
    system_files = {'desktop.ini', 'thumbs.db', '.ds_store'}
    valid_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp',
                       '.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm'}
    
    for root_dir in root_dirs:
        if not os.path.exists(root_dir):
            print(f"Warning: Directory not found: {root_dir}")
            continue
            
        print(f"Scanning: {root_dir}")
        for root, _, files in os.walk(root_dir):
            for file in files:
                # Skip system files
                if file.lower() in system_files:
                    continue
                    
                # Check extension
                if not any(file.lower().endswith(ext) for ext in valid_extensions):
                    continue
                    
                file_path = os.path.join(root, file)
                if file_path not in processed_files:
                    files_to_process.append({
                        'file_path': file_path,
                        'file_name': file,
                        'root': root
                    })
    
    total_files = len(files_to_process)
    print(f"\nFound {total_files} new media files to process")
    
    if total_files > 0:
        print("\nProcessing files...")
        
        # Process files one by one
        for idx, file_data in enumerate(files_to_process, 1):
            try:
                # Check if we've hit the test limit
                if test_limit and idx > test_limit:
                    print(f"\nTest limit of {test_limit} files reached. Stopping...")
                    break
                    
                file_path = file_data['file_path']
                file_type = get_file_type(file_path)
                
                if file_type:
                    file_size_bytes = os.path.getsize(file_path)
                    file_stats = os.stat(file_path)
                    
                    # Get file dates
                    creation_date = datetime.fromtimestamp(file_stats.st_ctime).date()
                    modified_date = datetime.fromtimestamp(file_stats.st_mtime).date()
                    
                    file_info = {
                        'File Path': file_path,
                        'File Name': file_data['file_name'],
                        'Directory': file_data['root'],
                        'Type': file_type,
                        'Size (Bytes)': file_size_bytes,
                        'Size (MB)': round(file_size_bytes / (1024 * 1024), 2),
                        'Creation Date': creation_date,
                        'Modified Date': modified_date
                    }
                    
                    if file_type == 'Photo':
                        resolution, gps, photo_date = get_image_metadata(file_path)
                        file_info['Resolution'] = resolution
                        file_info['GPS Coordinates'] = gps
                        
                        # Try to get date in this order: EXIF > filename > file system
                        if photo_date:
                            file_info['Photo Date'] = photo_date
                        else:
                            # Try to extract date from filename
                            filename_date = extract_date_from_filename(file_data['file_name'])
                            if filename_date:
                                file_info['Photo Date'] = filename_date
                            else:
                                # Use the earlier of creation or modified date
                                file_info['Photo Date'] = min(creation_date, modified_date)
                    else:  # Video
                        resolution = get_video_metadata(file_path)
                        file_info['Resolution'] = resolution
                        file_info['GPS Coordinates'] = None
                        file_info['Photo Date'] = extract_date_from_filename(file_data['file_name'])  # Use earliest file system date for videos
                    
                    media_files.append(file_info)
                    processed_files.add(file_path)
                    files_processed += 1
                
                # Update progress
                percentage = (idx / total_files) * 100
                print(f"\rProcessed: {idx}/{total_files} ({percentage:.1f}%) - Current: {file_data['file_name']}", 
                      end="", flush=True)
                
                # Save checkpoint every 1000 files
                if idx % 1000 == 0:
                    print(f"\nSaving checkpoint at {idx} files...")
                    save_checkpoint(media_files, processed_files, checkpoint_file, idx)
                    print("Continuing...")
                
            except Exception as e:
                print(f"\nSkipping {file_data['file_name']}: {str(e)}")
                continue
        
        # Process GPS coordinates in batches
        if media_files:
            print("\nProcessing location information...")
            process_gps_batch(media_files)
            
        # Save final results
        print("\nSaving final results...")
        save_checkpoint(media_files, processed_files, checkpoint_file, files_processed)
        print("\n=== Process Completed Successfully ===")
        print(f"Total files processed: {files_processed}")
        print(f"Media files found: {len(media_files)}")
    else:
        print("\nNo new files to process")
        print("=== Process Completed ===")
    
    return media_files

def main():
    parser = argparse.ArgumentParser(description='Media Inventory Scanner')
    parser.add_argument('--test', type=int, help='Limit processing to specified number of files (for testing)')
    parser.add_argument('--dirs', nargs='+', help='Directories to scan (optional)')
    args = parser.parse_args()
    
    # List of directories to scan
    directories_to_scan = args.dirs if args.dirs else [
        #os.path.expanduser("~/Pictures"),
        #os.path.expanduser("~/Videos"),
        #os.path.expanduser("~/Downloads"),
        #os.path.expanduser("C:/Users/sebas/OneDrive/Images"),  # Often contains media files
        os.path.expanduser("C:/photo/src")
        # Add more directories as needed
    ]
    
    print("Starting media inventory scan...")
    print("Will scan the following directories:")
    for dir in directories_to_scan:
        print(f"- {dir}")
    
    media_files = scan_directories(directories_to_scan, test_limit=args.test)
    
    if media_files:
        export_to_excel(media_files, 'media_inventory.xlsx')
        print(f"\nInventory has been exported to 'media_inventory.xlsx'")
        print("You can find the following information in the Excel file:")
        print("- File names")
        print("- Directory paths")
        print("- Media types (Photo/Video)")
        print("- Resolutions")
        print("- GPS coordinates")
        print("- File sizes (in MB and bytes)")
        print("- Creation and modified dates")
        print("- Photo date (extracted from EXIF, filename, or file system)")
        print("- Country and city (extracted from GPS coordinates)")
    else:
        print("\nNo media files were found in the specified directories.")

if __name__ == "__main__":
    main()