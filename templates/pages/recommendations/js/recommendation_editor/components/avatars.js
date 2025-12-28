/**
 * Avatar Management Component
 *
 * Handles avatar creation, positioning, animations, filtering, and interactions.
 * Extracted from lines 950-1792 of original code.
 */

import { CONFIG } from '../config.js';
import { AppState } from '../state.js';
import { getSupportLevelColor, getSupportBorderColor } from '../utils/colors.js';
import { Logger } from '../utils/logger.js';
import { getAllAvatarElements, getElement } from '../utils/dom.js';
import { safeTrack } from '../services/telemetry.js';

// =============================================================================
// TOOLTIP MANAGEMENT
// =============================================================================

/**
 * Create or get global tooltip element
 * Extracted from lines 950-972
 */
function createGlobalTooltip() {
    let globalTooltip = document.getElementById('global-avatar-tooltip');
    if (!globalTooltip) {
        globalTooltip = document.createElement('div');
        globalTooltip.id = 'global-avatar-tooltip';
        globalTooltip.style.cssText = `
            position: fixed;
            background: rgba(0,0,0,0.9);
            color: white;
            padding: 0.5rem 0.75rem;
            border-radius: 0.375rem;
            font-size: 0.75rem;
            white-space: nowrap;
            z-index: 99999;
            pointer-events: none;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            opacity: 0;
            transition: opacity 0.2s ease;
        `;
        document.body.appendChild(globalTooltip);
    }
    return globalTooltip;
}

/**
 * Show tooltip for avatar
 * Extracted from lines 974-995
 */
export function showTooltip(element, participantData) {
    const globalTooltip = createGlobalTooltip();
    const rect = element.getBoundingClientRect();

    globalTooltip.style.left = (rect.left + rect.width/2) + 'px';
    globalTooltip.style.top = (rect.top - 10) + 'px';
    globalTooltip.style.transform = 'translate(-50%, -100%)';

    const displayName = participantData.display_name || 'Unknown';
    const support = participantData.predicted_agreement || 0;
    const relevance = participantData.quality_score || 0;

    globalTooltip.innerHTML = `
        <strong>${displayName}</strong><br>
        Support: <span style="color:#ffe066;">${support}%</span><br>
        Relevance: <span style="color:#6ee7b7;">${relevance}%</span>
    `;

    globalTooltip.style.opacity = '1';
    element.style.transform = element.style.transform.replace(/scale\([^)]*\)/g, '').trim() + ' scale(1.1)';
    element.style.zIndex = '100';
}

/**
 * Hide tooltip
 * Extracted from lines 997-1004
 */
export function hideTooltip(element) {
    const globalTooltip = document.getElementById('global-avatar-tooltip');
    if (globalTooltip) {
        globalTooltip.style.opacity = '0';
    }
    element.style.transform = element.style.transform.replace(/scale\([^)]*\)/g, '').trim() + ' scale(1)';
    element.style.zIndex = '10';
}

// =============================================================================
// AVATAR CREATION
// =============================================================================

/**
 * Set avatar initials as fallback
 * Extracted from lines 1191-1201
 */
function setAvatarInitials(avatar, displayName) {
    avatar.innerHTML = '';
    avatar.style.display = 'flex';
    avatar.style.alignItems = 'center';
    avatar.style.justifyContent = 'center';
    avatar.style.color = 'white';
    avatar.style.fontWeight = 'bold';
    avatar.style.fontSize = '0.7rem';
    const initials = (displayName || 'U').split(' ').map(n => n[0]).join('').substring(0, 2);
    avatar.textContent = initials;
}

/**
 * Create avatar element
 * Extracted from lines 1094-1189
 */
