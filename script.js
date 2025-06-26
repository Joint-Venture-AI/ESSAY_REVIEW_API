// Global variables
let currentEssayText = ""
let originalEssayText = ""
const trackChanges = []
let changeCounter = 0

// Initialize the application
document.addEventListener("DOMContentLoaded", () => {
  initializeEventListeners()
  setupDragAndDrop()
})

function initializeEventListeners() {
  // File input change
  document.getElementById("essayFile").addEventListener("change", handleFileSelect)

  // Essay type change
  document.getElementById("essayTypeSelect").addEventListener("change", function () {
    const changeBtn = document.getElementById("changeTypeBtn")
    changeBtn.disabled = !this.value
  })
}

function setupDragAndDrop() {
  const uploadArea = document.getElementById("uploadArea")

  uploadArea.addEventListener("dragover", (e) => {
    e.preventDefault()
    uploadArea.classList.add("dragover")
  })

  uploadArea.addEventListener("dragleave", (e) => {
    e.preventDefault()
    uploadArea.classList.remove("dragover")
  })

  uploadArea.addEventListener("drop", (e) => {
    e.preventDefault()
    uploadArea.classList.remove("dragover")

    const files = e.dataTransfer.files
    if (files.length > 0) {
      const file = files[0]
      if (file.name.toLowerCase().endsWith(".docx")) {
        document.getElementById("essayFile").files = files
        handleFileSelect({ target: { files: files } })
      } else {
        showToast("Please upload a .docx file", "error")
      }
    }
  })
}

function handleFileSelect(event) {
  const file = event.target.files[0]
  if (file) {
    document.getElementById("fileName").textContent = file.name
    document.getElementById("fileInfo").style.display = "flex"
    showToast("File selected successfully", "success")
  }
}

async function analyzeEssay() {
  const fileInput = document.getElementById("essayFile")
  const file = fileInput.files[0]

  if (!file) {
    showToast("Please select a file first", "error")
    return
  }

  showLoading(true)

  const formData = new FormData()
  formData.append("file", file)

  try {
    const response = await fetch("http://127.0.0.1:5000/analyze_essay", {
      method: "POST",
      body: formData,
    })

    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`)
    }

    const result = await response.json()
    if (result.error) {
      throw new Error(result.error)
    }

    displayAnalysisResults(result)
    showToast("Essay analyzed successfully!", "success")
  } catch (error) {
    console.error("Error analyzing essay:", error)
    showToast("Failed to analyze essay: " + error.message, "error")
  } finally {
    showLoading(false)
  }
}

function displayAnalysisResults(result) {
  // Store essay text
  currentEssayText = result.corrected_essay
  originalEssayText = result.corrected_essay

  // Update UI elements
  document.getElementById("essayType").textContent = result.essay_type || "Unknown"
  document.getElementById("essayScore").textContent = result.essay_score + "/100" || "N/A"

  // Display essay with highlighting
  displayEssayWithHighlights(result.corrected_essay)

  // Display suggestions
  displaySuggestions(result.suggestions || [])

  // Show results section
  document.getElementById("resultsSection").style.display = "block"

  // Scroll to results
  document.getElementById("resultsSection").scrollIntoView({ behavior: "smooth" })
}

function displayEssayWithHighlights(text) {
  const editor = document.getElementById("essayEditor")

  // Process text to add interactive highlights
  let processedText = text
    .replace(
      /<del>(.*?)<\/del>/g,
      "<span class=\"deletion\" onclick=\"acceptChange('deletion', '$1', this)\">$1</span>",
    )
    .replace(
      /<ins>(.*?)<\/ins>/g,
      "<span class=\"addition\" onclick=\"acceptChange('addition', '$1', this)\">$1</span>",
    )

  // Convert line breaks to paragraphs
  processedText = processedText
    .split("\n\n")
    .map((paragraph) => (paragraph.trim() ? `<p>${paragraph.replace(/\n/g, "<br>")}</p>` : ""))
    .join("")

  editor.innerHTML = processedText
}

function acceptChange(type, text, element) {
  const changeId = "change_" + ++changeCounter
  const timestamp = new Date()

  // Create change record
  const change = {
    id: changeId,
    type: type,
    text: text,
    timestamp: timestamp,
    accepted: true,
  }

  trackChanges.push(change)

  // Update the text
  if (type === "addition") {
    // Keep the text, remove highlighting
    element.outerHTML = text
    currentEssayText = currentEssayText.replace(`<ins>${text}</ins>`, text)
  } else if (type === "deletion") {
    // Remove the text
    element.remove()
    currentEssayText = currentEssayText.replace(`<del>${text}</del>`, "")
  }

  // Update track changes display
  updateTrackChangesDisplay()

  showToast(`${type === "addition" ? "Addition" : "Deletion"} accepted`, "success")
}

function updateTrackChangesDisplay() {
  const trackChangesList = document.getElementById("trackChangesList")
  const changesCount = document.getElementById("changesCount")

  if (trackChanges.length === 0) {
    trackChangesList.innerHTML = `
            <div class="no-changes">
                <i class="fas fa-clipboard-list"></i>
                <p>No changes yet</p>
                <small>Accept suggestions to see changes here</small>
            </div>
        `
    changesCount.textContent = "0 changes"
    return
  }

  changesCount.textContent = `${trackChanges.length} change${trackChanges.length !== 1 ? "s" : ""}`

  trackChangesList.innerHTML = trackChanges
    .map(
      (change) => `
        <div class="change-item ${change.type} ${change.accepted ? "accepted" : ""}">
            <div class="change-header">
                <span class="change-type ${change.type}">${change.type}</span>
                <span class="change-time">${formatTime(change.timestamp)}</span>
            </div>
            <div class="change-text">"${change.text}"</div>
            ${change.accepted ? '<div class="change-status">✓ Accepted</div>' : ""}
        </div>
    `,
    )
    .join("")
}

function displaySuggestions(suggestions) {
  const suggestionsList = document.getElementById("suggestionsList")

  if (!suggestions || suggestions.length === 0) {
    suggestionsList.innerHTML = '<p class="no-suggestions">No additional suggestions available.</p>'
    return
  }

  suggestionsList.innerHTML = suggestions
    .map(
      (suggestion) => `
        <div class="suggestion-item">
            <i class="fas fa-lightbulb"></i>
            ${suggestion}
        </div>
    `,
    )
    .join("")
}

async function changeEssayType() {
  const targetType = document.getElementById("essayTypeSelect").value
  if (!targetType || !currentEssayText) {
    showToast("Please select an essay type", "warning")
    return
  }

  const changeBtn = document.getElementById("changeTypeBtn")
  const originalText = changeBtn.innerHTML
  changeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Converting...'
  changeBtn.disabled = true

  try {
    const response = await fetch("http://127.0.0.1:5000/change_essay_type", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        essay_text: currentEssayText,
        target_essay_type: targetType,
      }),
    })

    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`)
    }

    const result = await response.json()
    if (result.error) {
      throw new Error(result.error)
    }

    // Update display with new results
    displayAnalysisResults(result)
    showToast(`Essay converted to ${targetType}`, "success")
  } catch (error) {
    console.error("Error changing essay type:", error)
    showToast("Failed to change essay type: " + error.message, "error")
  } finally {
    changeBtn.innerHTML = originalText
    changeBtn.disabled = false
  }
}

