from flask_socketio import emit, join_room, leave_room
from flask import request
from datetime import datetime, timedelta
import hashlib, secrets, random, string
from . import socketio
from .crypto_utils import generate_aes_key, encrypt_aes_key_with_rsa

# ---------- БАЗЫ ДАННЫХ ----------
users_db = {}
online_users = {}
messages = []
private_chats = {}
group_chats = {}

channel_master_keys = {}
user_channel_keys = {}

CHANNELS = ["general", "games", "music", "memes"]
CHANNEL_NAMES = {
    "general": "📝 Общий чат",
    "games": "🎮 Игры",
    "music": "🎵 Музыка",
    "memes": "😂 Мемы"
}

def generate_user_id():
    while True:
        uid = ''.join(random.choices(string.digits, k=6))
        if not any(u['user_id'] == uid for u in users_db.values()):
            return uid

def generate_chat_id():
    while True:
        cid = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        if cid not in private_chats and cid not in group_chats:
            return cid

def hash_password(password):
    return hashlib.sha256((password + "messengerprosto").encode()).hexdigest()

def is_user_banned(username):
    return username in users_db and users_db[username].get('banned', False)

def is_user_muted(username):
    if username in users_db:
        muted_until = users_db[username].get('muted_until')
        if muted_until and datetime.now() < datetime.fromisoformat(muted_until):
            return True
    return False

def is_user_admin(username):
    return username in users_db and users_db[username].get('admin', False)

def get_user_by_id(user_id):
    for username, data in users_db.items():
        if data['user_id'] == user_id:
            return username, data
    return None, None

def get_next_message_id():
    return len(messages) + 1

def broadcast_system_message(message, channel='general'):
    msg = {
        'id': get_next_message_id(),
        'username': 'SYSTEM',
        'message': message,
        'timestamp': datetime.now().isoformat(),
        'type': 'system',
        'channel': channel,
        'encrypted': False
    }
    messages.append(msg)
    socketio.emit('new_message', msg)

def update_online_users():
    users = [{'username': d['username'], 'user_id': d['user_id']} for d in online_users.values()]
    socketio.emit('users_update', {'users': users})

# ======================== РЕГИСТРАЦИЯ И ВХОД ========================
@socketio.on('register')
def handle_register(data):
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    public_key = data.get('public_key')
    encrypted_private_key = data.get('encrypted_private_key')
    if not all([username, password, public_key, encrypted_private_key]):
        emit('register_error', {'message': 'Все поля обязательны'})
        return
    if len(username) < 3:
        emit('register_error', {'message': 'Имя должно быть не менее 3 символов'})
        return
    if username in users_db:
        emit('register_error', {'message': 'Пользователь уже существует'})
        return
    user_id = generate_user_id()
    users_db[username] = {
        'password_hash': hash_password(password),
        'user_id': user_id,
        'public_key': public_key,
        'encrypted_private_key': encrypted_private_key,
        'created_at': datetime.now().isoformat(),
        'banned': False,
        'muted_until': None,
        'admin': (username == 'admin')
    }
    emit('register_success', {'message': 'Регистрация успешна! Теперь войдите.'})

@socketio.on('login')
def handle_login(data):
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    if username not in users_db:
        emit('auth_error', {'message': 'Неверное имя или пароль'})
        return
    if hash_password(password) != users_db[username]['password_hash']:
        emit('auth_error', {'message': 'Неверное имя или пароль'})
        return
    if is_user_banned(username):
        emit('auth_error', {'message': 'Вы забанены'})
        return
    online_users[request.sid] = {
        'username': username,
        'user_id': users_db[username]['user_id']
    }
    emit('auth_success', {
        'username': username,
        'user_id': users_db[username]['user_id'],
        'encrypted_private_key': users_db[username]['encrypted_private_key'],
        'is_admin': is_user_admin(username),
        'is_muted': is_user_muted(username)
    })
    update_online_users()
    broadcast_system_message(f'👋 {username} присоединился к чату')

@socketio.on('disconnect')
def handle_disconnect():
    if request.sid in online_users:
        username = online_users[request.sid]['username']
        del online_users[request.sid]
        update_online_users()
        broadcast_system_message(f'{username} отключился')

