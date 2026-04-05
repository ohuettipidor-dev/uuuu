from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import uuid
import re

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

def parse_mentions(text):
    """Находит всех упомянутых пользователей и заменяет @username на маркер [MENTION:id:username]"""
    if not text:
        return text, []
    
    pattern = r'@([a-zA-Z0-9_]+)'
    mentions_found = re.findall(pattern, text)
    mentioned_users = []
    
    for mention in mentions_found:
        user = User.query.filter_by(username_link=f'@{mention}').first()
        if not user:
            user = User.query.filter_by(username=mention).first()
        if user:
            mentioned_users.append({'id': user.id, 'username': mention})
            text = text.replace(f'@{mention}', f'[MENTION:{user.id}:{mention}]')
    
    return text, mentioned_users

def render_mentions_to_html(text):
    """Преобразует маркеры [MENTION:id:username] в HTML-ссылки"""
    if not text:
        return ''
    pattern = r'\[MENTION:(\d+):([^\]]+)\]'
    return re.sub(pattern, r'<a href="/profile/\1" class="mention" data-user-id="\1">@\2</a>', text)

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

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

class Blacklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    blocked_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    
    sender = db.relationship('User', foreign_keys=[sender_id])
    forwarded_from = db.relationship('User', foreign_keys=[forwarded_from_id])

@login_manager.user_loader
def load_user(uid):
    return db.session.get(User, uid)

with app.app_context():
    db.create_all()

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
    content, mentions = parse_mentions(content)
    reply_to_id = request.form.get('reply_to_id', type=int)
    db.session.add(GroupMessage(
        content=content,
        file_path=request.form.get('file_path'),
        file_name=request.form.get('file_name'),
        file_type=request.form.get('file_type'),
        sender_id=current_user.id,
        group_id=request.form['group_id'],
        voice_duration=request.form.get('voice_duration', 0),
        reply_to_id=reply_to_id
    ))
    db.session.commit()
    return redirect(url_for('group_chat', gid=request.form['group_id']))

@app.route('/chat')
@login_required
def chat():
    current_user.last_seen = datetime.utcnow()
    db.session.commit()
    
    blocked_ids = [b.blocked_user_id for b in Blacklist.query.filter_by(user_id=current_user.id).all()]
    
    users = User.query.filter(User.id != current_user.id, ~User.id.in_(blocked_ids)).all()
    groups = Group.query.join(GroupMember).filter(GroupMember.user_id == current_user.id).all()
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
    convs.sort(key=lambda x: x['last'].timestamp if x['last'] and x['last'].timestamp else datetime.min, reverse=True)
    return render_template('chat.html', convs=convs)

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
    content, mentions = parse_mentions(content)
    reply_to_id = request.form.get('reply_to_id', type=int)
    db.session.add(Message(
        content=content,
        file_path=request.form.get('file_path'),
        file_name=request.form.get('file_name'),
        file_type=request.form.get('file_type'),
        sender_id=current_user.id,
        receiver_id=receiver_id,
        voice_duration=request.form.get('voice_duration', 0),
        reply_to_id=reply_to_id
    ))
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
            msg.content = new_content
            msg.edited = True
            db.session.commit()
            return jsonify({'success': True})
    elif msg_type == 'group':
        msg = GroupMessage.query.get(msg_id)
        if msg and msg.sender_id == current_user.id:
            msg.content = new_content
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
    """Возвращает JSON список всех чатов для пересылки сообщений"""
    blocked_ids = [b.blocked_user_id for b in Blacklist.query.filter_by(user_id=current_user.id).all()]
    
    users = User.query.filter(
        User.id != current_user.id, 
        ~User.id.in_(blocked_ids)
    ).all()
    
    groups = Group.query.join(GroupMember).filter(GroupMember.user_id == current_user.id).all()
    
    chats = []
    
    for u in users:
        chats.append({
            'type': 'private', 
            'id': u.id, 
            'name': u.username,
            'avatar': u.avatar
        })
    
    for g in groups:
        chats.append({
            'type': 'group', 
            'id': g.id, 
            'name': g.name,
            'avatar': g.avatar
        })
    
    return jsonify(chats)

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
            'forwarded_from_id': m.forwarded_from_id,
            'forwarded_from_name': m.forwarded_from.username if m.forwarded_from else None
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
            'forwarded_from_id': m.forwarded_from_id,
            'forwarded_from_name': m.forwarded_from.username if m.forwarded_from else None
        })
    return jsonify(result)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)