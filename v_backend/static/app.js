const chatLog = document.getElementById('chat-log');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const blastGateModal = document.getElementById('blast-gate-modal');
const blastGatePrompt = document.getElementById('blast-gate-prompt');

let currentSessionId = null;
let currentVMessageDiv = null; // Tracks the active token stream bubble

function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    msgDiv.innerText = `${role.toUpperCase()}: ${text}`;
    chatLog.appendChild(msgDiv);
    chatLog.scrollTop = chatLog.scrollHeight;
    return msgDiv; // Return the element so we can append tokens to it later
}

function sendQuery(message) {
    appendMessage('user', message);
    userInput.value = '';
    currentVMessageDiv = null; // Reset the active bubble for a new response
    
    // Connect to the correct async SSE endpoint
    const encodedMsg = encodeURIComponent(message);
    const eventSource = new EventSource(`/stream_response?prompt=${encodedMsg}`);

    // Single message handler to route the JSON payloads
    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);

        if (data.type === "status") {
            appendMessage('system', data.content);
            
        } else if (data.type === "token") {
            // If this is the first token, create the V bubble
            if (!currentVMessageDiv) {
                currentVMessageDiv = appendMessage('v', '');
                currentVMessageDiv.innerText = 'V: '; // Setup prefix
            }
            // Append the streaming token to the existing bubble
            currentVMessageDiv.innerText += data.content;
            chatLog.scrollTop = chatLog.scrollHeight;
            
        } else if (data.type === "warning" || data.type === "error") {
            appendMessage('error', data.content);
            
        } else if (data.type === "blocked") {
            // Trigger the human-in-the-loop intercept
            // Note: Session ID logic will need backend support to fully resume
            currentSessionId = data.session_id || "pending_auth"; 
            blastGatePrompt.innerText = data.content;
            blastGateModal.classList.remove('hidden');
            eventSource.close(); 
            
        } else if (data.type === "done") {
            eventSource.close();
        }
    };

    eventSource.onerror = function(err) {
        appendMessage('error', 'Connection lost or stream crashed.');
        eventSource.close();
    };
}

// Event Listeners for the UI
sendBtn.addEventListener('click', () => {
    if (userInput.value.trim() !== '') sendQuery(userInput.value);
});

// Allow hitting Enter to send
userInput.addEventListener('keypress', function (e) {
    if (e.key === 'Enter' && userInput.value.trim() !== '') {
        sendQuery(userInput.value);
    }
});

async function resolveBlastGate(authChoice) {
    if (!currentSessionId) return;

    blastGateModal.classList.add('hidden');
    appendMessage('system', `Sending authorization: ${authChoice}`);

    try {
        const response = await fetch('/chat/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                user_auth: authChoice
            })
        });

        const data = await response.json();
        
        if (response.ok) {
            appendMessage('v', data.v_response);
        } else {
            appendMessage('error', data.detail || 'Authorization failed.');
        }
    } catch (error) {
        appendMessage('error', 'Network error during authorization.');
    } finally {
        currentSessionId = null;
    }
}

document.getElementById('auth-yes-btn').addEventListener('click', () => resolveBlastGate('Y'));
document.getElementById('auth-no-btn').addEventListener('click', () => resolveBlastGate('N'));