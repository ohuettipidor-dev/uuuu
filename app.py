from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import uuid
import re
import json
import hashlib
import base64
import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

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
app.config['STICKER_FOLDER'] = STICKER_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp',
    'mp3', 'wav', 'ogg', 'flac', 'm4a',
    'mp4', 'avi', 'mov', 'mkv', 'webm',
    'pdf', 'doc', 'docx', 'txt', 'zip', 'rar', '7z'
}

def allowed_file(f):
    return '.' in f and f.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_secret_key(user_id, other_id):
    combined = f"beargram_secret_{min(user_id, other_id)}_{max(user_id, other_id)}_bear"
    return hashlib.sha256(combined.encode()).digest()

def encrypt_message(message, user_id, other_id):
    key = generate_secret_key(user_id, other_id)
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(message.encode()) + padder.finalize()
    encrypted = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(iv + encrypted).decode('utf-8')

def decrypt_message(encrypted_message, user_id, other_id):
    try:
        key = generate_secret_key(user_id, other_id)
        data = base64.b64decode(encrypted_message)
        iv = data[:16]
        encrypted = data[16:]
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted_padded = decryptor.update(encrypted) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        decrypted = unpadder.update(decrypted_padded) + unpadder.finalize()
        return decrypted.decode('utf-8')
    except Exception:
        return "[Зашифрованное сообщение]"

def render_mentions(text, current_user_id=None):
    if not text:
        return text, []
    
    mentioned_users = []
    users = User.query.all()
    
    for user in users:
        if user.id == current_user_id:
            continue
        
        if user.username_link:
            mention_name = user.username_link[1:]
        else:
            mention_name = user.username
        
        pattern = r'@' + re.escape(mention_name) + r'\b'
        if re.search(pattern, text):
            text = re.sub(pattern, f'<a href="/profile/{user.id}" class="mention">@{mention_name}</a>', text)
            mentioned_users.append(user.id)
    
    return text, mentioned_users

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ========== МОДЕЛИ ==========
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    username_link = db.Column(db.String(80), unique=True, nullable=True)
    password = db.Column(db.String(200), nullable=False)
    avatar = db.Column(db.String(200), default='default.png')
    status = db.Column(db.String(20), default='offline')
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    notifications_enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    current_theme_id = db.Column(db.Integer, nullable=True)

class Blacklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    blocked_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class SecretChat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    user1 = db.relationship('User', foreign_keys=[user1_id])
    user2 = db.relationship('User', foreign_keys=[user2_id])

class SecretMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    encrypted_content = db.Column(db.Text, nullable=False)
    file_path = db.Column(db.String(500), nullable=True)
    file_name = db.Column(db.String(200), nullable=True)
    file_type = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    secret_chat_id = db.Column(db.Integer, db.ForeignKey('secret_chat.id'), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    is_burn_after_read = db.Column(db.Boolean, default=False)
    burn_after_read_timer = db.Column(db.Integer, default=0)
    voice_duration = db.Column(db.Integer, default=0)
    
    sender = db.relationship('User', foreign_keys=[sender_id])
    secret_chat = db.relationship('SecretChat', foreign_keys=[secret_chat_id])

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
    reply_to_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=True)
    is_favorite = db.Column(db.Boolean, default=False)
    forwarded_from_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    forwarded_message_id = db.Column(db.Integer, nullable=True)
    mentions = db.Column(db.Text, default='')
    is_pinned = db.Column(db.Boolean, default=False)
    pinned_at = db.Column(db.DateTime, nullable=True)
    
    reply_to = db.relationship('Message', remote_side=[id], foreign_keys=[reply_to_id])
    forwarded_from = db.relationship('User', foreign_keys=[forwarded_from_id])
    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default='')
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
    file_name = db.Column(db.String(200), nullable=True)
    file_type = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    voice_duration = db.Column(db.Integer, default=0)
    edited = db.Column(db.Boolean, default=False)
    deleted_for = db.Column(db.Text, default='')
    reply_to_id = db.Column(db.Integer, nullable=True)
    is_favorite = db.Column(db.Boolean, default=False)
    forwarded_from_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    forwarded_message_id = db.Column(db.Integer, nullable=True)
    mentions = db.Column(db.Text, default='')
    is_pinned = db.Column(db.Boolean, default=False)
    pinned_at = db.Column(db.DateTime, nullable=True)
    
    sender = db.relationship('User', foreign_keys=[sender_id])
    forwarded_from = db.relationship('User', foreign_keys=[forwarded_from_id])

class VoiceChannel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    creator = db.relationship('User', foreign_keys=[created_by])
    group = db.relationship('Group', foreign_keys=[group_id])

class VoiceChannelMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('voice_channel.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    channel = db.relationship('VoiceChannel', foreign_keys=[channel_id])
    user = db.relationship('User', foreign_keys=[user_id])

class VideoCall(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    room_id = db.Column(db.String(100), unique=True, nullable=False)
    status = db.Column(db.String(20), default='waiting')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    from_user = db.relationship('User', foreign_keys=[from_user_id])
    to_user = db.relationship('User', foreign_keys=[to_user_id])

class Channel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default='')
    avatar = db.Column(db.String(200), default='channel_default.png')
    username = db.Column(db.String(80), unique=True, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_private = db.Column(db.Boolean, default=False)
    subscribers_count = db.Column(db.Integer, default=0)
    
    creator = db.relationship('User', foreign_keys=[created_by])

class ChannelSubscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subscribed_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_muted = db.Column(db.Boolean, default=False)
    
    channel = db.relationship('Channel', foreign_keys=[channel_id])
    user = db.relationship('User', foreign_keys=[user_id])

class ChannelPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    file_name = db.Column(db.String(200), nullable=True)
    file_type = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    views = db.Column(db.Integer, default=0)
    comments_enabled = db.Column(db.Boolean, default=True)
    attachments = db.Column(db.Text, default='')
    
    author = db.relationship('User', foreign_keys=[author_id])
    channel = db.relationship('Channel', foreign_keys=[channel_id])

class ChannelComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('channel_post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    post = db.relationship('ChannelPost', foreign_keys=[post_id])
    user = db.relationship('User', foreign_keys=[user_id])

class StickerPack(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_premium = db.Column(db.Boolean, default=False)
    preview = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Sticker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pack_id = db.Column(db.Integer, db.ForeignKey('sticker_pack.id'), nullable=False)
    emoji = db.Column(db.String(50), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    order_num = db.Column(db.Integer, default=0)
    
    pack = db.relationship('StickerPack', backref='stickers')

class UserSticker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pack_id = db.Column(db.Integer, db.ForeignKey('sticker_pack.id'), nullable=False)
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)

class Gift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    gift_type = db.Column(db.String(50), nullable=False)
    gift_id = db.Column(db.Integer, nullable=False)
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_used = db.Column(db.Boolean, default=False)
    
    from_user = db.relationship('User', foreign_keys=[from_user_id])
    to_user = db.relationship('User', foreign_keys=[to_user_id])

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan = db.Column(db.String(50), default='free')
    expires_at = db.Column(db.DateTime, nullable=True)
    auto_renew = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', foreign_keys=[user_id])

class CustomTheme(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    primary_color = db.Column(db.String(7), default='#ff9a9e')
    secondary_color = db.Column(db.String(7), default='#fecfef')
    bubble_color_sent = db.Column(db.String(7), default='#ff6b6b')
    bubble_color_received = db.Column(db.String(7), default='#ffffff')
    text_color = db.Column(db.String(7), default='#333333')
    is_premium = db.Column(db.Boolean, default=False)
    price = db.Column(db.Float, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    author = db.relationship('User', foreign_keys=[author_id])

class UserTheme(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    theme_id = db.Column(db.Integer, db.ForeignKey('custom_theme.id'), nullable=False)
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', foreign_keys=[user_id])
    theme = db.relationship('CustomTheme', foreign_keys=[theme_id])

class CloudStorage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    used_bytes = db.Column(db.BigInteger, default=0)
    total_bytes = db.Column(db.BigInteger, default=2 * 1024 * 1024 * 1024)
    upgraded_at = db.Column(db.DateTime, nullable=True)
    
    user = db.relationship('User', foreign_keys=[user_id])

class FamilyAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    owner = db.relationship('User', foreign_keys=[owner_id])

class FamilyMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey('family_account.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    family = db.relationship('FamilyAccount', foreign_keys=[family_id])
    user = db.relationship('User', foreign_keys=[user_id])

signaling_store = {}

@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, uid)

with app.app_context():
    db.create_all()
    
    # Создаём стикерпак если нет
    if StickerPack.query.count() == 0:
        pack = StickerPack(
            name='emotions',
            title='😊 МОИ ЭМОЦИИ',
            author_id=1,
            is_premium=False,
            preview='/static/stickers/preview.png'
        )
        db.session.add(pack)
        db.session.commit()
        print("✅ Стикерпак создан")

@app.template_filter('json_decode')
def json_decode_filter(data):
    try:
        return json.loads(data) if data else []
    except:
        return []

# ========== ОСНОВНЫЕ МАРШРУТЫ ==========
@app.route('/')
def index():
    return redirect(url_for('chat')) if current_user.is_authenticated else render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u = request.form['username']
        ul = request.form.get('username_link', '').strip().lower().replace(' ', '_')
        p = request.form['password']
        confirm = request.form['confirm_password']
        
        if ul and not ul.startswith('@'):
            ul = '@' + ul
        
        if p != confirm:
            flash('Пароли не совпадают', 'danger')
        elif User.query.filter_by(username=u).first():
            flash('Имя пользователя занято', 'danger')
        elif ul and User.query.filter_by(username_link=ul).first():
            flash('Такой @username уже существует', 'danger')
        elif ul and (len(ul) < 2 or len(ul) > 32):
            flash('@username должен быть от 2 до 32 символов', 'danger')
        elif ul and not re.match(r'^@[a-zA-Z0-9_]+$', ul):
            flash('@username может содержать только буквы, цифры и _', 'danger')
        else:
            db.session.add(User(username=u, username_link=ul if ul else None, password=generate_password_hash(p)))
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
            user.last_seen = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('chat'))
        flash('Неверные данные', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    current_user.status = 'offline'
    current_user.last_seen = datetime.utcnow()
    db.session.commit()
    logout_user()
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        if 'avatar' in request.files:
            f = request.files['avatar']
            if f and allowed_file(f.filename):
                ext = f.filename.rsplit('.', 1)[1].lower()
                name = f"avatar_{current_user.id}_{uuid.uuid4().hex}.{ext}"
                f.save(os.path.join(AVATAR_FOLDER, name))
                if current_user.avatar != 'default.png':
                    old = os.path.join(AVATAR_FOLDER, current_user.avatar)
                    if os.path.exists(old):
                        os.remove(old)
                current_user.avatar = name
                db.session.commit()
                flash('Аватар обновлён', 'success')
        
        if 'username_link' in request.form:
            ul = request.form['username_link'].strip().lower().replace(' ', '_')
            if ul:
                if not ul.startswith('@'):
                    ul = '@' + ul
                existing = User.query.filter_by(username_link=ul).first()
                if existing and existing.id != current_user.id:
                    flash('Такой @username уже занят', 'danger')
                elif len(ul) < 2 or len(ul) > 32:
                    flash('@username должен быть от 2 до 32 символов', 'danger')
                elif not re.match(r'^@[a-zA-Z0-9_]+$', ul):
                    flash('@username может содержать только буквы, цифры и _', 'danger')
                else:
                    current_user.username_link = ul
                    db.session.commit()
                    flash('@username обновлён!', 'success')
            else:
                current_user.username_link = None
                db.session.commit()
                flash('@username удалён', 'success')
        
        if 'notifications_enabled' in request.form:
            current_user.notifications_enabled = request.form['notifications_enabled'] == 'on'
            db.session.commit()
            flash('Настройки уведомлений сохранены', 'success')
        
        if 'delete_account' in request.form:
            Message.query.filter((Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id)).delete()
            GroupMessage.query.filter(GroupMessage.sender_id == current_user.id).delete()
            GroupMember.query.filter(GroupMember.user_id == current_user.id).delete()
            Blacklist.query.filter((Blacklist.user_id == current_user.id) | (Blacklist.blocked_user_id == current_user.id)).delete()
            SecretMessage.query.filter((SecretMessage.sender_id == current_user.id)).delete()
            SecretChat.query.filter((SecretChat.user1_id == current_user.id) | (SecretChat.user2_id == current_user.id)).delete()
            VoiceChannelMember.query.filter_by(user_id=current_user.id).delete()
            VoiceChannel.query.filter_by(created_by=current_user.id).delete()
            VideoCall.query.filter((VideoCall.from_user_id == current_user.id) | (VideoCall.to_user_id == current_user.id)).delete()
            ChannelSubscriber.query.filter_by(user_id=current_user.id).delete()
            Channel.query.filter_by(created_by=current_user.id).delete()
            Subscription.query.filter_by(user_id=current_user.id).delete()
            UserSticker.query.filter_by(user_id=current_user.id).delete()
            UserTheme.query.filter_by(user_id=current_user.id).delete()
            CloudStorage.query.filter_by(user_id=current_user.id).delete()
            Gift.query.filter((Gift.from_user_id == current_user.id) | (Gift.to_user_id == current_user.id)).delete()
            FamilyMember.query.filter_by(user_id=current_user.id).delete()
            FamilyAccount.query.filter_by(owner_id=current_user.id).delete()
            
            groups = Group.query.filter_by(created_by=current_user.id).all()
            for group in groups:
                GroupMember.query.filter_by(group_id=group.id).delete()
                GroupMessage.query.filter_by(group_id=group.id).delete()
                db.session.delete(group)
            
            db.session.delete(current_user)
            db.session.commit()
            logout_user()
            flash('Аккаунт удалён', 'success')
            return redirect(url_for('index'))
        
        return redirect(url_for('profile'))
    return render_template('profile.html', user=current_user)

@app.route('/profile/<int:uid>')
@login_required
def profile_by_id(uid):
    user = db.session.get(User, uid)
    if not user:
        flash('Пользователь не найден', 'danger')
        return redirect(url_for('chat'))
    
    is_blocked = Blacklist.query.filter_by(user_id=current_user.id, blocked_user_id=uid).first() is not None
    
    return render_template('profile_public.html', profile_user=user, is_blocked=is_blocked)

@app.route('/block_user/<int:uid>', methods=['POST'])
@login_required
def block_user(uid):
    if uid == current_user.id:
        flash('Нельзя заблокировать самого себя', 'danger')
        return redirect(url_for('profile_by_id', uid=uid))
    
    existing = Blacklist.query.filter_by(user_id=current_user.id, blocked_user_id=uid).first()
    if not existing:
        db.session.add(Blacklist(user_id=current_user.id, blocked_user_id=uid))
        db.session.commit()
        flash('Пользователь добавлен в черный список', 'success')
    else:
        db.session.delete(existing)
        db.session.commit()
        flash('Пользователь удалён из черного списка', 'success')
    
    return redirect(url_for('profile_by_id', uid=uid))

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
        elif ext in ['mp3','wav','ogg','flac','m4a']: ft = 'audio'
        elif ext in ['mp4','avi','mov','mkv','webm']: ft = 'video'
        else: ft = 'document'
        return jsonify({'path': f'/static/uploads/{name}', 'name': f.filename, 'type': ft})
    return jsonify({'error': 'Формат не поддерживается'}), 400

@app.route('/upload_voice', methods=['POST'])
@login_required
def upload_voice():
    if 'audio' not in request.files:
        return jsonify({'error': 'Нет аудио'}), 400
    f = request.files['audio']
    if f.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    name = f"voice_{current_user.id}_{uuid.uuid4().hex}.webm"
    f.save(os.path.join(VOICE_FOLDER, name))
    duration = request.form.get('duration', 0)
    return jsonify({'path': f'/static/voices/{name}', 'duration': duration})

@app.route('/upload_video_message', methods=['POST'])
@login_required
def upload_video_message():
    if 'video' not in request.files:
        return jsonify({'error': 'Нет видео'}), 400
    f = request.files['video']
    if f.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    
    name = f"video_msg_{current_user.id}_{uuid.uuid4().hex}.webm"
    f.save(os.path.join(FILE_FOLDER, name))
    
    return jsonify({'path': f'/static/uploads/{name}', 'duration': 0})

# ========== ВИДЕОЗВОНКИ ==========
@app.route('/send_offer', methods=['POST'])
@login_required
def send_offer():
    data = request.get_json()
    room_id = data['room_id']
    offer = data['offer']
    signaling_store[f"{room_id}_offer"] = offer
    return jsonify({'success': True})

@app.route('/send_answer', methods=['POST'])
@login_required
def send_answer():
    data = request.get_json()
    room_id = data['room_id']
    answer = data['answer']
    signaling_store[f"{room_id}_answer"] = answer
    return jsonify({'success': True})

@app.route('/send_ice_candidate', methods=['POST'])
@login_required
def send_ice_candidate():
    data = request.get_json()
    room_id = data['room_id']
    candidate = data['candidate']
    if f"{room_id}_candidates" not in signaling_store:
        signaling_store[f"{room_id}_candidates"] = []
    signaling_store[f"{room_id}_candidates"].append(candidate)
    return jsonify({'success': True})

@app.route('/get_signaling/<string:room_id>')
@login_required
def get_signaling(room_id):
    result = {}
    offer_key = f"{room_id}_offer"
    answer_key = f"{room_id}_answer"
    candidates_key = f"{room_id}_candidates"
    
    if offer_key in signaling_store:
        result['offer'] = signaling_store[offer_key]
        del signaling_store[offer_key]
    if answer_key in signaling_store:
        result['answer'] = signaling_store[answer_key]
        del signaling_store[answer_key]
    if candidates_key in signaling_store and signaling_store[candidates_key]:
        result['candidate'] = signaling_store[candidates_key].pop(0)
    
    return jsonify(result)

@app.route('/start_call/<int:user_id>', methods=['POST'])
@login_required
def start_call(user_id):
    other_user = db.session.get(User, user_id)
    if not other_user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    room_id = f"call_{current_user.id}_{user_id}_{uuid.uuid4().hex[:8]}"
    
    existing = VideoCall.query.filter(
        ((VideoCall.from_user_id == current_user.id) & (VideoCall.to_user_id == user_id)) |
        ((VideoCall.from_user_id == user_id) & (VideoCall.to_user_id == current_user.id)),
        VideoCall.status != 'ended'
    ).first()
    
    if existing:
        return jsonify({'room_id': existing.room_id, 'existing': True})
    
    call = VideoCall(from_user_id=current_user.id, to_user_id=user_id, room_id=room_id)
    db.session.add(call)
    db.session.commit()
    
    return jsonify({'room_id': room_id, 'existing': False})

@app.route('/call/<string:room_id>')
@login_required
def call_room(room_id):
    call = VideoCall.query.filter_by(room_id=room_id).first()
    if not call:
        flash('Звонок не найден', 'danger')
        return redirect(url_for('chat'))
    
    if call.from_user_id != current_user.id and call.to_user_id != current_user.id:
        flash('Нет доступа', 'danger')
        return redirect(url_for('chat'))
    
    other_id = call.to_user_id if call.from_user_id == current_user.id else call.from_user_id
    other_user = db.session.get(User, other_id)
    
    return render_template('call.html', room_id=room_id, other_user=other_user)

@app.route('/end_call/<string:room_id>', methods=['POST'])
@login_required
def end_call(room_id):
    call = VideoCall.query.filter_by(room_id=room_id).first()
    if call:
        call.status = 'ended'
        db.session.commit()
    return jsonify({'success': True})

# ========== СЕКРЕТНЫЕ ЧАТЫ ==========
@app.route('/create_secret_chat/<int:user_id>', methods=['POST'])
@login_required
def create_secret_chat(user_id):
    if user_id == current_user.id:
        if request.is_json:
            return jsonify({'error': 'Нельзя создать секретный чат с самим собой'}), 400
        flash('Нельзя создать секретный чат с самим собой', 'danger')
        return redirect(url_for('profile_by_id', uid=user_id))
    
    other_user = db.session.get(User, user_id)
    if not other_user:
        if request.is_json:
            return jsonify({'error': 'Пользователь не найден'}), 404
        flash('Пользователь не найден', 'danger')
        return redirect(url_for('chat'))
    
    existing = SecretChat.query.filter(
        ((SecretChat.user1_id == current_user.id) & (SecretChat.user2_id == user_id)) |
        ((SecretChat.user1_id == user_id) & (SecretChat.user2_id == current_user.id))
    ).first()
    
    if existing:
        if request.is_json:
            return jsonify({'chat_id': existing.id, 'redirect': f'/secret_chat/{existing.id}'})
        flash('Секретный чат уже существует', 'info')
        return redirect(url_for('secret_chat', chat_id=existing.id))
    
    secret_chat = SecretChat(user1_id=current_user.id, user2_id=user_id)
    db.session.add(secret_chat)
    db.session.commit()
    
    if request.is_json:
        return jsonify({'chat_id': secret_chat.id, 'redirect': f'/secret_chat/{secret_chat.id}'})
    
    flash(f'Секретный чат с {other_user.username} создан! Сообщения зашифрованы AES-256', 'success')
    return redirect(url_for('secret_chat', chat_id=secret_chat.id))

@app.route('/secret_chat/<int:chat_id>')
@login_required
def secret_chat(chat_id):
    secret_chat = db.session.get(SecretChat, chat_id)
    if not secret_chat:
        flash('Чат не найден', 'danger')
        return redirect(url_for('chat'))
    
    if secret_chat.user1_id != current_user.id and secret_chat.user2_id != current_user.id:
        flash('Нет доступа к этому чату', 'danger')
        return redirect(url_for('chat'))
    
    other_user_id = secret_chat.user2_id if secret_chat.user1_id == current_user.id else secret_chat.user1_id
    other_user = db.session.get(User, other_user_id)
    
    messages = SecretMessage.query.filter_by(secret_chat_id=chat_id).order_by(SecretMessage.timestamp).all()
    
    decrypted_messages = []
    for msg in messages:
        decrypted_content = decrypt_message(msg.encrypted_content, current_user.id, other_user_id)
        decrypted_messages.append({
            'id': msg.id,
            'content': decrypted_content,
            'file_path': msg.file_path,
            'file_name': msg.file_name,
            'file_type': msg.file_type,
            'timestamp': msg.timestamp,
            'sender_id': msg.sender_id,
            'is_own': msg.sender_id == current_user.id,
            'is_read': msg.is_read,
            'is_burn_after_read': msg.is_burn_after_read,
            'voice_duration': msg.voice_duration
        })
        
        if msg.sender_id != current_user.id and not msg.is_read:
            msg.is_read = True
    
    db.session.commit()
    
    return render_template('secret_chat.html', 
                         secret_chat=secret_chat, 
                         other_user=other_user, 
                         messages=decrypted_messages)

@app.route('/send_secret', methods=['POST'])
@login_required
def send_secret():
    chat_id = int(request.form['chat_id'])
    secret_chat = db.session.get(SecretChat, chat_id)
    
    if not secret_chat:
        return jsonify({'error': 'Чат не найден'}), 404
    
    if secret_chat.user1_id != current_user.id and secret_chat.user2_id != current_user.id:
        return jsonify({'error': 'Нет доступа'}), 403
    
    other_user_id = secret_chat.user2_id if secret_chat.user1_id == current_user.id else secret_chat.user1_id
    content = request.form.get('content', '')
    burn_after_read = request.form.get('burn_after_read') == 'true'
    
    encrypted_content = encrypt_message(content, current_user.id, other_user_id)
    
    msg = SecretMessage(
        encrypted_content=encrypted_content,
        file_path=request.form.get('file_path'),
        file_name=request.form.get('file_name'),
        file_type=request.form.get('file_type'),
        sender_id=current_user.id,
        secret_chat_id=chat_id,
        voice_duration=request.form.get('voice_duration', 0),
        is_burn_after_read=burn_after_read,
        burn_after_read_timer=5 if burn_after_read else 0
    )
    db.session.add(msg)
    db.session.commit()
    
    return redirect(url_for('secret_chat', chat_id=chat_id))

@app.route('/get_secret_messages/<int:chat_id>/<int:last_id>')
@login_required
def get_secret_messages(chat_id, last_id):
    secret_chat = db.session.get(SecretChat, chat_id)
    if not secret_chat:
        return jsonify([])
    
    if secret_chat.user1_id != current_user.id and secret_chat.user2_id != current_user.id:
        return jsonify([])
    
    other_user_id = secret_chat.user2_id if secret_chat.user1_id == current_user.id else secret_chat.user1_id
    
    messages = SecretMessage.query.filter(
        SecretMessage.secret_chat_id == chat_id,
        SecretMessage.id > last_id
    ).order_by(SecretMessage.timestamp).all()
    
    result = []
    for msg in messages:
        decrypted_content = decrypt_message(msg.encrypted_content, current_user.id, other_user_id)
        result.append({
            'id': msg.id,
            'content': decrypted_content,
            'file_path': msg.file_path,
            'file_name': msg.file_name,
            'file_type': msg.file_type,
            'timestamp': msg.timestamp.strftime('%H:%M'),
            'is_own': msg.sender_id == current_user.id,
            'voice_duration': msg.voice_duration,
            'is_burn_after_read': msg.is_burn_after_read
        })
        
        if msg.sender_id != current_user.id and not msg.is_read:
            msg.is_read = True
    
    db.session.commit()
    return jsonify(result)

@app.route('/secret_chats')
@login_required
def secret_chats():
    secret_chats_list = SecretChat.query.filter(
        (SecretChat.user1_id == current_user.id) | (SecretChat.user2_id == current_user.id),
        SecretChat.is_active == True
    ).all()
    
    chats_data = []
    for sc in secret_chats_list:
        other_id = sc.user2_id if sc.user1_id == current_user.id else sc.user1_id
        other_user = db.session.get(User, other_id)
        last_msg = SecretMessage.query.filter_by(secret_chat_id=sc.id).order_by(SecretMessage.timestamp.desc()).first()
        
        chats_data.append({
            'id': sc.id,
            'other_user': other_user,
            'last_msg': last_msg
        })
    
    return render_template('secret_chats.html', secret_chats=chats_data)

# ========== ГОЛОСОВЫЕ КАНАЛЫ ==========
@app.route('/create_voice_channel', methods=['POST'])
@login_required
def create_voice_channel():
    name = request.form.get('name')
    if not name:
        flash('Введите название канала', 'danger')
        return redirect(url_for('voice_channels'))
    
    channel = VoiceChannel(name=name, created_by=current_user.id)
    db.session.add(channel)
    db.session.commit()
    
    flash(f'🎤 Голосовой канал "{name}" создан!', 'success')
    return redirect(url_for('voice_channels'))

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

@app.route('/join_voice_channel/<int:channel_id>', methods=['POST'])
@login_required
def join_voice_channel(channel_id):
    existing = VoiceChannelMember.query.filter_by(channel_id=channel_id, user_id=current_user.id).first()
    if not existing:
        member = VoiceChannelMember(channel_id=channel_id, user_id=current_user.id)
        db.session.add(member)
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

@app.route('/get_voice_channel_members/<int:channel_id>')
@login_required
def get_voice_channel_members(channel_id):
    members = VoiceChannelMember.query.filter_by(channel_id=channel_id).all()
    result = []
    for m in members:
        result.append({
            'id': m.user.id,
            'username': m.user.username,
            'avatar': m.user.avatar
        })
    return jsonify(result)

# ========== КАНАЛЫ ==========
@app.route('/channels')
@login_required
def channels_list():
    my_channels = Channel.query.filter_by(created_by=current_user.id).all()
    subscribed = ChannelSubscriber.query.filter_by(user_id=current_user.id).all()
    subscribed_ids = [s.channel_id for s in subscribed]
    subscribed_channels = Channel.query.filter(Channel.id.in_(subscribed_ids)).all() if subscribed_ids else []
    popular = Channel.query.order_by(Channel.subscribers_count.desc()).limit(10).all()
    
    return render_template('channels.html', 
                         my_channels=my_channels,
                         subscribed_channels=subscribed_channels,
                         popular=popular)

@app.route('/channel/<string:identifier>')
@login_required
def channel_view(identifier):
    if identifier.startswith('@'):
        channel = Channel.query.filter_by(username=identifier[1:]).first()
    else:
        channel = Channel.query.get(int(identifier))
    
    if not channel:
        flash('Канал не найден', 'danger')
        return redirect(url_for('channels_list'))
    
    is_subscribed = ChannelSubscriber.query.filter_by(channel_id=channel.id, user_id=current_user.id).first() is not None
    is_admin = channel.created_by == current_user.id
    
    posts = ChannelPost.query.filter_by(channel_id=channel.id).order_by(ChannelPost.timestamp.desc()).all()
    
    for post in posts:
        post.comments = ChannelComment.query.filter_by(post_id=post.id).order_by(ChannelComment.timestamp.asc()).all()
    
    return render_template('channel.html', 
                         channel=channel, 
                         posts=posts, 
                         is_subscribed=is_subscribed,
                         is_admin=is_admin)

@app.route('/channel/create', methods=['GET', 'POST'])
@login_required
def channel_create():
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        description = request.form.get('description', '')
        
        if not name:
            flash('Название канала обязательно', 'danger')
            return redirect(url_for('channel_create'))
        
        if username and Channel.query.filter_by(username=username).first():
            flash('Такой @username канала уже занят', 'danger')
            return redirect(url_for('channel_create'))
        
        channel = Channel(
            name=name,
            username=username,
            description=description,
            created_by=current_user.id
        )
        db.session.add(channel)
        db.session.commit()
        
        flash(f'Канал "{name}" создан!', 'success')
        return redirect(url_for('channel_view', identifier=channel.id))
    
    return render_template('channel_create.html')

@app.route('/channel/subscribe/<int:channel_id>', methods=['POST'])
@login_required
def channel_subscribe(channel_id):
    existing = ChannelSubscriber.query.filter_by(channel_id=channel_id, user_id=current_user.id).first()
    if not existing:
        sub = ChannelSubscriber(channel_id=channel_id, user_id=current_user.id)
        db.session.add(sub)
        
        channel = Channel.query.get(channel_id)
        channel.subscribers_count += 1
        db.session.commit()
        flash('Вы подписались на канал!', 'success')
    else:
        db.session.delete(existing)
        channel = Channel.query.get(channel_id)
        channel.subscribers_count -= 1
        db.session.commit()
        flash('Вы отписались от канала', 'info')
    
    return redirect(url_for('channel_view', identifier=channel_id))

@app.route('/channel/<int:channel_id>/upload_avatar', methods=['POST'])
@login_required
def upload_channel_avatar(channel_id):
    channel = Channel.query.get(channel_id)
    if not channel or channel.created_by != current_user.id:
        flash('Нет прав', 'danger')
        return redirect(url_for('channel_view', identifier=channel_id))
    
    if 'avatar' in request.files:
        f = request.files['avatar']
        if f and allowed_file(f.filename):
            ext = f.filename.rsplit('.', 1)[1].lower()
            name = f"channel_avatar_{channel_id}_{uuid.uuid4().hex}.{ext}"
            f.save(os.path.join(AVATAR_FOLDER, name))
            
            if channel.avatar != 'channel_default.png':
                old = os.path.join(AVATAR_FOLDER, channel.avatar)
                if os.path.exists(old):
                    os.remove(old)
            
            channel.avatar = name
            db.session.commit()
            flash('Аватар канала обновлён!', 'success')
    
    return redirect(url_for('channel_view', identifier=channel_id))

@app.route('/channel/post/<int:channel_id>', methods=['POST'])
@login_required
def channel_post_create(channel_id):
    channel = Channel.query.get(channel_id)
    if not channel or channel.created_by != current_user.id:
        flash('Нет прав для публикации', 'danger')
        return redirect(url_for('channel_view', identifier=channel_id))
    
    content = request.form.get('content', '')
    files = request.files.getlist('files')
    
    if not content and not files:
        flash('Введите текст или прикрепите файлы', 'danger')
        return redirect(url_for('channel_view', identifier=channel_id))
    
    post = ChannelPost(
        content=content,
        author_id=current_user.id,
        channel_id=channel_id
    )
    db.session.add(post)
    db.session.commit()
    
    attachments = []
    for f in files:
        if f and f.filename and allowed_file(f.filename):
            ext = f.filename.rsplit('.', 1)[1].lower()
            name = f"channel_{channel_id}_{post.id}_{uuid.uuid4().hex}.{ext}"
            f.save(os.path.join(FILE_FOLDER, name))
            
            if ext in ['png','jpg','jpeg','gif','webp','bmp']:
                file_type = 'image'
            elif ext in ['mp3','wav','ogg','flac','m4a']:
                file_type = 'audio'
            elif ext in ['mp4','avi','mov','mkv','webm']:
                file_type = 'video'
            else:
                file_type = 'document'
            
            attachments.append({
                'path': f'/static/uploads/{name}',
                'name': f.filename,
                'type': file_type
            })
    
    post.attachments = json.dumps(attachments)
    db.session.commit()
    
    flash('Пост опубликован!', 'success')
    return redirect(url_for('channel_view', identifier=channel_id))

@app.route('/channel/comment/<int:post_id>', methods=['POST'])
@login_required
def channel_comment_create(post_id):
    post = ChannelPost.query.get(post_id)
    if not post:
        flash('Пост не найден', 'danger')
        return redirect(url_for('channels_list'))
    
    if not post.comments_enabled:
        flash('Комментарии отключены', 'danger')
        return redirect(url_for('channel_view', identifier=post.channel_id))
    
    content = request.form.get('content')
    if not content:
        flash('Введите текст комментария', 'danger')
        return redirect(url_for('channel_view', identifier=post.channel_id))
    
    comment = ChannelComment(
        content=content,
        post_id=post_id,
        user_id=current_user.id
    )
    db.session.add(comment)
    db.session.commit()
    
    return redirect(url_for('channel_view', identifier=post.channel_id))

@app.route('/api/channels/search')
@login_required
def api_channels_search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    
    channels = Channel.query.filter(
        (Channel.name.ilike(f'%{query}%')) | 
        (Channel.username.ilike(f'%{query}%'))
    ).limit(20).all()
    
    result = []
    for ch in channels:
        result.append({
            'id': ch.id,
            'name': ch.name,
            'username': f'@{ch.username}' if ch.username else None,
            'avatar': ch.avatar,
            'subscribers': ch.subscribers_count
        })
    
    return jsonify(result)

@app.route('/channel/post/edit/<int:post_id>', methods=['POST'])
@login_required
def edit_channel_post(post_id):
    post = ChannelPost.query.get(post_id)
    if not post or post.channel.created_by != current_user.id:
        return jsonify({'error': 'Нет прав'}), 403
    
    data = request.get_json()
    post.content = data.get('content', post.content)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/channel/post/delete/<int:post_id>', methods=['POST'])
@login_required
def delete_channel_post(post_id):
    post = ChannelPost.query.get(post_id)
    if not post or post.channel.created_by != current_user.id:
        return jsonify({'error': 'Нет прав'}), 403
    
    if post.attachments:
        attachments = json.loads(post.attachments)
        for att in attachments:
            file_path = os.path.join(FILE_FOLDER, os.path.basename(att['path']))
            if os.path.exists(file_path):
                os.remove(file_path)
    
    if post.file_path and os.path.exists(os.path.join(FILE_FOLDER, os.path.basename(post.file_path))):
        os.remove(os.path.join(FILE_FOLDER, os.path.basename(post.file_path)))
    
    db.session.delete(post)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/channel/delete/<int:channel_id>', methods=['POST'])
@login_required
def delete_channel(channel_id):
    channel = Channel.query.get(channel_id)
    if not channel or channel.created_by != current_user.id:
        return jsonify({'error': 'Нет прав'}), 403
    
    posts = ChannelPost.query.filter_by(channel_id=channel_id).all()
    for post in posts:
        if post.attachments:
            attachments = json.loads(post.attachments)
            for att in attachments:
                file_path = os.path.join(FILE_FOLDER, os.path.basename(att['path']))
                if os.path.exists(file_path):
                    os.remove(file_path)
        if post.file_path:
            file_path = os.path.join(FILE_FOLDER, os.path.basename(post.file_path))
            if os.path.exists(file_path):
                os.remove(file_path)
        db.session.delete(post)
    
    ChannelComment.query.filter_by(channel_id=channel_id).delete()
    ChannelSubscriber.query.filter_by(channel_id=channel_id).delete()
    
    db.session.delete(channel)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/channel/edit/<int:channel_id>', methods=['POST'])
@login_required
def edit_channel(channel_id):
    channel = Channel.query.get(channel_id)
    if not channel or channel.created_by != current_user.id:
        return jsonify({'error': 'Нет прав'}), 403
    
    data = request.get_json()
    channel.name = data.get('name', channel.name)
    channel.description = data.get('description', channel.description)
    channel.username = data.get('username', channel.username)
    db.session.commit()
    
    return jsonify({'success': True})

# ========== СТИКЕРЫ ==========
@app.route('/stickers')
@login_required
def stickers_page():
    user_packs = UserSticker.query.filter_by(user_id=current_user.id).all()
    packs = []
    for up in user_packs:
        pack = StickerPack.query.get(up.pack_id)
        if pack:
            stickers = Sticker.query.filter_by(pack_id=pack.id).order_by(Sticker.order_num).all()
            packs.append({'id': pack.id, 'title': pack.title, 'stickers': stickers})
    return render_template('stickers.html', packs=packs)

@app.route('/stickers/send/<int:sticker_id>', methods=['POST'])
@login_required
def send_sticker(sticker_id):
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    sticker = Sticker.query.get(sticker_id)
    
    if sticker:
        msg = Message(
            content=f'[СТИКЕР] {sticker.emoji}',
            file_path=sticker.file_path,
            file_type='sticker',
            sender_id=current_user.id,
            receiver_id=receiver_id
        )
        db.session.add(msg)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Стикер не найден'}), 404

@app.route('/stickers/api')
@login_required
def stickers_api():
    user_packs = UserSticker.query.filter_by(user_id=current_user.id).all()
    stickers_list = []
    for up in user_packs:
        pack = StickerPack.query.get(up.pack_id)
        if pack:
            for s in Sticker.query.filter_by(pack_id=pack.id).all():
                stickers_list.append({'id': s.id, 'emoji': s.emoji, 'url': s.file_path})
    return jsonify(stickers_list)

@app.route('/upload_sticker_by_url', methods=['POST'])
@login_required
def upload_sticker_by_url():
    data = request.get_json()
    url = data.get('url')
    receiver_id = data.get('receiver_id')
    
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

# ========== ПОДАРКИ ==========
@app.route('/gifts/send', methods=['POST'])
@login_required
def send_gift():
    data = request.get_json()
    to_user_id = data.get('to_user_id')
    gift_type = data.get('gift_type')
    gift_id = data.get('gift_id')
    message = data.get('message', '')
    
    to_user = User.query.get(to_user_id)
    if not to_user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    if gift_type == 'sticker_pack':
        item = StickerPack.query.get(gift_id)
        if not item:
            return jsonify({'error': 'Стикерпак не найден'}), 404
        price = item.price
    elif gift_type == 'premium_month':
        price = 299
    else:
        return jsonify({'error': 'Неверный тип подарка'}), 400
    
    gift = Gift(
        from_user_id=current_user.id,
        to_user_id=to_user_id,
        gift_type=gift_type,
        gift_id=gift_id,
        message=message
    )
    db.session.add(gift)
    db.session.commit()
    
    return jsonify({'success': True, 'price': price})

@app.route('/gifts/my')
@login_required
def my_gifts():
    gifts = Gift.query.filter_by(to_user_id=current_user.id, is_used=False).all()
    gifts_data = []
    for g in gifts:
        from_user = User.query.get(g.from_user_id)
        gift_info = {'type': g.gift_type, 'id': g.gift_id, 'message': g.message}
        
        if g.gift_type == 'sticker_pack':
            pack = StickerPack.query.get(g.gift_id)
            gift_info['name'] = pack.title if pack else 'Стикерпак'
        elif g.gift_type == 'premium_month':
            gift_info['name'] = 'Premium подписка на месяц'
        
        gifts_data.append({
            'id': g.id,
            'from_user': from_user,
            'gift': gift_info,
            'created_at': g.created_at
        })
    
    return render_template('my_gifts.html', gifts=gifts_data)

@app.route('/gifts/use/<int:gift_id>', methods=['POST'])
@login_required
def use_gift(gift_id):
    gift = Gift.query.get(gift_id)
    if not gift or gift.to_user_id != current_user.id:
        return jsonify({'error': 'Подарок не найден'}), 404
    
    if gift.is_used:
        return jsonify({'error': 'Подарок уже использован'}), 400
    
    if gift.gift_type == 'sticker_pack':
        existing = UserSticker.query.filter_by(user_id=current_user.id, pack_id=gift.gift_id).first()
        if not existing:
            user_pack = UserSticker(user_id=current_user.id, pack_id=gift.gift_id)
            db.session.add(user_pack)
    elif gift.gift_type == 'premium_month':
        sub = Subscription.query.filter_by(user_id=current_user.id).first()
        if not sub:
            sub = Subscription(user_id=current_user.id)
            db.session.add(sub)
        sub.plan = 'premium'
        sub.expires_at = datetime.utcnow() + timedelta(days=30)
    
    gift.is_used = True
    db.session.commit()
    
    return jsonify({'success': True})

# ========== ТЕМЫ ==========
@app.route('/themes')
@login_required
def themes_list():
    free_themes = CustomTheme.query.filter_by(is_premium=False).all()
    premium_themes = CustomTheme.query.filter_by(is_premium=True).all()
    
    user_themes = UserTheme.query.filter_by(user_id=current_user.id).all()
    user_theme_ids = [ut.theme_id for ut in user_themes]
    
    current_theme = None
    if current_user.current_theme_id:
        current_theme = CustomTheme.query.get(current_user.current_theme_id)
    
    return render_template('themes.html', 
                         free_themes=free_themes,
                         premium_themes=premium_themes,
                         user_theme_ids=user_theme_ids,
                         current_theme=current_theme)

@app.route('/themes/apply/<int:theme_id>', methods=['POST'])
@login_required
def apply_theme(theme_id):
    theme = CustomTheme.query.get(theme_id)
    if not theme:
        return jsonify({'error': 'Тема не найдена'}), 404
    
    if theme.is_premium:
        user_has = UserTheme.query.filter_by(user_id=current_user.id, theme_id=theme_id).first()
        if not user_has:
            return jsonify({'error': 'Тема не куплена'}), 403
    
    current_user.current_theme_id = theme_id
    db.session.commit()
    
    return jsonify({'success': True, 'theme': {
        'primary': theme.primary_color,
        'secondary': theme.secondary_color,
        'bubble_sent': theme.bubble_color_sent,
        'bubble_received': theme.bubble_color_received,
        'text': theme.text_color
    }})

@app.route('/themes/purchase/<int:theme_id>', methods=['POST'])
@login_required
def purchase_theme(theme_id):
    theme = CustomTheme.query.get(theme_id)
    if not theme:
        return jsonify({'error': 'Тема не найдена'}), 404
    
    existing = UserTheme.query.filter_by(user_id=current_user.id, theme_id=theme_id).first()
    if existing:
        return jsonify({'error': 'Тема уже куплена'}), 400
    
    if theme.is_premium and theme.price > 0:
        pass
    
    user_theme = UserTheme(user_id=current_user.id, theme_id=theme_id)
    db.session.add(user_theme)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/themes/create', methods=['GET', 'POST'])
@login_required
def create_theme():
    if request.method == 'POST':
        name = request.form.get('name')
        primary = request.form.get('primary_color', '#ff9a9e')
        secondary = request.form.get('secondary_color', '#fecfef')
        bubble_sent = request.form.get('bubble_sent', '#ff6b6b')
        bubble_received = request.form.get('bubble_received', '#ffffff')
        text = request.form.get('text_color', '#333333')
        is_premium = request.form.get('is_premium') == 'on'
        price = float(request.form.get('price', 0))
        
        theme = CustomTheme(
            name=name,
            author_id=current_user.id,
            primary_color=primary,
            secondary_color=secondary,
            bubble_color_sent=bubble_sent,
            bubble_color_received=bubble_received,
            text_color=text,
            is_premium=is_premium,
            price=price
        )
        db.session.add(theme)
        db.session.commit()
        
        flash('Тема создана!', 'success')
        return redirect(url_for('themes_list'))
    
    return render_template('create_theme.html')

# ========== ХРАНИЛИЩЕ ==========
@app.route('/storage')
@login_required
def storage_page():
    storage = CloudStorage.query.filter_by(user_id=current_user.id).first()
    if not storage:
        storage = CloudStorage(user_id=current_user.id)
        db.session.add(storage)
        db.session.commit()
    
    user_files = []
    if os.path.exists(FILE_FOLDER):
        for f in os.listdir(FILE_FOLDER):
            if f.startswith(f"user_{current_user.id}_"):
                file_path = os.path.join(FILE_FOLDER, f)
                user_files.append({
                    'name': f,
                    'size': os.path.getsize(file_path),
                    'modified': datetime.fromtimestamp(os.path.getmtime(file_path)),
                    'url': f'/static/uploads/{f}'
                })
    
    return render_template('storage.html', 
                         storage=storage,
                         user_files=user_files)

@app.route('/storage/upload', methods=['POST'])
@login_required
def upload_to_storage():
    if 'file' not in request.files:
        flash('Нет файла', 'danger')
        return redirect(url_for('storage_page'))
    
    f = request.files['file']
    if f.filename == '':
        flash('Файл не выбран', 'danger')
        return redirect(url_for('storage_page'))
    
    storage = CloudStorage.query.filter_by(user_id=current_user.id).first()
    if not storage:
        storage = CloudStorage(user_id=current_user.id)
        db.session.add(storage)
        db.session.commit()
    
    file_size = len(f.read())
    f.seek(0)
    
    if storage.used_bytes + file_size > storage.total_bytes:
        flash('Недостаточно места в хранилище', 'danger')
        return redirect(url_for('storage_page'))
    
    ext = f.filename.rsplit('.', 1)[1].lower() if '.' in f.filename else 'bin'
    name = f"user_{current_user.id}_{uuid.uuid4().hex}.{ext}"
    f.save(os.path.join(FILE_FOLDER, name))
    
    storage.used_bytes += file_size
    db.session.commit()
    
    flash('Файл загружен!', 'success')
    return redirect(url_for('storage_page'))

@app.route('/storage/delete/<string:filename>', methods=['POST'])
@login_required
def delete_from_storage(filename):
    file_path = os.path.join(FILE_FOLDER, filename)
    if os.path.exists(file_path) and filename.startswith(f"user_{current_user.id}_"):
        file_size = os.path.getsize(file_path)
        os.remove(file_path)
        
        storage = CloudStorage.query.filter_by(user_id=current_user.id).first()
        if storage:
            storage.used_bytes -= file_size
            db.session.commit()
        
        flash('Файл удалён', 'success')
    else:
        flash('Файл не найден', 'danger')
    
    return redirect(url_for('storage_page'))

@app.route('/storage/upgrade', methods=['POST'])
@login_required
def upgrade_storage():
    data = request.get_json()
    additional_gb = data.get('gb', 10)
    price = additional_gb * 50
    
    storage = CloudStorage.query.filter_by(user_id=current_user.id).first()
    if not storage:
        storage = CloudStorage(user_id=current_user.id)
        db.session.add(storage)
        db.session.commit()
    
    storage.total_bytes += additional_gb * 1024 * 1024 * 1024
    storage.upgraded_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True, 'total_gb': storage.total_bytes / (1024**3)})

# ========== СЕМЕЙНЫЕ АККАУНТЫ ==========
@app.route('/family/create', methods=['POST'])
@login_required
def create_family():
    data = request.get_json()
    name = data.get('name', 'Моя семья')
    
    family = FamilyAccount(owner_id=current_user.id, name=name)
    db.session.add(family)
    db.session.commit()
    
    member = FamilyMember(family_id=family.id, user_id=current_user.id)
    db.session.add(member)
    db.session.commit()
    
    return jsonify({'family_id': family.id})

@app.route('/family/invite/<int:family_id>', methods=['POST'])
@login_required
def invite_to_family(family_id):
    family = FamilyAccount.query.get(family_id)
    if not family or family.owner_id != current_user.id:
        return jsonify({'error': 'Нет прав'}), 403
    
    data = request.get_json()
    username = data.get('username')
    user = User.query.filter_by(username=username).first()
    
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    existing = FamilyMember.query.filter_by(family_id=family_id, user_id=user.id).first()
    if existing:
        return jsonify({'error': 'Уже в семье'}), 400
    
    member = FamilyMember(family_id=family_id, user_id=user.id)
    db.session.add(member)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/family/members/<int:family_id>')
@login_required
def family_members(family_id):
    family = FamilyAccount.query.get(family_id)
    if not family:
        return jsonify({'error': 'Семья не найдена'}), 404
    
    members = FamilyMember.query.filter_by(family_id=family_id).all()
    result = []
    for m in members:
        result.append({
            'id': m.user.id,
            'username': m.user.username,
            'avatar': m.user.avatar,
            'is_owner': m.user_id == family.owner_id
        })
    
    return jsonify(result)

# ========== ГРУППЫ ==========
@app.route('/create_group', methods=['POST'])
@login_required
def create_group():
    name = request.form.get('name')
    if not name:
        flash('Название группы обязательно', 'danger')
        return redirect(url_for('chat'))
    group = Group(name=name, created_by=current_user.id)
    db.session.add(group)
    db.session.commit()
    db.session.add(GroupMember(user_id=current_user.id, group_id=group.id, is_admin=True))
    db.session.commit()
    flash(f'Группа "{name}" создана!', 'success')
    return redirect(url_for('chat'))

@app.route('/group/<int:gid>/upload_avatar', methods=['POST'])
@login_required
def upload_group_avatar(gid):
    group = db.session.get(Group, gid)
    if not group:
        flash('Группа не найдена', 'danger')
        return redirect(url_for('chat'))
    
    member = GroupMember.query.filter_by(user_id=current_user.id, group_id=gid).first()
    if not member or not member.is_admin:
        flash('Только администратор может менять аватар группы', 'danger')
        return redirect(url_for('group_info', gid=gid))
    
    if 'avatar' in request.files:
        f = request.files['avatar']
        if f and allowed_file(f.filename):
            ext = f.filename.rsplit('.', 1)[1].lower()
            name = f"group_{gid}_{uuid.uuid4().hex}.{ext}"
            f.save(os.path.join(AVATAR_FOLDER, name))
            if group.avatar != 'group_default.png':
                old = os.path.join(AVATAR_FOLDER, group.avatar)
                if os.path.exists(old):
                    os.remove(old)
            group.avatar = name
            db.session.commit()
            flash('Аватар группы обновлён!', 'success')
    
    return redirect(url_for('group_info', gid=gid))

@app.route('/group/<int:gid>/info')
@login_required
def group_info(gid):
    group = db.session.get(Group, gid)
    if not group:
        flash('Группа не найдена', 'danger')
        return redirect(url_for('chat'))
    
    member = GroupMember.query.filter_by(user_id=current_user.id, group_id=gid).first()
    if not member:
        flash('Вы не участник этой группы', 'danger')
        return redirect(url_for('chat'))
    
    members = GroupMember.query.filter_by(group_id=gid).all()
    members_list = []
    for m in members:
        user = db.session.get(User, m.user_id)
        members_list.append({'user': user, 'is_admin': m.is_admin})
    
    is_admin = member.is_admin
    
    return render_template('group_info.html', group=group, members=members_list, is_admin=is_admin)

@app.route('/add_member/<int:gid>', methods=['POST'])
@login_required
def add_member(gid):
    group = db.session.get(Group, gid)
    if not group:
        flash('Группа не найдена', 'danger')
        return redirect(url_for('chat'))
    
    member = GroupMember.query.filter_by(user_id=current_user.id, group_id=gid).first()
    if not member or not member.is_admin:
        flash('Только администратор может добавлять участников', 'danger')
        return redirect(url_for('group_info', gid=gid))
    
    username = request.form.get('username')
    if not username:
        flash('Введите имя пользователя', 'danger')
        return redirect(url_for('group_info', gid=gid))
    
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('Пользователь не найден', 'danger')
    elif GroupMember.query.filter_by(user_id=user.id, group_id=gid).first():
        flash('Пользователь уже в группе', 'danger')
    else:
        db.session.add(GroupMember(user_id=user.id, group_id=gid))
        db.session.commit()
        flash(f'{user.username} добавлен в группу!', 'success')
    
    return redirect(url_for('group_info', gid=gid))

@app.route('/remove_member/<int:gid>/<int:uid>', methods=['POST'])
@login_required
def remove_member(gid, uid):
    group = db.session.get(Group, gid)
    if not group:
        flash('Группа не найдена', 'danger')
        return redirect(url_for('chat'))
    
    member = GroupMember.query.filter_by(user_id=current_user.id, group_id=gid).first()
    if not member or not member.is_admin:
        flash('Только администратор может удалять участников', 'danger')
        return redirect(url_for('group_info', gid=gid))
    
    if uid == current_user.id:
        flash('Нельзя удалить самого себя', 'danger')
        return redirect(url_for('group_info', gid=gid))
    
    target = GroupMember.query.filter_by(user_id=uid, group_id=gid).first()
    if target:
        db.session.delete(target)
        db.session.commit()
        flash('Пользователь удалён из группы', 'success')
    
    return redirect(url_for('group_info', gid=gid))

@app.route('/group/<int:gid>')
@login_required
def group_chat(gid):
    group = db.session.get(Group, gid)
    if not group:
        flash('Группа не найдена', 'danger')
        return redirect(url_for('chat'))
    member = GroupMember.query.filter_by(user_id=current_user.id, group_id=gid).first()
    if not member:
        flash('Вы не участник этой группы', 'danger')
        return redirect(url_for('chat'))
    messages = GroupMessage.query.filter_by(group_id=gid).order_by(GroupMessage.timestamp).all()
    members = GroupMember.query.filter_by(group_id=gid).all()
    members_list = []
    for m in members:
        user = db.session.get(User, m.user_id)
        members_list.append(user)
    return render_template('group_chat.html', group=group, messages=messages, members=members_list, current_user=current_user)

@app.route('/send_group', methods=['POST'])
@login_required
def send_group():
    content = request.form.get('content', '')
    reply_to_id = request.form.get('reply_to_id', type=int)
    
    content, mentioned_ids = render_mentions(content, current_user.id)
    
    if not content and request.form.get('file_path'):
        content = '📎 Файл'
    
    msg = GroupMessage(
        content=content,
        file_path=request.form.get('file_path'),
        file_name=request.form.get('file_name'),
        file_type=request.form.get('file_type'),
        sender_id=current_user.id,
        group_id=request.form['group_id'],
        voice_duration=request.form.get('voice_duration', 0),
        reply_to_id=reply_to_id,
        mentions=json.dumps(mentioned_ids)
    )
    db.session.add(msg)
    db.session.commit()
    
    return redirect(url_for('group_chat', gid=request.form['group_id']))

# ========== ЧАТ ==========
@app.route('/chat')
@login_required
def chat():
    current_user.last_seen = datetime.utcnow()
    db.session.commit()
    
    blocked_ids = [b.blocked_user_id for b in Blacklist.query.filter_by(user_id=current_user.id).all()]
    
    users = User.query.filter(User.id != current_user.id, ~User.id.in_(blocked_ids)).all()
    groups = Group.query.join(GroupMember).filter(GroupMember.user_id == current_user.id).all()
    secret_chats_list = SecretChat.query.filter(
        (SecretChat.user1_id == current_user.id) | (SecretChat.user2_id == current_user.id),
        SecretChat.is_active == True
    ).all()
    user_channels = Channel.query.join(ChannelSubscriber).filter(ChannelSubscriber.user_id == current_user.id).all()
    
    convs = []
    
    for u in users:
        last = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == u.id)) |
            ((Message.sender_id == u.id) & (Message.receiver_id == current_user.id)),
            ~Message.deleted_for.contains(str(current_user.id))
        ).order_by(Message.timestamp.desc()).first()
        unread = Message.query.filter(Message.sender_id == u.id, Message.receiver_id == current_user.id, Message.is_read == False, ~Message.deleted_for.contains(str(current_user.id))).count()
        convs.append({'type': 'private', 'id': u.id, 'name': u.username, 'username_link': u.username_link, 'avatar': u.avatar, 'status': u.status, 'last': last, 'unread': unread})
    
    for g in groups:
        last = GroupMessage.query.filter_by(group_id=g.id).filter(~GroupMessage.deleted_for.contains(str(current_user.id))).order_by(GroupMessage.timestamp.desc()).first()
        convs.append({'type': 'group', 'id': g.id, 'name': g.name, 'avatar': g.avatar, 'last': last, 'unread': 0})
    
    for sc in secret_chats_list:
        other_id = sc.user2_id if sc.user1_id == current_user.id else sc.user1_id
        other_user = db.session.get(User, other_id)
        last = SecretMessage.query.filter_by(secret_chat_id=sc.id).order_by(SecretMessage.timestamp.desc()).first()
        convs.append({'type': 'secret', 'id': sc.id, 'name': f'🔒 {other_user.username}', 'avatar': other_user.avatar, 'status': 'secret', 'last': last, 'unread': 0})
    
    convs.sort(key=lambda x: x['last'].timestamp if x['last'] and x['last'].timestamp else datetime.min, reverse=True)
    return render_template('chat.html', convs=convs, user_channels=user_channels)

@app.route('/messages/<int:uid>')
@login_required
def messages(uid):
    if Blacklist.query.filter_by(user_id=current_user.id, blocked_user_id=uid).first():
        flash('Вы заблокировали этого пользователя', 'danger')
        return redirect(url_for('chat'))
    if Blacklist.query.filter_by(user_id=uid, blocked_user_id=current_user.id).first():
        flash('Этот пользователь заблокировал вас', 'danger')
        return redirect(url_for('chat'))
    
    other = db.session.get(User, uid)
    if not other:
        flash('Пользователь не найден')
        return redirect(url_for('chat'))
    msgs = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == uid)) |
        ((Message.sender_id == uid) & (Message.receiver_id == current_user.id)),
        ~Message.deleted_for.contains(str(current_user.id))
    ).order_by(Message.timestamp).all()
    for m in msgs:
        if m.receiver_id == current_user.id and not m.is_read:
            m.is_read = True
    db.session.commit()
    return render_template('messages.html', msgs=msgs, other=other)