# ======================== КЛЮЧИ КАНАЛОВ ========================
@socketio.on('get_channel_key')
def handle_get_channel_key(data):
    if request.sid not in online_users:
        return
    username = online_users[request.sid]['username']
    user_id = online_users[request.sid]['user_id']
    channel_id = data.get('channel_id')
    channel_type = data.get('channel_type', 'public')

    if channel_type == 'public':
        if channel_id not in channel_master_keys:
            channel_master_keys[channel_id] = generate_aes_key()
        if channel_id not in user_channel_keys:
            user_channel_keys[channel_id] = {}
        if user_id not in user_channel_keys[channel_id]:
            raw_key = channel_master_keys[channel_id]
            encrypted_key = encrypt_aes_key_with_rsa(raw_key, users_db[username]['public_key'])
            user_channel_keys[channel_id][user_id] = encrypted_key
        emit('channel_key', {
            'channel_id': channel_id,
            'encrypted_key': user_channel_keys[channel_id][user_id]
        })
    else:  # private или group
        chat = private_chats.get(channel_id) or group_chats.get(channel_id)
        if not chat or user_id not in chat['users']:
            emit('error', {'message': 'Нет доступа'})
            return
        if channel_id not in user_channel_keys or user_id not in user_channel_keys.get(channel_id, {}):
            emit('error', {'message': 'Ключ ещё не готов'})
            return
        emit('channel_key', {
            'channel_id': channel_id,
            'encrypted_key': user_channel_keys[channel_id][user_id]
        })

# ======================== СООБЩЕНИЯ ========================
@socketio.on('join_channel')
def handle_join_channel(data):
    if request.sid not in online_users:
        return
    channel_id = data.get('channel_id')
    channel_type = data.get('channel_type')
    if channel_type == 'public':
        channel_messages = [msg for msg in messages if msg.get('channel') == channel_id]
    else:
        channel_messages = [msg for msg in messages if msg.get('channel') == channel_id]
    emit('chat_history', {'messages': channel_messages[-50:]})

@socketio.on('send_message')
def handle_send_message(data):
    if request.sid not in online_users:
        return
    username = online_users[request.sid]['username']
    user_id = online_users[request.sid]['user_id']
    channel = data.get('channel')
    ciphertext = data.get('message')
    channel_type = data.get('channel_type', 'public')
    if is_user_muted(username):
        emit('error', {'message': 'Вы заглушены'})
        return
    if not ciphertext:
        return
    if channel_type == 'private':
        if channel not in private_chats or user_id not in private_chats[channel]['users']:
            return
    elif channel_type == 'group':
        if channel not in group_chats or user_id not in group_chats[channel]['users']:
            return
    msg = {
        'id': get_next_message_id(),
        'username': username,
        'message': ciphertext,
        'timestamp': datetime.now().isoformat(),
        'type': 'message',
        'channel': channel,
        'channel_type': channel_type,
        'encrypted': True
    }
    messages.append(msg)
    if channel_type == 'public':
        emit('new_message', msg, broadcast=True)
    else:
        chat = private_chats.get(channel) or group_chats.get(channel)
        if chat:
            for uid in chat['users']:
                for sid, odata in online_users.items():
                    if odata['user_id'] == uid:
                        emit('new_message', msg, room=sid)

# ---------- ПРИВАТНЫЕ ЧАТЫ ----------
@socketio.on('create_private_chat')
def handle_create_private_chat(data):
    if request.sid not in online_users:
        return
    username = online_users[request.sid]['username']
    user_id = online_users[request.sid]['user_id']
    target_id = data.get('target_user_id', '').strip()
    target_name, target_data = get_user_by_id(target_id)
    if not target_name:
        emit('private_chat_error', {'message': 'Пользователь с таким ID не найден'})
        return
    if target_id == user_id:
        emit('private_chat_error', {'message': 'Нельзя создать чат с самим собой'})
        return
    for cid, cdata in private_chats.items():
        if user_id in cdata['users'] and target_id in cdata['users']:
            emit('private_chat_error', {'message': 'Чат уже существует'})
            return
    chat_id = generate_chat_id()
    private_chats[chat_id] = {
        'name': target_name,
        'users': [user_id, target_id],
        'creator_id': user_id,
        'created_at': datetime.now().isoformat(),
        'type': 'private'
    }
    # Генерируем ключ чата
    raw_key = generate_aes_key()
    channel_master_keys[chat_id] = raw_key
    user_channel_keys[chat_id] = {}
    for uid in [user_id, target_id]:
        u_name, u_data = get_user_by_id(uid)
        if u_data:
            encrypted = encrypt_aes_key_with_rsa(raw_key, u_data['public_key'])
            user_channel_keys[chat_id][uid] = encrypted
    emit('private_chat_created', {'chat_id': chat_id, 'other_user': target_name})
    for sid, odata in online_users.items():
        if odata['user_id'] == target_id:
            emit('private_chat_created', {'chat_id': chat_id, 'other_user': username}, room=sid)
            break

