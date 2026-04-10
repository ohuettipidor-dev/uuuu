from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///messenger.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

AVATAR_FOLDER = 'static/avatars'
FILE_FOLDER = 'static/uploads'
VOICE_FOLDER = 'static/voices'
STICKER_FOLDER = 'static/stickers'
os.makedirs(AVATAR_FOLDER, exist_ok=True)
os.makedirs(FILE_FOLDER, exist_ok=True)
os.makedirs(VOICE_FOLDER, exist_ok=True)
os.makedirs(STICKER_FOLDER, exist_ok=True)

app.config['AVATAR_FOLDER'] = AVATAR_FOLDER
app.config['FILE_FOLDER'] = FILE_FOLDER
app.config['VOICE_FOLDER'] = VOICE_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'mp3', 'wav', 'ogg', 'mp4', 'avi', 'mov', 'pdf', 'doc', 'docx', 'txt', 'zip'}

def allowed_file(f):
    return '.' in f and f.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ========== МОДЕЛИ ==========
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    avatar = db.Column(db.String(200), default='default.png')
    status = db.Column(db.String(20), default='offline')
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    file_name = db.Column(db.String(200), nullable=True)
    file_type = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    voice_duration = db.Column(db.Integer, default=0)
    edited = db.Column(db.Boolean, default=False)
    deleted_for = db.Column(db.Text, default='')
    reply_to_id = db.Column(db.Integer, nullable=True)
    is_favorite = db.Column(db.Boolean, default=False)
    forwarded_from_id = db.Column(db.Integer, nullable=True)
    mentions = db.Column(db.Text, default='')
    is_pinned = db.Column(db.Boolean, default=False)
    
    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    avatar = db.Column(db.String(200), default='group_default.png')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class GroupMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    file_type = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    
    sender = db.relationship('User', foreign_keys=[sender_id])

class SecretChat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class SecretMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    encrypted_content = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    file_name = db.Column(db.String(200), nullable=True)
    file_type = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    secret_chat_id = db.Column(db.Integer, db.ForeignKey('secret_chat.id'), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    is_burn_after_read = db.Column(db.Boolean, default=False)
    voice_duration = db.Column(db.Integer, default=0)

class VoiceChannel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class VoiceChannelMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('voice_channel.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class VideoCall(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    room_id = db.Column(db.String(100), unique=True, nullable=False)
    status = db.Column(db.String(20), default='waiting')

class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subscribers_count = db.Column(db.Integer, default=0)

class ChannelSubscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

signaling_store = {}
app.typing_status = {}

@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, uid)

with app.app_context():
    db.create_all()
    print("✅ База данных создана")

# ========== ОСНОВНЫЕ МАРШРУТЫ ==========
@app.route('/')
def index():
    return redirect(url_for('chat')) if current_user.is_authenticated else render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        confirm = request.form['confirm_password']
        if p != confirm:
            flash('Пароли не совпадают', 'danger')
        elif User.query.filter_by(username=u).first():
            flash('Имя пользователя занято', 'danger')
        else:
            db.session.add(User(username=u, password=generate_password_hash(p)))
            db.session.commit()
            flash('Регистрация успешна!', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        user = User.query.filter_by(username=u).first()
        if user and check_password_hash(user.password, p):
            login_user(user)
            user.status = 'online'
            db.session.commit()
            return redirect(url_for('chat'))
        flash('Неверные данные', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    current_user.status = 'offline'
    db.session.commit()
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html', user=current_user)

@app.route('/profile/<int:uid>')
@login_required
def profile_by_id(uid):
    user = User.query.get(uid)
    return render_template('profile_public.html', profile_user=user)

# ========== ЧАТ ==========
@app.route('/chat')
@login_required
def chat():
    users = User.query.filter(User.id != current_user.id).all()
    groups = Group.query.join(GroupMember).filter(GroupMember.user_id == current_user.id).all()
    secret_chats = SecretChat.query.filter(
        (SecretChat.user1_id == current_user.id) | (SecretChat.user2_id == current_user.id),
        SecretChat.is_active == True
    ).all()
    return render_template('chat.html', users=users, groups=groups, secret_chats=secret_chats)

@app.route('/messages/<int:uid>')
@login_required
def messages(uid):
    other = User.query.get(uid)
    msgs = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == uid)) |
        ((Message.sender_id == uid) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp).all()
    return render_template('messages.html', msgs=msgs, other=other)

@app.route('/send', methods=['POST'])
@login_required
def send():
    receiver_id = int(request.form['receiver_id'])
    msg = Message(
        content=request.form.get('content', ''),
        file_path=request.form.get('file_path'),
        file_name=request.form.get('file_name'),
        file_type=request.form.get('file_type'),
        sender_id=current_user.id,
        receiver_id=receiver_id,
        voice_duration=request.form.get('voice_duration', 0)
    )
    db.session.add(msg)
    db.session.commit()
    return redirect(url_for('messages', uid=receiver_id))

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'Нет файла'}), 400
    f = request.files['file']
    if f.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    if allowed_file(f.filename):
        ext = f.filename.rsplit('.', 1)[1].lower()
        name = f"{uuid.uuid4().hex}.{ext}"
        f.save(os.path.join(FILE_FOLDER, name))
        if ext in ['png','jpg','jpeg','gif','webp','bmp']: ft = 'image'
        elif ext in ['mp3','wav','ogg']: ft = 'audio'
        elif ext in ['mp4','avi','mov']: ft = 'video'
        else: ft = 'document'
        return jsonify({'path': f'/static/uploads/{name}', 'name': f.filename, 'type': ft})
    return jsonify({'error': 'Формат не поддерживается'}), 400

