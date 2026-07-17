const chatLog = document.getElementById('chat-log');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const globalStatus = document.getElementById('global-status');
const blastGateModal = document.getElementById('blast-gate-modal');
const blastGatePrompt = document.getElementById('blast-gate-prompt');

let currentSessionId = null;
let chatHistory = []; 
let currentLogsDiv = null;
let currentTextDiv = null;
let currentVMessageText = "";

// 1. Render the User's blue chat bubble
function appendUserMessage(text) {
    const row = document.createElement('div');
    row.className = 'message-row user';
    row.innerHTML = `<div class="bubble">${text}</div>`;
    chatLog.appendChild(row);
    chatLog.scrollTop = chatLog.scrollHeight;
}

// 2. Setup V's gray bubble with the embedded log accordion
function setupVTurn() {
    const row = document.createElement('div');
    row.className = 'message-row v';
    
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    
    // The collapsible logic accordion
    const details = document.createElement('details');
    details.className = 'engine-logs';
    details.innerHTML = `<summary>⚙️ View Process Logs</summary><div class="log-entries"></div>`;
    
    // The container for the final streamed response
    const textContent = document.createElement('div');
    textContent.className = 'v-text';
    
    bubble.appendChild(details);
    bubble.appendChild(textContent);
    row.appendChild(bubble);
    chatLog.appendChild(row);
    
    // Store references so the SSE can target them dynamically
    currentLogsDiv = details.querySelector('.log-entries');
    currentTextDiv = textContent;
}

// 3. The Main Execution Stream
function sendQuery(message) {
    appendUserMessage(message);
    userInput.value = '';
    
    // Push user prompt to memory
    chatHistory.push({ role: "user", content: message });
    
    const encodedMsg = encodeURIComponent(message);
    const encodedHistory = encodeURIComponent(JSON.stringify(chatHistory));
    const eventSource = new EventSource(`/stream_response?prompt=${encodedMsg}&history=${encodedHistory}`);

    setupVTurn();
    currentVMessageText = "";
    
    if (globalStatus) {
        globalStatus.innerText = "Thinking...";
        globalStatus.style.color = "#F59E0B"; // Amber
    }

    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);

        if (data.type === "status") {
            currentLogsDiv.innerText += `> ${data.content}\n`;
            chatLog.scrollTop = chatLog.scrollHeight;
            
        } else if (data.type === "token") {
            if (globalStatus) globalStatus.innerText = "Synthesizing...";
            
            // Render line breaks safely in HTML
            const safeText = data.content.replace(/\n/g, '<br>');
            currentTextDiv.innerHTML += safeText;
            currentVMessageText += data.content; 
            chatLog.scrollTop = chatLog.scrollHeight;
            
        } else if (data.type === "warning" || data.type === "error") {
            currentLogsDiv.innerText += `[ERROR] ${data.content}\n`;
            currentLogsDiv.parentElement.open = true; // Auto-open accordion to show the error
            
        } else if (data.type === "blocked") {
            if (globalStatus) globalStatus.innerText = "Intercepted";
            currentSessionId = data.session_id || "pending_auth"; 
            
            if (blastGatePrompt) blastGatePrompt.innerText = data.content;
            if (blastGateModal) blastGateModal.classList.remove('hidden');
            
            currentTextDiv.innerHTML += `<br><em style="color:#EF4444;">[Action Intercepted: Awaiting Human Authorization]</em>`;
            eventSource.close(); 
            
        } else if (data.type === "done") {
            // Commit final response to short-term memory
            chatHistory.push({ role: "assistant", content: currentVMessageText.trim() });
            
            // Memory compaction (keep last 10 turns to avoid URL overload)
            if (chatHistory.length > 10) chatHistory = chatHistory.slice(-10);
            
            if (globalStatus) {
                globalStatus.innerText = "Online";
                globalStatus.style.color = "#10B981"; // Green
            }
            eventSource.close();
        }
    };

    eventSource.onerror = function(err) {
        currentLogsDiv.innerText += `[STREAM DISCONNECTED]\n`;
        if (globalStatus) {
            globalStatus.innerText = "Error";
            globalStatus.style.color = "#EF4444";
        }
        eventSource.close();
    };
}

// 4. UI Triggers
sendBtn.addEventListener('click', () => {
    if (userInput.value.trim() !== '') sendQuery(userInput.value);
});

userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && userInput.value.trim() !== '') sendQuery(userInput.value);
});

// 5. The Blast Gate (Human-in-the-Loop) Resolution
async function resolveBlastGate(authChoice) {
    if (!currentSessionId) return;

    if (blastGateModal) blastGateModal.classList.add('hidden');
    
    // Setup a new bubble to display the system response to the auth decision
    setupVTurn();
    currentLogsDiv.innerText += `> Sending authorization: ${authChoice}\n`;
    currentLogsDiv.parentElement.open = true;

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
            currentTextDiv.innerHTML = data.v_response.replace(/\n/g, '<br>');
            chatHistory.push({ role: "assistant", content: data.v_response });
        } else {
            currentTextDiv.innerHTML = `<em style="color:#EF4444;">${data.detail || 'Authorization failed.'}</em>`;
        }
    } catch (error) {
        currentTextDiv.innerHTML = `<em style="color:#EF4444;">Network error during authorization.</em>`;
    } finally {
        currentSessionId = null;
    }
}

// Ensure the buttons exist before adding listeners to avoid null errors
document.getElementById('auth-yes-btn')?.addEventListener('click', () => resolveBlastGate('Y'));
document.getElementById('auth-no-btn')?.addEventListener('click', () => resolveBlastGate('N'));