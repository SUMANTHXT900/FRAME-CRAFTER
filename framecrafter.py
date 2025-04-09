import os
import time
import json
import re
import subprocess
import shutil
import sys
import threading
import uuid
from datetime import timedelta
from flask import Flask, render_template, request, jsonify, url_for, send_from_directory
from flask_cors import CORS
import yt_dlp
import cv2
import numpy as np
from fpdf import FPDF

# ------------------------ UTILITY FUNCTIONS AND CLASSES ------------------------

# Utility class for file operations and common functions
class Utils:
    @staticmethod
    def ensure_dir(dir_path):
        """Ensure a directory exists, create if it doesn't"""
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        return dir_path
    
    @staticmethod
    def get_temp_dir():
        """Get the temp directory path"""
        temp_dir = os.path.join(os.getcwd(), "temp_video_downloads")
        Utils.ensure_dir(temp_dir)
        return temp_dir
    
    @staticmethod
    def get_pdf_dir():
        """Get the PDF directory path"""
        pdf_dir = os.path.join(os.getcwd(), "PDF")
        Utils.ensure_dir(pdf_dir)
        return pdf_dir
    
    @staticmethod
    def sanitize_filename(filename):
        """Sanitize a filename to make it safe for all filesystems"""
        # Replace special Unicode characters
        safe_name = "".join(c if ord(c) < 128 and (c.isalnum() or c in " -_.") else "_" for c in filename)
        return safe_name[:50]  # Limit length
    
    @staticmethod
    def find_best_format(formats):
        """Find the best video format from the available formats"""
        # Find the best format that uses H.264 codec and is 1080p or lower
        best_format = None
        for f in formats:
            vcodec = f.get('vcodec', '')
            height = f.get('height', 0)
            if 'avc' in vcodec and f.get('ext') == 'mp4' and height <= 1080:
                if best_format is None or height > best_format.get('height', 0):
                    best_format = f
        
        # Fallback to any best format if H.264 is not available
        if best_format is None:
            best_format = max(
                (f for f in formats if f.get('height', 0) <= 1080),
                key=lambda f: f.get('height', 0),
                default=formats[0]
            )
        
        return best_format
    
    @staticmethod
    def sanitize_title(title):
        """Sanitize a title for use in PDF"""
        sanitized = ""
        for char in title:
            if ord(char) < 128:  # ASCII characters only
                sanitized += char
            else:
                sanitized += "_"
        return sanitized

# ------------------------ VIDEO PROCESSING FUNCTIONS ------------------------

# Function to get the direct video stream URL from YouTube
def get_youtube_stream_url(youtube_link):
    # Create a unique filename for this download
    temp_dir = Utils.get_temp_dir()
    temp_video_path = os.path.join(temp_dir, f"temp_video_{int(time.time())}.mp4")
    
    print("Downloading video to temporary file. This may take a moment...")
    
    ydl_opts = {
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "quiet": False,  # Show download progress
        "no_warnings": True,
        "socket_timeout": 30,
        "outtmpl": temp_video_path,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_link, download=True)
            
            if os.path.exists(temp_video_path) and os.path.getsize(temp_video_path) > 0:
                print(f"Video downloaded successfully to: {temp_video_path}")
                print(f"Selected format - Resolution: {info.get('height', 'unknown')}p, Codec: {info.get('vcodec', 'unknown')}")
                return temp_video_path, info.get("title", "Unknown"), info.get("duration", 0)
            else:
                # Check if yt-dlp used a different filename (sometimes adds extension)
                for filename in os.listdir(temp_dir):
                    if filename.startswith(os.path.basename(temp_video_path.split('.')[0])):
                        full_path = os.path.join(temp_dir, filename)
                        print(f"Video downloaded successfully to: {full_path}")
                        return full_path, info.get("title", "Unknown"), info.get("duration", 0)
                        
                print("Download appears to have failed. No file found.")
                return None, None, None
    except Exception as e:
        print(f"Error: Could not download YouTube video - {str(e)}")
        return None, None, None

# Function to get streaming URL without downloading
def get_streaming_url(youtube_link):
    ydl_opts = {
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_link, download=False)
            formats = info.get('formats', [])
            
            best_format = Utils.find_best_format(formats)
            
            print(f"Selected format - Resolution: {best_format.get('height', 'unknown')}p, Codec: {best_format.get('vcodec', 'unknown')}")
            return best_format['url'], info.get("title", "Unknown"), info.get("duration", 0)
    except Exception as e:
        print(f"Error: Could not process YouTube link - {str(e)}")
        return None, None, None

