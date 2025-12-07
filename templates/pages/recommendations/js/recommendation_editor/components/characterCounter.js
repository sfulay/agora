/**
 * Character Counter Component
 *
 * Manages character counting and status updates for recommendation text input.
 * Extracted and fixed from lines 634-672 (removed duplicate listener bug).
 */

import { CONFIG } from '../config.js';

/**
 * Setup character counter with status indicator
 * FIXES: Removed duplicate event listener that existed in original code
 *
 * @param {HTMLElement} textElement - Text input/textarea element
 * @param {HTMLElement} countElement - Element to display character count
 * @param {HTMLElement} statusElement - Element to display status badge
 * @param {string} originalText - Original text for comparison
 */
export function setupCharacterCounter(textElement, countElement, statusElement, originalText) {
    if (!textElement || !countElement) {
        return;
    }

    // Single unified event listener (fixes duplicate listener bug from lines 634-646 and 662-672)
    textElement.addEventListener('input', function() {
        const currentLength = this.value.length;
        countElement.textContent = currentLength;

        // Update color based on length
        if (currentLength > CONFIG.CHAR_LIMITS.ERROR) {
            countElement.style.color = CONFIG.COLORS.CHAR_COUNT_ERROR; // Red
        } else if (currentLength > CONFIG.CHAR_LIMITS.WARNING) {
            countElement.style.color = CONFIG.COLORS.CHAR_COUNT_WARNING; // Orange
        } else {
            countElement.style.color = CONFIG.COLORS.CHAR_COUNT_DEFAULT; // Gray
        }

        // Update status indicator if provided
        if (statusElement && originalText !== undefined) {
            if (this.value !== originalText) {
                statusElement.textContent = 'Modified';
                statusElement.className = 'badge bg-warning';
            } else {
                statusElement.textContent = 'Original';
                statusElement.className = 'badge bg-secondary';
            }
        }
    });
}

/**
 * Setup reset button
 *
 * @param {HTMLElement} resetBtn - Reset button element
 * @param {HTMLElement} textElement - Text input element
 * @param {HTMLElement} countElement - Count display element
 * @param {HTMLElement} statusElement - Status badge element
 * @param {string} originalText - Original text to reset to
 */
export function setupResetButton(resetBtn, textElement, countElement, statusElement, originalText) {
    if (!resetBtn || !textElement) {
        return;
    }

    resetBtn.addEventListener('click', function() {
        textElement.value = originalText;
        countElement.textContent = originalText.length;

        if (statusElement) {
            statusElement.textContent = 'Original';
            statusElement.className = 'badge bg-secondary';
        }
    });
}
