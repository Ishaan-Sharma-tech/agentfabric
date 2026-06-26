<script lang="ts">
  import { onMount, onDestroy } from "svelte";
  import { fade, fly, slide } from "svelte/transition";

  // Tab State
  let activeTab = $state("dashboard");

  // API/Server State
  let serverOnline = $state(false);
  let workspaces = $state<any[]>([]);
  let activeWorkspace = $state("default");
  let activeWorkspacePath = $state("");
  let stats = $state({
    agentsCount: 0,
    memoryCount: 0,
    eventsCount: 0,
  });

  // Agents Tab State
  let agentForm = $state({
    agent_name: "assistant",
    provider: "ollama",
    model: "llama3",
    system_prompt: "You are a helpful AI assistant.",
    task: "Explain quantum computing in one sentence.",
    temperature: 0.7,
    max_steps: 10
  });
  let runningAgent = $state(false);
  let agentResult = $state<any>(null);
  let agentLogs = $state<any[]>([]);

  // Memory Tab State
  let memories = $state<any[]>([]);
  let searchQuery = $state("");
  let newMemoryText = $state("");
  let newMemoryTags = $state("");

  // Event Log Tab State
  let events = $state<any[]>([]);
  let selectedEvent = $state<any>(null);

  // WebSockets and polling timers
  let ws: WebSocket | null = null;
  let pollInterval: any;
  let wsReconnectTimeout: any;

  // Lifecycle
  onMount(() => {
    startPolling();
    connectWebSocket();
  });

  onDestroy(() => {
    clearInterval(pollInterval);
    clearTimeout(wsReconnectTimeout);
    if (ws) ws.close();
  });

  // Polling loop to check server status & reload data
  function startPolling() {
    fetchData();
    pollInterval = setInterval(fetchData, 3000);
  }

  async function fetchData() {
    try {
      // 1. Fetch workspaces
      const res = await fetch("http://127.0.0.1:8000/workspaces");
      if (!res.ok) throw new Error("Server error");
      const data = await res.json();
      
      serverOnline = true;
      workspaces = data;

      // Find active workspace details
      const active = data.find((w: any) => w.active);
      if (active) {
        activeWorkspace = active.name;
        activeWorkspacePath = active.path;
      }

      // 2. Fetch stats & memories
      await refreshMemories();
    } catch (e) {
      serverOnline = false;
      workspaces = [];
      activeWorkspacePath = "";
    }
  }

  async function refreshMemories() {
    if (!serverOnline) return;
    try {
      const q = searchQuery ? `?query=${encodeURIComponent(searchQuery)}` : "";
      const res = await fetch(`http://127.0.0.1:8000/memory/search${q}`);
      if (res.ok) {
        memories = await res.json();
        stats.memoryCount = memories.length;
      }
    } catch (e) {
      console.error("Error loading memories:", e);
    }
  }

  // WebSocket for real-time EventBus streaming
  function connectWebSocket() {
    if (ws) {
      ws.close();
    }
    
    ws = new WebSocket("ws://127.0.0.1:8000/events");
    
    ws.onopen = () => {
      console.log("WebSocket connected to events stream");
    };

    ws.onmessage = (event) => {
      try {
        const ev = JSON.parse(event.data);
        // Prepend to events list
        events = [ev, ...events].slice(0, 100);
        stats.eventsCount = events.length;

        // If active agent is running, stream execution logs
        if (runningAgent) {
          if (ev.event_type === "ToolInvoked") {
            agentLogs = [...agentLogs, { type: "tool", text: `Invoked Tool: ${ev.actor} with inputs: ${JSON.stringify(ev.data)}` }];
          } else if (ev.event_type === "ToolResult") {
            agentLogs = [...agentLogs, { type: "tool-result", text: `Tool Returned: ${JSON.stringify(ev.data)}` }];
          } else if (ev.event_type === "AgentStopped") {
            // Keep logs updated
          }
        }
      } catch (e) {
        console.error("WebSocket parse error:", e);
      }
    };

    ws.onclose = () => {
      // Retry connection in 3 seconds
      wsReconnectTimeout = setTimeout(connectWebSocket, 3000);
    };
  }

  // API Call Handlers
  async function selectWorkspace(name: string) {
    if (!serverOnline) return;
    try {
      const res = await fetch("http://127.0.0.1:8000/workspaces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name })
      });
      if (res.ok) {
        await fetchData();
      }
    } catch (e) {
      console.error("Error switching workspace:", e);
    }
  }

  async function createWorkspace() {
    const name = prompt("Enter name for the new workspace:");
    if (!name) return;
    await selectWorkspace(name);
  }

  async function runAgentTask() {
    if (!serverOnline || runningAgent) return;
    runningAgent = true;
    agentResult = null;
    agentLogs = [{ type: "system", text: `Starting Agent execution loop... [Provider: ${agentForm.provider}]` }];
    
    try {
      const res = await fetch("http://127.0.0.1:8000/agents/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(agentForm)
      });
      
      if (!res.ok) {
        throw new Error(await res.text());
      }
      
      const data = await res.json();
      agentResult = data;
      agentLogs = [...agentLogs, { type: "system", text: "Execution complete." }];
    } catch (e: any) {
      agentLogs = [...agentLogs, { type: "error", text: `Error during run: ${e.message}` }];
    } finally {
      runningAgent = false;
    }
  }

  async function addMemory() {
    if (!serverOnline || !newMemoryText) return;
    try {
      const tagsList = newMemoryTags.split(",").map(t => t.trim()).filter(t => t);
      const res = await fetch("http://127.0.0.1:8000/memory/store", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: newMemoryText,
          tags: tagsList
        })
      });
      if (res.ok) {
        newMemoryText = "";
        newMemoryTags = "";
        await refreshMemories();
      }
    } catch (e) {
      console.error("Error creating memory:", e);
    }
  }

  function handleSearchInput() {
    refreshMemories();
  }