export function createAvatarElement(participantData, loadModalCallback, avatarSize = CONFIG.AVATAR_SIZE.DEFAULT) {
    const avatar = document.createElement('div');
    avatar.className = 'participant-avatar processing';
    avatar.setAttribute('data-participant-id', participantData.username);
    avatar.setAttribute('data-support', participantData.predicted_agreement);
    avatar.setAttribute('data-relevance', participantData.quality_score);
    avatar.setAttribute('data-confidence', participantData.confidence_score);

    // Get border color based on support level
    const borderColor = getSupportBorderColor(participantData.predicted_agreement);

    // Set cursor based on SHOW_AVATARS flag
    const cursorStyle = AppState.showAvatars ? 'pointer' : 'default';

    avatar.style.cssText = `
        position: absolute;
        width: ${avatarSize}px;
        height: ${avatarSize}px;
        border-radius: 50%;
        border: 2px solid ${borderColor};
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        cursor: ${cursorStyle};
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        z-index: 10;
        overflow: hidden;
        opacity: 0.8;
        transform: scale(0.9);
        background: #f5f5f5;
    `;

    // Add avatar image or initials fallback
    const avatarUrl = AppState.showAvatars ? participantData.avatar_url : 'https://ccc-sfulay.s3.us-east-1.amazonaws.com/media/GeneratedAvatars/default_avatar.png';

    if (avatarUrl && avatarUrl !== '/static/assets/img/avatars/default.png') {
        const avatarImg = document.createElement('img');
        avatarImg.src = avatarUrl;
        avatarImg.style.cssText = `
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: block;
            border-radius: 50%;
        `;
        avatarImg.onerror = function() {
            setAvatarInitials(avatar, participantData.display_name);
        };
        avatar.appendChild(avatarImg);
    } else {
        setAvatarInitials(avatar, participantData.display_name);
    }

    // Only add hover and click interactions when SHOW_AVATARS is true
    if (AppState.showAvatars) {
        // Add hover effects
        avatar.addEventListener('mouseenter', () => showTooltip(avatar, participantData));
        avatar.addEventListener('mouseleave', () => hideTooltip(avatar));

        // Add click handler for modal
        avatar.addEventListener('click', (event) => {
            // Track telemetry for avatar click
            if (AppState.telemetry && loadModalCallback) {
                safeTrack(AppState.telemetry, AppState.telemetry.trackAvatarClick,
                    AppState.recommendation.currentId,
                    participantData.participant_id || 0,
                    'other',
                    Math.round(event.clientX - avatar.getBoundingClientRect().left),
                    Math.round(event.clientY - avatar.getBoundingClientRect().top)
                );
            }

            // Load modal
            if (loadModalCallback) {
                loadModalCallback(participantData.username);
            }
        });
    }

    return avatar;
}

/**
 * Update existing avatar with new data
 * Extracted from lines 1069-1092
 */
export function updateExistingAvatar(avatar, participantData) {
    // Update data attributes
    avatar.setAttribute('data-support', participantData.predicted_agreement);
    avatar.setAttribute('data-relevance', participantData.quality_score);
    avatar.setAttribute('data-confidence', participantData.confidence_score);

    // Remove existing event listeners and add fresh ones
    if (avatar._hoverEnter) avatar.removeEventListener('mouseenter', avatar._hoverEnter);
    if (avatar._hoverLeave) avatar.removeEventListener('mouseleave', avatar._hoverLeave);

    // Add hover effects
    avatar._hoverEnter = () => showTooltip(avatar, participantData);
    avatar._hoverLeave = () => hideTooltip(avatar);

    avatar.addEventListener('mouseenter', avatar._hoverEnter);
    avatar.addEventListener('mouseleave', avatar._hoverLeave);

    // Update visual state
    avatar.classList.remove('processing');
    const borderColor = getSupportBorderColor(participantData.predicted_agreement);
    avatar.style.borderColor = borderColor;
    avatar.style.opacity = '1';
    avatar.style.transform = 'scale(1)';
}

// =============================================================================
// DYNAMIC AVATAR SIZING
// =============================================================================

/**
 * Calculate maximum stack size based on participant distribution
 * Groups participants by support level and returns the size of the largest group
 */
function calculateMaxStackSize(participants) {
    if (!participants || participants.length === 0) {
        return 1; // Avoid division by zero
    }

    // Group participants by rounded support level (nearest 5%)
    const supportGroups = new Map();

    participants.forEach(participant => {
        const roundedSupport = Math.round(participant.predicted_agreement / 5) * 5;
        const count = supportGroups.get(roundedSupport) || 0;
        supportGroups.set(roundedSupport, count + 1);
    });

    // Find the maximum group size
    let maxStackSize = 0;
    for (const count of supportGroups.values()) {
        maxStackSize = Math.max(maxStackSize, count);
    }

    Logger.debug(`Max stack size: ${maxStackSize} participants (from ${participants.length} total)`);
    return maxStackSize;
}

/**
 * Calculate dynamic avatar size based on participant distribution
 * Ensures the tallest stack fits within the plot height
 */
