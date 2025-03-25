console.log("function.js loaded");

document.addEventListener("DOMContentLoaded", function() {
    const submitBtn = document.getElementById("submit-btn");
    if (submitBtn) {
        submitBtn.addEventListener("click", submitStory);
    } else {
        console.error("Submit button not found!");
    }
    
    // Set up the duration slider with snapping functionality and update the display
    const durationSlider = document.getElementById("duration-slider");
    const durationValue = document.getElementById("duration-value");
    
    if (durationSlider) {
        // Set the step attribute to 1 second for snapping
        durationSlider.setAttribute("step", "1");
        
        // Update the duration counter when the slider changes
        durationSlider.addEventListener("input", function() {
            // Round to the nearest integer to ensure perfect snapping
            const value = Math.round(this.value);
            if (this.value != value) {
                this.value = value;
            }
            
            // Update the duration display
            if (durationValue) {
                durationValue.textContent = value;
            }
        });
        
        // Initialize the duration display with the default value
        if (durationValue) {
            durationValue.textContent = durationSlider.value;
        }
    } else {
        console.error("Duration slider not found!");
    }
    
    // Set up style button functionality
    const styleButtons = document.querySelectorAll('.style-btn');
    if (styleButtons.length > 0) {
        styleButtons.forEach(button => {
            button.addEventListener('click', function() {
                // Remove active class from all buttons and add inactive
                styleButtons.forEach(btn => {
                    btn.classList.remove('active');
                    if (btn !== this) {
                        btn.classList.add('inactive');
                    } else {
                        btn.classList.remove('inactive');
                    }
                });
                
                // Add active class to clicked button
                this.classList.add('active');
                
                // Store the selected style for later use when submitting
                window.selectedStyle = this.getAttribute('data-style');
                console.log(`Selected style: ${window.selectedStyle}`);
            });
        });
        
        // Initialize by setting the first button (Brain Rot) as active and others as inactive
        const firstButton = styleButtons[0];
        if (firstButton) {
            firstButton.classList.add('active');
            window.selectedStyle = firstButton.getAttribute('data-style');
            
            // Set others as inactive
            for (let i = 1; i < styleButtons.length; i++) {
                styleButtons[i].classList.add('inactive');
            }
        }
    }
    
    populateMusicDropdown();
    populateVideoDropdown();
});

// Global variable to store current job ID
let currentJobId = null;

// Handle API response - check for errors and parse JSON
function handleApiResponse(response) {
    if (!response.ok) {
        // Check if the response contains JSON error details
        return response.json().then(errorData => {
            throw new Error(errorData.error || `API request failed with status: ${response.status}`);
        }).catch(err => {
            // If JSON parsing fails, use the response status text
            throw new Error(`API request failed: ${response.statusText || response.status}`);
        });
    }
    return response.json();
}

// Handle API errors and display them to the user
function handleApiError(error) {
    console.error('API Error:', error);
    
    // Hide loading state
    showLoading(false);
    
    // Show error message in the loader text area
    const loaderText = document.querySelector('.loader-text');
    if (loaderText) {
        loaderText.innerText = `Error: ${error.message || 'Unknown error occurred'}`;
        loaderText.classList.remove('hidden');
        loaderText.style.color = 'red';
    }
    
    // You could also show a notification or alert
    // alert(`Error: ${error.message}`);
}

