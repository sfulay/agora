/**
 * DOM Utilities
 *
 * Safe DOM query functions with error handling.
 */

import { Logger } from './logger.js';

/**
 * Get element by ID with error handling
 * Throws error if element is required but not found
 *
 * @param {string} id - Element ID
 * @param {boolean} required - Whether element is required
 * @returns {HTMLElement|null}
 */
export function getElement(id, required = false) {
    const element = document.getElementById(id);

    if (!element && required) {
        throw new Error(`Required element #${id} not found`);
    }

    if (!element) {
        Logger.warn(`Element #${id} not found`);
    }

    return element;
}

/**
 * Get all avatar elements (both .participant-avatar and .avatar-circle)
 *
 * @returns {NodeList}
 */
export function getAllAvatarElements() {
    return document.querySelectorAll('.participant-avatar, .avatar-circle');
}

/**
 * Get CSRF token from DOM
 *
 * @returns {string}
 */
export function getCSRFToken() {
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    return token ? token.value : '';
}

/**
 * Format time in M:SS format
 *
 * @param {number} totalSeconds - Total seconds
 * @returns {string} Formatted time string
 */
export function formatTime(totalSeconds) {
    const seconds = Math.max(totalSeconds, 0);
    const minutes = Math.floor(seconds / 60);
    const remainder = Math.floor(seconds % 60);
    return `${minutes}:${remainder.toString().padStart(2, '0')}`;
}
