/**
 * Configuration and Constants
 *
 * All magic numbers, hardcoded values, and configuration settings
 * extracted from the original recommendation_editor.html code.
 */

export const CONFIG = {
    // Character limits for recommendation text
    CHAR_LIMITS: {
        WARNING: 400,   // Show orange color
        ERROR: 450,     // Show red color
        MAX: 500        // Maximum allowed characters
    },

    // Avatar sizing - dynamic based on participant count
    AVATAR_SIZE: {
        MIN: 20,                    // Minimum avatar size (at max participants)
        MAX: 60,                    // Maximum avatar size (at 0 participants)
        MAX_PARTICIPANTS: 500,      // Expected maximum number of participants
        MODAL_REDUCTION_FACTOR: 0.8 // Size reduction factor when modal is open
    },

    // Timing and delays (in milliseconds)
    DELAYS: {
        REFLOW: 50,         // Force reflow delay
        CHART_RESIZE: 350,  // Chart resize transition delay
        MODAL_INIT: 100,    // Modal initialization delay
        STAGGER: 75,        // Avatar drop animation stagger
        PANEL_INIT: 200,    // Meta-medley panel initialization delay
        LEADERBOARD_RELOAD: 1000  // Delay before reloading leaderboard
    },

    // Leaderboard settings
    LEADERBOARD: {
        ITEMS_PER_PAGE: 10
    },

    // Meta-medley group configuration
    META_MEDLEY: {
        TOTAL_PARTICIPANTS: 90,  // Minimum participants for fixed groups
        GROUP_SIZE: 30           // Size of each group (bottom, middle, top)
    },

    // Color scheme
    COLORS: {
        CHAR_COUNT_ERROR: '#dc3545',      // Red
        CHAR_COUNT_WARNING: '#fd7e14',    // Orange
        CHAR_COUNT_DEFAULT: '#6c757d'     // Gray
    },

    // Plot/Chart configuration
    PLOT: {
        BOTTOM_MARGIN: 25,         // Space at bottom for x-axis
        STACKING_TOLERANCE: 0.02,  // 2% of width for grouping avatars
        START_Y: 30                // Avatar drop start position
    },

    // API Endpoints
    ENDPOINTS: {
        RECOMPUTE_STREAM: '/api/editor/{rec_id}/recompute-stream/',
        PARTICIPANT_MODAL: '/api/medley/{rec_id}/participant/{username}/',
        LEADERBOARD: '/api/editor/{rec_id}/leaderboard/',
        META_MEDLEY_PANEL: '/api/meta-medley/{rec_id}/{medley_type}/',
        CONNECTION_REQUEST: '/api/send_connection_request/',
        SUBMIT_REFLECTION: '/api/submit_reflection/',
        TELEMETRY: {
            AVATAR_CLICK: '/api/telemetry/avatar/click/',
            META_MEDLEY_CLICK: '/api/telemetry/meta-medley/click/'
        }
    }
};

/**
 * Calculate dynamic avatar size based on participant count
 * Uses inverse scaling: fewer participants = larger avatars
 *
 * @param {number} participantCount - Current number of participants
 * @param {boolean} isModalOpen - Whether the participant modal is open
 * @returns {number} Avatar size in pixels
 */
export function calculateAvatarSize(participantCount, isModalOpen = false) {
    const { MIN, MAX, MAX_PARTICIPANTS, MODAL_REDUCTION_FACTOR } = CONFIG.AVATAR_SIZE;

    // Inverse scaling: 60px at 0 participants, 20px at 500+ participants
    // Formula: MAX - ((participantCount / MAX_PARTICIPANTS) * (MAX - MIN))
    const scaling = Math.min(participantCount / MAX_PARTICIPANTS, 1.0);
    let size = MAX - (scaling * (MAX - MIN));

    // Apply modal reduction if modal is open
    if (isModalOpen) {
        size = size * MODAL_REDUCTION_FACTOR;
    }

    // Ensure we stay within bounds
    return Math.max(MIN, Math.min(MAX, Math.round(size)));
}
