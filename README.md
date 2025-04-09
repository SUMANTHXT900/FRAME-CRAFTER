# FrameCrafter

FrameCrafter is a powerful tool that converts YouTube videos into PDF documents containing screenshots at specified intervals or custom timestamps. It provides both a web interface and a command-line interface for easy use.

## Features

- Extract screenshots from YouTube videos at regular intervals or specific timestamps
- Create well-formatted PDF documents with screenshots
- Add custom notes for timestamps
- Support for both web interface and command-line usage
- Progress tracking for conversion jobs
- Automatic cleanup of temporary files
- Support for high-quality video formats up to 1080p

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/framecrafter.git
cd framecrafter
```

2. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Web Interface

1. Start the Flask server:
```bash
python framecrafter.py
```

2. Open your web browser and navigate to `http://localhost:5000`

3. Enter a YouTube URL and choose your preferred screenshot method:
   - Interval mode: Take screenshots at regular intervals
   - Custom mode: Specify exact timestamps for screenshots

### Command Line Interface

The script can also be used from the command line with various options:

```bash
python framecrafter.py --url "YOUTUBE_URL" [OPTIONS]

Options:
  --url, -u          YouTube URL to process
  --mode, -m         Processing mode: stream (default) or download
  --timestamp-type, -t  Timestamp type: specific or interval (default)
  --timestamps, -ts   Comma-separated list of timestamps (e.g., "0:30,1:45,2:10")
  --interval, -i      Interval in seconds between screenshots (default: 30)
  --output, -o       Output PDF file path
```

Example usage:
```bash
# Take screenshots every 30 seconds
python framecrafter.py -u "https://www.youtube.com/watch?v=VIDEO_ID" -i 30

# Take screenshots at specific timestamps
python framecrafter.py -u "https://www.youtube.com/watch?v=VIDEO_ID" -t specific -ts "0:30,1:45,2:10"
```

## Requirements

- Python 3.7+
- Flask
- OpenCV (cv2)
- yt-dlp
- FPDF
- Other dependencies listed in requirements.txt

## Project Structure

```
framecrafter/
├── framecrafter.py     # Main application file
├── requirements.txt    # Python dependencies
├── LICENSE            # Apache License 2.0
├── README.md         # Project documentation
├── static/           # Static files for web interface
└── templates/        # HTML templates for web interface
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for YouTube video processing
- [OpenCV](https://opencv.org/) for image processing
- [FPDF](https://pyfpdf.readthedocs.io/en/latest/) for PDF generation
- [Flask](https://flask.palletsprojects.com/) for web interface 