function submitStory() {
    console.log("submitStory clicked"); // Confirm the function fires
    
    // Show loading state
    showLoading(true);
    
    const textarea = document.querySelector('textarea');
    const story = textarea.value;
    
    // Get the duration value from the slider
    const durationSlider = document.getElementById("duration-slider");
    const duration = durationSlider ? parseInt(durationSlider.value) : 30; // Default to 30 if slider not found
    
    // Get the selected style (default to brain-rot if none selected)
    const styleType = window.selectedStyle || 'brain-rot';
    
    // Retrieve the selected background music from the dropdown
    const selectedMusic = document.getElementById('musicSelector').value;
    
    // Add background video selection to the payload
    const selectedVideo = document.getElementById('videoSelector').value;
    
    console.log(`Submitting story with duration: ${duration} seconds, style: ${styleType}, music: ${selectedMusic}, and video: ${selectedVideo}`);
    
    // Create a new story using the RESTful API
    fetch('http://localhost:8000/api/v1/stories', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
            text: story,
            duration: duration,     // Duration parameter
            style: styleType,       // Style parameter
            music: selectedMusic,   // Music parameter
            video: selectedVideo    // Video background parameter
        })
    })
    .then(handleApiResponse)
    .then(data => {
        console.log('Server response:', data);
        currentJobId = data.data.job_id;
        
        // Display ROT output
        displayRotOutput(data.data.rot_output);
        
        // Begin polling for status if processing continues
        if (data.data.status !== 'completed') {
            startStatusPolling();
        } else {
            showLoading(false);
        }
    })
    .catch(handleApiError);
}

function displayRotOutput(rotOutput) {
    const outputDiv = document.getElementById('output');
    const responseContainer = document.getElementById('response-container');
    
    if (outputDiv && responseContainer) {
        outputDiv.value = rotOutput;
        responseContainer.classList.remove('hidden');
        responseContainer.offsetHeight; // Force reflow
    } else {
        console.error('Output elements not found!');
    }
}

function startStatusPolling() {
    if (!currentJobId) {
        console.error("No job ID to poll status for");
        return;
    }
    
    const loaderText = document.querySelector('.loader-text');
    if (!loaderText) {
        console.error("Loader text element not found");
        return;
    }
    
    // Keep track of how long we've been waiting
    let pollCount = 0;
    const maxPolls = 60; // About 2 minutes at 2-second intervals
    let previousImageCount = 0; // Track the previous image count
    
    const pollInterval = setInterval(() => {
        fetch(`http://localhost:8000/api/v1/stories/${currentJobId}`)
            .then(handleApiResponse)
            .then(data => {
                console.log('Status update:', data);
                
                // Check if image count has changed
                const currentImageCount = data.data.image_count || 0;
                if (currentImageCount !== previousImageCount) {
                    previousImageCount = currentImageCount;
                    console.log(`Image count updated: ${currentImageCount}`);
                }
                
                updateStatusDisplay(data.data, loaderText);
                
                // If processing is complete or failed, stop polling
                if (data.data.status === 'completed' || 
                    data.data.status === 'completed_with_errors' || 
                    data.data.status === 'failed') {
                    clearInterval(pollInterval);
                    
                    if (data.data.status === 'completed' || data.data.status === 'completed_with_errors') {
                        showVideoResult(currentJobId);
                    } else {
                        // Show failure message and enable the submit button again
                        showLoading(false);
                    }
                }
                
                // For video processing, give more feedback about waiting
                if (data.data.status === 'processing_video') {
                    pollCount++;
                    if (pollCount > 15 && pollCount % 5 === 0) { // After 30 seconds, give updates
                        loaderText.innerText = `Still processing video... (${Math.floor(pollCount*2/60)} minute${pollCount*2/60 >= 2 ? 's' : ''})`;
                    }
                }
            })
            .catch(error => {
                console.error('Status check error:', error);
                clearInterval(pollInterval);
                showLoading(false);
            });
    }, 1000); // Poll every 1 second to get more responsive image count updates
}

