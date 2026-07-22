const chatLog = document.getElementById('chat-log');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const globalStatus = document.getElementById('global-status');

let chatHistory = []; 
let currentLogsDiv = null;
let currentTextDiv = null;
let currentVMessageText = "";
let isStreaming = false; // Concurrency lock to prevent multiple streams

function appendUserMessage(text) {
    const row = document.createElement('div');
    row.className = 'message-row user';
    row.innerHTML = `<div class="bubble">${text}</div>`;
    chatLog.appendChild(row);
    chatLog.scrollTop = chatLog.scrollHeight;
}

function setupVTurn() {
    const row = document.createElement('div');
    row.className = 'message-row v';
    
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    
    const details = document.createElement('details');
    details.className = 'engine-logs';
    details.innerHTML = `<summary>⚙️ View Process Logs</summary><div class="log-entries"></div>`;
    
    const textContent = document.createElement('div');
    textContent.className = 'v-text';
    
    bubble.appendChild(details);
    bubble.appendChild(textContent);
    row.appendChild(bubble);
    chatLog.appendChild(row);
    
    currentLogsDiv = details.querySelector('.log-entries');
    currentTextDiv = textContent;
}

// Function to lock/unlock the UI
function toggleInput(state) {
    isStreaming = !state;
    userInput.disabled = !state;
    sendBtn.disabled = !state;
    if (state) userInput.focus();
}

function sendQuery(message) {
    if (isStreaming) return; // Hard block against spam clicking
    toggleInput(false);
    
    appendUserMessage(message);
    userInput.value = '';
    
    chatHistory.push({ role: "user", content: message });
    
    const encodedMsg = encodeURIComponent(message);
    const encodedHistory = encodeURIComponent(JSON.stringify(chatHistory));
    const eventSource = new EventSource(`/stream_response?prompt=${encodedMsg}&history=${encodedHistory}`);

    setupVTurn();
    currentVMessageText = "";
    
    if (globalStatus) {
        globalStatus.innerText = "Thinking...";
        globalStatus.style.color = "#F59E0B"; 
    }

    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);

        if (data.type === "status") {
            // FIX: Create an independent DOM node to avoid innerText race conditions
            const logLine = document.createElement('div');
            logLine.innerText = `> ${data.content}`;
            currentLogsDiv.appendChild(logLine);
            chatLog.scrollTop = chatLog.scrollHeight;
            
        } else if (data.type === "token") {
            if (globalStatus) globalStatus.innerText = "Synthesizing...";
            
            // 1. Accumulate raw token string
            currentVMessageText += (data.content || ""); 
            
            // 2. Parse complete Markdown safely to HTML on every token
            currentTextDiv.innerHTML = marked.parse(currentVMessageText);
            
            chatLog.scrollTop = chatLog.scrollHeight;
            
        } else if (data.type === "warning" || data.type === "error") {
            const errorLine = document.createElement('div');
            errorLine.innerText = `[ERROR] ${data.content}`;
            currentLogsDiv.appendChild(errorLine);
            currentLogsDiv.parentElement.open = true; 
            
        } else if (data.type === "blocked") {
            if (globalStatus) globalStatus.innerText = "Intercepted";
            currentTextDiv.innerHTML += `<br><em style="color:#EF4444;">[Action Intercepted: Security Halt]</em>`;
            eventSource.close();
            toggleInput(true);
            
        } else if (data.type === "done") {
            chatHistory.push({ role: "assistant", content: currentVMessageText.trim() });
            if (chatHistory.length > 10) chatHistory = chatHistory.slice(-10);
            
            if (globalStatus) {
                globalStatus.innerText = "Online";
                globalStatus.style.color = "#10B981"; 
            }
            eventSource.close();
            toggleInput(true);
        }
    };

    eventSource.onerror = function(err) {
        const disconnectLine = document.createElement('div');
        disconnectLine.innerText = `[STREAM DISCONNECTED]`;
        currentLogsDiv.appendChild(disconnectLine);
        currentLogsDiv.parentElement.open = true;

        if (globalStatus) {
            globalStatus.innerText = "Error";
            globalStatus.style.color = "#EF4444";
        }
        eventSource.close();
        toggleInput(true);
    };
}

sendBtn.addEventListener('click', () => {
    if (userInput.value.trim() !== '') sendQuery(userInput.value);
});

userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && userInput.value.trim() !== '') sendQuery(userInput.value);
});