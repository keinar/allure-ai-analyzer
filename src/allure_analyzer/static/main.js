// Create a unique ID for this chat session when the page loads
const sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);

// Global state
let currentReportDataAsText = '';
let reportTimestamps = [];
const charts = {}; // Object to hold our chart instances

document.addEventListener('DOMContentLoaded', () => {
    // --- UI elements ---
    const groupsContainer = document.getElementById('groups-container');
    const searchBox = document.getElementById('search-box');
    const darkModeToggle = document.getElementById('dark-mode-toggle');
    const reportSelector = document.getElementById('report-selector');
    const chatMessages = document.getElementById('chat-messages');
    const chatInputForm = document.getElementById('chat-input-form');
    const chatInput = document.getElementById('chat-input');
    const chatSendBtn = document.getElementById('chat-send-btn');
    
    const escapeHtml = (unsafe) => 
        unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");

    // --- Dashboard Rendering ---
    function renderDashboard(data) {
        if (charts.failuresByEpic) charts.failuresByEpic.destroy();
        if (charts.statusBreakdown) charts.statusBreakdown.destroy();

        const epicCounts = {};
        let totalFailed = 0;
        let totalBroken = 0;

        (data.groups || []).forEach(group => {
            totalFailed += group.status_counts?.failed || 0;
            totalBroken += group.status_counts?.broken || 0;
            const epics = group.epics && group.epics.length > 0 ? group.epics : ['Uncategorized'];
            epics.forEach(epic => {
                epicCounts[epic] = (epicCounts[epic] || 0) + (group.count || 0);
            });
        });

        const epicCtx = document.getElementById('failuresByEpicChart').getContext('2d');
        charts.failuresByEpic = new Chart(epicCtx, {
            type: 'bar',
            data: {
                labels: Object.keys(epicCounts),
                datasets: [{
                    label: 'Total Failures',
                    data: Object.values(epicCounts),
                    backgroundColor: 'rgba(0, 123, 255, 0.6)',
                    borderColor: 'rgba(0, 123, 255, 1)',
                    borderWidth: 1
                }]
            },
            options: { indexAxis: 'y', responsive: true, plugins: { legend: { display: false } } }
        });

        const statusCtx = document.getElementById('statusBreakdownChart').getContext('2d');
        charts.statusBreakdown = new Chart(statusCtx, {
            type: 'doughnut',
            data: {
                labels: ['Failed', 'Broken'],
                datasets: [{
                    data: [totalFailed, totalBroken],
                    backgroundColor: ['rgba(220, 53, 69, 0.7)', 'rgba(255, 193, 7, 0.7)'],
                    borderColor: ['rgba(220, 53, 69, 1)', 'rgba(255, 193, 7, 1)'],
                    borderWidth: 1
                }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });
    }

    function createGroupCardHTML(group) {
        const epicsHtml = (group.epics || []).map(e => `<span class="label-tag">${escapeHtml(e)}</span>`).join('') || 'N/A';
        const featuresHtml = (group.features || []).map(f => `<span class="label-tag">${escapeHtml(f)}</span>`).join('') || 'N/A';
        const statusCounts = group.status_counts || {};
        const failedCount = statusCounts.failed || 0;
        const brokenCount = statusCounts.broken || 0;
        const totalInGroup = group.count || 0;
        const failedPercent = totalInGroup > 0 ? (failedCount / totalInGroup) * 100 : 0;
        const brokenPercent = totalInGroup > 0 ? (brokenCount / totalInGroup) * 100 : 0;
        let statusTagsHtml = '';
        let progressBarTitle = [];
        if (failedCount > 0) {
            statusTagsHtml += `<span class="status-tag status-failed">${failedCount} F</span>`;
            progressBarTitle.push(`${failedCount} Failed`);
        }
        if (brokenCount > 0) {
            statusTagsHtml += `<span class="status-tag status-broken">${brokenCount} B</span>`;
            progressBarTitle.push(`${brokenCount} Broken`);
        }
        return `
        <div class="group-card" data-index="${group.id}">
            <div class="card-header">
                <div class="card-title"><span class="arrow">▶</span> Group ${group.id}: ${escapeHtml(group.title || '')}</div>
                <div class="card-summary">
                    <div class="status-tags">${statusTagsHtml}</div>
                    <div class="progress-bar" title="${progressBarTitle.join(', ')}">
                        <div class="progress-segment progress-failed" style="width: ${failedPercent.toFixed(2)}%;"></div>
                        <div class="progress-segment progress-broken" style="width: ${brokenPercent.toFixed(2)}%;"></div>
                    </div>
                </div>
            </div>
            <div class="card-content">
                <h4>Fingerprint</h4>
                <code><b>What:</b> ${escapeHtml(group.fingerprint_what || '')}</code><br>
                <code><b>Where:</b> ${escapeHtml(group.fingerprint_where || '')}</code>
                <h4>Affected Areas</h4>
                <p><b>Epics:</b> ${epicsHtml}</p>
                <p><b>Features:</b> ${featuresHtml}</p>
                <h4>Example from Test: code>${escapeHtml(group.example?.test_name || '')}</code></h4>
                <b>Original Message:</b><pre>${escapeHtml(group.example?.message || '')}</pre>
                <b>Full Stack Trace:</b><pre>${escapeHtml(group.example?.trace || '')}</pre>
            </div>
        </div>`;
    }

    function renderReport(data) {
        let totalFailed = 0, totalBroken = 0;
        (data.groups || []).forEach(g => {
            totalFailed += g.status_counts?.failed || 0;
            totalBroken += g.status_counts?.broken || 0;
        });
        const metadata = data.metadata || {};
        document.getElementById('meta-date').textContent = new Date(metadata.generation_date || Date.now()).toLocaleString();
        document.getElementById('meta-total').innerHTML = `${metadata.total_failures || 0} (<span style="color:var(--status-failed-bg);">${totalFailed} F</span>, <span style="color:var(--status-broken-bg);">${totalBroken} B</span>)`;
        document.getElementById('meta-groups').textContent = metadata.unique_groups || 0;
        groupsContainer.innerHTML = (data.groups || []).map(createGroupCardHTML).join('');
    }

    async function loadReport(timestamp) {
        groupsContainer.innerHTML = '<div id="loader">Loading report data...</div>';
        try {
            const response = await fetch(`/reports/${timestamp}`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            currentReportDataAsText = await response.text();
            const data = JSON.parse(currentReportDataAsText);
            renderDashboard(data);
            renderReport(data);
        } catch (error) {
            groupsContainer.innerHTML = `<div id="loader" style="color: var(--status-failed-bg);">Failed to load report data: ${error.message}.</div>`;
            console.error("Failed to fetch report data:", error);
        }
    }

    async function initializeReports() {
        try {
            const response = await fetch('/reports');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            reportTimestamps = await response.json();
            if (reportTimestamps && reportTimestamps.length > 0) {
                reportSelector.innerHTML = reportTimestamps.map(ts => `<option value="${ts}">${ts.replace('_', ' ')}</option>`).join('');
                await loadReport(reportTimestamps[0]);
                
                // Read the config value from the body's data attribute
                const proactiveSummaryEnabled = document.body.dataset.proactiveSummary === 'True';
                
                if (proactiveSummaryEnabled) {
                    getProactiveSummary();
                } else {
                    const welcomeMessage = "Hello! I've read the failure report. Ask me anything about the data.";
                    document.querySelector('#chat-messages').innerHTML = `<div class="ai-message">${welcomeMessage}</div>`;
                }
            } else {
                 groupsContainer.innerHTML = '<div id="loader">No historical reports found. Run "allure-analyze generate" first.</div>';
            }
        } catch (error) {
            groupsContainer.innerHTML = `<div id="loader" style="color: var(--status-failed-bg);">Could not fetch reports list. Is the server running?</div>`;
            console.error("Failed to list reports:", error);
        }
    }
    
    function addMessageToUI(content, sender, isLoading = false) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('chat-message', `${sender}-message`);
        if (isLoading) {
            messageDiv.classList.add('loading');
            messageDiv.innerHTML = '<span></span><span></span><span></span>';
        } else {
            if (sender === 'ai') {
                messageDiv.innerHTML = marked.parse(content || "");
            } else {
                messageDiv.textContent = content;
            }
        }
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    async function getAIResponse(userInput, isProactive = false) {
        if (!isProactive) {
            addMessageToUI(userInput, 'user');
        }
        chatInput.value = '';
        addMessageToUI('', 'ai', true);

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    question: userInput,
                    session_id: sessionId 
                })
            });
            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || `API error! status: ${response.status}`);
            }
            const result = await response.json();
            chatMessages.querySelector('.loading').remove();
            addMessageToUI(result.response, 'ai');
        } catch (error) {
            chatMessages.querySelector('.loading').remove();
            addMessageToUI(`Sorry, I encountered an error: ${error.message}`, 'ai');
            console.error("AI Chat Error:", error);
        }
    }

    function getProactiveSummary() {
        const proactivePrompt = "Provide a brief 'executive summary' comparing the latest report to the one before it. Highlight the main trend, any new critical failures, and any significant resolved issues.";
        // Clear initial message and get summary
        document.querySelector('#chat-messages').innerHTML = '';
        getAIResponse(proactivePrompt, true);
    }
    
    // --- EVENT LISTENERS ---
    chatInputForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const userInput = chatInput.value.trim();
        if (userInput) {
            getAIResponse(userInput);
        }
    });

    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatSendBtn.click();
        }
    });

    reportSelector.addEventListener('change', (e) => loadReport(e.target.value));
    
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
        document.body.classList.add('dark-mode');
    }
    darkModeToggle.addEventListener('click', () => {
        document.body.classList.toggle('dark-mode');
        localStorage.setItem('theme', document.body.classList.contains('dark-mode') ? 'dark' : 'light');
    });

    groupsContainer.addEventListener('click', (event) => {
        const header = event.target.closest('.card-header');
        if (header) {
            const content = header.nextElementSibling;
            const arrow = header.querySelector('.arrow');
            if (content.classList.contains('card-content')) {
                content.style.display = content.style.display === 'block' ? 'none' : 'block';
                arrow.classList.toggle('expanded');
            }
        }
    });
    
    searchBox.addEventListener('input', (event) => {
        const searchTerm = event.target.value.toLowerCase();
        document.querySelectorAll('.group-card').forEach(card => {
            card.style.display = card.textContent.toLowerCase().includes(searchTerm) ? '' : 'none';
        });
    });

    // --- INITIALIZE THE APP ---
    initializeReports();
});