@app.route('/upload_voice', methods=['POST'])
@login_required
def upload_voice():
    if 'audio' not in request.files:
        return jsonify({'error': 'Нет аудио'}), 400
    f = request.files['audio']
    name = f"voice_{current_user.id}_{uuid.uuid4().hex}.webm"
    f.save(os.path.join(VOICE_FOLDER, name))
    duration = request.form.get('duration', 0)
    return jsonify({'path': f'/static/voices/{name}', 'duration': duration})

# ========== ТАЙПИНГ ==========
@app.route('/typing', methods=['POST'])
@login_required
def typing():
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    is_typing = data.get('is_typing', False)
    key = f"typing_{current_user.id}_{receiver_id}"
    if is_typing:
        app.typing_status[key] = datetime.utcnow()
    else:
        app.typing_status.pop(key, None)
    return jsonify({'success': True})

@app.route('/get_typing/<int:receiver_id>')
@login_required
def get_typing(receiver_id):
    key = f"typing_{receiver_id}_{current_user.id}"
    typing_time = app.typing_status.get(key)
    if typing_time and (datetime.utcnow() - typing_time).seconds < 3:
        return jsonify({'is_typing': True})
    return jsonify({'is_typing': False})

# ========== ПОЛУЧЕНИЕ НОВЫХ СООБЩЕНИЙ ==========
@app.route('/get_new_messages/<int:last_id>/<int:receiver_id>')
@login_required
def get_new_messages(last_id, receiver_id):
    msgs = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == receiver_id)) |
        ((Message.sender_id == receiver_id) & (Message.receiver_id == current_user.id)),
        Message.id > last_id,
        ~Message.deleted_for.contains(str(current_user.id))
    ).order_by(Message.timestamp).all()
    
    result = []
    for m in msgs:
        result.append({
            'id': m.id,
            'content': m.content,
            'file_path': m.file_path,
            'file_name': m.file_name,
            'file_type': m.file_type,
            'timestamp': m.timestamp.strftime('%H:%M'),
            'is_own': m.sender_id == current_user.id,
            'voice_duration': m.voice_duration,
            'edited': m.edited,
            'reply_to_id': m.reply_to_id,
            'is_favorite': m.is_favorite,
            'is_pinned': m.is_pinned,
            'forwarded_from_id': m.forwarded_from_id,
            'mentions': m.mentions,
            'is_read': m.is_read
        })
        
        if m.receiver_id == current_user.id and not m.is_read:
            m.is_read = True
    
    db.session.commit()
    return jsonify(result)

# ========== РЕДАКТИРОВАНИЕ/УДАЛЕНИЕ ==========
@app.route('/edit_message', methods=['POST'])
@login_required
def edit_message():
    data = request.get_json()
    msg = Message.query.get(data['msg_id'])
    if msg and msg.sender_id == current_user.id:
        msg.content = data['new_content']
        msg.edited = True
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Нельзя редактировать'}), 403

