// Global State
let currentTab = 'dashboard';
let accountsData = [];
let postsData = [];
let uploadedVideo = null;
let pollInterval = null;

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    initApp();
    setupDropzone();
});

async function initApp() {
    await fetchAccounts();
    await fetchPosts();

    const handledTab = checkUrlParams();
    if (!handledTab) {
        renderOverview();
    }

    // Periodic poll for posts & queue updates
    pollInterval = setInterval(async () => {
        if (currentTab === 'queue' || currentTab === 'dashboard') {
            await fetchPosts();
            if (currentTab === 'dashboard') renderOverview();
            if (currentTab === 'queue') renderQueue();
        }
    }, 6000);
}

function checkUrlParams() {
    const url = new URL(window.location.href);
    const searchParams = url.searchParams;
    const hash = window.location.hash || '';

    let targetTab = searchParams.get('tab');
    if (!targetTab) {
        if (hash.includes('accounts')) targetTab = 'accounts';
        else if (hash.includes('queue')) targetTab = 'queue';
        else if (hash.includes('clipper')) targetTab = 'clipper';
        else if (hash.includes('create')) targetTab = 'create';
    }

    let connected = searchParams.get('connected');
    let error = searchParams.get('error');
    let warning = searchParams.get('warning');

    if (!error && hash.includes('error=')) {
        const match = hash.match(/error=([^&]+)/);
        if (match) error = decodeURIComponent(match[1]);
    }
    if (!connected && hash.includes('connected=')) {
        const match = hash.match(/connected=([^&]+)/);
        if (match) connected = decodeURIComponent(match[1]);
    }
    if (!warning && hash.includes('warning=')) {
        const match = hash.match(/warning=([^&]+)/);
        if (match) warning = decodeURIComponent(match[1]);
    }

    if (targetTab) {
        switchTab(targetTab);
    }

    if (error) {
        showToast(decodeURIComponent(error), 'error');
    } else if (warning) {
        showToast(decodeURIComponent(warning), 'warning');
    } else if (connected) {
        showToast(`Successfully connected ${connected.toUpperCase()} channel!`, 'success');
    }

    if (targetTab || connected || error || warning) {
        try {
            window.history.replaceState({}, document.title, window.location.pathname);
        } catch (_) {}
        return true;
    }
    return false;
}

// Navigation Tab Switcher
function switchTab(tabId) {
    currentTab = tabId;
    document.querySelectorAll('.tab-pane').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));

    const targetTab = document.getElementById(`tab-${tabId}`);
    const navBtn = document.getElementById(`nav-${tabId}`);
    if (targetTab) targetTab.classList.add('active');
    if (navBtn) navBtn.classList.add('active');

    const heading = document.getElementById('page-heading');
    const subheading = document.getElementById('page-subheading');

    if (tabId === 'dashboard') {
        heading.innerText = 'Dashboard Overview';
        subheading.innerText = 'Monitor publishing status, connected accounts, and queued tasks';
        renderOverview();
    } else if (tabId === 'accounts') {
        heading.innerText = 'Connected Accounts';
        subheading.innerText = 'Launch browser sessions to connect YouTube, TikTok, Instagram, and Facebook';
        renderAccounts();
    } else if (tabId === 'create') {
        heading.innerText = 'Create & Schedule';
        subheading.innerText = 'Upload your video and schedule publication across connected networks';
    } else if (tabId === 'clipper') {
        heading.innerText = 'AI Video Clipper';
        subheading.innerText = 'Cut long videos into vertical 9:16 Shorts/Reels and combine key highlights';
        populateClipperVideos();
    } else if (tabId === 'queue') {
        heading.innerText = 'Posts & Queue';
        subheading.innerText = 'Live status and direct links for all scheduled and published videos';
        renderQueue();
    }
}

function refreshCurrentView() {
    fetchAccounts().then(() => {
        fetchPosts().then(() => {
            if (currentTab === 'dashboard') renderOverview();
            if (currentTab === 'accounts') renderAccounts();
            if (currentTab === 'queue') renderQueue();
            showToast('Refreshed data successfully', 'success');
        });
    });
}

