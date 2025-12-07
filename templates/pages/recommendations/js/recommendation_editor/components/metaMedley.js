/**
 * Meta-Medley Component
 *
 * Manages meta-medley panel functionality including:
 * - Panel loading and display
 * - Sequential audio playback across segments
 * - Transcript highlighting (karaoke style)
 * - Avatar group highlighting
 *
 * Extracted from lines 2420-2889 of original code.
 */

import { AppState } from '../state.js';
import { Logger } from '../utils/logger.js';
import { CONFIG } from '../config.js';
import { formatTime, getAllAvatarElements } from '../utils/dom.js';
import { fetchMetaMedleyPanel } from '../services/api.js';
import {
    applyGroupAvatarFocus,
    clearGroupAvatarFocus,
    repositionAllAvatarsAfterResize
} from './avatars.js';
import { loadParticipantModal } from './modals.js';

/**
 * Audio state for meta-medley playback
 */
let metaMedleyAudioState = null;

/**
 * Set loading state for medley button
 *
 * @param {HTMLElement} button - Button element
 * @param {boolean} isLoading - Loading state
 */
function setMedleyButtonLoading(button, isLoading) {
    if (!button) {
        return;
    }

    if (isLoading) {
        if (!button.dataset.originalHtml) {
            button.dataset.originalHtml = button.innerHTML;
        }
        button.classList.add('disabled', 'loading');
        button.innerHTML = `
            <span class="medley-spinner"><i class="fas fa-circle-notch fa-spin"></i></span>
            <span class="medley-label">Loading...</span>
        `;
    } else {
        button.classList.remove('disabled', 'loading');
        if (button.dataset.originalHtml) {
            button.innerHTML = button.dataset.originalHtml;
        }
    }
}

/**
 * Show meta-medley panel loading indicator
 */
function showMetaMedleyPanelLoading() {
    const loading = document.getElementById('meta-medley-panel-loading');
    if (loading) {
        loading.style.display = 'flex';
    }
}

/**
 * Hide meta-medley panel loading indicator
 */
function hideMetaMedleyPanelLoading() {
    const loading = document.getElementById('meta-medley-panel-loading');
    if (loading) {
        loading.style.display = 'none';
    }
}

/**
 * Open meta-medley panel
 *
 * @param {number} recommendationId - Recommendation ID
 * @param {string} medleyType - Type of medley ('bottom', 'middle', 'top')
 * @param {HTMLElement} sourceButton - Button that triggered the panel
 */
export async function openMetaMedleyPanel(recommendationId, medleyType, sourceButton) {
    Logger.debug('=== BUTTON CLICKED ===');
    Logger.debug(`Opening meta-medley panel: ${medleyType}`, recommendationId);

    const url = `/api/meta-medley/${recommendationId}/${medleyType}/`;
    Logger.debug('Fetching from URL:', url);

    // Add body class to trigger chart resize
    document.body.classList.add('meta-panel-open');

    // Trigger avatar repositioning after CSS transition completes
    setTimeout(() => repositionAllAvatarsAfterResize(), CONFIG.DELAYS.CHART_RESIZE);

    // Show alert to confirm function is called
    Logger.debug('Starting fetch request...');
    const targetButton = sourceButton || document.querySelector(`.medley-button[data-medley-type="${medleyType}"]`);
    setMedleyButtonLoading(targetButton, true);

    // Show panel loading indicator
    showMetaMedleyPanelLoading();

    AppState.metaMedley.activeGroup = medleyType;
    AppState.metaMedley.panelLoading = true;
    AppState.metaMedley.panelOpen = false;
    applyGroupAvatarFocus(medleyType);

    try {
        // Fetch panel content
        const response = await fetch(url);
        Logger.debug('Response received:', response.status);
        const html = await response.text();
        Logger.debug('HTML received, length:', html.length);

        // Remove existing panel if any
        const existingPanel = document.getElementById('meta-medley-panel-container');
        if (existingPanel) {
            existingPanel.remove();
        }

        // Create panel container
        const panelContainer = document.createElement('div');
        panelContainer.id = 'meta-medley-panel-container';
        panelContainer.innerHTML = html;
        document.body.appendChild(panelContainer);

        // Execute any script tags in the inserted HTML
        const scripts = panelContainer.querySelectorAll('script');
        scripts.forEach(script => {
            const newScript = document.createElement('script');
            if (script.src) {
                newScript.src = script.src;
            } else {
                newScript.textContent = script.textContent;
            }
            document.body.appendChild(newScript);
            document.body.removeChild(newScript); // Execute and remove
        });

        Logger.debug('Panel appended to body');
        Logger.debug('Segments data available:', !!AppState.metaMedley.segmentsData);
        Logger.debug('Participants data available:', !!AppState.metaMedley.participantsData);

        // Wait for scripts in the HTML to execute before initializing
        setTimeout(() => {
            Logger.debug('Initializing panel after delay...');
            Logger.debug('Segments data NOW:', !!AppState.metaMedley.segmentsData);
            Logger.debug('Participants data NOW:', !!AppState.metaMedley.participantsData);

            AppState.metaMedley.panelLoading = false;
            AppState.metaMedley.panelOpen = true;
            applyGroupAvatarFocus(AppState.metaMedley.activeGroup);

            // Hide panel loading indicator
            hideMetaMedleyPanelLoading();

            // Highlight corresponding avatars
            highlightMetaMedleyAvatars(medleyType);

            // Initialize panel functionality
            initializeMetaMedleyPanel();
        }, CONFIG.DELAYS.PANEL_INIT);

    } catch (error) {
        Logger.error('Failed to load meta-medley panel:', error);
        AppState.metaMedley.panelLoading = false;
        AppState.metaMedley.panelOpen = false;
        AppState.metaMedley.activeGroup = null;
        clearGroupAvatarFocus();

        // Hide panel loading indicator on error
        hideMetaMedleyPanelLoading();
    } finally {
        setMedleyButtonLoading(targetButton, false);
    }
}

