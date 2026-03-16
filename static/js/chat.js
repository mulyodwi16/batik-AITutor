// Chat functionality
const chatContainer = document.getElementById('chatContainer');
const messageInput = document.getElementById('messageInput');
const chatForm = document.getElementById('chatForm');
const suggestionsContainer = document.getElementById('suggestionsContainer');

// Send message on form submit
chatForm.addEventListener('submit', handleSubmit);

// Enter key to send
messageInput.addEventListener('keypress', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit(e);
    }
});

function handleSubmit(event) {
    event.preventDefault();
    const message = messageInput.value.trim();

    if (!message) return;

    // Add user message to chat
    addMessage(message, 'user');
    messageInput.value = '';

    // Hide suggestions
    suggestionsContainer.classList.add('hidden');

    // Send to backend
    sendMessageToBackend(message);
}

function addMessage(text, sender, metadata = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${sender}-message`;

    if (sender === 'bot') {
        let metadataHTML = '';
        if (metadata && metadata.has_context) {
            const score = (metadata.top_score * 100).toFixed(1);
            metadataHTML = `
                <div class="message-metadata">
                    <small>📊 Confidence: ${score}% | ${metadata.retrieved_chunks.length} sources</small>
                </div>
            `;
        }

        messageDiv.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-content">
                <p>${escapeHtml(text)}</p>
                ${metadataHTML}
            </div>
        `;
    } else {
        messageDiv.innerHTML = `
            <div class="message-content">
                <p>${escapeHtml(text)}</p>
            </div>
            <div class="message-avatar">👤</div>
        `;
    }

    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function addLoadingMessage() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'chat-message bot-message';
    messageDiv.id = 'loading-message';
    messageDiv.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="loading-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;

    chatContainer.appendChild(messageDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function removeLoadingMessage() {
    const loadingMsg = document.getElementById('loading-message');
    if (loadingMsg) {
        loadingMsg.remove();
    }
}

async function sendMessageToBackend(message) {
    addLoadingMessage();

    try {
        // Use AbortController for timeout (LLM generation can be slow, need 180s)
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 180000); // 180 second timeout

        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: message }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }

        const data = await response.json();
        removeLoadingMessage();

        // Pass metadata untuk ditampilkan
        const metadata = data.metadata || {};
        addMessage(data.reply, 'bot', metadata);

        // Log metadata ke console untuk debugging
        if (metadata.has_context) {
            console.log('RAG Retrieval:', {
                chunks: metadata.retrieved_chunks,
                scores: metadata.retrieval_scores,
                model: metadata.model_used
            });
        }

    } catch (error) {
        removeLoadingMessage();
        if (error.name === 'AbortError') {
            addMessage('Tunggu terlalu lama (timeout). Coba pertanyaan yang lebih pendek atau ulangi lagi.', 'bot');
        } else {
            addMessage('Maaf, terjadi kesalahan saat menghubungi server. Silakan coba lagi.', 'bot');
        }
        console.error('Error:', error);
    }
}

function askQuestion(element) {
    const question = element.textContent;
    messageInput.value = question;
    messageInput.focus();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Focus input on load
window.addEventListener('load', function () {
    messageInput.focus();
});

// Load suggestions on startup
document.addEventListener('DOMContentLoaded', function () {
    fetch('/api/suggestions')
        .then(r => r.json())
        .then(data => {
            console.log('Suggestions loaded:', data);
        })
        .catch(error => console.error('Error loading suggestions:', error));
});