// API Calls: Accounts
async function fetchAccounts() {
    try {
        const res = await fetch('/api/accounts');
        accountsData = await res.json();
        updateAccountsCountBadge();
        return accountsData;
    } catch (e) {
        console.error('Failed to fetch accounts:', e);
    }
}

function updateAccountsCountBadge() {
    const connectedCount = accountsData.filter(a => a.is_connected).length;
    const badge = document.getElementById('sidebar-accounts-count');
    if (badge) badge.innerText = `${connectedCount}/${accountsData.length}`;
    const statConn = document.getElementById('stat-connected');
    if (statConn) statConn.innerText = `${connectedCount} / ${accountsData.length}`;
}

const PLATFORM_LOGIN_URLS = {
    youtube: "https://studio.youtube.com",
    tiktok: "https://www.tiktok.com/creator-center/upload",
    instagram: "https://www.instagram.com",
    facebook: "https://www.facebook.com"
};

async function importBrowserCookies(platform, closeBrowser = false) {
    showToast(`Importing your ${platform.toUpperCase()} login from your browser...`, 'info');
    try {
        const res = await fetch(`/api/accounts/${platform}/import-cookies?close_browser=${closeBrowser}`, { method: 'POST' });
        const data = await res.json();
        await fetchAccounts();
        renderAccounts();
        if (data.success) {
            showToast(`${platform.toUpperCase()} connected using your existing login!`, 'success');
        } else if (data.needs_browser_closed && !closeBrowser) {
            const names = (data.locked_browsers || ['Your browser']).join(', ');
            if (confirm(`${names} must be closed briefly to read your login.\n\nIt will close and reopen automatically with your tabs restored (this page will reload in the reopened browser: http://127.0.0.1:8000).\n\nContinue?`)) {
                return importBrowserCookies(platform, true);
            }
        } else {
            showToast(data.details || data.detail || 'Import failed', 'error');
        }
    } catch (e) {
        showToast(`Import error: ${e}`, 'error');
    }
}

async function openLoginWindow(platform) {
    try {
        await fetch(`/api/accounts/${platform}/login-window`, { method: 'POST' });
        showToast(`Login window opened. Sign in, close it, then click "Verify".`, 'info');
    } catch (e) {
        showToast(`Could not open login window: ${e}`, 'error');
    }
}

async function verifyBrowserSession(platform) {
    showToast(`Checking ${platform.toUpperCase()} session...`, 'info');
    try {
        const res = await fetch(`/api/accounts/${platform}/verify`, { method: 'POST' });
        const data = await res.json();
        await fetchAccounts();
        renderAccounts();
        if (data.success) {
            showToast(`${platform.toUpperCase()} connected!`, 'success');
        } else {
            showToast(data.details || 'Not logged in yet', 'error');
        }
    } catch (e) {
        showToast(`Verify error: ${e}`, 'error');
    }
}

async function disconnectAccount(platform) {
    if (!confirm(`Are you sure you want to disconnect ${platform}?`)) return;
    try {
        const res = await fetch(`/api/accounts/${platform}/disconnect`, { method: 'POST' });
        const data = await res.json();
        await fetchAccounts();
        renderAccounts();
        showToast(data.message, 'success');
    } catch (e) {
        showToast(`Failed to disconnect: ${e}`, 'error');
    }
}

