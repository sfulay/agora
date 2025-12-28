/**
 * Centralized State Management
 *
 * Replaces the 15+ window.* global variables with a single
 * organized state object.
 */

export const AppState = {
    // Feature flags
    showAvatars: true,  // Control/Treatment condition flag

    // Services
    telemetry: null,

    // Participant data
    currentParticipants: new Map(),  // Map<username, participantData>

    // Meta-medley system
    metaMedley: {
        groups: {
            bottom: [],  // Array of usernames
            middle: [],  // Array of usernames
            top: []      // Array of usernames
        },
        activeGroup: null,          // Currently active group ('bottom'|'middle'|'top')
        panelOpen: false,           // Is panel currently open?
        panelLoading: false,        // Is panel currently loading?
        hoveredGroup: null,         // Currently hovered group
        segmentsData: null,         // Data from server
        participantsData: null,     // Participant data for panel
        segments: null,             // Audio segments
        currentSegment: 0           // Current playing segment index
    },

    // Recommendation tracking
    recommendation: {
        baseId: null,              // Base recommendation ID (never changes)
        currentId: null,           // Current recommendation ID (updates after edits)
        previousMeanSupport: null  // For comparison alerts
    },

    // UI state
    ui: {
        useAIRecommendation: null,  // Function to use AI recommendation
        currentUserId: null         // Current logged-in user ID
    },

    // Avatar sizing
    avatars: {
        currentSize: 60,           // Current avatar size in pixels (starts at max)
        totalParticipantCount: 0   // Total participant count from server
    }
};

/**
 * Initialize state from Django template variables
 * @param {Object} templateData - Data from Django template
 */
export function initializeState(templateData) {
    AppState.showAvatars = templateData.showAvatars;
    AppState.recommendation.baseId = templateData.baseRecommendationId;
    AppState.recommendation.currentId = templateData.currentRecommendationId;
    AppState.ui.currentUserId = templateData.currentUserId;
}

/**
 * Reset state (useful for testing or cleanup)
 */
export function resetState() {
    AppState.currentParticipants.clear();
    AppState.metaMedley = {
        groups: { bottom: [], middle: [], top: [] },
        activeGroup: null,
        panelOpen: false,
        panelLoading: false,
        hoveredGroup: null,
        segmentsData: null,
        participantsData: null,
        segments: null,
        currentSegment: 0
    };
    AppState.recommendation.previousMeanSupport = null;
    AppState.avatars = {
        currentSize: 60,
        totalParticipantCount: 0
    };
}
