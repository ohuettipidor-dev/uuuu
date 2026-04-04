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
os.makedirs(AVATAR_FOLDER, exist_ok=True)
os.makedirs(FILE_FOLDER, exist_ok=True)
os.makedirs(VOICE_FOLDER, exist_ok=True)

app.config['AVATAR_FOLDER'] = AVATAR_FOLDER
app.config['FILE_FOLDER'] = FILE_FOLDER
app.config['VOICE_FOLDER'] = VOICE_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp',
    'mp3', 'wav', 'ogg', 'flac', 'm4a',
    'mp4', 'avi', 'mov', 'mkv', 'webm',
    'pdf', 'doc', 'docx', 'txt', 'zip', 'rar', '7z'
}

def allowed_file(f):
    return '.' in f and f.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

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
    reactions = db.Column(db.Text, default='{}')

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))

class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)

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
    reactions = db.Column(db.Text, default='{}')

@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    return redirect(url_for('chat')) if current_user.is_authenticated else render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        if User.query.filter_by(username=u).first():
            flash('Имя занято', 'danger')
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
    if request.method == 'POST' and 'avatar' in request.files:
        f = request.files['avatar']
        if f and allowed_file(f.filename):
            ext = f.filename.rsplit('.', 1)[1].lower()
            name = f"avatar_{current_user.id}_{uuid.uuid4().hex}.{ext}"
            f.save(os.path.join(AVATAR_FOLDER, name))
            current_user.avatar = name
            db.session.commit()
            flash('Аватар обновлён', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', user=current_user)

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

@app.route('/add_reaction', methods=['POST'])
@login_required
def add_reaction():
    data = request.get_json()
    msg_type = data.get('type')
    msg_id = data.get('msg_id')
    emoji = data.get('emoji')
    import json
    if msg_type == 'private':
        msg = Message.query.get(msg_id)
        if msg:
            reactions = json.loads(msg.reactions) if msg.reactions else {}
            if emoji in reactions:
                if current_user.id in reactions[emoji]:
                    reactions[emoji].remove(current_user.id)
                    if not reactions[emoji]:
                        del reactions[emoji]
                else:
                    reactions[emoji].append(current_user.id)
            else:
                reactions[emoji] = [current_user.id]
            msg.reactions = json.dumps(reactions)
            db.session.commit()
    else:
        msg = GroupMessage.query.get(msg_id)
        if msg:
            reactions = json.loads(msg.reactions) if msg.reactions else {}
            if emoji in reactions:
                if current_user.id in reactions[emoji]:
                    reactions[emoji].remove(current_user.id)
                    if not reactions[emoji]:
                        del reactions[emoji]
                else:
                    reactions[emoji].append(current_user.id)
            else:
                reactions[emoji] = [current_user.id]
            msg.reactions = json.dumps(reactions)
            db.session.commit()
    return jsonify({'success': True})

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
    db.session.add(GroupMember(user_id=current_user.id, group_id=group.id))
    db.session.commit()
    flash(f'Группа "{name}" создана!', 'success')
    return redirect(url_for('chat'))

@app.route('/add_member/<int:gid>', methods=['POST'])
@login_required
def add_member(gid):
    group = Group.query.get(gid)
    if not group or group.created_by != current_user.id:
        flash('Нет прав', 'danger')
        return redirect(url_for('group_chat', gid=gid))
    user = User.query.filter_by(username=request.form['username']).first()
    if not user:
        flash('Пользователь не найден', 'danger')
    elif GroupMember.query.filter_by(user_id=user.id, group_id=gid).first():
        flash('Уже в группе', 'danger')
    else:
        db.session.add(GroupMember(user_id=user.id, group_id=gid))
        db.session.commit()
        flash(f'{user.username} добавлен', 'success')
    return redirect(url_for('group_chat', gid=gid))

@app.route('/group/<int:gid>')
@login_required
def group_chat(gid):
    group = Group.query.get(gid)
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
        user = User.query.get(m.user_id)
        members_list.append(user)
    return render_template('group_chat.html', group=group, messages=messages, members=members_list, current_user=current_user)

@app.route('/send_group', methods=['POST'])
@login_required
def send_group():
    db.session.add(GroupMessage(
        content=request.form.get('content'),
        file_path=request.form.get('file_path'),
        file_name=request.form.get('file_name'),
        file_type=request.form.get('file_type'),
        sender_id=current_user.id,
        group_id=request.form['group_id'],
        voice_duration=request.form.get('voice_duration', 0)
    ))
    db.session.commit()
    return '', 204

@app.route('/chat')
@login_required
def chat():
    current_user.last_seen = datetime.utcnow()
    db.session.commit()
    users = User.query.filter(User.id != current_user.id).all()
    groups = Group.query.join(GroupMember).filter(GroupMember.user_id == current_user.id).all()
    convs = []
    for u in users:
        last = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == u.id)) |
            ((Message.sender_id == u.id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.timestamp.desc()).first()
        unread = Message.query.filter(Message.sender_id == u.id, Message.receiver_id == current_user.id, Message.is_read == False).count()
        convs.append({'type': 'private', 'id': u.id, 'name': u.username, 'avatar': u.avatar, 'status': u.status, 'last': last, 'unread': unread})
    for g in groups:
        last = GroupMessage.query.filter_by(group_id=g.id).order_by(GroupMessage.timestamp.desc()).first()
        convs.append({'type': 'group', 'id': g.id, 'name': g.name, 'last': last, 'unread': 0})
    convs.sort(key=lambda x: x['last'].timestamp if x['last'] else datetime.min, reverse=True)
    return render_template('chat.html', convs=convs)

@app.route('/messages/<int:uid>')
@login_required
def messages(uid):
    other = User.query.get(uid)
    if not other:
        flash('Пользователь не найден')
        return redirect(url_for('chat'))
    msgs = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == uid)) |
        ((Message.sender_id == uid) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp).all()
    for m in msgs:
        if m.receiver_id == current_user.id and not m.is_read:
            m.is_read = True
    db.session.commit()
    return render_template('messages.html', msgs=msgs, other=other)

