/* ====== DAY 10 JS: Chat History with Session Management ====== */

// Change this to your backend origin if needed
const BASE_URL = 'http://127.0.0.1:8000';

// Session Management
function getSessionId() {
  const params = new URLSearchParams(window.location.search);
  let sessionId = params.get("session_id");
  if (!sessionId) {
    sessionId = crypto.randomUUID();
    params.set("session_id", sessionId);
    window.history.replaceState({}, "", `${window.location.pathname}?${params}`);
  }
  return sessionId;
}

// Toast Helpers
const showPopup = () => {
  document.getElementById("popup").classList.remove("hidden");
  setTimeout(() => document.getElementById("popup").classList.add("hidden"), 3000);
}

const showErrorPopup = msg => {
  document.getElementById("error-message").textContent = msg;
  document.getElementById("error-popup").classList.remove("hidden");
  setTimeout(() => document.getElementById("error-popup").classList.add("hidden"), 4000);
}

const showLoading = (txt = "Processing...") => {
  const loadingEl = document.getElementById("loading");
  loadingEl.querySelector('span').textContent = txt;
  loadingEl.classList.remove("hidden");
  loadingEl.querySelector('svg').classList.add('animate-spin');
};

const hideLoading = () => {
  document.getElementById("loading").classList.add("hidden");
  document.getElementById("loading").querySelector('svg').classList.remove('animate-spin');
};

let mediaRecorder, echoChunks = [];
let isRecording = false;
const recordBtn = document.getElementById('record-button');
const recordIcon = document.getElementById('record-icon');
const stopIcon = document.getElementById('stop-icon');
const recordText = document.getElementById('record-text');
const echoPlayer = document.getElementById('echo-player');
const statusText = document.getElementById('recording-status');
const playbackPlaceholder = document.getElementById('playback-placeholder');
const transcriptionOutput = document.getElementById('transcription');
const murfPlayer = document.getElementById('murf-player');
const murfPlaceholder = document.getElementById('murf-placeholder');
const chatHistory = document.getElementById('chat-history');
const autoRecordingStatus = document.getElementById('auto-recording-status');
const manualAutoRestartBtn = document.getElementById('manual-auto-restart');
const testAutoRestartBtn = document.getElementById('test-auto-restart');

// Update status indicator
const updateStatus = (status) => {
  statusText.className = `status-indicator mb-6 text-sm text-cursor-gray status-${status.toLowerCase()}`;
  statusText.textContent = status === 'ready' ? 'Ready to record' :
    status === 'recording' ? 'Recording...' : 'Processing...';
};

// Update record button state
const updateRecordButton = (state) => {
  recordBtn.className = recordBtn.className.replace(/record-button-\w+/g, '');
  recordBtn.classList.add(`record-button-${state}`);
  
  if (state === 'recording') {
    recordIcon.classList.add('hidden');
    stopIcon.classList.remove('hidden');
    recordText.textContent = 'Stop';
    recordBtn.classList.add('recording-active', 'recording-glow');
  } else if (state === 'processing') {
    recordIcon.classList.remove('hidden');
    stopIcon.classList.add('hidden');
    recordText.textContent = 'Processing...';
    recordBtn.classList.remove('recording-active', 'recording-glow');
  } else {
    recordIcon.classList.remove('hidden');
    stopIcon.classList.add('hidden');
    recordText.textContent = 'Record';
    recordBtn.classList.remove('recording-active', 'recording-glow');
  }
};

// Auto-start recording after TTS response finishes
const autoStartRecording = async () => {
  console.log('Auto-starting recording...');
  
  // Show auto-recording status
  if (autoRecordingStatus) {
    autoRecordingStatus.classList.remove('hidden');
  }
  
  // Show countdown in status
  updateStatus('ready');
  updateRecordButton('ready');
  statusText.textContent = 'Auto-recording in 3...';
  
  setTimeout(() => {
    statusText.textContent = 'Auto-recording in 2...';
  }, 500);
  
  setTimeout(() => {
    statusText.textContent = 'Auto-recording in 1...';
  }, 1000);
  
  setTimeout(async () => {
    try {
      // Check if we can access the microphone
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // If we can get the stream, start recording
      if (recordBtn && !isRecording) {
        console.log('Starting auto-recording...');
        recordBtn.click();
      } else {
        console.log('Record button not available or already recording');
        // Try to start recording if not already recording
        if (recordBtn && !isRecording) {
          recordBtn.click();
        }
      }
    } catch (err) {
      console.error('Auto-start recording failed:', err);
      showErrorPopup('Auto-recording failed. Please click Record manually.');
      isRecording = false;
      updateRecordButton('ready');
      updateStatus('ready');
    }
  }, 1500); // Increased delay to ensure audio has finished
};

