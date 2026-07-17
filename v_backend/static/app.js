const chatLog = document.getElementById('chat-log');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const blastGateModal = document.getElementById('blast-gate-modal');
const blastGatePrompt = document.getElementById('blast-gate-prompt');

let currentSessionId = null;
let currentVMessageDiv = null; 

// NEW: Client-side memory states
let chatHistory = []; 
let currentVMessageText = ""; 

function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    msgDiv.innerText = `${role.toUpperCase()}: ${text}`;
    chatLog.appendChild(msgDiv);
    chatLog.scrollTop = chatLog.scrollHeight;
    return msgDiv; 
}

function sendQuery(message) {
    appendMessage('user', message);
    userInput.value = '';
    currentVMessageDiv = null; 
    currentVMessageText = ""; // Reset the buffer for the incoming response
    
    // Commit the user's prompt to the short-term history
    chatHistory.push({ role: "user", content: message });
    
    // Package the prompt and the history array into the SSE request
    const encodedMsg = encodeURIComponent(message);
    const encodedHistory = encodeURIComponent(JSON.stringify(chatHistory));
    const eventSource = new EventSource(`/stream_response?prompt=${encodedMsg}&history=${encodedHistory}`);

    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);

        if (data.type === "status") {
            appendMessage('system', data.content);
            
        } else if (data.type === "token") {
            if (!currentVMessageDiv) {
                currentVMessageDiv = appendMessage('v', '');
                currentVMessageDiv.innerText = 'V: '; 
            }
            // Append visually for the UI, and buffer internally for the memory array
            currentVMessageDiv.innerText += data.content;
            currentVMessageText += data.content; 
            chatLog.scrollTop = chatLog.scrollHeight;
            
        } else if (data.type === "warning" || data.type === "error") {
            appendMessage('error', data.content);
            
        } else if (data.type === "blocked") {
            currentSessionId = data.session_id || "pending_auth"; 
            blastGatePrompt.innerText = data.content;
            blastGateModal.classList.remove('hidden');
            eventSource.close(); 
            
        } else if (data.type === "done") {
            // The response is complete. Push V's full answer into the memory array.
            chatHistory.push({ role: "assistant", content: currentVMessageText.trim() });
            
            // Memory Compaction: Prevent the URL from getting too massive (keep last 10 turns)
            if (chatHistory.length > 10) chatHistory = chatHistory.slice(-10);
            
            eventSource.close();
        }
    };

    eventSource.onerror = function(err) {
        appendMessage('error', 'Connection lost or stream crashed.');
        eventSource.close();
    };
}

// UI Event Listeners
sendBtn.addEventListener('click', () => {
    if (userInput.value.trim() !== '') sendQuery(userInput.value);
});

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
            // Inject authorized bypass actions back into the context window
            chatHistory.push({ role: "assistant", content: data.v_response });
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