@socketio.on('get_private_chats')
def handle_get_private_chats():
    if request.sid not in online_users:
        return
    user_id = online_users[request.sid]['user_id']
    result = []
    for cid, cdata in private_chats.items():
        if user_id in cdata['users']:
            other_id = cdata['users'][0] if cdata['users'][1] == user_id else cdata['users'][1]
            other_name, _ = get_user_by_id(other_id)
            result.append({
                'id': cid,
                'name': other_name or 'Неизвестный',
                'is_creator': (cdata['creator_id'] == user_id)
            })
    emit('private_chats_list', {'chats': result})

# ---------- ГРУППЫ ----------
@socketio.on('create_group')
def handle_create_group(data):
    if request.sid not in online_users:
        return
    username = online_users[request.sid]['username']
    user_id = online_users[request.sid]['user_id']
    group_name = data.get('group_name', '').strip()
    members = data.get('members', [])
    if not group_name:
        emit('group_error', {'message': 'Введите название группы'})
        return
    if len(members) == 0:
        emit('group_error', {'message': 'Добавьте хотя бы одного участника'})
        return
    valid_members = [user_id]
    for member_id in members:
        if member_id == user_id:
            continue
        target_name, target_data = get_user_by_id(member_id)
        if not target_name:
            emit('group_error', {'message': f'Пользователь с ID {member_id} не найден'})
            return
        valid_members.append(member_id)
    valid_members = list(set(valid_members))
    chat_id = generate_chat_id()
    group_chats[chat_id] = {
        'name': group_name,
        'users': valid_members,
        'creator_id': user_id,
        'created_at': datetime.now().isoformat(),
        'type': 'group'
    }
    raw_key = generate_aes_key()
    channel_master_keys[chat_id] = raw_key
    user_channel_keys[chat_id] = {}
    for uid in valid_members:
        u_name, u_data = get_user_by_id(uid)
        if u_data:
            encrypted = encrypt_aes_key_with_rsa(raw_key, u_data['public_key'])
            user_channel_keys[chat_id][uid] = encrypted
    emit('group_created', {'chat_id': chat_id, 'group_name': group_name})
    for uid in valid_members:
        if uid != user_id:
            for sid, odata in online_users.items():
                if odata['user_id'] == uid:
                    emit('group_created', {'chat_id': chat_id, 'group_name': group_name}, room=sid)
                    break

@socketio.on('get_groups')
def handle_get_groups():
    if request.sid not in online_users:
        return
    user_id = online_users[request.sid]['user_id']
    result = []
    for cid, cdata in group_chats.items():
        if user_id in cdata['users']:
            result.append({
                'id': cid,
                'name': cdata['name'],
                'is_creator': (cdata['creator_id'] == user_id)
            })
    emit('groups_list', {'groups': result})

# ---------- УДАЛЕНИЕ И РЕДАКТИРОВАНИЕ СООБЩЕНИЙ ----------
@socketio.on('delete_message')
def handle_delete_message(data):
    if request.sid not in online_users:
        return
    username = online_users[request.sid]['username']
    message_id = data.get('message_id')
    channel = data.get('channel')
    message_to_delete = None
    for msg in messages:
        if msg['id'] == message_id and msg['channel'] == channel:
            message_to_delete = msg
            break
    if not message_to_delete:
        emit('system_message', {'message': 'Сообщение не найдено'})
        return
    if message_to_delete['username'] != username and not is_user_admin(username):
        emit('system_message', {'message': 'Вы можете удалять только свои сообщения'})
        return
    messages.remove(message_to_delete)
    emit('message_deleted', {'message_id': message_id, 'channel': channel}, broadcast=True)

@socketio.on('edit_message')
def handle_edit_message(data):
    if request.sid not in online_users:
        return
    username = online_users[request.sid]['username']
    message_id = data.get('message_id')
    channel = data.get('channel')
    new_text = data.get('message', '').strip()
    if not new_text:
        emit('system_message', {'message': 'Сообщение не может быть пустым'})
        return
    message_to_edit = None
    for msg in messages:
        if msg['id'] == message_id and msg['channel'] == channel:
            message_to_edit = msg
            break
    if not message_to_edit:
        emit('system_message', {'message': 'Сообщение не найдено'})
        return
    if message_to_edit['username'] != username:
        emit('system_message', {'message': 'Вы можете редактировать только свои сообщения'})
        return
    message_to_edit['message'] = new_text
    message_to_edit['edited'] = True
    emit('message_edited', {'message_id': message_id, 'channel': channel, 'message': new_text}, broadcast=True)