# Function to parse time format (supports HH:MM:SS, MM:SS, or seconds)
def parse_timestamp(timestamp_str):
    # Handle numeric values directly
    try:
        # First, make sure we're working with a string
        timestamp_str = str(timestamp_str).strip()
        
        # Check if it's just a number (seconds)
        if re.match(r'^\d+(\.\d+)?$', timestamp_str):
            return float(timestamp_str)
        
        # Try to parse as MM:SS or HH:MM:SS
        parts = timestamp_str.split(':')
        if len(parts) == 2:  # MM:SS
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:  # HH:MM:SS
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        else:
            raise ValueError(f"Invalid time format: {timestamp_str}")
    except Exception as e:
        print(f"Error parsing timestamp '{timestamp_str}': {str(e)}")
        # Return 0 as a fallback to avoid breaking the process
        return 0

# Function to generate timestamps at regular intervals
def generate_interval_timestamps(duration, interval):
    return list(range(0, int(duration) + 1, interval))

# Function to capture screenshots at specific timestamps
def capture_screenshots(video_path, timestamps, output_dir="high_res_screenshots", max_retries=3, progress_callback=None):
    # Ensure output_dir is a full path
    if not os.path.isabs(output_dir):
        output_dir = os.path.join(os.getcwd(), output_dir)
    
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    images = []
    total = len(timestamps)
    
    # Check if we're working with a local file
    is_local_file = os.path.exists(video_path) and os.path.isfile(video_path)
    
    # Get video information first to validate timestamps
    print("Checking video duration...")
    try:
        # Use OpenCV for local files or if ffmpeg is not available
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print("Error: Cannot open video file for initial check")
            return []
            
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # For local files, we can rely on frame count * fps
        if is_local_file and fps > 0 and total_frames > 0:
            duration = total_frames / fps
        else:
            # For streams, try to use other methods to get duration
            duration = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if duration <= 0:
                # If we get here, use the duration passed from yt_dlp
                if len(timestamps) > 0 and max(timestamps) > 0:
                    duration = max(timestamps) + 60  # Add a buffer
        
        cap.release()
        
        # Proceed with taking screenshots
        print(f"Starting screenshot capture of {total} timestamps...")
        
        for i, timestamp in enumerate(timestamps):
            # Report progress if callback is provided
            if progress_callback and callable(progress_callback):
                progress_callback(i, total)
                
            # Skip timestamps beyond video duration
            if timestamp > duration:
                print(f"Skipping timestamp {timestamp}s as it exceeds video duration of {duration}s")
                continue
            
            # Output filename will include the timestamp
            output_filename = os.path.join(output_dir, f"screenshot_{i:03d}_{int(timestamp)}s.png")
            
            # Check if we already have this screenshot
            if os.path.exists(output_filename) and os.path.getsize(output_filename) > 0:
                print(f"Screenshot for {timestamp}s already exists, skipping")
                images.append(output_filename)
                continue
            
            print(f"Taking screenshot at {timestamp}s")
            success = False
            retry_count = 0
            
            while not success and retry_count < max_retries:
                try:
                    # Use OpenCV to capture the frame
                    cap = cv2.VideoCapture(video_path)
                    if not cap.isOpened():
                        print("Error: Cannot open video file")
                        break
                        
                    # Convert timestamp to milliseconds for seek
                    cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
                    
                    # Read the frame
                    ret, frame = cap.read()
                    if not ret:
                        print(f"Failed to read frame at {timestamp}s, retry {retry_count + 1}")
                        retry_count += 1
                        cap.release()
                        time.sleep(0.5)  # Short delay before retry
                        continue
                    
                    # Save the frame as an image
                    cv2.imwrite(output_filename, frame)
                    
                    # Check if the image was saved
                    if os.path.exists(output_filename) and os.path.getsize(output_filename) > 0:
                        success = True
                        images.append(output_filename)
                    else:
                        print(f"Failed to save image for {timestamp}s, retry {retry_count + 1}")
                        retry_count += 1
                    
                    cap.release()
                    
                except Exception as e:
                    print(f"Error capturing screenshot at {timestamp}s: {str(e)}")
                    retry_count += 1
            
            if not success:
                print(f"Failed to capture screenshot at {timestamp}s after {max_retries} attempts")
        
        # Report final progress
        if progress_callback and callable(progress_callback):
            progress_callback(total, total)
        
        return images
        
    except Exception as e:
        print(f"Error in capture_screenshots: {str(e)}")
        return []