@app.route('/delete_message', methods=['POST'])
@login_required
def delete_message():
    data = request.get_json()
    msg = Message.query.get(data['msg_id'])
    if msg:
        if data.get('delete_for_all') or msg.sender_id == current_user.id:
            db.session.delete(msg)
        else:
            if msg.deleted_for:
                msg.deleted_for += f',{current_user.id}'
            else:
                msg.deleted_for = str(current_user.id)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Сообщение не найдено'}), 404

@app.route('/toggle_favorite', methods=['POST'])
@login_required
def toggle_favorite():
    data = request.get_json()
    msg = Message.query.get(data['msg_id'])
    if msg and (msg.sender_id == current_user.id or msg.receiver_id == current_user.id):
        msg.is_favorite = not msg.is_favorite
        db.session.commit()
        return jsonify({'success': True, 'is_favorite': msg.is_favorite})
    return jsonify({'error': 'Не найдено'}), 404

@app.route('/forward_message', methods=['POST'])
@login_required
def forward_message():
    data = request.get_json()
    original = Message.query.get(data['msg_id'])
    if original:
        new_msg = Message(
            content=original.content,
            file_path=original.file_path,
            file_name=original.file_name,
            file_type=original.file_type,
            sender_id=current_user.id,
            receiver_id=data['target_id'],
            forwarded_from_id=original.sender_id
        )
        db.session.add(new_msg)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Не найдено'}), 404

@app.route('/get_reply_preview/<int:msg_id>/<string:msg_type>')
@login_required
def get_reply_preview(msg_id, msg_type):
    msg = Message.query.get(msg_id)
    if msg:
        return jsonify({
            'id': msg.id,
            'content': msg.content[:100] if msg.content else '[Файл]',
            'sender_name': msg.sender.username
        })
    return jsonify({'error': 'Не найдено'}), 404

@app.route('/pin_message', methods=['POST'])
@login_required
def pin_message():
    data = request.get_json()
    msg = Message.query.get(data['msg_id'])
    if msg:
        # Открепляем предыдущее закреплённое сообщение в этом диалоге
        old_pinned = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == msg.receiver_id)) |
            ((Message.sender_id == msg.receiver_id) & (Message.receiver_id == current_user.id)),
            Message.is_pinned == True
        ).first()
        if old_pinned:
            old_pinned.is_pinned = False
        
        msg.is_pinned = not msg.is_pinned
        db.session.commit()
        return jsonify({'success': True, 'is_pinned': msg.is_pinned})
    return jsonify({'error': 'Не найдено'}), 404

@app.route('/get_pinned_message/<int:chat_id>/<string:chat_type>')
@login_required
def get_pinned_message(chat_id, chat_type):
    pinned = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == chat_id)) |
        ((Message.sender_id == chat_id) & (Message.receiver_id == current_user.id)),
        Message.is_pinned == True
    ).first()
    if pinned:
        return jsonify({
            'id': pinned.id,
            'content': pinned.content[:100] if pinned.content else '[Файл]',
            'sender_name': pinned.sender.username
        })
    return jsonify({'error': 'Нет закрепленных'}), 404

# ========== УПОМИНАНИЯ ==========
@app.route('/search_users')
@login_required
def search_users():
    query = request.args.get('q', '').lower().strip()
    if not query:
        return jsonify([])
    users = User.query.filter(
        User.id != current_user.id,
        User.username.ilike(f'%{query}%')
    ).limit(10).all()
    result = [{'id': u.id, 'username': u.username, 'avatar': u.avatar} for u in users]
    return jsonify(result)

@app.route('/get_mention_notifications')
@login_required
def get_mention_notifications():
    return jsonify({'count': 0})

# ========== ГРУППЫ ==========
@app.route('/create_group', methods=['POST'])
@login_required
def create_group():
    name = request.form.get('name')
    if name:
        group = Group(name=name, created_by=current_user.id)
        db.session.add(group)
        db.session.commit()
        db.session.add(GroupMember(user_id=current_user.id, group_id=group.id, is_admin=True))
        db.session.commit()
        flash(f'Группа "{name}" создана!', 'success')
    return redirect(url_for('chat'))