@socketio.on('clear_history')
def handle_clear_history(data):
    if request.sid not in online_users:
        return
    username = online_users[request.sid]['username']
    user_id = online_users[request.sid]['user_id']
    channel = data.get('channel')
    channel_type = data.get('channel_type')
    if channel_type == 'public':
        if not is_user_admin(username):
            emit('system_message', {'message': 'Только администратор может очищать историю публичных чатов'})
            return
    elif channel_type == 'private':
        if channel not in private_chats or user_id not in private_chats[channel]['users']:
            emit('system_message', {'message': 'Нет доступа'})
            return
    elif channel_type == 'group':
        if channel not in group_chats or user_id not in group_chats[channel]['users']:
            emit('system_message', {'message': 'Нет доступа'})
            return
    global messages
    messages = [msg for msg in messages if msg.get('channel') != channel]
    emit('history_cleared', {'channel': channel}, broadcast=True)

# ---------- ВЫХОД ИЗ ЧАТОВ ----------
@socketio.on('leave_private_chat')
def handle_leave_private_chat(data):
    if request.sid not in online_users:
        return
    username = online_users[request.sid]['username']
    user_id = online_users[request.sid]['user_id']
    chat_id = data.get('chat_id')
    if chat_id not in private_chats:
        emit('system_message', {'message': 'Приватный чат не найден'})
        return
    chat_data = private_chats[chat_id]
    if user_id not in chat_data['users']:
        emit('system_message', {'message': 'Вы не участник'})
        return
    chat_data['users'].remove(user_id)
    if len(chat_data['users']) <= 1:
        # Удаляем чат
        for uid in chat_data['users']:
            for sid, odata in online_users.items():
                if odata['user_id'] == uid:
                    emit('private_chat_deleted', {'chat_id': chat_id}, room=sid)
        del private_chats[chat_id]
        global messages
        messages = [msg for msg in messages if msg.get('channel') != chat_id]
    else:
        for uid in chat_data['users']:
            for sid, odata in online_users.items():
                if odata['user_id'] == uid:
                    send_private_chats_to_user(sid)
    send_private_chats_to_user(request.sid)
    emit('system_message', {'message': 'Вы вышли из приватного чата'})

@socketio.on('delete_private_chat')
def handle_delete_private_chat(data):
    if request.sid not in online_users:
        return
    username = online_users[request.sid]['username']
    user_id = online_users[request.sid]['user_id']
    chat_id = data.get('chat_id')
    if chat_id not in private_chats:
        emit('system_message', {'message': 'Приватный чат не найден'})
        return
    if private_chats[chat_id]['creator_id'] != user_id:
        emit('system_message', {'message': 'Только создатель может удалить чат'})
        return
    for uid in private_chats[chat_id]['users']:
        for sid, odata in online_users.items():
            if odata['user_id'] == uid:
                emit('private_chat_deleted', {'chat_id': chat_id}, room=sid)
                send_private_chats_to_user(sid)
    del private_chats[chat_id]
    global messages
    messages = [msg for msg in messages if msg.get('channel') != chat_id]

@socketio.on('leave_group')
def handle_leave_group(data):
    if request.sid not in online_users:
        return
    user_id = online_users[request.sid]['user_id']
    chat_id = data.get('chat_id')
    if chat_id not in group_chats:
        emit('system_message', {'message': 'Группа не найдена'})
        return
    chat_data = group_chats[chat_id]
    if user_id not in chat_data['users']:
        emit('system_message', {'message': 'Вы не участник'})
        return
    if chat_data['creator_id'] == user_id:
        emit('system_message', {'message': 'Создатель не может выйти. Удалите группу.'})
        return
    chat_data['users'].remove(user_id)
    if len(chat_data['users']) <= 1:
        for uid in chat_data['users']:
            for sid, odata in online_users.items():
                if odata['user_id'] == uid:
                    emit('system_message', {'message': f'Группа "{chat_data["name"]}" удалена'}, room=sid)
        del group_chats[chat_id]
        global messages
        messages = [msg for msg in messages if msg.get('channel') != chat_id]
    else:
        for uid in chat_data['users']:
            for sid, odata in online_users.items():
                if odata['user_id'] == uid:
                    send_groups_to_user(sid)
    send_groups_to_user(request.sid)

@socketio.on('delete_group')
def handle_delete_group(data):
    if request.sid not in online_users:
        return
    user_id = online_users[request.sid]['user_id']
    chat_id = data.get('chat_id')
    if chat_id not in group_chats:
        emit('system_message', {'message': 'Группа не найдена'})
        return
    if group_chats[chat_id]['creator_id'] != user_id:
        emit('system_message', {'message': 'Только создатель может удалить группу'})
        return
    for uid in group_chats[chat_id]['users']:
        for sid, odata in online_users.items():
            if odata['user_id'] == uid:
                emit('system_message', {'message': f'Группа "{group_chats[chat_id]["name"]}" удалена создателем'}, room=sid)
                send_groups_to_user(sid)
    del group_chats[chat_id]
    global messages
    messages = [msg for msg in messages if msg.get('channel') != chat_id]