@app.route('/send', methods=['POST'])
@login_required
def send():
    receiver_id = int(request.form['receiver_id'])
    
    if Blacklist.query.filter_by(user_id=current_user.id, blocked_user_id=receiver_id).first():
        flash('Вы не можете отправлять сообщения заблокированному пользователю', 'danger')
        return redirect(url_for('chat'))
    if Blacklist.query.filter_by(user_id=receiver_id, blocked_user_id=current_user.id).first():
        flash('Этот пользователь заблокировал вас', 'danger')
        return redirect(url_for('chat'))
    
    content = request.form.get('content', '')
    reply_to_id = request.form.get('reply_to_id', type=int)
    
    content, mentioned_ids = render_mentions(content, current_user.id)
    
    if not content and request.form.get('file_path'):
        content = '📎 Файл'
    
    msg = Message(
        content=content,
        file_path=request.form.get('file_path'),
        file_name=request.form.get('file_name'),
        file_type=request.form.get('file_type'),
        sender_id=current_user.id,
        receiver_id=receiver_id,
        voice_duration=request.form.get('voice_duration', 0),
        reply_to_id=reply_to_id,
        mentions=json.dumps(mentioned_ids)
    )
    db.session.add(msg)
    db.session.commit()
    
    return redirect(url_for('messages', uid=receiver_id))