// Official API Connect Handlers
async function connectYouTubeOfficial(forceReset = false) {
    if (!forceReset) {
        try {
            const res = await fetch('/api/accounts/youtube/auth-url');
            if (res.ok) {
                const data = await res.json();
                window.location.href = data.url; // Redirect to official Google sign-in
                return;
            }
        } catch (e) {}
    }

    // Prompt user for Google OAuth Client ID and Secret with clear guidance
    const clientId = prompt(
        "Enter your Google OAuth Client ID:\n(Looks like: 123456789-abcdef.apps.googleusercontent.com)\n*Note: Do NOT enter Project ID*", 
        ""
    );
    if (!clientId) return;

    const clientSecret = prompt(
        "Enter your Google OAuth Client Secret:\n(Looks like: GOCSPX-abc123def456...)\n*Note: Do NOT enter standard API key*", 
        ""
    );
    if (!clientSecret) return;

    try {
        const setupRes = await fetch('/api/accounts/youtube/setup-keys', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ client_id: clientId.trim(), client_secret: clientSecret.trim() })
        });
        if (setupRes.ok) {
            const authRes = await fetch('/api/accounts/youtube/auth-url');
            const data = await authRes.json();
            window.location.href = data.url;
        } else {
            showToast("Failed to save credentials", "error");
        }
    } catch (e) {
        showToast(`Setup error: ${e}`, 'error');
    }
}

async function resetYouTubeOfficial() {
    if (!confirm("Reset saved Google credentials and re-enter them?")) return;
    try {
        await fetch('/api/accounts/youtube/reset-keys', { method: 'POST' });
        await fetchAccounts();
        renderAccounts();
        showToast("Credentials cleared. Click 'Connect Google API' to enter your real keys.", "info");
        connectYouTubeOfficial(true);
    } catch (e) {
        showToast(`Reset error: ${e}`, 'error');
    }
}

async function connectTelegramOfficial() {
    const token = prompt("Enter your Telegram Bot Token (from @BotFather):", "");
    if (!token) return;
    const chatId = prompt("Enter your Telegram Channel Username or ID (e.g. @mychannel or -100123456789):", "@");
    if (!chatId) return;

    showToast("Connecting to Telegram...", "info");
    try {
        const res = await fetch('/api/accounts/telegram/setup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bot_token: token, chat_id: chatId })
        });
        const data = await res.json();
        if (res.ok) {
            await fetchAccounts();
            renderAccounts();
            showToast(`Telegram channel "${data.channel.title}" connected with ${data.channel.subscribers_count} subscribers!`, 'success');
        } else {
            showToast(`Error: ${data.detail || 'Connection failed'}`, 'error');
        }
    } catch (e) {
        showToast(`Telegram error: ${e}`, 'error');
    }
}

