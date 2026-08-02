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

const toggleSidebarBtn = document.getElementById('toggle-sidebar-btn');
const mainAppContainer = document.querySelector('.app-container');
const currentChatTitle = document.getElementById('current-chat-title');

let currentSessionId = null;
let chatHistory = []; 
let currentLogsDiv = null;
let currentTextDiv = null;
let isStreaming = false;
let isSetupMode = false;
let activeEventSource = null;


toggleSidebarBtn.addEventListener('click', () => {
    mainAppContainer.classList.toggle('sidebar-collapsed');
});
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
            titleSpan.onclick = () => switchSession(session.id, session.title || "New Chat");

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

async function switchSession(sessionId, sessionTitle = "V") {    // 1. Intercept and Abort Logic
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
    currentChatTitle.innerText = sessionTitle; 

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

function showAuthModal(commandText, intentText, actionId) {
    const modal = document.getElementById('command-auth-modal');
    const commandDisplay = document.getElementById('auth-command-display');
    const intentDisplay = document.getElementById('auth-intent-display'); // Assuming you add this
    const approveBtn = document.getElementById('auth-approve-btn');
    const denyBtn = document.getElementById('auth-deny-btn');

    // Defensive check: If the modal doesn't exist, log it and abort cleanly
    if (!modal || !commandDisplay || !approveBtn || !denyBtn) {
        console.error("Critical UI elements for the Auth Modal are missing from index.html.");
        return; 
    }

    // Inject the raw command and the human intent
    commandDisplay.innerText = commandText;
    if (intentDisplay) {
        intentDisplay.innerText = intentText || "No intent provided.";
    }
    
    modal.style.display = 'flex'; // This won't crash now!

    // Clear old listeners by cloning to prevent multiple triggers
    const newApproveBtn = approveBtn.cloneNode(true);
    const newDenyBtn = denyBtn.cloneNode(true);
    approveBtn.parentNode.replaceChild(newApproveBtn, approveBtn);
    denyBtn.parentNode.replaceChild(newDenyBtn, denyBtn);

    // Wire up the new buttons
    newApproveBtn.addEventListener('click', () => submitCommandAuth(actionId, true));
    newDenyBtn.addEventListener('click', () => submitCommandAuth(actionId, false));
}

async function sendQuery(message) {
    if (!message.trim()) return;
    
    // Auto-create session if none exists
    if (!currentSessionId) {
        await createNewSession();
    }
    
    appendUserMessage(message);
    userInput.value = ''; 
    setupVTurn();
    toggleInput(false); 

    // --- SEND MESSAGE TO BACKEND ---
    const encodedMsg = encodeURIComponent(message);
    activeEventSource = new EventSource(`/stream_response?prompt=${encodedMsg}&session_id=${currentSessionId}`);
    
    // ---> THE FIX: WE ADDED THE MESSAGE LISTENER HERE <---
    activeEventSource.onmessage = function(event) {
        try {
            const msg = JSON.parse(event.data);
            
            if (msg.type === "status") {
                if (currentLogsDiv) {
                    currentLogsDiv.innerHTML += `<div>> ${msg.content}</div>`;
                }
            } else if (msg.type === "token") {
                if (currentTextDiv) {
                    currentTextDiv.innerHTML += msg.content;
                }
            } else if (msg.type === "task_update") {
                fetchTasks();
            } else if (msg.type === "title_update") {
                currentChatTitle.innerText = msg.title;
                fetchSessions(); 
            } else if (msg.type === "memory_draft") {
                // Route the data to the new Memory Bank text area
                const memoryBox = document.getElementById("learned-facts-input");
                if (memoryBox) {
                    const currentText = memoryBox.value.trim();
                    // Append as a clean bullet point
                    memoryBox.value = currentText ? `${currentText}\n- ${msg.content}` : `- ${msg.content}`;
                    if (currentLogsDiv) {
                        currentLogsDiv.innerHTML += `<div style="color:#10B981;">> [SYSTEM] New memory drafted to Memory Bank.</div>`;
                    }
                }

            } else if (msg.type === "auth_request") {
                if (currentLogsDiv) {
                    currentLogsDiv.innerHTML += `<div style="color:#F59E0B; font-weight:bold;">> [SYSTEM PAUSE] Authorization required for command execution.</div>`;
                }
                
                // Pass the command, the intent, and the action ID
                showAuthModal(msg.command, msg.intent, msg.action_id);

            } else if (msg.type === "done") {
                if (activeEventSource) {
                    activeEventSource.close();
                    activeEventSource = null;
                }
                if (currentTextDiv && typeof marked !== 'undefined') {
                    currentTextDiv.innerHTML = marked.parse(currentTextDiv.innerHTML);
                }
                toggleInput(true);
            }                           
        } catch (e) {
            console.error("Stream Parsing Error:", e);
        }
    };

    activeEventSource.addEventListener("error", function(event) {
        // 1. If there is no data payload, this is a native network drop. 
        // Let the onerror block handle it!
        if (!event.data) return; 

        let errorMessage = "System Exception triggered.";
        try {
            const data = JSON.parse(event.data);
            errorMessage = data.error || errorMessage;
        } catch(e) {}
        
        if (currentLogsDiv) {
            currentLogsDiv.innerHTML += `<div style="color:#EF4444; font-weight:bold;">> [SYSTEM HALT] ${errorMessage}</div>`;
        }
        if (currentTextDiv) {
            currentTextDiv.innerHTML += `<br><br><span style="color:#EF4444; font-weight:bold;">⚠️ ${errorMessage}</span>`;
        }

        isStreaming = false;
        if (activeEventSource) {
            activeEventSource.close();
            activeEventSource = null;
        }
        toggleInput(true); 
    });

    // The native error handler
    activeEventSource.onerror = function() {
        if (activeEventSource) {
            activeEventSource.close();
            activeEventSource = null; 
        }
        if (currentLogsDiv) {
            currentLogsDiv.innerHTML += `<div style="color:red;">> Connection Error.</div>`;
        }
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
        const activeContainer = document.getElementById('active-tasks-list');
        
        activeContainer.innerHTML = ''; 
        
        // Filter out completed tasks so the sidebar only processes active ones
        const activeTasks = tasks.filter(task => task.status !== 'completed');
        
        if (activeTasks.length === 0) {
            activeContainer.innerHTML = '<div style="color: #9CA3AF; text-align: center; padding: 20px;">No pending tasks.</div>';
            return;
        }

        activeTasks.forEach(task => {
            const card = document.createElement('div');
            card.className = 'task-card';
            // THE FIX: Added flex-style layout and the delete button
            card.innerHTML = `
                <input type="checkbox" class="task-checkbox" onchange="toggleTaskStatus(${task.id}, this.checked)">
                <div class="task-details">
                    <span class="task-title">${task.title}</span>
                    <span class="task-meta">
                        <span class="priority-${task.priority}">${task.priority}</span> | ${task.status.replace('_', ' ')}
                    </span>
                </div>
                <button onclick="deleteTaskUI(${task.id})" style="background: none; border: none; color: #EF4444; cursor: pointer; font-size: 1.2rem; margin-left: auto; padding: 0 5px;" title="Delete Task">×</button>
            `;
            
            activeContainer.appendChild(card);
        });
        
    } catch (error) {
        console.error("Task Fetch Error:", error);
        document.getElementById('active-tasks-list').innerHTML = '<div style="color: #EF4444; text-align: center; padding: 20px;">Failed to load tasks.</div>';
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


// --- VIEW ROUTING LOGIC ---
const settingsView = document.getElementById('settings-view');
const mainAppView = document.getElementById('app-container');
const contextInput = document.getElementById('user-context-input');

// Open Settings
document.getElementById('settings-btn').addEventListener('click', async () => {
    mainAppView.style.display = 'none';
    settingsView.style.display = 'block';
    
    // Fetch context directly from the ROM Database
    try {
        const res = await fetch('/api/settings/context');
        const data = await res.json();
        contextInput.value = data.context || '';
    } catch (e) {
        console.error("Failed to load context:", e);
    }
});

// Close Settings
document.getElementById('close-settings-btn').addEventListener('click', () => {
    settingsView.style.display = 'none';
    mainAppView.style.display = 'grid'; // Restore the 3-column grid
});

// Save Context
document.getElementById('save-settings-btn').addEventListener('click', async () => {
    const btn = document.getElementById('save-settings-btn');
    const originalText = btn.innerText;
    btn.innerText = 'Saving...';
    
    try {
        await fetch('/api/settings/context', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ context: contextInput.value })
        });
        
        // Visual success feedback
        btn.innerText = '✓ Saved';
        btn.style.backgroundColor = '#10B981';
    } catch (e) {
        console.error("Failed to save context:", e);
        btn.innerText = 'X Error';
        btn.style.backgroundColor = '#EF4444';
    }
    
    setTimeout(() => {
        btn.innerText = originalText;
        btn.style.backgroundColor = ''; // Reverts to CSS default
    }, 1500);
});