@app.route('/edit_message', methods=['POST'])
@login_required
def edit_message():
    data = request.get_json()
    msg_id = data['msg_id']
    new_content = data['new_content']
    msg_type = data['type']
    
    if msg_type == 'private':
        msg = Message.query.get(msg_id)
        if msg and msg.sender_id == current_user.id:
            content, mentioned_ids = render_mentions(new_content, current_user.id)
            msg.content = content
            msg.mentions = json.dumps(mentioned_ids)
            msg.edited = True
            db.session.commit()
            return jsonify({'success': True})
    elif msg_type == 'group':
        msg = GroupMessage.query.get(msg_id)
        if msg and msg.sender_id == current_user.id:
            content, mentioned_ids = render_mentions(new_content, current_user.id)
            msg.content = content
            msg.mentions = json.dumps(mentioned_ids)
            msg.edited = True
            db.session.commit()
            return jsonify({'success': True})
    return jsonify({'error': 'Нельзя редактировать чужое сообщение'}), 403

@app.route('/delete_message', methods=['POST'])
@login_required
def delete_message():
    data = request.get_json()
    msg_id = data['msg_id']
    msg_type = data['type']
    delete_for_all = data.get('delete_for_all', False)
    
    if msg_type == 'private':
        msg = Message.query.get(msg_id)
        if msg:
            if delete_for_all or msg.sender_id == current_user.id:
                if delete_for_all:
                    db.session.delete(msg)
                else:
                    if msg.deleted_for:
                        msg.deleted_for += f',{current_user.id}'
                    else:
                        msg.deleted_for = str(current_user.id)
                db.session.commit()
                return jsonify({'success': True})
            else:
                return jsonify({'error': 'Нельзя удалить чужое сообщение'}), 403
    elif msg_type == 'group':
        msg = GroupMessage.query.get(msg_id)
        if msg and msg.sender_id == current_user.id:
            if msg.deleted_for:
                msg.deleted_for += f',{current_user.id}'
            else:
                msg.deleted_for = str(current_user.id)
            db.session.commit()
            return jsonify({'success': True})
    return jsonify({'error': 'Сообщение не найдено'}), 404