function updateStatusDisplay(jobData, loaderElement) {
    switch (jobData.status) {
        case 'processing_images':
            // Display image count if available
            if (jobData.hasOwnProperty('image_count')) {
                const expectedImages = jobData.total_images_expected || "multiple";
                loaderElement.innerText = `Generating images... ${jobData.image_count} ${jobData.image_count === 1 ? 'image' : 'images'} created${jobData.total_images_expected ? ' of ' + expectedImages : ''}`;
            } else {
                loaderElement.innerText = "Generating images...";
            }
            break;
        case 'processing_video':
            if (jobData.hasOwnProperty('image_count')) {
                loaderElement.innerText = `Editing video with ${jobData.image_count} images... (this may take a few minutes)`;
            } else {
                loaderElement.innerText = "Editing video... (this may take a few minutes)";
            }
            break;
        case 'completed':
            if (jobData.hasOwnProperty('image_count')) {
                loaderElement.innerText = `Processing complete! Created video with ${jobData.image_count} images.`;
            } else {
                loaderElement.innerText = "Processing complete!";
            }
            break;
        case 'completed_with_errors':
            loaderElement.innerText = "Video processed with issues. Attempting to display...";
            break;
        case 'failed':
            if (jobData.video_status === 'timeout') {
                loaderElement.innerText = "Video processing timed out. This can happen with longer stories. Please try with a shorter story.";
            } else {
                loaderElement.innerText = `Error: ${jobData.error || 'Processing failed'}`;
            }
            loaderElement.style.color = 'red';
            break;
        default:
            loaderElement.innerText = `Processing: ${jobData.status}`;
    }
    
    // Additional information based on the specific statuses
    if (jobData.images_status === 'completed' && jobData.video_status === 'processing') {
        if (jobData.hasOwnProperty('image_count')) {
            loaderElement.innerText = `${jobData.image_count} images created! Now editing video (this may take several minutes)...`;
        } else {
            loaderElement.innerText = "Images created! Now editing video (this may take several minutes)...";
        }
    }
}

function showVideoResult(jobId) {
    // Get the side panel element
    const sidePanel = document.querySelector('.side-panel');
    
    if (!sidePanel) {
        console.error('Side panel not found');
        return;
    }
    
    // Ensure the side panel is visible
    sidePanel.classList.add('visible');
    
    // Get the video container and video element
    const videoContainer = document.getElementById('video-container');
    const videoWrapper = document.getElementById('video-wrapper');
    const videoElement = document.getElementById('result-video');
    const downloadButton = document.getElementById('download-video');
    const readyMessage = document.getElementById('ready-message');
    
    if (!videoContainer || !videoElement || !videoWrapper) {
        console.error('Video elements not found');
        return;
    }
    
    // Hide the ready message
    if (readyMessage) {
        readyMessage.style.display = 'none';
    }
    
    // Show loading state
    const loadingText = document.querySelector('.loader-text');
    if (loadingText) {
        loadingText.innerText = 'Loading video, please wait...';
    }
    
    // Set up error handling for the video
    videoElement.onerror = function() {
        if (loadingText) {
            loadingText.innerText = 'Error loading video. Please try again later.';
            loadingText.style.color = 'red';
        }
    };
    
    // Set up load completion handler
    videoElement.onloadeddata = function() {
        // Hide loader and loader text
        const loader = document.querySelector('.loader');
        if (loader) {
            loader.classList.add('hidden');
        }
        
        if (loadingText) {
            loadingText.classList.add('hidden');
        }
        
        // Show the video wrapper and video element
        videoWrapper.classList.remove('hidden');
        videoElement.classList.remove('hidden');
        
        // Enable download button
        downloadButton.classList.remove('hidden');
        downloadButton.addEventListener('click', function() {
            downloadVideo(jobId);
        });
        
        console.log('Video loaded successfully and is now visible');
    };
    
    // Set source with a timestamp to prevent caching issues
    const videoUrl = `http://localhost:8000/api/v1/videos/${jobId}?t=${new Date().getTime()}`;
    console.log(`Loading video from URL: ${videoUrl}`);
    videoElement.src = videoUrl;
}