# Function to create a PDF from the screenshots
def create_pdf(image_paths, video_title="YouTube Video", output_pdf="screenshots.pdf", timestamp_notes=None):
    if not image_paths:
        print("No images to add to PDF")
        return None
        
    # Use original title if possible, but ensure it's sanitized for PDF
    safe_title = Utils.sanitize_title(video_title)
    print(f"Creating PDF with title: {safe_title}")
    
    # If not specified, create a default output filename in PDF directory
    if output_pdf == "screenshots.pdf":
        pdf_dir = Utils.get_pdf_dir()
        output_pdf = os.path.join(pdf_dir, f"{Utils.sanitize_filename(video_title)}.pdf")
    
    try:    
        # Sort the images by timestamp (which is included in the filename)
        image_paths.sort(key=lambda path: int(os.path.basename(path).split('_')[2].split('s')[0]))
        
        # Initialize PDF object
        pdf = FPDF(orientation='P', unit='mm', format='A4')
        # Set minimal margins
        pdf.set_margins(0, 0, 0)
        pdf.set_auto_page_break(False)
        
        # Add metadata
        pdf.set_title(safe_title)
        pdf.set_author("YouTube Screenshot PDF Generator")
        pdf.set_creator("https://github.com/example/youtube-screenshot-pdf")
        
        # Add a cover page with all notes
        pdf.add_page()
        pdf.set_font("Arial", "B", 18)
        pdf.set_text_color(50, 50, 50)
        pdf.set_xy(10, 10)
        pdf.cell(0, 15, "YouTube Video Screenshots", 0, 1, "C")
        
        pdf.set_font("Arial", "", 12)
        pdf.set_text_color(80, 80, 80)
        pdf.set_xy(10, 30)
        pdf.multi_cell(0, 8, f"Title: {safe_title}\nGenerated: {time.strftime('%Y-%m-%d %H:%M:%S')}\nNumber of screenshots: {len(image_paths)}", 0, "L")
        
        # Add notes section if there are any notes
        if timestamp_notes and any(note.strip() for note in timestamp_notes.values()):
            pdf.set_xy(10, 60)
            pdf.set_font("Arial", "B", 14)
            pdf.set_text_color(50, 50, 50)
            pdf.cell(0, 10, "Notes:", 0, 1, "L")
            
            y_position = 75
            for i, img_path in enumerate(image_paths):
                # Extract timestamp from filename
                timestamp_seconds = int(os.path.basename(img_path).split('_')[2].split('s')[0])
                formatted_time = str(timedelta(seconds=timestamp_seconds))
                
                # Check if there's a note for this timestamp
                note = ""
                if timestamp_notes and str(timestamp_seconds) in timestamp_notes:
                    note = timestamp_notes[str(timestamp_seconds)]
                
                if note and note.strip():
                    pdf.set_xy(10, y_position)
                    pdf.set_font("Arial", "B", 11)
                    pdf.set_text_color(80, 80, 80)
                    pdf.cell(0, 6, f"Timestamp {formatted_time}:", 0, 1, "L")
                    
                    pdf.set_xy(20, y_position + 6)
                    pdf.set_font("Arial", "", 10)
                    pdf.set_text_color(100, 100, 100)
                    pdf.multi_cell(170, 6, note.strip(), 0, "L")
                    
                    y_position += 20  # Move down for next note
                    
                    # Add a new page if we're running out of space
                    if y_position > 270:
                        pdf.add_page()
                        y_position = 20
        
        # Add screenshots as full pages
        for i, img_path in enumerate(image_paths):
            # Add a new page for each image
            pdf.add_page()
            
            # Extract timestamp from filename for the small timestamp overlay
            timestamp_seconds = int(os.path.basename(img_path).split('_')[2].split('s')[0])
            formatted_time = str(timedelta(seconds=timestamp_seconds))
            
            # Get image dimensions
            img = cv2.imread(img_path)
            img_h, img_w = img.shape[:2]
            
            # Calculate dimensions to fit the entire page
            page_w = 210  # A4 width in mm
            page_h = 297  # A4 height in mm
            
            # Calculate scaling factor to fit the page while preserving aspect ratio
            scale_w = page_w / img_w
            scale_h = page_h / img_h
            scale = min(scale_w, scale_h)  # Use min to ensure the full image is visible without cropping
            
            new_w = img_w * scale
            new_h = img_h * scale
            
            # Center the image on the page
            x_pos = (page_w - new_w) / 2
            y_pos = (page_h - new_h) / 2
            
            # Fill page with black background (to ensure no white margins around images)
            pdf.set_fill_color(0, 0, 0)
            pdf.rect(0, 0, page_w, page_h, 'F')
            
            # Add image to PDF as full page background
            pdf.image(img_path, x=x_pos, y=y_pos, w=new_w, h=new_h)
            
            # Add a small, dark timestamp overlay
            pdf.set_xy(5, 5)
            pdf.set_font("Arial", "B", 10)
            pdf.set_text_color(255, 255, 255)  # White text
            
            # Draw a small dark background for the timestamp
            pdf.set_fill_color(0, 0, 0)
            pdf.rect(5, 5, 50, 8, style='F')  # 'F' means filled rectangle
            
            # Add the timestamp text
            pdf.set_xy(7, 6)
            pdf.cell(0, 6, f"Time: {formatted_time}", 0, 0, "L")
            
            # Add page number at the bottom
            pdf.set_xy(5, 287)
            pdf.set_font("Arial", "I", 8)
            
            # Draw a small dark background for the page number
            pdf.set_fill_color(0, 0, 0)
            pdf.rect(5, 287, 30, 8, style='F')
            
            # Add the page number
            pdf.set_xy(7, 288)
            pdf.set_text_color(255, 255, 255)  # White text
            pdf.cell(0, 6, f"Page {i+1}/{len(image_paths)}", 0, 0, "L")
            
            print(f"Added image {i+1}/{len(image_paths)} to PDF")
        
        # Save PDF
        pdf.output(output_pdf)
        print(f"PDF created successfully: {output_pdf}")
        return output_pdf
        
    except Exception as e:
        print(f"Error creating PDF: {str(e)}")
        return None