async function downloadEssay() {
  if (!currentEssayText) {
    showToast("No essay to download", "warning")
    return
  }

  try {
    const response = await fetch("http://127.0.0.1:5000/download_revision", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        final_text: currentEssayText,
        title: "Revised_Essay",
      }),
    })

    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`)
    }

    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "Revised_Essay_final.docx"
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)

    showToast("Essay downloaded successfully!", "success")
  } catch (error) {
    console.error("Error downloading essay:", error)
    showToast("Failed to download essay: " + error.message, "error")
  }
}

async function compareEssays() {
  const file1Input = document.getElementById("essay1")
  const file2Input = document.getElementById("essay2")
  const file1 = file1Input.files[0]
  const file2 = file2Input.files[0]

  if (!file1 || !file2) {
    showToast("Please select both essays to compare", "warning")
    return
  }

  const formData = new FormData()
  formData.append("essay1", file1)
  formData.append("essay2", file2)

  try {
    const response = await fetch("http://127.0.0.1:5000/compare_essays", {
      method: "POST",
      body: formData,
    })

    if (!response.ok) {
      throw new Error(`HTTP error! Status: ${response.status}`)
    }

    const result = await response.json()
    if (result.error) {
      throw new Error(result.error)
    }

    displayComparisonResults(result)
    showToast("Essays compared successfully!", "success")
  } catch (error) {
    console.error("Error comparing essays:", error)
    showToast("Failed to compare essays: " + error.message, "error")
  }
}

function displayComparisonResults(result) {
  document.getElementById("draft1Analysis").textContent = result.draft1_analysis || "No analysis available"
  document.getElementById("draft2Analysis").textContent = result.draft2_analysis || "No analysis available"
  document.getElementById("keyDifferences").textContent = result.key_differences || "No differences found"

  document.getElementById("compareResults").style.display = "block"
}

// Utility functions
function showLoading(show) {
  document.getElementById("loading").style.display = show ? "block" : "none"
}

function showToast(message, type = "success") {
  const toastContainer = document.getElementById("toastContainer")
  const toast = document.createElement("div")
  toast.className = `toast ${type}`
  toast.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <i class="fas fa-${type === "success" ? "check-circle" : type === "error" ? "exclamation-circle" : "exclamation-triangle"}"></i>
            <span>${message}</span>
        </div>
    `

  toastContainer.appendChild(toast)

  setTimeout(() => {
    toast.remove()
  }, 5000)
}

function formatTime(date) {
  return date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  })
}

// Helper function to clean HTML tags from text
function stripHtmlTags(html) {
  const tmp = document.createElement("div")
  tmp.innerHTML = html
  return tmp.textContent || tmp.innerText || ""
}