function calculateDynamicAvatarSize(participants, plotHeight, isModalOpen = false, maxParticipants = 300) {
    const numParticipants = participants.length;

    // Min-max scaling: using visible participant count in numerator, total count in denominator
    const minParticipants = 0;
    const minSize = 20;
    const maxSize = 50;

    // Calculate scaling factor
    const scaling = (numParticipants - minParticipants) / (maxParticipants - minParticipants);

    // Calculate avatar size: 20 + scaling * (50 - 20)
    // Note: Larger participant count = smaller avatars, so we invert the scaling
    let avatarSize = minSize + (1 - scaling) * (maxSize - minSize);

    // Clamp to bounds
    avatarSize = Math.max(minSize, Math.min(maxSize, avatarSize));
    avatarSize = Math.floor(avatarSize);

    console.log(`🎯 DYNAMIC SIZING DEBUG:`, {
        participantCount: numParticipants,
        scaling: scaling.toFixed(3),
        calculatedSize: avatarSize,
        isModalOpen
    });

    // Reduce by 25% when modal is open
    if (isModalOpen) {
        avatarSize = Math.floor(avatarSize * 0.75);
        avatarSize = Math.max(minSize, avatarSize); // Ensure still above minimum
    }

    console.log(`✅ Final avatar size: ${avatarSize}px`);
    Logger.debug(`Dynamic avatar size: ${avatarSize}px (modal: ${isModalOpen})`);
    return avatarSize;
}

// =============================================================================
// AVATAR POSITIONING
// =============================================================================

/**
 * Find stacking position (dynamic - reads from DOM)
 * Extracted from lines 1250-1293
 */
export function findStackingPosition(targetX, roundedSupport, currentUsername, plotWidth, plotHeight, avatarSize) {
    const tolerance = plotWidth * CONFIG.PLOT.STACKING_TOLERANCE;
    const existingAvatarsAtLevel = [];

    for (let [username, participant] of AppState.currentParticipants) {
        if (username === currentUsername) continue;

        const existingAvatar = document.querySelector(`[data-participant-id="${username}"]`);
        if (existingAvatar) {
            const rect = existingAvatar.getBoundingClientRect();
            const plotRect = document.getElementById('editor-support-plot').getBoundingClientRect();

            const existingX = rect.left - plotRect.left + avatarSize/2;

            // Check if this avatar is at the same support level
            if (Math.abs(existingX - targetX) <= tolerance) {
                const existingY = rect.top - plotRect.top + avatarSize/2;
                existingAvatarsAtLevel.push(existingY);
            }
        }
    }

    // Sort existing Y positions
    existingAvatarsAtLevel.sort((a, b) => a - b);

    // Find the best Y position (stack from bottom up)
    let stackY = plotHeight - avatarSize/2 - CONFIG.PLOT.BOTTOM_MARGIN;

    // Stack upward, checking for overlaps
    for (let existingY of existingAvatarsAtLevel.reverse()) {
        if (Math.abs(stackY - existingY) < avatarSize) {
            stackY = existingY - avatarSize;
        }
    }

    // Ensure we don't go above the plot area
    stackY = Math.max(avatarSize/2, stackY);

    return {
        x: targetX,
        y: stackY
    };
}

/**
 * Find stacking position (static - uses array)
 * Extracted from lines 1295-1326
 */
export function findStackingPositionStatic(targetX, roundedSupport, currentUsername, plotWidth, plotHeight, avatarSize, positionedAvatars) {
    const tolerance = plotWidth * CONFIG.PLOT.STACKING_TOLERANCE;
    const existingAvatarsAtLevel = [];

    for (const positioned of positionedAvatars) {
        if (Math.abs(positioned.x - targetX) <= tolerance) {
            existingAvatarsAtLevel.push(positioned.y);
        }
    }

    // Sort existing Y positions
    existingAvatarsAtLevel.sort((a, b) => a - b);

    // Find the best Y position (stack from bottom up)
    let stackY = plotHeight - avatarSize/2 - CONFIG.PLOT.BOTTOM_MARGIN;

    // Stack upward, checking for overlaps
    for (let existingY of existingAvatarsAtLevel.reverse()) {
        if (Math.abs(stackY - existingY) < avatarSize) {
            stackY = existingY - avatarSize;
        }
    }

    // Ensure we don't go above the plot area
    stackY = Math.max(avatarSize/2, stackY);

    return {
        x: targetX,
        y: stackY
    };
}

