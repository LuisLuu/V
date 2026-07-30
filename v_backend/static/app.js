/* ==========================================================================
   DOM ELEMENTS & STATE
   ========================================================================== */
// Auth Elements
const authOverlay = document.getElementById('auth-overlay');
const appContainer = document.getElementById('app-container');
const authTitle = document.getElementById('auth-title');
const authSubtitle = document.getElementById('auth-subtitle');
const pinInput = document.getElementById('pin-input');
const authBtn = document.getElementById('auth-btn');
const authError = document.getElementById('auth-error');

// Chat Elements
const chatLog = document.getElementById('chat-log');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const stopBtn = document.getElementById('stop-btn');
const globalStatus = document.getElementById('global-status');

// Task Elements
const taskList = document.getElementById('task-list');
const refreshBtn = document.getElementById('refresh-tasks-btn');
const newTaskInput = document.getElementById('new-task-input');
const addTaskBtn = document.getElementById('add-task-btn');

const sessionList = document.getElementById('session-list');
const newChatBtn = document.getElementById('new-chat-btn');

let currentSessionId = null;
let chatHistory = []; 
let currentLogsDiv = null;
let currentTextDiv = null;
let isStreaming = false;
let isSetupMode = false;
let activeEventSource = null;

/* ==========================================================================
   AUTHENTICATION LOGIC (The Security Gate)
   ========================================================================== */
async function checkAuthStatus() {
    try {
        const response = await fetch('/api/auth/status');
        const data = await response.json();
        
        if (data.is_setup) {
            isSetupMode = false;
            authTitle.innerText = "System Locked";
            authSubtitle.innerText = "Enter Master PIN to access V.";
            authBtn.innerText = "Unlock";
        } else {
            isSetupMode = true;
            authTitle.innerText = "Welcome to V";
            authSubtitle.innerText = "Create a Master PIN to secure local data.";
            authBtn.innerText = "Set PIN";
        }
    } catch (e) {
        authError.innerText = "Failed to connect to local server.";
    }
}

async function handleAuth() {
    const pin = pinInput.value.trim();
    if (pin.length < 4) {
        authError.innerText = "PIN must be at least 4 characters.";
        return;
    }

    const endpoint = isSetupMode ? '/api/auth/setup' : '/api/auth/verify';
    
    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin: pin })
        });

        if (response.ok) {
            authOverlay.remove();
            appContainer.style.display = 'grid'; 
            fetchTasks(); 
            fetchSessions();
        } else {
            const errorData = await response.json();
            authError.innerText = errorData.detail || "Authentication failed.";
        }
    } catch (e) {
        authError.innerText = "Server communication error.";
    }
}

authBtn.addEventListener('click', handleAuth);
pinInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') handleAuth();
});

/* ==========================================================================
   SESSION LOGIC
   ========================================================================== */
async function fetchSessions() {
    try {
        const response = await fetch('/api/sessions/');
        if (!response.ok) throw new Error("Failed to fetch sessions");
        const data = await response.json();
        
        sessionList.innerHTML = '';
        
        if (data.sessions.length === 0) {
            sessionList.innerHTML = '<div style="padding: 15px; color: #9CA3AF; text-align: center; font-size: 0.9rem;">No sessions yet.</div>';
            return;
        }

        data.sessions.forEach(session => {
            const container = document.createElement('div');
            container.style.cssText = `
                position: relative; /* Critical for anchoring the dropdown */
                display: flex; justify-content: space-between; align-items: center; 
                padding: 8px 12px; margin-bottom: 8px; border-radius: 8px; cursor: pointer; 
                background: ${session.id === currentSessionId ? '#E5E7EB' : 'transparent'};
                transition: background 0.2s;
            `;

            const titleSpan = document.createElement('span');
            titleSpan.innerText = session.title || "New Chat";
            titleSpan.style.cssText = `
                flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; 
                color: #1F2937; font-weight: ${session.id === currentSessionId ? '600' : '400'};
            `;
            titleSpan.onclick = () => switchSession(session.id);

            // Context Menu Button (The "⋮")
            const menuBtn = document.createElement('button');
            menuBtn.innerText = '⋮';
            menuBtn.style.cssText = `background: none; border: none; cursor: pointer; padding: 4px 8px; border-radius: 4px; color: #6B7280; font-weight: bold;`;
            
            // The Dropdown Element
            const dropdown = document.createElement('div');
            dropdown.className = 'session-dropdown';
            dropdown.innerHTML = `
                <div class="dropdown-item rename-item">Rename</div>
                <div class="dropdown-item delete-item">Delete</div>
            `;

            // Toggle Dropdown Logic
            menuBtn.onclick = (e) => {
                e.stopPropagation();
                // Close any other open dropdowns first
                document.querySelectorAll('.session-dropdown').forEach(d => d.style.display = 'none');
                dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
            };

            // Action Listeners
            dropdown.querySelector('.rename-item').onclick = (e) => {
                e.stopPropagation();
                dropdown.style.display = 'none';
                const newTitle = prompt("Enter new session name:", session.title); // Kept prompt here just for the text input, but it's triggered from the clean menu now
                if (newTitle) renameSession(session.id, newTitle);
            };

            dropdown.querySelector('.delete-item').onclick = (e) => {
                e.stopPropagation();
                dropdown.style.display = 'none';
                if (confirm("Are you sure you want to delete this session?")) deleteSession(session.id);
            };

            // Close dropdown if clicking anywhere else on the screen
            document.addEventListener('click', (e) => {
                if (!container.contains(e.target)) {
                    dropdown.style.display = 'none';
                }
            });

            container.appendChild(titleSpan);
            container.appendChild(menuBtn);
            container.appendChild(dropdown);
            sessionList.appendChild(container);
        });
    } catch (error) {
        console.error("Session Fetch Error:", error);
    }
}

