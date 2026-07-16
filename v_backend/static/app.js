const chatLog = document.getElementById('chat-log');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const blastGateModal = document.getElementById('blast-gate-modal');
const blastGatePrompt = document.getElementById('blast-gate-prompt');

let currentSessionId = null;

function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    msgDiv.innerText = `${role.toUpperCase()}: ${text}`;
    chatLog.appendChild(msgDiv);
    chatLog.scrollTop = chatLog.scrollHeight;
}

function sendQuery(message) {
    appendMessage('user', message);
    userInput.value = '';
    
    // Open the Server-Sent Events stream
    const encodedMsg = encodeURIComponent(message);
    const eventSource = new EventSource(`/stream/?message=${encodedMsg}`);

    eventSource.addEventListener('status', (e) => {
        const data = JSON.parse(e.data);
        appendMessage('system', data.message);
    });

    eventSource.addEventListener('thought', (e) => {
        const data = JSON.parse(e.data);
        appendMessage('thought', data.thought);
    });

    eventSource.addEventListener('security_intercept', (e) => {
        const data = JSON.parse(e.data);
        currentSessionId = data.session_id;
        blastGatePrompt.innerText = data.prompt;
        blastGateModal.classList.remove('hidden');
        eventSource.close(); // Pause stream pending user action
    });

    eventSource.addEventListener('final_answer', (e) => {
        const data = JSON.parse(e.data);
        appendMessage('v', data.answer);
        eventSource.close(); // Close stream on completion
    });

    eventSource.addEventListener('error', (e) => {
        appendMessage('error', 'Connection lost or stream crashed.');
        eventSource.close();
    });
}

// Event Listeners for the UI
sendBtn.addEventListener('click', () => {
    if (userInput.value.trim() !== '') sendQuery(userInput.value);
});


async function resolveBlastGate(authChoice) {
    if (!currentSessionId) return;

    // 1. Hide the modal immediately
    blastGateModal.classList.add('hidden');
    appendMessage('system', `Sending authorization: ${authChoice}`);

    try {
        // 2. Send the authorization back to the POST endpoint
        const response = await fetch('/chat/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                user_auth: authChoice
            })
        });

        const data = await response.json();
        
        // 3. Print V's final answer after the gate unfreezes
        if (response.ok) {
            appendMessage('v', data.v_response);
        } else {
            appendMessage('error', data.detail || 'Authorization failed.');
        }
    } catch (error) {
        appendMessage('error', 'Network error during authorization.');
    } finally {
        currentSessionId = null; // Clear the session state
    }
}

// Attach the event listeners to the modal buttons
document.getElementById('auth-yes-btn').addEventListener('click', () => resolveBlastGate('Y'));
document.getElementById('auth-no-btn').addEventListener('click', () => resolveBlastGate('N'));