/**
 * Animate avatar to position
 * Extracted from lines 1203-1248
 */
export function animateAvatarToPosition(avatar, participantData, plot, avatarSize = null) {
    const plotWidth = plot.offsetWidth;
    const plotHeight = plot.offsetHeight;

    // If no size provided, calculate it dynamically
    if (!avatarSize) {
        const isModalOpen = document.body.classList.contains('participant-modal-open') ||
                            document.body.classList.contains('meta-panel-open');
        const participants = Array.from(AppState.currentParticipants.values());
        avatarSize = calculateDynamicAvatarSize(participants, plotHeight, isModalOpen, AppState.totalParticipantCount);
    }

    // Round support to nearest 5
    const roundedSupport = Math.round(participantData.predicted_agreement / 5) * 5;

    // Calculate x position based on rounded support
    let x = (roundedSupport / 100) * plotWidth;

    // Ensure x stays within bounds
    x = Math.max(avatarSize/2, Math.min(plotWidth - avatarSize/2, x));

    // Find vertical stacking position
    const finalPosition = findStackingPosition(x, roundedSupport, participantData.username, plotWidth, plotHeight, avatarSize);

    // Start position: top of chart
    const startX = finalPosition.x - avatarSize/2;
    const startY = CONFIG.PLOT.START_Y;
    const finalX = finalPosition.x - avatarSize/2;
    const finalY = finalPosition.y - avatarSize/2;

    // Set initial position and size
    avatar.style.left = startX + 'px';
    avatar.style.top = startY + 'px';
    avatar.style.width = avatarSize + 'px';
    avatar.style.height = avatarSize + 'px';
    avatar.style.transition = 'none';

    // Force reflow
    avatar.offsetHeight;

    // Animate to final position
    setTimeout(() => {
        avatar.style.transition = 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)';
        avatar.style.left = finalX + 'px';
        avatar.style.top = finalY + 'px';

        // Update visual state
        const borderColor = getSupportBorderColor(participantData.predicted_agreement);
        avatar.style.borderColor = borderColor;
        avatar.style.opacity = '1';
        avatar.style.transform = 'scale(1)';
        avatar.classList.remove('processing');
    }, CONFIG.DELAYS.REFLOW);
}

// =============================================================================
// PARTICIPANT UPDATES
// =============================================================================

/**
 * Update single participant (called during streaming)
 * Extracted from lines 1039-1067
 */
export function updateSingleParticipant(participantData, loadModalCallback) {
    // Store participant data
    AppState.currentParticipants.set(participantData.username, participantData);

    const container = getElement('avatars-container');
    const plot = getElement('editor-support-plot');

    if (!container || !plot) {
        Logger.error('Missing container or plot element');
        return;
    }

    // Find existing avatar or create new one
    let avatar = container.querySelector(`[data-participant-id="${participantData.username}"]`);

    if (!avatar) {
        avatar = createAvatarElement(participantData, loadModalCallback);
        container.appendChild(avatar);
    } else {
        updateExistingAvatar(avatar, participantData);
    }

    // Animate to position (uses default or existing size)
    animateAvatarToPosition(avatar, participantData, plot);

    // Update meta-medley groups
    updateMetaMedleyGroups(Array.from(AppState.currentParticipants.values()));
}

/**
 * Update all avatars (bulk update)
 * Extracted from lines 1615-1692
 */
