/**
 * Streaming Service
 *
 * Handles Server-Sent Events (SSE) for real-time recommendation recomputation.
 * Extracted from lines 784-946 of original code.
 */

import { Logger } from '../utils/logger.js';
import { CONFIG, calculateAvatarSize } from '../config.js';
import { AppState } from '../state.js';

/**
 * Start recompute stream
 *
 * @param {number} recId - Recommendation ID
 * @param {string} recText - New recommendation text
 * @param {Object} callbacks - Callback functions
 * @param {Function} callbacks.onStarted - Called when stream starts
 * @param {Function} callbacks.onTotalCount - Called with total participant count
 * @param {Function} callbacks.onParticipantUpdate - Called for each participant
 * @param {Function} callbacks.onParticipantError - Called on participant error
 * @param {Function} callbacks.onCompleted - Called when all processing complete
 * @param {Function} callbacks.onError - Called on stream error
 * @returns {EventSource} The EventSource instance
 */
export function startRecomputeStream(recId, recText, callbacks) {
    const url = CONFIG.ENDPOINTS.RECOMPUTE_STREAM
        .replace('{rec_id}', recId) + `?rec_text=${encodeURIComponent(recText)}`;

    const eventSource = new EventSource(url);
    let totalParticipants = 0;
    let completedCount = 0;
    const allResults = [];

    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);

            switch(data.type) {
                case 'started':
                    Logger.debug('EventSource: started message received');
                    Logger.debug('Old recommendation ID:', recId);
                    Logger.debug('New recommendation ID from server:', data.new_recommendation_id);
                    if (callbacks.onStarted) {
                        callbacks.onStarted(data.new_recommendation_id);
                    }
                    break;

                case 'total_count':
                    totalParticipants = data.total;

                    // Update state with total participant count
                    AppState.avatars.totalParticipantCount = totalParticipants;

                    // Calculate and set initial avatar size based on total count
                    const isModalOpen = document.body.classList.contains('participant-modal-open') ||
                                         document.body.classList.contains('meta-panel-open');
                    AppState.avatars.currentSize = calculateAvatarSize(totalParticipants, isModalOpen);

                    Logger.debug(`Avatar size calculated: ${AppState.avatars.currentSize}px for ${totalParticipants} participants`);

                    if (callbacks.onTotalCount) {
                        callbacks.onTotalCount(totalParticipants);
                    }
                    break;

                case 'participant_update':
                    completedCount = data.completed;
                    const progressPercent = (completedCount / totalParticipants) * 100;

                    allResults.push(data.participant);

                    if (callbacks.onParticipantUpdate) {
                        callbacks.onParticipantUpdate({
                            participant: data.participant,
                            completed: completedCount,
                            total: totalParticipants,
                            progressPercent
                        });
                    }
                    break;

                case 'participant_error':
                    completedCount = data.completed;
                    const errorProgressPercent = (completedCount / totalParticipants) * 100;

                    Logger.error(`Error processing participant ${data.username}:`, data.error);

                    if (callbacks.onParticipantError) {
                        callbacks.onParticipantError({
                            username: data.username,
                            error: data.error,
                            completed: completedCount,
                            total: totalParticipants,
                            progressPercent: errorProgressPercent
                        });
                    }
                    break;

                case 'completed':
                    // Fallback: Ensure recommendation ID is updated
                    if (data.new_recommendation_id) {
                        Logger.debug('EventSource: completed message - ensuring ID is updated');
                        Logger.debug('ID from completed message:', data.new_recommendation_id);
                    }

                    if (callbacks.onCompleted) {
                        callbacks.onCompleted({
                            newRecommendationId: data.new_recommendation_id,
                            allResults
                        });
                    }

                    eventSource.close();
                    break;

                case 'error':
                    Logger.error('Server error:', data.message);

                    if (callbacks.onError) {
                        callbacks.onError(data.message);
                    }

                    eventSource.close();
                    break;
            }
        } catch (e) {
            Logger.error('Error parsing SSE data:', e, event.data);
        }
    };

    eventSource.onerror = function(event) {
        Logger.error('EventSource error:', event);
        eventSource.close();

        if (callbacks.onError) {
            callbacks.onError('Connection error while processing');
        }
    };

    return eventSource;
}
