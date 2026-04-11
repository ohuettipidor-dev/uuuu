from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import uuid
import requests

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
    is_burn_after_read = db.Column(db.Boolean, default=False)

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))

class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)

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

@app.route('/chat')
@login_required
def chat():
    users = User.query.filter(User.id != current_user.id).all()
    secret_chats = SecretChat.query.filter(
        (SecretChat.user1_id == current_user.id) | (SecretChat.user2_id == current_user.id),
        SecretChat.is_active == True
    ).all()
    return render_template('chat.html', users=users, secret_chats=secret_chats)

# ========== ОТПРАВКА И ПОЛУЧЕНИЕ СООБЩЕНИЙ ==========
@app.route('/send', methods=['POST'])
@login_required
def send():
    receiver_id = int(request.form['receiver_id'])
    content = request.form.get('content', '')
    
    if not content and request.form.get('file_path'):
        content = '📎 Файл'
    
    msg = Message(
        content=content,
        file_path=request.form.get('file_path'),
        file_name=request.form.get('file_name'),
        file_type=request.form.get('file_type'),
        sender_id=current_user.id,
        receiver_id=receiver_id,
        voice_duration=int(request.form.get('voice_duration', 0)),
        timestamp=datetime.utcnow()
    )
    db.session.add(msg)
    db.session.commit()
    
    return redirect(url_for('messages', uid=receiver_id))

@app.route('/messages/<int:uid>')
@login_required
def messages(uid):
    other = User.query.get(uid)
    msgs = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == uid)) |
        ((Message.sender_id == uid) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp).all()
    return render_template('messages.html', msgs=msgs, other=other)

@app.route('/get_new_messages/<int:last_id>/<int:receiver_id>')
@login_required
def get_new_messages(last_id, receiver_id):
    msgs = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == receiver_id)) |
        ((Message.sender_id == receiver_id) & (Message.receiver_id == current_user.id)),
        Message.id > last_id
    ).order_by(Message.timestamp.asc()).all()
    
    result = []
    for m in msgs:
        if m.receiver_id == current_user.id and not m.is_read:
            m.is_read = True
        
        result.append({
            'id': m.id,
            'content': m.content,
            'file_path': m.file_path,
            'file_name': m.file_name,
            'file_type': m.file_type,
            'timestamp': m.timestamp.strftime('%H:%M'),
            'is_own': m.sender_id == current_user.id,
            'voice_duration': m.voice_duration
        })
    
    db.session.commit()
    return jsonify(result)

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
    if not secret_chat:
        flash('Чат не найден', 'danger')
        return redirect(url_for('chat'))
    
    other_id = secret_chat.user2_id if secret_chat.user1_id == current_user.id else secret_chat.user1_id
    other_user = User.query.get(other_id)
    messages = SecretMessage.query.filter_by(secret_chat_id=chat_id).order_by(SecretMessage.timestamp).all()
    return render_template('secret_chat.html', secret_chat=secret_chat, other_user=other_user, messages=messages)

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
    result = [{
        'id': m.id,
        'content': m.encrypted_content,
        'file_path': m.file_path,
        'file_name': m.file_name,
        'file_type': m.file_type,
        'timestamp': m.timestamp.strftime('%H:%M'),
        'is_own': m.sender_id == current_user.id,
        'is_burn_after_read': m.is_burn_after_read
    } for m in messages]
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

# ========== ГРУППЫ ==========
@app.route('/create_group', methods=['POST'])
@login_required
def create_group():
    name = request.form.get('name')
    if name:
        group = Group(name=name, created_by=current_user.id)
        db.session.add(group)
        db.session.commit()
        db.session.add(GroupMember(user_id=current_user.id, group_id=group.id))
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
    return render_template('group_chat.html', group=group)

# ========== ВИДЕОЗВОНКИ ==========
signaling_store = {}

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

# ========== СТИКЕРЫ ==========
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)