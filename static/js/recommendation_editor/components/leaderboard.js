/**
 * Leaderboard Component
 *
 * Manages the recommendation history leaderboard with sorting and pagination.
 * Extracted from lines 2224-2418 of original code.
 */

import { CONFIG } from '../config.js';
import { AppState } from '../state.js';
import { Logger } from '../utils/logger.js';
import { getElement } from '../utils/dom.js';
import { fetchLeaderboard } from '../services/api.js';

/**
 * Leaderboard state
 */
const LeaderboardState = {
    currentData: [],
    currentPage: 0
};

/**
 * Update leaderboard with new data
 *
 * @param {Array} leaderboardData - Array of recommendation objects
 */
export function updateLeaderboard(leaderboardData) {
    LeaderboardState.currentData = leaderboardData;
    LeaderboardState.currentPage = 0; // Reset to first page

    renderLeaderboard();
}

/**
 * Render the leaderboard table with current filters and pagination
 */
export function renderLeaderboard() {
    const sortSelect = getElement('leaderboard-sort');
    if (!sortSelect) {
        Logger.warn('Leaderboard sort dropdown not found');
        return;
    }

    const sortBy = sortSelect.value;
    const currentUserId = AppState.ui.currentUserId;

    // Filter data to show only current user's recommendations
    let filteredData = LeaderboardState.currentData.filter(
        item => item.editor_id === currentUserId
    );

    // Sort data
    if (sortBy === 'support') {
        filteredData.sort((a, b) => b.mean_support - a.mean_support);
    } else if (sortBy === 'recent') {
        filteredData.sort((a, b) => b.rec_id_for_sorting - a.rec_id_for_sorting);
    }

    // Update pagination info
    const totalItems = filteredData.length;
    const startIndex = LeaderboardState.currentPage * CONFIG.LEADERBOARD.ITEMS_PER_PAGE;
    const endIndex = Math.min(
        startIndex + CONFIG.LEADERBOARD.ITEMS_PER_PAGE,
        totalItems
    );
    const paginatedData = filteredData.slice(startIndex, endIndex);

    // Update pagination controls
    updatePaginationControls(totalItems, startIndex, endIndex);

    // Render table
    renderLeaderboardTable(paginatedData);
}

/**
 * Update pagination controls
 *
 * @param {number} totalItems - Total number of items
 * @param {number} startIndex - Starting index of current page
 * @param {number} endIndex - Ending index of current page
 */
function updatePaginationControls(totalItems, startIndex, endIndex) {
    const paginationDiv = getElement('leaderboard-pagination');
    const rangeSpan = getElement('leaderboard-range');
    const totalSpan = getElement('leaderboard-total');
    const prevBtn = getElement('leaderboard-prev');
    const nextBtn = getElement('leaderboard-next');

    if (!paginationDiv) return;

    if (totalItems > CONFIG.LEADERBOARD.ITEMS_PER_PAGE) {
        paginationDiv.style.display = 'flex';

        if (rangeSpan) rangeSpan.textContent = `${startIndex + 1}-${endIndex}`;
        if (totalSpan) totalSpan.textContent = totalItems;

        if (prevBtn) prevBtn.disabled = LeaderboardState.currentPage === 0;
        if (nextBtn) nextBtn.disabled = endIndex >= totalItems;
    } else {
        paginationDiv.style.display = 'none';
    }
}

/**
 * Render the leaderboard table
 *
 * @param {Array} data - Array of recommendation objects to display
 */
function renderLeaderboardTable(data) {
    const contentDiv = getElement('leaderboard-content');
    if (!contentDiv) {
        Logger.warn('Leaderboard content div not found');
        return;
    }

    if (data.length === 0) {
        contentDiv.innerHTML = `
            <div class="text-center py-4 text-muted">
                <i class="fas fa-info-circle me-2"></i>
                No recommendations found.
            </div>
        `;
        return;
    }

    let tableHTML = `
        <div class="table-responsive" style="overflow: visible;">
            <table class="table">
                <thead class="table-light">
                    <tr>
                        <th style="width: 60px;">#</th>
                        <th>Recommendation</th>
                        <th style="width: 120px;">Editor</th>
                        <th style="width: 120px;">Support</th>
                    </tr>
                </thead>
                <tbody>
    `;

    data.forEach((item, index) => {
        const globalRank = LeaderboardState.currentPage * CONFIG.LEADERBOARD.ITEMS_PER_PAGE + index + 1;
        const recommendationText = item.rec_text;

        // Determine row styling for latest recommendation
        const rowClass = item.is_latest ? 'table-success' : '';
        const latestBadge = item.is_latest ? '<i class="fas fa-star text-warning me-1" title="Latest"></i>' : '';

        // Rank badge color based on position
        let badgeClass = 'bg-light text-dark';
        if (index < 3) {
            badgeClass = index === 0 ? 'bg-warning' : index === 1 ? 'bg-secondary' : 'bg-dark';
        }

        tableHTML += `
            <tr class="${rowClass}">
                <td>
                    <span class="badge ${badgeClass}">${globalRank}</span>
                </td>
                <td class="small">${latestBadge}${recommendationText}</td>
                <td class="small">${item.editor_name}</td>
                <td class="small">
                    ${item.mean_support.toFixed(1)}%
                </td>
            </tr>
        `;
    });

    tableHTML += `
                </tbody>
            </table>
        </div>
    `;

    contentDiv.innerHTML = tableHTML;
}

