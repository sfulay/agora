/**
 * Color Utilities
 *
 * Functions for generating colors based on support levels.
 * Extracted from lines 1016-1037 of original code.
 */

/**
 * Get color based on support level
 * Maps 0-100 support to a color gradient: Red -> Yellow -> Dark Green
 *
 * @param {number} supportLevel - Support level (0-100)
 * @returns {string} RGBA color string
 */
export function getSupportLevelColor(supportLevel) {
    // Clamp support level between 0 and 100
    const support = Math.max(0, Math.min(100, supportLevel || 0));

    let r, g, b;

    if (support <= 50) {
        // Red (255,0,0) to Yellow (255,255,0) - increasing green
        r = 255;
        g = Math.round((support / 50) * 255);
        b = 0;
    } else {
        // Yellow (255,255,0) to Dark Green (0,128,0) - decreasing red and green
        r = Math.round(255 * (1 - (support - 50) / 50));
        g = Math.round(255 - ((support - 50) / 50) * 127); // Fade from 255 to 128
        b = 0;
    }

    // Return with higher alpha for more visibility
    return `rgba(${r}, ${g}, ${b}, 0.6)`;
}

/**
 * Convert support color to softer border color
 * Reduces opacity from 0.6 to 0.4
 *
 * @param {number} supportLevel - Support level (0-100)
 * @returns {string} RGBA color string with reduced opacity
 */
export function getSupportBorderColor(supportLevel) {
    const supportColor = getSupportLevelColor(supportLevel);
    return supportColor.replace('0.6)', '0.4)');
}