@app.route('/send', methods=['POST'])
@login_required
def send():
    db.session.add(Message(
        content=request.form.get('content'),
        file_path=request.form.get('file_path'),
        file_name=request.form.get('file_name'),
        file_type=request.form.get('file_type'),
        sender_id=current_user.id,
        receiver_id=request.form['receiver_id'],
        voice_duration=request.form.get('voice_duration', 0)
    ))
    db.session.commit()
    return '', 204

@app.route('/get_new_messages/<int:last_id>/<int:receiver_id>')
@login_required
def get_new_messages(last_id, receiver_id):
    msgs = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == receiver_id)) |
        ((Message.sender_id == receiver_id) & (Message.receiver_id == current_user.id)),
        Message.id > last_id
    ).order_by(Message.timestamp).all()
    result = []
    for m in msgs:
        import json
        result.append({
            'id': m.id,
            'content': m.content,
            'file_path': m.file_path,
            'file_name': m.file_name,
            'file_type': m.file_type,
            'timestamp': m.timestamp.strftime('%H:%M'),
            'is_own': m.sender_id == current_user.id,
            'voice_duration': m.voice_duration,
            'reactions': json.loads(m.reactions) if m.reactions else {}
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
        GroupMessage.id > last_id
    ).order_by(GroupMessage.timestamp).all()
    result = []
    for m in msgs:
        import json
        result.append({
            'id': m.id,
            'content': m.content,
            'file_path': m.file_path,
            'file_name': m.file_name,
            'file_type': m.file_type,
            'timestamp': m.timestamp.strftime('%H:%M'),
            'is_own': m.sender_id == current_user.id,
            'sender_name': m.sender.username,
            'voice_duration': m.voice_duration,
            'reactions': json.loads(m.reactions) if m.reactions else {}
        })
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)