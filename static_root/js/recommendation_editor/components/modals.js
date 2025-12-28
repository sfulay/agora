/**
 * Modals Component
 *
 * Manages participant modal creation and functionality including:
 * - Dynamic modal loading
 * - Karaoke transcript highlighting
 * - Sequential medley playback
 * - Form validation and submission
 *
 * Extracted from lines 1798-2221 of original code.
 */

import { AppState } from '../state.js';
import { Logger } from '../utils/logger.js';
import { CONFIG } from '../config.js';
import { getCSRFToken } from '../utils/dom.js';
import { fetchParticipantModal, sendConnectionRequest, submitReflection } from '../services/api.js';
import { repositionAllAvatarsAfterResize } from './avatars.js';

/**
 * Setup karaoke-style transcript highlighting
 *
 * @param {HTMLElement} modal - The modal element
 */
function setupKaraokeTranscript(modal) {
    // Add click-to-play/pause for transcript text
    modal.querySelectorAll('.karaoke-transcript-sent').forEach(function(transcriptBlock) {
        const audioId = transcriptBlock.dataset.audioId;
        const audio = modal.querySelector(`#audio-${audioId}`);
        if (!audio) return;

        transcriptBlock.style.cursor = 'pointer';
        transcriptBlock.addEventListener('click', function() {
            if (audio.paused) {
                audio.play();
            } else {
                audio.pause();
            }
        });
    });

    // Setup karaoke functionality for sentence-level highlighting
    modal.querySelectorAll('.karaoke-transcript-sent').forEach(function(transcriptBlock) {
        const audioId = transcriptBlock.dataset.audioId;
        const audio = modal.querySelector(`#audio-${audioId}`);
        if (!audio) return;

        // Get the HTML (not just text)
        const html = transcriptBlock.innerHTML;

        // Split the HTML into sentences (simple regex, can be improved)
        const sentences = html.match(/[^.!?]+[.!?]+(\s|$)/g) || [html];

        // Clear the block and add each sentence in a span
        transcriptBlock.innerHTML = '';
        sentences.forEach((sentence, idx) => {
            const span = document.createElement('span');
            span.className = 'karaoke-sentence';
            span.dataset.index = idx;
            span.innerHTML = sentence.trim() + ' ';
            transcriptBlock.appendChild(span);
        });

        const sentenceSpans = transcriptBlock.querySelectorAll('.karaoke-sentence');
        const sentenceCount = sentenceSpans.length;

        audio.addEventListener('timeupdate', function() {
            if (!audio.duration || sentenceCount === 0) return;

            const secondsPerSentence = audio.duration / sentenceCount;
            const currentSentenceIndex = Math.floor(audio.currentTime / secondsPerSentence);

            sentenceSpans.forEach((span, idx) => {
                if (idx === currentSentenceIndex) {
                    span.classList.add('highlight');
                } else {
                    span.classList.remove('highlight');
                }
            });
        });

        audio.addEventListener('pause', function() {
            sentenceSpans.forEach(span => span.classList.remove('highlight'));
            transcriptBlock.classList.remove('active');
        });

        audio.addEventListener('play', function() {
            transcriptBlock.classList.add('active');
        });

        audio.addEventListener('ended', function() {
            sentenceSpans.forEach(span => span.classList.remove('highlight'));
            transcriptBlock.classList.remove('active');
        });
    });
}

/**
 * Initialize sequential medley playback
 *
 * @param {HTMLElement} modal - The modal element
 */
