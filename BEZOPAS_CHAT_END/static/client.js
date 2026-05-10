const socket = io();

// ========== КРИПТОГРАФИЯ ==========
function arrayBufferToBase64(buffer) { return btoa(String.fromCharCode(...new Uint8Array(buffer))); }
function base64ToArrayBuffer(base64) { const binary = atob(base64); const bytes = new Uint8Array(binary.length); for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i); return bytes.buffer; }
async function deriveKey(password) {
    const enc = new TextEncoder();
    const keyMaterial = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveKey"]);
    return await crypto.subtle.deriveKey({ name: "PBKDF2", salt: enc.encode("bezopasnichat-salt"), iterations: 100000, hash: "SHA-256" }, keyMaterial, { name: "AES-GCM", length: 256 }, false, ["wrapKey", "unwrapKey", "encrypt", "decrypt"]);
}
async function generateRSAKeyPair() {
    return await crypto.subtle.generateKey({ name: "RSA-OAEP", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["wrapKey", "unwrapKey", "encrypt", "decrypt"]);
}
async function wrapPrivateKey(privateKey, wrappingKey) { return await crypto.subtle.wrapKey("pkcs8", privateKey, wrappingKey, { name: "AES-GCM", iv: new Uint8Array(12) }); }
async function unwrapPrivateKey(wrappedKey, wrappingKey) { return await crypto.subtle.unwrapKey("pkcs8", wrappedKey, wrappingKey, { name: "AES-GCM", iv: new Uint8Array(12) }, { name: "RSA-OAEP", hash: "SHA-256" }, false, ["decrypt", "unwrapKey"]); }
async function exportPublicKey(key) { const exported = await crypto.subtle.exportKey("spki", key); const body = arrayBufferToBase64(exported); return `-----BEGIN PUBLIC KEY-----\n${body}\n-----END PUBLIC KEY-----`; }
async function importPublicKey(pem) { const pemContents = pem.replace(/-----[^-]+-----/g, "").replace(/\n/g, ""); const binaryDer = base64ToArrayBuffer(pemContents); return await crypto.subtle.importKey("spki", binaryDer, { name: "RSA-OAEP", hash: "SHA-256" }, false, ["encrypt", "wrapKey"]); }
async function encryptAESKeyWithRSA(aesKey, rsaPublicKeyCrypto) { const wrapped = await crypto.subtle.wrapKey("raw", aesKey, rsaPublicKeyCrypto, { name: "RSA-OAEP" }); return arrayBufferToBase64(wrapped); }
async function decryptAESKeyWithRSA(encryptedKeyBase64, rsaPrivateKeyCrypto) { const wrapped = base64ToArrayBuffer(encryptedKeyBase64); return await crypto.subtle.unwrapKey("raw", wrapped, rsaPrivateKeyCrypto, { name: "RSA-OAEP" }, { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"]); }
async function encryptMessageAES(plaintext, aesKey) { const iv = crypto.getRandomValues(new Uint8Array(12)); const encoded = new TextEncoder().encode(plaintext); const ciphertext = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, aesKey, encoded); const packed = new Uint8Array(iv.length + new Uint8Array(ciphertext).length); packed.set(iv); packed.set(new Uint8Array(ciphertext), iv.length); return arrayBufferToBase64(packed.buffer); }
async function decryptMessageAES(packedBase64, aesKey) { const packed = new Uint8Array(base64ToArrayBuffer(packedBase64)); const iv = packed.slice(0, 12); const ciphertext = packed.slice(12); const decrypted = await crypto.subtle.decrypt({ name: "AES-GCM", iv }, aesKey, ciphertext); return new TextDecoder().decode(decrypted); }

// ========== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ ==========
let currentUser = '', currentUserId = '', currentChannel = null, onlineUsers = [], isMuted = false, editingMessageId = null, isAdmin = false;
let channelKeys = {}, currentPrivateKey = null;

// ========== БАЗОВЫЕ UI ФУНКЦИИ ==========
function showError(msg) { const el = document.getElementById('error-message'); el.textContent = msg; setTimeout(() => el.textContent = '', 3000); }
function showSuccess(msg) { const el = document.getElementById('success-message'); el.textContent = msg; setTimeout(() => el.textContent = '', 3000); }
function escapeHtml(text) { const div = document.createElement('div'); div.textContent = text; return div.innerHTML; }
function scrollToBottom() { const container = document.getElementById('messages-container'); container.scrollTop = container.scrollHeight; }

function showSystemMessage(text) {
    const container = document.getElementById('messages-container');
    const placeholder = container.querySelector('div[style*="text-align: center"]');
    if (placeholder) placeholder.remove();
    const div = document.createElement('div'); div.className = 'message system';
    const time = new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    div.innerHTML = `<div class="message-header"><span class="message-username">SYSTEM</span><span class="message-time">${time}</span></div><div class="message-text">${escapeHtml(text)}</div>`;
    container.appendChild(div); scrollToBottom();
}

function addMessageToChat(data) {
    const container = document.getElementById('messages-container');
    const placeholder = container.querySelector('div[style*="text-align: center"]');
    if (placeholder) placeholder.remove();
    const div = document.createElement('div');
    div.className = `message ${data.type === 'system' ? 'system' : data.is_private ? 'private' : data.is_group ? 'group' : ''}`;
    div.dataset.messageId = data.id;
    const time = new Date(data.timestamp).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
    const displayName = data.username === currentUser ? 'Вы' : data.username;
    const isOwnMessage = data.username === currentUser;
    const canDelete = isOwnMessage || isAdmin;
    const editedBadge = data.edited ? '<span class="message-edited"> (ред.)</span>' : '';
    div.innerHTML = `
        <div class="message-header"><span class="message-username">${escapeHtml(displayName)}</span><span class="message-time">${time}</span></div>
        <div class="message-text">${escapeHtml(data.message)}${editedBadge}</div>
        ${canDelete && data.type !== 'system' ? `
            <div class="message-actions">
                ${isOwnMessage ? `<button class="message-btn" onclick="editMessage(${data.id})"><i class="fas fa-edit"></i></button>` : ''}
                <button class="message-btn delete" onclick="deleteMessage(${data.id})"><i class="fas fa-trash"></i></button>
            </div>` : ''}
    `;
    container.appendChild(div); scrollToBottom();
}

function updateOnlineUsers() {
    const container = document.getElementById('online-users');
    const countEl = document.getElementById('online-count');
    container.innerHTML = '';
    countEl.textContent = onlineUsers.length;
    onlineUsers.forEach(user => {
        const div = document.createElement('div');
        div.className = 'user-item';
        const isCurrent = user.user_id === currentUserId;
        div.innerHTML = `
            <div>
                <div class="user-status online"></div>
                <span>${escapeHtml(user.username)}${isCurrent ? ' (Вы)' : ''}</span>
            </div>
            <div class="user-id-badge">${user.user_id}</div>
        `;
        container.appendChild(div);
    });
}

// ========== КАНАЛЫ ==========
function loadChannels() {
    const publicContainer = document.getElementById('public-channels');
    publicContainer.innerHTML = `
        <div class="channel active" onclick="joinChannel('general', '📝 Общий чат', 'public')"><div><span class="channel-icon">#</span><span>Общий чат</span></div></div>
        <div class="channel" onclick="joinChannel('games', '🎮 Игры', 'public')"><div><span class="channel-icon">#</span><span>Игры</span></div></div>
        <div class="channel" onclick="joinChannel('music', '🎵 Музыка', 'public')"><div><span class="channel-icon">#</span><span>Музыка</span></div></div>
        <div class="channel" onclick="joinChannel('memes', '😂 Мемы', 'public')"><div><span class="channel-icon">#</span><span>Мемы</span></div></div>`;
}

function joinChannel(channelId, channelName, channelType) {
    currentChannel = { id: channelId, name: channelName, type: channelType };
    document.querySelectorAll('.channel').forEach(ch => ch.classList.remove('active'));
    const active = Array.from(document.querySelectorAll('.channel')).find(ch => {
        const text = ch.textContent;
        if (channelType === 'private') return text.includes(channelName.replace('🔒 ', ''));
        if (channelType === 'group') return text.includes(channelName.replace('👥 ', ''));
        return text.includes(channelName);
    });
    if (active) active.classList.add('active');
    document.getElementById('current-channel').textContent = channelName;
    let info = ''; if (channelType === 'private') info = 'Приватный чат'; else if (channelType === 'group') info = 'Групповой чат'; else info = 'Публичный канал';
    document.getElementById('channel-info').textContent = info;
    document.getElementById('clear-history-btn').style.display = 'block';
    document.getElementById('message-input').disabled = isMuted;
    document.getElementById('send-btn').disabled = isMuted;
    document.getElementById('message-input').placeholder = isMuted ? 'Вы заглушены!' : 'Напишите сообщение...';
    socket.emit('get_channel_key', { channel_id: channelId, channel_type: channelType });
    socket.emit('join_channel', { channel_id: channelId, channel_type: channelType });
}

async function sendMessage() {
    const input = document.getElementById('message-input');
    const text = input.value.trim();
    if (!text || !currentChannel || isMuted) return;
    const aesKey = channelKeys[currentChannel.id];
    if (!aesKey) { alert('Ключ канала ещё не получен'); return; }
    const encrypted = await encryptMessageAES(text, aesKey);
    socket.emit('send_message', { channel: currentChannel.id, message: encrypted, channel_type: currentChannel.type });
    input.value = ''; input.style.height = 'auto';
}

function handleKeyDown(event) { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendMessage(); } }

// ========== СОБЫТИЯ СЕРВЕРА ==========
function setupSocketListeners() {
    socket.on('auth_success', async (data) => {
        currentUser = data.username; currentUserId = data.user_id; isMuted = data.is_muted || false; isAdmin = data.is_admin || false;
        const password = sessionStorage.getItem('password');
        const wrappingKey = await deriveKey(password);
        const wrappedBuf = base64ToArrayBuffer(data.encrypted_private_key);
        currentPrivateKey = await unwrapPrivateKey(wrappedBuf, wrappingKey);
        document.getElementById('current-user-display').textContent = `Вы: ${currentUser}`;
        document.getElementById('current-user-id').textContent = currentUserId;
        document.getElementById('login-screen').classList.add('hidden');
        document.getElementById('main-interface').classList.remove('hidden');
        loadChannels(); socket.emit('get_private_chats'); socket.emit('get_groups');
        joinChannel('general', '📝 Общий чат', 'public');
        showSystemMessage(`Добро пожаловать, ${currentUser}!`);
    });

    socket.on('auth_error', (data) => showError(data.message));
    socket.on('register_success', (data) => {
        showSuccess('Регистрация успешна! Теперь войдите.');
        document.getElementById('username-input').value = '';
        document.getElementById('password-input').value = '';
    });
    socket.on('register_error', (data) => showError(data.message));

    socket.on('new_message', async (msg) => {
        if (!currentChannel || msg.channel !== currentChannel.id) return;
        if (msg.type === 'system' || msg.encrypted === false) {
            addMessageToChat(msg);
        } else {
            const aesKey = channelKeys[currentChannel.id];
            if (aesKey) {
                const decrypted = await decryptMessageAES(msg.message, aesKey);
                addMessageToChat({ ...msg, message: decrypted });
            }
        }
    });

    socket.on('chat_history', (data) => {
        const container = document.getElementById('messages-container'); container.innerHTML = '';
        if (data.messages.length === 0) {
            container.innerHTML = '<div style="text-align: center; color: #999; padding: 40px;"><i class="fas fa-comment-dots" style="font-size: 48px;"></i><h3>Нет сообщений</h3><p>Будьте первым!</p></div>';
        } else {
            data.messages.forEach(msg => {
                if (msg.encrypted && channelKeys[currentChannel.id]) {
                    decryptMessageAES(msg.message, channelKeys[currentChannel.id]).then(dec => addMessageToChat({ ...msg, message: dec }));
                } else {
                    addMessageToChat(msg);
                }
            });
            scrollToBottom();
        }
    });

    socket.on('channel_key', async (data) => {
        try { channelKeys[data.channel_id] = await decryptAESKeyWithRSA(data.encrypted_key, currentPrivateKey); } catch(e) { console.error(e); }
    });

    socket.on('users_update', (data) => { onlineUsers = data.users; updateOnlineUsers(); });

    socket.on('user_joined', (data) => {
        if (data.username !== currentUser) showSystemMessage(`${data.username} подключился`);
    });
    socket.on('user_left', (data) => {
        if (data.username !== currentUser) showSystemMessage(`${data.username} отключился`);
    });

    socket.on('user_banned', (data) => {
        if (data.username === currentUser) { logout(); } else showSystemMessage(`${data.username} был забанен`);
    });
    socket.on('user_muted', (data) => {
        if (data.username === currentUser) {
            isMuted = true;
            showSystemMessage('Вас заглушили');
            document.getElementById('message-input').disabled = true;
            document.getElementById('send-btn').disabled = true;
        } else showSystemMessage(`${data.username} был заглушен`);
    });
    socket.on('user_kicked', (data) => {
        if (data.username === currentUser) { logout(); } else showSystemMessage(`${data.username} был кикнут`);
    });

    // Приватные чаты
    socket.on('private_chat_created', (data) => {
        hideCreateChatModal();
        showSystemMessage(`Создан приватный чат с ${data.other_user}`);
        socket.emit('get_private_chats');
        joinChannel(data.chat_id, `🔒 ${data.other_user}`, 'private');
    });
    socket.on('private_chat_error', (data) => showError(data.message));
    socket.on('private_chats_list', (data) => {
        const container = document.getElementById('private-channels');
        container.innerHTML = '';
        if (data.chats.length === 0) {
            container.innerHTML = '<div style="color: #999; font-size: 12px; padding: 10px;">У вас нет приватных чатов</div>';
        } else {
            data.chats.forEach(chat => {
                const div = document.createElement('div');
                div.className = 'channel';
                div.innerHTML = `
                    <div onclick="joinChannel('${chat.id}', '🔒 ${escapeHtml(chat.name)}', 'private')" style="flex: 1; display: flex; align-items: center;">
                        <span class="channel-icon"><i class="fas fa-lock"></i></span>
                        <span>${escapeHtml(chat.name)}</span>
                    </div>
                    <div class="channel-actions">
                        <button class="channel-btn" onclick="leavePrivateChat('${chat.id}', event)"><i class="fas fa-sign-out-alt"></i></button>
                        ${chat.is_creator ? `<button class="channel-btn delete" onclick="deletePrivateChat('${chat.id}', event)"><i class="fas fa-trash"></i></button>` : ''}
                    </div>
                `;
                container.appendChild(div);
            });
        }
    });
    socket.on('private_chat_deleted', (data) => {
        showSystemMessage('Приватный чат был удален');
        socket.emit('get_private_chats');
        if (currentChannel && currentChannel.id === data.chat_id) joinChannel('general', '📝 Общий чат', 'public');
    });

    // Группы
    socket.on('group_created', (data) => {
        hideCreateGroupModal();
        showSystemMessage(`Создана группа "${data.group_name}"`);
        socket.emit('get_groups');
        joinChannel(data.chat_id, `👥 ${data.group_name}`, 'group');
    });
    socket.on('group_error', (data) => showError(data.message));
    socket.on('groups_list', (data) => {
        const container = document.getElementById('group-channels');
        container.innerHTML = '';
        if (data.groups.length === 0) {
            container.innerHTML = '<div style="color: #999; font-size: 12px; padding: 10px;">У вас нет групп</div>';
        } else {
            data.groups.forEach(group => {
                const div = document.createElement('div');
                div.className = 'channel';
                div.innerHTML = `
                    <div onclick="joinChannel('${group.id}', '👥 ${escapeHtml(group.name)}', 'group')" style="flex: 1; display: flex; align-items: center;">
                        <span class="channel-icon"><i class="fas fa-users"></i></span>
                        <span>${escapeHtml(group.name)}</span>
                    </div>
                    <div class="channel-actions">
                        <button class="channel-btn" onclick="leaveGroup('${group.id}', event)"><i class="fas fa-sign-out-alt"></i></button>
                        ${group.is_creator ? `<button class="channel-btn delete" onclick="deleteGroup('${group.id}', event)"><i class="fas fa-trash"></i></button>` : ''}
                    </div>
                `;
                container.appendChild(div);
            });
        }
    });

    // Сообщения
    socket.on('message_deleted', (data) => {
        if (currentChannel && currentChannel.id === data.channel) {
            const el = document.querySelector(`[data-message-id="${data.message_id}"]`);
            if (el) el.remove();
        }
    });
    socket.on('message_edited', (data) => {
        if (currentChannel && currentChannel.id === data.channel) {
            const el = document.querySelector(`[data-message-id="${data.message_id}"]`);
            if (el) {
                const textEl = el.querySelector('.message-text');
                if (textEl) textEl.innerHTML = escapeHtml(data.message) + '<span class="message-edited"> (ред.)</span>';
            }
        }
    });
    socket.on('history_cleared', (data) => {
        if (currentChannel && currentChannel.id === data.channel) {
            document.getElementById('messages-container').innerHTML = `
                <div style="text-align: center; color: #999; padding: 40px;">
                    <i class="fas fa-comment-dots" style="font-size: 48px;"></i>
                    <h3>История чата очищена</h3>
                    <p>Начните общение заново!</p>
                </div>`;
        }
    });
}
document.addEventListener('DOMContentLoaded', setupSocketListeners);

// ========== ФУНКЦИИ КНОПОК ==========
async function login() {
    const username = document.getElementById('username-input').value.trim();
    const password = document.getElementById('password-input').value;
    if (!username || !password) return showError('Заполните все поля');
    sessionStorage.setItem('password', password);
    socket.emit('login', { username, password });
}

async function register() {
    const username = document.getElementById('username-input').value.trim();
    const password = document.getElementById('password-input').value;
    if (!username || !password) return showError('Заполните все поля');
    if (username.length < 3) return showError('Минимум 3 символа');
    const wrappingKey = await deriveKey(password);
    const keyPair = await generateRSAKeyPair();
    const wrappedPriv = await wrapPrivateKey(keyPair.privateKey, wrappingKey);
    const publicKeyPem = await exportPublicKey(keyPair.publicKey);
    socket.emit('register', { username, password, public_key: publicKeyPem, encrypted_private_key: arrayBufferToBase64(wrappedPriv) });
}

function logout() {
    if (confirm('Выйти из аккаунта?')) { socket.disconnect(); window.location.reload(); }
}

// ========== МОДАЛЬНЫЕ ОКНА ==========
function showCreateChatModal() {
    document.getElementById('create-chat-modal').classList.remove('hidden');
    document.getElementById('invite-user-id').focus();
}
function hideCreateChatModal() {
    document.getElementById('create-chat-modal').classList.add('hidden');
    document.getElementById('invite-user-id').value = '';
}
function createPrivateChat() {
    const userId = document.getElementById('invite-user-id').value.trim();
    if (!userId) return showError('Введите ID пользователя');
    if (userId === currentUserId) return showError('Нельзя создать чат с самим собой');
    socket.emit('create_private_chat', { target_user_id: userId });
}

function showCreateGroupModal() {
    document.getElementById('create-group-modal').classList.remove('hidden');
    document.getElementById('group-name').focus();
}
function hideCreateGroupModal() {
    document.getElementById('create-group-modal').classList.add('hidden');
    document.getElementById('group-name').value = '';
    document.getElementById('group-members').value = '';
}
function createGroup() {
    const groupName = document.getElementById('group-name').value.trim();
    const membersText = document.getElementById('group-members').value.trim();
    if (!groupName) return showError('Введите название группы');
    if (!membersText) return showError('Введите ID участников');
    const members = membersText.split(',').map(id => id.trim()).filter(id => id);
    if (members.length === 0) return showError('Введите хотя бы одного участника');
    socket.emit('create_group', { group_name: groupName, members: members });
}

// ========== ВЫХОД И УДАЛЕНИЕ ЧАТОВ ==========
function leavePrivateChat(chatId, event) {
    event.stopPropagation();
    if (confirm('Вы уверены, что хотите выйти из этого чата?')) socket.emit('leave_private_chat', { chat_id: chatId });
}
function deletePrivateChat(chatId, event) {
    event.stopPropagation();
    if (confirm('Вы уверены, что хотите удалить этот чат? Это действие удалит чат для всех участников.')) socket.emit('delete_private_chat', { chat_id: chatId });
}
function leaveGroup(chatId, event) {
    event.stopPropagation();
    if (confirm('Вы уверены, что хотите выйти из этой группы?')) socket.emit('leave_group', { chat_id: chatId });
}
function deleteGroup(chatId, event) {
    event.stopPropagation();
    if (confirm('Вы уверены, что хотите удалить эту группу? Это действие удалит группу для всех участников.')) socket.emit('delete_group', { chat_id: chatId });
}

// ========== РЕДАКТИРОВАНИЕ И УДАЛЕНИЕ СООБЩЕНИЙ ==========
function editMessage(messageId) {
    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
    if (messageElement) {
        const textElement = messageElement.querySelector('.message-text');
        let text = textElement.textContent.replace(' (ред.)', '');
        document.getElementById('edit-message-text').value = text;
        editingMessageId = messageId;
        document.getElementById('edit-message-modal').classList.remove('hidden');
    }
}
function saveEditedMessage() {
    const newText = document.getElementById('edit-message-text').value.trim();
    if (!newText) return showError('Введите текст сообщения');
    if (editingMessageId) {
        socket.emit('edit_message', { message_id: editingMessageId, channel: currentChannel.id, message: newText });
        hideEditModal();
    }
}
function hideEditModal() {
    document.getElementById('edit-message-modal').classList.add('hidden');
    editingMessageId = null;
}
function deleteMessage(messageId) {
    if (confirm('Удалить это сообщение?')) socket.emit('delete_message', { message_id: messageId, channel: currentChannel.id });
}

// ========== ОЧИСТКА ИСТОРИИ ==========
function clearHistory() {
    if (confirm('Очистить всю историю этого чата? Это действие нельзя отменить.')) {
        socket.emit('clear_history', { channel: currentChannel.id, channel_type: currentChannel.type });
    }
}

