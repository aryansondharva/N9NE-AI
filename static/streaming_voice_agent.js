class VoiceAgent {
    constructor() {
        this.websocket = null;
        this.mediaRecorder = null;
        this.audioStream = null;
        this.isRecording = false;
        this.isConnected = false;
        this.audioContext = null;
        this.analyser = null;
        this.dataArray = null;
        this.animationFrame = null;

        this.initializeElements();
        this.setupEventListeners();
        this.connectWebSocket();
    }

    initializeElements() {
        this.recordBtn = document.getElementById('record-btn');
        this.statusText = document.getElementById('status-text');
        this.statusDetail = document.getElementById('status-detail');
        this.connectionStatus = document.getElementById('connection-status');
        this.messagesContainer = document.getElementById('messages-container');
        this.liveTranscription = document.getElementById('live-transcription');
        this.liveText = document.getElementById('live-text');
        this.audioLevel = document.getElementById('audio-level');
        this.clearBtn = document.getElementById('clear-btn');
        this.debugPanel = document.getElementById('debug-panel');
        this.debugContent = document.getElementById('debug-content');
        this.debugToggleBtn = document.getElementById('debug-toggle');
        this.clearDebugBtn = document.getElementById('clear-debug');
    }

    setupEventListeners() {
        this.recordBtn.addEventListener('click', () => {
            if (!this.recordBtn.disabled) {
                this.toggleRecording();
            }
        });
        this.clearBtn.addEventListener('click', () => this.clearMessages());
        this.debugToggleBtn.addEventListener('click', () => this.toggleDebug());
        this.clearDebugBtn.addEventListener('click', () => this.clearDebug());

        document.getElementById('toggle-debug')?.addEventListener('click', () => {
            this.debugPanel.classList.add('hidden');
        });
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host || 'localhost:8000';
        const wsUrl = `${protocol}//${host}/ws`;

        this.log(`Attempting to connect to: ${wsUrl}`);
        this.setRecordButtonState(false, 'Connecting...'); // Disable button
        this.websocket = new WebSocket(wsUrl);

        this.websocket.onopen = () => {
            this.isConnected = true;
            this.updateConnectionStatus(true);
            this.setRecordButtonState(true); // Enable button
            this.log('WebSocket connected');
            this.updateStatus('Connected to server', 'Ready to start recording');
        };

        this.websocket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleWebSocketMessage(data);
            } catch (e) {
                // Handle plain text messages
                this.log('Server message: ' + event.data);
                if (event.data.includes('transcription session started')) {
                    this.updateStatus('Recording...', 'Speak now - real-time transcription active');
                }
            }
        };

        this.websocket.onclose = () => {
            this.isConnected = false;
            this.updateConnectionStatus(false);
            this.setRecordButtonState(false, 'Reconnecting...'); // Disable button
            this.log('WebSocket disconnected');
            this.updateStatus('Disconnected', 'Attempting to reconnect...');

            // Attempt to reconnect after 3 seconds
            setTimeout(() => this.connectWebSocket(), 3000);
        };

        this.websocket.onerror = (error) => {
            this.log('WebSocket error: ' + JSON.stringify(error));
            this.setRecordButtonState(false, 'Connection Error'); // Disable button
            this.updateStatus('Connection error', 'Please refresh the page');
        };
    }

    handleWebSocketMessage(data) {
        try {
            if (!data) {
                this.log('Received empty message');
                return;
            }

            this.log('Received: ' + JSON.stringify(data));

            // Handle both string and object messages
            if (typeof data === 'string') {
                try {
                    data = JSON.parse(data);
                } catch (e) {
                    this.log('Non-JSON message: ' + data);
                    return;
                }
            }

            if (!data.type) {
                this.log('Message missing type field:', data);
                return;
            }

            switch (data.type) {
                case 'transcription':
                    this.handleTranscription(data);
                    break;
                case 'turn_detection':
                    this.handleTurnDetection(data);
                    break;
                case 'llm_response':
                    this.handleLLMResponse(data);
                    break;
                case 'error':
                    this.handleError(data);
                    break;
                default:
                    this.log('Unknown message type: ' + (data.type || 'none'));
            }
        } catch (error) {
            console.error('Error handling WebSocket message:', error);
            this.log('Error handling message: ' + (error.message || String(error)));
        }
    }

    handleTranscription(data) {
        if (!data || !data.text) return;

        try {
            if (data.message_type === 'PartialTranscript') {
                this.updateOrCreateUserMessage(data.text);
            } else if (data.message_type === 'FinalTranscript') {
                this.updateOrCreateUserMessage(data.text, true);
            }
        } catch (error) {
            console.error('Error handling transcription:', error);
            this.log('Transcription error: ' + error.message);
        }
    }

    handleTurnDetection(data) {
        this.log('Turn detected: ' + JSON.stringify(data));

        const final_text = data.final_text ? data.final_text.trim() : '';
        if (final_text) {
            this.updateOrCreateUserMessage(final_text, true);
        }

        this.addMessage('system', `🔄 Turn detected - Processing your request...`, new Date().toLocaleTimeString());
        this.updateStatus('Processing...', 'AI is generating response');
        this.hideLiveTranscription();
    }

    handleLLMResponse(data) {
        // Log the raw LLM response chunk to the console for debugging
        console.log('LLM Response Chunk:', data);

        if (data.chunk) {
            // Handle streaming LLM response
            this.updateOrCreateLLMMessage(data.chunk, data.is_complete);
        }

        if (data.is_complete) {
            console.log('LLM Streaming Complete. Full Response:', data.full_response);
        }
    }

    handleError(data) {
        this.log('Error: ' + data.message);
        this.addMessage('error', `❌ Error: ${data.message}`, new Date().toLocaleTimeString());
    }

    setRecordButtonState(enabled, tooltip = '') {
        if (!this.recordBtn) return;

        this.recordBtn.disabled = !enabled;
        if (enabled) {
            this.recordBtn.classList.remove('bg-gray-400', 'cursor-not-allowed');
            this.recordBtn.classList.add('bg-red-500', 'hover:bg-red-600');
            this.recordBtn.title = 'Click to start/stop recording';
        } else {
            this.recordBtn.classList.add('bg-gray-400', 'cursor-not-allowed');
            this.recordBtn.classList.remove('bg-red-500', 'hover:bg-red-600', 'recording');
            this.recordBtn.title = tooltip;
        }
    }

    toggleRecording() {
        if (this.isRecording) {
            this.stopRecording();
        } else {
            this.startRecording();
        }
    }

    async startRecording() {
        if (!this.isConnected || !this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
            this.log('Cannot start recording: WebSocket is not connected.');
            this.updateStatus('Error', 'Not connected to the server. Please wait.');
            return;
        }

        try {
            // Request microphone access
            this.audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // Setup audio context for level monitoring
            this.setupAudioContext();

            // Setup MediaRecorder
            this.mediaRecorder = new MediaRecorder(this.audioStream);

            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0 && this.websocket.readyState === WebSocket.OPEN) {
                    this.websocket.send(event.data);
                }
            };

            // Send start recording command
            this.websocket.send('start_recording');

            // Start recording with small chunks for real-time streaming
            this.mediaRecorder.start(100); // Send data every 100ms

            this.isRecording = true;
            this.updateRecordingUI(true);
            this.startAudioLevelMonitoring();

        } catch (error) {
            console.error('Error starting recording:', error);
            this.log(`Error starting recording: ${error.name} - ${error.message}`);

            let errorMessage = 'Could not access microphone.';
            if (error.name === 'NotAllowedError') {
                errorMessage = 'Microphone access denied. Please check your browser permissions.';
            } else if (error.name === 'NotFoundError') {
                errorMessage = 'No microphone found. Please connect a microphone and try again.';
            } else {
                errorMessage = `Could not access microphone: ${error.name}. Please check the browser console for details.`;
            }

            this.updateStatus('Error', errorMessage);
            this.addMessage('error', `🎤 ${errorMessage}`, new Date().toLocaleTimeString());
            this.isRecording = false;
            if (this.recordBtn) {
                this.recordBtn.classList.remove('recording');
            }
        }
    }

    stopRecording() {
        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            this.mediaRecorder.stop();
        }

        if (this.audioStream) {
            this.audioStream.getTracks().forEach(track => track.stop());
        }

        // Send stop recording command
        if (this.websocket.readyState === WebSocket.OPEN) {
            this.websocket.send('stop_recording');
        }

        this.isRecording = false;
        this.updateRecordingUI(false);
        this.stopAudioLevelMonitoring();
    }

    updateRecordingUI(isRecording) {
        if (isRecording) {
            this.recordBtn.classList.add('recording');
            this.updateStatus('Recording...', 'Speak now - real-time transcription active');
        } else {
            this.recordBtn.classList.remove('recording');
            this.updateStatus('Processing...', 'Please wait');
            this.hideLiveTranscription();
        }
    }

    setupAudioContext() {
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        }
        const source = this.audioContext.createMediaStreamSource(this.audioStream);
        this.analyser = this.audioContext.createAnalyser();
        this.analyser.fftSize = 256;
        source.connect(this.analyser);
        this.dataArray = new Uint8Array(this.analyser.frequencyBinCount);
    }

    startAudioLevelMonitoring() {
        const draw = () => {
            if (!this.isRecording) return;

            this.analyser.getByteFrequencyData(this.dataArray);
            let sum = 0;
            for (const amplitude of this.dataArray) {
                sum += amplitude * amplitude;
            }
            const level = Math.sqrt(sum / this.dataArray.length);

            // Update audio level indicator
            if (this.audioLevel) {
                this.audioLevel.style.width = `${level}%`;
            }

            this.animationFrame = requestAnimationFrame(draw);
        };
        this.animationFrame = requestAnimationFrame(draw);
    }

    stopAudioLevelMonitoring() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }
        if (this.audioLevel) {
            this.audioLevel.style.width = '0%';
        }
    }

    updateConnectionStatus(isConnected) {
        const statusDiv = this.connectionStatus;
        if (!statusDiv) return;

        const indicator = statusDiv.querySelector('div');
        const text = statusDiv.querySelector('span');

        if (isConnected) {
            indicator.classList.remove('bg-red-500');
            indicator.classList.add('bg-green-500');
            text.textContent = 'Connected';
            statusDiv.className = 'flex items-center gap-2 px-3 py-1.5 bg-green-100 rounded-full';
        } else {
            indicator.classList.remove('bg-green-500');
            indicator.classList.add('bg-red-500');
            text.textContent = 'Disconnected';
            statusDiv.className = 'flex items-center gap-2 px-3 py-1.5 bg-red-100 rounded-full';
        }
    }

    updateStatus(main, detail) {
        this.statusText.textContent = main;
        this.statusDetail.textContent = detail;
    }

    showLiveTranscription(text) {
        try {
            if (!this.liveTranscription || !this.liveText) return;
            this.liveTranscription.classList.remove('hidden');
            this.liveText.textContent = text || '';
            // Auto-scroll to show latest transcription
            this.liveTranscription.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } catch (error) {
            console.error('Error showing live transcription:', error);
        }
    }

    hideLiveTranscription() {
        this.liveTranscription.classList.add('hidden');
        this.liveText.textContent = '';
    }

    updateOrCreateUserMessage(text, isComplete = false) {
        let userMessage = this.messagesContainer.querySelector('.user-streaming');

        if (!userMessage) {
            const placeholder = this.messagesContainer.querySelector('.text-center');
            if (placeholder) placeholder.remove();

            const messageDiv = document.createElement('div');
            messageDiv.className = 'flex gap-3 mb-3 user-streaming justify-end';
            messageDiv.innerHTML = `
                <div class="flex-1 max-w-[75%]">
                    <div class="message-bubble user-message p-3 rounded-lg bg-blue-500 text-white ml-auto">
                        <p class="whitespace-pre-wrap break-words"></p>
                        <div class="text-xs opacity-70 mt-1 text-right">${new Date().toLocaleTimeString()}</div>
                    </div>
                </div>
                <div class="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-sm">
                     <i class="fas fa-user"></i>
                </div>
            `;
            this.messagesContainer.appendChild(messageDiv);
            userMessage = messageDiv;
        }

        const p = userMessage.querySelector('p');
        if (p) {
            p.textContent = text;
        }

        if (isComplete) {
            userMessage.classList.remove('user-streaming');
        }

        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }

    addMessage(type, content, timestamp) {
        try {
            if (!this.messagesContainer) return;

            // Remove placeholder if it exists
            const placeholder = this.messagesContainer.querySelector('.text-center');
            if (placeholder) {
                placeholder.remove();
            }

            const messageDiv = document.createElement('div');
            messageDiv.className = 'flex gap-3 mb-3';

            let messageClass = 'message-bubble p-3 rounded-lg max-w-3/4';
            let icon = '';

            // Set message styling based on type
            switch (type) {
                case 'user':
                    messageClass += ' bg-blue-500 text-white ml-auto';
                    icon = '<i class="fas fa-user"></i>';
                    break;
                case 'assistant':
                    messageClass += ' bg-gray-100 text-gray-800';
                    icon = '<i class="fas fa-robot"></i>';
                    break;
                case 'system':
                    messageClass += ' bg-yellow-100 text-yellow-800 text-center';
                    icon = '<i class="fas fa-info-circle"></i>';
                    break;
                case 'error':
                    messageClass += ' bg-red-100 text-red-700';
                    icon = '<i class="fas fa-exclamation-triangle"></i>';
                    break;
            }

            // Create message HTML
            messageDiv.innerHTML = `
                <div class="flex-shrink-0 w-8 h-8 rounded-full ${type === 'user' ? 'bg-blue-100' : 'bg-gray-200'} flex items-center justify-center text-sm">
                    ${icon}
                </div>
                <div class="flex-1">
                    <div class="${messageClass}">
                        <p class="whitespace-pre-wrap break-words">${content || ''}</p>
                        <div class="text-xs opacity-70 mt-1">${timestamp || new Date().toLocaleTimeString()}</div>
                    </div>
                </div>
            `;

            // Add message to container
            this.messagesContainer.appendChild(messageDiv);

            // Auto-scroll to bottom
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;

        } catch (error) {
            console.error('Error adding message:', error);
            this.log('Error adding message: ' + error.message);
        }
    }

    updateOrCreateLLMMessage(chunk, isComplete) {
        let llmMessage = this.messagesContainer.querySelector('.llm-streaming');

        if (!llmMessage) {
            // Remove placeholder if it exists
            const placeholder = this.messagesContainer.querySelector('.text-center');
            if (placeholder) {
                placeholder.remove();
            }

            const messageDiv = document.createElement('div');
            messageDiv.className = 'flex gap-3 mb-3 llm-streaming';
            messageDiv.innerHTML = `
                <div class="flex-shrink-0 w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center text-sm">
                    <i class="fas fa-robot"></i>
                </div>
                <div class="flex-1">
                    <div class="message-bubble assistant-message p-3 rounded-lg bg-gray-100 text-gray-800">
                        <p class="whitespace-pre-wrap break-words"></p>
                        <div class="text-xs opacity-70 mt-1">${new Date().toLocaleTimeString()}</div>
                    </div>
                </div>
            `;
            this.messagesContainer.appendChild(messageDiv);
            llmMessage = messageDiv;
        }

        const p = llmMessage.querySelector('p');
        if (p) {
            p.textContent += chunk;
        }

        if (isComplete) {
            llmMessage.classList.remove('llm-streaming');
            this.updateStatus('Ready', 'Click the button to speak');
        }

        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }
    
     clearMessages() {
        this.messagesContainer.innerHTML = `
            <div class="text-center py-12 text-gray-400">
                <i class="fas fa-comments text-4xl mb-3 opacity-30"></i>
                <p class="text-sm">Your conversation will appear here...</p>
            </div>
        `;
    }
    
    toggleDebug() {
        this.debugPanel.classList.toggle('hidden');
    }
    
    log(message) {
        console.log(message);
        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = 'mb-1';
        logEntry.textContent = `[${timestamp}] ${message}`;
        this.debugContent.appendChild(logEntry);
        this.debugContent.scrollTop = this.debugContent.scrollHeight;
    }

    clearDebug() {
        this.debugContent.innerHTML = '';
    }
}

// Initialize the voice agent when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new VoiceAgent();
});
