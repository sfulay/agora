/**
 * Telemetry Tracking Service
 *
 * Tracks user interactions for analytics.
 * Extracted from lines 2894-2967 of original code.
 */

import { getCSRFToken } from '../utils/dom.js';
import { Logger } from '../utils/logger.js';
import { CONFIG } from '../config.js';

export class TelemetryTracker {
    constructor(options = {}) {
        this.sessionId = this.generateSessionId();
        this.currentRecommendationId = null;
        this.currentProfileId = null;
        this.currentAudioId = null;
        this.startTimes = {};
        this.options = {
            endpoint: '/api/telemetry/',
            debug: false,
            ...options
        };
        this.init();
    }

    init() {
        Logger.debug('TelemetryTracker initialized with session ID:', this.sessionId);
    }

    generateSessionId() {
        return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    async makeRequest(endpoint, data) {
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken(),
                },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            Logger.error('Telemetry request failed:', error);
            throw error;
        }
    }

    trackAvatarClick(recommendationId, clickedParticipantId, avatarType, clickX, clickY) {
        Logger.debug('Avatar click tracked:', { recommendationId, clickedParticipantId, avatarType, clickX, clickY });

        return this.makeRequest(CONFIG.ENDPOINTS.TELEMETRY.AVATAR_CLICK, {
            recommendation_id: recommendationId,
            participant_id: clickedParticipantId,
            avatar_type: avatarType,
            click_x: clickX,
            click_y: clickY,
            session_id: this.sessionId
        });
    }

    trackMetaMedleyClick(recommendationId, metaMedleyType) {
        Logger.debug('Meta-medley click tracked:', { recommendationId, metaMedleyType });

        return this.makeRequest(CONFIG.ENDPOINTS.TELEMETRY.META_MEDLEY_CLICK, {
            recommendation_id: recommendationId,
            meta_medley_type: metaMedleyType,
            session_id: this.sessionId
        });
    }
}

/**
 * Helper function to safely track telemetry without throwing errors
 * Replaces the try-catch pattern used throughout the original code
 *
 * @param {TelemetryTracker} tracker - Telemetry tracker instance
 * @param {Function} trackingFn - Function to call
 * @param  {...any} args - Arguments to pass to tracking function
 */
export function safeTrack(tracker, trackingFn, ...args) {
    if (!tracker) return;

    try {
        trackingFn.call(tracker, ...args);
    } catch (error) {
        Logger.warn('Telemetry tracking failed:', error);
    }
}
