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
  let expandedMemories = $state<Record<string, boolean>>({});

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
    agentLogs = [{ type: "system", text: `Starting execution loop... [Provider: ${agentForm.provider}]` }];
    
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
      agentLogs = [...agentLogs, { type: "system", text: "Execution completed successfully." }];
    } catch (e: any) {
      agentLogs = [...agentLogs, { type: "error", text: `Execution failed: ${e.message}` }];
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

  function clearLogs() {
    agentLogs = [];
    agentResult = null;
  }

  function toggleMemory(id: string) {
    expandedMemories[id] = !expandedMemories[id];
  }

  function copyEventPayload(payload: any) {
    navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
  }
</script>

<div class="studio-app">
  <!-- Sidebar Navigation -->
  <aside class="sidebar">
    <div class="brand">
      <div class="brand-header flex align-center gap-2">
        <div class="logo-box">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <rect x="1" y="1" width="10" height="10" stroke="#ffffff" stroke-width="1.5"/>
            <rect x="4" y="4" width="4" height="4" fill="#ffffff"/>
          </svg>
        </div>
        <h1 class="brand-title">FABRIC</h1>
      </div>
      <div class="brand-subtitle">STUDIO ENGINE v1.0</div>
    </div>

    <!-- Navigation Links -->
    <nav class="nav-links flex flex-col">
      <button 
        class="nav-btn {activeTab === 'dashboard' ? 'active' : ''}" 
        onclick={() => activeTab = 'dashboard'}
      >
        <span class="nav-marker">▪</span>
        DASHBOARD
      </button>
      <button 
        class="nav-btn {activeTab === 'agents' ? 'active' : ''}" 
        onclick={() => activeTab = 'agents'}
      >
        <span class="nav-marker">▪</span>
        AGENTS CONSOLE
        {#if runningAgent}
          <span class="active-pulse-dot animate-pulse"></span>
        {/if}
      </button>
      <button 
        class="nav-btn {activeTab === 'memory' ? 'active' : ''}" 
        onclick={() => activeTab = 'memory'}
      >
        <span class="nav-marker">▪</span>
        MEMORY STORE
        <span class="nav-badge">{stats.memoryCount}</span>
      </button>
      <button 
        class="nav-btn {activeTab === 'events' ? 'active' : ''}" 
        onclick={() => activeTab = 'events'}
      >
        <span class="nav-marker">▪</span>
        EVENT LOG
        <span class="nav-badge">{stats.eventsCount}</span>
      </button>
    </nav>

    <!-- Sidebar Footer Info -->
    <div class="sidebar-footer">
      <div class="info-block">
        <div class="info-title">VERSION</div>
        <div class="info-val font-mono">0.1.0-alpha</div>
      </div>
    </div>
  </aside>

  <!-- Workspace Wrapper -->
  <div class="workspace-container">
    <!-- Top Bar -->
    <header class="topbar">
      <div class="topbar-left flex align-center gap-4">
        <div class="ws-dropdown-container flex align-center gap-2">
          <span class="topbar-label">WORKSPACE:</span>
          <select 
            id="ws-select" 
            value={activeWorkspace} 
            onchange={(e: any) => selectWorkspace(e.target.value)}
            disabled={!serverOnline}
            class="topbar-select font-mono"
          >
            {#each workspaces as ws}
              <option value={ws.name}>{ws.name}</option>
            {/each}
          </select>
          <button class="topbar-add-btn" onclick={createWorkspace} disabled={!serverOnline} title="Create Workspace">+</button>
        </div>
      </div>

      <div class="topbar-right">
        <div class="status-indicator flex align-center gap-2">
          <span class="status-dot {serverOnline ? 'online animate-pulse' : 'offline'}"></span>
          <span class="status-text font-mono">{serverOnline ? 'SYS: ONLINE' : 'SYS: OFFLINE'}</span>
        </div>
      </div>
    </header>

    <!-- Main View Panel -->
    <main class="content-area">
      {#if activeTab === 'dashboard'}
        <div class="tab-view animate-fade-in" in:fly={{ x: 8, duration: 250 }}>
          <div class="header-section">
            <h2 class="view-title">DASHBOARD</h2>
            <p class="view-subtitle font-mono">System Topology & Workspace Overview</p>
          </div>

          <!-- Stats Grid -->
          <div class="stats-grid-minimal">
            <div class="stat-box-minimal">
              <span class="label">ACTIVE WORKSPACE</span>
              <span class="value">{activeWorkspace}</span>
            </div>
            <div class="stat-box-minimal">
              <span class="label">MEMORIES PERSISTED</span>
              <span class="value">{stats.memoryCount}</span>
            </div>
            <div class="stat-box-minimal">
              <span class="label">EVENTS DISPATCHED</span>
              <span class="value">{stats.eventsCount}</span>
            </div>
          </div>

          <!-- Animated Topology Section -->
          <div class="topology-wrapper mt-6">
            <div class="topology-header">
              <span class="diag-title">WORKSPACE DATA-FLOW ARCHITECTURE</span>
              <span class="diag-live flex align-center gap-1 font-mono"><span class="live-dot animate-pulse"></span> LIVE TOPOLOGY</span>
            </div>
            
            <div class="topology-canvas">
              <svg class="topology-svg" viewBox="0 0 600 220" fill="none">
                <defs>
                  <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
                    <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#090909" stroke-width="1"/>
                  </pattern>
                </defs>
                <rect width="100%" height="100%" fill="url(#grid)" />

                <!-- Connections -->
                <path d="M 80 110 H 220" stroke="#121212" stroke-width="1" />
                <path d="M 80 110 H 220" stroke="#ffffff" stroke-width="1" class="march-line" />

                <path d="M 300 110 H 440" stroke="#121212" stroke-width="1" />
                <path d="M 300 110 H 440" stroke="#ffffff" stroke-width="1" class="march-line" />

                <path d="M 260 70 V 45 H 440" stroke="#121212" stroke-width="1" />
                <path d="M 260 70 V 45 H 440" stroke="#ffffff" stroke-width="1" class="march-line" />

                <path d="M 260 150 V 175 H 440" stroke="#121212" stroke-width="1" />
                <path d="M 260 150 V 175 H 440" stroke="#ffffff" stroke-width="1" class="march-line" />

                <!-- Nodes -->
                <!-- 1. Workspace Context -->
                <g transform="translate(10, 90)">
                  <rect x="0" y="0" width="70" height="40" fill="#000000" stroke="#1a1a1a" stroke-width="1" />
                  <text x="35" y="24" fill="#666666" font-size="8" font-family="var(--font-title)" letter-spacing="0.08rem" text-anchor="middle">WORKSPACE</text>
                </g>

                <!-- 2. Agent Runtime -->
                <g transform="translate(220, 70)">
                  <rect x="0" y="0" width="80" height="80" fill="#000000" stroke="#ffffff" stroke-width="1" />
                  <text x="40" y="42" fill="#ffffff" font-size="10" font-family="var(--font-title)" letter-spacing="0.12rem" text-anchor="middle" font-weight="bold">AGENT</text>
                  <text x="40" y="54" fill="#666666" font-size="8" font-family="var(--font-mono)" text-anchor="middle">RUNTIME</text>
                </g>

                <!-- 3. Tool Registry -->
                <g transform="translate(440, 90)">
                  <rect x="0" y="0" width="100" height="40" fill="#000000" stroke="#1a1a1a" stroke-width="1" />
                  <text x="50" y="24" fill="#666666" font-size="8" font-family="var(--font-title)" letter-spacing="0.08rem" text-anchor="middle">TOOL REGISTRY</text>
                </g>

                <!-- 4. Memory Store -->
                <g transform="translate(440, 25)">
                  <rect x="0" y="0" width="100" height="40" fill="#000000" stroke="#1a1a1a" stroke-width="1" />
                  <text x="50" y="24" fill="#666666" font-size="8" font-family="var(--font-title)" letter-spacing="0.08rem" text-anchor="middle">MEMORY STORE</text>
                </g>

                <!-- 5. Event Bus -->
                <g transform="translate(440, 155)">
                  <rect x="0" y="0" width="100" height="40" fill="#000000" stroke="#1a1a1a" stroke-width="1" />
                  <text x="50" y="24" fill="#666666" font-size="8" font-family="var(--font-title)" letter-spacing="0.08rem" text-anchor="middle">EVENT BUS</text>
                </g>
              </svg>
            </div>
          </div>

          <!-- Metadata table -->
          <div class="system-meta-panel mt-6">
            <h3 class="panel-header-minimal">DIAGNOSTICS & SYSTEM META</h3>
            <div class="meta-rows">
              <div class="meta-row">
                <span class="lbl font-mono">DB PATH</span>
                <span class="val font-mono">{activeWorkspacePath ? activeWorkspacePath + '\\agentfabric.db' : 'N/A'}</span>
              </div>
              <div class="meta-row">
                <span class="lbl font-mono">CONNECTION</span>
                <span class="val font-mono text-white">{serverOnline ? 'CONNECTED TO 127.0.0.1:8000' : 'DISCONNECTED'}</span>
              </div>
              <div class="meta-row">
                <span class="lbl font-mono">PROVIDER</span>
                <span class="val font-mono">ollama (llama3)</span>
              </div>
            </div>
          </div>
        </div>

      {:else if activeTab === 'agents'}
        <div class="tab-view animate-fade-in" in:fly={{ x: 8, duration: 250 }}>
          <div class="header-section">
            <h2 class="view-title">AGENTS CONSOLE</h2>
            <p class="view-subtitle">Deploy, execute tasks, and inspect LLM runtime workflows</p>
          </div>

          <div class="agents-console-split flex gap-6">
            <!-- Left Side Config Drawer -->
            <div class="config-drawer flex flex-col gap-4">
              <h3 class="drawer-title">RUNTIME CONFIG</h3>

              <div class="form-group flex flex-col gap-1">
                <label for="agent-name">Agent Name</label>
                <input id="agent-name" type="text" bind:value={agentForm.agent_name} disabled={runningAgent} />
              </div>

              <div class="form-group flex flex-col gap-1">
                <label for="agent-provider">LLM Provider</label>
                <select id="agent-provider" bind:value={agentForm.provider} disabled={runningAgent}>
                  <option value="ollama">ollama (Local)</option>
                  <option value="openai">openai (Cloud)</option>
                </select>
              </div>

              <div class="form-group flex flex-col gap-1">
                <label for="agent-model">Model</label>
                <input id="agent-model" type="text" bind:value={agentForm.model} disabled={runningAgent} />
              </div>

              <div class="form-group flex flex-col gap-1">
                <label for="agent-prompt">System Prompt</label>
                <textarea id="agent-prompt" rows="3" bind:value={agentForm.system_prompt} disabled={runningAgent}></textarea>
              </div>

              <div class="form-group flex flex-col gap-1">
                <label for="agent-task">Task Input</label>
                <textarea id="agent-task" rows="3" bind:value={agentForm.task} disabled={runningAgent}></textarea>
              </div>

              <button 
                class="w-full mt-4" 
                onclick={runAgentTask} 
                disabled={runningAgent || !serverOnline}
              >
                {#if runningAgent}
                  <span class="btn-spinner animate-spin"></span>
                  RUNNING...
                {:else}
                  DEPLOY & RUN
                {/if}
              </button>
            </div>

            <!-- Right Side Console logs -->
            <div class="logs-pane flex-1 flex flex-col">
              <div class="logs-pane-header flex justify-between align-center">
                <span class="title flex align-center gap-2">
                  <span class="active-dot {runningAgent ? 'active animate-pulse' : ''}"></span>
                  STDOUT LOGGER
                </span>
                <button class="secondary btn-xs-custom" onclick={clearLogs} disabled={runningAgent}>CLEAR</button>
              </div>

              <div class="console-wrapper flex-1 flex flex-col">
                <div class="console-log-box flex-1">
                  {#if agentLogs.length === 0}
                    <div class="console-empty font-mono">CONSOLE READY. DEPLOY AGENT TO VIEW ACTIVE STDOUT LOGS.</div>
                  {:else}
                    {#each agentLogs as log}
                      <div class="log-entry {log.type}" transition:slide>
                        <span class="log-marker">
                          {#if log.type === 'system'}
                            [SYS]
                          {:else if log.type === 'tool'}
                            [TOOL]
                          {:else if log.type === 'tool-result'}
                            [RET]
                          {:else if log.type === 'error'}
                            [ERR]
                          {/if}
                        </span>
                        <span class="log-text font-mono">{log.text}</span>
                      </div>
                    {/each}
                  {/if}

                  {#if agentResult}
                    <div class="final-result-card animate-fade-in mt-4">
                      <div class="card-header font-mono">FINAL RESPONSE</div>
                      <pre class="card-content font-mono">{agentResult.text}</pre>
                    </div>
                  {/if}
                  
                  {#if runningAgent}
                    <div class="console-cursor flex align-center gap-2 mt-2 font-mono text-xs">
                      <span class="spinner-line animate-spin"></span>
                      <span>AGENT EVALUATING RESPONSE LOOP</span>
                      <span class="cursor-blink">█</span>
                    </div>
                  {/if}
                </div>
              </div>
            </div>
          </div>
        </div>

      {:else if activeTab === 'memory'}
        <div class="tab-view animate-fade-in" in:fly={{ x: 8, duration: 250 }}>
          <div class="header-section">
            <h2 class="view-title">MEMORY STORE</h2>
            <p class="view-subtitle font-mono">SQLite FTS5 Full-Text Index & Entity Graph</p>
          </div>

          <!-- Search layout -->
          <div class="memory-search-wrapper flex gap-2">
            <input 
              type="text" 
              placeholder="Query memory records (FTS5 match syntax supported)..." 
              bind:value={searchQuery}
              oninput={handleSearchInput}
              disabled={!serverOnline}
              class="flex-1 font-mono search-input"
            />
            <button class="secondary search-btn" onclick={refreshMemories} disabled={!serverOnline}>QUERY</button>
          </div>

          <!-- Content split -->
          <div class="memory-grid-split flex gap-6 mt-6">
            <!-- Left Pane list -->
            <div class="memory-records-list flex-1 flex flex-col">
              <h3 class="list-title">PERSISTED MEMORIES</h3>

              <div class="records-container flex-1">
                {#if memories.length === 0}
                  <div class="records-empty">No persisted memories matched search filters in this workspace.</div>
                {:else}
                  {#each memories as mem}
                    <!-- svelte-ignore a11y_click_events_have_key_events -->
                    <!-- svelte-ignore a11y_no_static_element_interactions -->
                    <div class="mem-card-minimal" onclick={() => toggleMemory(mem.id)}>
                      <div class="card-hdr flex justify-between font-mono">
                        <span class="card-id">ID: {mem.id.slice(0, 8)}...</span>
                        <span class="card-score">SCORE: {mem.importance_score}</span>
                      </div>
                      <p class="card-txt">{mem.text}</p>
                      
                      {#if expandedMemories[mem.id] || (mem.tags && mem.tags.length > 0)}
                        <div class="card-footer-tags flex gap-2 mt-2" transition:slide>
                          {#each mem.tags as tag}
                            <span class="tag-badge">#{tag}</span>
                          {/each}
                          {#if mem.created_at}
                            <span class="card-timestamp font-mono">ADDED: {new Date(mem.created_at * 1000).toLocaleDateString()}</span>
                          {/if}
                        </div>
                      {/if}
                    </div>
                  {/each}
                {/if}
              </div>
            </div>

            <!-- Right Pane add -->
            <div class="memory-persist-drawer flex flex-col gap-4">
              <h3 class="drawer-title">INJECT MEMORY</h3>
              
              <div class="form-group flex flex-col gap-1">
                <label for="mem-text">Record Content</label>
                <textarea id="mem-text" rows="6" placeholder="Type text payload here..." bind:value={newMemoryText} disabled={!serverOnline}></textarea>
              </div>

              <div class="form-group flex flex-col gap-1">
                <label for="mem-tags">Tags (Comma Separated)</label>
                <input id="mem-tags" type="text" placeholder="user, preferences, context" bind:value={newMemoryTags} disabled={!serverOnline} />
              </div>

              <button onclick={addMemory} disabled={!serverOnline || !newMemoryText} class="w-full mt-4">PERSIST TO DB</button>
            </div>
          </div>
        </div>

      {:else if activeTab === 'events'}
        <div class="tab-view animate-fade-in" in:fly={{ x: 8, duration: 250 }}>
          <div class="header-section">
            <h2 class="view-title">EVENT LOG</h2>
            <p class="view-subtitle font-mono">Active EventBus Streaming logs & metrics</p>
          </div>

          <div class="events-log-split flex gap-6">
            <!-- Left Pane stream -->
            <div class="events-stream-list flex-1 flex flex-col">
              <h3 class="list-title">REAL-TIME EVENTS TIMELINE</h3>
              
              <div class="stream-container flex-1">
                {#if events.length === 0}
                  <div class="stream-empty font-mono">WAITING FOR EVENT EMISSIONS ON WS STREAM...</div>
                {:else}
                  {#each events as ev}
                    <button 
                      class="event-log-row {selectedEvent && selectedEvent.id === ev.id ? 'selected' : ''}"
                      onclick={() => selectedEvent = ev}
                      transition:slide
                    >
                      <span class="dot-bullet"></span>
                      <span class="ev-name font-mono">{ev.event_type}</span>
                      <span class="ev-actor font-mono">{ev.actor}</span>
                    </button>
                  {/each}
                {/if}
              </div>
            </div>

            <!-- Right Pane inspector -->
            <div class="events-inspector flex-1 flex flex-col">
              <h3 class="list-title">PAYLOAD METRICS INSPECTOR</h3>
              
              <div class="inspector-card flex-1 flex flex-col">
                {#if selectedEvent}
                  <div class="inspector-content flex flex-col gap-3 font-mono text-xs flex-1 animate-fade-in">
                    <div class="meta-row-clean">
                      <span class="k">EVENT TYPE</span>
                      <span class="v text-white">{selectedEvent.event_type}</span>
                    </div>
                    <div class="meta-row-clean">
                      <span class="k">ACTOR SOURCE</span>
                      <span class="v text-white">{selectedEvent.actor}</span>
                    </div>
                    <div class="meta-row-clean">
                      <span class="k">WORKSPACE</span>
                      <span class="v">{selectedEvent.workspace}</span>
                    </div>
                    <div class="meta-row-clean">
                      <span class="k">TIMESTAMP</span>
                      <span class="v">{new Date(selectedEvent.timestamp * 1000).toLocaleTimeString()}</span>
                    </div>

                    <div class="payload-box flex flex-col gap-2 flex-1 mt-4">
                      <div class="payload-hdr flex justify-between align-center">
                        <span>PAYLOAD STATE</span>
                        <button class="secondary btn-xs-clean" onclick={() => copyEventPayload(selectedEvent.data)}>COPY</button>
                      </div>
                      <pre class="payload-pre flex-1">{JSON.stringify(selectedEvent.data, null, 2)}</pre>
                    </div>
                  </div>
                {:else}
                  <div class="inspector-empty font-mono">SELECT AN ACTIVE EVENT FROM THE STREAM LIST TO ANALYZE PAYLOAD METRICS.</div>
                {/if}
              </div>
            </div>
          </div>
        </div>
      {/if}
    </main>
  </div>
</div>

<style>
  /* Sidebar branding definitions */
  .brand {
    border-bottom: 1px solid var(--border-main);
    padding-bottom: 1.5rem;
    margin-bottom: 2rem;
  }
  .brand-header {
    height: 24px;
  }
  .logo-box {
    width: 14px;
    height: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .brand-title {
    font-family: var(--font-title);
    font-size: 0.85rem;
    letter-spacing: 0.25rem;
    font-weight: 800;
    color: var(--text-main);
  }
  .brand-subtitle {
    font-family: var(--font-mono);
    font-size: 0.55rem;
    color: var(--text-dim);
    letter-spacing: 0.05rem;
    margin-top: 0.35rem;
  }

  /* Nav Links styling */
  .nav-links {
    gap: 0.2rem;
  }
  .nav-btn {
    text-align: left;
    background: transparent;
    border: none;
    color: var(--text-muted);
    font-family: var(--font-title);
    font-weight: 600;
    font-size: 0.75rem;
    letter-spacing: 0.08rem;
    padding: 0.65rem 0.5rem;
    cursor: pointer;
    display: flex;
    align-items: center;
    border-radius: 0;
    transition: var(--transition-fast);
    position: relative;
  }
  .nav-marker {
    font-size: 0.5rem;
    color: transparent;
    margin-right: 0.5rem;
    transition: var(--transition-fast);
  }
  .nav-btn:hover {
    color: var(--text-main);
    background-color: var(--accent-gray);
  }
  .nav-btn:hover .nav-marker {
    color: var(--text-muted);
  }
  .nav-btn.active {
    color: var(--text-main);
    background-color: var(--accent-gray);
  }
  .nav-btn.active .nav-marker {
    color: var(--text-main);
  }
  .active-pulse-dot {
    width: 4px;
    height: 4px;
    border-radius: 50%;
    background-color: #ffffff;
    position: absolute;
    right: 0.8rem;
  }
  .nav-badge {
    font-family: var(--font-mono);
    font-size: 0.6rem;
    color: var(--text-dim);
    margin-left: auto;
    border: 1px solid var(--border-main);
    padding: 0.05rem 0.3rem;
    border-radius: 2px;
  }

  /* Sidebar footer layout */
  .sidebar-footer {
    margin-top: auto;
    border-top: 1px solid var(--border-main);
    padding-top: 1.2rem;
  }
  .info-block {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }
  .info-title {
    font-family: var(--font-title);
    font-size: 0.55rem;
    font-weight: 700;
    color: var(--text-dim);
    letter-spacing: 0.05rem;
  }
  .info-val {
    font-size: 0.7rem;
    color: var(--text-muted);
  }

  /* Top bar elements styling */
  .topbar-label {
    font-family: var(--font-title);
    font-size: 0.7rem;
    font-weight: 700;
    color: var(--text-muted);
    letter-spacing: 0.05rem;
  }
  .topbar-select {
    border: none;
    border-bottom: 1px solid transparent;
    padding: 0.2rem 0.5rem;
    font-size: 0.75rem;
    font-weight: 700;
    cursor: pointer;
    width: auto;
    min-width: 90px;
    background-color: transparent;
    transition: var(--transition-fast);
  }
  .topbar-select:focus {
    border-bottom-color: var(--border-active);
  }
  .topbar-add-btn {
    padding: 0.2rem 0.5rem;
    font-size: 0.75rem;
    border: 1px solid var(--border-main);
    background-color: transparent;
    color: var(--text-muted);
    border-radius: 2px;
    cursor: pointer;
    transition: var(--transition-fast);
  }
  .topbar-add-btn:hover {
    color: var(--text-main);
    border-color: var(--border-active);
    letter-spacing: 0.08rem;
  }

  .status-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
  }
  .status-dot.online {
    background-color: #ffffff;
  }
  .status-dot.offline {
    background-color: transparent;
    border: 1px solid var(--border-main);
  }
  .status-text {
    font-size: 0.65rem;
    font-weight: 700;
    color: var(--text-muted);
    letter-spacing: 0.05rem;
  }

  /* Core Content titles */
  .header-section {
    margin-bottom: 2rem;
  }
  .view-title {
    font-family: var(--font-title);
    font-size: 1.2rem;
    font-weight: 800;
    letter-spacing: 0.05rem;
  }
  .view-subtitle {
    font-size: 0.75rem;
    color: var(--text-muted);
    margin-top: 0.2rem;
  }

  /* Stats grid dashboard */
  .stats-grid-minimal {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0;
    border: 1px solid var(--border-main);
  }
  .stat-box-minimal {
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    border-right: 1px solid var(--border-main);
  }
  .stat-box-minimal:last-child {
    border-right: none;
  }
  .stat-box-minimal .label {
    font-family: var(--font-title);
    font-size: 0.6rem;
    font-weight: 700;
    color: var(--text-muted);
    letter-spacing: 0.08rem;
  }
  .stat-box-minimal .value {
    font-family: var(--font-title);
    font-size: 1.5rem;
    font-weight: 800;
    color: var(--text-main);
  }

  /* Topology drawing section */
  .topology-wrapper {
    border: 1px solid var(--border-main);
    background-color: var(--bg-card);
  }
  .topology-header {
    border-bottom: 1px solid var(--border-main);
    padding: 0.8rem 1.2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .diag-title {
    font-family: var(--font-title);
    font-size: 0.65rem;
    font-weight: 700;
    color: var(--text-muted);
    letter-spacing: 0.08rem;
  }
  .diag-live {
    font-size: 0.6rem;
    color: var(--text-muted);
  }
  .live-dot {
    display: inline-block;
    width: 4px;
    height: 4px;
    border-radius: 50%;
    background-color: #ffffff;
  }
  .topology-canvas {
    padding: 1.5rem 2rem;
    display: flex;
    justify-content: center;
    align-items: center;
    position: relative;
    overflow: hidden;
  }
  .topology-canvas::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 100%;
    background: linear-gradient(to bottom, rgba(255,255,255,0) 0%, rgba(255,255,255,0.015) 50%, rgba(255,255,255,0) 100%);
    pointer-events: none;
    animation: scanLine 4s linear infinite;
  }
  .topology-svg {
    width: 100%;
    max-width: 580px;
    height: auto;
  }

  /* Diagnostic tables */
  .system-meta-panel {
    border: 1px solid var(--border-main);
    padding: 1.5rem;
  }
  .panel-header-minimal {
    font-family: var(--font-title);
    font-size: 0.7rem;
    font-weight: 800;
    color: var(--text-main);
    letter-spacing: 0.08rem;
    margin-bottom: 1rem;
  }
  .meta-rows {
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }
  .meta-row {
    display: flex;
    justify-content: space-between;
    border-bottom: 1px solid #0b0b0b;
    padding-bottom: 0.4rem;
  }
  .meta-row:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }
  .meta-row .lbl {
    font-size: 0.75rem;
    color: var(--text-muted);
  }
  .meta-row .val {
    font-size: 0.75rem;
    color: var(--text-muted);
  }

  /* Agent tab layout styling */
  .agents-console-split {
    min-height: 520px;
  }
  .config-drawer {
    width: 260px;
    flex-shrink: 0;
    border-right: 1px solid var(--border-main);
    padding-right: 1.5rem;
  }
  .drawer-title {
    font-family: var(--font-title);
    font-size: 0.75rem;
    font-weight: 800;
    color: var(--text-main);
    letter-spacing: 0.08rem;
    margin-bottom: 0.5rem;
  }
  .form-group label {
    font-family: var(--font-title);
    font-size: 0.65rem;
    font-weight: 700;
    color: var(--text-muted);
    letter-spacing: 0.05rem;
  }
  .form-group textarea {
    resize: none;
  }
  .btn-spinner {
    display: inline-block;
    width: 10px;
    height: 10px;
    border: 1.5px solid var(--border-main);
    border-top-color: var(--accent-white);
    border-radius: 50%;
  }

  /* Console stdout */
  .logs-pane {
    border: 1px solid var(--border-main);
    background-color: #020202;
    display: flex;
    flex-direction: column;
  }
  .logs-pane-header {
    border-bottom: 1px solid var(--border-main);
    padding: 0.6rem 1rem;
  }
  .logs-pane-header .title {
    font-family: var(--font-title);
    font-size: 0.65rem;
    font-weight: 700;
    color: var(--text-muted);
    letter-spacing: 0.08rem;
  }
  .logs-pane-header .active-dot {
    width: 4px;
    height: 4px;
    background-color: transparent;
    border-radius: 50%;
    display: inline-block;
  }
  .logs-pane-header .active-dot.active {
    background-color: #ffffff;
  }
  .btn-xs-custom {
    padding: 0.2rem 0.5rem;
    font-size: 0.6rem;
    letter-spacing: 0.02rem !important;
    border-color: #1a1a1a;
  }
  .btn-xs-custom:hover {
    letter-spacing: 0.04rem !important;
  }
  .console-wrapper {
    padding: 1rem;
    overflow-y: auto;
  }
  .console-log-box {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .console-empty {
    font-size: 0.75rem;
    color: var(--text-dim);
  }
  .log-entry {
    font-size: 0.75rem;
    line-height: 1.35;
    display: flex;
    align-items: flex-start;
    gap: 0.6rem;
  }
  .log-marker {
    color: var(--text-dim);
    flex-shrink: 0;
  }
  .log-entry.system {
    color: var(--text-muted);
  }
  .log-entry.tool {
    color: #aaaaaa;
  }
  .log-entry.tool-result {
    color: #cccccc;
  }
  .log-entry.error {
    color: #ffffff;
    border-left: 2px solid #ffffff;
    padding-left: 0.5rem;
  }
  .spinner-line {
    display: inline-block;
    width: 10px;
    height: 10px;
    border: 1px solid var(--border-main);
    border-top-color: #ffffff;
    border-radius: 50%;
  }

  /* Result styling card */
  .final-result-card {
    border: 1px solid var(--border-main);
    background-color: var(--bg-card);
  }
  .final-result-card .card-header {
    border-bottom: 1px solid var(--border-main);
    padding: 0.4rem 0.8rem;
    font-size: 0.65rem;
    color: var(--text-muted);
    font-weight: 700;
  }
  .final-result-card .card-content {
    padding: 0.8rem;
    font-size: 0.75rem;
    white-space: pre-wrap;
    line-height: 1.4;
  }

  /* Memory Tab Layout */
  .search-input {
    font-size: 0.85rem;
    padding: 0.4rem 0.2rem;
  }
  .search-btn {
    padding: 0.4rem 1rem;
    font-size: 0.75rem;
  }
  .memory-grid-split {
    min-height: 480px;
  }
  .memory-records-list {
    border-right: 1px solid var(--border-main);
    padding-right: 1.5rem;
  }
  .list-title {
    font-family: var(--font-title);
    font-size: 0.75rem;
    font-weight: 800;
    color: var(--text-main);
    letter-spacing: 0.08rem;
    margin-bottom: 1rem;
  }
  .records-container {
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    max-height: 420px;
    padding-right: 4px;
  }
  .records-empty {
    font-size: 0.75rem;
    color: var(--text-dim);
  }
  .mem-card-minimal {
    border: 1px solid var(--border-main);
    background-color: var(--bg-card);
    padding: 1rem;
    cursor: pointer;
    transition: var(--transition-fast);
  }
  .mem-card-minimal:hover {
    border-color: var(--border-active);
    background-color: var(--accent-gray);
  }
  .mem-card-minimal .card-hdr {
    font-size: 0.6rem;
    color: var(--text-dim);
    margin-bottom: 0.4rem;
  }
  .mem-card-minimal .card-txt {
    font-size: 0.8rem;
    line-height: 1.4;
    color: var(--text-main);
  }
  .tag-badge {
    font-family: var(--font-mono);
    font-size: 0.6rem;
    background-color: #000000;
    border: 1px solid var(--border-main);
    color: var(--text-muted);
    padding: 0.1rem 0.4rem;
    border-radius: 2px;
  }
  .card-timestamp {
    font-size: 0.6rem;
    color: var(--text-dim);
    margin-left: auto;
    align-self: center;
  }
  .memory-persist-drawer {
    width: 260px;
    flex-shrink: 0;
  }

  /* Event Log timeline lists */
  .events-log-split {
    min-height: 480px;
  }
  .events-stream-list {
    border-right: 1px solid var(--border-main);
    padding-right: 1.5rem;
  }
  .stream-container {
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    max-height: 420px;
  }
  .stream-empty {
    font-size: 0.75rem;
    color: var(--text-dim);
  }
  .event-log-row {
    width: 100%;
    background: transparent;
    border: 1px solid var(--border-main);
    color: var(--text-muted);
    padding: 0.6rem 0.8rem;
    display: flex;
    align-items: center;
    gap: 0.6rem;
    cursor: pointer;
    transition: var(--transition-fast);
    text-transform: none !important;
  }
  .event-log-row:hover {
    border-color: var(--border-active);
    color: var(--text-main);
    letter-spacing: 0.01rem !important; /* overrides button inherit hover */
  }
  .event-log-row.selected {
    border-color: var(--border-active);
    background-color: var(--accent-gray);
    color: var(--text-main);
  }
  .dot-bullet {
    width: 4px;
    height: 4px;
    background-color: var(--text-dim);
    border-radius: 50%;
  }
  .event-log-row.selected .dot-bullet {
    background-color: #ffffff;
  }
  .ev-name {
    font-weight: 700;
    font-size: 0.75rem;
  }
  .ev-actor {
    font-size: 0.7rem;
    color: var(--text-dim);
    margin-left: auto;
  }

  /* Inspector card styling */
  .inspector-card {
    border: 1px solid var(--border-main);
    background-color: #020202;
    padding: 1.2rem;
  }
  .inspector-empty {
    font-size: 0.75rem;
    color: var(--text-dim);
    text-align: center;
    margin: auto 0;
  }
  .meta-row-clean {
    display: flex;
    justify-content: space-between;
    border-bottom: 1px solid var(--border-main);
    padding-bottom: 0.4rem;
  }
  .meta-row-clean .k {
    color: var(--text-dim);
    font-weight: 700;
  }
  .meta-row-clean .v {
    color: var(--text-muted);
  }
  .payload-box {
    overflow: hidden;
  }
  .payload-hdr {
    font-size: 0.65rem;
    color: var(--text-dim);
    font-weight: 700;
  }
  .btn-xs-clean {
    padding: 0.1rem 0.4rem;
    font-size: 0.55rem;
    letter-spacing: 0;
    border-color: #1a1a1a;
  }
  .btn-xs-clean:hover {
    letter-spacing: 0.02rem !important;
  }
  .payload-pre {
    background-color: #000000;
    border: 1px solid var(--border-main);
    padding: 0.8rem;
    overflow-y: auto;
    font-size: 0.7rem;
    color: #aaaaaa;
    line-height: 1.35;
    white-space: pre-wrap;
    word-break: break-all;
    max-height: 240px;
  }
</style>