# Function to clean up temporary files
def cleanup_temp_files(video_path):
    try:
        if video_path and os.path.exists(video_path):
            # If it's in our temp directory, delete it
            temp_dir = Utils.get_temp_dir()
            if os.path.dirname(video_path) == temp_dir:
                os.remove(video_path)
                print(f"Deleted temporary video: {video_path}")
        
        # Delete screenshot directory if it exists and is empty
        screenshots_dir = os.path.join(os.getcwd(), "high_res_screenshots")
        if os.path.exists(screenshots_dir) and not os.listdir(screenshots_dir):
            os.rmdir(screenshots_dir)
            print(f"Deleted empty screenshots directory: {screenshots_dir}")
    except Exception as e:
        print(f"Error cleaning up temporary files: {str(e)}")

# ------------------------ FLASK WEB APPLICATION ------------------------

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# Store ongoing conversion jobs
jobs = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_conversion', methods=['POST'])
def start_conversion():
    try:
        data = request.json
        youtube_url = data.get('youtube_url')
        mode = data.get('mode', 'interval')
        
        if not youtube_url:
            return jsonify({'error': 'YouTube URL is required'}), 400
        
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Initialize variables
        interval = None
        timestamp_list = []
        timestamp_notes = {}
        
        # Process based on mode
        if mode == 'interval':
            interval = int(data.get('interval', 60))
            if interval < 5:
                return jsonify({'error': 'Interval must be at least 5 seconds'}), 400
        else:  # custom mode
            timestamp_json = data.get('timestamp_list')
            if not timestamp_json:
                return jsonify({'error': 'Timestamp list is required for custom mode'}), 400
            
            try:
                timestamp_data = json.loads(timestamp_json)
                
                # Handle different formats of timestamp data
                if isinstance(timestamp_data, dict):
                    # Check if this is the format with video ID as the key
                    # Format: {"videoId": {"timestamps": {"63": "note1", "369": "note2"}, "title": "Video Title"}}
                    for video_id, video_data in timestamp_data.items():
                        if isinstance(video_data, dict) and 'timestamps' in video_data:
                            # Extract timestamps from nested structure
                            timestamp_dict = video_data['timestamps']
                            if isinstance(timestamp_dict, dict):
                                timestamp_list = list(timestamp_dict.keys())
                                timestamp_notes = timestamp_dict
                                break  # We only process the first video ID entry
                        else:
                            # Regular format: {"1:30": "note1", "2:45": "note2"}
                            timestamp_list = list(timestamp_data.keys())
                            timestamp_notes = timestamp_data
                elif isinstance(timestamp_data, list):
                    timestamp_list = timestamp_data
                else:
                    return jsonify({'error': 'Invalid timestamp format'}), 400
            except json.JSONDecodeError:
                return jsonify({'error': 'Invalid JSON format for timestamps'}), 400
        
        # Create job entry
        jobs[job_id] = {
            'status': 'queued',
            'message': 'Job queued',
            'progress': 0,
            'pdf_path': None,
            'timestamp_notes': timestamp_notes
        }
        
        # Start conversion in a separate thread
        thread = threading.Thread(
            target=process_conversion,
            args=(job_id, youtube_url, mode, timestamp_list, interval, timestamp_notes)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'job_id': job_id
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def process_conversion(job_id, youtube_url, mode, timestamp_list, interval, timestamp_notes=None):
    try:
        # Update job status
        jobs[job_id]['status'] = 'processing'
        jobs[job_id]['message'] = 'Getting video stream...'
        jobs[job_id]['progress'] = 5
        jobs[job_id]['details'] = 'Analyzing YouTube video and preparing for capture'
        
        # Get video stream URL and info without downloading
        stream_url, video_title, duration = get_streaming_url(youtube_url)
        
        if not stream_url:
            jobs[job_id]['status'] = 'error'
            jobs[job_id]['message'] = 'Failed to get video stream'
            return
        
        # Update job status
        jobs[job_id]['message'] = 'Preparing to capture screenshots...'
        jobs[job_id]['progress'] = 15
        jobs[job_id]['details'] = f'Video title: {video_title}, Duration: {duration} seconds'
        
        # Determine timestamps
        if mode == 'interval':
            timestamps = generate_interval_timestamps(duration, interval)
            jobs[job_id]['details'] = f'Video title: {video_title}, Taking screenshots every {interval} seconds'
        else:  # custom timestamps
            # Convert string timestamps to seconds
            timestamps = []
            for ts in timestamp_list:
                try:
                    seconds = parse_timestamp(ts)
                    timestamps.append(seconds)
                except Exception as e:
                    print(f"Error parsing timestamp {ts}: {str(e)}")
            
            if not timestamps:
                timestamps = generate_interval_timestamps(duration, 60)  # Default fallback
                jobs[job_id]['details'] = f'Video title: {video_title}, Using default intervals (60s) as custom timestamps failed'
            else:
                jobs[job_id]['details'] = f'Video title: {video_title}, Using {len(timestamps)} custom timestamps'
        
        # Capture screenshots
        screenshots_dir = os.path.join(os.getcwd(), "screenshots_" + job_id)
        Utils.ensure_dir(screenshots_dir)
        
        # Update job status before starting capture
        jobs[job_id]['message'] = 'Capturing screenshots...'
        jobs[job_id]['progress'] = 20
        
        # Track progress for each screenshot
        total_screenshots = len(timestamps)
        screenshot_progress_weight = 50  # Screenshots account for 50% of total progress
        base_progress = 20  # Starting progress for screenshot phase
        
        # Define a progress callback function
        def update_screenshot_progress(current_index, total):
            if total <= 0:
                return
            screenshot_progress = (current_index / total) * screenshot_progress_weight
            jobs[job_id]['progress'] = base_progress + screenshot_progress
            jobs[job_id]['details'] = f'Capturing screenshot {current_index} of {total} ({int(current_index/total*100)}%)'
        
        # Capture screenshots with progress updates
        image_paths = capture_screenshots(stream_url, timestamps, output_dir=screenshots_dir, progress_callback=update_screenshot_progress)
        
        if not image_paths:
            jobs[job_id]['status'] = 'error'
            jobs[job_id]['message'] = 'Failed to capture screenshots'
            return
        
        # Update job status
        jobs[job_id]['status'] = 'generating_pdf'
        jobs[job_id]['message'] = 'Creating PDF...'
        jobs[job_id]['progress'] = 70
        jobs[job_id]['details'] = f'Combining {len(image_paths)} screenshots into PDF'
        
        # Create PDF
        safe_title = Utils.sanitize_filename(video_title if video_title else "YouTube_Video")
        pdf_filename = f"{safe_title}_{job_id}.pdf"
        pdf_path = os.path.join(Utils.get_pdf_dir(), pdf_filename)
        
        # Pass timestamp notes to the PDF creation function
        jobs[job_id]['progress'] = 80
        jobs[job_id]['details'] = 'Generating PDF with timestamps and notes'
        
        create_pdf(image_paths, video_title=video_title, output_pdf=pdf_path, timestamp_notes=timestamp_notes)
        
        # Cleanup phase
        jobs[job_id]['progress'] = 95
        jobs[job_id]['details'] = 'Cleaning up temporary files'
        
        # Delete screenshots after PDF creation
        for img_path in image_paths:
            if os.path.exists(img_path):
                os.remove(img_path)
        
        if os.path.exists(screenshots_dir):
            os.rmdir(screenshots_dir)
        
        # Delete temporary files
        temp_dir = Utils.get_temp_dir()
        for filename in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        # Update job status
        jobs[job_id]['status'] = 'completed'
        jobs[job_id]['message'] = 'Conversion completed successfully!'
        jobs[job_id]['progress'] = 100
        jobs[job_id]['details'] = f'PDF created successfully: {pdf_filename}'
        jobs[job_id]['pdf_path'] = pdf_path
        jobs[job_id]['pdf_filename'] = pdf_filename
        
    except Exception as e:
        print(f"Error in conversion process: {str(e)}")
        jobs[job_id]['status'] = 'error'
        jobs[job_id]['message'] = f'Error: {str(e)}'
        jobs[job_id]['details'] = f'Failed at step: {jobs[job_id].get("details", "Unknown step")}'

@app.route('/job_status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    if job_id not in jobs:
        return jsonify({'status': 'failed', 'message': 'Job not found'}), 404
    
    job = jobs[job_id]
    response = {
        'status': job['status'] if job['status'] != 'error' else 'failed',
        'message': job['message'],
        'progress': job['progress'] / 100  # Convert to 0-1 range for frontend
    }
    
    if job.get('details'):
        response['details'] = job['details']
    
    if job['status'] == 'completed' and job.get('pdf_filename'):
        response['pdf_filename'] = job['pdf_filename']
    
    return jsonify(response)

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    pdf_dir = Utils.get_pdf_dir()
    
    # Check if file exists
    file_path = os.path.join(pdf_dir, filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    # Schedule file deletion after a short delay (3 minutes)
    def delete_file_later(file_path, delay=180):
        time.sleep(delay)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Deleted temporary file: {file_path}")
        except Exception as e:
            print(f"Error deleting file {file_path}: {str(e)}")
    
    # Start a thread to delete the file after it's been downloaded
    threading.Thread(target=delete_file_later, args=(file_path,), daemon=True).start()
    
    return send_from_directory(pdf_dir, filename, as_attachment=True)

# Command line interface function
def cli_main():
    parser = argparse.ArgumentParser(description="YouTube Video to PDF Converter - Terminal Version")
    parser.add_argument("--url", '-u', type=str, help="YouTube URL to process")
    parser.add_argument("--mode", '-m', type=str, choices=["stream", "download"], default="stream",
                        help="Processing mode: stream (default) or download")
    parser.add_argument("--timestamp-type", '-t', type=str, choices=["specific", "interval"], default="interval",
                        help="Timestamp type: specific (list of times) or interval (regular intervals)")
    parser.add_argument("--timestamps", '-ts', type=str, default="",
                        help="Comma-separated list of specific timestamps (e.g., '0:30,1:45,2:10')")
    parser.add_argument("--interval", '-i', type=int, default=30,
                        help="Interval in seconds between screenshots (default: 30)")
    parser.add_argument("--output", '-o', type=str, default="",
                        help="Output PDF file path (default: auto-generate from video title)")
    
    args = parser.parse_args()
    
    # If no URL is provided, prompt for it
    youtube_url = args.url
    if not youtube_url:
        youtube_url = input("Enter YouTube URL: ")
    
    mode = args.mode
    timestamp_type = args.timestamp_type
    timestamp_input = args.timestamps
    interval = args.interval
    output_file = args.output
    
    print(f"\nYouTube to PDF Converter - Terminal Version")
    print(f"=======================================\n")
    print(f"Processing YouTube URL: {youtube_url}")
    print(f"Mode: {mode}")
    print(f"Timestamp type: {timestamp_type}")
    
    if timestamp_type == "specific":
        if not timestamp_input:
            timestamp_input = input("Enter comma-separated timestamps (e.g., 0:30,1:45,2:10): ")
        print(f"Using specific timestamps: {timestamp_input}")
    else:
        print(f"Using interval: {interval} seconds")
    
    if output_file:
        print(f"Output file: {output_file}")
    
    try:
        # Process video based on mode
        if mode == "download":
            video_path, video_title, duration = get_youtube_stream_url(youtube_url)
        else:  # stream mode
            video_path, video_title, duration = get_streaming_url(youtube_url)
        
        if not video_path or not video_title:
            print("Failed to process video URL.")
            return
        
        print(f"Video title: {video_title}")
        print(f"Video duration: {timedelta(seconds=int(duration))}")
        
        # Process timestamps
        timestamps = []
        if timestamp_type == "specific":
            # Parse specific timestamps
            if timestamp_input:
                timestamp_strings = timestamp_input.split(',')
                try:
                    timestamps = [parse_timestamp(ts.strip()) for ts in timestamp_strings if ts.strip()]
                    timestamps.sort()  # Ensure timestamps are in order
                except ValueError as e:
                    print(f"Error parsing timestamps: {e}")
                    return
            if not timestamps:
                print("No valid timestamps provided.")
                return
        else:  # interval mode
            timestamps = generate_interval_timestamps(duration, interval)
        
        print(f"Processing {len(timestamps)} timestamps...")
        
        # Capture screenshots
        screenshots_dir = "high_res_screenshots"
        image_paths = capture_screenshots(video_path, timestamps, screenshots_dir)
        
        if not image_paths:
            print("No screenshots were captured.")
            return
        
        # Create PDF
        pdf_path = create_pdf(image_paths, video_title, output_file)
        
        if pdf_path and os.path.exists(pdf_path):
            print(f"\nPDF created successfully at: {pdf_path}")
        else:
            print("Failed to create PDF.")
        
        # Clean up
        cleanup_temp_files(video_path)
        
        # Clean up screenshot directory
        for img_path in image_paths:
            if os.path.exists(img_path):
                os.remove(img_path)
                
        if os.path.exists(screenshots_dir) and not os.listdir(screenshots_dir):
            os.rmdir(screenshots_dir)
            
    except Exception as e:
        print(f"Error processing video: {str(e)}")

if __name__ == '__main__':
    # Ensure necessary directories exist
    Utils.get_temp_dir()
    pdf_dir = Utils.get_pdf_dir()
    
    # Clean up existing files in PDF directory
    def cleanup_directories():
        print("Running directory cleanup...")
        # Clean PDF directory
        for filename in os.listdir(pdf_dir):
            if filename.endswith('.pdf'):
                try:
                    file_path = os.path.join(pdf_dir, filename)
                    # Check if file is older than 1 hour
                    if os.path.exists(file_path) and time.time() - os.path.getmtime(file_path) > 3600:
                        os.remove(file_path)
                        print(f"Cleaned up old PDF file: {filename}")
                except Exception as e:
                    print(f"Error removing file {filename}: {str(e)}")
        
        # Clean temp directory
        temp_dir = Utils.get_temp_dir()
        for filename in os.listdir(temp_dir):
            try:
                file_path = os.path.join(temp_dir, filename)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Cleaned up temp file: {filename}")
            except Exception as e:
                print(f"Error removing temp file {filename}: {str(e)}")
    
    # Run initial cleanup
    cleanup_directories()
    
    # Start periodic cleanup thread
    def periodic_cleanup():
        while True:
            time.sleep(1800)  # Run every 30 minutes
            cleanup_directories()
    
    cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
    cleanup_thread.start()
    
    # Run the Flask app
    app.run(debug=True, host='0.0.0.0', port=5000) 