/**
 * Get current filtered data
 *
 * @returns {Array} Filtered recommendation data
 */
function getCurrentFilteredData() {
    const currentUserId = AppState.ui.currentUserId;
    // Always return only current user's recommendations
    return LeaderboardState.currentData.filter(
        item => item.editor_id === currentUserId
    );
}

/**
 * Reload leaderboard data from server
 */
export async function reloadLeaderboard() {
    Logger.debug('Reloading leaderboard');

    const contentDiv = getElement('leaderboard-content');

    try {
        const data = await fetchLeaderboard(AppState.recommendation.baseId);

        if (data.success && data.leaderboard_data) {
            Logger.debug('Leaderboard data:', data.leaderboard_data);
            updateLeaderboard(data.leaderboard_data);
        } else {
            Logger.debug('No leaderboard data');
            updateLeaderboard([]);
        }
    } catch (error) {
        Logger.error('Error loading leaderboard:', error);

        if (contentDiv) {
            contentDiv.innerHTML = `
                <div class="text-center py-4 text-danger">
                    <i class="fas fa-exclamation-triangle me-2"></i>
                    Error loading leaderboard
                </div>
            `;
        }
    }
}

/**
 * Setup leaderboard event listeners
 */
function setupLeaderboardEventListeners() {
    // Sort dropdown
    const sortSelect = getElement('leaderboard-sort');
    if (sortSelect) {
        sortSelect.addEventListener('change', function() {
            LeaderboardState.currentPage = 0;
            renderLeaderboard();
        });
    }

    // Previous page button
    const prevBtn = getElement('leaderboard-prev');
    if (prevBtn) {
        prevBtn.addEventListener('click', function() {
            if (LeaderboardState.currentPage > 0) {
                LeaderboardState.currentPage--;
                renderLeaderboard();
            }
        });
    }

    // Next page button
    const nextBtn = getElement('leaderboard-next');
    if (nextBtn) {
        nextBtn.addEventListener('click', function() {
            const totalItems = getCurrentFilteredData().length;
            const maxPage = Math.ceil(totalItems / CONFIG.LEADERBOARD.ITEMS_PER_PAGE) - 1;
            if (LeaderboardState.currentPage < maxPage) {
                LeaderboardState.currentPage++;
                renderLeaderboard();
            }
        });
    }
}

/**
 * Setup collapse/expand chevron toggle
 */
function setupCollapseToggle() {
    const leaderboardCollapse = getElement('leaderboardCollapse');
    const chevronIcon = getElement('leaderboard-chevron');

    if (leaderboardCollapse && chevronIcon) {
        leaderboardCollapse.addEventListener('show.bs.collapse', function() {
            chevronIcon.classList.remove('fa-chevron-right');
            chevronIcon.classList.add('fa-chevron-down');
        });

        leaderboardCollapse.addEventListener('hide.bs.collapse', function() {
            chevronIcon.classList.remove('fa-chevron-down');
            chevronIcon.classList.add('fa-chevron-right');
        });
    }
}

/**
 * Initialize the leaderboard component
 */
export function initializeLeaderboard() {
    Logger.debug('Initializing leaderboard component');

    // Setup collapse toggle
    setupCollapseToggle();

    // Setup event listeners
    setupLeaderboardEventListeners();

    // Load initial data
    reloadLeaderboard();
}

/**
 * Navigate to a specific recommendation
 *
 * @param {number} recommendationId - ID of recommendation to load
 */
export function loadRecommendation(recommendationId) {
    window.location.href = `/editor/${recommendationId}/`;
}