@app.route('/group/<int:gid>')
@login_required
def group_chat(gid):
    group = Group.query.get(gid)
    if not group:
        flash('Группа не найдена', 'danger')
        return redirect(url_for('chat'))
    member = GroupMember.query.filter_by(user_id=current_user.id, group_id=gid).first()
    if not member:
        flash('Вы не участник группы', 'danger')
        return redirect(url_for('chat'))
    messages = GroupMessage.query.filter_by(group_id=gid).order_by(GroupMessage.timestamp).all()
    members = GroupMember.query.filter_by(group_id=gid).all()
    members_list = [User.query.get(m.user_id) for m in members]
    return render_template('group_chat.html', group=group, messages=messages, members=members_list)

@app.route('/send_group', methods=['POST'])
@login_required
def send_group():
    msg = GroupMessage(
        content=request.form.get('content', ''),
        file_path=request.form.get('file_path'),
        file_type=request.form.get('file_type'),
        sender_id=current_user.id,
        group_id=int(request.form['group_id'])
    )
    db.session.add(msg)
    db.session.commit()
    return redirect(url_for('group_chat', gid=request.form['group_id']))

# ========== СЕКРЕТНЫЕ ЧАТЫ ==========
@app.route('/create_secret_chat/<int:user_id>', methods=['POST'])
@login_required
def create_secret_chat(user_id):
    existing = SecretChat.query.filter(
        ((SecretChat.user1_id == current_user.id) & (SecretChat.user2_id == user_id)) |
        ((SecretChat.user1_id == user_id) & (SecretChat.user2_id == current_user.id))
    ).first()
    if existing:
        return jsonify({'chat_id': existing.id, 'redirect': f'/secret_chat/{existing.id}'})
    
    secret_chat = SecretChat(user1_id=current_user.id, user2_id=user_id)
    db.session.add(secret_chat)
    db.session.commit()
    return jsonify({'chat_id': secret_chat.id, 'redirect': f'/secret_chat/{secret_chat.id}'})

@app.route('/secret_chat/<int:chat_id>')
@login_required
def secret_chat(chat_id):
    secret_chat = SecretChat.query.get(chat_id)
    if not secret_chat or (secret_chat.user1_id != current_user.id and secret_chat.user2_id != current_user.id):
        flash('Нет доступа', 'danger')
        return redirect(url_for('chat'))
    
    other_id = secret_chat.user2_id if secret_chat.user1_id == current_user.id else secret_chat.user1_id
    other_user = User.query.get(other_id)
    messages = SecretMessage.query.filter_by(secret_chat_id=chat_id).order_by(SecretMessage.timestamp).all()
    
    decrypted_messages = []
    for msg in messages:
        decrypted_messages.append({
            'id': msg.id,
            'content': msg.encrypted_content,  # Для простоты без шифрования в демо
            'file_path': msg.file_path,
            'file_name': msg.file_name,
            'file_type': msg.file_type,
            'timestamp': msg.timestamp,
            'sender_id': msg.sender_id,
            'is_own': msg.sender_id == current_user.id,
            'is_burn_after_read': msg.is_burn_after_read,
            'voice_duration': msg.voice_duration
        })
    
    return render_template('secret_chat.html', secret_chat=secret_chat, other_user=other_user, messages=decrypted_messages)

@app.route('/send_secret', methods=['POST'])
@login_required
def send_secret():
    chat_id = int(request.form['chat_id'])
    msg = SecretMessage(
        encrypted_content=request.form.get('content', ''),
        file_path=request.form.get('file_path'),
        file_name=request.form.get('file_name'),
        file_type=request.form.get('file_type'),
        sender_id=current_user.id,
        secret_chat_id=chat_id,
        voice_duration=request.form.get('voice_duration', 0),
        is_burn_after_read=request.form.get('burn_after_read') == 'true'
    )
    db.session.add(msg)
    db.session.commit()
    return redirect(url_for('secret_chat', chat_id=chat_id))

