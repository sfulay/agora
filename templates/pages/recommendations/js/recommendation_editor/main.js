/**
 * Main Entry Point
 *
 * Initializes the recommendation editor application.
 * Replaces the massive DOMContentLoaded handler from lines 616-947.
 */

import { CONFIG } from './config.js';
import { AppState, initializeState } from './state.js';
import { Logger } from './utils/logger.js';
import { getElement } from './utils/dom.js';
import { setupCharacterCounter, setupResetButton } from './components/characterCounter.js';
import { TelemetryTracker } from './services/telemetry.js';
import { startRecomputeStream } from './services/streaming.js';
import {
    initializeAvatars,
    updateSingleParticipant,
    updateSummaryStats,
    calculateMeanSupport,
    initializeConfidenceFilter,
    setupChartResizeListener
} from './components/avatars.js';
import { initializeLeaderboard, reloadLeaderboard } from './components/leaderboard.js';
import { openMetaMedleyPanel } from './components/metaMedley.js';
import { loadParticipantModal } from './components/modals.js';

// Wait for DOM to be ready
document.addEventListener('DOMContentLoaded', function() {
    Logger.info('Recommendation Editor initializing...');

    try {
        // Initialize state from template data
        const templateData = {
            showAvatars: (window.SHOW_AVATARS_FROM_TEMPLATE === "False") ? false : true,
            baseRecommendationId: window.BASE_REC_ID_FROM_TEMPLATE,
            currentRecommendationId: window.CURRENT_REC_ID_FROM_TEMPLATE,
            currentUserId: window.CURRENT_USER_ID_FROM_TEMPLATE
        };
        initializeState(templateData);

        // Get DOM references
        const recommendationText = getElement('recommendation-text', true);
        const charCount = getElement('char-count', true);
        const statusIndicator = getElement('status-indicator');
        const resetBtn = getElement('reset-btn');
        const recomputeBtn = getElement('recompute-btn');
        const resultsSection = getElement('results-section');
        const progressBar = getElement('progress-bar');

        const originalText = window.ORIGINAL_TEXT_FROM_TEMPLATE || '';

        // Setup character counter (FIXES duplicate listener bug)
        setupCharacterCounter(recommendationText, charCount, statusIndicator, originalText);

        // Setup reset button
        if (resetBtn) {
            setupResetButton(resetBtn, recommendationText, charCount, statusIndicator, originalText);
        }

        // Initialize telemetry
        AppState.telemetry = new TelemetryTracker();

        // Initialize visualization
        requestAnimationFrame(() => {
            // Initialize avatars if enabled
            if (AppState.showAvatars) {
                initializeAvatars();
                initializeConfidenceFilter();
                setupChartResizeListener();
            }

            // Initialize leaderboard
            initializeLeaderboard();
        });

        // Setup event delegation for meta-medley buttons
        setupMetaMedleyButtonDelegation();

        // Setup recompute button
        if (recomputeBtn) {
            setupRecomputeButton(recomputeBtn, recommendationText, statusIndicator, progressBar, resultsSection);
        }

        Logger.info('Recommendation Editor initialized successfully');

    } catch (error) {
        Logger.error('Failed to initialize Recommendation Editor:', error);
    }
});

/**
 * Setup event delegation for meta-medley buttons
 */
function setupMetaMedleyButtonDelegation() {
    document.addEventListener('click', function(e) {
        const button = e.target.closest('.medley-button');
        if (button) {
            // Ignore clicks on disabled buttons
            if (button.classList.contains('disabled')) {
                return;
            }
            const medleyType = button.dataset.medleyType;
            Logger.debug('Meta-medley button clicked:', medleyType, 'Using recommendation ID:', AppState.recommendation.currentId);

            // Track telemetry for meta-medley click
            if (AppState.telemetry) {
                try {
                    AppState.telemetry.trackMetaMedleyClick(
                        parseInt(AppState.recommendation.currentId),
                        medleyType
                    );
                } catch (error) {
                    Logger.warn('Telemetry tracking failed:', error);
                }
            }

            openMetaMedleyPanel(AppState.recommendation.currentId, medleyType, button);
        }
    });
}

/**
 * Setup recompute button with full streaming integration
 *
 * @param {HTMLElement} btn - Recompute button
 * @param {HTMLElement} textElement - Text input element
 * @param {HTMLElement} statusIndicator - Status badge element
 * @param {HTMLElement} progressBar - Progress bar element
 * @param {HTMLElement} resultsSection - Results section element
 */
