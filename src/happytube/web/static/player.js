/**
 * HappyTube player — one video at a time, full width, next plays on its own.
 * The list lives in a bottom sheet, out of the way until asked for.
 */

const LAST_KEY = 'happytube:last';
const MAX_SKIPS = 5; // stop auto-skipping after this many failed videos in a row

let player;
let videos = [];
let current = 0;
let failedInRow = 0;

const $ = (id) => document.getElementById(id);

let apiReady = false;

// Called by the YouTube script; the list may or may not be loaded yet.
function onYouTubeIframeAPIReady() {
    apiReady = true;
    createPlayer();
}

/** videos.json sits next to this page: live under /player/, built on Pages. */
async function loadVideos() {
    try {
        const response = await fetch('videos.json', { cache: 'no-store' });
        if (!response.ok) throw new Error(`videos.json: HTTP ${response.status}`);
        videos = await response.json();
    } catch (error) {
        console.error('Error loading videos:', error);
        showMessage('Videos could not be loaded. Please try again later.');
        return;
    }
    if (videos.length === 0) {
        showMessage('No videos yet.');
        return;
    }
    const last = localStorage.getItem(LAST_KEY);
    current = Math.max(0, videos.findIndex((v) => v.video_id === last));
    showMessage('');
    renderList();
    showInfo();
    createPlayer();
}

/** Needs both the YouTube script and the list; runs once. */
function createPlayer() {
    if (player || !apiReady || videos.length === 0) return;
    player = new YT.Player('player', {
        width: '100%',
        height: '100%',
        videoId: videos[current].video_id,
        playerVars: {
            rel: 0,             // related videos only from the same channel
            iv_load_policy: 3,  // no annotations
            playsinline: 1,     // iOS: play in the page, not forced fullscreen
            fs: 1,
            disablekb: 1,
            origin: window.location.origin,
        },
        events: { onStateChange, onError },
    });
}

function onStateChange(event) {
    if (event.data === YT.PlayerState.PLAYING) failedInRow = 0;
    if (event.data === YT.PlayerState.ENDED) next();
}

/** An unplayable video (removed, embedding off) is skipped quietly. */
function onError(event) {
    console.error('Player error:', event.data, videos[current]?.video_id);
    failedInRow += 1;
    if (failedInRow >= MAX_SKIPS) {
        showMessage('These videos cannot be played right now.');
        return;
    }
    setTimeout(next, 800);
}

function play(index) {
    current = (index + videos.length) % videos.length;
    localStorage.setItem(LAST_KEY, videos[current].video_id);
    player?.loadVideoById?.(videos[current].video_id);
    showInfo();
    markCurrent();
}

const next = () => play(current + 1);
const previous = () => play(current - 1);

function showInfo() {
    const video = videos[current];
    $('title').textContent = video.title;
    $('channel').textContent = video.channel_name;
    document.title = `${video.title} · HappyTube`;
}

function showMessage(text) {
    $('message').textContent = text;
}

function formatDuration(seconds) {
    if (!seconds) return '';
    const m = Math.floor(seconds / 60);
    const s = String(seconds % 60).padStart(2, '0');
    return m >= 60 ? `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}:${s}` : `${m}:${s}`;
}

/** Built with DOM nodes, never innerHTML: titles come from YouTube. */
function renderList() {
    const list = $('list');
    list.replaceChildren(...videos.map((video, index) => {
        const img = document.createElement('img');
        img.src = `https://i.ytimg.com/vi/${encodeURIComponent(video.video_id)}/mqdefault.jpg`;
        img.alt = '';
        img.loading = 'lazy';

        const title = document.createElement('span');
        title.className = 'item-title';
        title.textContent = video.title;

        const meta = document.createElement('span');
        meta.className = 'item-meta';
        meta.textContent = [video.channel_name, formatDuration(video.duration_s)]
            .filter(Boolean).join(' · ');

        const text = document.createElement('span');
        text.className = 'item-text';
        text.append(title, meta);

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'item';
        button.append(img, text);
        button.addEventListener('click', () => {
            play(index);
            $('sheet').close();
        });

        const li = document.createElement('li');
        li.append(button);
        return li;
    }));
    markCurrent();
}

function markCurrent() {
    $('list').querySelectorAll('.item').forEach((item, index) => {
        item.classList.toggle('current', index === current);
    });
}

/**
 * YouTube's fullscreen button makes the iframe fullscreen; turn the phone to
 * landscape with it, and let it rotate freely again on exit. Android browsers
 * only — iOS has no orientation lock (its native player rotates on its own).
 */
function onFullscreenChange() {
    const orientation = screen.orientation;
    if (!orientation?.lock) return;
    if (document.fullscreenElement || document.webkitFullscreenElement) {
        orientation.lock('landscape').catch(() => {}); // desktop: not supported
    } else {
        orientation.unlock?.();
    }
}

function openList() {
    if (videos.length === 0) return;
    $('sheet').showModal();
    $('list').querySelectorAll('.item')[current]?.scrollIntoView({ block: 'center' });
}

document.addEventListener('DOMContentLoaded', () => {
    loadVideos();
    document.addEventListener('fullscreenchange', onFullscreenChange);
    document.addEventListener('webkitfullscreenchange', onFullscreenChange);
    const sheet = $('sheet');
    $('listBtn').addEventListener('click', openList);
    $('cornerBtn').addEventListener('click', openList);
    $('closeBtn').addEventListener('click', () => sheet.close());
    $('nextBtn').addEventListener('click', () => videos.length && next());
    // Tap on the dimmed backdrop closes the sheet.
    sheet.addEventListener('click', (event) => {
        if (event.target === sheet) sheet.close();
    });

    document.addEventListener('keydown', (event) => {
        if (sheet.open || videos.length === 0) return;
        if (event.key === 'ArrowRight' || event.key === 'n') next();
        if (event.key === 'ArrowLeft' || event.key === 'p') previous();
        if (event.key === 'l') openList();
    });
});