// Render Accounts Tab with Profile Analytics
function renderAccounts() {
    const grid = document.getElementById('accounts-cards-grid');
    if (!grid) return;

    const platformLabels = {
        youtube: { name: 'YouTube Channel', desc: 'Official Data API v3 • Uploads & Analytics' },
        telegram: { name: 'Telegram Channel', desc: 'Official Bot API • 2GB Video Uploads & Subscribers' },
        tiktok: { name: 'TikTok Creator', desc: 'Auto-publish to your TikTok profile & feed' },
        instagram: { name: 'Instagram Professional', desc: 'Direct Instagram Reels publishing' },
        facebook: { name: 'Facebook Page', desc: 'Reels and Page Video feed publishing' }
    };

    grid.innerHTML = accountsData.map(acc => {
        const info = platformLabels[acc.platform] || { name: acc.platform, desc: '' };
        const avatarHtml = acc.avatar_url 
            ? `<img src="${acc.avatar_url}" class="plat-avatar" alt="Avatar">`
            : `<div class="plat-icon ${acc.platform}">${acc.platform.substring(0, 2).toUpperCase()}</div>`;

        return `
            <div class="platform-card" id="card-${acc.platform}">
                <div class="plat-header">
                    <div class="plat-badge-group">
                        ${avatarHtml}
                        <div>
                            <div class="plat-name">${info.name}</div>
                            <div class="account-desc">${info.desc}</div>
                        </div>
                    </div>
                    <span class="status-pill ${acc.is_connected ? 'connected' : 'disconnected'}">
                        ${acc.is_connected ? '● CONNECTED' : '○ DISCONNECTED'}
                    </span>
                </div>
                <div class="plat-body">
                    <div class="account-user">${acc.is_connected ? acc.account_name : 'Not Connected'}</div>
                    
                    ${acc.is_connected ? `
                        <div class="profile-stats-bar">
                            <div class="p-stat">
                                <span class="p-stat-val">${Number(acc.followers_count || 0).toLocaleString()}</span>
                                <span class="p-stat-label">Subscribers</span>
                            </div>
                            <div class="p-stat">
                                <span class="p-stat-val">${isNaN(acc.views_count) ? acc.views_count : Number(acc.views_count || 0).toLocaleString()}</span>
                                <span class="p-stat-label">Views</span>
                            </div>
                            <div class="p-stat">
                                <span class="p-stat-val">${isNaN(acc.posts_count) ? acc.posts_count : Number(acc.posts_count || 0).toLocaleString()}</span>
                                <span class="p-stat-label">Videos</span>
                            </div>
                        </div>
                    ` : `
                        <div class="field-hint">Connect this account to view live followers, views, and auto-publish.</div>
                    `}
                </div>
                <div class="plat-actions">
                    ${acc.platform === 'youtube' && !acc.is_connected ? `
                        <button class="btn btn-primary" onclick="connectYouTubeOfficial()" style="background: linear-gradient(135deg, #ef4444, #991b1b);">
                            <span>🔴 Connect Google API</span>
                        </button>
                        <button class="btn btn-secondary" onclick="resetYouTubeOfficial()" title="Re-enter Client ID and Secret">
                            <span>⚙️ Reset Keys</span>
                        </button>
                    ` : ''}

                    ${acc.platform === 'telegram' && !acc.is_connected ? `
                        <button class="btn btn-primary" onclick="connectTelegramOfficial()" style="background: linear-gradient(135deg, #229ed9, #0088cc);">
                            <span>✈️ Connect Bot & Channel</span>
                        </button>
                    ` : ''}

                    ${acc.platform !== 'youtube' && acc.platform !== 'telegram' && !acc.is_connected ? `
                        <button class="btn btn-primary" onclick="importBrowserCookies('${acc.platform}')" title="Use the account you are already logged into in Brave/Chrome/Edge">
                            <span>🍪 Use My Browser Login</span>
                        </button>
                        <button class="btn btn-secondary" onclick="openLoginWindow('${acc.platform}')" title="Log in once in a separate window; it is remembered">
                            <span>🔑 Login Window</span>
                        </button>
                        <button class="btn btn-secondary" onclick="verifyBrowserSession('${acc.platform}')" style="color: var(--accent-emerald); border-color: rgba(16, 185, 129, 0.4);">
                            <span>✓ Verify</span>
                        </button>
                    ` : ''}

                    ${acc.is_connected ? `
                        <button class="btn btn-secondary" onclick="${['tiktok','instagram','facebook'].includes(acc.platform) ? `verifyBrowserSession('${acc.platform}')` : 'refreshCurrentView()'}">
                            <span>🔄 Sync Stats</span>
                        </button>
                        <button class="btn btn-secondary" onclick="disconnectAccount('${acc.platform}')" style="color: var(--accent-rose);">
                            <span>Disconnect</span>
                        </button>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
}

// API Calls: Posts
async function fetchPosts() {
    try {
        const res = await fetch('/api/posts');
        postsData = await res.json();
        updatePostsStats();
        return postsData;
    } catch (e) {
        console.error('Failed to fetch posts:', e);
    }
}

function updatePostsStats() {
    const scheduledCount = postsData.filter(p => p.status === 'scheduled').length;
    const publishedCount = postsData.filter(p => p.status === 'completed' || p.status === 'partial').length;
    
    const countBadge = document.getElementById('sidebar-posts-count');
    if (countBadge) countBadge.innerText = postsData.length;

    const schedEl = document.getElementById('stat-scheduled');
    if (schedEl) schedEl.innerText = scheduledCount;

    const pubEl = document.getElementById('stat-published');
    if (pubEl) pubEl.innerText = publishedCount;
}

// Render Overview Tab
function renderOverview() {
    const postsContainer = document.getElementById('overview-posts-container');
    const platformsList = document.getElementById('overview-platforms-list');

    // Recent posts
    if (postsContainer) {
        if (postsData.length === 0) {
            postsContainer.innerHTML = `<div class="empty-state"><p>No posts created yet. Click "New Post" to schedule your first upload!</p></div>`;
        } else {
            postsContainer.innerHTML = postsData.slice(0, 5).map(p => renderPostCardHtml(p)).join('');
        }
    }

    // Platform status list
    if (platformsList) {
        platformsList.innerHTML = accountsData.map(acc => `
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 0.75rem 0; border-bottom: 1px solid var(--border-color);">
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    <span style="font-weight: 700; text-transform: capitalize;">${acc.platform}</span>
                </div>
                <span class="status-pill ${acc.is_connected ? 'connected' : 'disconnected'}">
                    ${acc.is_connected ? 'READY' : 'OFFLINE'}
                </span>
            </div>
        `).join('');
    }
}

// Render Queue Tab
function renderQueue() {
    const container = document.getElementById('queue-posts-container');
    if (!container) return;

    if (postsData.length === 0) {
        container.innerHTML = `<div class="empty-state"><p>Queue is empty. Use the "Create & Schedule" tab to upload a video.</p></div>`;
    } else {
        container.innerHTML = postsData.map(p => renderPostCardHtml(p)).join('');
    }
}

function renderPostCardHtml(post) {
    const dateFormatted = post.scheduled_at 
        ? new Date(post.scheduled_at).toLocaleString() 
        : new Date(post.created_at).toLocaleString();

    const platformPills = (post.platform_statuses || []).map(ps => {
        let tagClass = ps.status;
        let urlLink = ps.external_url ? `<a href="${ps.external_url}" target="_blank" style="color: inherit; text-decoration: underline;">🔗</a>` : '';
        return `<span class="plat-tag ${tagClass}" title="${ps.error_message || ps.status}">${ps.platform}: ${ps.status} ${urlLink}</span>`;
    }).join('');

    return `
        <div class="post-card" id="post-row-${post.id}">
            <div class="post-meta-col">
                <span class="post-card-title">${escapeHtml(post.title)}</span>
                <span class="post-card-desc">${escapeHtml(post.description || 'No description')}</span>
                ${post.tags ? `<span class="post-card-tags">${escapeHtml(post.tags)}</span>` : ''}
                <span class="field-hint">Time: ${dateFormatted} • Status: <strong style="text-transform: capitalize;">${post.status}</strong></span>
            </div>
            <div class="post-status-col">
                <div class="platform-pill-list">
                    ${platformPills}
                </div>
                <div class="post-action-btns">
                    ${post.status !== 'completed' && post.status !== 'publishing' ? `
                        <button class="btn btn-secondary" onclick="publishNowPost(${post.id})" title="Publish immediately">
                            <span>🚀 Post Now</span>
                        </button>
                    ` : ''}
                    <button class="btn btn-secondary" onclick="deletePost(${post.id})" style="color: var(--accent-rose);" title="Delete">
                        <span>✕</span>
                    </button>
                </div>
            </div>
        </div>
    `;
}

// File Drag & Drop & Upload Handling
function setupDropzone() {
    const dropzone = document.getElementById('dropzone');
    if (!dropzone) return;

    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.style.borderColor = 'var(--accent-primary)';
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.style.borderColor = 'rgba(255, 255, 255, 0.15)';
        }, false);
    });

    dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            uploadFile(files[0]);
        }
    });
}