function setupRecomputeButton(btn, textElement, statusIndicator, progressBar, resultsSection) {
    btn.addEventListener('click', function() {
        const newText = textElement.value.trim();

        if (!newText) {
            alert('Please enter recommendation text');
            return;
        }

        if (newText.length > CONFIG.CHAR_LIMITS.MAX) {
            alert(`Recommendation text must be ${CONFIG.CHAR_LIMITS.MAX} characters or less`);
            return;
        }

        // Keep chart visible, just update status
        if (statusIndicator) {
            statusIndicator.textContent = 'Computing...';
            statusIndicator.className = 'badge';
            statusIndicator.style.backgroundColor = '#000';
            statusIndicator.style.color = '#fff';
        }
        btn.disabled = true;

        // Disable medley buttons during recomputation
        document.querySelectorAll('.medley-button').forEach(btn => {
            btn.classList.add('disabled');
        });

        // Show progress bar within the existing chart area
        if (progressBar) {
            progressBar.style.width = '0%';
            if (progressBar.parentElement) {
                progressBar.parentElement.style.display = 'block';
            }
        }

        // Clear existing avatars to make room for new ones
        const container = document.getElementById('avatars-container');
        if (container) {
            container.innerHTML = '';
        }
        AppState.currentParticipants.clear();

        // Show progress indicator
        const liveProgress = getElement('live-progress');
        const liveProgressBar = getElement('live-progress-bar');
        const progressText = getElement('progress-text');
        if (liveProgress) {
            liveProgress.style.display = 'block';
            if (liveProgressBar) liveProgressBar.style.width = '0%';
            if (progressText) progressText.textContent = '0 / ? completed';
        }

        const allResults = [];

        // Start streaming recompute
        startRecomputeStream(
            AppState.recommendation.currentId,
            newText,
            {
                onStarted: (newRecommendationId) => {
                    Logger.debug('EventSource: started message received');
                    Logger.debug('Old recommendation ID:', AppState.recommendation.currentId);
                    Logger.debug('New recommendation ID from server:', newRecommendationId);
                    AppState.recommendation.currentId = newRecommendationId;
                    Logger.debug('Updated AppState.recommendation.currentId to:', AppState.recommendation.currentId);
                },

                onTotalCount: (totalParticipants) => {
                    if (progressText) {
                        progressText.textContent = `0 / ${totalParticipants} completed`;
                    }
                },

                onParticipantUpdate: ({ participant, completed, total, progressPercent }) => {
                    if (progressBar) {
                        progressBar.style.width = progressPercent + '%';
                    }

                    if (liveProgressBar && progressText) {
                        liveProgressBar.style.width = progressPercent + '%';
                        progressText.textContent = `${completed} / ${total} completed`;
                    }

                    allResults.push(participant);
                    updateSingleParticipant(participant, loadParticipantModal);
                },

                onParticipantError: ({ username, error, completed, total, progressPercent }) => {
                    if (progressBar) {
                        progressBar.style.width = progressPercent + '%';
                    }

                    if (liveProgressBar && progressText) {
                        liveProgressBar.style.width = progressPercent + '%';
                        progressText.textContent = `${completed} / ${total} completed`;
                    }

                    Logger.error(`Error processing participant ${username}:`, error);
                },

                onCompleted: ({ newRecommendationId, allResults: results }) => {
                    // Fallback: Ensure recommendation ID is updated (in case 'started' message was missed)
                    if (newRecommendationId) {
                        Logger.debug('EventSource: completed message - ensuring ID is updated');
                        Logger.debug('Current ID:', AppState.recommendation.currentId, 'ID from completed message:', newRecommendationId);
                        AppState.recommendation.currentId = newRecommendationId;
                    }

                    if (progressBar) {
                        progressBar.style.width = '100%';
                    }
                    if (statusIndicator) {
                        statusIndicator.textContent = 'Updated';
                        statusIndicator.className = 'badge';
                        statusIndicator.style.backgroundColor = '#007bff';
                        statusIndicator.style.color = '#fff';
                    }

                    updateSummaryStats(allResults);

                    setTimeout(() => {
                        reloadLeaderboard();
                    }, CONFIG.DELAYS.LEADERBOARD_RELOAD);

                    // Calculate new mean support and compare with previous
                    const newMeanSupport = calculateMeanSupport(allResults);
                    const previousMean = AppState.recommendation.previousMeanSupport;

                    let alertClass, alertIcon, alertMessage;

                    if (previousMean === null) {
                        // First time - just show success
                        alertClass = 'alert-success';
                        alertIcon = '✓';
                        alertMessage = `<strong>Success!</strong> Initial prediction completed with ${newMeanSupport}% average support.`;
                    } else if (newMeanSupport > previousMean) {
                        // Improvement
                        alertClass = 'alert-success';
                        alertIcon = '🎉';
                        alertMessage = `<strong>Great job!</strong> You improved the predicted support from ${previousMean}% to ${newMeanSupport}%.`;
                    } else if (newMeanSupport < previousMean) {
                        // Decline
                        alertClass = 'alert-danger';
                        alertIcon = '😞';
                        alertMessage = `<strong>Sorry!</strong> The predicted support went down from ${previousMean}% to ${newMeanSupport}%.`;
                    } else {
                        // No change
                        alertClass = 'alert-info';
                        alertIcon = '🔄';
                        alertMessage = `<strong>No change.</strong> The predicted support stayed the same at ${newMeanSupport}%.`;
                    }

                    if (resultsSection) {
                        const alertDiv = document.createElement('div');
                        alertDiv.className = `alert ${alertClass} alert-dismissible fade show mt-3`;
                        alertDiv.style.color = alertClass === 'alert-danger' ? '#721c24' : '#155724';
                        alertDiv.innerHTML = `
                            ${alertIcon} ${alertMessage}
                            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                        `;
                        resultsSection.insertBefore(alertDiv, resultsSection.firstChild);
                    }

                    // Update previous mean support for next comparison
                    AppState.recommendation.previousMeanSupport = newMeanSupport;

                    if (liveProgress) {
                        liveProgress.style.display = 'none';
                    }

                    btn.disabled = false;

                    // Re-enable medley buttons
                    document.querySelectorAll('.medley-button').forEach(btn => {
                        btn.classList.remove('disabled');
                    });
                },

                onError: (errorMessage) => {
                    Logger.error('Server error:', errorMessage);
                    alert('Error: ' + errorMessage);
                    if (statusIndicator) {
                        statusIndicator.textContent = 'Error';
                        statusIndicator.className = 'badge bg-danger';
                    }

                    btn.disabled = false;

                    // Re-enable medley buttons
                    document.querySelectorAll('.medley-button').forEach(btn => {
                        btn.classList.remove('disabled');
                    });
                }
            }
        );
    });
}