/**
 * Close meta-medley panel
 */
export function closeMetaMedleyPanel() {
    cleanupMetaMedleyAudio();
    document.removeEventListener('click', handleOutsideClick);

    const panel = document.getElementById('meta-medley-panel-container');
    if (panel) {
        panel.remove();
    }

    // Remove avatar highlighting
    getAllAvatarElements().forEach(avatar => {
        avatar.classList.remove('meta-medley-highlight');
    });
    clearGroupAvatarFocus();
    AppState.metaMedley.panelOpen = false;
    AppState.metaMedley.panelLoading = false;
    AppState.metaMedley.activeGroup = null;

    // Remove body class to restore chart width
    document.body.classList.remove('meta-panel-open');

    // Trigger avatar repositioning after CSS transition completes
    setTimeout(() => repositionAllAvatarsAfterResize(), CONFIG.DELAYS.CHART_RESIZE);

    // Clean up
    AppState.metaMedley.segments = null;
    AppState.metaMedley.currentSegment = 0;
}

/**
 * Highlight avatars for a medley
 *
 * @param {string} medleyType - Type of medley
 */
function highlightMetaMedleyAvatars(medleyType) {
    // Wait a bit for the panel to fully load and set state variables
    setTimeout(() => {
        if (!AppState.metaMedley.participantsData) {
            Logger.error('No participants data available');
            return;
        }

        applyGroupAvatarFocus(AppState.metaMedley.activeGroup || medleyType);
    }, CONFIG.DELAYS.MODAL_INIT);
}

/**
 * Initialize panel functionality
 */
function initializeMetaMedleyPanel() {
    setupMetaMedleyAudio();
    document.addEventListener('click', handleOutsideClick);
}

/**
 * Setup meta-medley audio playback
 */