@app.route('/upload_secret_file', methods=['POST'])
@login_required
def upload_secret_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Нет файла'}), 400
    f = request.files['file']
    if allowed_file(f.filename):
        ext = f.filename.rsplit('.', 1)[1].lower()
        name = f"secret_{current_user.id}_{uuid.uuid4().hex}.{ext}"
        f.save(os.path.join(FILE_FOLDER, name))
        if ext in ['png','jpg','jpeg','gif','webp','bmp']: ft = 'image'
        elif ext in ['mp3','wav','ogg']: ft = 'audio'
        elif ext in ['mp4','avi','mov']: ft = 'video'
        else: ft = 'document'
        return jsonify({'path': f'/static/uploads/{name}', 'name': f.filename, 'type': ft})
    return jsonify({'error': 'Формат не поддерживается'}), 400

@app.route('/get_secret_messages/<int:chat_id>/<int:last_id>')
@login_required
def get_secret_messages(chat_id, last_id):
    messages = SecretMessage.query.filter(
        SecretMessage.secret_chat_id == chat_id,
        SecretMessage.id > last_id
    ).order_by(SecretMessage.timestamp).all()
    
    result = []
    for msg in messages:
        result.append({
            'id': msg.id,
            'content': msg.encrypted_content,
            'file_path': msg.file_path,
            'file_name': msg.file_name,
            'file_type': msg.file_type,
            'timestamp': msg.timestamp.strftime('%H:%M'),
            'is_own': msg.sender_id == current_user.id,
            'voice_duration': msg.voice_duration,
            'is_burn_after_read': msg.is_burn_after_read
        })
    return jsonify(result)

@app.route('/secret_chats')
@login_required
def secret_chats_list():
    secret_chats = SecretChat.query.filter(
        (SecretChat.user1_id == current_user.id) | (SecretChat.user2_id == current_user.id),
        SecretChat.is_active == True
    ).all()
    chats_data = []
    for sc in secret_chats:
        other_id = sc.user2_id if sc.user1_id == current_user.id else sc.user1_id
        other_user = User.query.get(other_id)
        last_msg = SecretMessage.query.filter_by(secret_chat_id=sc.id).order_by(SecretMessage.timestamp.desc()).first()
        chats_data.append({'id': sc.id, 'other_user': other_user, 'last_msg': last_msg})
    return render_template('secret_chats.html', secret_chats=chats_data)

# ========== ВИДЕОЗВОНКИ ==========
@app.route('/start_call/<int:user_id>', methods=['POST'])
@login_required
def start_call(user_id):
    room_id = f"call_{current_user.id}_{user_id}_{uuid.uuid4().hex[:8]}"
    return jsonify({'room_id': room_id})

@app.route('/call/<string:room_id>')
@login_required
def call_room(room_id):
    return render_template('call.html', room_id=room_id)

@app.route('/send_offer', methods=['POST'])
@login_required
def send_offer():
    data = request.get_json()
    signaling_store[f"{data['room_id']}_offer"] = data['offer']
    return jsonify({'success': True})

@app.route('/send_answer', methods=['POST'])
@login_required
def send_answer():
    data = request.get_json()
    signaling_store[f"{data['room_id']}_answer"] = data['answer']
    return jsonify({'success': True})

@app.route('/send_ice_candidate', methods=['POST'])
@login_required
def send_ice_candidate():
    data = request.get_json()
    key = f"{data['room_id']}_candidates"
    if key not in signaling_store:
        signaling_store[key] = []
    signaling_store[key].append(data['candidate'])
    return jsonify({'success': True})

@app.route('/get_signaling/<string:room_id>')
@login_required
def get_signaling(room_id):
    result = {}
    if f"{room_id}_offer" in signaling_store:
        result['offer'] = signaling_store.pop(f"{room_id}_offer")
    if f"{room_id}_answer" in signaling_store:
        result['answer'] = signaling_store.pop(f"{room_id}_answer")
    if f"{room_id}_candidates" in signaling_store and signaling_store[f"{room_id}_candidates"]:
        result['candidate'] = signaling_store[f"{room_id}_candidates"].pop(0)
    return jsonify(result)

