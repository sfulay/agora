/**
 * Logging Utility
 *
 * Replaces all console.log statements with a toggleable logger.
 * In production, debug logs are disabled.
 */

const DEBUG_MODE = false; // Set to true to enable debug logging

export const Logger = {
    /**
     * Debug log (only shown when DEBUG_MODE is true)
     */
    debug: (msg, ...args) => {
        if (DEBUG_MODE) {
            console.log(`[DEBUG] ${msg}`, ...args);
        }
    },

    /**
     * Info log (always shown)
     */
    info: (msg, ...args) => {
        console.log(`[INFO] ${msg}`, ...args);
    },

    /**
     * Warning log (always shown)
     */
    warn: (msg, ...args) => {
        console.warn(`[WARN] ${msg}`, ...args);
    },

    /**
     * Error log (always shown)
     */
    error: (msg, ...args) => {
        console.error(`[ERROR] ${msg}`, ...args);
    }
};