// Alternative auto-start function that directly starts recording
const forceStartRecording = async () => {
  console.log('Force starting recording...');
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    echoChunks = [];

    mediaRecorder.ondataavailable = e => { 
      if (e.data && e.data.size > 0) echoChunks.push(e.data); 
    };

    mediaRecorder.onstop = async () => {
      const blob = new Blob(echoChunks, { type: 'audio/webm' });
      const url = URL.createObjectURL(blob);

      echoPlayer.src = url;
      echoPlayer.classList.remove('hidden');
      playbackPlaceholder.classList.add('hidden');

      murfPlayer.classList.add('hidden');
      murfPlaceholder.classList.remove('hidden');

      await getTranscription(blob);
      await processAudioWithHistory(blob);
    };

    mediaRecorder.start();
    isRecording = true;
    updateRecordButton('recording');
    updateStatus('recording');
    
    if (autoRecordingStatus) {
      autoRecordingStatus.classList.add('hidden');
    }
    
    console.log('Force recording started successfully');
  } catch (err) {
    console.error('Force recording failed:', err);
    showErrorPopup('Recording failed. Please try again.');
    isRecording = false;
    updateRecordButton('ready');
  }
};

// Process audio with chat history
const processAudioWithHistory = async (audioBlob) => {
  const sessionId = getSessionId();
  
  try {
    const formData = new FormData();
    formData.append('file', audioBlob, 'recording.webm');
    formData.append('voice', 'default');

    showLoading("Processing with chat history...");
    updateStatus('processing');

    // Call the chat history endpoint
    const response = await fetch(`${BASE_URL}/agent/chat/${sessionId}`, {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const errorText = await response.text().catch(() => 'Chat history processing failed');
      console.error('agent/chat failed', response.status, errorText);
      showErrorPopup('Chat history processing failed — check server logs.');
      updateStatus('ready');
      return;
    }

    const responseBlob = await response.blob();
    const murfAudioUrl = URL.createObjectURL(responseBlob);
    
    murfPlayer.src = murfAudioUrl;
    murfPlayer.classList.remove('hidden');
    murfPlaceholder.classList.add('hidden');
    
    // Auto-play the response and restart recording when it finishes
    try {
      await murfPlayer.play();
      console.log('Audio playing, will auto-restart recording when finished');
      
      // Set up multiple event listeners to ensure we catch the end
      const handleAudioEnd = () => {
        console.log('Audio ended, triggering auto-restart');
        autoStartRecording();
      };
      
      murfPlayer.addEventListener('ended', handleAudioEnd, { once: true });
      murfPlayer.addEventListener('pause', handleAudioEnd, { once: true });
      
      // Also set a timeout as backup in case events don't fire
      const audioDuration = murfPlayer.duration || 5; // Default 5 seconds if duration unknown
      setTimeout(() => {
        console.log('Audio timeout backup, triggering auto-restart');
        autoStartRecording();
      }, (audioDuration * 1000) + 2000); // Audio duration + 2 seconds buffer
      
    } catch (e) {
      console.warn('Autoplay blocked, user will need to click play');
      // If autoplay is blocked, still set up the ended event
      const handleAudioEnd = () => {
        console.log('Audio ended (manual play), triggering auto-restart');
        autoStartRecording();
      };
      
      murfPlayer.addEventListener('ended', handleAudioEnd, { once: true });
      murfPlayer.addEventListener('pause', handleAudioEnd, { once: true });
    }

    showPopup();
    isRecording = false;
    updateRecordButton('ready');
    updateStatus('ready');
    
    // Update chat history display
    await updateChatHistory();

  } catch (err) {
    console.error(err);
    showErrorPopup("Error during chat history processing");
    isRecording = false;
    updateRecordButton('ready');
    updateStatus('ready');
  } finally {
    hideLoading();
  }
};

// Update chat history display
const updateChatHistory = async () => {
  const sessionId = getSessionId();
  try {
    const response = await fetch(`${BASE_URL}/agent/chat/${sessionId}/history`);
    if (response.ok) {
      const data = await response.json();
      if (data.messages && data.messages.length > 0) {
        const historyHtml = data.messages.map(msg => {
          const isUser = msg.role === 'user';
          const bgColor = isUser ? 'bg-blue-50' : 'bg-green-50';
          const borderColor = isUser ? 'border-blue-200' : 'border-green-200';
          const textColor = isUser ? 'text-blue-900' : 'text-green-900';
          const roleText = isUser ? 'You' : 'Assistant';
          
          return `
            <div class="mb-3 p-3 rounded-lg border ${bgColor} ${borderColor}">
              <div class="text-xs font-medium ${textColor} mb-1">${roleText}</div>
              <div class="text-sm ${textColor}">${msg.content}</div>
            </div>
          `;
        }).join('');
        chatHistory.innerHTML = historyHtml;
        chatHistory.scrollTop = chatHistory.scrollHeight; // Auto-scroll to bottom
      } else {
        chatHistory.innerHTML = '<div class="text-center text-cursor-gray">No messages yet. Start recording to begin the conversation.</div>';
      }
    }
  } catch (err) {
    console.error('Error fetching chat history:', err);
  }
};

// Get quick transcription for display
const getTranscription = async (audioBlob) => {
  try {
    const formData = new FormData();
    formData.append('file', audioBlob, 'recording.webm');

    const transRes = await fetch(`${BASE_URL}/transcribe/file`, { method: 'POST', body: formData });
    if (!transRes.ok) {
      const errText = await transRes.text().catch(() => 'Transcription error');
      console.warn('Transcribe failed:', transRes.status, errText);
      transcriptionOutput.textContent = "Transcription failed.";
    } else {
      const transData = await transRes.json();
      transcriptionOutput.textContent = transData.transcription || "No transcription returned.";
    }
  } catch (err) {
    console.error('Transcription error:', err);
    transcriptionOutput.textContent = "Transcription error.";
  }
};

// Setup event listeners
function setupEventListeners() {
  // Record button event listener
  recordBtn.addEventListener('click', async () => {
    if (isRecording) {
      // Stop recording
      if (mediaRecorder && mediaRecorder.state !== 'inactive') {
        mediaRecorder.stop();
        isRecording = false;
        updateRecordButton('processing');
        updateStatus('processing');
        try { 
          mediaRecorder.stream.getTracks().forEach(track => track.stop()); 
        } catch (e) {
          console.warn('Error stopping tracks:', e);
        }
      }
    } else {
      // Start recording
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        echoChunks = [];

        mediaRecorder.ondataavailable = e => { 
          if (e.data && e.data.size > 0) echoChunks.push(e.data); 
        };

        mediaRecorder.onstop = async () => {
          // build blob (we use webm because MediaRecorder default is often webm)
          const blob = new Blob(echoChunks, { type: 'audio/webm' });
          const url = URL.createObjectURL(blob);

          // show the original recording
          echoPlayer.src = url;
          echoPlayer.classList.remove('hidden');
          playbackPlaceholder.classList.add('hidden');

          // hide murf audio until ready
          murfPlayer.classList.add('hidden');
          murfPlaceholder.classList.remove('hidden');

          // Get transcription for display
          await getTranscription(blob);

          // Process with chat history
          await processAudioWithHistory(blob);
        };

        mediaRecorder.start();
        isRecording = true;
        updateRecordButton('recording');
        updateStatus('recording');
        
        // Hide auto-recording status when recording starts
        if (autoRecordingStatus) {
          autoRecordingStatus.classList.add('hidden');
        }
      } catch (err) {
        console.error(err);
        showErrorPopup("Microphone access denied");
        isRecording = false;
        updateRecordButton('ready');
      }
    }
  });

  // Manual auto-restart button event listener
  if (manualAutoRestartBtn) {
    manualAutoRestartBtn.addEventListener('click', () => {
      console.log('Manual auto-restart triggered');
      forceStartRecording();
    });
  }

  // Test auto-restart button event listener
  if (testAutoRestartBtn) {
    testAutoRestartBtn.addEventListener('click', () => {
      console.log('Test auto-restart triggered');
      autoStartRecording();
    });
  }
}

// Initialize application
function initializeApp() {
  const sessionId = getSessionId();
  const sessionDisplay = document.getElementById('session-display');
  if (sessionDisplay) {
    sessionDisplay.textContent = sessionId.substring(0, 8) + '...';
    sessionDisplay.title = sessionId; // Full ID on hover
  }
  console.log('Session ID initialized:', sessionId);
  
  // Initialize record button state
  updateRecordButton('ready');
  
  // Load initial chat history
  updateChatHistory();
  
  // Show auto-recording status on first load
  if (autoRecordingStatus) {
    autoRecordingStatus.classList.remove('hidden');
  }
  
  // Setup all event listeners
  setupEventListeners();
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initializeApp);