function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
        uploadFile(files[0]);
    }
}

function uploadFile(file) {
    const prompt = document.getElementById('dropzone-prompt');
    const progress = document.getElementById('dropzone-progress');
    const selected = document.getElementById('dropzone-selected');
    const fill = document.getElementById('upload-progress-fill');
    const text = document.getElementById('upload-progress-text');

    prompt.style.display = 'none';
    progress.style.display = 'block';
    selected.style.display = 'none';

    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/posts/upload-video', true);

    xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) {
            const percent = Math.round((e.loaded / e.total) * 100);
            fill.style.width = percent + '%';
            text.innerText = `Uploading video... ${percent}%`;
        }
    };

    xhr.onload = () => {
        if (xhr.status === 200) {
            const res = JSON.parse(xhr.responseText);
            uploadedVideo = res;
            progress.style.display = 'none';
            selected.style.display = 'flex';
            document.getElementById('selected-video-filename').innerText = file.name;
            document.getElementById('selected-video-filesize').innerText = (file.size / (1024 * 1024)).toFixed(1) + ' MB';

            // Show video preview
            const previewCard = document.getElementById('video-preview-card');
            const previewPlayer = document.getElementById('video-preview-player');
            previewPlayer.src = `/videos/${res.filename}`;
            previewCard.style.display = 'block';

            showToast('Video uploaded and ready!', 'success');
        } else {
            prompt.style.display = 'block';
            progress.style.display = 'none';
            showToast('Video upload failed', 'error');
        }
    };

    xhr.onerror = () => {
        prompt.style.display = 'block';
        progress.style.display = 'none';
        showToast('Network error during video upload', 'error');
    };

    xhr.send(formData);
}