export function updateAvatars(results, loadModalCallback) {
    console.log('🔄 updateAvatars called with', results.length, 'participants');
    Logger.debug('Updating avatars');

    const container = getElement('avatars-container');
    const plot = getElement('editor-support-plot');

    if (!container || !plot) {
        Logger.error('Missing container or plot element');
        return;
    }

    // Clear existing avatars
    container.innerHTML = '';

    // Force reflow
    plot.offsetHeight;

    const plotWidth = plot.offsetWidth;
    const plotHeight = plot.offsetHeight;
    Logger.debug('Plot dimensions:', plotWidth, plotHeight);

    if (plotWidth === 0 || plotHeight === 0) {
        setTimeout(() => updateAvatars(results, loadModalCallback), 100);
        return;
    }

    // Store total participant count for scaling (first time only)
    if (AppState.totalParticipantCount === 0) {
        AppState.totalParticipantCount = results.length;
        Logger.debug('Stored total participant count:', AppState.totalParticipantCount);
    }

    // Calculate dynamic avatar size ONCE for all participants
    const isModalOpen = document.body.classList.contains('participant-modal-open') ||
                        document.body.classList.contains('meta-panel-open');
    const avatarSize = calculateDynamicAvatarSize(results, plotHeight, isModalOpen, AppState.totalParticipantCount);

    const positionedAvatars = [];

    results.forEach((participant, index) => {
        // Create avatar with calculated size
        const avatar = createAvatarElement(participant, loadModalCallback, avatarSize);
        avatar.className = 'participant-avatar';

        // Apply support-based border color
        const borderColor = getSupportBorderColor(participant.predicted_agreement);
        avatar.style.borderColor = borderColor;

        // Calculate stacking position
        const roundedSupport = Math.round(participant.predicted_agreement / 5) * 5;
        let x = (roundedSupport / 100) * plotWidth;
        x = Math.max(avatarSize/2, Math.min(plotWidth - avatarSize/2, x));

        const stackingPosition = findStackingPositionStatic(x, roundedSupport, participant.username, plotWidth, plotHeight, avatarSize, positionedAvatars);

        // Set initial position (top of chart)
        const startX = stackingPosition.x - avatarSize/2;
        const startY = CONFIG.PLOT.START_Y;
        avatar.style.left = startX + 'px';
        avatar.style.top = startY + 'px';
        avatar.style.transition = 'none';

        container.appendChild(avatar);
        positionedAvatars.push({x: stackingPosition.x, y: stackingPosition.y, element: avatar});
    });

    // Animate avatars dropping down with stagger
    const avatars = container.querySelectorAll('.participant-avatar');
    avatars.forEach((avatar, index) => {
        avatar.offsetHeight; // Force reflow

        setTimeout(() => {
            const avatarData = positionedAvatars[index];
            const finalX = avatarData.x - avatarSize/2;
            const finalY = avatarData.y - avatarSize/2;

            avatar.style.transition = 'all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)';
            avatar.style.left = finalX + 'px';
            avatar.style.top = finalY + 'px';
            avatar.style.opacity = '1';
            avatar.style.transform = 'scale(1)';
        }, index * CONFIG.DELAYS.STAGGER);
    });
}

// =============================================================================
// META-MEDLEY GROUPS
// =============================================================================

/**
 * Update meta-medley groups based on participants
 * Extracted from lines 1365-1401
 */
export function updateMetaMedleyGroups(participants) {
    if (!Array.isArray(participants) || participants.length === 0) {
        AppState.metaMedley.groups = { bottom: [], middle: [], top: [] };
        return;
    }

    const sorted = [...participants].sort((a, b) => {
        const aSupport = typeof a.predicted_agreement === 'number' ? a.predicted_agreement : 0;
        const bSupport = typeof b.predicted_agreement === 'number' ? b.predicted_agreement : 0;
        return aSupport - bSupport;
    });

    let bottom = [];
    let middle = [];
    let top = [];

    if (sorted.length >= CONFIG.META_MEDLEY.TOTAL_PARTICIPANTS) {
        bottom = sorted.slice(0, CONFIG.META_MEDLEY.GROUP_SIZE);
        middle = sorted.slice(CONFIG.META_MEDLEY.GROUP_SIZE, CONFIG.META_MEDLEY.GROUP_SIZE * 2);
        top = sorted.slice(CONFIG.META_MEDLEY.GROUP_SIZE * 2, CONFIG.META_MEDLEY.GROUP_SIZE * 3);
    } else {
        const third = Math.floor(sorted.length / 3);
        bottom = sorted.slice(0, third);
        middle = sorted.slice(third, third * 2);
        top = sorted.slice(third * 2);
    }

    AppState.metaMedley.groups = {
        bottom: bottom.map(p => p.username),
        middle: middle.map(p => p.username),
        top: top.map(p => p.username)
    };

    if (AppState.metaMedley.activeGroup) {
        applyGroupAvatarFocus(AppState.metaMedley.activeGroup);
    }
}

/**
 * Apply group avatar focus (highlight/dim)
 * Extracted from lines 1407-1429
 */