function initializeMedleyModal(modal) {
    Logger.debug('=== Initializing Medley Modal ===');

    // Sequential audio playback for medley
    const segmentAudios = modal.querySelectorAll('.segment-audio');
    const medleyPlayer = modal.querySelector('#medley-player');
    const transcriptSegments = modal.querySelectorAll('.medley-segment');

    Logger.debug('Found segment audios:', segmentAudios.length);
    Logger.debug('Found transcript segments:', transcriptSegments.length);
    Logger.debug('Medley player:', medleyPlayer);

    if (segmentAudios.length > 0 && medleyPlayer) {
        let currentSegmentIndex = 0;

        // Initialize: load first segment into medley player
        const firstSegment = segmentAudios[0];
        const firstSource = firstSegment.querySelector('source');
        Logger.debug('First segment source:', firstSource);

        if (firstSource) {
            Logger.debug('First source URL:', firstSource.src);
            const medleySource = modal.querySelector('#medley-source');
            medleySource.src = firstSource.src;
            medleyPlayer.load();
            Logger.debug('Loaded first segment into medley player');
        } else {
            Logger.error('No source found for first segment');
        }

        // Karaoke highlighting function
        function highlightSegment(index) {
            // Remove highlight from all segments
            transcriptSegments.forEach(seg => seg.classList.remove('highlight'));

            // Add highlight to current segment
            if (transcriptSegments[index]) {
                transcriptSegments[index].classList.add('highlight');

                // Scroll segment into view if needed
                transcriptSegments[index].scrollIntoView({
                    behavior: 'smooth',
                    block: 'nearest',
                    inline: 'nearest'
                });
            }
        }

        // Highlight first segment when play starts
        medleyPlayer.addEventListener('play', function() {
            Logger.debug('Medley player started, highlighting segment:', currentSegmentIndex);
            highlightSegment(currentSegmentIndex);

            // If user clicks play after it finished, start from beginning
            if (medleyPlayer.currentTime === 0 && currentSegmentIndex >= segmentAudios.length) {
                Logger.debug('Restarting from beginning');
                currentSegmentIndex = 0;
                const firstSource = segmentAudios[0].querySelector('source');
                if (firstSource) {
                    const medleySource = modal.querySelector('#medley-source');
                    medleySource.src = firstSource.src;
                    medleyPlayer.load();
                    medleyPlayer.play();
                    highlightSegment(0);
                }
            }
        });

        // Remove highlight when paused
        medleyPlayer.addEventListener('pause', function() {
            // Keep highlight but reduce opacity slightly
            const highlightedSegment = modal.querySelector('.medley-segment.highlight');
            if (highlightedSegment) {
                // Don't remove highlight, just indicate paused state visually
                Logger.debug('Playback paused on segment:', currentSegmentIndex);
            }
        });

        // When medley player ends, play next segment
        medleyPlayer.addEventListener('ended', function() {
            Logger.debug('Segment ended, moving to next. Current index:', currentSegmentIndex);
            currentSegmentIndex++;

            if (currentSegmentIndex < segmentAudios.length) {
                const nextSegment = segmentAudios[currentSegmentIndex];
                const nextSource = nextSegment.querySelector('source');
                if (nextSource) {
                    Logger.debug('Playing next segment:', currentSegmentIndex, nextSource.src);
                    const medleySource = modal.querySelector('#medley-source');
                    medleySource.src = nextSource.src;
                    medleyPlayer.load();
                    medleyPlayer.play();

                    // Highlight the next segment
                    highlightSegment(currentSegmentIndex);
                }
            } else {
                // All segments completed - remove highlight
                Logger.debug('All segments played, resetting to beginning');
                transcriptSegments.forEach(seg => seg.classList.remove('highlight'));
                currentSegmentIndex = 0;
                const firstSource = segmentAudios[0].querySelector('source');
                if (firstSource) {
                    const medleySource = modal.querySelector('#medley-source');
                    medleySource.src = firstSource.src;
                    medleyPlayer.load();
                }
            }
        });
    } else {
        Logger.debug('No segments or medley player found - this may be the old modal format');
    }
}

/**
 * Initialize modal form validation and submission
 *
 * @param {HTMLElement} modal - The modal element
 */
