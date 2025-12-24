/**
 * Data Guardian - Main Application JavaScript
 * Extracted and cleaned from inline script
 */

// Wrap everything in IIFE to avoid global pollution
(function() {
    'use strict';
    
    console.log('🚀 Loading Data Guardian Application...');
    
        // Global variables
        let map = null;
        let markerClusterGroup = null;
        let albums = [];
        let selectedPhotos = new Set(); // Track selected photo media IDs
        let selectedVideos = new Set(); // Track selected video media IDs
        
        // User permissions (loaded from page data)
        let userPermissions = {
            canUpload: false,
            canEdit: false,
            canDelete: false,
            canCreateAlbum: false,
            canAdmin: false,
            userRole: 'guest'
        };
        
        // Load permissions from page
        function loadUserPermissions() {
            const permEl = document.getElementById('userPermissionsData');
            if (permEl) {
                try {
                    const data = JSON.parse(permEl.textContent);
                    Object.assign(userPermissions, data);
                } catch (e) {
                    console.warn('Could not load user permissions:', e);
                }
            }
        }

        // Initialize on load
        document.addEventListener('DOMContentLoaded', function() {
            loadUserPermissions();
            initializeMap();
            loadAlbums();
            loadMapData();
            setupUploadZone();
            setupEnterKeySearch();
        });

        // Initialize Leaflet map
        function initializeMap() {
            map = L.map('map').setView([37.7749, -122.4194], 4);
            
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }).addTo(map);
            
            markerClusterGroup = L.markerClusterGroup({
                maxClusterRadius: 50,
                spiderfyOnMaxZoom: true,
                showCoverageOnHover: false
            });
            
            map.addLayer(markerClusterGroup);
        }

        // Load albums
        async function loadAlbums() {
            try {
                const response = await fetch('/list_unified_albums');
                const data = await response.json();
                
                albums = data.albums || [];
                
                // Update album filter dropdown
                const albumFilter = document.getElementById('albumFilter');
                albumFilter.innerHTML = '<option value="">All Albums</option>';
                albums.forEach(album => {
                    const option = document.createElement('option');
                    option.value = album.album_name;
                    option.textContent = `${album.album_name} (${album.total_items || 0} items)`;
                    albumFilter.appendChild(option);
                });
                
                // Display albums grid
                displayAlbums(albums);
            } catch (error) {
                console.error('Error loading albums:', error);
                document.getElementById('albumsContainer').innerHTML = `
                    <div class="status-message status-error">
                        <i class="bi bi-exclamation-triangle me-2"></i>
                        Failed to load albums: ${error.message}
                    </div>
                `;
            }
        }

        // Display albums in grid
        function displayAlbums(albums) {
            const container = document.getElementById('albumsContainer');
            
            if (!albums || albums.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <i class="bi bi-folder2"></i>
                        <h4>No Albums Yet</h4>
                        <p class="text-muted">Upload media to create your first album</p>
                    </div>
                `;
                return;
            }
            
            const html = `
                <div class="album-grid">
                    ${albums.map(album => {
                        const escapedName = album.album_name.replace(/'/g, '&apos;').replace(/"/g, '&quot;');
                        return `
                        <div class="album-card" data-album-name="${escapedName}">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <div class="d-flex align-items-center album-open-btn" style="cursor: pointer; flex: 1;">
                                    <i class="bi bi-folder2-open text-primary" style="font-size: 2rem;"></i>
                                </div>
                                ${userPermissions.canDelete ? `
                                <button class="btn btn-sm btn-outline-danger album-delete-btn" 
                                        title="Delete Album">
                                    <i class="bi bi-trash"></i>
                                </button>
                                ` : ''}
                            </div>
                            <div class="album-name album-open-btn" style="cursor: pointer;">${album.album_name}</div>
                            <div class="album-stats">
                                <i class="bi bi-image me-1"></i>${album.photo_count || 0} photos
                                <span class="mx-1">•</span>
                                <i class="bi bi-camera-video me-1"></i>${album.video_count || 0} videos
                            </div>
                            <div class="album-stats mt-2">
                                <small class="text-muted">
                                    ${album.total_items || 0} total items
                                </small>
                            </div>
                        </div>
                        `;
                    }).join('')}
                </div>
            `;
            
            container.innerHTML = html;
            
            console.log(`📁 Displayed ${albums.length} albums, attaching click listeners...`);
            
            // Add event delegation for album clicks
            container.querySelectorAll('.album-open-btn').forEach(btn => {
                btn.addEventListener('click', function() {
                    const albumCard = this.closest('.album-card');
                    const albumName = albumCard.dataset.albumName.replace(/&apos;/g, "'").replace(/&quot;/g, '"');
                    console.log(`🖱️ Album clicked: ${albumName}`);
                    searchAlbum(albumName);
                });
            });
            
            // Add event delegation for delete buttons
            container.querySelectorAll('.album-delete-btn').forEach(btn => {
                btn.addEventListener('click', function(e) {
                    e.stopPropagation();
                    const albumCard = this.closest('.album-card');
                    const albumName = albumCard.dataset.albumName.replace(/&apos;/g, "'").replace(/&quot;/g, '"');
                    deleteAlbum(albumName);
                });
            });
        }

        // Search album - view album contents
        async function searchAlbum(albumName) {
            console.log(`🔍 searchAlbum called for: ${albumName}`);
            document.getElementById('albumFilter').value = albumName;
            document.getElementById('searchQuery').value = '';
            
            // Switch to results tab
            const resultsTab = new bootstrap.Tab(document.querySelector('[href="#results-tab"]'));
            resultsTab.show();
            
            showStatus(`Loading album: ${albumName}...`, 'info');
            
            try {
                const response = await fetch(`/album_contents/${encodeURIComponent(albumName)}`);
                const data = await response.json();
                
                if (data.error) {
                    showStatus(data.error, 'error');
                    return;
                }
                
                displayResults(data.results || []);
                showStatus(`${data.count || 0} items in ${albumName}`, 'success');
            } catch (error) {
                console.error('Album load error:', error);
                showStatus(`Failed to load album: ${error.message}`, 'error');
            }
        }

        // Search by face/person name
        async function searchByFace() {
            const faceName = document.getElementById('faceSearchQuery').value.trim();
            
            if (!faceName) {
                showStatus('Please enter a person name to search', 'error');
                return;
            }
            
            showStatus(`🔍 Searching for ${faceName} (including similar faces)...`, 'info');
            
            try {
                console.log('Sending face search request for:', faceName);
                
                const response = await fetch('/search/faces', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        face_name: faceName,
                        include_similar: true,
                        similarity_threshold: 0.6
                    })
                });
                
                console.log('Response status:', response.status, response.statusText);
                
                if (!response.ok) {
                    const errorText = await response.text();
                    console.error('Server error response:', errorText);
                    showStatus(`Server error: ${response.status} - ${errorText}`, 'error');
                    return;
                }
                
                const data = await response.json();
                console.log('Face search response data:', data);
                
                if (data.error) {
                    console.error('API error:', data.error);
                    showStatus(data.error, 'error');
                    return;
                }
                
                // Validate data structure
                if (!data.results || !Array.isArray(data.results)) {
                    console.error('Invalid response format - no results array:', data);
                    showStatus('Invalid response from server', 'error');
                    return;
                }
                
                console.log(`Processing ${data.results.length} results...`);
                
                // Convert face search results to standard display format
                const results = data.results.map((item, index) => {
                    console.log(`Result ${index}:`, item);
                    return {
                        media_id: item.media_id,
                        file_name: item.file_name,
                        album_name: item.album_name,
                        file_type: item.file_type || 'photo',  // Default to photo
                        file_path: item.file_path,
                        upload_date: item.upload_date,
                        file_size: item.file_size,
                        score: 1.0,  // Face match = 100% relevance
                        segment_start: null,  // Not applicable for photos
                        segment_end: null,
                        face_matches: item.faces  // Store face info for display
                    };
                });
                
                console.log('Mapped results:', results);
                console.log('Calling displayResults with', results.length, 'items');
                
                displayResults(results);
                
                // Enhanced status message with breakdown
                const breakdown = data.breakdown || {};
                const manualCount = breakdown.manually_tagged || 0;
                const similarCount = breakdown.similar_faces || 0;
                const autoDetectedCount = breakdown.auto_detected || 0;
                
                let statusMsg = `Found ${data.total} photos with ${faceName}`;
                const parts = [];
                if (manualCount > 0) parts.push(`${manualCount} tagged`);
                if (similarCount > 0) parts.push(`${similarCount} similar`);
                if (autoDetectedCount > 0) parts.push(`${autoDetectedCount} auto-detected`);
                
                if (parts.length > 0) {
                    statusMsg += ` (${parts.join(' + ')})`;
                }
                
                showStatus(statusMsg, 'success');
                
                // Log for debugging
                console.log('Face search complete:', {
                    total: data.total,
                    manually_tagged: manualCount,
                    similar_faces: similarCount,
                    auto_detected: autoDetectedCount,
                    results_displayed: results.length
                });
                
            } catch (error) {
                console.error('Face search error:', error);
                console.error('Error stack:', error.stack);
                showStatus(`Face search failed: ${error.message}`, 'error');
            }
        }

        // Allow Enter key to trigger face search
        document.addEventListener('DOMContentLoaded', function() {
            const faceSearchInput = document.getElementById('faceSearchQuery');
            if (faceSearchInput) {
                faceSearchInput.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') {
                        searchByFace();
                    }
                });
            }
        });

        // Perform search
        async function performSearch() {
            const query = document.getElementById('searchQuery').value.trim();
            const albumFilter = document.getElementById('albumFilter').value;
            
            if (!query && !albumFilter) {
                showStatus('Please enter a search query or select an album', 'error');
                return;
            }
            
            showStatus('Searching...', 'info');
            
            try {
                const response = await fetch('/search_unified', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        query: query || '*',
                        album_filter: albumFilter || null,
                        limit: 50
                    })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    showStatus(data.error, 'error');
                    return;
                }
                
                displayResults(data.results || []);
                showStatus(`Found ${data.count || 0} results`, 'success');
            } catch (error) {
                console.error('Search error:', error);
                showStatus(`Search failed: ${error.message}`, 'error');
            }
        }

        // Display search results
        function displayResults(results) {
            console.log('📋 displayResults called with', results.length, 'results');
            console.log('First result:', results[0]);
            
            const container = document.getElementById('resultsContainer');
            
            console.log(`📸 Displaying ${results.length} results`);
            
            if (!results || results.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <i class="bi bi-inbox"></i>
                        <h4>No Results Found</h4>
                        <p class="text-muted">Try a different search query or check another album</p>
                    </div>
                `;
                return;
            }
            
            const html = `
                <div class="results-grid">
                    ${results.map(result => {
                        const isVideo = result.file_type === 'video';
                        const icon = isVideo ? 'camera-video-fill' : 'image-fill';
                        const score = Math.round((result.score || 0) * 100);
                        const mediaId = result.media_id;
                        
                        // Debug: Check if ai_tags exists
                        if (result.ai_tags) {
                            console.log('Result has ai_tags:', result.ai_tags);
                        }
                        
                        // Format timestamp for videos
                        const hasSegment = isVideo && result.segment_start !== null && result.segment_start !== undefined;
                        const segmentInfo = hasSegment ? formatTimestamp(result.segment_start, result.segment_end) : '';
                        
                        return `
                            <div class="result-card" data-media-id="${mediaId}" data-file-type="${result.file_type}" data-segment-start="${result.segment_start || ''}" data-segment-end="${result.segment_end || ''}">
                                <div class="position-relative">
                                    <div class="position-absolute top-0 start-0 m-2" style="z-index: 10;">
                                        <input class="form-check-input ${isVideo ? 'video-select-checkbox' : 'photo-select-checkbox'}" 
                                               type="checkbox" 
                                               data-media-id="${mediaId}" 
                                               style="width: 20px; height: 20px; cursor: pointer;">
                                    </div>
                                    <div class="result-thumbnail d-flex align-items-center justify-content-center" id="thumb-${mediaId}-${result.segment_start || 0}">
                                        <div class="spinner-border spinner-border-sm text-primary" role="status">
                                            <span class="visually-hidden">Loading...</span>
                                        </div>
                                    </div>
                                    ${hasSegment ? `
                                        <span class="position-absolute bottom-0 start-0 m-2 badge bg-dark" style="opacity: 0.9;">
                                            <i class="bi bi-clock me-1"></i>${segmentInfo}
                                        </span>
                                    ` : ''}
                                    ${userPermissions.canDelete ? `
                                    <button class="btn btn-sm btn-danger position-absolute top-0 end-0 m-2 delete-media-btn" 
                                            title="Delete this media"
                                            style="opacity: 0.9; padding: 0.25rem 0.5rem;">
                                        <i class="bi bi-trash"></i>
                                    </button>
                                    ` : ''}
                                </div>
                                <div class="result-info">
                                    <div class="d-flex justify-content-between align-items-start mb-2">
                                        <div class="result-filename">${result.file_name}</div>
                                        ${score > 0 ? `<span class="score-badge">${score}%</span>` : ''}
                                    </div>
                                    <div class="result-meta">
                                        <div><i class="bi bi-folder2 me-1"></i>${result.album_name}</div>
                                        <div class="mt-1">
                                            <i class="bi bi-${isVideo ? 'camera-video' : 'image'} me-1"></i>
                                            ${isVideo ? (hasSegment ? 'Video Segment' : 'Video') : 'Photo'}
                                        </div>
                                    </div>
                                    ${result.ai_tags && result.ai_tags.trim() !== '' ? (() => {
                                        // Parse AI tags to separate title and hashtags
                                        const tags = result.ai_tags;
                                        const titleMatch = tags.match(/TITLE:\s*([^,\n]+)/i);
                                        const hashtagMatch = tags.match(/HASHTAGS?:\s*([^\n]+)/i);
                                        
                                        const title = titleMatch ? titleMatch[1].trim() : null;
                                        const hashtags = hashtagMatch ? hashtagMatch[1].trim() : null;
                                        
                                        return `
                                        <div class="mt-2">
                                            ${title ? `
                                            <div class="mb-1">
                                                <span class="badge bg-primary" style="font-size: 0.85em; font-weight: 500;">
                                                    <i class="bi bi-quote me-1"></i>${title}
                                                </span>
                                            </div>
                                            ` : ''}
                                            ${hashtags ? `
                                            <div style="font-size: 0.75em; color: #6c757d;">
                                                <i class="bi bi-hash" style="font-size: 0.9em;"></i>${hashtags}
                                            </div>
                                            ` : ''}
                                            ${!title && !hashtags ? `
                                            <span class="badge bg-info d-inline-block" 
                                                  style="max-width: 100%; white-space: normal; text-align: left; font-size: 0.85em;">
                                                <i class="bi bi-tags-fill me-1"></i>${tags}
                                            </span>
                                            ` : ''}
                                        </div>
                                        `;
                                    })() : ''}
                                    <div class="mt-2 d-flex gap-1 flex-wrap">
                                        <button class="btn btn-sm btn-outline-primary find-similar-btn" 
                                                title="Find similar ${isVideo ? 'videos' : 'photos'}">
                                            <i class="bi bi-collection"></i> Similar
                                        </button>
                                        <button class="btn btn-sm btn-outline-info auto-tag-btn" 
                                                title="Generate AI tags">
                                            <i class="bi bi-tags"></i> Tags
                                        </button>
                                        ${!isVideo ? `
                                        <button class="btn btn-sm btn-outline-primary face-tagging-btn" 
                                                title="Tag people in this photo">
                                            <i class="bi bi-person-badge"></i> Faces
                                        </button>
                                        ` : ''}
                                        ${isVideo ? `
                                        <button class="btn btn-sm btn-outline-success clip-extractor-btn" 
                                                title="Extract video clip">
                                            <i class="bi bi-scissors"></i> Clip
                                        </button>
                                        <button class="btn btn-sm btn-outline-warning analyze-video-btn" 
                                                title="Video analysis: titles, topics, summary, chapters">
                                            <i class="bi bi-bar-chart"></i> Analyze
                                        </button>
                                        <button class="btn btn-sm btn-outline-info video-highlights-btn" 
                                                title="Extract key moments">
                                            <i class="bi bi-stars"></i> Highlights
                                        </button>
                                        <button class="btn btn-sm btn-outline-secondary suggest-thumbnails-btn" 
                                                title="AI thumbnail suggestions">
                                            <i class="bi bi-image"></i> Thumbs
                                        </button>
                                        ` : ''}
                                        <button class="btn btn-sm btn-outline-danger moderate-content-btn" 
                                                title="Content moderation check">
                                            <i class="bi bi-shield-check"></i> Moderate
                                        </button>
                                    </div>
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            `;
            
            container.innerHTML = html;
            
            // Add event delegation for all action buttons
            container.querySelectorAll('.result-card').forEach(card => {
                const mediaId = parseInt(card.dataset.mediaId);
                const fileType = card.dataset.fileType;
                const fileName = results.find(r => r.media_id === mediaId)?.file_name || '';
                const albumName = results.find(r => r.media_id === mediaId)?.album_name || '';
                
                // Delete button
                const deleteBtn = card.querySelector('.delete-media-btn');
                if (deleteBtn) {
                    deleteBtn.addEventListener('click', () => deleteMedia(mediaId, fileName, albumName));
                }
                
                // Find similar button
                const similarBtn = card.querySelector('.find-similar-btn');
                if (similarBtn) {
                    similarBtn.addEventListener('click', () => findSimilar(mediaId, fileName));
                }
                
                // Auto tag button
                const tagBtn = card.querySelector('.auto-tag-btn');
                if (tagBtn) {
                    tagBtn.addEventListener('click', () => autoTag(mediaId, fileName));
                }
                
                // Face tagging button
                const faceBtn = card.querySelector('.face-tagging-btn');
                if (faceBtn) {
                    faceBtn.addEventListener('click', () => showFaceTagging(mediaId, fileName));
                }
                
                // Clip extractor button
                const clipBtn = card.querySelector('.clip-extractor-btn');
                if (clipBtn) {
                    clipBtn.addEventListener('click', () => showClipExtractor(mediaId, fileName));
                }
                
                // Analyze video button
                const analyzeBtn = card.querySelector('.analyze-video-btn');
                if (analyzeBtn) {
                    analyzeBtn.addEventListener('click', () => analyzeVideo(mediaId, fileName));
                }
                
                // Video highlights button
                const highlightsBtn = card.querySelector('.video-highlights-btn');
                if (highlightsBtn) {
                    highlightsBtn.addEventListener('click', () => getVideoHighlights(mediaId, fileName));
                }
                
                // Suggest thumbnails button
                const thumbsBtn = card.querySelector('.suggest-thumbnails-btn');
                if (thumbsBtn) {
                    thumbsBtn.addEventListener('click', () => suggestThumbnails(mediaId, fileName));
                }
                
                // Moderate content button
                const moderateBtn = card.querySelector('.moderate-content-btn');
                if (moderateBtn) {
                    moderateBtn.addEventListener('click', () => moderateContent(mediaId, fileName));
                }
                
                // Checkbox selection
                const checkbox = card.querySelector('.video-select-checkbox, .photo-select-checkbox');
                if (checkbox) {
                    checkbox.addEventListener('change', () => {
                        if (fileType === 'video') {
                            updateVideoSelection();
                        } else {
                            updatePhotoSelection();
                        }
                    });
                }
            });
            
            // Load thumbnails asynchronously
            console.log('🖼️ Starting to load thumbnails for', results.length, 'results');
            results.forEach(result => {
                console.log(`Queuing thumbnail load for media ${result.media_id}, type: ${result.file_type}`);
                loadThumbnail(result.media_id, result.file_type, result.segment_start, result.segment_end);
            });
        }
        
        // Load thumbnail for a media item
        async function loadThumbnail(mediaId, fileType, segmentStart, segmentEnd) {
            try {
                console.log(`Loading thumbnail for mediaId=${mediaId}, type=${fileType}`);
                // Use unique ID that includes segment start time
                const thumbId = `thumb-${mediaId}-${segmentStart || 0}`;
                const thumbElement = document.getElementById(thumbId);
                
                if (!thumbElement) {
                    console.warn(`Thumbnail element not found: ${thumbId}`);
                    return;
                }
                
                if (fileType === 'photo') {
                    // The endpoint returns the image directly, not JSON
                    const imageUrl = `/media_thumbnail/${mediaId}`;
                    console.log(`Loading photo thumbnail from: ${imageUrl}`);
                    
                    thumbElement.innerHTML = `
                        <img src="${imageUrl}" 
                             alt="Photo thumbnail" 
                             style="width: 100%; height: 100%; object-fit: cover; border-radius: 8px; cursor: pointer; display: block;"
                             loading="lazy"
                             class="thumbnail-img">
                    `;
                    
                    // Add all event handlers to the img element
                    const img = thumbElement.querySelector('img');
                    
                    img.addEventListener('load', function() {
                        console.log(`✅ Image loaded successfully: ${imageUrl}`);
                    });
                    
                    img.addEventListener('error', function() {
                        console.error(`Failed to load image from: ${imageUrl}`);
                        this.parentElement.innerHTML = '<i class="bi bi-image-fill text-danger" style="font-size: 3rem;" title="Image failed to load"></i>';
                    });
                    
                    img.addEventListener('click', async function() {
                        const response = await fetch(`/get_media_url/${mediaId}`);
                        const data = await response.json();
                        showImageModal(mediaId, data.file_name);
                    });
                } else if (fileType === 'video') {
                    // For video segments, the endpoint returns the image directly
                    const timestamp = segmentStart || 0;
                    const imageUrl = `/video_thumbnail/${mediaId}?timestamp=${timestamp}`;
                    console.log(`Loading video thumbnail from: ${imageUrl}`);
                    
                    thumbElement.innerHTML = `
                        <img src="${imageUrl}" 
                             alt="Video thumbnail at ${formatTime(timestamp)}" 
                             style="width: 100%; height: 100%; object-fit: cover; border-radius: 8px; cursor: pointer;"
                             loading="lazy"
                             class="thumbnail-img">
                    `;
                    
                    // Add error handler
                    const img = thumbElement.querySelector('img');
                    img.addEventListener('error', function() {
                        this.parentElement.innerHTML = '<i class="bi bi-camera-video-fill text-warning" style="font-size: 3rem; opacity: 0.5;" title="Thumbnail generation failed"></i>';
                    });
                    
                    // Add click handler to play video at specific timestamp
                    img.addEventListener('click', async function() {
                        const response = await fetch(`/get_media_url/${mediaId}`);
                        const data = await response.json();
                        showVideoModal(data.par_url, data.file_name, timestamp, segmentEnd);
                    });
                }
            } catch (error) {
                console.error(`Failed to load thumbnail for media ${mediaId}:`, error);
                const thumbId = `thumb-${mediaId}-${segmentStart || 0}`;
                const thumbElement = document.getElementById(thumbId);
                if (thumbElement) {
                    thumbElement.innerHTML = `
                        <i class="bi bi-exclamation-triangle text-warning" style="font-size: 3rem;" title="Failed to load thumbnail"></i>
                    `;
                }
            }
        }
        
        // Format timestamp helper
        function formatTimestamp(startSec, endSec) {
            const start = formatTime(startSec);
            const end = formatTime(endSec);
            return `${start} - ${end}`;
        }
        
        // Format seconds to MM:SS or HH:MM:SS
        function formatTime(seconds) {
            if (!seconds && seconds !== 0) return '00:00';
            
            const hours = Math.floor(seconds / 3600);
            const minutes = Math.floor((seconds % 3600) / 60);
            const secs = Math.floor(seconds % 60);
            
            if (hours > 0) {
                return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
            } else {
                return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
            }
        }
        
        // Show video in modal with optional start time
        function showVideoModal(videoUrl, fileName, startTime, endTime) {
            const modal = new bootstrap.Modal(document.getElementById('videoModal') || createVideoModal());
            const modalVideo = document.getElementById('modalVideo');
            const modalLabel = document.getElementById('videoModalLabel');
            
            modalVideo.src = videoUrl;
            modalLabel.textContent = fileName + (startTime ? ` (${formatTime(startTime)})` : '');
            
            // Set start time if provided
            modalVideo.addEventListener('loadedmetadata', function() {
                if (startTime) {
                    modalVideo.currentTime = startTime;
                }
            }, { once: true });
            
            modal.show();
        }
        
        // Create video modal if it doesn't exist
        function createVideoModal() {
            const modalHtml = `
                <div class="modal fade" id="videoModal" tabindex="-1">
                    <div class="modal-dialog modal-lg modal-dialog-centered">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title" id="videoModalLabel">Video</h5>
                                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body p-0">
                                <video id="modalVideo" controls style="width: 100%; max-height: 70vh;"></video>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            document.body.insertAdjacentHTML('beforeend', modalHtml);
            return document.getElementById('videoModal');
        }
        
        // Show full image in modal
        function showImageModal(mediaId, fileName) {
            const modal = new bootstrap.Modal(document.getElementById('imageModal'));
            const modalImage = document.getElementById('modalImage');
            const modalLabel = document.getElementById('imageModalLabel');

            // Use cached modal-sized image for faster loading
            const modalImageUrl = `/media_modal/${mediaId}`;
            modalImage.src = modalImageUrl;
            modalImage.alt = fileName;
            modalLabel.textContent = fileName;

            modal.show();
        }

        // Show status message
        function showStatus(message, type = 'info') {
            const statusDiv = document.getElementById('searchStatus');
            const iconMap = {
                success: 'check-circle',
                error: 'exclamation-triangle',
                info: 'info-circle'
            };
            
            statusDiv.innerHTML = `
                <div class="status-message status-${type}">
                    <i class="bi bi-${iconMap[type]} me-2"></i>${message}
                </div>
            `;
        }

        // Setup enter key search
        function setupEnterKeySearch() {
            document.getElementById('searchQuery').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    performSearch();
                }
            });
        }

        // Setup upload zone
        function setupUploadZone() {
            const uploadZone = document.getElementById('uploadZone');
            const fileInput = document.getElementById('mediaFiles');
            
            uploadZone.addEventListener('click', () => fileInput.click());
            
            uploadZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                uploadZone.classList.add('dragover');
            });
            
            uploadZone.addEventListener('dragleave', () => {
                uploadZone.classList.remove('dragover');
            });
            
            uploadZone.addEventListener('drop', (e) => {
                e.preventDefault();
                uploadZone.classList.remove('dragover');
                fileInput.files = e.dataTransfer.files;
                displaySelectedFiles();
            });
            
            fileInput.addEventListener('change', displaySelectedFiles);
            
            document.getElementById('uploadForm').addEventListener('submit', handleUpload);
        }

        // Display selected files
        function displaySelectedFiles() {
            const fileInput = document.getElementById('mediaFiles');
            const container = document.getElementById('selectedFiles');
            
            if (!fileInput.files.length) {
                container.innerHTML = '';
                return;
            }
            
            const html = `
                <div class="status-message status-info">
                    <i class="bi bi-files me-2"></i>
                    <strong>${fileInput.files.length} file(s) selected</strong>
                    <ul class="mb-0 mt-2">
                        ${Array.from(fileInput.files).map(file => `
                            <li>${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)</li>
                        `).join('')}
                    </ul>
                </div>
            `;
            
            container.innerHTML = html;
        }

        // Handle upload
        async function handleUpload(e) {
            e.preventDefault();
            
            const formData = new FormData();
            const fileInput = document.getElementById('mediaFiles');
            const albumName = document.getElementById('albumName').value.trim();
            
            if (!fileInput.files.length) {
                alert('Please select files to upload');
                return;
            }
            
            if (!albumName) {
                alert('Please enter an album name');
                return;
            }
            
            // Calculate total file size and check if video processing needed
            const files = Array.from(fileInput.files);
            const totalSize = files.reduce((sum, file) => sum + file.size, 0);
            const hasLargeVideo = files.some(f => 
                f.type.startsWith('video/') && f.size > 100 * 1024 * 1024
            );
            
            // Show processing overlay for large files or videos
            if (hasLargeVideo || totalSize > 100 * 1024 * 1024) {
                showProcessingOverlay(files, totalSize);
            }
            
            // Add files and album name
            files.forEach(file => {
                formData.append('mediaFile', file);
            });
            formData.append('album_name', albumName);
            formData.append('auto_embed', 'true');
            
            // Show progress
            document.getElementById('uploadProgress').style.display = 'block';
            document.getElementById('uploadStatusLog').innerHTML = ''; // Clear previous log
            updateProgress(0, 'Starting upload...', 'init');
            
            try {
                const response = await fetch('/upload_unified', {
                    method: 'POST',
                    body: formData
                });
                
                const data = await response.json();
                
                if (data.error) {
                    hideProcessingOverlay();
                    showUploadResults(`Upload failed: ${data.error}`, 'error');
                    return;
                }
                
                // Monitor progress via SSE
                const taskId = data.task_id;
                if (taskId) {
                    const eventSource = new EventSource(`/progress/${taskId}`);
                    
                    eventSource.onmessage = (event) => {
                        const progress = JSON.parse(event.data);
                        updateProgress(progress.percent, progress.message, progress.stage || 'upload');
                        updateProcessingOverlay(progress.stage, progress.percent, progress.message);
                        
                        if (progress.stage === 'complete' || progress.stage === 'error') {
                            eventSource.close();
                            
                            setTimeout(() => {
                                hideProcessingOverlay();
                                
                                if (progress.stage === 'complete') {
                                    showUploadResults(`Successfully uploaded ${data.success_count || fileInput.files.length} file(s)!`, 'success');
                                    loadAlbums(); // Refresh albums
                                    
                                    // Reset form
                                    setTimeout(() => {
                                        document.getElementById('uploadForm').reset();
                                        document.getElementById('selectedFiles').innerHTML = '';
                                        document.getElementById('uploadProgress').style.display = 'none';
                                    }, 3000);
                                } else {
                                    showUploadResults('Upload encountered errors', 'error');
                                }
                            }, 1000); // Brief delay to show completion
                        }
                    };
                    
                    eventSource.onerror = () => {
                        eventSource.close();
                        hideProcessingOverlay();
                        showUploadResults('Connection to upload progress lost', 'error');
                    };
                } else {
                    hideProcessingOverlay();
                    updateProgress(100, 'Upload complete!');
                    showUploadResults('Upload completed successfully', 'success');
                }
            } catch (error) {
                console.error('Upload error:', error);
                hideProcessingOverlay();
                showUploadResults(`Upload failed: ${error.message}`, 'error');
            }
        }

        // Update progress bar
        function updateProgress(percent, message, stage = 'upload') {
            const progressBar = document.getElementById('uploadProgressBar');
            const statusDiv = document.getElementById('uploadStatus');
            
            progressBar.style.width = `${percent}%`;
            progressBar.textContent = `${percent}%`;
            statusDiv.textContent = message;
            
            // Add to status log
            addStatusLogEntry(stage, message);
        }
        
        // Add entry to status log
        function addStatusLogEntry(stage, message) {
            const logDiv = document.getElementById('uploadStatusLog');
            if (!logDiv) return;
            
            const timestamp = new Date().toLocaleTimeString();
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            entry.innerHTML = `
                <span class="log-timestamp">${timestamp}</span>
                <span class="log-stage log-stage-${stage}">${stage}</span>
                <span class="log-message">${message}</span>
            `;
            
            logDiv.appendChild(entry);
            
            // Auto-scroll to bottom
            logDiv.scrollTop = logDiv.scrollHeight;
        }

        // Show upload results
        function showUploadResults(message, type) {
            const resultsDiv = document.getElementById('uploadResults');
            const iconMap = {
                success: 'check-circle-fill',
                error: 'exclamation-triangle-fill'
            };
            
            resultsDiv.innerHTML = `
                <div class="status-message status-${type}">
                    <i class="bi bi-${iconMap[type]} me-2"></i>${message}
                </div>
            `;
        }

        // Load map data
        async function loadMapData() {
            try {
                const response = await fetch('/media_with_gps');
                const data = await response.json();
                const mediaItems = data.media || [];
                
                markerClusterGroup.clearLayers();
                
                mediaItems.forEach(item => {
                    if (item.latitude && item.longitude) {
                        const marker = L.marker([item.latitude, item.longitude])
                            .bindPopup(`
                                <strong>${item.file_name}</strong><br>
                                <small>Album: ${item.album_name}</small>
                            `);
                        markerClusterGroup.addLayer(marker);
                    }
                });
                
                document.getElementById('mapCount').textContent = mediaItems.length;
                
                if (mediaItems.length > 0) {
                    const bounds = markerClusterGroup.getBounds();
                    map.fitBounds(bounds, { padding: [50, 50] });
                }
            } catch (error) {
                console.error('Error loading map data:', error);
            }
        }

        // Load created slideshows
        async function loadCreatedSlideshows() {
            try {
                const response = await fetch('/list_slideshows');
                const data = await response.json();
                const slideshows = data.slideshows || [];
                
                const container = document.getElementById('slideshowsContainer');
                document.getElementById('slideshowCount').textContent = slideshows.length;
                
                if (slideshows.length === 0) {
                    container.innerHTML = `
                        <div class="empty-state">
                            <i class="bi bi-collection-play"></i>
                            <h4>No Slideshows Yet</h4>
                            <p class="text-muted">Create your first slideshow by searching for photos and selecting them</p>
                        </div>
                    `;
                    return;
                }
                
                container.innerHTML = `
                    <div class="row g-3">
                        ${slideshows.map(slideshow => `
                            <div class="col-md-6 col-lg-4">
                                <div class="card">
                                    <div class="card-body">
                                        <h5 class="card-title">
                                            <i class="bi bi-${slideshow.type === 'montage' ? 'film' : 'images'} me-2"></i>${slideshow.filename}
                                        </h5>
                                        <p class="card-text">
                                            <small class="text-muted">
                                                <i class="bi bi-folder me-1"></i>${slideshow.album_name}<br>
                                                <i class="bi bi-calendar me-1"></i>${slideshow.created}<br>
                                                <i class="bi bi-file-earmark me-1"></i>${slideshow.size_mb} MB
                                                ${slideshow.duration ? ` • ${Math.round(slideshow.duration)}s` : ''}
                                                ${slideshow.searchable ? '<br><span class="badge bg-success">Searchable</span>' : '<br><span class="badge bg-warning">Indexing...</span>'}
                                            </small>
                                        </p>
                                        <div class="d-flex gap-2">
                                            <a href="${slideshow.download_url}" class="btn btn-success btn-sm flex-grow-1" download>
                                                <i class="bi bi-download me-1"></i>Download
                                            </a>
                                            ${userPermissions.canDelete ? `
                                            <button class="btn btn-danger btn-sm delete-slideshow-btn" data-media-id="${slideshow.media_id}" title="Delete">
                                                <i class="bi bi-trash"></i>
                                            </button>
                                            ` : ''}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                `;
                
                // Add event delegation for delete slideshow buttons
                container.querySelectorAll('.delete-slideshow-btn').forEach(btn => {
                    btn.addEventListener('click', function() {
                        const mediaId = parseInt(this.dataset.mediaId);
                        deleteSlideshow(mediaId);
                    });
                });
            } catch (error) {
                console.error('Error loading slideshows:', error);
                document.getElementById('slideshowsContainer').innerHTML = `
                    <div class="alert alert-danger">
                        <i class="bi bi-exclamation-triangle me-2"></i>
                        Failed to load slideshows: ${error.message}
                    </div>
                `;
            }
        }

        // Delete slideshow
        async function deleteSlideshow(mediaId) {
            if (!confirm(`Delete this generated media?\n\nThis will remove it from cloud storage and database.\nThis action cannot be undone.`)) {
                return;
            }
            
            try {
                const response = await fetch(`/delete_generated_media/${mediaId}`, {
                    method: 'DELETE'
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    showStatus(data.message || 'Media deleted successfully', 'success');
                    loadCreatedSlideshows();
                } else {
                    showStatus(data.error || 'Failed to delete media', 'danger');
                }
            } catch (error) {
                console.error('Delete slideshow error:', error);
                showStatus(`Error: ${error.message}`, 'danger');
            }
        }

        // Delete individual media item
        async function deleteMedia(mediaId, fileName, albumName) {
            if (!confirm(`Are you sure you want to delete "${fileName}"?\n\nThis will permanently remove the ${albumName.includes('video') || fileName.includes('.mp4') ? 'video' : 'photo'} from:\n• The database\n• OCI Object Storage\n\nThis action cannot be undone.`)) {
                return;
            }
            
            try {
                const response = await fetch(`/delete_media/${mediaId}`, {
                    method: 'DELETE'
                });
                
                const data = await response.json();
                
                if (data.error) {
                    alert(`Failed to delete: ${data.error}`);
                    return;
                }
                
                // Remove the card from UI
                const card = document.querySelector(`[data-media-id="${mediaId}"]`);
                if (card) {
                    card.style.transition = 'opacity 0.3s';
                    card.style.opacity = '0';
                    setTimeout(() => card.remove(), 300);
                }
                
                // Show success message
                showStatus(data.message, 'success');
                
                // Refresh albums list
                loadAlbums();
            } catch (error) {
                console.error('Delete error:', error);
                alert(`Failed to delete media: ${error.message}`);
            }
        }

        // Delete entire album
        async function deleteAlbum(albumName) {
            if (!confirm(`⚠️ DELETE ENTIRE ALBUM?\n\nAlbum: "${albumName}"\n\nThis will permanently delete:\n• All photos and videos in this album\n• All files from OCI Object Storage\n• All AI embeddings and metadata\n\nThis action CANNOT be undone.\n\nAre you absolutely sure?`)) {
                return;
            }
            
            // Second confirmation for safety
            const confirmText = prompt(`To confirm, type the album name: ${albumName}`);
            if (confirmText !== albumName) {
                alert('Album name did not match. Deletion cancelled.');
                return;
            }
            
            try {
                const response = await fetch(`/delete_album/${encodeURIComponent(albumName)}`, {
                    method: 'DELETE'
                });
                
                const data = await response.json();
                
                if (data.error) {
                    alert(`Failed to delete album: ${data.error}`);
                    return;
                }
                
                // Show success message
                alert(data.message);
                
                // Refresh albums list
                loadAlbums();
                
                // Clear results if showing this album
                const albumFilter = document.getElementById('albumFilter');
                if (albumFilter.value === albumName) {
                    albumFilter.value = '';
                    document.getElementById('resultsContainer').innerHTML = `
                        <div class="empty-state">
                            <i class="bi bi-search"></i>
                            <h4>Start Searching</h4>
                            <p class="text-muted">Use natural language to search through your photos and videos</p>
                        </div>
                    `;
                }
            } catch (error) {
                console.error('Delete album error:', error);
                alert(`Failed to delete album: ${error.message}`);
            }
        }

        // Refresh map when tab is shown
        document.querySelector('[href="#map-tab"]').addEventListener('shown.bs.tab', function() {
            setTimeout(() => map.invalidateSize(), 100);
        });

        // =====================================================================
        // ADVANCED FEATURES
        // =====================================================================

        // Toggle Advanced Search Panel
        function toggleAdvancedSearch() {
            const panel = document.getElementById('advancedSearchPanel');
            panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
        }

        // Perform Advanced Search
        async function performAdvancedSearch() {
            try {
                const query = document.getElementById('searchQuery').value.trim();
                const mode = document.getElementById('searchMode').value;
                const mediaType = document.getElementById('mediaTypeFilter').value;
                const dateFrom = document.getElementById('dateFrom').value;
                const dateTo = document.getElementById('dateTo').value;
                const album = document.getElementById('albumFilter').value;
                
                if (!query) {
                    alert('Please enter a search query');
                    return;
                }
                
                showStatus('Searching with advanced filters...', 'info');
                
                const payload = { query, mode };
                if (mediaType) payload.media_type = mediaType;
                if (dateFrom) payload.date_from = dateFrom;
                if (dateTo) payload.date_to = dateTo;
                if (album) payload.album = album;
                
                const response = await fetch('/advanced_search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                
                const data = await response.json();
                
                if (data.error) {
                    showStatus(`Error: ${data.error}`, 'danger');
                    return;
                }
                
                displayResults(data.results || []);
                showStatus(`Found ${data.results.length} results`, 'success');
            } catch (error) {
                console.error('Advanced search error:', error);
                showStatus(`Error: ${error.message}`, 'danger');
            }
        }

        // Find Similar Media
        async function findSimilar(mediaId, fileName) {
            try {
                showStatus(`Finding similar media to ${fileName}...`, 'info');
                
                const response = await fetch(`/find_similar/${mediaId}`);
                const data = await response.json();
                
                if (data.error) {
                    showStatus(`Error: ${data.error}`, 'danger');
                    return;
                }
                
                if (data.similar_items && data.similar_items.length > 0) {
                    showStatus(`Found ${data.similar_items.length} similar items!`, 'success');
                    displayResults(data.similar_items);
                } else {
                    showStatus('No similar items found', 'warning');
                }
            } catch (error) {
                console.error('Find similar error:', error);
                showStatus(`Error finding similar media: ${error.message}`, 'danger');
            }
        }

        // Auto-tag Media
        async function autoTag(mediaId, fileName, forceOverwrite = false) {
            try {
                showStatus(`Generating AI tags for ${fileName}...`, 'info');
                
                const response = await fetch(`/auto_tag/${mediaId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        force_overwrite: forceOverwrite
                    })
                });
                const data = await response.json();
                
                if (data.error) {
                    showStatus(`Error: ${data.error}`, 'danger');
                    return;
                }
                
                // If confirmation is required (tags already exist)
                if (data.confirm_required) {
                    const confirmModal = document.createElement('div');
                    confirmModal.className = 'modal fade';
                    confirmModal.innerHTML = `
                        <div class="modal-dialog">
                            <div class="modal-content">
                                <div class="modal-header bg-warning text-dark">
                                    <h5 class="modal-title">
                                        <i class="bi bi-exclamation-triangle-fill me-2"></i>Tags Already Exist
                                    </h5>
                                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                                </div>
                                <div class="modal-body">
                                    <p><strong>${data.message}</strong></p>
                                    <div class="alert alert-info">
                                        <strong>Existing tags:</strong>
                                        <div class="mt-2" style="white-space: pre-wrap; font-size: 0.9em;">${data.existing_tags}</div>
                                    </div>
                                </div>
                                <div class="modal-footer">
                                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                                    <button type="button" class="btn btn-warning confirm-overwrite-btn" data-media-id="${mediaId}" data-file-name="${fileName}">
                                        <i class="bi bi-arrow-repeat me-1"></i>Overwrite Tags
                                    </button>
                                </div>
                            </div>
                        </div>
                    `;
                    
                    document.body.appendChild(confirmModal);
                    const bsConfirmModal = new bootstrap.Modal(confirmModal);
                    
                    // Add event listener for the overwrite button
                    const overwriteBtn = confirmModal.querySelector('.confirm-overwrite-btn');
                    overwriteBtn.addEventListener('click', function() {
                        const mediaId = parseInt(this.dataset.mediaId);
                        const fileName = this.dataset.fileName;
                        bsConfirmModal.hide();
                        confirmOverwriteTags(mediaId, fileName);
                    });
                    
                    bsConfirmModal.show();
                    confirmModal.addEventListener('hidden.bs.modal', () => confirmModal.remove());
                    return;
                }
                
                if (!data.success) {
                    showStatus(`Error: ${data.error || 'Failed to generate tags'}`, 'warning');
                    return;
                }
                
                // Get image URL for photos
                let imageHtml = '';
                if (data.file_type === 'photo') {
                    try {
                        const urlResponse = await fetch(`/get_media_url/${mediaId}`);
                        const urlData = await urlResponse.json();
                        imageHtml = `
                            <div class="col-md-5 text-center mb-3">
                                <img src="${urlData.par_url}" class="img-fluid rounded" alt="${fileName}" 
                                     style="max-height: 300px; object-fit: contain;"
                                     onerror="this.style.display='none';">
                                <p class="text-muted mt-2 small">${fileName}</p>
                            </div>
                        `;
                    } catch (e) {
                        console.warn('Failed to load image:', e);
                    }
                }
                
                // Display the generated tags in a modal
                const modal = document.createElement('div');
                modal.className = 'modal fade';
                modal.innerHTML = `
                    <div class="modal-dialog modal-lg">
                        <div class="modal-content">
                            <div class="modal-header bg-info text-white">
                                <h5 class="modal-title">
                                    <i class="bi bi-tags-fill me-2"></i>AI Generated Tags
                                </h5>
                                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body">
                                <div class="row">
                                    ${imageHtml}
                                    <div class="col-md-${imageHtml ? '7' : '12'}">
                                        <div class="alert alert-light">
                                            <div style="white-space: pre-wrap; font-family: system-ui; line-height: 1.6;">${data.generated_tags}</div>
                                        </div>
                                        ${data.video_id ? `<p class="text-muted small"><i class="bi bi-info-circle me-1"></i>Video ID: ${data.video_id}</p>` : ''}
                                    </div>
                                </div>
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                            </div>
                        </div>
                    </div>
                `;
                
                document.body.appendChild(modal);
                const bsModal = new bootstrap.Modal(modal);
                bsModal.show();
                modal.addEventListener('hidden.bs.modal', () => modal.remove());
                
                showStatus('✅ Tags generated successfully!', 'success');
            } catch (error) {
                console.error('Auto-tag error:', error);
                showStatus(`Error generating tags: ${error.message}`, 'danger');
            }
        }

        // Helper function to confirm tag overwrite
        function confirmOverwriteTags(mediaId, fileName) {
            // Close the confirmation modal
            const modals = document.querySelectorAll('.modal.show');
            modals.forEach(m => {
                const bsModal = bootstrap.Modal.getInstance(m);
                if (bsModal) bsModal.hide();
            });
            
            // Call autoTag with force overwrite
            setTimeout(() => autoTag(mediaId, fileName, true), 300);
        }

        // Show Clip Extractor Modal
        function showClipExtractor(mediaId, fileName) {
            const modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">Extract Video Clip</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p><strong>File:</strong> ${fileName}</p>
                            <div class="mb-3">
                                <label class="form-label">Start Time (seconds)</label>
                                <input type="number" class="form-control" id="clipStartTime" value="0" min="0" step="0.1">
                            </div>
                            <div class="mb-3">
                                <label class="form-label">End Time (seconds)</label>
                                <input type="number" class="form-control" id="clipEndTime" value="10" min="0.1" step="0.1">
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary extract-clip-confirm-btn" data-media-id="${mediaId}">
                                <i class="bi bi-scissors"></i> Extract Clip
                            </button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            const bsModal = new bootstrap.Modal(modal);
            
            // Add event listener for extract button
            const extractBtn = modal.querySelector('.extract-clip-confirm-btn');
            extractBtn.addEventListener('click', function() {
                const mediaId = parseInt(this.dataset.mediaId);
                extractClip(mediaId);
            });
            
            bsModal.show();
            modal.addEventListener('hidden.bs.modal', () => modal.remove());
        }

        // Extract Clip
        async function extractClip(mediaId) {
            try {
                const startTime = parseFloat(document.getElementById('clipStartTime').value);
                const endTime = parseFloat(document.getElementById('clipEndTime').value);
                
                if (startTime >= endTime) {
                    alert('End time must be greater than start time');
                    return;
                }
                
                showStatus('Extracting clip...', 'info');
                
                const response = await fetch('/extract_clip', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        media_id: mediaId,
                        start_time: startTime,
                        end_time: endTime
                    })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    showStatus(`Error: ${data.error}`, 'danger');
                    return;
                }
                
                showStatus(data.message || 'Clip extraction initiated!', 'success');
                bootstrap.Modal.getInstance(document.querySelector('.modal.show')).hide();
            } catch (error) {
                console.error('Extract clip error:', error);
                showStatus(`Error extracting clip: ${error.message}`, 'danger');
            }
        }

        // Show status message
        function showStatus(message, type = 'info') {
            const alert = document.createElement('div');
            alert.className = `alert alert-${type} alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3`;
            alert.style.zIndex = '9999';
            alert.innerHTML = `
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;
            document.body.appendChild(alert);
            setTimeout(() => alert.remove(), 5000);
        }

        // Video Analysis - Comprehensive
        async function analyzeVideo(mediaId, fileName) {
            try {
                showStatus(`Analyzing video: ${fileName}...`, 'info');
                
                const response = await fetch(`/video_analysis/${mediaId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        types: ['title', 'topics', 'hashtags', 'summary', 'chapters']
                    })
                });
                const data = await response.json();
                
                if (data.error) {
                    showStatus(`Error: ${data.error}`, 'danger');
                    return;
                }
                
                // Display results in a modal
                const analysis = data.analysis || {};
                let content = `<h5>Video Analysis: ${fileName}</h5>`;
                
                if (analysis.title) {
                    content += `<p><strong>Title:</strong> ${analysis.title}</p>`;
                }
                if (analysis.summary) {
                    content += `<p><strong>Summary:</strong> ${analysis.summary}</p>`;
                }
                if (analysis.topics && analysis.topics.length > 0) {
                    content += `<p><strong>Topics:</strong> ${analysis.topics.join(', ')}</p>`;
                }
                if (analysis.hashtags && analysis.hashtags.length > 0) {
                    content += `<p><strong>Hashtags:</strong> ${analysis.hashtags.join(' ')}</p>`;
                }
                if (analysis.chapters && analysis.chapters.length > 0) {
                    content += `<p><strong>Chapters:</strong></p><ul>`;
                    analysis.chapters.forEach(ch => {
                        content += `<li>${ch.title} (${ch.start}s - ${ch.end}s)</li>`;
                    });
                    content += `</ul>`;
                }
                
                showModal('Video Analysis', content);
                showStatus('Video analysis complete!', 'success');
            } catch (error) {
                console.error('Video analysis error:', error);
                showStatus(`Error: ${error.message}`, 'danger');
            }
        }

        // Get Video Highlights
        async function getVideoHighlights(mediaId, fileName) {
            try {
                showStatus(`Extracting highlights from: ${fileName}...`, 'info');
                
                const response = await fetch(`/video_highlights/${mediaId}`);
                const data = await response.json();
                
                if (data.error) {
                    showStatus(`Error: ${data.error}`, 'danger');
                    return;
                }
                
                showModal('Video Highlights', `
                    <p>Key moments identified for: <strong>${fileName}</strong></p>
                    <p>${data.message}</p>
                `);
                showStatus('Highlights extraction complete!', 'success');
            } catch (error) {
                console.error('Highlights error:', error);
                showStatus(`Error: ${error.message}`, 'danger');
            }
        }

        // Suggest Thumbnails
        async function suggestThumbnails(mediaId, fileName) {
            try {
                showStatus(`Getting thumbnail suggestions for: ${fileName}...`, 'info');
                
                const response = await fetch(`/thumbnail_suggestions/${mediaId}`);
                const data = await response.json();
                
                if (data.error) {
                    showStatus(`Error: ${data.error}`, 'danger');
                    return;
                }
                
                let content = `<h5>AI Thumbnail Suggestions for ${fileName}</h5>`;
                if (data.suggestions && data.suggestions.length > 0) {
                    content += '<div class="list-group">';
                    data.suggestions.forEach((sug, idx) => {
                        content += `
                            <div class="list-group-item">
                                <strong>#${idx + 1}</strong> at ${sug.timestamp}s 
                                <span class="badge bg-success">${Math.round(sug.score * 100)}%</span>
                                <br><small>${sug.reason}</small>
                            </div>
                        `;
                    });
                    content += '</div>';
                }
                
                showModal('Thumbnail Suggestions', content);
                showStatus('Thumbnail suggestions ready!', 'success');
            } catch (error) {
                console.error('Thumbnail suggestions error:', error);
                showStatus(`Error: ${error.message}`, 'danger');
            }
        }

        // Content Moderation
        async function moderateContent(mediaId, fileName) {
            try {
                showStatus(`Checking content safety for: ${fileName}...`, 'info');
                
                const response = await fetch(`/content_moderation/${mediaId}`, {
                    method: 'POST'
                });
                const data = await response.json();
                
                if (data.error) {
                    showStatus(`Error: ${data.error}`, 'danger');
                    return;
                }
                
                const statusClass = data.is_safe ? 'success' : 'danger';
                const statusIcon = data.is_safe ? 'check-circle' : 'exclamation-triangle';
                
                let content = `
                    <h5>Content Moderation: ${fileName}</h5>
                    <div class="alert alert-${statusClass}">
                        <i class="bi bi-${statusIcon}"></i> 
                        ${data.message} (${Math.round(data.confidence * 100)}% confidence)
                    </div>
                `;
                
                if (data.categories) {
                    content += '<p><strong>Category Scores:</strong></p><ul>';
                    for (const [cat, score] of Object.entries(data.categories)) {
                        content += `<li>${cat}: ${Math.round(score * 100)}%</li>`;
                    }
                    content += '</ul>';
                }
                
                showModal('Content Moderation', content);
                showStatus('Moderation check complete!', 'success');
            } catch (error) {
                console.error('Moderation error:', error);
                showStatus(`Error: ${error.message}`, 'danger');
            }
        }

        // Face Tagging Functions
        let currentFaceTaggingMediaId = null;
        let detectedFaces = [];

        async function showFaceTagging(mediaId, fileName) {
            currentFaceTaggingMediaId = mediaId;
            
            // Set modal title
            document.getElementById('faceTaggingModalLabel').innerHTML = 
                `<i class="bi bi-person-badge me-2"></i>Face Tagging - ${fileName}`;
            
            // Reset state
            detectedFaces = [];
            document.getElementById('detectedFacesPanel').style.display = 'none';
            document.getElementById('faceDetectionStatus').textContent = '';
            document.getElementById('faceBoxesOverlay').innerHTML = '';
            
            // Load face name suggestions for autocomplete
            await loadFaceNameSuggestions();
            
            // Load photo into modal using the media URL endpoint
            try {
                const response = await fetch(`/get_media_url/${mediaId}`);
                if (!response.ok) throw new Error('Failed to get media URL');
                
                const data = await response.json();
                const img = document.getElementById('faceTaggingImage');
                img.src = data.par_url;
                img.alt = data.file_name;
                
                // Handle image load error
                img.onerror = function() {
                    showStatus('Error loading photo', 'danger');
                    img.alt = 'Failed to load image';
                };
                
                // Auto-detect faces when image loads
                img.onload = function() {
                    console.log('Image loaded, auto-detecting faces...');
                    detectFaces();
                };
            } catch (error) {
                console.error('Error loading photo:', error);
                showStatus(`Error loading photo: ${error.message}`, 'danger');
            }
            
            // Load existing tagged faces
            await loadTaggedFaces(mediaId);
            
            // Show modal
            const modal = new bootstrap.Modal(document.getElementById('faceTaggingModal'));
            modal.show();
        }

        async function detectFaces() {
            if (!currentFaceTaggingMediaId) return;
            
            const statusEl = document.getElementById('faceDetectionStatus');
            const btn = document.getElementById('detectFacesBtn');
            
            try {
                btn.disabled = true;
                statusEl.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Detecting faces...';
                
                const response = await fetch(`/media/${currentFaceTaggingMediaId}/detect_faces`, {
                    method: 'POST'
                });
                const data = await response.json();
                
                if (data.error) {
                    statusEl.innerHTML = `<span class="text-danger"><i class="bi bi-x-circle me-1"></i>${data.error}</span>`;
                    return;
                }
                
                detectedFaces = data.faces || [];
                const existingTags = data.existing_tags || [];
                
                if (detectedFaces.length === 0) {
                    statusEl.innerHTML = '<span class="text-muted"><i class="bi bi-info-circle me-1"></i>No faces detected</span>';
                    document.getElementById('detectedFacesPanel').style.display = 'none';
                } else {
                    const taggedCount = existingTags.length;
                    statusEl.innerHTML = `<span class="text-success"><i class="bi bi-check-circle me-1"></i>Found ${detectedFaces.length} face(s) (${taggedCount} already tagged)</span>`;
                    displayDetectedFaces(detectedFaces, existingTags);
                }
            } catch (error) {
                console.error('Face detection error:', error);
                statusEl.innerHTML = `<span class="text-danger"><i class="bi bi-x-circle me-1"></i>Error: ${error.message}</span>`;
            } finally {
                btn.disabled = false;
            }
        }

        function displayDetectedFaces(faces, existingTags = []) {
            const panel = document.getElementById('detectedFacesPanel');
            const list = document.getElementById('detectedFacesList');
            const countEl = document.getElementById('detectedFaceCount');
            
            countEl.textContent = faces.length;
            
            list.innerHTML = faces.map((face, index) => {
                const isMatched = face.matched_tag;
                const tagName = isMatched ? face.matched_tag.face_name : '';
                
                return `
                <div class="card mb-2 ${isMatched ? 'border-success' : ''}">
                    <div class="card-body p-2">
                        <div class="d-flex align-items-center gap-2">
                            <span class="badge ${isMatched ? 'bg-success' : 'bg-primary'}">
                                ${isMatched ? '<i class="bi bi-check-circle me-1"></i>' : ''}Face ${index + 1}
                            </span>
                            ${isMatched ? 
                                `<span class="text-success fw-bold">${tagName}</span>
                                 <small class="text-muted">(already tagged)</small>` : 
                                `<input type="text" 
                                       class="form-control form-control-sm" 
                                       id="faceName${index}" 
                                       list="faceNameSuggestions"
                                       placeholder="Enter or select name">
                                 <button class="btn btn-sm btn-success" 
                                        onclick="tagFace(${index})">
                                    <i class="bi bi-tag"></i> Tag
                                 </button>`
                            }
                        </div>
                    </div>
                </div>
            `}).join('');
            
            panel.style.display = 'block';
            
            // Draw bounding boxes on the image with existing tags
            drawFaceBoundingBoxes(faces, existingTags);
        }

        function drawFaceBoundingBoxes(faces, existingTags = []) {
            const img = document.getElementById('faceTaggingImage');
            const overlay = document.getElementById('faceBoxesOverlay');
            
            console.log('Drawing bounding boxes for', faces.length, 'faces');
            console.log('Face data:', faces);
            console.log('Existing tags:', existingTags);
            
            // Clear existing boxes
            overlay.innerHTML = '';
            
            if (!img.complete || !img.naturalWidth) {
                // Image not loaded yet, wait for it
                console.log('Image not loaded, waiting...');
                img.onload = function() {
                    drawFaceBoundingBoxes(faces, existingTags);
                };
                return;
            }
            
            // Get the displayed image dimensions
            const displayedWidth = img.offsetWidth;
            const displayedHeight = img.offsetHeight;
            const naturalWidth = img.naturalWidth;
            const naturalHeight = img.naturalHeight;
            
            console.log('Image dimensions:', {
                displayed: { width: displayedWidth, height: displayedHeight },
                natural: { width: naturalWidth, height: naturalHeight }
            });
            
            // Calculate scale factors
            const scaleX = displayedWidth / naturalWidth;
            const scaleY = displayedHeight / naturalHeight;
            
            console.log('Scale factors:', { scaleX, scaleY });
            
            // Position overlay to match image
            const imgRect = img.getBoundingClientRect();
            const parentRect = img.parentElement.getBoundingClientRect();
            
            overlay.style.left = (imgRect.left - parentRect.left) + 'px';
            overlay.style.top = (imgRect.top - parentRect.top) + 'px';
            overlay.style.width = displayedWidth + 'px';
            overlay.style.height = displayedHeight + 'px';
            
            console.log('Overlay positioned:', {
                left: overlay.style.left,
                top: overlay.style.top,
                width: overlay.style.width,
                height: overlay.style.height
            });
            
            // Draw each face box
            faces.forEach((face, index) => {
                // Handle both formats: face.bbox (array) or face.facial_area (object)
                let x, y, width, height;
                
                if (face.bbox && Array.isArray(face.bbox) && face.bbox.length === 4) {
                    [x, y, width, height] = face.bbox;
                } else if (face.facial_area) {
                    // OpenCV format: {x, y, w, h}
                    x = face.facial_area.x;
                    y = face.facial_area.y;
                    width = face.facial_area.w;
                    height = face.facial_area.h;
                } else {
                    console.warn('Face data missing bbox or facial_area:', face);
                    return;
                }
                
                // Check if this face is matched with an existing tag
                const isMatched = face.matched_tag;
                const borderColor = isMatched ? '#198754' : '#0d6efd';  // Green if matched, blue otherwise
                const shadowColor = isMatched ? 'rgba(25, 135, 84, 0.5)' : 'rgba(13, 110, 253, 0.5)';
                
                // Scale to displayed size
                const scaledX = x * scaleX;
                const scaledY = y * scaleY;
                const scaledWidth = width * scaleX;
                const scaledHeight = height * scaleY;
                
                // Create box element
                const box = document.createElement('div');
                box.style.position = 'absolute';
                box.style.left = scaledX + 'px';
                box.style.top = scaledY + 'px';
                box.style.width = scaledWidth + 'px';
                box.style.height = scaledHeight + 'px';
                box.style.border = `3px solid ${borderColor}`;
                box.style.boxShadow = `0 0 10px ${shadowColor}`;
                box.style.borderRadius = '4px';
                
                // Create label with face number or matched name
                const label = document.createElement('div');
                label.style.position = 'absolute';
                label.style.top = '-28px';
                label.style.left = '0';
                label.style.background = borderColor;
                label.style.color = 'white';
                label.style.padding = '4px 10px';
                label.style.borderRadius = '4px';
                label.style.fontWeight = 'bold';
                label.style.fontSize = '14px';
                label.style.boxShadow = '0 2px 4px rgba(0,0,0,0.3)';
                
                if (isMatched) {
                    label.innerHTML = `<i class="bi bi-check-circle me-1"></i>${face.matched_tag.face_name}`;
                } else {
                    label.textContent = `Face ${index + 1}`;
                }
                
                box.appendChild(label);
                overlay.appendChild(box);
            });
        }


        async function tagFace(faceIndex) {
            const nameInput = document.getElementById(`faceName${faceIndex}`);
            const name = nameInput.value.trim();
            
            if (!name) {
                alert('Please enter a name');
                return;
            }
            
            try {
                const response = await fetch(`/media/${currentFaceTaggingMediaId}/tag_face`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        face_index: faceIndex,
                        name: name
                    })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    showStatus(`Error: ${data.error}`, 'danger');
                    return;
                }
                
                showStatus(`Tagged face as "${name}"`, 'success');
                nameInput.value = '';
                
                // Reload tagged faces
                await loadTaggedFaces(currentFaceTaggingMediaId);
                
                // Re-detect faces to show the updated tag on the face
                await detectFaces();
            } catch (error) {
                console.error('Face tagging error:', error);
                showStatus(`Error: ${error.message}`, 'danger');
            }
        }

        async function loadTaggedFaces(mediaId) {
            try {
                const response = await fetch(`/media/${mediaId}/faces`);
                const data = await response.json();
                
                const list = document.getElementById('taggedFacesList');
                const countEl = document.getElementById('taggedFaceCount');
                
                const faces = data.face_tags || data.faces || [];
                countEl.textContent = faces.length;
                
                if (faces.length === 0) {
                    list.innerHTML = '<p class="text-muted text-center mb-0">No faces tagged yet</p>';
                    return;
                }
                
                list.innerHTML = faces.map(face => {
                    const faceId = face.tag_id || face.id;
                    const faceName = face.name || face.face_name;
                    const autoTagged = face.auto_tagged !== undefined ? face.auto_tagged : false;
                    const confidence = face.confidence || 0;
                    const taggedBy = face.tagged_by || 'Unknown';
                    
                    return `
                    <div class="card mb-2" id="face-card-${faceId}">
                        <div class="card-body p-2">
                            <div class="d-flex justify-content-between align-items-center">
                                <div class="flex-grow-1">
                                    <div class="d-flex align-items-center gap-2">
                                        <i class="bi bi-person-fill"></i>
                                        <span id="face-name-${faceId}" 
                                              class="face-name-display face-name-hover" 
                                              data-face-id="${faceId}"
                                              data-face-name="${faceName.replace(/'/g, '&apos;').replace(/"/g, '&quot;')}"
                                              title="Double-click to edit"
                                              style="cursor: pointer; padding: 2px 8px; border-radius: 4px; transition: background-color 0.2s;">
                                            <strong>${faceName}</strong>
                                        </span>
                                        <input type="text" 
                                               id="face-edit-${faceId}" 
                                               class="form-control form-control-sm" 
                                               value="${faceName.replace(/"/g, '&quot;')}" 
                                               style="display: none; max-width: 200px;"
                                               onkeydown="handleFaceEditKeyPress(event, ${faceId})">
                                    </div>
                                    <div class="small text-muted mt-1">
                                        ${autoTagged ? 
                                            `<span class="badge bg-info">Auto</span> ${Math.round(confidence * 100)}%` : 
                                            '<span class="badge bg-success">Manual</span>'}
                                        · Tagged by ${taggedBy}
                                    </div>
                                </div>
                                <div class="btn-group btn-group-sm" role="group">
                                    <button class="btn btn-outline-primary face-edit-btn" 
                                            id="face-edit-btn-${faceId}"
                                            data-face-id="${faceId}"
                                            data-face-name="${faceName.replace(/'/g, '&apos;').replace(/"/g, '&quot;')}"
                                            title="Edit name">
                                        <i class="bi bi-pencil"></i>
                                    </button>
                                    <button class="btn btn-outline-success face-save-btn" 
                                            id="face-save-btn-${faceId}"
                                            data-face-id="${faceId}"
                                            style="display: none;"
                                            title="Save">
                                        <i class="bi bi-check-lg"></i>
                                    </button>
                                    <button class="btn btn-outline-secondary face-cancel-btn" 
                                            id="face-cancel-btn-${faceId}"
                                            data-face-id="${faceId}"
                                            data-face-name="${faceName.replace(/'/g, '&apos;').replace(/"/g, '&quot;')}"
                                            style="display: none;"
                                            title="Cancel">
                                        <i class="bi bi-x-lg"></i>
                                    </button>
                                    <button class="btn btn-outline-danger face-delete-btn" 
                                            data-face-id="${faceId}"
                                            title="Delete">
                                        <i class="bi bi-trash"></i>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                `}).join('');
                
                // Add event delegation for face tagging buttons
                list.querySelectorAll('.face-name-display').forEach(span => {
                    span.addEventListener('dblclick', function() {
                        const faceId = parseInt(this.dataset.faceId);
                        const faceName = this.dataset.faceName.replace(/&apos;/g, "'").replace(/&quot;/g, '"');
                        editFaceTagInline(faceId, faceName);
                    });
                });
                
                list.querySelectorAll('.face-edit-btn').forEach(btn => {
                    btn.addEventListener('click', function() {
                        const faceId = parseInt(this.dataset.faceId);
                        const faceName = this.dataset.faceName.replace(/&apos;/g, "'").replace(/&quot;/g, '"');
                        editFaceTagInline(faceId, faceName);
                    });
                });
                
                list.querySelectorAll('.face-save-btn').forEach(btn => {
                    btn.addEventListener('click', function() {
                        const faceId = parseInt(this.dataset.faceId);
                        saveFaceTagInline(faceId);
                    });
                });
                
                list.querySelectorAll('.face-cancel-btn').forEach(btn => {
                    btn.addEventListener('click', function() {
                        const faceId = parseInt(this.dataset.faceId);
                        const faceName = this.dataset.faceName.replace(/&apos;/g, "'").replace(/&quot;/g, '"');
                        cancelFaceEditInline(faceId, faceName);
                    });
                });
                
                list.querySelectorAll('.face-delete-btn').forEach(btn => {
                    btn.addEventListener('click', function() {
                        const faceId = parseInt(this.dataset.faceId);
                        deleteFaceTag(faceId);
                    });
                });
            } catch (error) {
                console.error('Error loading tagged faces:', error);
            }
        }

        async function loadFaceNameSuggestions() {
            try {
                const response = await fetch('/api/face_names');
                const data = await response.json();
                
                if (data.success && data.face_names) {
                    const datalist = document.getElementById('faceNameSuggestions');
                    datalist.innerHTML = data.face_names.map(item => 
                        `<option value="${item.name}">${item.name} (${item.count} photos)</option>`
                    ).join('');
                }
            } catch (error) {
                console.error('Error loading face name suggestions:', error);
            }
        }

        async function deleteFaceTag(tagId) {
            if (!confirm('Delete this face tag?')) return;
            
            try {
                const response = await fetch(`/face_tags/${tagId}`, {
                    method: 'DELETE'
                });
                
                const data = await response.json();
                
                if (data.error) {
                    showStatus(`Error: ${data.error}`, 'danger');
                    return;
                }
                
                showStatus('Face tag deleted', 'success');
                await loadTaggedFaces(currentFaceTaggingMediaId);
            } catch (error) {
                console.error('Error deleting face tag:', error);
                showStatus(`Error: ${error.message}`, 'danger');
            }
        }

        // Face tag inline editing functions
        let currentEditingFaceId = null;

        function editFaceTagInline(faceId, currentName) {
            // Cancel any existing edit
            if (currentEditingFaceId && currentEditingFaceId !== faceId) {
                cancelFaceEditInline(currentEditingFaceId, currentName);
            }

            currentEditingFaceId = faceId;
            
            // Hide display, show input
            const nameDisplay = document.getElementById(`face-name-${faceId}`);
            const editInput = document.getElementById(`face-edit-${faceId}`);
            const editBtn = document.getElementById(`face-edit-btn-${faceId}`);
            const saveBtn = document.getElementById(`face-save-btn-${faceId}`);
            const cancelBtn = document.getElementById(`face-cancel-btn-${faceId}`);
            
            if (nameDisplay) nameDisplay.style.display = 'none';
            if (editInput) {
                editInput.style.display = 'inline-block';
                editInput.focus();
                editInput.select();
            }
            if (editBtn) editBtn.style.display = 'none';
            if (saveBtn) saveBtn.style.display = 'inline-block';
            if (cancelBtn) cancelBtn.style.display = 'inline-block';
        }

        function cancelFaceEditInline(faceId, originalName) {
            const nameDisplay = document.getElementById(`face-name-${faceId}`);
            const editInput = document.getElementById(`face-edit-${faceId}`);
            const editBtn = document.getElementById(`face-edit-btn-${faceId}`);
            const saveBtn = document.getElementById(`face-save-btn-${faceId}`);
            const cancelBtn = document.getElementById(`face-cancel-btn-${faceId}`);
            
            // Reset to original value
            if (editInput) editInput.value = originalName;
            
            // Show display, hide input
            if (nameDisplay) nameDisplay.style.display = 'inline-block';
            if (editInput) editInput.style.display = 'none';
            if (editBtn) editBtn.style.display = 'inline-block';
            if (saveBtn) saveBtn.style.display = 'none';
            if (cancelBtn) cancelBtn.style.display = 'none';
            
            currentEditingFaceId = null;
        }

        async function saveFaceTagInline(faceId) {
            const editInput = document.getElementById(`face-edit-${faceId}`);
            const newName = editInput ? editInput.value.trim() : '';
            const nameDisplay = document.getElementById(`face-name-${faceId}`);
            const oldName = nameDisplay ? nameDisplay.textContent.trim() : '';
            
            if (!newName) {
                showStatus('Face name cannot be empty', 'danger');
                return;
            }
            
            // No change
            if (newName === oldName) {
                cancelFaceEditInline(faceId, oldName);
                return;
            }
            
            // Disable buttons during save
            const saveBtn = document.getElementById(`face-save-btn-${faceId}`);
            const cancelBtn = document.getElementById(`face-cancel-btn-${faceId}`);
            if (saveBtn) {
                saveBtn.disabled = true;
                saveBtn.innerHTML = '<i class="bi bi-hourglass-split"></i>';
            }
            if (cancelBtn) cancelBtn.disabled = true;
            
            try {
                const response = await fetch(`/api/face_tags/${faceId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ face_name: newName })
                });
                
                const data = await response.json();
                
                if (!response.ok) {
                    throw new Error(data.error || 'Failed to update face tag');
                }
                
                // Update display
                if (nameDisplay) {
                    nameDisplay.innerHTML = `<strong>${newName}</strong>`;
                    // Update the ondblclick and onclick attributes with new name
                    nameDisplay.setAttribute('ondblclick', `editFaceTagInline(${faceId}, '${newName.replace(/'/g, "\\'")}')`);
                }
                
                // Update cancel button
                const cancelButton = document.getElementById(`face-cancel-btn-${faceId}`);
                if (cancelButton) {
                    cancelButton.setAttribute('onclick', `cancelFaceEditInline(${faceId}, '${newName.replace(/'/g, "\\'")}')`);
                }
                
                cancelFaceEditInline(faceId, newName);
                showStatus(`✅ Updated: ${data.old_name} → ${data.new_name}`, 'success');
                
            } catch (error) {
                showStatus(`❌ Error: ${error.message}`, 'danger');
                // Re-enable buttons on error
                if (saveBtn) {
                    saveBtn.disabled = false;
                    saveBtn.innerHTML = '<i class="bi bi-check-lg"></i>';
                }
                if (cancelBtn) cancelBtn.disabled = false;
            }
        }

        function handleFaceEditKeyPress(event, faceId) {
            if (event.key === 'Enter') {
                event.preventDefault();
                saveFaceTagInline(faceId);
            } else if (event.key === 'Escape') {
                event.preventDefault();
                const nameDisplay = document.getElementById(`face-name-${faceId}`);
                const originalName = nameDisplay ? nameDisplay.textContent.trim() : '';
                cancelFaceEditInline(faceId, originalName);
            }
        }

        // Attach detect faces button handler
        document.addEventListener('DOMContentLoaded', function() {
            const detectBtn = document.getElementById('detectFacesBtn');
            if (detectBtn) {
                detectBtn.addEventListener('click', detectFaces);
            }
        });

        // Generic Modal Display
        function showModal(title, content) {
            const modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${title}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            ${content}
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Close</button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            const bsModal = new bootstrap.Modal(modal);
            bsModal.show();
            modal.addEventListener('hidden.bs.modal', () => modal.remove());
        }

        // ========== CREATIVE TOOLS ==========

        // Show Montage Creator Modal
        function showMontageCreator() {
            const modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header bg-primary text-white">
                            <h5 class="modal-title"><i class="bi bi-film me-2"></i>Create Video Montage</h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="alert alert-info">
                                <i class="bi bi-info-circle me-2"></i>
                                Select videos to combine into a montage with transitions
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label"><strong>Video Selection</strong></label>
                                <div id="montageVideoList" class="border rounded p-3" style="max-height: 300px; overflow-y: auto;">
                                    <div class="text-center text-muted py-4">
                                        <div class="spinner-border spinner-border-sm" role="status"></div>
                                        <p class="mt-2">Loading videos...</p>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="row g-3">
                                <div class="col-md-6">
                                    <label class="form-label">Transition Effect</label>
                                    <select id="montageTransition" class="form-select">
                                        <option value="fade">Fade (Smooth)</option>
                                        <option value="dissolve">Dissolve</option>
                                        <option value="wipe">Wipe</option>
                                    </select>
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Duration per Clip (seconds)</label>
                                    <input type="number" id="montageDuration" class="form-control" value="5" min="1" max="30" step="0.5">
                                </div>
                                <div class="col-12">
                                    <label class="form-label">Output Filename</label>
                                    <input type="text" id="montageOutputName" class="form-control" value="my_montage.mp4" placeholder="montage.mp4">
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-primary" onclick="createMontage()">
                                <i class="bi bi-film me-2"></i>Create Montage
                            </button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            const bsModal = new bootstrap.Modal(modal);
            bsModal.show();
            modal.addEventListener('hidden.bs.modal', () => modal.remove());
            
            // Load available videos
            loadVideosForMontage();
        }

        // Load Videos for Montage
        async function loadVideosForMontage() {
            try {
                const response = await fetch('/albums');
                const data = await response.json();
                
                const container = document.getElementById('montageVideoList');
                let html = '';
                
                if (data.albums && data.albums.length > 0) {
                    for (const album of data.albums) {
                        const albumResponse = await fetch(`/album/${encodeURIComponent(album)}`);
                        const albumData = await albumResponse.json();
                        
                        const videos = (albumData.media || []).filter(m => m.file_type === 'video');
                        
                        if (videos.length > 0) {
                            html += `<div class="mb-3"><strong>${album}</strong></div>`;
                            videos.forEach(video => {
                                html += `
                                    <div class="form-check mb-2">
                                        <input class="form-check-input montage-video-check" type="checkbox" 
                                               value="${video.id}" id="montage-video-${video.id}">
                                        <label class="form-check-label" for="montage-video-${video.id}">
                                            ${video.file_name}
                                        </label>
                                    </div>
                                `;
                            });
                        }
                    }
                }
                
                if (!html) {
                    html = '<p class="text-muted text-center py-4">No videos available</p>';
                }
                
                container.innerHTML = html;
            } catch (error) {
                console.error('Error loading videos:', error);
                document.getElementById('montageVideoList').innerHTML = 
                    '<p class="text-danger text-center py-4">Error loading videos</p>';
            }
        }

        // Create Montage
        async function createMontage() {
            try {
                const selectedVideos = Array.from(document.querySelectorAll('.montage-video-check:checked'))
                    .map(cb => parseInt(cb.value));
                
                if (selectedVideos.length < 2) {
                    showStatus('Please select at least 2 videos for montage', 'warning');
                    return;
                }
                
                const transition = document.getElementById('montageTransition').value;
                const duration = parseFloat(document.getElementById('montageDuration').value);
                const outputName = document.getElementById('montageOutputName').value || 'montage.mp4';
                
                showStatus(`Creating montage with ${selectedVideos.length} videos...`, 'info');
                
                const response = await fetch('/create_montage', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        video_ids: selectedVideos,
                        transition: transition,
                        duration_per_clip: duration,
                        output_name: outputName
                    })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    showStatus(`Error: ${data.error}`, 'danger');
                    return;
                }
                
                showStatus(`✅ ${data.message}! Estimated duration: ${Math.round(data.estimated_duration)}s`, 'success');
                bootstrap.Modal.getInstance(document.querySelector('.modal.show')).hide();
            } catch (error) {
                console.error('Montage creation error:', error);
                showStatus(`Error creating montage: ${error.message}`, 'danger');
            }
        }

        // Update photo selection tracking
        function updatePhotoSelection() {
            selectedPhotos.clear();
            document.querySelectorAll('.photo-select-checkbox:checked').forEach(checkbox => {
                selectedPhotos.add(parseInt(checkbox.dataset.mediaId));
            });
            
            const count = selectedPhotos.size;
            const button = document.getElementById('createSlideshowFromSelected');
            const countSpan = document.getElementById('selectedPhotoCount');
            
            if (count > 0) {
                button.style.display = 'inline-block';
                countSpan.textContent = count;
            } else {
                button.style.display = 'none';
            }
        }

        // Update video selection tracking
        function updateVideoSelection() {
            selectedVideos.clear();
            document.querySelectorAll('.video-select-checkbox:checked').forEach(checkbox => {
                selectedVideos.add(parseInt(checkbox.dataset.mediaId));
            });
            
            const count = selectedVideos.size;
            const button = document.getElementById('createMontageFromSelected');
            const countSpan = document.getElementById('selectedVideoCount');
            
            if (count > 0) {
                button.style.display = 'inline-block';
                countSpan.textContent = count;
            } else {
                button.style.display = 'none';
            }
        }

        // Create slideshow from selected photos
        async function createSlideshowFromSelected() {
            if (selectedPhotos.size === 0) {
                showStatus('Please select at least one photo', 'warning');
                return;
            }

            const modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header bg-success text-white">
                            <h5 class="modal-title"><i class="bi bi-images me-2"></i>Create Slideshow</h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="alert alert-info">
                                <i class="bi bi-info-circle me-2"></i>
                                Creating slideshow from ${selectedPhotos.size} selected photo${selectedPhotos.size > 1 ? 's' : ''}
                            </div>
                            
                            <div class="row g-3">
                                <div class="col-md-6">
                                    <label class="form-label">Transition Effect</label>
                                    <select id="slideshowTransition" class="form-select">
                                        <option value="fade">Fade</option>
                                        <option value="dissolve">Dissolve</option>
                                        <option value="slide">Slide</option>
                                    </select>
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Duration per Photo (seconds)</label>
                                    <input type="number" id="slideshowDuration" class="form-control" value="3" min="1" max="10" step="0.5">
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Resolution</label>
                                    <select id="slideshowResolution" class="form-select">
                                        <option value="1920x1080">1920x1080 (Full HD)</option>
                                        <option value="1280x720">1280x720 (HD)</option>
                                        <option value="3840x2160">3840x2160 (4K)</option>
                                    </select>
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Output Filename</label>
                                    <input type="text" id="slideshowFilename" class="form-control" placeholder="slideshow.mp4">
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-success" onclick="submitSlideshowCreation()">
                                <i class="bi bi-play-circle me-2"></i>Create Slideshow
                            </button>
                        </div>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            const bsModal = new bootstrap.Modal(modal);
            bsModal.show();
            modal.addEventListener('hidden.bs.modal', () => modal.remove());
        }

        // Submit slideshow creation
        async function submitSlideshowCreation() {
            const transition = document.getElementById('slideshowTransition').value;
            const duration = parseFloat(document.getElementById('slideshowDuration').value);
            const resolution = document.getElementById('slideshowResolution').value;
            const filename = document.getElementById('slideshowFilename').value || 'slideshow.mp4';

            try {
                showStatus('Creating slideshow...', 'info');
                
                const response = await fetch('/create_slideshow', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        photo_ids: Array.from(selectedPhotos),
                        duration_per_photo: duration,
                        transition: transition,
                        resolution: resolution,
                        output_filename: filename
                    })
                });

                const data = await response.json();
                
                if (!response.ok) {
                    showStatus(`Error: ${data.error}`, 'danger');
                    return;
                }
                
                // Show success with download link and searchability info
                const downloadLink = data.download_url ? 
                    `<br><a href="${data.download_url}" class="btn btn-success btn-sm mt-2" download><i class="bi bi-download me-2"></i>Download (${data.file_size_mb} MB)</a>` : '';
                
                const searchInfo = data.searchable ? 
                    '<br><small class="text-success"><i class="bi bi-check-circle me-1"></i>Uploaded to cloud storage & AI indexing started - will be searchable soon!</small>' : '';
                
                showStatus(`✅ ${data.message}! Duration: ${Math.round(data.estimated_duration)}s${downloadLink}${searchInfo}`, 'success', 12000);
                bootstrap.Modal.getInstance(document.querySelector('.modal.show')).hide();
                
                // Refresh slideshow list if on that tab
                loadCreatedSlideshows();
                
                // Clear selections
                document.querySelectorAll('.photo-select-checkbox:checked').forEach(checkbox => {
                    checkbox.checked = false;
                });
                updatePhotoSelection();
                
            } catch (error) {
                console.error('Slideshow creation error:', error);
                showStatus(`Error creating slideshow: ${error.message}`, 'danger');
            }
        }

        // Create montage from selected videos
        async function createMontageFromSelected() {
            if (selectedVideos.size === 0) {
                showStatus('Please select at least one video', 'warning');
                return;
            }

            const modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header bg-danger text-white">
                            <h5 class="modal-title"><i class="bi bi-film me-2"></i>Create Video Montage</h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="alert alert-info">
                                <i class="bi bi-info-circle me-2"></i>
                                Creating montage from ${selectedVideos.size} selected video${selectedVideos.size > 1 ? 's' : ''}
                            </div>
                            
                            <div class="row g-3">
                                <div class="col-md-6">
                                    <label class="form-label">Transition Effect</label>
                                    <select id="montageTransition" class="form-select">
                                        <option value="fade">Fade</option>
                                        <option value="dissolve">Dissolve</option>
                                        <option value="wipeleft">Wipe Left</option>
                                        <option value="wiperight">Wipe Right</option>
                                    </select>
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Duration per Clip (seconds)</label>
                                    <input type="number" id="montageDuration" class="form-control" value="5" min="1" max="30" step="0.5">
                                </div>
                                <div class="col-12">
                                    <label class="form-label">Output Filename</label>
                                    <input type="text" id="montageFilename" class="form-control" placeholder="montage.mp4">
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-danger" onclick="submitMontageCreation()">
                                <i class="bi bi-play-circle me-2"></i>Create Montage
                            </button>
                        </div>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            const bsModal = new bootstrap.Modal(modal);
            bsModal.show();
            modal.addEventListener('hidden.bs.modal', () => modal.remove());
        }

        // Submit montage creation
        async function submitMontageCreation() {
            const transition = document.getElementById('montageTransition').value;
            const duration = parseFloat(document.getElementById('montageDuration').value);
            const filename = document.getElementById('montageFilename').value || 'montage.mp4';

            try {
                showStatus('Creating video montage...', 'info');
                
                const response = await fetch('/create_montage', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        video_ids: Array.from(selectedVideos),
                        duration_per_clip: duration,
                        transition: transition,
                        output_filename: filename
                    })
                });

                const data = await response.json();
                
                if (!response.ok) {
                    showStatus(`Error: ${data.error}`, 'danger');
                    return;
                }
                
                // Show success with download link and searchability info
                const downloadLink = data.download_url ? 
                    `<br><a href="${data.download_url}" class="btn btn-danger btn-sm mt-2" download><i class="bi bi-download me-2"></i>Download (${data.file_size_mb} MB)</a>` : '';
                
                const searchInfo = data.searchable ? 
                    '<br><small class="text-success"><i class="bi bi-check-circle me-1"></i>Uploaded to cloud storage & AI indexing started - will be searchable soon!</small>' : '';
                
                showStatus(`✅ ${data.message}! Duration: ${Math.round(data.estimated_duration)}s${downloadLink}${searchInfo}`, 'success', 12000);
                bootstrap.Modal.getInstance(document.querySelector('.modal.show')).hide();
                
                // Refresh slideshow list (which also shows montages)
                loadCreatedSlideshows();
                
                // Clear selections
                document.querySelectorAll('.video-select-checkbox:checked').forEach(checkbox => {
                    checkbox.checked = false;
                });
                updateVideoSelection();
                
            } catch (error) {
                console.error('Montage creation error:', error);
                showStatus(`Error creating montage: ${error.message}`, 'danger');
            }
        }

        // Show Slideshow Creator Modal
        function showSlideshowCreator() {
            const modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header bg-success text-white">
                            <h5 class="modal-title"><i class="bi bi-images me-2"></i>Create Photo Slideshow</h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="alert alert-info">
                                <i class="bi bi-info-circle me-2"></i>
                                Select photos to create an animated slideshow video
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label"><strong>Photo Selection</strong></label>
                                <div id="slideshowPhotoList" class="border rounded p-3" style="max-height: 300px; overflow-y: auto;">
                                    <div class="text-center text-muted py-4">
                                        <div class="spinner-border spinner-border-sm" role="status"></div>
                                        <p class="mt-2">Loading photos...</p>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="row g-3">
                                <div class="col-md-6">
                                    <label class="form-label">Transition Effect</label>
                                    <select id="slideshowTransition" class="form-select">
                                        <option value="fade">Fade</option>
                                        <option value="dissolve">Dissolve</option>
                                        <option value="slide">Slide</option>
                                    </select>
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Duration per Photo (seconds)</label>
                                    <input type="number" id="slideshowDuration" class="form-control" value="3" min="1" max="10" step="0.5">
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Resolution</label>
                                    <select id="slideshowResolution" class="form-select">
                                        <option value="1920x1080">1920x1080 (Full HD)</option>
                                        <option value="1280x720">1280x720 (HD)</option>
                                        <option value="3840x2160">3840x2160 (4K)</option>
                                    </select>
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">Output Filename</label>
                                    <input type="text" id="slideshowOutputName" class="form-control" value="my_slideshow.mp4" placeholder="slideshow.mp4">
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button>
                            <button type="button" class="btn btn-success" onclick="createSlideshow()">
                                <i class="bi bi-images me-2"></i>Create Slideshow
                            </button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
            const bsModal = new bootstrap.Modal(modal);
            bsModal.show();
            modal.addEventListener('hidden.bs.modal', () => modal.remove());
            
            // Load available photos
            loadPhotosForSlideshow();
        }

        // Load Photos for Slideshow
        async function loadPhotosForSlideshow() {
            try {
                const response = await fetch('/albums');
                const data = await response.json();
                
                const container = document.getElementById('slideshowPhotoList');
                let html = '';
                
                if (data.albums && data.albums.length > 0) {
                    for (const album of data.albums) {
                        const albumResponse = await fetch(`/album/${encodeURIComponent(album)}`);
                        const albumData = await albumResponse.json();
                        
                        const photos = (albumData.media || []).filter(m => m.file_type === 'photo');
                        
                        if (photos.length > 0) {
                            html += `<div class="mb-3"><strong>${album}</strong></div>`;
                            photos.forEach(photo => {
                                html += `
                                    <div class="form-check mb-2">
                                        <input class="form-check-input slideshow-photo-check" type="checkbox" 
                                               value="${photo.id}" id="slideshow-photo-${photo.id}">
                                        <label class="form-check-label" for="slideshow-photo-${photo.id}">
                                            ${photo.file_name}
                                        </label>
                                    </div>
                                `;
                            });
                        }
                    }
                }
                
                if (!html) {
                    html = '<p class="text-muted text-center py-4">No photos available</p>';
                }
                
                container.innerHTML = html;
            } catch (error) {
                console.error('Error loading photos:', error);
                document.getElementById('slideshowPhotoList').innerHTML = 
                    '<p class="text-danger text-center py-4">Error loading photos</p>';
            }
        }

        // Create Slideshow
        async function createSlideshow() {
            try {
                const selectedPhotos = Array.from(document.querySelectorAll('.slideshow-photo-check:checked'))
                    .map(cb => parseInt(cb.value));
                
                if (selectedPhotos.length < 2) {
                    showStatus('Please select at least 2 photos for slideshow', 'warning');
                    return;
                }
                
                const transition = document.getElementById('slideshowTransition').value;
                const duration = parseFloat(document.getElementById('slideshowDuration').value);
                const resolution = document.getElementById('slideshowResolution').value;
                const outputName = document.getElementById('slideshowOutputName').value || 'slideshow.mp4';
                
                showStatus(`Creating slideshow with ${selectedPhotos.length} photos...`, 'info');
                
                const response = await fetch('/create_slideshow', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        photo_ids: selectedPhotos,
                        duration_per_photo: duration,
                        transition: transition,
                        resolution: resolution,
                        output_name: outputName
                    })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    showStatus(`Error: ${data.error}`, 'danger');
                    return;
                }
                
                showStatus(`✅ ${data.message}! Estimated duration: ${Math.round(data.estimated_duration)}s`, 'success');
                bootstrap.Modal.getInstance(document.querySelector('.modal.show')).hide();
            } catch (error) {
                console.error('Slideshow creation error:', error);
                showStatus(`Error creating slideshow: ${error.message}`, 'danger');
            }
        }

        // Show Bulk Clip Extractor (placeholder for future enhancement)
        function showBulkClipExtractor() {
            showStatus('Batch Clip Extraction feature coming soon! Use the "Clip" button on individual videos for now.', 'info');
        }

        // ====================================================================
        // PROCESSING OVERLAY FUNCTIONS - Full Page Block During Processing
        // ====================================================================
        
        let processingStartTime = null;
        let estimatedTotalTime = null;
        
        /**
         * Show the processing overlay and block UI
         */
        function showProcessingOverlay(files, totalSize) {
            processingStartTime = Date.now();
            
            // Calculate estimated time based on file size
            // Rough estimates from performance test:
            // - Upload: varies by network
            // - Compression: 0.28 MB/s (if needed)
            // - Slicing: 236 MB/s (very fast)
            // - Indexing: ~15-45 minutes for large files
            
            const totalSizeMB = totalSize / (1024 * 1024);
            const hasVideo = files.some(f => f.type.startsWith('video/'));
            
            // Estimate total time (very rough)
            let estimatedMinutes = 2; // Base upload time
            
            if (hasVideo) {
                if (totalSizeMB > 1000) {
                    // Large video - may need compression
                    estimatedMinutes += Math.ceil(totalSizeMB * 1.2); // ~1.2 min per MB for compression
                } else {
                    estimatedMinutes += Math.ceil(totalSizeMB * 0.1); // Just upload + indexing
                }
            }
            
            estimatedTotalTime = estimatedMinutes * 60 * 1000; // Convert to ms
            
            // Show overlay
            const overlay = document.getElementById('processingOverlay');
            overlay.style.display = 'flex';
            
            // Initialize steps
            setStepState('upload', 'pending');
            setStepState('compress', 'pending');
            setStepState('slice', 'pending');
            setStepState('index', 'pending');
            setStepState('complete', 'pending');
            
            // Update time estimate
            updateTimeEstimate();
            
            // Clear log
            document.getElementById('overlayDetailLog').innerHTML = '';
            
            // Add initial log entry
            addDetailLogEntry('init', `Starting upload for ${files.length} file(s), total size: ${totalSizeMB.toFixed(2)} MB`);
            
            // Disable body scroll
            document.body.style.overflow = 'hidden';
        }
        
        /**
         * Update processing overlay with current progress
         */
        function updateProcessingOverlay(stage, percent, message) {
            // Update progress bar
            const progressBar = document.getElementById('overlayProgressBar');
            progressBar.style.width = `${percent}%`;
            progressBar.querySelector('span').textContent = `${percent}%`;
            
            // Update status message
            const stageNames = {
                'init': 'Initializing',
                'validate': 'Validating Files',
                'slice': 'Slicing Video',
                'upload': 'Uploading to Cloud',
                'compress': 'Compressing Video',
                'metadata': 'Storing Metadata',
                'embedding': 'Creating AI Index',
                'embed': 'Creating AI Index',
                'complete': 'Complete',
                'error': 'Error'
            };
            
            document.getElementById('overlayStatusTitle').textContent = stageNames[stage] || 'Processing';
            document.getElementById('overlayStatusMessage').textContent = message;
            
            // Update step indicators
            if (percent < 20) {
                setStepState('upload', 'active');
            } else if (percent < 40 && (stage === 'compress' || message.toLowerCase().includes('compress'))) {
                setStepState('upload', 'completed');
                setStepState('compress', 'active');
            } else if (percent < 40 && (stage === 'slice' || message.toLowerCase().includes('slice') || message.toLowerCase().includes('chunk'))) {
                setStepState('upload', 'completed');
                setStepState('compress', 'skipped');
                setStepState('slice', 'active');
            } else if (percent < 50) {
                setStepState('upload', 'completed');
                if (stage === 'compress' || message.toLowerCase().includes('compress')) {
                    setStepState('compress', 'completed');
                } else {
                    setStepState('compress', 'skipped');
                }
                if (stage === 'slice' || message.toLowerCase().includes('slice')) {
                    setStepState('slice', 'completed');
                } else {
                    setStepState('slice', 'skipped');
                }
            } else if (percent < 95) {
                setStepState('upload', 'completed');
                setStepState('compress', 'completed');
                setStepState('slice', 'skipped');
                setStepState('index', 'active');
            } else {
                setStepState('upload', 'completed');
                setStepState('compress', 'skipped');
                setStepState('slice', 'skipped');
                setStepState('index', 'completed');
                setStepState('complete', 'active');
            }
            
            // Add to detail log
            addDetailLogEntry(stage, message);
            
            // Update time estimate
            updateTimeEstimate();
        }
        
        /**
         * Set step state (pending, active, completed, skipped, error)
         */
        function setStepState(stepName, state) {
            const step = document.getElementById(`step-${stepName}`);
            if (!step) return;
            
            // Remove all state classes
            step.classList.remove('pending', 'active', 'completed', 'skipped', 'error');
            
            // Add new state
            step.classList.add(state);
            
            // Update status text
            const statusEl = step.querySelector('.step-status');
            const statusText = {
                'pending': '',
                'active': '⏳ In progress',
                'completed': '✅ Done',
                'skipped': '⊘ Skipped',
                'error': '❌ Failed'
            };
            statusEl.textContent = statusText[state] || '';
        }
        
        /**
         * Add entry to detail log
         */
        function addDetailLogEntry(stage, message) {
            const logDiv = document.getElementById('overlayDetailLog');
            const timestamp = new Date().toLocaleTimeString();
            
            const entry = document.createElement('div');
            entry.style.marginBottom = '4px';
            entry.style.padding = '4px 0';
            entry.style.borderBottom = '1px solid #e5e7eb';
            
            const stageColors = {
                'init': '#3b82f6',
                'validate': '#8b5cf6',
                'slice': '#f59e0b',
                'upload': '#6366f1',
                'compress': '#f59e0b',
                'metadata': '#ec4899',
                'embedding': '#3b82f6',
                'embed': '#3b82f6',
                'complete': '#10b981',
                'error': '#ef4444'
            };
            
            entry.innerHTML = `
                <span style="color: #6b7280; margin-right: 8px;">${timestamp}</span>
                <span style="color: ${stageColors[stage] || '#6b7280'}; font-weight: 600; margin-right: 8px;">[${stage.toUpperCase()}]</span>
                <span>${message}</span>
            `;
            
            logDiv.appendChild(entry);
            
            // Auto-scroll to bottom
            logDiv.scrollTop = logDiv.scrollHeight;
        }
        
        /**
         * Update time estimate display
         */
        function updateTimeEstimate() {
            if (!processingStartTime || !estimatedTotalTime) return;
            
            const elapsed = Date.now() - processingStartTime;
            const remaining = Math.max(0, estimatedTotalTime - elapsed);
            
            const minutes = Math.floor(remaining / 60000);
            const seconds = Math.floor((remaining % 60000) / 1000);
            
            const timeEstDiv = document.getElementById('overlayTimeEstimate');
            const timeText = document.getElementById('estimatedTime');
            
            if (remaining > 5000) {
                timeEstDiv.style.display = 'block';
                if (minutes > 0) {
                    timeText.textContent = `Estimated time remaining: ${minutes}m ${seconds}s`;
                } else {
                    timeText.textContent = `Estimated time remaining: ${seconds}s`;
                }
            } else {
                timeEstDiv.style.display = 'block';
                timeText.textContent = 'Almost done...';
            }
        }
        
        /**
         * Hide processing overlay
         */
        function hideProcessingOverlay() {
            const overlay = document.getElementById('processingOverlay');
            overlay.style.display = 'none';
            
            // Re-enable body scroll
            document.body.style.overflow = '';
            
            // Reset variables
            processingStartTime = null;
            estimatedTotalTime = null;
        }
        
        /**
         * Cancel processing (optional - for future implementation)
         */
        function cancelProcessing() {
            if (confirm('Are you sure you want to cancel? This may leave incomplete uploads.')) {
                hideProcessingOverlay();
                showUploadResults('Processing canceled by user', 'error');
            }
        }

        /* ========================================
         * Camera Search Functionality with Real-Time Face Detection
         * ======================================== */
        
        let cameraStream = null;
        let capturedImageData = null;
        let faceDetectionInterval = null;
        let modelsLoaded = false;

        // Load face-api.js models
        async function loadFaceDetectionModels() {
            if (modelsLoaded) return true;
            
            try {
                const MODEL_URL = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api/model';
                await faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL);
                modelsLoaded = true;
                console.log('✅ Face detection models loaded');
                return true;
            } catch (error) {
                console.error('❌ Error loading face detection models:', error);
                return false;
            }
        }

        // Detect faces in real-time and draw overlay
        async function detectFacesRealtime() {
            const video = document.getElementById('video');
            const overlay = document.getElementById('faceOverlay');
            const faceStatus = document.getElementById('faceStatus');
            const captureBtn = document.getElementById('captureBtn');
            
            if (!video || video.paused || video.ended) return;
            
            try {
                const detections = await faceapi.detectAllFaces(
                    video, 
                    new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.5 })
                );
                
                // Clear overlay
                const ctx = overlay.getContext('2d');
                ctx.clearRect(0, 0, overlay.width, overlay.height);
                
                if (detections.length > 0) {
                    // Draw bounding boxes for all detected faces
                    ctx.strokeStyle = '#00ff00';
                    ctx.lineWidth = 3;
                    ctx.font = '16px Arial';
                    ctx.fillStyle = '#00ff00';
                    
                    detections.forEach((detection, i) => {
                        const box = detection.box;
                        ctx.strokeRect(box.x, box.y, box.width, box.height);
                        ctx.fillText(`Face ${i + 1}`, box.x, box.y - 5);
                    });
                    
                    // Show status and enable capture
                    faceStatus.style.display = 'block';
                    faceStatus.innerHTML = `<span class="badge bg-success">
                        <i class="bi bi-check-circle"></i> ${detections.length} Face(s) Detected
                    </span>`;
                    captureBtn.disabled = false;
                } else {
                    faceStatus.style.display = 'block';
                    faceStatus.innerHTML = `<span class="badge bg-warning">
                        <i class="bi bi-exclamation-triangle"></i> No Face Detected
                    </span>`;
                    captureBtn.disabled = true;
                }
            } catch (error) {
                console.error('Face detection error:', error);
            }
        }

        // Initialize camera search when tab is shown
        let cameraSearchInitialized = false;
        
        document.addEventListener('DOMContentLoaded', () => {
            const cameraTab = document.querySelector('a[href="#camera-search-tab"]');
            if (cameraTab) {
                // Bootstrap 5 tab event
                cameraTab.addEventListener('shown.bs.tab', (e) => {
                    if (!cameraSearchInitialized) {
                        initCameraSearch();
                        cameraSearchInitialized = true;
                    }
                });
                
                // Also try to initialize on click as fallback
                cameraTab.addEventListener('click', () => {
                    setTimeout(() => {
                        if (!cameraSearchInitialized) {
                            initCameraSearch();
                            cameraSearchInitialized = true;
                        }
                    }, 100);
                });
            }
            
            // Also initialize if we're already on the camera tab
            const cameraTabPane = document.getElementById('camera-search-tab');
            if (cameraTabPane && cameraTabPane.classList.contains('active')) {
                initCameraSearch();
                cameraSearchInitialized = true;
            }
        });

        function initCameraSearch() {
            console.log('🎥 Initializing camera search...');
            
            const video = document.getElementById('video');
            const canvas = document.getElementById('canvas');
            const overlay = document.getElementById('faceOverlay');
            const capturedImage = document.getElementById('capturedImage');
            const startCameraBtn = document.getElementById('startCamera');
            const captureBtn = document.getElementById('captureBtn');
            const searchBtn = document.getElementById('searchBtn');
            const retakeBtn = document.getElementById('retakeBtn');
            const cameraStatus = document.getElementById('cameraStatus');
            const faceStatus = document.getElementById('faceStatus');
            const thresholdInput = document.getElementById('threshold');
            const thresholdValue = document.getElementById('thresholdValue');

            console.log('Camera elements:', { 
                video: !!video, 
                startCameraBtn: !!startCameraBtn, 
                captureBtn: !!captureBtn 
            });

            // Update threshold display
            if (thresholdInput) {
                thresholdInput.addEventListener('input', (e) => {
                    const value = (1 - parseFloat(e.target.value)) * 100;
                    thresholdValue.textContent = Math.round(value) + '%';
                });
            }

            // Start camera
            if (startCameraBtn) {
                console.log('✅ Attaching click handler to Start Camera button');
                startCameraBtn.onclick = async () => {
                    console.log('📹 Start Camera button clicked');
                    try {
                        // Load face detection models first
                        showCameraStatus('📦 Loading face detection models...', 'info');
                        const loaded = await loadFaceDetectionModels();
                        if (!loaded) {
                            showCameraStatus('❌ Failed to load face detection models', 'danger');
                            return;
                        }

                        cameraStream = await navigator.mediaDevices.getUserMedia({ 
                            video: { 
                                width: { ideal: 1280 },
                                height: { ideal: 720 },
                                facingMode: 'user'
                            } 
                        });
                        
                        video.srcObject = cameraStream;
                        await video.play();
                        
                        // Setup overlay canvas to match video
                        video.addEventListener('loadedmetadata', () => {
                            overlay.width = video.videoWidth;
                            overlay.height = video.videoHeight;
                            overlay.style.width = video.offsetWidth + 'px';
                            overlay.style.height = video.offsetHeight + 'px';
                        });
                        
                        video.style.display = 'block';
                        overlay.style.display = 'block';
                        capturedImage.style.display = 'none';
                        faceStatus.style.display = 'none';
                        startCameraBtn.disabled = true;
                        
                        showCameraStatus('📹 Camera active - Position your face in the frame', 'info');
                        
                        // Start real-time face detection
                        faceDetectionInterval = setInterval(detectFacesRealtime, 300); // Check every 300ms
                    } catch (error) {
                        const isSecure = window.location.protocol === 'https:';
                        const errorMsg = isSecure 
                            ? 'Camera access denied. Please allow camera access in your browser settings.'
                            : '🔒 Camera requires HTTPS. Please access via https://' + window.location.hostname + ':8443';
                        showCameraStatus(errorMsg, 'danger');
                    }
                };
            }

            // Capture photo
            if (captureBtn) {
                captureBtn.onclick = async () => {
                    // Stop face detection
                    if (faceDetectionInterval) {
                        clearInterval(faceDetectionInterval);
                        faceDetectionInterval = null;
                    }
                    
                    // Detect face one more time to get bounding box
                    const detections = await faceapi.detectAllFaces(
                        video,
                        new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.5 })
                    );
                    
                    if (detections.length === 0) {
                        showCameraStatus('⚠️ No face detected. Please try again.', 'warning');
                        return;
                    }
                    
                    // Use the largest detected face
                    const detection = detections.reduce((prev, curr) => 
                        curr.box.width * curr.box.height > prev.box.width * prev.box.height ? curr : prev
                    );
                    
                    const box = detection.box;
                    
                    // Capture full frame
                    canvas.width = video.videoWidth;
                    canvas.height = video.videoHeight;
                    const ctx = canvas.getContext('2d');
                    ctx.drawImage(video, 0, 0);
                    
                    // Crop to face region with some padding
                    const padding = 50;
                    const cropX = Math.max(0, box.x - padding);
                    const cropY = Math.max(0, box.y - padding);
                    const cropW = Math.min(canvas.width - cropX, box.width + padding * 2);
                    const cropH = Math.min(canvas.height - cropY, box.height + padding * 2);
                    
                    const croppedCanvas = document.createElement('canvas');
                    croppedCanvas.width = cropW;
                    croppedCanvas.height = cropH;
                    const croppedCtx = croppedCanvas.getContext('2d');
                    croppedCtx.drawImage(canvas, cropX, cropY, cropW, cropH, 0, 0, cropW, cropH);
                    
                    capturedImageData = croppedCanvas.toDataURL('image/jpeg', 0.9);
                    capturedImage.src = capturedImageData;
                    capturedImage.style.display = 'block';
                    video.style.display = 'none';
                    overlay.style.display = 'none';
                    faceStatus.style.display = 'none';
                    
                    captureBtn.style.display = 'none';
                    searchBtn.style.display = 'inline-block';
                    retakeBtn.style.display = 'inline-block';
                    
                    // Stop camera
                    if (cameraStream) {
                        cameraStream.getTracks().forEach(track => track.stop());
                    }
                    
                    showCameraStatus('✅ Face captured! Click "Search My Photos" to find matches', 'success');
                };
            }

            // Retake photo
            if (retakeBtn) {
                retakeBtn.onclick = () => {
                    capturedImage.style.display = 'none';
                    searchBtn.style.display = 'none';
                    retakeBtn.style.display = 'none';
                    captureBtn.style.display = 'inline-block';
                    captureBtn.disabled = true;
                    startCameraBtn.disabled = false;
                    startCameraBtn.click();
                };
            }

            // Search photos
            if (searchBtn) {
                searchBtn.onclick = async () => {
                    if (!capturedImageData) {
                        showCameraStatus('Please capture a photo first', 'danger');
                        return;
                    }

                    showCameraStatus('🔍 Searching for photos... This may take a moment', 'info');
                    searchBtn.disabled = true;

                    try {
                        const response = await fetch('/api/search/selfie', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                image: capturedImageData,
                                similarity_threshold: parseFloat(thresholdInput.value),
                                max_results: 100
                            })
                        });

                        if (!response.ok) {
                            const errorText = await response.text();
                            console.error('Camera search failed:', response.status, errorText);
                            
                            if (response.status === 404) {
                                showCameraStatus('❌ Camera search feature is not yet available. The backend endpoint /api/search/selfie needs to be implemented.', 'danger');
                            } else {
                                showCameraStatus(`❌ Server error: ${response.status}`, 'danger');
                            }
                            return;
                        }
                        
                        const contentType = response.headers.get('content-type');
                        if (!contentType || !contentType.includes('application/json')) {
                            console.error('Invalid response type:', contentType);
                            const text = await response.text();
                            console.error('Response body:', text.substring(0, 200));
                            showCameraStatus('❌ Server returned invalid response (not JSON)', 'danger');
                            return;
                        }

                        const result = await response.json();
                        
                        console.log('Camera search response:', result);
                        console.log('Success:', result.success);
                        console.log('Photos:', result.photos);
                        console.log('Unique photos:', result.unique_photos);
                        console.log('Matches found:', result.matches_found);

                        if (result.success) {
                            // Display results in the main results tab
                            displayCameraSearchResults(result);
                            // Switch to results tab
                            const resultsTab = document.querySelector('a[href="#results-tab"]');
                            if (resultsTab) {
                                const tab = new bootstrap.Tab(resultsTab);
                                tab.show();
                            }
                            showCameraStatus(`✅ Found ${result.unique_photos} photos! Check the Results tab`, 'success');
                        } else {
                            showCameraStatus('❌ ' + (result.error || 'Search failed'), 'danger');
                        }
                    } catch (error) {
                        console.error('Camera search error:', error);
                        showCameraStatus('❌ Error: ' + error.message, 'danger');
                    } finally {
                        searchBtn.disabled = false;
                    }
                };
            }
        }

        function showCameraStatus(message, type) {
            const statusDiv = document.getElementById('cameraStatus');
            if (statusDiv) {
                statusDiv.textContent = message;
                statusDiv.className = `alert alert-${type}`;
                statusDiv.style.display = 'block';
            }
        }

        function displayCameraSearchResults(result) {
            const resultsContainer = document.getElementById('resultsContainer');
            if (!resultsContainer) return;

            resultsContainer.innerHTML = '';

            // Add header
            const header = document.createElement('div');
            header.className = result.photos && result.photos.length > 0 ? 'alert alert-success mb-4' : 'alert alert-info mb-4';
            const photoCount = result.unique_photos || result.photos?.length || 0;
            const matchCount = result.matches_found || 0;
            header.innerHTML = `
                <h5><i class="bi bi-camera-fill me-2"></i>Camera Search Results</h5>
                <p class="mb-0">Found ${photoCount} photos with ${matchCount} face matches</p>
            `;
            resultsContainer.appendChild(header);

            if (!result.photos || result.photos.length === 0) {
                resultsContainer.innerHTML += '<div class="alert alert-info">No matching photos found. Try adjusting the match sensitivity.</div>';
                return;
            }

            // Create gallery grid
            const grid = document.createElement('div');
            grid.className = 'row g-3';

            result.photos.forEach(photo => {
                console.log('Rendering photo:', photo);
                const col = document.createElement('div');
                col.className = 'col-6 col-md-4 col-lg-3';
                
                const bestMatch = photo.matched_faces && photo.matched_faces[0] ? photo.matched_faces[0] : {confidence: 0};
                const confidence = Math.round(bestMatch.confidence * 100);
                
                // Use thumbnail URL from backend response, fallback to constructing it
                const imageUrl = photo.thumbnail_url || `/media_thumbnail/${photo.media_id}`;
                const streamUrl = photo.stream_url || '#';
                
                console.log(`📸 Using thumbnail URL: ${imageUrl} for media_id: ${photo.media_id}`);
                
                col.innerHTML = `
                    <div class="card h-100 shadow-sm hover-lift camera-search-card" style="cursor: pointer;" data-stream-url="${streamUrl}">
                        <div class="position-relative" style="height: 200px; background: #f0f0f0; overflow: hidden;">
                            <img src="${imageUrl}" 
                                 class="card-img-top main-image" 
                                 alt="${photo.file_name || 'Photo'}" 
                                 style="width: 100%; height: 200px; object-fit: cover; display: block; position: relative; z-index: 1;" 
                                 loading="lazy">
                        </div>
                        <div class="card-body">
                            <h6 class="card-title text-truncate">${photo.file_name}</h6>
                            <div class="mb-2">
                                ${photo.matched_faces.map(face => 
                                    `<span class="badge bg-primary me-1">${face.face_name} (${Math.round(face.confidence * 100)}%)</span>`
                                ).join('')}
                            </div>
                            <div class="progress" style="height: 6px;">
                                <div class="progress-bar bg-success" role="progressbar" style="width: ${confidence}%"></div>
                            </div>
                            <small class="text-muted">${photo.match_count} match(es)</small>
                        </div>
                    </div>
                `;
                
                // Add error handler for image
                const img = col.querySelector('.main-image');
                console.log('Setting up image handlers for:', imageUrl);
                
                img.addEventListener('load', function() {
                    console.log('✅ Camera search image loaded:', imageUrl);
                    this.classList.add('loaded'); // Add loaded class to make image visible
                });
                
                img.addEventListener('error', function(e) {
                    console.error('❌ Camera search image failed to load:', imageUrl, e);
                    this.parentElement.innerHTML = '<i class="bi bi-image-fill text-danger" style="font-size: 3rem; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);" title="Image failed to load"></i>';
                });
                
                // Add click handler
                const card = col.querySelector('.camera-search-card');
                card.addEventListener('click', function() {
                    const url = this.dataset.streamUrl;
                    if (url && url !== '#') {
                        window.open(url, '_blank');
                    }
                });
                
                grid.appendChild(col);
            });

            resultsContainer.appendChild(grid);
        }

        // Progressive Image Loading Enhancement
        function setupProgressiveLoading() {
            const mainImages = document.querySelectorAll('.main-image');
            mainImages.forEach(img => {
                if (img.complete) {
                    img.classList.add('loaded');
                } else {
                    img.addEventListener('load', function() {
                        this.classList.add('loaded');
                    });
                }
            });
        }

        // Setup progressive loading when new images are added
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                    setupProgressiveLoading();
                }
            });
        });

        // Observe changes to the results container
        const resultsContainer = document.getElementById('searchResults');
        if (resultsContainer) {
            observer.observe(resultsContainer, { childList: true, subtree: true });
        }

        // Initial setup
        setupProgressiveLoading();

})();

console.log("✅ app.js loaded successfully");
