# Media File Inventory Script

This script scans specified directories for photos and videos, collecting information about each media file and exporting it to an Excel spreadsheet.

## Setup and Installation

1. Make sure you have Python 3.x installed on your system.

2. Set up the virtual environment:
   ```bash
   # Create virtual environment
   python -m venv venv

   # Activate virtual environment
   # On Windows:
   venv\Scripts\activate
   # On Unix or MacOS:
   source venv/bin/activate
   ```

3. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. Edit the `media_inventory.py` script to specify the directories you want to scan:
   ```python
   directories_to_scan = [
       "C:/Path/To/Your/Photos",
       "D:/Another/Path/To/Media",
       # Add more directories as needed
   ]
   ```

2. Run the script:
   ```bash
   python media_inventory.py
   ```

3. The script will create an Excel file named `media_inventory.xlsx` containing:
   - File Name
   - Directory where found
   - Type of media (Photo or Video)
   - Size in MB
   - Size in bytes

## Supported File Types

### Photos
- .jpg, .jpeg
- .png
- .gif
- .bmp
- .tiff
- .webp

### Videos
- .mp4
- .avi
- .mov
- .wmv
- .flv
- .mkv
- .webm

"C:/Users/sebas/OneDrive/Documents/dev/python/photo inventory 2/media_inventory/.venv/Scripts/python.exe" "c:/Users/sebas/OneDrive/Documents/dev/python/photo inventory 2/media_inventory/reorganize_media.py" --inventory media_inventory.xlsx --root C:/photo/dest --prod