export function applyGroupAvatarFocus(groupKey) {
    if (!groupKey || !AppState.metaMedley.groups || !AppState.metaMedley.groups[groupKey]) {
        return;
    }

    const targetUsernames = new Set(AppState.metaMedley.groups[groupKey] || []);

    if (targetUsernames.size === 0) {
        clearGroupAvatarFocus();
        return;
    }

    getAllAvatarElements().forEach(avatar => {
        const username = avatar.dataset.participantId || avatar.dataset.username;
        if (username && targetUsernames.has(username)) {
            avatar.classList.add('avatar-group-focus');
            avatar.classList.remove('avatar-dimmed');
        } else {
            avatar.classList.add('avatar-dimmed');
            avatar.classList.remove('avatar-group-focus');
        }
    });
}

/**
 * Clear group avatar focus
 * Extracted from lines 1431-1435
 */
export function clearGroupAvatarFocus() {
    getAllAvatarElements().forEach(avatar => {
        avatar.classList.remove('avatar-dimmed', 'avatar-group-focus');
    });
}

// =============================================================================
// CONFIDENCE FILTER
// =============================================================================

/**
 * Initialize confidence filter slider
 * Extracted from lines 1441-1466
 */
export function initializeConfidenceFilter() {
    const slider = getElement('confidenceSlider');
    const valueDisplay = getElement('confidenceValue');

    if (!slider || !valueDisplay) {
        Logger.warn('Confidence filter elements not found');
        return;
    }

    Logger.debug('Confidence filter initialized');

    // Update display value and hide/show avatars in real-time (while dragging)
    // Don't reposition or update mean line yet - just hide/show
    slider.addEventListener('input', function() {
        const value = parseInt(this.value);
        valueDisplay.textContent = value;
        Logger.debug('Slider value changed to:', value);
        applyConfidenceFilter(value, false, false);
    });

    // Reposition avatars AND update mean line when user releases the slider
    slider.addEventListener('change', function() {
        const value = parseInt(this.value);
        Logger.debug('Slider released at:', value);
        applyConfidenceFilter(value, true, true);
    });
}

/**
 * Apply confidence filter
 * Extracted from lines 1468-1524
 *
 * @param {number} minConfidence - Minimum confidence score to show
 * @param {boolean} shouldReposition - Whether to reposition avatars after filtering
 * @param {boolean} shouldUpdateMean - Whether to update mean support line for visible avatars
 */
function applyConfidenceFilter(minConfidence, shouldReposition = false, shouldUpdateMean = false) {
    const plot = getElement('editor-support-plot');
    if (!plot) {
        Logger.warn('Support plot not found');
        return;
    }

    const plotWidth = plot.offsetWidth;
    const plotHeight = plot.offsetHeight;

    const avatars = Array.from(getAllAvatarElements());
    Logger.debug(`Found ${avatars.length} avatars to filter`);

    if (avatars.length === 0) {
        Logger.warn('No avatars found to filter');
        return;
    }

    const visibleAvatars = [];
    const hiddenAvatars = [];

    avatars.forEach(avatar => {
        const confidence = parseFloat(avatar.getAttribute('data-confidence')) || 0;

        if (confidence >= minConfidence) {
            visibleAvatars.push(avatar);
            avatar.classList.remove('confidence-filtered');
        } else {
            hiddenAvatars.push(avatar);
            avatar.classList.add('confidence-filtered');
        }
    });

    Logger.debug(`Visible: ${visibleAvatars.length}, Hidden: ${hiddenAvatars.length}, Reposition: ${shouldReposition}, UpdateMean: ${shouldUpdateMean}`);

    // Hide filtered avatars
    hiddenAvatars.forEach(avatar => {
        avatar.style.opacity = '0';
        avatar.style.transform = 'scale(0)';
        avatar.style.pointerEvents = 'none';
    });

    // Show visible avatars
    visibleAvatars.forEach(avatar => {
        avatar.style.opacity = '1';
        avatar.style.transform = 'scale(1)';
        avatar.style.pointerEvents = 'auto';
    });

    // Reposition when user releases slider
    if (shouldReposition) {
        // Calculate dynamic size based on visible avatars only
        const visibleParticipants = Array.from(AppState.currentParticipants.values()).filter(p => {
            const confidence = p.confidence_score || 0;
            return confidence >= minConfidence;
        });
        const isModalOpen = document.body.classList.contains('participant-modal-open') ||
                            document.body.classList.contains('meta-panel-open');
        const avatarSize = calculateDynamicAvatarSize(visibleParticipants, plotHeight, isModalOpen, AppState.totalParticipantCount);

        repositionVisibleAvatars(visibleAvatars, plotWidth, plotHeight, avatarSize);
    }

    // Update mean support line for visible avatars only when user releases slider
    if (shouldUpdateMean) {
        updateMeanForVisibleAvatars();
    }
}