// Safe Shutdown
document.getElementById('exit-btn').addEventListener('click', () => {
    if (confirm("Are you sure you want to trigger a system shutdown?")) {
        fetch('/api/shutdown', { method: 'POST' }).catch(e => console.log("Server offline."));
        document.body.innerHTML = `
            <div style="height: 100vh; display: flex; align-items: center; justify-content: center; background: #f3f4f6;">
                <h1 style="color: #374151; font-family: sans-serif;">V Engine Terminated. Safe to close tab.</h1>
            </div>`;
    }
});

// --- TASK ARCHIVE LOGIC ---
const viewArchiveBtn = document.getElementById('view-archive-btn');
const archiveContainer = document.getElementById('archive-list-container');

async function loadArchive() {
    viewArchiveBtn.innerText = 'Loading...';
    try {
        // Fetch strictly completed tasks
        const response = await fetch('/api/tasks/?status=completed');
        if (!response.ok) throw new Error("Failed to fetch archive");
        
        const tasks = await response.json();
        archiveContainer.innerHTML = '';

        if (tasks.length === 0) {
            archiveContainer.innerHTML = '<div style="color: #9CA3AF; text-align: center; padding: 10px;">No completed tasks found.</div>';
        } else {
            tasks.forEach(task => {
                const card = document.createElement('div');
                card.className = 'task-card';
                card.style.opacity = '0.7'; // Dimmed for archive
                
                card.innerHTML = `
                    <input type="checkbox" class="task-checkbox" checked onchange="restoreTask(${task.id}, this.checked)">
                    <div class="task-details" style="text-decoration: line-through;">
                        <span class="task-title">${task.title}</span>
                        <span class="task-meta">
                            <span class="priority-${task.priority}">${task.priority}</span> | ARCHIVED
                        </span>
                    </div>
                    <!-- THE FIX: Injected the exact same delete button for the archive -->
                    <button onclick="deleteTaskUI(${task.id})" style="background: none; border: none; color: #EF4444; cursor: pointer; font-size: 1.2rem; margin-left: auto; padding: 0 5px;" title="Delete Task">×</button>
                `;
                archiveContainer.appendChild(card);
            });
        }
        
        archiveContainer.style.display = 'flex';
        viewArchiveBtn.innerText = 'Hide Archive';
        viewArchiveBtn.classList.replace('btn-primary', 'btn-secondary');

    } catch (error) {
        console.error("Archive Fetch Error:", error);
        archiveContainer.innerHTML = '<div style="color: #EF4444; text-align: center;">Failed to load archive.</div>';
        archiveContainer.style.display = 'flex';
        viewArchiveBtn.innerText = 'Hide Archive';
    }
}

