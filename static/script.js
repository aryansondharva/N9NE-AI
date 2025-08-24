/**
 * AudioStreamClient - Handles WebSocket connection for streaming audio
 * Connects to the WebSocket server and manages audio chunks
 */
class AudioStreamClient {
    constructor() {
        this.ws = null;
        this.audioChunks = []; // Array to accumulate base64 chunks
        this.streamingAudioChunks = []; // Array to accumulate streaming audio chunks (Day 21)
        this.isConnected = false;
        this.audioContext = null;
        this.audioQueue = [];
        this.isPlaying = false;
        this.currentSource = null;
        this.bufferSize = 4; // Number of chunks to buffer before starting playback
        this.maxBufferSize = 8; // Maximum number of chunks to buffer
        this.playbackRate = 1.0; // Default playback rate
        this.volume = 1.0; // Default volume
        this.isPaused = false;
        this.lastPlayTime = 0;
        this.bufferedChunks = 0;
        this.connect();
        this.initializeUI();
    }

    connect() {
        // Adjust the WebSocket URL to your server
        const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const host = window.location.host;
        this.ws = new WebSocket(`${protocol}${host}/ws/audio`);
        
        this.ws.onopen = () => {
            console.log('✅ WebSocket connected to audio stream.');
            this.isConnected = true;
            this.initializeAudioContext();
        };

        this.ws.onmessage = async (event) => {
            try {
                const message = JSON.parse(event.data);
                
                if (message.type === 'audio_chunk') {
                    // Accumulate the base64 chunk
                    this.audioChunks.push(message.data);
                    console.log('📦 Received audio chunk. Total chunks:', this.audioChunks.length);
                    
                    // Add to playback queue if audio context is ready
                    if (this.audioContext) {
                        await this.queueAudioChunk(message.data);
                    }
                } else if (message.type === 'streaming_audio') {
                    // Day 21: Handle streaming audio data from Murf
                    const base64Audio = message.base64_audio;
                    this.streamingAudioChunks.push(base64Audio);
                    
                    // Print acknowledgement to console
                    console.log(`🎵 [DAY 21] Received streaming audio chunk #${this.streamingAudioChunks.length}`);
                    console.log(`📊 Audio data length: ${base64Audio.length} characters`);
                    console.log(`📈 Total accumulated chunks: ${this.streamingAudioChunks.length}`);
                    console.log(`✅ Audio data acknowledged and stored in array`);
                    
                    // Optional: Show first few characters for verification
                    console.log(`🔍 Audio data preview: ${base64Audio.substring(0, 50)}...`);
                    
                } else if (message.type === 'stream_complete') {
                    console.log('🎉 Audio stream complete!');
                    console.log('Full audio data (as base64 chunks array):', this.audioChunks);
                    
                    // Reset for next stream
                    this.audioChunks = [];
                }
            } catch (error) {
                console.error('Error processing WebSocket message:', error);
            }
        };

        this.ws.onclose = () => {
            console.log('❌ WebSocket connection closed.');
            this.isConnected = false;
            // Attempt to reconnect after a delay
            setTimeout(() => this.connect(), 3000);
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    async initializeAudioContext() {
        try {
            // Create audio context when user interacts with the page
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (!this.audioContext) {
                this.audioContext = new AudioContext();
                await this.audioContext.resume();
                console.log('🔊 Audio context initialized');
            }
        } catch (error) {
            console.error('Error initializing audio context:', error);
        }
    }

    async queueAudioChunk(base64Audio) {
        // Don't queue if we've reached max buffer size
        if (this.audioQueue.length >= this.maxBufferSize) {
            console.log('Buffer full, dropping chunk');
            return;
        }
        
        try {
            // Convert base64 to ArrayBuffer in a web worker to avoid blocking the main thread
            const binaryString = atob(base64Audio);
            const len = binaryString.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }

            // Decode the audio data and add to queue
            try {
                const audioData = await this.audioContext.decodeAudioData(bytes.buffer);
                this.audioQueue.push(audioData);
                this.updateBufferStatus();
                
                // Start playback if not already playing
                if (!this.isPlaying) {
                    this.playNextChunk();
                }
                
            } catch (error) {
                console.error('Error decoding audio data:', error);
                // Try to recover by playing the next chunk if available
                if (this.audioQueue.length > 0) {
                    this.playNextChunk();
                }
            }
            
        } catch (error) {
            console.error('Error processing audio chunk:', error);
            this.updateBufferStatus();
        }
    }
    
    async playNextChunk() {
        // Don't play if paused or already playing
        if (this.isPaused || this.isPlaying || this.audioQueue.length === 0) {
            this.updateBufferStatus();
            return;
        }
        
        // Start playing only if we have enough buffered chunks
        if (this.audioQueue.length < this.bufferSize && this.audioQueue.length < this.maxBufferSize) {
            this.updateBufferStatus();
            return;
        }
        
        this.isPlaying = true;
        const audioData = this.audioQueue.shift();
        this.bufferedChunks--;
        this.updateBufferStatus();
        
        try {
            this.currentSource = this.audioContext.createBufferSource();
            const gainNode = this.audioContext.createGain();
            
            // Configure audio source
            this.currentSource.buffer = audioData;
            this.currentSource.playbackRate.value = this.playbackRate;
            
            // Set up audio graph
            this.currentSource.connect(gainNode);
            gainNode.gain.value = this.volume;
            gainNode.connect(this.audioContext.destination);
            
            // Calculate precise timing
            const now = this.audioContext.currentTime;
            const startTime = Math.max(now, this.lastPlayTime);
            
            // Start playback
            this.currentSource.start(startTime);
            this.lastPlayTime = startTime + audioData.duration;
            
            // Set up event for when this chunk finishes playing
            this.currentSource.onended = () => {
                try {
                    if (this.currentSource) {
                        this.currentSource.disconnect();
                        gainNode.disconnect();
                        this.currentSource = null;
                    }
                    
                    this.isPlaying = false;
                    this.updateBufferStatus();
                    
                    // Immediately schedule next chunk if available
                    if (this.audioQueue.length > 0) {
                        this.playNextChunk();
                    }
                } catch (error) {
                    console.error('Error in onended handler:', error);
                    this.isPlaying = false;
                    this.updateBufferStatus();
                }
            };
            
            // Add error handler
            this.currentSource.onerror = (error) => {
                console.error('Audio playback error:', error);
                this.isPlaying = false;
                this.updateBufferStatus();
                
                // Try to recover by playing the next chunk if available
                if (this.audioQueue.length > 0) {
                    this.playNextChunk();
                }
            };
            
            // Schedule next chunk if buffer is healthy
            if (this.audioQueue.length >= this.bufferSize) {
                setTimeout(() => this.playNextChunk(), (audioData.duration * 1000) * 0.8);
            }
            
        } catch (error) {
            console.error('Error playing audio chunk:', error);
            this.isPlaying = false;
            this.updateBufferStatus();
            
            // Try to recover by playing the next chunk if available
            if (this.audioQueue.length > 0) {
                this.playNextChunk();
            }
        }
    }

    // Initialize UI elements and event listeners
    initializeUI() {
        this.audioStatus = document.getElementById('audio-status');
        this.bufferIndicator = document.getElementById('buffer-indicator');
        this.bufferText = document.getElementById('buffer-text');
        this.chunkCount = document.getElementById('chunk-count');
        
        // Show audio status by default
        if (this.audioStatus) {
            this.audioStatus.classList.remove('hidden');
        }
    }
    
    // Update the buffer status UI
    updateBufferStatus() {
        if (!this.bufferIndicator || !this.bufferText || !this.chunkCount) return;
        
        const bufferPercentage = Math.min(100, Math.round((this.audioQueue.length / this.maxBufferSize) * 100));
        const bufferedSeconds = this.audioQueue.reduce((total, chunk) => total + chunk.duration, 0);
        
        this.bufferIndicator.style.width = `${bufferPercentage}%`;
        this.bufferText.textContent = `Buffer: ${bufferedSeconds.toFixed(1)}s (${bufferPercentage}%)`;
        this.chunkCount.textContent = `Chunks: ${this.audioQueue.length}`;
        
        // Update status indicator
        if (this.isPaused) {
            this.setAudioStatus('paused', 'Paused');
        } else if (this.isPlaying) {
            this.setAudioStatus('playing', 'Playing...');
        } else if (this.audioQueue.length > 0) {
            if (this.audioQueue.length < this.bufferSize) {
                this.setAudioStatus('buffering', 'Buffering...');
            } else {
                this.setAudioStatus('ready', 'Ready to play');
            }
        } else {
            this.setAudioStatus('idle', 'Waiting for audio');
        }
    }
    
    // Set audio status with visual feedback
    setAudioStatus(status, message) {
        if (!this.audioStatus) return;
        
        // Remove all status classes
        this.audioStatus.classList.remove('playing', 'buffering', 'idle');
        
        // Add current status class
        this.audioStatus.classList.add(status);
        
        // Update status text
        const statusText = this.audioStatus.querySelector('span');
        if (statusText) {
            statusText.textContent = message;
        }
        
        // Update icon
        const icon = this.audioStatus.querySelector('i');
        if (icon) {
            switch(status) {
                case 'playing':
                    icon.className = 'fas fa-volume-up animate-pulse';
                    break;
                case 'buffering':
                    icon.className = 'fas fa-spinner fa-spin';
                    break;
                default:
                    icon.className = 'fas fa-volume-up';
            }
        }
    }
    
    // Pause audio playback
    pause() {
        if (this.isPlaying && this.audioContext) {
            this.audioContext.suspend();
            this.isPaused = true;
            this.isPlaying = false;
            this.updateBufferStatus();
        }
    }
    
    // Resume audio playback
    resume() {
        if (this.isPaused && this.audioContext) {
            this.audioContext.resume();
            this.isPaused = false;
            this.isPlaying = false; // Will be set to true when next chunk plays
            this.updateBufferStatus();
            this.playNextChunk(); // Resume playback if chunks are available
        }
    }
    
    // Set playback rate (0.5 to 4.0)
    setPlaybackRate(rate) {
        this.playbackRate = Math.min(4.0, Math.max(0.5, rate));
        if (this.currentSource) {
            this.currentSource.playbackRate.value = this.playbackRate;
        }
    }
    
    // Set volume (0.0 to 1.0)
    setVolume(volume) {
        this.volume = Math.min(1.0, Math.max(0.0, volume));
        // Volume changes are applied when creating new audio nodes
    }
    
    // Clean up resources
    cleanup() {
        this.pause();
        
        if (this.currentSource) {
            try {
                this.currentSource.stop();
                this.currentSource.disconnect();
            } catch (e) {
                console.warn('Error cleaning up audio source:', e);
            }
            this.currentSource = null;
        }
        
        if (this.audioContext) {
            this.audioContext.close().catch(e => console.warn('Error closing audio context:', e));
            this.audioContext = null;
        }
        
        this.audioQueue = [];
        this.isPlaying = false;
        this.isPaused = false;
        this.lastPlayTime = 0;
        this.bufferedChunks = 0;
        this.updateBufferStatus();
    }
    
    // Function to send text for TTS
    async sendTextForTTS(text, voice = 'default') {
        if (!this.isConnected) {
            console.error('WebSocket not connected');
            return;
        }

        try {
            const response = await fetch('/tts', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: text,
                    voice: voice
                })
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const result = await response.json();
            console.log('TTS request sent:', result);
            return result;
            
        } catch (error) {
            console.error('Error sending text for TTS:', error);
            throw error;
        }
    }
}

// Initialize the WebSocket client when the page loads
document.addEventListener('DOMContentLoaded', () => {
    // Create global instance
    window.audioStreamClient = new AudioStreamClient();
    
    // Example usage with a button
    const ttsButton = document.getElementById('tts-button');
    const ttsInput = document.getElementById('tts-input');
    
    if (ttsButton && ttsInput) {
        ttsButton.addEventListener('click', async () => {
            const text = ttsInput.value.trim();
            if (text) {
                try {
                    await window.audioStreamClient.sendTextForTTS(text);
                    ttsInput.value = ''; // Clear input after sending
                } catch (error) {
                    console.error('Failed to send text for TTS:', error);
                }
            }
        });
    }
});
