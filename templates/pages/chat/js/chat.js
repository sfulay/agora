/**
 * AgoraChat JavaScript Module
 *
 * Handles chat interface, query submission, and medley playback
 */

// State
const state = {
    conversationId: window.CONVERSATION_ID,
    isLoading: false,
    currentAudio: null,
    currentSegmentIndex: 0,
    currentMedleySegments: []
};

// DOM Elements
const messagesContainer = document.getElementById('messages-container');
const queryInput = document.getElementById('query-input');
const sendButton = document.getElementById('send-button');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
});

function setupEventListeners() {
    sendButton.addEventListener('click', handleSendQuery);

    queryInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !state.isLoading) {
            handleSendQuery();
        }
    });
}

async function handleSendQuery() {
    const query = queryInput.value.trim();

    if (!query || state.isLoading) {
        return;
    }

    // Add user message to UI
    addUserMessage(query);

    // Clear input
    queryInput.value = '';

    // Disable input
    setLoading(true);

    try {
        // Send query to API
        const response = await fetch('/api/chat/query/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                query: query,
                conversation_id: state.conversationId
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();

        // Load medley data
        const medleyData = await loadMedley(data.response_message_id);

        // Add agora response with medley
        addAgoraMessage(medleyData);

    } catch (error) {
        console.error('Error sending query:', error);
        addErrorMessage('Sorry, something went wrong. Please try again.');
    } finally {
        setLoading(false);
    }
}

async function loadMedley(messageId) {
    const response = await fetch(`/api/chat/medley/${messageId}/`);

    if (!response.ok) {
        throw new Error(`Failed to load medley: ${response.status}`);
    }

    return await response.json();
}

function addUserMessage(text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message message-user';

    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'message-bubble';
    bubbleDiv.textContent = text;

    messageDiv.appendChild(bubbleDiv);
    messagesContainer.appendChild(messageDiv);

    scrollToBottom();
}

function addAgoraMessage(medleyData) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message message-agora';

    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'message-bubble';

    // Add relevance badge
    const relevanceClass = getRelevanceClass(medleyData.relevance_score);
    bubbleDiv.innerHTML = `
        <div>
            <strong>Here's what the agora has to say:</strong>
            <span class="relevance-badge ${relevanceClass}">${medleyData.relevance_score}% relevant</span>
        </div>
        <div style="margin-top: 10px; color: #666; font-size: 13px;">
            ${medleyData.gpt_reasoning}
        </div>
    `;

    // Add medley player
    const playerDiv = createMedleyPlayer(medleyData);
    bubbleDiv.appendChild(playerDiv);

    messageDiv.appendChild(bubbleDiv);
    messagesContainer.appendChild(messageDiv);

    scrollToBottom();
}

function getRelevanceClass(score) {
    if (score >= 75) return 'relevance-high';
    if (score >= 50) return 'relevance-medium';
    return 'relevance-low';
}

function createMedleyPlayer(medleyData) {
    const playerDiv = document.createElement('div');
    playerDiv.className = 'medley-player';

    // Title
    const title = document.createElement('div');
    title.innerHTML = `<strong><i class="bi bi-music-note-beamed"></i> Audio Medley</strong> (${Math.round(medleyData.total_duration)}s, ${medleyData.segments.length} clips)`;
    playerDiv.appendChild(title);

    // Segments list
    const segmentsList = document.createElement('div');
    segmentsList.style.maxHeight = '200px';
    segmentsList.style.overflowY = 'auto';
    segmentsList.style.marginTop = '10px';

    medleyData.segments.forEach((segment, index) => {
        const segmentItem = document.createElement('div');
        segmentItem.className = 'segment-item';
        segmentItem.id = `segment-${index}`;
        segmentItem.innerHTML = `
            <div><strong>${index + 1}. ${segment.participant_display_name}</strong> (${Math.round(segment.duration)}s)</div>
            <div class="segment-text">"${segment.segment_text}"</div>
        `;
        segmentsList.appendChild(segmentItem);
    });

    playerDiv.appendChild(segmentsList);

    // Audio player
    const audioContainer = document.createElement('div');
    audioContainer.style.marginTop = '15px';

    const audio = document.createElement('audio');
    audio.controls = true;
    audio.style.width = '100%';

    // Play button
    const playButton = document.createElement('button');
    playButton.innerHTML = '<i class="bi bi-play-fill"></i> Play Medley';
    playButton.className = 'send-button';
    playButton.style.marginTop = '10px';
    playButton.style.width = '100%';

    let currentSegmentIndex = 0;

    playButton.addEventListener('click', () => {
        if (medleyData.segments.length === 0) return;

        currentSegmentIndex = 0;
        playSegment(audio, medleyData.segments, currentSegmentIndex, playButton);
    });

    audio.addEventListener('ended', () => {
        currentSegmentIndex++;
        if (currentSegmentIndex < medleyData.segments.length) {
            playSegment(audio, medleyData.segments, currentSegmentIndex, playButton);
        } else {
            playButton.innerHTML = '<i class="bi bi-play-fill"></i> Play Medley';
            // Clear highlights
            medleyData.segments.forEach((_, i) => {
                const item = document.getElementById(`segment-${i}`);
                if (item) item.style.background = 'white';
            });
        }
    });

    audioContainer.appendChild(audio);
    audioContainer.appendChild(playButton);
    playerDiv.appendChild(audioContainer);

    return playerDiv;
}

function playSegment(audioElement, segments, index, playButton) {
    const segment = segments[index];

    // Highlight current segment
    segments.forEach((_, i) => {
        const item = document.getElementById(`segment-${i}`);
        if (item) {
            item.style.background = i === index ? '#e7f3ff' : 'white';
        }
    });

    // Update button
    playButton.innerHTML = `<i class="bi bi-pause-fill"></i> Playing ${index + 1}/${segments.length}`;

    // Load and play audio
    audioElement.src = segment.audio_url;
    audioElement.play();
}

function addErrorMessage(text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message message-agora';

    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'message-bubble';
    bubbleDiv.style.background = '#f8d7da';
    bubbleDiv.style.color = '#721c24';
    bubbleDiv.innerHTML = `<i class="bi bi-exclamation-triangle-fill"></i> ${text}`;

    messageDiv.appendChild(bubbleDiv);
    messagesContainer.appendChild(messageDiv);

    scrollToBottom();
}

function setLoading(loading) {
    state.isLoading = loading;
    sendButton.disabled = loading;
    queryInput.disabled = loading;

    if (loading) {
        // Add loading indicator
        const loadingDiv = document.createElement('div');
        loadingDiv.id = 'loading-indicator';
        loadingDiv.className = 'loading-indicator';
        loadingDiv.innerHTML = '<i class="bi bi-arrow-repeat"></i><div>Searching interviews and creating medley...</div>';
        messagesContainer.appendChild(loadingDiv);
        scrollToBottom();
    } else {
        // Remove loading indicator
        const loadingDiv = document.getElementById('loading-indicator');
        if (loadingDiv) {
            loadingDiv.remove();
        }
    }
}

function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}