function downloadVideo(jobId) {
    // Create a temporary link to download the video
    const videoUrl = `http://localhost:8000/api/v1/videos/${jobId}`;
    const link = document.createElement('a');
    link.href = videoUrl;
    link.download = `brain-rot-video-${jobId}.mp4`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function showLoading(isLoading) {
    const submitBtn = document.getElementById("submit-btn");
    if (submitBtn) {
        submitBtn.disabled = isLoading;
    }
    
    let sidePanel = document.querySelector('.side-panel');
    if (sidePanel) {
        sidePanel.classList.add('visible'); // Always keep the panel visible
        
        // Toggle loader and ready message
        const loader = sidePanel.querySelector('.loader');
        const loaderText = sidePanel.querySelector('.loader-text');
        const readyMessage = document.getElementById('ready-message');
        
        if (isLoading) {
            // Show loader, hide ready message
            if (loader) loader.classList.remove('hidden');
            if (loaderText) loaderText.classList.remove('hidden');
            if (readyMessage) readyMessage.style.display = 'none';
        } else {
            // Hide loader
            if (loader) loader.classList.add('hidden');
            if (loaderText) loaderText.classList.add('hidden');
            
            // Show ready message if no video is displayed
            const videoElement = document.getElementById('result-video');
            if (readyMessage && videoElement && videoElement.classList.contains('hidden')) {
                readyMessage.style.display = 'block';
            }
            
            // Reset video container
            resetVideoContainer();
        }
    }
}

function resetVideoContainer() {
    const videoContainer = document.getElementById('video-container');
    const videoElement = document.getElementById('result-video');
    const downloadButton = document.getElementById('download-video');
    const readyMessage = document.getElementById('ready-message');
    
    if (videoElement) {
        videoElement.src = '';
        videoElement.classList.add('hidden');
    }
    
    if (downloadButton) {
        downloadButton.classList.add('hidden');
    }
    
    if (readyMessage) {
        readyMessage.style.display = 'block';
    }
}

function toggleTheme(){
    document.body.classList.toggle("light");
    const btn = document.querySelector(".theme-toggle");
    if (document.body.classList.contains("light")) {
        btn.innerText = "☀️ Light";
    } else {
        btn.innerText = "🌙 Dark";
    }
}

function scrollToTop(){
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// New function to populate the background music dropdown from the server
function populateMusicDropdown() {
    const selectEl = document.getElementById('musicSelector');
    if (!selectEl) {
        console.error('Music selector element not found');
        return;
    }
    fetch('http://localhost:8000/api/v1/music')
        .then(response => response.json())
        .then(data => {
            if (data.success && Array.isArray(data.data)) {
                // Clear existing options
                selectEl.innerHTML = '';
                // Add default 'None' option
                const noneOption = document.createElement('option');
                noneOption.value = 'none';
                noneOption.textContent = 'None';
                selectEl.appendChild(noneOption);
                // Populate dropdown with music files
                data.data.forEach(music => {
                    const option = document.createElement('option');
                    option.value = music;
                    // Remove the .mp3 extension for display
                    option.textContent = music.replace(/\.mp3$/i, '');
                    selectEl.appendChild(option);
                });
            } else {
                console.error('Error fetching music options:', data.error);
            }
        })
        .catch(error => console.error('Error fetching music options:', error));
}

// New function to populate background video dropdown similar to the music dropdown
function populateVideoDropdown() {
    const selectEl = document.getElementById('videoSelector');
    if (!selectEl) {
        console.error('Video selector element not found');
        return;
    }
    fetch('http://localhost:8000/api/v1/videos/backgrounds')
        .then(response => response.json())
        .then(data => {
            if (data.success && Array.isArray(data.data)) {
                // Clear existing options
                selectEl.innerHTML = '';
                // Add default 'None' option
                const noneOption = document.createElement('option');
                noneOption.value = 'none';
                noneOption.textContent = 'None';
                selectEl.appendChild(noneOption);
                // Populate dropdown with video files
                data.data.forEach(video => {
                    const option = document.createElement('option');
                    option.value = video;
                    // Remove the extension for display
                    option.textContent = video.replace(/\.(mp4|mov)$/i, '');
                    selectEl.appendChild(option);
                });
            } else {
                console.error('Error fetching video options:', data.error);
            }
        })
        .catch(error => console.error('Error fetching video options:', error));
}