function clearSelectedVideo(e) {
    e.stopPropagation();
    uploadedVideo = null;
    document.getElementById('dropzone-prompt').style.display = 'block';
    document.getElementById('dropzone-progress').style.display = 'none';
    document.getElementById('dropzone-selected').style.display = 'none';
    document.getElementById('video-preview-card').style.display = 'none';
    document.getElementById('video-preview-player').src = '';
    document.getElementById('video-file-input').value = '';
}

function toggleScheduleDate(show) {
    const dtGroup = document.getElementById('datetime-picker-group');
    const submitBtnText = document.getElementById('submit-btn-text');
    if (show) {
        dtGroup.style.display = 'block';
        submitBtnText.innerText = '📅 Schedule Auto-Publish';
        // Set default date to 1 hour from now
        const now = new Date();
        now.setHours(now.getHours() + 1);
        now.setMinutes(0);
        document.getElementById('post-scheduled-at').value = now.toISOString().slice(0, 16);
    } else {
        dtGroup.style.display = 'none';
        submitBtnText.innerText = '🚀 Publish to Platforms';
    }
}

async function submitPost() {
    if (!uploadedVideo) {
        showToast('Please upload a video file first', 'error');
        return;
    }

    const title = document.getElementById('post-title').value.trim();
    if (!title) {
        showToast('Please enter a video title', 'error');
        return;
    }

    const description = document.getElementById('post-description').value.trim();
    const tags = document.getElementById('post-tags').value.trim();

    // Destination platforms
    const platforms = [];
    if (document.getElementById('dest-youtube')?.checked) platforms.push('youtube');
    if (document.getElementById('dest-tiktok')?.checked) platforms.push('tiktok');
    if (document.getElementById('dest-instagram')?.checked) platforms.push('instagram');
    if (document.getElementById('dest-facebook')?.checked) platforms.push('facebook');
    if (document.getElementById('dest-telegram')?.checked) platforms.push('telegram');

    if (platforms.length === 0) {
        showToast('Please select at least one platform', 'error');
        return;
    }

    // Schedule mode
    const scheduleMode = document.querySelector('input[name="schedule-mode"]:checked').value;
    let scheduledAt = null;
    if (scheduleMode === 'later') {
        const dtVal = document.getElementById('post-scheduled-at').value;
        if (!dtVal) {
            showToast('Please select a schedule time', 'error');
            return;
        }
        scheduledAt = new Date(dtVal).toISOString();
    }

    const submitBtn = document.getElementById('btn-submit-post');
    submitBtn.disabled = true;

    try {
        const res = await fetch('/api/posts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title,
                description,
                tags,
                video_filename: uploadedVideo.filename,
                platforms,
                scheduled_at: scheduledAt
            })
        });

        if (res.ok) {
            const createdPost = await res.json();

            // If publish now mode was selected, trigger publish immediately
            if (scheduleMode === 'now') {
                await fetch(`/api/posts/${createdPost.id}/publish-now`, { method: 'POST' });
                showToast('Publishing initiated across selected platforms!', 'success');
            } else {
                showToast('Post scheduled successfully!', 'success');
            }

            // Reset form
            document.getElementById('post-title').value = '';
            document.getElementById('post-description').value = '';
            document.getElementById('post-tags').value = '';
            clearSelectedVideo({ stopPropagation: () => {} });

            await fetchPosts();
            switchTab('queue');
        } else {
            const err = await res.json();
            showToast(`Error: ${err.detail || 'Could not create post'}`, 'error');
        }
    } catch (e) {
        showToast(`Failed to create post: ${e}`, 'error');
    } finally {
        submitBtn.disabled = false;
    }
}