async function renameSession(sessionId, newTitle) {
    await fetch(`/api/sessions/${sessionId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: newTitle })
    });
    fetchSessions();
}

async function deleteSession(sessionId) {
    await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' });
    if (currentSessionId === sessionId) {
        currentSessionId = null;
        chatLog.innerHTML = `<div class="welcome-screen" id="welcome-screen">
            <h1>Hello!</h1>
            <p>What are we building today?</p>
        </div>`;
    }
    fetchSessions();
}

async function createNewSession() {
    try {
        const response = await fetch('/api/sessions/', { method: 'POST' });
        const data = await response.json();
        currentSessionId = data.session_id;
        
        chatLog.innerHTML = `<div class="welcome-screen" id="welcome-screen">
            <h1>Hello!</h1>
            <p>What are we building today?</p>
        </div>`;
        fetchSessions();
    } catch (error) {
        console.error("Failed to create session:", error);
    }
}

async function switchSession(sessionId) {
    // 1. Intercept and Abort Logic
    if (isStreaming) {
        const confirmSwitch = confirm("V is currently responding. Switching sessions will abort the current response. Continue?");
        if (confirmSwitch) {
            if (activeEventSource) {
                activeEventSource.close(); // Cleanly kill the HTTP connection
                activeEventSource = null;
            }
            toggleInput(true); // Unlock the text box
            isStreaming = false; // Reset state
        } else {
            return; // Abort the switch and let V finish
        }
    }

    currentSessionId = sessionId;
    chatLog.innerHTML = ''; 
    fetchSessions(); 

    try {
        const res = await fetch(`/api/sessions/${sessionId}/messages`);
        if (!res.ok) throw new Error("Failed to load history");
        const data = await res.json();
        
        if (data.messages && data.messages.length > 0) {
            data.messages.forEach(msg => {
                if (msg.role === 'user') {
                    appendUserMessage(msg.content);
                } else {
                    const row = document.createElement('div');
                    row.className = 'message-row v';

                    // Parse stored logs if present, or show default history label
                    let logEntries = '';
                    if (msg.logs) {
                        try {
                            const parsedLogs = typeof msg.logs === 'string' ? JSON.parse(msg.logs) : msg.logs;
                            logEntries = parsedLogs.map(l => `<div>> ${l}</div>`).join('');
                        } catch(e) {
                            logEntries = `<div>> ${msg.logs}</div>`;
                        }
                    } else {
                        logEntries = `<div>> Process logs archived in ROM.</div>`;
                    }

                    row.innerHTML = `
                        <div class="bubble">
                            <details class="engine-logs">
                                <summary>View Process Logs</summary>
                                <div class="log-entries">${logEntries}</div>
                            </details>
                            <div class="v-text">${typeof marked !== 'undefined' ? marked.parse(msg.content) : msg.content}</div>
                        </div>
                    `;
                    chatLog.appendChild(row);
                }
            });
            chatLog.scrollTop = chatLog.scrollHeight;
        } else {
             chatLog.innerHTML = `<div class="welcome-screen" id="welcome-screen">
                <h1>Hello!</h1>
                <p>What are we building today?</p>
            </div>`;
        }
    } catch (err) {
        console.error("History Retrieval Error:", err);
    }
}

newChatBtn.addEventListener('click', createNewSession);

/* ==========================================================================
   CHAT LOGIC
   ========================================================================== */
function appendUserMessage(text) {
    const row = document.createElement('div');
    row.className = 'message-row user';
    row.innerHTML = `<div class="bubble">${text}</div>`;
    
    // Remove welcome screen if it exists
    const welcome = document.getElementById('welcome-screen');
    if (welcome) welcome.remove();

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
    details.innerHTML = `<summary>View Process Logs</summary><div class="log-entries"></div>`;
    
    const textContent = document.createElement('div');
    textContent.className = 'v-text';
    
    bubble.appendChild(details);
    bubble.appendChild(textContent);
    row.appendChild(bubble);
    chatLog.appendChild(row);
    
    currentLogsDiv = details.querySelector('.log-entries');
    currentTextDiv = textContent;
}

function toggleInput(state) {
    isStreaming = !state;
    userInput.disabled = !state;
    
    if (state) {
        // UI is unlocked: Show Send, Hide Stop
        sendBtn.style.display = 'block';
        stopBtn.style.display = 'none';
        userInput.focus();
    } else {
        // UI is locked (streaming): Hide Send, Show Stop
        sendBtn.style.display = 'none';
        stopBtn.style.display = 'block';
    }
}

async function sendQuery(message) {
    if (!message.trim()) return;
    
    // Fail-safe: Auto-create a session if the user just starts typing
    if (!currentSessionId) {
        await createNewSession();
    }
    
    appendUserMessage(message);
    userInput.value = ''; 
    setupVTurn();
    toggleInput(false); 

    const encodedMsg = encodeURIComponent(message);
    
    // Now using the dynamic DB session ID instead of the hardcoded ghost ID
    activeEventSource = new EventSource(`/stream_response?prompt=${encodedMsg}&session_id=${currentSessionId}`);
    
    activeEventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        
       if (data.type === "status") {
            currentLogsDiv.innerHTML += `<div>> ${data.content}</div>`;
        } else if (data.type === "title_update") {
            // Catch the background task signal and refresh the sidebar instantly
            fetchSessions(); 
        } else if (data.type === "token") {
            currentTextDiv.innerHTML += data.content;
        } else if (data.type === "warning") {
            currentLogsDiv.innerHTML += `<div style="color:red;">> Error: ${data.content}</div>`;
        } else if (data.type === "done") {
            // 1. Reset streaming state
            isStreaming = false;
            
            // 2. Call the CORRECT function name to reload sidebar sessions
            fetchSessions(); 

            activeEventSource.close();
            activeEventSource = null;
            if (typeof marked !== 'undefined') {
                currentTextDiv.innerHTML = marked.parse(currentTextDiv.innerHTML);
            }
            toggleInput(true); 
            fetchTasks(); 
        }
        chatLog.scrollTop = chatLog.scrollHeight;
    };

    activeEventSource.onerror = function() {
        activeEventSource.close();
        activeEventSource = null; // Clean up
        currentLogsDiv.innerHTML += `<div style="color:red;">> Connection Error.</div>`;
        toggleInput(true);
    };
}       

sendBtn.addEventListener('click', () => {
    if (userInput.value.trim() !== '') sendQuery(userInput.value);
});

stopBtn.addEventListener('click', () => {
    if (activeEventSource) {
        activeEventSource.close(); // Kill the stream connection
        activeEventSource = null;
        
        // Log the abort into the UI so the user knows it worked
        if (currentLogsDiv) {
            currentLogsDiv.innerHTML += `<div style="color:#EF4444;">> [USER OVERRIDE] Generation aborted.</div>`;
        }
        
        // Ensure markdown is parsed for whatever partial text was generated
        if (currentTextDiv && typeof marked !== 'undefined') {
            currentTextDiv.innerHTML = marked.parse(currentTextDiv.innerHTML);
        }
        
        toggleInput(true); // Unlock the UI
    }
});

userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && userInput.value.trim() !== '') sendQuery(userInput.value);
});

/* ==========================================================================
   TASK LEDGER LOGIC
   ========================================================================== */
async function fetchTasks() {
    try {
        const response = await fetch('/api/tasks/');
        if (!response.ok) throw new Error("Failed to fetch tasks");
        
        const tasks = await response.json();
        taskList.innerHTML = ''; 
        
        const activeTasks = tasks.filter(t => t.status !== 'completed' && t.status !== 'cancelled');

        if (activeTasks.length === 0) {
            taskList.innerHTML = '<div style="color: #9CA3AF; text-align: center; padding: 20px;">No active tasks.</div>';
            return;
        }

        activeTasks.forEach(task => {
            const card = document.createElement('div');
            card.className = 'task-card';
            card.innerHTML = `
                <input type="checkbox" class="task-checkbox" onchange="toggleTaskStatus(${task.id}, this.checked)">
                <div class="task-details">
                    <span class="task-title">${task.title}</span>
                    <span class="task-meta">
                        <span class="priority-${task.priority}">${task.priority}</span> | ${task.status.replace('_', ' ')}
                    </span>
                </div>
            `;
            taskList.appendChild(card);
        });
    } catch (error) {
        console.error("Task Fetch Error:", error);
        taskList.innerHTML = '<div style="color: #EF4444; text-align: center; padding: 20px;">Failed to load tasks. Check DB schema.</div>';
    }
}

async function toggleTaskStatus(taskId, isChecked) {
    const newStatus = isChecked ? 'completed' : 'pending';
    try {
        await fetch(`/api/tasks/${taskId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        fetchTasks();
    } catch (error) {
        console.error("Failed to update task:", error);
    }
}

async function createTask(title) {
    try {
        await fetch('/api/tasks/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: title, priority: "medium" })
        });
        newTaskInput.value = '';
        fetchTasks();
    } catch (error) {
        console.error("Failed to create task:", error);
    }
}

refreshBtn.addEventListener('click', fetchTasks);
addTaskBtn.addEventListener('click', () => {
    if (newTaskInput.value.trim() !== '') createTask(newTaskInput.value);
});
newTaskInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && newTaskInput.value.trim() !== '') createTask(newTaskInput.value);
});

// Initialize Security Gate
window.addEventListener('load', checkAuthStatus);