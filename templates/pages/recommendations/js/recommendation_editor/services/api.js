/**
 * API Service
 *
 * Centralized API calls with error handling.
 * Extracted from various fetch() calls throughout original code.
 */

import { getCSRFToken } from '../utils/dom.js';
import { Logger } from '../utils/logger.js';
import { CONFIG } from '../config.js';

/**
 * Fetch participant modal HTML
 *
 * @param {number} recId - Recommendation ID
 * @param {string} username - Participant username
 * @returns {Promise<Object>} Modal data
 */
export async function fetchParticipantModal(recId, username) {
    const url = CONFIG.ENDPOINTS.PARTICIPANT_MODAL
        .replace('{rec_id}', recId)
        .replace('{username}', username);

    const response = await fetch(url);
    return await response.json();
}

/**
 * Fetch leaderboard data
 *
 * @param {number} recId - Recommendation ID
 * @returns {Promise<Object>} Leaderboard data
 */
export async function fetchLeaderboard(recId) {
    const url = CONFIG.ENDPOINTS.LEADERBOARD.replace('{rec_id}', recId);

    const response = await fetch(url);
    return await response.json();
}

/**
 * Fetch meta-medley panel HTML
 *
 * @param {number} recId - Recommendation ID
 * @param {string} medleyType - Type ('bottom'|'middle'|'top')
 * @returns {Promise<string>} Panel HTML
 */
export async function fetchMetaMedleyPanel(recId, medleyType) {
    const url = CONFIG.ENDPOINTS.META_MEDLEY_PANEL
        .replace('{rec_id}', recId)
        .replace('{medley_type}', medleyType);

    const response = await fetch(url);
    return await response.text();
}

/**
 * Send connection request
 *
 * @param {number} targetParticipantId - Target participant ID
 * @param {number} recommendationId - Recommendation ID
 * @returns {Promise<Object>} Response data
 */
export async function sendConnectionRequest(targetParticipantId, recommendationId) {
    const response = await fetch(CONFIG.ENDPOINTS.CONNECTION_REQUEST, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify({
            target_participant_id: parseInt(targetParticipantId),
            recommendation_id: parseInt(recommendationId)
        })
    });

    return await response.json();
}

/**
 * Submit reflection/feedback
 *
 * @param {Object} data - Reflection data
 * @returns {Promise<Object>} Response data
 */
export async function submitReflection(data) {
    const response = await fetch(CONFIG.ENDPOINTS.SUBMIT_REFLECTION, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCSRFToken()
        },
        body: JSON.stringify(data)
    });

    return await response.json();
}