function initializeModalJavaScript(modal) {
    try {
        // Initialize sliders
        const connectionSlider = modal.querySelector('input[name="connection_score"]');
        const voteSlider = modal.querySelector('input[name="vote_prediction"]');

        let connectionTouched = false;
        let voteTouched = false;

        function checkFormCompletion() {
            const submitButton = modal.querySelector('#submit-reflection-close');
            if (submitButton) {
                if (connectionTouched && voteTouched) {
                    submitButton.disabled = false;
                    submitButton.classList.remove('btn-secondary');
                    submitButton.classList.add('btn-success');
                } else {
                    submitButton.disabled = true;
                    submitButton.classList.remove('btn-success');
                    submitButton.classList.add('btn-secondary');
                }
            }
        }

        // Add slider event listeners
        if (connectionSlider) {
            connectionSlider.addEventListener('input', function () {
                connectionTouched = true;
                checkFormCompletion();
            });
        }

        if (voteSlider) {
            voteSlider.addEventListener('input', function () {
                voteTouched = true;
                checkFormCompletion();
            });
        }

        // Initialize connection request button
        const connectionRequestBtn = modal.querySelector('#send-connection-request');
        if (connectionRequestBtn) {
            connectionRequestBtn.addEventListener('click', async function() {
                // Change button to show "Connection sent"
                this.innerHTML = '<span class="me-2">✓</span> Connection sent';
                this.classList.remove('btn-primary');
                this.classList.add('btn-outline-secondary');
                this.disabled = true;

                // Get participant and recommendation IDs from modal attributes
                const participantId = modal.getAttribute('data-participant-id');
                const recId = AppState.recommendation.currentId;

                try {
                    const data = await sendConnectionRequest(
                        parseInt(participantId),
                        parseInt(recId)
                    );

                    if (!data.success) {
                        Logger.error('Error sending connection request:', data.error);
                        // Revert button state if there was an error
                        this.innerHTML = '<span class="me-2">&#10148;</span> Send connection request';
                        this.classList.remove('btn-outline-secondary');
                        this.classList.add('btn-primary');
                        this.disabled = false;
                    }
                } catch (err) {
                    Logger.error('Error sending connection request:', err);
                    // Revert button state if there was an error
                    this.innerHTML = '<span class="me-2">&#10148;</span> Send connection request';
                    this.classList.remove('btn-outline-secondary');
                    this.classList.add('btn-primary');
                    this.disabled = false;
                }
            });
        }

        // Initialize submit button
        const submitButton = modal.querySelector('#submit-reflection-close');
        if (submitButton) {
            // Enable submit button by default
            submitButton.disabled = false;
            submitButton.classList.remove('btn-secondary');
            submitButton.classList.add('btn-success');

            submitButton.addEventListener('click', async function(e) {
                e.preventDefault();

                // Get values with defensive checks
                const connectionSlider = modal.querySelector('input[name="connection_score"]');
                const connectionTextarea = modal.querySelector('textarea[name="connection_text"]');
                const voteSlider = modal.querySelector('input[name="vote_prediction"]');
                const voteTextarea = modal.querySelector('textarea[name="vote_explanation"]');

                if (!connectionSlider || !voteSlider) {
                    Logger.error('Required form elements not found');
                    return;
                }

                const connection_score = connectionSlider.value;
                const connection_text = connectionTextarea ? connectionTextarea.value : '';
                const vote_prediction = voteSlider.value;
                const vote_explanation = voteTextarea ? voteTextarea.value : '';

                // Get IDs from modal attributes
                const participantId = modal.getAttribute('data-participant-id');
                const recId = AppState.recommendation.currentId;

                try {
                    await submitReflection(
                        parseInt(recId),
                        parseInt(participantId),
                        parseInt(connection_score),
                        connection_text,
                        parseInt(vote_prediction),
                        vote_explanation
                    );

                    // Close the modal
                    const bsModal = bootstrap.Modal.getInstance(modal);
                    if (bsModal) {
                        bsModal.hide();
                    }
                } catch (err) {
                    Logger.error('Error saving reflection:', err);
                    alert('Error saving your reflection. Please try again.');
                }
            });
        }

    } catch (error) {
        Logger.error('Error initializing modal JavaScript:', error);
    }
}

/**
 * Load and display participant modal
 *
 * @param {string} participantUsername - Username of participant to display
 */
export async function loadParticipantModal(participantUsername) {
    // Create container if it doesn't exist
    let container = document.getElementById('dynamic-modal-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'dynamic-modal-container';
        document.body.appendChild(container);
    }

    // Use current recommendation ID (updated after edits) or fallback to original
    const recId = AppState.recommendation.currentId;

    try {
        const data = await fetchParticipantModal(recId, participantUsername);

        if (data.error) {
            Logger.error('Error loading modal:', data.error);
            alert('Error loading participant details');
            return;
        }

        // Clear previous modal
        container.innerHTML = '';

        // Create the actual modal
        const modal = document.createElement('div');
        modal.className = 'modal fade';
        modal.id = `participantModal-${participantUsername}`;
        modal.setAttribute('tabindex', '-1');
        modal.setAttribute('aria-labelledby', `participantModalLabel-${participantUsername}`);
        modal.setAttribute('aria-hidden', 'true');
        modal.setAttribute('data-participant-id', data.participant_id);
        modal.setAttribute('data-bs-backdrop', 'true');
        modal.setAttribute('data-bs-keyboard', 'true');

        // Set modal content
        modal.innerHTML = data.modal_html;

        // Add to container
        container.appendChild(modal);

        // Re-initialize modal JavaScript after DOM insertion
        setTimeout(() => {
            initializeModalJavaScript(modal);
            initializeMedleyModal(modal);
            setupKaraokeTranscript(modal);
        }, CONFIG.DELAYS.MODAL_INIT);

        // Show modal with clickable backdrop
        const bsModal = new bootstrap.Modal(modal, {
            backdrop: true,
            keyboard: true
        });
        bsModal.show();

        // Add body class to trigger chart resize
        document.body.classList.add('participant-modal-open');

        // Trigger avatar repositioning after CSS transition completes
        setTimeout(() => repositionAllAvatarsAfterResize(), CONFIG.DELAYS.CHART_RESIZE);

        // Clean up when modal is hidden
        modal.addEventListener('hidden.bs.modal', function() {
            // Remove body class to restore chart width
            document.body.classList.remove('participant-modal-open');

            // Trigger avatar repositioning after CSS transition completes
            setTimeout(() => repositionAllAvatarsAfterResize(), CONFIG.DELAYS.CHART_RESIZE);

            modal.remove();
        });

    } catch (error) {
        Logger.error('Error fetching modal:', error);
        alert('Error loading participant details');
    }
}