function setupMetaMedleyAudio() {
    const panel = document.querySelector('.meta-medley-panel');
    if (!panel) {
        Logger.error('Meta-medley panel not found');
        return;
    }

    const audioElement = panel.querySelector('#meta-medley-audio');
    const audioSource = panel.querySelector('#meta-medley-source');
    const hiddenAudios = Array.from(panel.querySelectorAll('.meta-segment-audio'));
    const transcriptSegments = Array.from(panel.querySelectorAll('#meta-medley-transcript .medley-segment'));
    const playButton = panel.querySelector('#meta-medley-play-button');
    const currentTimeEl = panel.querySelector('#meta-medley-current-time');
    const totalTimeEl = panel.querySelector('#meta-medley-total-time');
    const progressFill = panel.querySelector('#meta-medley-progress-fill');

    if (!audioElement || !audioSource || hiddenAudios.length === 0) {
        Logger.error('Meta-medley audio setup incomplete');
        return;
    }

    cleanupMetaMedleyAudio();

    const segmentDurations = hiddenAudios.map(audio => parseFloat(audio.dataset.duration || '0'));
    let totalDuration = segmentDurations.reduce((sum, value) => sum + value, 0);
    if (!totalDuration && AppState.metaMedley.segmentsData) {
        totalDuration = AppState.metaMedley.segmentsData.reduce((sum, seg) => sum + (seg.duration || 0), 0);
    }

    const state = {
        audio: audioElement,
        source: audioSource,
        hiddenAudios,
        transcriptSegments,
        playButton,
        currentTimeEl,
        totalTimeEl,
        progressFill,
        segmentDurations,
        totalDuration,
        currentIndex: 0,
        isPlaying: false,
        handlers: {}
    };

    if (state.totalTimeEl) {
        state.totalTimeEl.textContent = formatTime(state.totalDuration);
    }

    const highlightSegment = (index) => {
        state.transcriptSegments.forEach(seg => seg.classList.remove('highlight'));
        if (index >= 0 && state.transcriptSegments[index]) {
            const segmentEl = state.transcriptSegments[index];
            segmentEl.classList.add('highlight');
            segmentEl.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'nearest' });
        }
    };

    const updateProgress = () => {
        const elapsedBefore = state.segmentDurations
            .slice(0, state.currentIndex)
            .reduce((sum, value) => sum + value, 0);
        const elapsed = Math.min(state.totalDuration, elapsedBefore + (state.audio.currentTime || 0));
        if (state.currentTimeEl) {
            state.currentTimeEl.textContent = formatTime(elapsed);
        }
        if (state.progressFill) {
            const progressPercent = state.totalDuration ? (elapsed / state.totalDuration) * 100 : 0;
            state.progressFill.style.width = `${Math.min(100, progressPercent)}%`;
        }
    };

    const updatePlayButton = () => {
        if (!state.playButton) return;
        if (state.isPlaying) {
            state.playButton.classList.add('is-playing');
        } else {
            state.playButton.classList.remove('is-playing');
        }
    };

    const loadSegment = (index, autoplay) => {
        const segmentAudio = state.hiddenAudios[index];
        if (!segmentAudio) {
            Logger.error('Segment audio not found for index', index);
            return;
        }
        const sourceEl = segmentAudio.querySelector('source');
        if (!sourceEl) {
            Logger.error('Source element missing for segment', index);
            return;
        }
        state.currentIndex = index;
        state.source.src = sourceEl.src;
        state.audio.load();
        highlightSegment(index);
        updateProgress();
        if (autoplay) {
            state.audio.play().catch(err => {
                Logger.error('Failed to autoplay segment:', err);
            });
        }
    };

    const onPlay = () => {
        state.isPlaying = true;
        updatePlayButton();
        highlightSegment(state.currentIndex);
    };

    const onPause = () => {
        state.isPlaying = false;
        updatePlayButton();
    };

    const onEnded = () => {
        updateProgress();
        const nextIndex = state.currentIndex + 1;
        if (nextIndex < state.hiddenAudios.length) {
            loadSegment(nextIndex, true);
        } else {
            state.isPlaying = false;
            updatePlayButton();
            highlightSegment(-1);
            state.currentIndex = 0;
            const firstSource = state.hiddenAudios[0]?.querySelector('source');
            if (firstSource) {
                state.source.src = firstSource.src;
                state.audio.load();
            }
            updateProgress();
        }
    };

    const onTimeUpdate = () => {
        updateProgress();
    };

    const togglePlayback = () => {
        if (!state.audio) return;
        if (state.isPlaying) {
            state.audio.pause();
        } else {
            state.audio.play().catch(err => Logger.error('Play failed:', err));
        }
    };

    state.handlers = { onPlay, onPause, onEnded, onTimeUpdate, togglePlayback };
    state.loadSegment = loadSegment;
    state.highlightSegment = highlightSegment;
    state.updateProgress = updateProgress;

    state.audio.addEventListener('play', onPlay);
    state.audio.addEventListener('pause', onPause);
    state.audio.addEventListener('ended', onEnded);
    state.audio.addEventListener('timeupdate', onTimeUpdate);

    if (state.playButton) {
        state.playButton.addEventListener('click', togglePlayback);
        updatePlayButton();
    }

    loadSegment(0, false);
    highlightSegment(-1);
    updateProgress();

    metaMedleyAudioState = state;
}