# ---------- ВСПОМОГАТЕЛЬНЫЕ РАССЫЛКИ ----------
def send_private_chats_to_user(sid):
    """Отправить список приватных чатов конкретному пользователю по sid"""
    if sid not in online_users:
        return
    user_id = online_users[sid]['user_id']
    result = []
    for cid, cdata in private_chats.items():
        if user_id in cdata['users'] and cdata['type'] == 'private':
            other_id = cdata['users'][0] if cdata['users'][1] == user_id else cdata['users'][1]
            other_name, _ = get_user_by_id(other_id)
            result.append({
                'id': cid,
                'name': other_name or 'Неизвестный',
                'is_creator': (cdata['creator_id'] == user_id)
            })
    emit('private_chats_list', {'chats': result}, room=sid)

def send_groups_to_user(sid):
    """Отправить список групп конкретному пользователю по sid"""
    if sid not in online_users:
        return
    user_id = online_users[sid]['user_id']
    result = []
    for cid, cdata in group_chats.items():
        if user_id in cdata['users'] and cdata['type'] == 'group':
            result.append({
                'id': cid,
                'name': cdata['name'],
                'is_creator': (cdata['creator_id'] == user_id)
            })
    emit('groups_list', {'groups': result}, room=sid)



# ---------- АДМИН-КОМАНДЫ ----------
def ban_user(username):
    if username in users_db:
        users_db[username]['banned'] = True
        for sid, data in list(online_users.items()):
            if data['username'] == username:
                socketio.emit('user_banned', {'username': username}, room=sid)
                socketio.server.disconnect(sid)
                del online_users[sid]
                break
        broadcast_system_message(f'🚫 Пользователь {username} забанен')
        update_online_users()

def unban_user(username):
    if username in users_db:
        users_db[username]['banned'] = False

def kick_user(username):
    for sid, data in list(online_users.items()):
        if data['username'] == username:
            socketio.emit('user_kicked', {'username': username}, room=sid)
            socketio.server.disconnect(sid)
            del online_users[sid]
            break
    broadcast_system_message(f'👢 Пользователь {username} кикнут')
    update_online_users()

def mute_user(username, minutes):
    if username in users_db:
        users_db[username]['muted_until'] = (datetime.now() + timedelta(minutes=minutes)).isoformat()
        for sid, data in online_users.items():
            if data['username'] == username:
                socketio.emit('user_muted', {'username': username}, room=sid)
                break
        broadcast_system_message(f'🔇 Пользователь {username} заглушен на {minutes} минут')

def unmute_user(username):
    if username in users_db:
        users_db[username]['muted_until'] = None

# Запуск админ-панели (как в оригинале)
def admin_commands():
    print("\n" + "="*50)
    print("АДМИН-ПАНЕЛЬ")
    print("="*50)
    print("Доступные команды: /list /online /ban <ник> /unban <ник> /kick <ник> /mute <ник> <мин> /unmute <ник> /broadcast <текст> /exit")
    while True:
        try:
            cmd = input("\nadmin> ").strip()
            if cmd == "/exit":
                break
            elif cmd == "/list":
                for u, d in users_db.items():
                    print(f"{u} (ID: {d['user_id']}) BAN:{d['banned']} MUTE:{d.get('muted_until','-')} ADMIN:{d.get('admin',False)}")
            elif cmd == "/online":
                for s, d in online_users.items():
                    print(f"{d['username']} (ID: {d['user_id']})")
            elif cmd.startswith("/ban "):
                ban_user(cmd.split(" ",1)[1])
            elif cmd.startswith("/unban "):
                unban_user(cmd.split(" ",1)[1])
            elif cmd.startswith("/kick "):
                kick_user(cmd.split(" ",1)[1])
            elif cmd.startswith("/mute "):
                parts = cmd.split()
                if len(parts) == 3:
                    mute_user(parts[1], int(parts[2]))
            elif cmd.startswith("/unmute "):
                unmute_user(cmd.split(" ",1)[1])
            elif cmd.startswith("/broadcast "):
                broadcast_system_message("📢 АДМИН: " + cmd.split(" ",1)[1])
            elif cmd == "":
                continue
            else:
                print("Неизвестная команда")
        except Exception as e:
            print(f"Ошибка: {e}")

