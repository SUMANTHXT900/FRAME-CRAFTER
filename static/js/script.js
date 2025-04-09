document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const converterForm = document.getElementById('converter-form');
    const youtubeUrlInput = document.getElementById('youtube-url');
    const intervalModeRadio = document.getElementById('interval-mode');
    const customModeRadio = document.getElementById('custom-mode');
    const intervalConfig = document.getElementById('interval-config');
    const customTimestamps = document.getElementById('custom-timestamps');
    const intervalInput = document.getElementById('interval');
    const statusSection = document.querySelector('.status-section');
    const converterSection = document.querySelector('.converter-section');
    const progressBarFill = document.querySelector('.progress-bar-fill');
    const progressText = document.querySelector('.progress-text');
    const statusMessage = document.querySelector('.status-message');
    const downloadSection = document.querySelector('.download-section');
    const downloadBtn = document.getElementById('download-btn');
    const errorModal = document.getElementById('error-modal');
    const errorMessage = document.getElementById('error-message');
    const modalClose = document.querySelector('.modal-close');
    const closeModalBtn = document.getElementById('close-modal');
    const themeToggle = document.getElementById('theme-toggle');
    const timestampsJsonInput = document.getElementById('timestamps-json');
    const jsonFileName = document.getElementById('json-file-name');
    const statusIcon = document.querySelector('.status-icon');
    const statusDetails = document.querySelector('.status-details');
    const timestampsList = document.getElementById('timestamps-list');
    const timestampsPreviewCount = document.querySelector('.preview-count');
    const intervalPresets = document.querySelectorAll('.interval-preset');

    let currentJobId = null;
    let statusCheckInterval = null;

    // Theme switcher
    function initTheme() {
        // Check for saved theme preference
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark') {
            document.body.setAttribute('data-theme', 'dark');
            themeToggle.checked = true;
        }
    }

    themeToggle.addEventListener('change', function() {
        if (this.checked) {
            document.body.setAttribute('data-theme', 'dark');
            localStorage.setItem('theme', 'dark');
        } else {
            document.body.removeAttribute('data-theme');
            localStorage.setItem('theme', 'light');
        }
    });

    initTheme();

    // Mode switcher
    intervalModeRadio.addEventListener('change', toggleMode);
    customModeRadio.addEventListener('change', toggleMode);

    function toggleMode() {
        if (intervalModeRadio.checked) {
            intervalConfig.style.display = 'block';
            customTimestamps.style.display = 'none';
        } else {
            intervalConfig.style.display = 'none';
            customTimestamps.style.display = 'block';
        }
    }

    // Interval presets
    intervalPresets.forEach(preset => {
        preset.addEventListener('click', function() {
            // Remove active class from all presets
            intervalPresets.forEach(p => p.classList.remove('active'));
            // Add active class to clicked preset
            this.classList.add('active');
            // Set the interval value
            intervalInput.value = this.dataset.value;
        });
    });

    // Initialize with 1m preset active
    document.querySelector('.interval-preset[data-value="60"]').classList.add('active');

    // Handle JSON file upload
    timestampsJsonInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (!file) {
            jsonFileName.textContent = 'No file selected';
            resetTimestampsPreview();
            return;
        }

        if (file.type !== 'application/json' && !file.name.endsWith('.json')) {
            showError('Please upload a valid JSON file (.json).');
            timestampsJsonInput.value = ''; // Clear the input
            jsonFileName.textContent = 'No file selected';
            resetTimestampsPreview();
            return;
        }

        jsonFileName.textContent = file.name;

        const reader = new FileReader();
        reader.onload = function(event) {
            try {
                const jsonData = JSON.parse(event.target.result);
                // Store the timestamps data for later use
                window.timestampData = jsonData;
                
                // Display timestamps in the preview
                updateTimestampsPreview(jsonData);
            } catch (error) {
                showError('Error parsing JSON file: ' + error.message);
                jsonFileName.textContent = 'No file selected';
                timestampsJsonInput.value = ''; // Clear the input
                resetTimestampsPreview();
            }
        };
        reader.onerror = function() {
            showError('Error reading the file.');
            jsonFileName.textContent = 'No file selected';
            timestampsJsonInput.value = ''; // Clear the input
            resetTimestampsPreview();
        };
        reader.readAsText(file);
    });

    // Update timestamps preview
    function updateTimestampsPreview(data) {
        // Clear previous content
        timestampsList.innerHTML = '';
        
        let timestamps = [];
        let notes = {};
        
        // Handle different formats of timestamp data
        if (Array.isArray(data)) {
            timestamps = data;
        } else if (typeof data === 'object' && data !== null) {
            // Check if this is the format with video ID as the key
            // Format: {"videoId": {"timestamps": {"63": "note1", "369": "note2"}, "title": "Video Title"}}
            let foundNestedFormat = false;
            
            for (const videoId in data) {
                if (data[videoId] && data[videoId].timestamps) {
                    // Found the nested format
                    const timestampData = data[videoId].timestamps;
                    timestamps = Object.keys(timestampData);
                    notes = timestampData;
                    foundNestedFormat = true;
                    break;  // We only process the first video ID
                }
            }
            
            // If not in the nested format, use the regular format
            if (!foundNestedFormat) {
                timestamps = Object.keys(data);
                notes = data;
            }
        }
        
        if (timestamps.length === 0) {
            resetTimestampsPreview();
            return;
        }
        
        // Update count
        timestampsPreviewCount.textContent = `${timestamps.length} timestamps`;
        
        // Sort timestamps numerically
        timestamps.sort((a, b) => {
            // Convert to numbers if possible
            const numA = Number(a);
            const numB = Number(b);
            if (!isNaN(numA) && !isNaN(numB)) {
                return numA - numB;
            }
            return String(a).localeCompare(String(b));
        });
        
        // Create timestamp items
        timestamps.forEach((timestamp, index) => {
            const item = document.createElement('div');
            item.className = 'timestamp-item';
            
            // Format the timestamp for display
            let displayTime = timestamp;
            // If it's numeric seconds, convert to MM:SS format
            if (!isNaN(Number(timestamp))) {
                const seconds = Number(timestamp);
                const minutes = Math.floor(seconds / 60);
                const remainingSeconds = Math.floor(seconds % 60);
                displayTime = `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
            }
            
            // Add note if available
            let note = '';
            if (notes[timestamp]) {
                note = notes[timestamp];
            }
            
            item.innerHTML = `
                <span class="timestamp-number">#${index + 1}</span>
                <span class="timestamp-value">${displayTime}</span>
                ${note ? `<span class="timestamp-note">${note}</span>` : ''}
            `;
            
            timestampsList.appendChild(item);
        });
    }
    
    // Reset timestamps preview
    function resetTimestampsPreview() {
        timestampsList.innerHTML = `
            <div class="empty-state">
                <i class="fas fa-clock"></i>
                <p>No timestamps loaded yet</p>
            </div>
        `;
        timestampsPreviewCount.textContent = '0 timestamps';
    }

    // Modal controls
    modalClose.addEventListener('click', function() {
        errorModal.style.display = 'none';
    });

    closeModalBtn.addEventListener('click', function() {
        errorModal.style.display = 'none';
    });

    // Show error modal
    function showError(message) {
        errorMessage.textContent = message;
        errorModal.style.display = 'block';
    }

    // Form submission
    converterForm.addEventListener('submit', function(e) {
        e.preventDefault();

        // Validate URL
        const youtubeUrl = youtubeUrlInput.value.trim();
        if (!youtubeUrl) {
            showError('Please enter a YouTube URL.');
            return;
        }

        // YouTube URL validation regex
        const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.?be)\/.+$/;
        if (!youtubeRegex.test(youtubeUrl)) {
            showError('Please enter a valid YouTube URL.');
            return;
        }

        // Collect form data
        const mode = intervalModeRadio.checked ? 'interval' : 'custom';
        let interval = null;
        let timestampList = null;

        if (mode === 'interval') {
            interval = parseInt(intervalInput.value);
            if (isNaN(interval) || interval < 5) {
                showError('Please enter a valid interval (minimum 5 seconds).');
                return;
            }
        } else {
            // Use the JSON file data
            if (!window.timestampData) {
                showError('Please upload a valid timestamps JSON file.');
                return;
            }
            timestampList = window.timestampData;
        }

        // Show the status section and hide the converter section
        converterSection.style.display = 'none';
        statusSection.style.display = 'block';
        statusMessage.textContent = 'Initializing conversion...';
        progressBarFill.style.width = '0%';
        progressText.textContent = '0%';
        downloadSection.style.display = 'none';
        statusIcon.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        statusDetails.textContent = '';

        // Prepare request data
        const requestData = {
            youtube_url: youtubeUrl,
            mode: mode
        };

        if (mode === 'interval') {
            requestData.interval = interval;
        } else {
            requestData.timestamp_list = JSON.stringify(timestampList);
        }

        // Send the conversion request
        fetch('/start_conversion', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData),
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showError(data.error);
                converterSection.style.display = 'block';
                statusSection.style.display = 'none';
                return;
            }

            currentJobId = data.job_id;
            startStatusCheck();
        })
        .catch(error => {
            showError('An error occurred: ' + error.message);
            converterSection.style.display = 'block';
            statusSection.style.display = 'none';
        });
    });

    // Check job status
    function startStatusCheck() {
        // Clear any existing interval
        if (statusCheckInterval) {
            clearInterval(statusCheckInterval);
        }

        // Check immediately and then set interval
        checkJobStatus();
        statusCheckInterval = setInterval(checkJobStatus, 2000); // Check every 2 seconds
    }

    function checkJobStatus() {
        if (!currentJobId) return;

        fetch(`/job_status/${currentJobId}`)
            .then(response => response.json())
            .then(data => {
                updateStatusUI(data);

                // If job is completed or failed, stop checking
                if (data.status === 'completed' || data.status === 'failed') {
                    clearInterval(statusCheckInterval);
                }
            })
            .catch(error => {
                showError('Error checking job status: ' + error.message);
                clearInterval(statusCheckInterval);
            });
    }

    function updateStatusUI(data) {
        // Update progress
        if (data.progress !== undefined) {
            const progressPercent = Math.round(data.progress * 100);
            progressBarFill.style.width = `${progressPercent}%`;
            progressText.textContent = `${progressPercent}%`;
        }

        // Update status message
        if (data.message) {
            statusMessage.textContent = data.message;
        }

        // Update status details
        if (data.details) {
            statusDetails.textContent = data.details;
        }

        // Handle completed state
        if (data.status === 'completed') {
            clearInterval(statusCheckInterval);
            statusMessage.textContent = 'Conversion completed successfully!';
            statusIcon.innerHTML = '<i class="fas fa-check"></i>';
            statusIcon.classList.remove('pulse-animation');
            downloadSection.style.display = 'block';
            
            // Set up download button
            downloadBtn.onclick = function() {
                window.location.href = `/download/${data.pdf_filename}`;
            };
        }

        // Handle failed state
        if (data.status === 'failed') {
            statusIcon.innerHTML = '<i class="fas fa-exclamation-circle"></i>';
            statusIcon.classList.remove('pulse-animation');
            showError(data.message || 'Conversion failed. Please try again.');
        }
    }

    // Add ripple effect to buttons
    const buttons = document.querySelectorAll('.primary-button, .secondary-button, .interval-preset');
    
    buttons.forEach(button => {
        button.addEventListener('click', function(e) {
            const x = e.clientX - this.getBoundingClientRect().left;
            const y = e.clientY - this.getBoundingClientRect().top;
            
            const ripple = document.createElement('span');
            ripple.classList.add('ripple');
            ripple.style.left = `${x}px`;
            ripple.style.top = `${y}px`;
            
            this.appendChild(ripple);
            
            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });
});