@app.route('/forward_message', methods=['POST'])
@login_required
def forward_message():
    data = request.get_json()
    msg_id = data['msg_id']
    target_type = data['target_type']
    target_id = data['target_id']
    msg_type = data['msg_type']
    
    if msg_type == 'private':
        original = Message.query.get(msg_id)
        if not original:
            return jsonify({'error': 'Сообщение не найдено'}), 404
        if target_type == 'private':
            new_msg = Message(
                content=original.content,
                file_path=original.file_path,
                file_name=original.file_name,
                file_type=original.file_type,
                sender_id=current_user.id,
                receiver_id=target_id,
                voice_duration=original.voice_duration,
                forwarded_from_id=original.sender_id,
                forwarded_message_id=original.id
            )
            db.session.add(new_msg)
        else:
            new_msg = GroupMessage(
                content=original.content,
                file_path=original.file_path,
                file_name=original.file_name,
                file_type=original.file_type,
                sender_id=current_user.id,
                group_id=target_id,
                voice_duration=original.voice_duration,
                forwarded_from_id=original.sender_id,
                forwarded_message_id=original.id
            )
            db.session.add(new_msg)
    else:
        original = GroupMessage.query.get(msg_id)
        if not original:
            return jsonify({'error': 'Сообщение не найдено'}), 404
        if target_type == 'private':
            new_msg = Message(
                content=original.content,
                file_path=original.file_path,
                file_name=original.file_name,
                file_type=original.file_type,
                sender_id=current_user.id,
                receiver_id=target_id,
                voice_duration=original.voice_duration,
                forwarded_from_id=original.sender_id,
                forwarded_message_id=original.id
            )
            db.session.add(new_msg)
        else:
            new_msg = GroupMessage(
                content=original.content,
                file_path=original.file_path,
                file_name=original.file_name,
                file_type=original.file_type,
                sender_id=current_user.id,
                group_id=target_id,
                voice_duration=original.voice_duration,
                forwarded_from_id=original.sender_id,
                forwarded_message_id=original.id
            )
            db.session.add(new_msg)
    db.session.commit()
    return jsonify({'success': True, 'target_type': target_type, 'target_id': target_id})