// Toggle Archive Visibility
viewArchiveBtn.addEventListener('click', () => {
    if (archiveContainer.style.display === 'flex') {
        archiveContainer.style.display = 'none';
        viewArchiveBtn.innerText = 'Load Archive';
        viewArchiveBtn.classList.replace('btn-secondary', 'btn-primary');
    } else {
        loadArchive();
    }
});

// Restore Task to Pending
async function restoreTask(taskId, isChecked) {
    // If user unchecks the box, status becomes 'pending'
    const newStatus = isChecked ? 'completed' : 'pending';
    try {
        await fetch(`/api/tasks/${taskId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        
        // Refresh both the main sidebar and the archive view to keep states synced
        fetchTasks(); 
        loadArchive();
    } catch (error) {
        console.error("Failed to restore task:", error);
    }
}

async function submitCommandAuth(actionId, isApproved) {
    // Hide the modal
    document.getElementById('command-auth-modal').style.display = 'none';
    
    if (!isApproved) {
        if (currentLogsDiv) {
            currentLogsDiv.innerHTML += `<div style="color:#EF4444;">> [USER OVERRIDE] Command execution denied.</div>`;
        }
        toggleInput(true);
        return;
    }

    if (currentLogsDiv) {
        currentLogsDiv.innerHTML += `<div style="color:#10B981;">> [SYSTEM] Command authorized. Resuming execution...</div>`;
    }

    // Send approval to backend
    await fetch('/api/authorize_command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action_id: actionId, approved: true })
    });
}