# ========== ГОЛОСОВЫЕ КАНАЛЫ ==========
@app.route('/voice_channels')
@login_required
def voice_channels():
    channels = VoiceChannel.query.filter_by(is_active=True).all()
    channel_data = []
    for ch in channels:
        member_count = VoiceChannelMember.query.filter_by(channel_id=ch.id).count()
        channel_data.append({
            'id': ch.id,
            'name': ch.name,
            'member_count': member_count,
            'creator': ch.creator.username,
            'is_joined': VoiceChannelMember.query.filter_by(channel_id=ch.id, user_id=current_user.id).first() is not None
        })
    return render_template('voice_channels.html', channels=channel_data)

@app.route('/create_voice_channel', methods=['POST'])
@login_required
def create_voice_channel():
    name = request.form.get('name')
    if name:
        channel = VoiceChannel(name=name, created_by=current_user.id)
        db.session.add(channel)
        db.session.commit()
        flash(f'🎤 Голосовой канал "{name}" создан!', 'success')
    return redirect(url_for('voice_channels'))

@app.route('/join_voice_channel/<int:channel_id>', methods=['POST'])
@login_required
def join_voice_channel(channel_id):
    if not VoiceChannelMember.query.filter_by(channel_id=channel_id, user_id=current_user.id).first():
        db.session.add(VoiceChannelMember(channel_id=channel_id, user_id=current_user.id))
        db.session.commit()
    return jsonify({'success': True})

@app.route('/leave_voice_channel/<int:channel_id>', methods=['POST'])
@login_required
def leave_voice_channel(channel_id):
    member = VoiceChannelMember.query.filter_by(channel_id=channel_id, user_id=current_user.id).first()
    if member:
        db.session.delete(member)
        db.session.commit()
    return jsonify({'success': True})

# ========== КАНАЛЫ ==========
@app.route('/channels')
@login_required
def channels_list():
    my_channels = Channel.query.filter_by(created_by=current_user.id).all()
    subscribed = ChannelSubscriber.query.filter_by(user_id=current_user.id).all()
    subscribed_ids = [s.channel_id for s in subscribed]
    subscribed_channels = Channel.query.filter(Channel.id.in_(subscribed_ids)).all() if subscribed_ids else []
    return render_template('channels.html', my_channels=my_channels, subscribed_channels=subscribed_channels)

@app.route('/channel/create', methods=['GET', 'POST'])
@login_required
def channel_create():
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        if name:
            channel = Channel(name=name, username=username, created_by=current_user.id)
            db.session.add(channel)
            db.session.commit()
            flash(f'Канал "{name}" создан!', 'success')
            return redirect(url_for('channels_list'))
    return render_template('channel_create.html')

@app.route('/channel/<int:channel_id>')
@login_required
def channel_view(channel_id):
    channel = Channel.query.get(channel_id)
    if not channel:
        flash('Канал не найден', 'danger')
        return redirect(url_for('channels_list'))
    is_subscribed = ChannelSubscriber.query.filter_by(channel_id=channel_id, user_id=current_user.id).first() is not None
    return render_template('channel.html', channel=channel, is_subscribed=is_subscribed)

@app.route('/channel/subscribe/<int:channel_id>', methods=['POST'])
@login_required
def channel_subscribe(channel_id):
    if not ChannelSubscriber.query.filter_by(channel_id=channel_id, user_id=current_user.id).first():
        db.session.add(ChannelSubscriber(channel_id=channel_id, user_id=current_user.id))
        channel = Channel.query.get(channel_id)
        channel.subscribers_count += 1
        db.session.commit()
    return redirect(url_for('channel_view', channel_id=channel_id))

# ========== СТИКЕРЫ ==========
@app.route('/upload_sticker_by_url', methods=['POST'])
@login_required
def upload_sticker_by_url():
    data = request.get_json()
    url = data.get('url')
    receiver_id = data.get('receiver_id')
    
    import requests
    response = requests.get(url, timeout=10)
    filename = f"sticker_{uuid.uuid4().hex}.png"
    filepath = os.path.join(STICKER_FOLDER, filename)
    with open(filepath, 'wb') as f:
        f.write(response.content)
    
    msg = Message(
        content='',
        file_path=f'/static/stickers/{filename}',
        file_name='sticker.png',
        file_type='sticker',
        sender_id=current_user.id,
        receiver_id=receiver_id
    )
    db.session.add(msg)
    db.session.commit()
    
    return jsonify({'success': True})

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)