@app.route('/toggle_favorite', methods=['POST'])
@login_required
def toggle_favorite():
    data = request.get_json()
    msg_id = data['msg_id']
    msg_type = data['type']
    
    if msg_type == 'private':
        msg = Message.query.get(msg_id)
        if msg and (msg.sender_id == current_user.id or msg.receiver_id == current_user.id):
            msg.is_favorite = not msg.is_favorite
            db.session.commit()
            return jsonify({'success': True, 'is_favorite': msg.is_favorite})
    elif msg_type == 'group':
        msg = GroupMessage.query.get(msg_id)
        if msg:
            msg.is_favorite = not msg.is_favorite
            db.session.commit()
            return jsonify({'success': True, 'is_favorite': msg.is_favorite})
    return jsonify({'error': 'Сообщение не найдено'}), 404

@app.route('/get_reply_preview/<int:msg_id>/<string:msg_type>')
@login_required
def get_reply_preview(msg_id, msg_type):
    if msg_type == 'private':
        msg = Message.query.get(msg_id)
    else:
        msg = GroupMessage.query.get(msg_id)
    if not msg:
        return jsonify({'error': 'Сообщение не найдено'}), 404
    return jsonify({
        'id': msg.id,
        'content': msg.content[:100] if msg.content else '[Файл]',
        'sender_name': msg.sender.username if msg.sender else User.query.get(msg.sender_id).username
    })

