console.log("function.js loaded");

document.addEventListener("DOMContentLoaded", function() {
    const submitBtn = document.getElementById("submit-btn");
    if (submitBtn) {
        submitBtn.addEventListener("click", submitStory);
    } else {
        console.error("Submit button not found!");
    }
});

// Global variable to store current job ID
let currentJobId = null;

function submitStory() {
    console.log("submitStory clicked"); // Confirm the function fires
    
    // Show loading state
    showLoading(true);
    
    const textarea = document.querySelector('textarea');
    const story = textarea.value;
    
    // Create a new story using the RESTful API
    fetch('http://localhost:8000/api/v1/stories', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ text: story })
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
    
    const pollInterval = setInterval(() => {
        fetch(`http://localhost:8000/api/v1/stories/${currentJobId}`)
            .then(handleApiResponse)
            .then(data => {
                console.log('Status update:', data);
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
    }, 2000); // Check every 2 seconds
}

function updateStatusDisplay(jobData, loaderElement) {
    switch (jobData.status) {
        case 'processing_images':
            loaderElement.innerText = "Generating images...";
            break;
        case 'processing_video':
            loaderElement.innerText = "Editing video... (this may take a few minutes)";
            break;
        case 'completed':
            loaderElement.innerText = "Processing complete!";
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
        loaderElement.innerText = "Images created! Now editing video (this may take several minutes)...";
    }
}

function showVideoResult(jobId) {
    // Get the side panel element
    const sidePanel = document.querySelector('.side-panel');
    
    if (!sidePanel) {
        console.error('Side panel not found');
        return;
    }
    
    // Create a video container inside the side panel
    const videoElement = document.createElement('video');
    videoElement.controls = true;
    videoElement.style.width = '100%'; // Make video fit the side panel width
    videoElement.style.maxHeight = '60vh'; // Limit height to 60% of viewport height
    
    // Add loading indicator inside the video element
    const loadingText = document.createElement('p');
    loadingText.innerText = 'Loading video, please wait...';
    loadingText.style.textAlign = 'center';
    sidePanel.appendChild(loadingText);
    
    // Set up error handling for the video
    videoElement.onerror = function() {
        loadingText.innerText = 'Error loading video. Please try again later.';
        loadingText.style.color = 'red';
    };
    
    // Set up load completion handler
    videoElement.onloadeddata = function() {
        loadingText.style.display = 'none';
    };
    
    // Set source with a timestamp to prevent caching issues
    videoElement.src = `http://localhost:8000/api/v1/videos/${jobId}?t=${new Date().getTime()}`;
    videoElement.className = 'result-video';
    
    // Add a title above the video
    const videoTitle = document.createElement('h3');
    videoTitle.innerText = 'Generated Video:';
    videoTitle.style.marginTop = '20px';
    
    // Find the loader text element
    const loaderText = sidePanel.querySelector('.loader-text');
    
    // Hide the loading spinner but keep the panel open
    const loader = sidePanel.querySelector('.loader');
    if (loader) {
        loader.style.display = 'none';
    }
    
    // Add elements to the side panel - after the loader text
    if (loaderText) {
        sidePanel.insertBefore(videoTitle, loaderText.nextSibling);
        sidePanel.insertBefore(videoElement, videoTitle.nextSibling);
    } else {
        sidePanel.appendChild(videoTitle);
        sidePanel.appendChild(videoElement);
    }
    
    // Make sure the side panel stays open
    sidePanel.style.width = '30%';
    
    // Add a close button to the panel
    const closeButton = document.createElement('button');
    closeButton.innerText = '✕';
    closeButton.className = 'close-panel-btn';
    closeButton.style.position = 'absolute';
    closeButton.style.top = '10px';
    closeButton.style.right = '10px';
    closeButton.style.background = 'none';
    closeButton.style.border = 'none';
    closeButton.style.fontSize = '20px';
    closeButton.style.cursor = 'pointer';
    closeButton.style.color = 'white';
    
    closeButton.onclick = function() {
        showLoading(false); // Close the panel
    };
    
    sidePanel.appendChild(closeButton);
}

// This function is no longer needed as we're using the side panel instead
// Keeping it for reference
function createResultsContainer() {
    const container = document.createElement('div');
    container.id = 'results-container';
    container.className = 'results-container';
    
    const responseContainer = document.getElementById('response-container');
    if (responseContainer) {
        responseContainer.parentNode.insertBefore(container, responseContainer.nextSibling);
    } else {
        document.body.appendChild(container);
    }
    
    return container;
}

function showLoading(isLoading) {
    const submitBtn = document.getElementById("submit-btn");
    if (submitBtn) {
        submitBtn.disabled = isLoading;
    }
    
    let sidePanel = document.querySelector('.side-panel');
    if (sidePanel) {
        sidePanel.offsetWidth; // Force reflow to restart transition
        sidePanel.style.width = isLoading ? "30%" : "0";
        
        // If we're hiding the side panel, clean up any video content
        if (!isLoading) {
            // Reset the loader visibility
            const loader = sidePanel.querySelector('.loader');
            if (loader) {
                loader.style.display = 'block';
            }
            
            // Remove video elements
            const video = sidePanel.querySelector('.result-video');
            if (video) {
                video.remove();
            }
            
            // Remove title
            const title = sidePanel.querySelector('h3');
            if (title) {
                title.remove();
            }
            
            // Remove close button
            const closeBtn = sidePanel.querySelector('.close-panel-btn');
            if (closeBtn) {
                closeBtn.remove();
            }
            
            // Reset the loader text
            const loaderText = sidePanel.querySelector('.loader-text');
            if (loaderText) {
                loaderText.innerText = "creating video...";
                loaderText.style.color = ''; // Reset color
            }
        }
    }
}

// API response handlers
function handleApiResponse(response) {
    if (!response.ok) {
        // If the server response is not OK, parse the JSON to get the error message
        return response.json().then(errorData => {
            throw new Error(errorData.error || 'API Error');
        });
    }
    return response.json();
}

function handleApiError(error) {
    console.error('Error:', error);
    
    // Show error in UI
    const loaderText = document.querySelector('.loader-text');
    if (loaderText) {
        loaderText.innerText = `Error: ${error.message}`;
        loaderText.style.color = 'red';
    }
    
    // Re-enable the button
    showLoading(false);
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