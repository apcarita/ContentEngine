console.log("function.js loaded");

document.addEventListener("DOMContentLoaded", function() {
    const submitBtn = document.getElementById("submit-btn");
    if (submitBtn) {
        submitBtn.addEventListener("click", submitStory);
    } else {
        console.error("Submit button not found!");
    }
});

function submitStory() {
    console.log("submitStory clicked"); // Confirm the function fires
    // Disable the submit button
    const submitBtn = document.getElementById("submit-btn");
    if (submitBtn) {
        submitBtn.disabled = true;
    }

    let sidePanel = document.querySelector('.side-panel');
    if (sidePanel) {
        sidePanel.offsetWidth; // Force reflow to restart transition
        sidePanel.style.width = "30%";
    } else {
        console.error("Side panel element not found!");
    }

    const textarea = document.querySelector('textarea');
    const story = textarea.value;

    // Fetch call to run RotPrompt.py on the server
    fetch('http://localhost:8000/run-script', {  // Updated port to 8000
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ story: story })
    })
    .then(response => {
        if (!response.ok) throw new Error('Network response error');
        return response.json();  // Parse as JSON to get output
    })
    .then(json => {
        console.log('Server response:', json);
        const outputDiv = document.getElementById('output');
        const responseContainer = document.getElementById('response-container');
        if (outputDiv && responseContainer) {
            outputDiv.value = json.rot_output;
            responseContainer.classList.remove('hidden');
            responseContainer.offsetHeight;

            const loaderText = document.querySelector('.loader-text');

            if(loaderText && json.status === 'images_started') {
                // Start polling for status
                loaderText.innerText = "fetching images...";
                pollImagesStatus(loaderText);

            }
        } else {
            console.error('Output elements not found!');
        }
    })
    .catch((error) => {
        console.error('Error:', error);
        // Re-enable the button on error
        if (submitBtn) {
            submitBtn.disabled = false;
        }
    });
}

function pollImagesStatus(loaderElement) {
    const checkStatus = () => {
        fetch('http://localhost:8000/check-status')
            .then(response => response.json())
            .then(status => {
                console.log('Status:', status);
                if (!status.images_started) {
                    loaderElement.innerText = "Editing video... (this may take a few minutes)";
                    return;
                }
                // If still running, check again in 2 seconds
                setTimeout(checkStatus, 2000);
            })
            .catch(error => console.error('Status check error:', error));
    };
    // Start checking
    checkStatus();
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