@app.route('/get_chats_list')
@login_required
def get_chats_list():
    blocked_ids = [b.blocked_user_id for b in Blacklist.query.filter_by(user_id=current_user.id).all()]
    users = User.query.filter(User.id != current_user.id, ~User.id.in_(blocked_ids)).all()
    groups = Group.query.join(GroupMember).filter(GroupMember.user_id == current_user.id).all()
    secret_chats_list = SecretChat.query.filter(
        (SecretChat.user1_id == current_user.id) | (SecretChat.user2_id == current_user.id),
        SecretChat.is_active == True
    ).all()
    
    chats = []
    for u in users:
        chats.append({'type': 'private', 'id': u.id, 'name': u.username, 'avatar': u.avatar})
    for g in groups:
        chats.append({'type': 'group', 'id': g.id, 'name': g.name, 'avatar': g.avatar})
    for sc in secret_chats_list:
        other_id = sc.user2_id if sc.user1_id == current_user.id else sc.user1_id
        other_user = db.session.get(User, other_id)
        chats.append({'type': 'secret', 'id': sc.id, 'name': f'🔒 {other_user.username}', 'avatar': other_user.avatar})
    return jsonify(chats)

@app.route('/search_users')
@login_required
def search_users():
    query = request.args.get('q', '').lower().strip()
    if not query:
        return jsonify([])
    
    if query.startswith('@'):
        query = query[1:]
    
    users = User.query.filter(
        User.id != current_user.id,
        (User.username.ilike(f'%{query}%')) | 
        (User.username_link.ilike(f'%@{query}%'))
    ).limit(10).all()
    
    result = []
    for user in users:
        result.append({
            'id': user.id,
            'username': user.username,
            'username_link': user.username_link if user.username_link else f'@{user.username}',
            'avatar': user.avatar
        })
    return jsonify(result)

