const chatLog = document.getElementById('chat-log');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const globalStatus = document.getElementById('global-status');

// Task Ledger DOM Elements
const taskList = document.getElementById('task-list');
const refreshBtn = document.getElementById('refresh-tasks-btn');
const newTaskInput = document.getElementById('new-task-input');
const addTaskBtn = document.getElementById('add-task-btn');

let chatHistory = []; 
let currentLogsDiv = null;
let currentTextDiv = null;
let currentVMessageText = "";
let isStreaming = false;

/* ==========================================================================
   CHAT LOGIC
   ========================================================================== */

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

function toggleInput(state) {
    isStreaming = !state;
    userInput.disabled = !state;
    sendBtn.disabled = !state;
    if (state) userInput.focus();
}

function sendQuery(message) {
    if (!message.trim()) return;
    
    // 1. Create the User's message bubble using your existing helper
    appendUserMessage(message);
    userInput.value = ''; // Clear input
    
    // 2. Setup V's message UI and lock the input field
    setupVTurn();
    toggleInput(false); // Disables input while V is "typing"

    // 3. Connect to the Backend Stream
    const encodedMsg = encodeURIComponent(message);
    const sessionId = "desktop_client_1";
    const eventSource = new EventSource(`/stream_response?prompt=${encodedMsg}&session_id=${sessionId}`);

    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        
        // Map the backend stream payload to your existing HTML nodes
        if (data.type === "status") {
            currentLogsDiv.innerHTML += `<div>> ${data.content}</div>`;
        } else if (data.type === "token") {
            currentTextDiv.innerHTML += data.content;
        } else if (data.type === "warning") {
            currentLogsDiv.innerHTML += `<div style="color:red;">> Error: ${data.content}</div>`;
        } else if (data.type === "done") {
            eventSource.close();
            
            // Optional: Parse Markdown if V outputs lists or bold text
            if (typeof marked !== 'undefined') {
                currentTextDiv.innerHTML = marked.parse(currentTextDiv.innerHTML);
            }
            
            toggleInput(true); // Re-enable input
            fetchTasks(); // Refresh tasks after stream completes
        }
        
        chatLog.scrollTop = chatLog.scrollHeight;
    };

    eventSource.onerror = function() {
        eventSource.close();
        currentLogsDiv.innerHTML += `<div style="color:red;">> Connection Error.</div>`;
        toggleInput(true);
        fetchTasks();
    };
}

sendBtn.addEventListener('click', () => {
    if (userInput.value.trim() !== '') sendQuery(userInput.value);
});

userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && userInput.value.trim() !== '') sendQuery(userInput.value);
});


/* ==========================================================================
   TASK LEDGER LOGIC (Direct REST to Backend)
   ========================================================================== */

// 1. Fetch tasks from the database and render them
async function fetchTasks() {
    try {
        const response = await fetch('/api/tasks/');
        const tasks = await response.json();
        
        taskList.innerHTML = ''; // Clear UI
        
        // Filter out completed and cancelled tasks before rendering
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
        console.error("Failed to fetch tasks:", error);
    }
}

// 2. Toggle task status (User UI interaction)
async function toggleTaskStatus(taskId, isChecked) {
    const newStatus = isChecked ? 'completed' : 'pending';
    try {
        await fetch(`/api/tasks/${taskId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        fetchTasks(); // Reload visual state
    } catch (error) {
        console.error("Failed to update task:", error);
    }
}

// 3. Create a new task (User UI interaction)
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

// Event Listeners for the Task Widget
refreshBtn.addEventListener('click', fetchTasks);
addTaskBtn.addEventListener('click', () => {
    if (newTaskInput.value.trim() !== '') createTask(newTaskInput.value);
});
newTaskInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && newTaskInput.value.trim() !== '') createTask(newTaskInput.value);
});

// Initial load
window.addEventListener('load', fetchTasks);