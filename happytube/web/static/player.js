/**
 * HappyTube Player - Controlled YouTube video player
 * Prevents recommendations and unwanted content navigation
 */

let player;
let videos = [];
let currentVideoIndex = 0;
let filteredVideos = [];

// YouTube IFrame API ready callback
function onYouTubeIframeAPIReady() {
    console.log('YouTube IFrame API ready');
    loadVideos();
}

/**
 * Load videos from backend API (Flask) or static JSON file (GitHub Pages)
 */
async function loadVideos() {
    try {
        // Try Flask API first (for local development)
        let response;
        try {
            response = await fetch('/api/videos');
            if (!response.ok) throw new Error('API not available');
        } catch (apiError) {
            // Fallback to static JSON (for GitHub Pages deployment)
            console.log('API not available, loading from static JSON');
            response = await fetch('videos.json');
        }

        videos = await response.json();
        filteredVideos = [...videos];

        if (videos.length > 0) {
            renderVideoList();
            initPlayer(videos[0].video_id);
        } else {
            document.getElementById('videoList').innerHTML =
                '<div class="loading">No videos available. Please run the main HappyTube script first.</div>';
        }
    } catch (error) {
        console.error('Error loading videos:', error);
        document.getElementById('videoList').innerHTML =
            '<div class="loading">Error loading videos. Make sure videos.json exists.</div>';
    }
}

/**
 * Initialize the YouTube player with restricted parameters
 */
function initPlayer(videoId) {
    player = new YT.Player('player', {
        height: '100%',
        width: '100%',
        videoId: videoId,
        playerVars: {
            // Disable related videos from other channels
            'rel': 0,
            // Minimal branding
            'modestbranding': 1,
            // Disable annotations
            'iv_load_policy': 3,
            // Disable keyboard controls (prevents space/enter from opening YouTube)
            'disablekb': 1,
            // Enable fullscreen
            'fs': 1,
            // Disable video info
            'showinfo': 0,
            // Auto-hide controls
            'autohide': 1,
            // Control bar color
            'color': 'white',
            // Disable logo
            'modestbranding': 1,
            // Playback origin
            'origin': window.location.origin
        },
        events: {
            'onReady': onPlayerReady,
            'onStateChange': onPlayerStateChange,
            'onError': onPlayerError
        }
    });
}

/**
 * Player ready callback
 */
function onPlayerReady(event) {
    console.log('Player ready');
    updateVideoInfo(currentVideoIndex);
}

/**
 * Player state change callback
 */
function onPlayerStateChange(event) {
    // If video ended and autoplay is enabled, play next
    if (event.data === YT.PlayerState.ENDED) {
        const autoplay = document.getElementById('autoplayNext').checked;
        if (autoplay) {
            playNext();
        }
    }
}

/**
 * Player error callback
 */
function onPlayerError(event) {
    console.error('Player error:', event.data);
    alert('Error playing video. It may be unavailable or restricted.');
}

/**
 * Render the video list in the sidebar
 */
function renderVideoList() {
    const videoListEl = document.getElementById('videoList');

    if (filteredVideos.length === 0) {
        videoListEl.innerHTML = '<div class="loading">No videos match your search</div>';
        return;
    }

    videoListEl.innerHTML = filteredVideos.map((video, index) => `
        <div class="video-item ${index === currentVideoIndex ? 'active' : ''}"
             data-index="${index}"
             onclick="playVideo(${index})">
            <div class="video-item-title">${escapeHtml(video.title)}</div>
            <div class="video-item-channel">${escapeHtml(video.channel_title)}</div>
        </div>
    `).join('');
}

/**
 * Play a specific video by index
 */
function playVideo(index) {
    if (index < 0 || index >= filteredVideos.length) return;

    currentVideoIndex = index;
    const video = filteredVideos[index];

    if (player && player.loadVideoById) {
        player.loadVideoById(video.video_id);
        updateVideoInfo(index);
        updateActiveItem();
    }
}

/**
 * Update video information display
 */
function updateVideoInfo(index) {
    const video = filteredVideos[index];
    document.getElementById('videoTitle').textContent = video.title;
    document.getElementById('channelTitle').textContent = video.channel_title;
    document.getElementById('videoDescription').textContent = video.description || 'No description available';

    // Update previous/next button states
    document.getElementById('prevBtn').disabled = index === 0;
    document.getElementById('nextBtn').disabled = index === filteredVideos.length - 1;
}

/**
 * Update active item in the playlist
 */
function updateActiveItem() {
    const items = document.querySelectorAll('.video-item');
    items.forEach((item, idx) => {
        if (idx === currentVideoIndex) {
            item.classList.add('active');
            item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } else {
            item.classList.remove('active');
        }
    });
}

/**
 * Play next video
 */
function playNext() {
    if (currentVideoIndex < filteredVideos.length - 1) {
        playVideo(currentVideoIndex + 1);
    }
}

/**
 * Play previous video
 */
function playPrevious() {
    if (currentVideoIndex > 0) {
        playVideo(currentVideoIndex - 1);
    }
}

/**
 * Filter videos based on search input
 */
function filterVideos(searchTerm) {
    const term = searchTerm.toLowerCase();

    if (!term) {
        filteredVideos = [...videos];
    } else {
        filteredVideos = videos.filter(video =>
            video.title.toLowerCase().includes(term) ||
            video.description.toLowerCase().includes(term) ||
            video.channel_title.toLowerCase().includes(term)
        );
    }

    // Reset to first video if current index is out of bounds
    if (currentVideoIndex >= filteredVideos.length) {
        currentVideoIndex = 0;
    }

    renderVideoList();

    if (filteredVideos.length > 0) {
        playVideo(currentVideoIndex);
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    // Search box
    const searchBox = document.getElementById('searchBox');
    let searchTimeout;
    searchBox.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            filterVideos(e.target.value);
        }, 300);
    });

    // Control buttons
    document.getElementById('nextBtn').addEventListener('click', playNext);
    document.getElementById('prevBtn').addEventListener('click', playPrevious);

    // Keyboard shortcuts (global)
    document.addEventListener('keydown', (e) => {
        // Don't interfere if user is typing in search box
        if (e.target.id === 'searchBox') return;

        switch(e.key) {
            case 'ArrowRight':
            case 'n':
                e.preventDefault();
                playNext();
                break;
            case 'ArrowLeft':
            case 'p':
                e.preventDefault();
                playPrevious();
                break;
        }
    });
});

// Prevent YouTube from capturing keyboard events
window.addEventListener('keydown', (e) => {
    // Allow only certain keys when player is focused
    if (e.target.tagName === 'IFRAME') {
        // Allow space, k (play/pause), m (mute), f (fullscreen)
        const allowedKeys = [' ', 'k', 'm', 'f'];
        if (!allowedKeys.includes(e.key)) {
            e.preventDefault();
        }
    }
});