@app.route('/get_mention_notifications')
@login_required
def get_mention_notifications():
    private_mentions = Message.query.filter(
        Message.receiver_id == current_user.id,
        Message.is_read == False,
        Message.mentions != '',
        Message.mentions.contains(str(current_user.id))
    ).count()
    
    group_mentions = GroupMessage.query.filter(
        GroupMessage.group_id.in_([gm.group_id for gm in GroupMember.query.filter_by(user_id=current_user.id).all()]),
        GroupMessage.mentions != '',
        GroupMessage.mentions.contains(str(current_user.id))
    ).count()
    
    return jsonify({'count': private_mentions + group_mentions})

@app.route('/get_new_messages/<int:last_id>/<int:receiver_id>')
@login_required
def get_new_messages(last_id, receiver_id):
    if Blacklist.query.filter_by(user_id=current_user.id, blocked_user_id=receiver_id).first():
        return jsonify([])
    if Blacklist.query.filter_by(user_id=receiver_id, blocked_user_id=current_user.id).first():
        return jsonify([])
    
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
            'forwarded_from_name': m.forwarded_from.username if m.forwarded_from else None,
            'mentions': m.mentions
        })
    return jsonify(result)

@app.route('/get_new_group_messages/<int:last_id>/<int:group_id>')
@login_required
def get_new_group_messages(last_id, group_id):
    member = GroupMember.query.filter_by(user_id=current_user.id, group_id=group_id).first()
    if not member:
        return jsonify([])
    
    msgs = GroupMessage.query.filter(
        GroupMessage.group_id == group_id,
        GroupMessage.id > last_id,
        ~GroupMessage.deleted_for.contains(str(current_user.id))
    ).order_by(GroupMessage.timestamp).all()
    
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
            'sender_name': m.sender.username if m.sender else 'Unknown',
            'voice_duration': m.voice_duration,
            'edited': m.edited,
            'reply_to_id': m.reply_to_id,
            'is_favorite': m.is_favorite,
            'is_pinned': m.is_pinned,
            'forwarded_from_id': m.forwarded_from_id,
            'forwarded_from_name': m.forwarded_from.username if m.forwarded_from else None,
            'mentions': m.mentions
        })
    return jsonify(result)

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)