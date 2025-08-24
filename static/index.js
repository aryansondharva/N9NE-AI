// Popup functionality
function showPopup() {
  const popup = document.getElementById("popup");
  popup.classList.remove("hidden");
  setTimeout(() => popup.classList.add("hidden"), 1000);
}

// Handle explore button click
function handleExploreClick() {
  showPopup();
  setTimeout(() => {
    window.location.href = '/voice-agent';
  }, 1000);
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  // Set up event listener for launch button
  const launchBtn = document.getElementById('launch-btn');
  if (launchBtn) {
    launchBtn.addEventListener('click', handleExploreClick);
  }
  
  // Also make function globally available as backup
  window.handleExploreClick = handleExploreClick;
});