async function publishNowPost(postId) {
    try {
        const res = await fetch(`/api/posts/${postId}/publish-now`, { method: 'POST' });
        const data = await res.json();
        showToast(data.message, 'info');
        await fetchPosts();
        renderQueue();
    } catch (e) {
        showToast(`Error: ${e}`, 'error');
    }
}

async function deletePost(postId) {
    if (!confirm('Are you sure you want to delete this post?')) return;
    try {
        const res = await fetch(`/api/posts/${postId}`, { method: 'DELETE' });
        const data = await res.json();
        showToast(data.message, 'success');
        await fetchPosts();
        renderQueue();
    } catch (e) {
        showToast(`Error: ${e}`, 'error');
    }
}

// Toast System
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerText = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function escapeHtml(text) {
    if (!text) return '';
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// AI Clipper Functions
function populateClipperVideos() {
    const select = document.getElementById('clipper-video-select');
    if (!select) return;

    // Collect unique videos from posts
    const videoFilenames = new Set();
    postsData.forEach(p => {
        if (p.video_filename) videoFilenames.add(p.video_filename);
    });

    select.innerHTML = '<option value="">-- Select video file --</option>' + 
        Array.from(videoFilenames).map(fn => `<option value="${fn}">${fn}</option>`).join('');
}

async function generateShortClip() {
    const videoFilename = document.getElementById('clipper-video-select').value;
    if (!videoFilename) {
        showToast('Please select a video file first', 'error');
        return;
    }

    const startSec = parseFloat(document.getElementById('clip-start-sec').value) || 0;
    const endSec = parseFloat(document.getElementById('clip-end-sec').value) || 30;
    if (endSec <= startSec) {
        showToast('End time must be greater than start time', 'error');
        return;
    }

    let title = document.getElementById('clip-title').value.trim();
    if (!title) {
        title = `Short Clip (${Math.round(startSec)}s - ${Math.round(endSec)}s)`;
    }
    const tags = document.getElementById('clip-desc').value.trim();

    const btn = document.getElementById('btn-run-clipper');
    btn.disabled = true;
    btn.innerText = '⏳ Processing 9:16 Video (Cutting & Framing)...';
    showToast('Starting video cutting and 9:16 vertical re-framing...', 'info');

    try {
        const res = await fetch('/api/clipper/cut-short', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                video_filename: videoFilename,
                start_sec: startSec,
                end_sec: endSec,
                title: title,
                tags: tags
            })
        });

        const data = await res.json();
        if (res.ok) {
            showToast(`Short created! Added to queue as post #${data.post_id}`, 'success');
            await fetchPosts();
            switchTab('queue');
        } else {
            showToast(`Error: ${data.detail || 'Failed to process clip'}`, 'error');
        }
    } catch (e) {
        showToast(`Processing error: ${e}`, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>⚡ Cut & Convert to 9:16 Vertical Short</span>';
    }
}