/**
 * Reposition visible avatars
 * Extracted from lines 1526-1585
 */
function repositionVisibleAvatars(avatars, plotWidth, plotHeight, avatarSize) {
    Logger.debug('Repositioning', avatars.length, 'visible avatars');

    const positionedAvatars = [];

    // Sort avatars by support level
    avatars.sort((a, b) => {
        const supportA = parseFloat(a.getAttribute('data-support')) || 0;
        const supportB = parseFloat(b.getAttribute('data-support')) || 0;

        if (Math.abs(supportA - supportB) < 2.5) {
            const usernameA = a.getAttribute('data-participant-id') || '';
            const usernameB = b.getAttribute('data-participant-id') || '';
            return usernameA.localeCompare(usernameB);
        }
        return supportA - supportB;
    });

    // Reposition each avatar
    avatars.forEach((avatar, index) => {
        const support = parseFloat(avatar.getAttribute('data-support')) || 0;
        const username = avatar.getAttribute('data-participant-id');

        const roundedSupport = Math.round(support / 5) * 5;
        const targetX = (roundedSupport / 100) * (plotWidth - avatarSize);

        const position = findStackingPositionStatic(
            targetX,
            roundedSupport,
            username,
            plotWidth,
            plotHeight,
            avatarSize,
            positionedAvatars
        );

        positionedAvatars.push(position);

        const leftPosition = position.x - avatarSize/2;
        const topPosition = position.y - avatarSize/2;

        Logger.debug(`Avatar ${index} (${username}): support=${support}, left=${leftPosition}, top=${topPosition}`);

        avatar.style.left = `${leftPosition}px`;
        avatar.style.top = `${topPosition}px`;
        avatar.style.width = `${avatarSize}px`;
        avatar.style.height = `${avatarSize}px`;
        avatar.style.opacity = '1';
        avatar.style.transform = 'scale(1)';
        avatar.style.pointerEvents = 'auto';
    });
}

// =============================================================================
// CHART RESIZE
// =============================================================================

/**
 * Setup chart resize listener
 * Extracted from lines 1738-1748
 */
export function setupChartResizeListener() {
    const plot = getElement('editor-support-plot');
    if (!plot) return;

    plot.addEventListener('transitionend', (e) => {
        if (e.propertyName === 'max-width') {
            repositionAllAvatarsAfterResize();
        }
    });
}

/**
 * Reposition existing avatars without animation
 * Extracted from lines 1751-1790
 */
function repositionExistingAvatars() {
    const container = getElement('avatars-container');
    const plot = getElement('editor-support-plot');

    if (!container || !plot) return;

    const plotWidth = plot.offsetWidth;
    const plotHeight = plot.offsetHeight;

    // Calculate dynamic avatar size based on current participants
    const isModalOpen = document.body.classList.contains('participant-modal-open') ||
                        document.body.classList.contains('meta-panel-open');
    const participants = Array.from(AppState.currentParticipants.values());
    const avatarSize = calculateDynamicAvatarSize(participants, plotHeight, isModalOpen, AppState.totalParticipantCount);

    console.log('🔧 repositionExistingAvatars:', {
        isModalOpen,
        participantCount: participants.length,
        totalCount: AppState.totalParticipantCount,
        plotWidth,
        plotHeight,
        calculatedAvatarSize: avatarSize
    });

    const avatars = container.querySelectorAll('.participant-avatar');
    if (avatars.length === 0) return;

    const positionedAvatars = [];

    avatars.forEach(avatar => {
        const support = parseFloat(avatar.dataset.support);
        const username = avatar.dataset.participantId;

        if (isNaN(support)) return;

        const roundedSupport = Math.round(support / 5) * 5;
        let x = (roundedSupport / 100) * plotWidth;
        x = Math.max(avatarSize/2, Math.min(plotWidth - avatarSize/2, x));

        const stackingPosition = findStackingPositionStatic(x, roundedSupport, username, plotWidth, plotHeight, avatarSize, positionedAvatars);

        // Update avatar size and position
        avatar.style.width = avatarSize + 'px';
        avatar.style.height = avatarSize + 'px';
        avatar.style.left = (stackingPosition.x - avatarSize/2) + 'px';
        avatar.style.top = (stackingPosition.y - avatarSize/2) + 'px';

        positionedAvatars.push({x: stackingPosition.x, y: stackingPosition.y, element: avatar});
    });
}

