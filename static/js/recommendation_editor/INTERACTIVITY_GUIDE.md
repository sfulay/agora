# Recommendation Editor - Interactivity Guide

This document explains how all the interactive features work in the recommendation editor, from user actions to server responses.

---

## Table of Contents
1. [Page Load & Initialization](#1-page-load--initialization)
2. [Character Counter & Text Editing](#2-character-counter--text-editing)
3. [Avatar System](#3-avatar-system)
4. [Recompute with Streaming](#4-recompute-with-streaming)
5. [Confidence Filter](#5-confidence-filter)
6. [Participant Modals](#6-participant-modals)
7. [Meta-Medley Panels](#7-meta-medley-panels)
8. [Leaderboard](#8-leaderboard)
9. [Telemetry Tracking](#9-telemetry-tracking)

---

## 1. Page Load & Initialization

### What Happens When You Load the Page

```
User visits /editor/273/
    ↓
Django renders template
    ↓
Template creates window variables:
    - SHOW_AVATARS_FROM_TEMPLATE
    - BASE_REC_ID_FROM_TEMPLATE
    - CURRENT_REC_ID_FROM_TEMPLATE
    - CURRENT_USER_ID_FROM_TEMPLATE
    - ORIGINAL_TEXT_FROM_TEMPLATE
    - PARTICIPANT_DATA_FROM_TEMPLATE (array of ~90 participants)
    ↓
Browser loads /js/recommendation_editor/main.js
    ↓
main.js imports all modules:
    - config.js (constants)
    - state.js (AppState)
    - utils/* (helpers)
    - services/* (API, telemetry, streaming)
    - components/* (avatars, modals, leaderboard, etc.)
    ↓
DOMContentLoaded event fires
    ↓
main.js initialization:
    1. initializeState(templateData)
       → Stores recommendation IDs, user ID, avatar flag in AppState

    2. setupCharacterCounter()
       → Attaches input listener to textarea

    3. setupResetButton()
       → Attaches click listener to reset button

    4. new TelemetryTracker()
       → Creates telemetry instance with session ID

    5. initializeAvatars()
       → Reads PARTICIPANT_DATA_FROM_TEMPLATE
       → Calls updateAvatars() to create all avatar elements
       → Animates avatars dropping into position
       → Updates summary stats (mean, median, mode)

    6. initializeConfidenceFilter()
       → Attaches listeners to confidence slider

    7. setupChartResizeListener()
       → Watches for chart width changes (when modals/panels open)

    8. initializeLeaderboard()
       → Loads recommendation history from API
       → Sets up pagination and sorting

    9. setupMetaMedleyButtonDelegation()
       → Event delegation for bottom/middle/top medley buttons
```

**Files Involved:**
- `main.js` - orchestrates initialization
- `state.js` - initializes AppState
- `components/avatars.js` - creates initial avatars
- `components/leaderboard.js` - loads leaderboard data

---

## 2. Character Counter & Text Editing

### How the Character Counter Works

```
User types in textarea
    ↓
'input' event fires
    ↓
characterCounter.js → setupCharacterCounter()
    ↓
Updates character count display
    ↓
Changes color based on length:
    - < 400 chars: gray (#6c757d)
    - 400-450 chars: orange (#fd7e14)
    - > 450 chars: red (#dc3545)
    ↓
Updates status badge:
    - Text changed → "Modified" (yellow badge)
    - Text matches original → "Original" (gray badge)
```

### Reset Button

```
User clicks "Reset" button
    ↓
characterCounter.js → setupResetButton()
    ↓
1. Sets textarea value = ORIGINAL_TEXT_FROM_TEMPLATE
2. Updates character count
3. Sets status badge to "Original"
```

**Files Involved:**
- `components/characterCounter.js`
- `config.js` (CHAR_LIMITS constants)

---

## 3. Avatar System

### Avatar Creation & Positioning

```
updateAvatars(participantData) is called
    ↓
For each participant:
    ↓
1. createAvatarElement(participant)
   → Creates <div class="participant-avatar">
   → Sets background image to avatar_url
   → Calculates border color based on support level:
      - 0-50%: red → yellow gradient
      - 50-100%: yellow → green gradient
   → Adds tooltip with participant info
   → Adds click handler → loadParticipantModal()
    ↓
2. findStackingPosition(support_level)
   → Converts support % to X position (0-100% = left-right)
   → Finds Y position by stacking avatars at similar support levels
   → Uses STACKING_TOLERANCE (2%) to group nearby avatars
   → Returns {x, y} coordinates
    ↓
3. animateAvatarToPosition(avatar, position)
   → Starts avatar at top of chart (y = START_Y = 30px)
   → Animates with cubic-bezier easing ("bouncy" drop)
   → Uses STAGGER (75ms) delay between avatars
    ↓
4. Append to #avatars-container
```

### Avatar Click

```
User clicks on avatar
    ↓
Click event handler in createAvatarElement()
    ↓
1. Track telemetry:
   AppState.telemetry.trackAvatarClick(
       recId, participantId, avatarType, clickX, clickY
   )
   → Sends POST to /api/telemetry/avatar/click/
    ↓
2. Load modal:
   loadParticipantModal(username)
   → See "Participant Modals" section below
```

### Avatar Tooltips

```
Mouse enters avatar
    ↓
showTooltip(element, participantData)
    ↓
1. Creates/gets #global-avatar-tooltip div
2. Sets tooltip content:
   - Display name
   - Predicted support %
   - Confidence score
3. Positions tooltip near cursor
4. Shows tooltip with fade-in
    ↓
Mouse leaves avatar
    ↓
hideTooltip()
    ↓
Fades out and hides tooltip
```

**Files Involved:**
- `components/avatars.js` - all avatar logic
- `utils/colors.js` - support color calculations
- `config.js` - avatar sizes, delays, stacking tolerance

---

## 4. Recompute with Streaming

### The Full Recompute Flow

```
User clicks "Recompute" button
    ↓
main.js → setupRecomputeButton()
    ↓
Validation:
    1. Text not empty?
    2. Length ≤ 500 chars?
    ↓
UI Updates:
    - Status badge → "Computing..." (black)
    - Disable recompute button
    - Disable all medley buttons
    - Show progress bar (0%)
    - Clear existing avatars
    - Clear AppState.currentParticipants
    - Show live progress: "0 / ? completed"
    ↓
Start Server-Sent Events (SSE) stream:
    ↓
streaming.js → startRecomputeStream(recId, newText, callbacks)
    ↓
Opens EventSource connection:
    GET /api/editor/273/recompute-stream/?rec_text=<new_text>
    ↓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SERVER SIDE (Django)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

views.py → recompute_recommendation_stream()
    ↓
1. Creates new Recommendation object with new text
2. Gets all participants (~90)
3. Streams updates back to client:
    ↓
    Event 1: {'type': 'started', 'new_recommendation_id': 274}
    Event 2: {'type': 'total_count', 'total': 90}
    Event 3: {'type': 'participant_update', 'participant': {...}, 'completed': 1}
    Event 4: {'type': 'participant_update', 'participant': {...}, 'completed': 2}
    ...
    Event 91: {'type': 'participant_update', 'participant': {...}, 'completed': 90}
    Event 92: {'type': 'completed', 'new_recommendation_id': 274}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLIENT SIDE (JavaScript)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EventSource.onmessage receives events:
    ↓

Case 'started':
    → AppState.recommendation.currentId = 274
    → URL stays /editor/273/ but app now uses ID 274

Case 'total_count':
    → Update progress text: "0 / 90 completed"

Case 'participant_update':
    → Parse participant data
    → updateSingleParticipant(participant)
        → Create avatar element
        → Animate drop into position
        → Add to AppState.currentParticipants
    → Update progress bar: (completed / total) * 100%
    → Update progress text: "57 / 90 completed"

Case 'completed':
    → Update progress bar to 100%
    → Status badge → "Updated" (blue)
    → Calculate new mean support
    → Compare with previous mean:
        - Better → Green alert "Great job! 45% → 62%"
        - Worse → Red alert "Sorry! 62% → 45%"
        - Same → Blue alert "No change at 62%"
    → Update AppState.recommendation.previousMeanSupport
    → Reload leaderboard (after 1 second delay)
    → Re-enable recompute button
    → Re-enable medley buttons
    → Hide live progress indicator
    → Close EventSource connection

Case 'error':
    → Show error alert
    → Status badge → "Error" (red)
    → Re-enable buttons
    → Close connection
```

**Why Streaming?**
- **90 participants** = 90 AI predictions
- Each prediction takes ~1-2 seconds
- Total time: ~90-180 seconds
- Streaming lets users see progress in real-time instead of waiting 3 minutes!

**Files Involved:**
- `main.js` - setupRecomputeButton()
- `services/streaming.js` - startRecomputeStream()
- `components/avatars.js` - updateSingleParticipant()
- `pages/views.py` (server) - recompute_recommendation_stream()

---

## 5. Confidence Filter

### How the Slider Works

```
User drags confidence slider
    ↓
'input' event fires (real-time while dragging)
    ↓
avatars.js → applyConfidenceFilter(minConfidence, shouldReposition=false)
    ↓
For each avatar:
    if (participant.confidence_score < minConfidence):
        → Add class 'confidence-filtered'
        → CSS: opacity: 0, transform: scale(0)
        → Avatar disappears (smooth fade-out)
    else:
        → Remove class 'confidence-filtered'
        → Avatar visible
    ↓
User releases slider
    ↓
'change' event fires
    ↓
applyConfidenceFilter(minConfidence, shouldReposition=true)
    ↓
Reposition remaining avatars:
    1. Get all visible avatars (not filtered)
    2. Clear their current positions
    3. Call findStackingPositionStatic() for each
       → Recalculates stacking from bottom-up
    4. Animate to new positions
       → Avatars "drop down" to fill gaps
```

**Why Two Events?**
- **'input'** (while dragging): Hide/show avatars instantly for immediate feedback
- **'change'** (on release): Reposition avatars (expensive calculation) only once

**Files Involved:**
- `components/avatars.js` - initializeConfidenceFilter(), applyConfidenceFilter()
- `recommendation_editor.html` - slider HTML (lines 102-108)
- CSS (lines 3042-3055) - transition animations

---

## 6. Participant Modals

### Opening a Modal

```
User clicks avatar
    ↓
modals.js → loadParticipantModal(username)
    ↓
1. Check for existing container #dynamic-modal-container
   → Create if doesn't exist
    ↓
2. Fetch modal content from API:
   GET /api/medley/273/participant/alex_jones/
    ↓
3. Server returns JSON:
   {
       "participant_id": 42,
       "modal_html": "<div class='modal-dialog'>...</div>"
   }
    ↓
4. Create modal element:
   <div class="modal fade"
        id="participantModal-alex_jones"
        data-participant-id="42">
    ↓
5. Insert modal_html into modal
    ↓
6. Append to #dynamic-modal-container
    ↓
7. Wait 100ms, then initialize modal JavaScript:
   → initializeModalJavaScript(modal)
   → initializeMedleyModal(modal)
   → setupKaraokeTranscript(modal)
    ↓
8. Show modal using Bootstrap:
   new bootstrap.Modal(modal).show()
    ↓
9. Add body class: 'participant-modal-open'
    ↓
10. Trigger chart resize:
    CSS: #editor-support-plot { max-width: calc(100vw - 18% - 450px) }
    ↓
11. After 350ms, reposition avatars for new chart width:
    repositionAllAvatarsAfterResize()
```

### Modal Features

#### Karaoke Transcript
```
setupKaraokeTranscript(modal)
    ↓
For each transcript block:
    1. Split text into sentences (regex: /[^.!?]+[.!?]+/g)
    2. Wrap each sentence in <span class="karaoke-sentence">
    3. Attach audio.timeupdate listener:
       → Calculate: currentSentence = floor(currentTime / avgSentenceTime)
       → Highlight current sentence (yellow background)
       → Unhighlight others
    4. Click transcript → play/pause audio
```

#### Sequential Medley Playback
```
initializeMedleyModal(modal)
    ↓
Find all .segment-audio elements (3-5 audio clips)
    ↓
Load first segment into #medley-player
    ↓
User clicks play:
    → Highlight first transcript segment
    → Play audio
    ↓
Audio ends:
    → Load next segment
    → Highlight next transcript segment
    → Auto-play next audio
    ↓
All segments complete:
    → Reset to first segment
    → Remove all highlights
```

#### Form Validation
```
initializeModalJavaScript(modal)
    ↓
Monitor sliders:
    - Connection score (0-100)
    - Vote prediction (0-100)
    ↓
Both sliders touched?
    → Enable "Submit & Close" button (green)
Otherwise:
    → Disable button (gray)
    ↓
User clicks submit:
    → POST /api/submit_reflection/
    → Data: {recId, participantId, connectionScore, voteScore, text}
    → Close modal
```

### Closing a Modal

```
User clicks X or outside modal
    ↓
Bootstrap fires 'hidden.bs.modal' event
    ↓
1. Remove body class: 'participant-modal-open'
2. Trigger chart resize (chart expands back)
3. After 350ms, reposition avatars
4. Remove modal element from DOM
```

**Files Involved:**
- `components/modals.js` - loadParticipantModal(), initializeModalJavaScript(), etc.
- `services/api.js` - fetchParticipantModal()
- `pages/views.py` (server) - get_medley_participant_modal()

---

## 7. Meta-Medley Panels

### What are Meta-Medleys?
Groups of participants by support level:
- **Bottom 30** - lowest support (0-33%)
- **Middle 30** - medium support (33-66%)
- **Top 30** - highest support (66-100%)

### Opening a Panel

```
User clicks "Bottom 30", "Middle 30", or "Top 30" button
    ↓
Event delegation in main.js → setupMetaMedleyButtonDelegation()
    ↓
Detects click on .medley-button
    ↓
1. Track telemetry:
   AppState.telemetry.trackMetaMedleyClick(recId, 'bottom')
    ↓
2. Open panel:
   metaMedley.js → openMetaMedleyPanel(recId, 'bottom', button)
    ↓
3. Show loading state:
   → Button shows spinner: "Loading..."
   → Show #meta-medley-panel-loading overlay
    ↓
4. Add body class: 'meta-panel-open'
   → Chart width shrinks (same as modal)
    ↓
5. Update AppState:
   → AppState.metaMedley.activeGroup = 'bottom'
   → AppState.metaMedley.panelLoading = true
    ↓
6. Apply avatar focus:
   applyGroupAvatarFocus('bottom')
   → Dim avatars NOT in bottom group (opacity: 0.3)
   → Highlight avatars IN bottom group (opacity: 1.0)
    ↓
7. Fetch panel HTML:
   GET /api/meta-medley/273/bottom/
    ↓
8. Server returns HTML with:
   - 30 participant cards
   - Audio segments for each participant
   - Combined medley player
   - Transcript
    ↓
9. Create #meta-medley-panel-container
10. Insert HTML
11. Execute any <script> tags in HTML
    ↓
12. Wait 200ms, then initialize:
    → setupMetaMedleyAudio() - sequential playback
    → Add outside-click listener
    ↓
13. Hide loading state
14. Panel slides in from right
```

### Panel Audio System

```
setupMetaMedleyAudio()
    ↓
1. Find all .meta-segment-audio elements (30 clips)
2. Read duration from data-duration attribute
3. Calculate total duration
4. Load first segment into #meta-medley-audio player
    ↓
User clicks play button:
    ↓
    1. Highlight first transcript segment
    2. Play first audio clip
    3. Update progress bar
    4. Update time display (0:00 / 5:30)
        ↓
    Audio ends:
        ↓
        Load next segment
        Highlight next transcript segment
        Auto-play
        Update progress
        ↓
        (Repeat for all 30 segments)
        ↓
    All segments complete:
        → Remove all highlights
        → Reset to first segment
        → Update button to "play" state
```

### Closing a Panel

```
User clicks X button (onclick="closeMetaMedleyPanel()")
    ↓
metaMedley.js → closeMetaMedleyPanel()
    ↓
1. Stop audio & cleanup:
   → Pause audio
   → Remove event listeners
   → Reset progress bar
    ↓
2. Remove outside-click listener
    ↓
3. Remove #meta-medley-panel-container from DOM
    ↓
4. Clear avatar highlighting:
   → Remove 'meta-medley-highlight' class from all
   → clearGroupAvatarFocus() - restore all opacities
    ↓
5. Update AppState:
   → AppState.metaMedley.panelOpen = false
   → AppState.metaMedley.activeGroup = null
    ↓
6. Remove body class: 'meta-panel-open'
    → Chart expands back
    ↓
7. After 350ms, reposition avatars
```

**Outside Click to Close:**
```
Click anywhere on page
    ↓
handleOutsideClick(event)
    ↓
Is click outside panel?
AND not on medley button?
AND audio not playing?
    ↓
YES → closeMetaMedleyPanel()
NO → Ignore
```

**Files Involved:**
- `components/metaMedley.js` - panel open/close, audio system
- `main.js` - button event delegation, expose closeMetaMedleyPanel globally
- `pages/views.py` (server) - get_meta_medley_panel()
- `templates/pages/recommendations/meta_medley_panel.html` - panel template

---

## 8. Leaderboard

### Loading the Leaderboard

```
Page loads
    ↓
leaderboard.js → initializeLeaderboard()
    ↓
1. Setup collapse/expand chevron toggle:
   → Chevron right when collapsed
   → Chevron down when expanded
    ↓
2. Setup sort dropdown listener
3. Setup pagination buttons (prev/next)
    ↓
4. Load initial data:
   reloadLeaderboard()
    ↓
   Fetch from API:
   GET /api/editor/273/leaderboard/
    ↓
   Server returns:
   {
       "success": true,
       "leaderboard_data": [
           {
               "rec_id_for_sorting": 274,
               "rec_text": "New recommendation text...",
               "editor_id": 5,
               "editor_name": "John Doe",
               "mean_support": 62.5,
               "is_latest": true
           },
           {
               "rec_id_for_sorting": 273,
               "rec_text": "Previous version...",
               "editor_id": 5,
               "editor_name": "John Doe",
               "mean_support": 58.3,
               "is_latest": false
           },
           ...
       ]
   }
    ↓
5. Store data in LeaderboardState.currentData
6. Render table: renderLeaderboard()
```

### Rendering the Table

```
renderLeaderboard()
    ↓
1. Get current sort order from dropdown:
   - 'support' → Sort by mean_support DESC
   - 'recent' → Sort by rec_id_for_sorting DESC
    ↓
2. Filter to current user only:
   filteredData = data.filter(item => item.editor_id === currentUserId)
    ↓
3. Apply sort
    ↓
4. Paginate:
   - Page 1: items 0-9
   - Page 2: items 10-19
   - etc.
    ↓
5. Build HTML table:
   For each recommendation:
       Rank badge:
           #1 → Gold badge (bg-warning)
           #2 → Silver badge (bg-secondary)
           #3 → Bronze badge (bg-dark)
           Others → Light gray badge

       Latest indicator:
           is_latest === true → ⭐ star icon

       Row highlight:
           is_latest === true → Green background (table-success)
    ↓
6. Update pagination controls:
   - Show "1-10 of 25"
   - Enable/disable prev/next buttons
```

### User Interactions

```
User changes sort dropdown
    ↓
Reset to page 1
Re-render table with new sort
    ↓

User clicks "Previous"
    ↓
currentPage--
Re-render table
    ↓

User clicks "Next"
    ↓
currentPage++
Re-render table
    ↓

User clicks "Collapse/Expand"
    ↓
Bootstrap handles collapse
Chevron icon toggles direction
```

### Auto-Reload After Recompute

```
Recompute completes
    ↓
main.js → onCompleted callback
    ↓
Wait 1 second (DELAYS.LEADERBOARD_RELOAD)
    ↓
reloadLeaderboard()
    ↓
Fetch fresh data from API
Render updated table with new recommendation
```

**Files Involved:**
- `components/leaderboard.js` - all leaderboard logic
- `services/api.js` - fetchLeaderboard()
- `pages/views.py` (server) - get_leaderboard()

---

## 9. Telemetry Tracking

### What Gets Tracked?

**Avatar Clicks:**
```
User clicks avatar
    ↓
telemetry.js → trackAvatarClick(recId, participantId, avatarType, clickX, clickY)
    ↓
POST /api/telemetry/avatar/click/
Body: {
    recommendation_id: 273,
    participant_id: 42,
    avatar_type: 'other',
    click_x: 15,
    click_y: 8,
    session_id: '1701234567-abc123'
}
    ↓
Server creates AvatarClickTelemetry record:
    - Which user clicked
    - Which recommendation
    - Which participant avatar
    - Click position (for heatmaps)
    - Timestamp
```

**Meta-Medley Clicks:**
```
User clicks medley button
    ↓
telemetry.js → trackMetaMedleyClick(recId, 'bottom')
    ↓
POST /api/telemetry/meta-medley/click/
Body: {
    recommendation_id: 273,
    meta_medley_type: 'bottom',
    session_id: '1701234567-abc123'
}
    ↓
Server creates MetaMedleyClickTelemetry record
```

### Session ID

```
Page loads
    ↓
new TelemetryTracker()
    ↓
Generate session ID:
    sessionId = Date.now() + '-' + Math.random().toString(36).slice(2)
    Example: '1701234567-abc123'
    ↓
Store in AppState.telemetry
    ↓
Included in all telemetry requests
```

### Error Handling

```
Telemetry request fails (400, 404, 500)
    ↓
.catch() in trackAvatarClick() or trackMetaMedleyClick()
    ↓
Logger.warn('Telemetry failed (non-critical)')
    ↓
Continue normal operation
(User never sees error)
```

**Why Track?**
- Understand which participants users explore
- See which support groups get most attention
- Measure engagement with different features
- Build interaction heatmaps

**Files Involved:**
- `services/telemetry.js` - TelemetryTracker class
- `pages/views.py` (server) - track_avatar_click(), track_meta_medley_click()
- `pages/models.py` (server) - AvatarClickTelemetry, MetaMedleyClickTelemetry models

---

## Summary: The Complete User Journey

```
1. User loads page
   → Avatars drop into position
   → Leaderboard shows history

2. User edits recommendation text
   → Character counter updates in real-time
   → Status shows "Modified"

3. User clicks "Recompute"
   → Streaming begins
   → Avatars appear one-by-one (90 total, ~2 min)
   → Progress bar fills up
   → Comparison alert shows improvement/decline

4. User drags confidence slider
   → Low-confidence avatars fade out
   → Release slider → remaining avatars reposition

5. User clicks an avatar
   → Modal opens with participant details
   → Audio plays with karaoke highlighting
   → User rates connection and votes
   → Submit saves to database

6. User clicks "Bottom 30" medley button
   → Panel slides in from right
   → Bottom 30 avatars highlighted, others dimmed
   → User plays combined audio medley
   → 30 clips play sequentially with highlighting

7. User clicks outside panel
   → Panel closes
   → Avatar highlighting clears
   → Chart expands back

8. User checks leaderboard
   → Sees all their past recommendations
   → Sorts by support or recent
   → Pages through history
```

---

## Key Technologies

- **ES6 Modules** - Code organization
- **Server-Sent Events (SSE)** - Real-time streaming
- **Bootstrap Modals** - Participant details
- **Web Audio API** - Sequential playback
- **CSS Transitions** - Smooth animations
- **Django Templates** - Server-side rendering
- **Fetch API** - AJAX requests
- **Event Delegation** - Efficient event handling

---

## Performance Optimizations

1. **Stagger Animation** (75ms delay) - Prevents all 90 avatars animating at once
2. **requestAnimationFrame** - Smooth 60fps animations
3. **Event Delegation** - One listener for all medley buttons instead of 3
4. **Debounced Resize** - Only reposition after resize completes (350ms)
5. **Dynamic Imports** - Avoid circular dependencies
6. **Confidence Filter** - Separate input (real-time) from change (reposition)

---

## Debugging Tips

**Enable Debug Mode:**
```javascript
// In utils/logger.js
const DEBUG_MODE = true;  // Change from false to true
```

**Check Console:**
- Avatar creation: "Creating avatar for: alex_jones"
- Streaming: "EventSource: participant_update received"
- Modal: "Initializing medley modal"
- Panel: "Opening meta-medley panel: bottom"

**Common Issues:**
- Avatars not appearing → Check PARTICIPANT_DATA_FROM_TEMPLATE
- Modal not opening → Check participant_id in data
- Panel not closing → Check window.closeMetaMedleyPanel exists
- Streaming stuck → Check EventSource connection in Network tab

---

## File Reference

**Core:**
- `main.js` - Entry point, initialization
- `config.js` - All constants
- `state.js` - AppState management

**Components:**
- `avatars.js` - Avatar system (827 lines)
- `modals.js` - Participant modals (424 lines)
- `metaMedley.js` - Meta-medley panels (503 lines)
- `leaderboard.js` - Recommendation history (294 lines)
- `characterCounter.js` - Text input handling (75 lines)

**Services:**
- `api.js` - All fetch() calls (137 lines)
- `streaming.js` - EventSource for recompute (131 lines)
- `telemetry.js` - Analytics tracking (111 lines)

**Utils:**
- `dom.js` - DOM helpers (73 lines)
- `colors.js` - Support level colors (38 lines)
- `logger.js` - Debug logging (45 lines)

---

**Total:** ~3,205 lines of modular, documented JavaScript
**Original:** 2,354 lines of monolithic embedded code

The refactoring makes the code easier to understand, maintain, and debug! 🎉