/**
 * Cleanup meta-medley audio state and event listeners
 */
function cleanupMetaMedleyAudio() {
    if (!metaMedleyAudioState || !metaMedleyAudioState.audio) {
        metaMedleyAudioState = null;
        return;
    }

    const state = metaMedleyAudioState;
    state.audio.pause();
    state.audio.currentTime = 0;
    if (state.handlers) {
        state.audio.removeEventListener('play', state.handlers.onPlay);
        state.audio.removeEventListener('pause', state.handlers.onPause);
        state.audio.removeEventListener('ended', state.handlers.onEnded);
        state.audio.removeEventListener('timeupdate', state.handlers.onTimeUpdate);
        if (state.playButton) {
            state.playButton.removeEventListener('click', state.handlers.togglePlayback);
        }
    }
    if (state.source) {
        state.source.src = '';
        state.audio.load();
    }
    if (state.transcriptSegments) {
        state.transcriptSegments.forEach(seg => seg.classList.remove('highlight'));
    }
    if (state.progressFill) {
        state.progressFill.style.width = '0%';
    }
    if (state.currentTimeEl) {
        state.currentTimeEl.textContent = '0:00';
    }
    if (state.playButton) {
        state.playButton.classList.remove('is-playing');
    }

    metaMedleyAudioState = null;
}

/**
 * Reset meta-medley audio to beginning
 */
export function resetMetaMedleyAudio() {
    if (!metaMedleyAudioState) return;
    const state = metaMedleyAudioState;
    state.audio.pause();
    state.audio.currentTime = 0;
    state.isPlaying = false;
    if (state.transcriptSegments) {
        state.transcriptSegments.forEach(seg => seg.classList.remove('highlight'));
    }
    if (state.loadSegment) {
        state.loadSegment(0, false);
    }
    if (state.updateProgress) {
        state.updateProgress();
    }
    if (state.playButton) {
        state.playButton.classList.remove('is-playing');
    }
}

/**
 * Initialize tab switching (Bootstrap handles the toggling)
 */
export function initializeMetaMedleyTabs() {
    return;
}

/**
 * Switch tabs
 *
 * @param {string} tabName - Name of tab to switch to
 */
export function switchMetaMedleyTab(tabName) {
    document.querySelectorAll('.panel-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    const targetTab = document.querySelector(`.panel-tab[data-tab="${tabName}"]`);
    if (targetTab) {
        targetTab.classList.add('active');
    }

    document.querySelectorAll('.panel-tab-content').forEach(content => {
        content.classList.remove('active');
    });
    const targetContent = document.getElementById(`${tabName}-tab`);
    if (targetContent) {
        targetContent.classList.add('active');
    }
}

/**
 * Handle outside clicks to close panel
 *
 * @param {Event} event - Click event
 */
function handleOutsideClick(event) {
    const panel = document.querySelector('.meta-medley-panel');
    const medleyButtons = document.querySelectorAll('.medley-button');

    if (!panel) return;

    const isOutside = !panel.contains(event.target);
    const isOnMedleyButton = Array.from(medleyButtons).some(btn => btn.contains(event.target));
    const isPlaying = metaMedleyAudioState && metaMedleyAudioState.isPlaying;

    if (isOutside && !isOnMedleyButton && !isPlaying) {
        closeMetaMedleyPanel();
    }
}

/**
 * Open individual medley
 *
 * @param {number} recommendationId - Recommendation ID
 * @param {string} participantUsername - Participant username
 */
export function openIndividualMedley(recommendationId, participantUsername) {
    closeMetaMedleyPanel();
    loadParticipantModal(participantUsername, recommendationId);
}

/**
 * Play individual medley (placeholder)
 *
 * @param {Event} event - Click event
 * @param {string} participantUsername - Participant username
 */
export function playIndividualMedley(event, participantUsername) {
    event.stopPropagation();
    Logger.debug(`Play individual medley for: ${participantUsername}`);
}