/**
 * Reposition all avatars after chart resize
 * Extracted from lines 1793-1796
 */
export function repositionAllAvatarsAfterResize() {
    repositionExistingAvatars();
}

// =============================================================================
// SUMMARY STATS
// =============================================================================

/**
 * Calculate mean support from results
 * Extracted from lines 1006-1014
 */
export function calculateMeanSupport(results) {
    if (!results || results.length === 0) return 0;

    const totalAgreement = results.reduce((sum, participant) => {
        return sum + (participant.predicted_agreement || 0);
    }, 0);

    return Math.round(totalAgreement / results.length);
}

/**
 * Update mean support line on chart
 * Extracted from lines 1603-1613
 */
export function updateMeanSupportLine(meanSupport) {
    const meanLine = getElement('mean-support-line');
    const meanLabel = getElement('mean-support-label');
    const meanValue = getElement('mean-support-value');

    if (meanLine && meanLabel && meanValue) {
        meanLine.style.left = `calc(${meanSupport}% - 1px)`;
        meanLabel.style.left = `calc(${meanSupport}% - 75px)`;
        meanValue.textContent = meanSupport;
    }
}

/**
 * Update summary stats
 * Extracted from lines 1328-1341
 */
export function updateSummaryStats(results) {
    if (results.length === 0) return;

    let totalAgreement = 0;

    results.forEach(participant => {
        totalAgreement += participant.predicted_agreement;
    });

    const meanSupport = Math.round(totalAgreement / results.length);
    updateMeanSupportLine(meanSupport);
}

/**
 * Update mean support line based on visible (non-filtered) avatars only
 * Used when confidence filter is applied to show accurate mean of visible participants
 */
function updateMeanForVisibleAvatars() {
    Logger.debug('Updating mean support line for visible avatars');

    // Get all avatars that are NOT filtered out
    const visibleAvatars = Array.from(getAllAvatarElements()).filter(avatar =>
        !avatar.classList.contains('confidence-filtered')
    );

    if (visibleAvatars.length === 0) {
        Logger.warn('No visible avatars to calculate mean');
        return;
    }

    // Calculate total support from data-support attributes on visible avatars
    let totalSupport = 0;
    visibleAvatars.forEach(avatar => {
        const support = parseFloat(avatar.getAttribute('data-support')) || 0;
        totalSupport += support;
    });

    const meanSupport = Math.round(totalSupport / visibleAvatars.length);

    Logger.debug(`Calculating mean for ${visibleAvatars.length} visible participants: ${meanSupport}%`);

    // Update mean support line
    updateMeanSupportLine(meanSupport);
}

/**
 * Initialize avatars from template data
 * Reads participant data from window variable set by Django template
 */
export function initializeAvatars() {
    Logger.debug('Initializing avatars from template data');

    // Get participant data from window variable
    const initialData = window.PARTICIPANT_DATA_FROM_TEMPLATE || [];

    if (!initialData || initialData.length === 0) {
        Logger.warn('No participant data found');
        updateSummaryStats([]);
        AppState.recommendation.previousMeanSupport = 0;
        return;
    }

    Logger.debug('Initial data:', initialData);

    // Clear existing participants
    AppState.currentParticipants.clear();

    // Store participants in state
    initialData.forEach(participant => {
        AppState.currentParticipants.set(participant.username, participant);
    });

    Logger.debug('Current participants:', AppState.currentParticipants);

    if (initialData.length > 0) {
        const plot = document.getElementById('editor-support-plot');
        if (plot && plot.offsetWidth > 0 && plot.offsetHeight > 0) {
            // Import loadParticipantModal dynamically to avoid circular dependency
            import('./modals.js').then(({ loadParticipantModal }) => {
                // Update avatars with initial data and modal callback
                updateAvatars(initialData, loadParticipantModal);

                // Update stats and store initial mean support
                setTimeout(() => {
                    updateSummaryStats(initialData);
                    AppState.recommendation.previousMeanSupport = calculateMeanSupport(initialData);
                }, CONFIG.DELAYS.MODAL_INIT);
            });
        } else {
            // Plot not ready, retry
            setTimeout(() => initializeAvatars(), CONFIG.DELAYS.REFLOW);
        }
    } else {
        updateSummaryStats([]);
        AppState.recommendation.previousMeanSupport = 0;
    }
}