</script>

<div class="studio-app">
  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="brand flex align-center gap-2">
      <div class="logo-box"></div>
      <h1 class="brand-title">A G E N T O S</h1>
    </div>

    <!-- Workspace Manager -->
    <div class="workspace-section flex flex-col gap-2">
      <label for="ws-select" class="sidebar-label">WORKSPACE</label>
      <div class="flex gap-2">
        <select 
          id="ws-select" 
          value={activeWorkspace} 
          onchange={(e: any) => selectWorkspace(e.target.value)}
          disabled={!serverOnline}
          class="flex-1"
        >
          {#each workspaces as ws}
            <option value={ws.name}>{ws.name} {ws.name === activeWorkspace ? '✓' : ''}</option>
          {/each}
        </select>
        <button class="secondary px-3" onclick={createWorkspace} disabled={!serverOnline} title="Create Workspace">+</button>
      </div>
    </div>

    <!-- Navigation -->
    <nav class="nav-links flex flex-col gap-2">
      <button 
        class="nav-btn {activeTab === 'dashboard' ? 'active' : ''}" 
        onclick={() => activeTab = 'dashboard'}
      >
        DASHBOARD
      </button>
      <button 
        class="nav-btn {activeTab === 'agents' ? 'active' : ''}" 
        onclick={() => activeTab = 'agents'}
      >
        AGENTS
      </button>
      <button 
        class="nav-btn {activeTab === 'memory' ? 'active' : ''}" 
        onclick={() => activeTab = 'memory'}
      >
        MEMORY
      </button>
      <button 
        class="nav-btn {activeTab === 'events' ? 'active' : ''}" 
        onclick={() => activeTab = 'events'}
      >
        EVENT LOG
      </button>
    </nav>

    <!-- Connection Status -->
    <div class="sidebar-footer">
      <div class="status-indicator flex align-center gap-2">
        <span class="status-dot {serverOnline ? 'online animate-pulse' : 'offline'}"></span>
        <span class="status-text">{serverOnline ? 'SERVER: ONLINE' : 'SERVER: OFFLINE'}</span>
      </div>
    </div>
  </aside>

  <!-- Main View Panel -->
  <main class="content-area">
    {#if activeTab === 'dashboard'}
      <div class="tab-view animate-fade-in" in:fly={{ y: 8, duration: 250 }}>
        <h2 class="view-title">DASHBOARD</h2>
        <p class="view-subtitle">Workspace Overview & Platform Diagnostics</p>

        <!-- Stats Grid -->
        <div class="stats-grid">
          <div class="card animate-border-pulse">
            <span class="card-label">ACTIVE WORKSPACE</span>
            <span class="card-val">{activeWorkspace}</span>
          </div>
          <div class="card">
            <span class="card-label">MEMORIES STORED</span>
            <span class="card-val">{stats.memoryCount}</span>
          </div>
          <div class="card">
            <span class="card-label">EVENTS DETECTED</span>
            <span class="card-val">{stats.eventsCount}</span>
          </div>
        </div>

        <!-- Details Card -->
        <div class="panel flex flex-col gap-4 mt-6">
          <h3 class="panel-header">DIAGNOSTICS & SYSTEM META</h3>
          <div class="info-row">
            <span class="info-label">Active Database Path:</span>
            <span class="info-value font-mono">{activeWorkspacePath ? activeWorkspacePath + '/agentfabric.db' : 'N/A'}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Backend Connection Status:</span>
            <span class="info-value font-mono">{serverOnline ? 'Connected to 127.0.0.1:8000' : 'Disconnected'}</span>
          </div>
          <div class="info-row">
            <span class="info-label">Default LLM Provider:</span>
            <span class="info-value font-mono">ollama (llama3)</span>
          </div>
        </div>
      </div>

    {:else if activeTab === 'agents'}
      <div class="tab-view animate-fade-in" in:fly={{ y: 8, duration: 250 }}>
        <h2 class="view-title">AGENTS CONSOLE</h2>
        <p class="view-subtitle">Deploy, execute tasks, and inspect LLM runtime workflows</p>

        <div class="agents-layout flex gap-4">
          <!-- Control Panel -->
          <div class="panel flex flex-col gap-4 flex-1">
            <h3 class="panel-header">LAUNCH AGENT RUN</h3>
            
            <div class="form-group flex flex-col gap-2">
              <label for="agent-name">Agent Name</label>
              <input id="agent-name" type="text" bind:value={agentForm.agent_name} disabled={runningAgent} />
            </div>

            <div class="form-group flex flex-col gap-2">
              <label for="agent-provider">LLM Provider</label>
              <select id="agent-provider" bind:value={agentForm.provider} disabled={runningAgent}>
                <option value="ollama">ollama (Local)</option>
                <option value="openai">openai (Cloud)</option>
              </select>
            </div>

            <div class="form-group flex flex-col gap-2">
              <label for="agent-model">Model</label>
              <input id="agent-model" type="text" bind:value={agentForm.model} disabled={runningAgent} />
            </div>

            <div class="form-group flex flex-col gap-2">
              <label for="agent-prompt">System Prompt</label>
              <textarea id="agent-prompt" rows="3" bind:value={agentForm.system_prompt} disabled={runningAgent}></textarea>
            </div>

            <div class="form-group flex flex-col gap-2">
              <label for="agent-task">Task Input</label>
              <textarea id="agent-task" rows="3" bind:value={agentForm.task} disabled={runningAgent}></textarea>
            </div>

            <button 
              class="w-full flex justify-center align-center gap-2" 
              onclick={runAgentTask} 
              disabled={runningAgent || !serverOnline}
            >
              {#if runningAgent}
                <span class="spinner animate-spin"></span>
                EXECUTING RUN...
              {:else}
                EXECUTE AGENT RUN
              {/if}
            </button>
          </div>

          <!-- Console Output -->
          <div class="panel flex flex-col flex-1 gap-2 console-panel">
            <h3 class="panel-header">STREAMING STDOUT & SYSTEM EVENTS</h3>
            <div class="console-box flex-1 flex flex-col gap-2">
              {#each agentLogs as log}
                <div class="log-line {log.type}" transition:slide>
                  <span class="time-stamp">[{new Date().toLocaleTimeString()}]</span>
                  <span class="log-text">{log.text}</span>
                </div>
              {/each}

              {#if agentResult}
                <div class="agent-result-box mt-4 p-4 border animate-fade-in">
                  <h4 class="font-bold border-b pb-2 mb-2">FINAL AGENT RESPONSE:</h4>
                  <p class="whitespace-pre-wrap">{agentResult.text}</p>
                </div>
              {/if}
              
              {#if runningAgent}
                <div class="thinking-loader flex align-center gap-2 animate-pulse mt-2">
                  <span class="spinner animate-spin"></span>
                  <span>Agent is thinking... executing runtime step...</span>
                </div>
              {/if}
            </div>
          </div>
        </div>
      </div>

    {:else if activeTab === 'memory'}
      <div class="tab-view animate-fade-in" in:fly={{ y: 8, duration: 250 }}>
        <h2 class="view-title">MEMORY STORE</h2>
        <p class="view-subtitle">Browse, query, and inject records into the workspace FTS5 SQLite index</p>

        <!-- Search Bar -->
        <div class="search-section flex gap-2">
          <input 
            type="text" 
            placeholder="Search memories via full-text search index..." 
            bind:value={searchQuery}
            oninput={handleSearchInput}
            disabled={!serverOnline}
            class="flex-1"
          />
          <button class="secondary" onclick={refreshMemories} disabled={!serverOnline}>QUERY</button>
        </div>

        <div class="memory-layout flex gap-4 mt-6">
          <!-- Memory List -->
          <div class="panel flex-1 flex flex-col gap-4">
            <h3 class="panel-header">STORED RECORDS</h3>
            <div class="memory-grid flex flex-col gap-3">
              {#if memories.length === 0}
                <div class="empty-state">No memory records found in this workspace.</div>
              {:else}
                {#each memories as mem}
                  <div class="memory-card" transition:slide>
                    <div class="mem-header flex justify-between">
                      <span class="mem-id font-mono">ID: {mem.id.slice(0, 8)}...</span>
                      <span class="mem-score">Importance: {mem.importance_score}</span>
                    </div>
                    <p class="mem-text">{mem.text}</p>
                    {#if mem.tags && mem.tags.length > 0}
                      <div class="mem-tags flex gap-2">
                        {#each mem.tags as tag}
                          <span class="tag-pill">#{tag}</span>
                        {/each}
                      </div>
                    {/if}
                  </div>
                {/each}
              {/if}
            </div>
          </div>

          <!-- Add Memory Box -->
          <div class="panel flex flex-col gap-4 add-mem-panel">
            <h3 class="panel-header">MANUALLY WRITE MEMORY</h3>
            <div class="form-group flex flex-col gap-2">
              <label for="mem-text">Memory Content</label>
              <textarea id="mem-text" rows="5" placeholder="Inject text content..." bind:value={newMemoryText} disabled={!serverOnline}></textarea>
            </div>
            <div class="form-group flex flex-col gap-2">
              <label for="mem-tags">Tags (Comma Separated)</label>
              <input id="mem-tags" type="text" placeholder="e.g. user, preferences, calendar" bind:value={newMemoryTags} disabled={!serverOnline} />
            </div>
            <button onclick={addMemory} disabled={!serverOnline || !newMemoryText}>PERSIST RECORD</button>
          </div>
        </div>
      </div>

    {:else if activeTab === 'events'}
      <div class="tab-view animate-fade-in" in:fly={{ y: 8, duration: 250 }}>
        <h2 class="view-title">SYSTEM EVENTS</h2>
        <p class="view-subtitle">Real-time WebSocket event bus stream tracking agent execution steps</p>

        <div class="events-layout flex gap-4">
          <!-- Live Events list -->
          <div class="panel flex-1 flex flex-col gap-4">
            <h3 class="panel-header">LIVE EVENT STREAM</h3>
            <div class="events-list flex flex-col gap-2">
              {#if events.length === 0}
                <div class="empty-state">Waiting for events from active runtime...</div>
              {:else}
                {#each events as ev}
                  <button 
                    class="event-row-btn {selectedEvent && selectedEvent.id === ev.id ? 'selected' : ''}"
                    onclick={() => selectedEvent = ev}
                    transition:slide
                  >
                    <div class="flex justify-between w-full">
                      <span class="event-name font-mono">{ev.event_type}</span>
                      <span class="event-actor">{ev.actor}</span>
                    </div>
                  </button>
                {/each}
              {/if}
            </div>
          </div>

          <!-- Event Details -->
          <div class="panel flex-1 flex flex-col gap-4">
            <h3 class="panel-header">RAW EVENT METRICS</h3>
            <div class="event-details-box flex-1 flex flex-col">
              {#if selectedEvent}
                <div class="details-content flex flex-col gap-2 font-mono text-sm flex-1 overflow-auto animate-fade-in">
                  <div><strong>EVENT TYPE:</strong> {selectedEvent.event_type}</div>
                  <div><strong>ACTOR:</strong> {selectedEvent.actor}</div>
                  <div><strong>WORKSPACE:</strong> {selectedEvent.workspace}</div>
                  <div><strong>TIMESTAMP:</strong> {new Date(selectedEvent.timestamp * 1000).toLocaleString()}</div>
                  <div class="flex flex-col gap-1 mt-2">
                    <strong>DATA STRUCT:</strong>
                    <pre class="raw-json">{JSON.stringify(selectedEvent.data, null, 2)}</pre>
                  </div>
                </div>
              {:else}
                <div class="empty-state flex-1 flex align-center justify-center">Select an event to view structured payload.</div>
              {/if}
            </div>
          </div>
        </div>
      </div>
    {/if}
  </main>
</div>

<style>
  /* Local styling overrides matching high contrast B&W design */
  .brand {
    padding-bottom: 2rem;
    border-bottom: 1px solid var(--border-main);
    margin-bottom: 2rem;
  }
  
  .logo-box {
    width: 14px;
    height: 14px;
    background-color: var(--accent-white);
    border-radius: 50%;
  }

  .brand-title {
    font-size: 1rem;
    font-weight: 800;
    letter-spacing: 0.2rem;
  }

  .sidebar-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    font-weight: 700;
    letter-spacing: 0.05rem;
  }

  /* Nav buttons styling */
  .nav-links {
    margin-top: 2rem;
  }

  .nav-btn {
    text-align: left;
    background-color: transparent;
    border: 1px solid transparent;
    color: var(--text-muted);
    padding: 0.8rem 1rem;
    font-size: 0.8rem;
    font-weight: 700;
    letter-spacing: 0.1rem;
    transition: color var(--transition-fast), border-color var(--transition-fast), transform var(--transition-fast), background-color var(--transition-fast);
  }

  .nav-btn:hover {
    color: var(--text-main);
    border-color: var(--border-main);
    background-color: var(--accent-gray);
    transform: translateX(2px);
  }

  .nav-btn.active {
    color: var(--text-main);
    border-color: var(--border-active);
    background-color: var(--accent-gray);
  }

  .sidebar-footer {
    margin-top: auto;
    padding-top: 1.5rem;
    border-top: 1px solid var(--border-main);
  }

  /* Status Indicator */
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
  }
  
  .status-dot.online {
    background-color: var(--accent-white);
  }

  .status-dot.offline {
    background-color: transparent;
    border: 1px solid var(--border-main);
  }

  .status-text {
    font-size: 0.75rem;
    font-weight: 700;
    letter-spacing: 0.05rem;
    color: var(--text-muted);
  }

  /* Views common elements */
  .view-title {
    font-size: 1.8rem;
    font-weight: 800;
    letter-spacing: -0.02rem;
    margin-bottom: 0.2rem;
  }

  .view-subtitle {
    font-size: 0.9rem;
    color: var(--text-muted);
    margin-bottom: 2rem;
  }

  /* Panel container cards */
  .panel {
    background-color: var(--bg-card);
    border: 1px solid var(--border-main);
    border-radius: 6px;
    padding: 1.5rem;
    transition: border-color var(--transition-medium);
  }

  .panel:hover {
    border-color: var(--text-dim);
  }

  .panel-header {
    font-size: 0.85rem;
    font-weight: 800;
    letter-spacing: 0.05rem;
    color: var(--text-main);
    border-bottom: 1px solid var(--border-main);
    padding-bottom: 0.8rem;
    margin-bottom: 1rem;
    text-transform: uppercase;
  }

  /* Stats Grid */
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1.5rem;
  }

  .card {
    background-color: var(--bg-card);
    border: 1px solid var(--border-main);
    padding: 1.5rem;
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    transition: transform var(--transition-fast), border-color var(--transition-fast);
  }

  .card:hover {
    transform: translateY(-2px);
    border-color: var(--border-active);
  }

  .card-label {
    font-size: 0.75rem;
    color: var(--text-muted);
    font-weight: 700;
    letter-spacing: 0.05rem;
  }

  .card-val {
    font-size: 2.2rem;
    font-weight: 800;
  }

  /* Details Panel rows */
  .info-row {
    display: flex;
    justify-content: space-between;
    padding-bottom: 0.6rem;
    border-bottom: 1px solid var(--border-main);
  }

  .info-row:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }

  .info-label {
    color: var(--text-muted);
    font-size: 0.9rem;
  }

  .info-value {
    font-weight: 600;
    font-size: 0.9rem;
  }

  /* Form Elements overrides */
  .form-group label {
    font-size: 0.8rem;
    font-weight: 700;
    color: var(--text-muted);
    text-transform: uppercase;
  }

  .w-full {
    width: 100%;
  }

  /* Spinner icon */
  .spinner {
    display: inline-block;
    width: 14px;
    height: 14px;
    border: 2px solid var(--border-main);
    border-top-color: var(--accent-white);
    border-radius: 50%;
  }

  /* Console output */
  .console-panel {
    background-color: var(--bg-main) !important;
    border-color: var(--border-main);
  }

  .console-box {
    background-color: #020202;
    border: 1px solid var(--border-main);
    border-radius: 4px;
    padding: 1rem;
    font-family: var(--font-mono);
    font-size: 0.85rem;
    overflow-y: auto;
    max-height: 480px;
    color: #e0e0e0;
  }

  .log-line {
    padding: 0.2rem 0;
    border-bottom: 1px solid #080808;
    display: flex;
    gap: 0.5rem;
  }

  .log-line.system {
    color: var(--text-muted);
  }
  
  .log-line.tool {
    color: #aaaaaa;
  }

  .log-line.tool-result {
    color: #ffffff;
  }

  .log-line.error {
    color: #ffffff;
    border-left: 2px solid #ffffff;
    padding-left: 0.5rem;
  }

  .time-stamp {
    color: var(--text-dim);
  }

  .agent-result-box {
    border-color: var(--border-main);
    background-color: var(--bg-card);
  }

  /* Memory tab specifics */
  .search-section input {
    font-size: 1rem;
  }

  .memory-grid {
    overflow-y: auto;
    max-height: 520px;
    padding-right: 4px;
  }

  .memory-card {
    background-color: var(--bg-card);
    border: 1px solid var(--border-main);
    border-radius: 4px;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    transition: border-color var(--transition-fast), transform var(--transition-fast);
  }

  .memory-card:hover {
    border-color: var(--border-active);
    transform: translateX(2px);
  }

  .mem-header {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  .mem-text {
    font-size: 0.9rem;
    line-height: 1.4;
  }

  .mem-tags {
    flex-wrap: wrap;
  }

  .tag-pill {
    font-size: 0.75rem;
    font-family: var(--font-mono);
    background-color: var(--accent-gray);
    border: 1px solid var(--border-main);
    color: var(--text-muted);
    padding: 0.1rem 0.4rem;
    border-radius: 2px;
  }

  .add-mem-panel {
    width: 320px;
    height: fit-content;
  }

  /* Events Log Tab */
  .events-list {
    overflow-y: auto;
    max-height: 500px;
  }

  .event-row-btn {
    width: 100%;
    text-align: left;
    background-color: var(--bg-card);
    border: 1px solid var(--border-main);
    color: var(--text-main);
    padding: 0.8rem 1rem;
    font-size: 0.85rem;
    transition: transform var(--transition-fast), border-color var(--transition-fast), background-color var(--transition-fast);
  }

  .event-row-btn:hover {
    transform: translateX(2px);
    border-color: var(--border-active);
  }

  .event-row-btn.selected {
    border-color: var(--border-active);
    background-color: var(--accent-gray);
  }

  .event-name {
    font-weight: 700;
  }

  .event-actor {
    color: var(--text-muted);
    font-size: 0.8rem;
  }

  .event-details-box {
    background-color: #020202;
    border: 1px solid var(--border-main);
    border-radius: 4px;
    padding: 1.5rem;
  }

  .raw-json {
    background-color: #000000;
    border: 1px solid var(--border-main);
    border-radius: 2px;
    padding: 1rem;
    overflow: auto;
    max-height: 380px;
    font-size: 0.8rem;
    color: #cccccc;
  }

  .empty-state {
    color: var(--text-dim);
    font-size: 0.9rem;
    text-align: center;
    padding: 2rem;
  }
  
  .mt-6 { margin-top: 1.5rem; }
  .mt-4 { margin-top: 1rem; }
  .mb-2 { margin-bottom: 0.5rem; }
  .pb-2 { padding-bottom: 0.5rem; }
  .px-3 { padding-left: 0.75rem; padding-right: 0.75rem; }
</style>
