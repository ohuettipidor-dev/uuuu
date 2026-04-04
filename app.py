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

UPLOAD_FOLDER_AVATARS = 'static/avatars'
os.makedirs(UPLOAD_FOLDER_AVATARS, exist_ok=True)

UPLOAD_FOLDER_FILES = 'static/uploads'
os.makedirs(UPLOAD_FOLDER_FILES, exist_ok=True)

app.config['UPLOAD_FOLDER_AVATARS'] = UPLOAD_FOLDER_AVATARS
app.config['UPLOAD_FOLDER_FILES'] = UPLOAD_FOLDER_FILES
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx', 'txt', 'zip'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
    
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))

class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

class GroupMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    file_name = db.Column(db.String(200), nullable=True)
    file_type = db.Column(db.String(50), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    sender = db.relationship('User', foreign_keys=[sender_id])

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            flash('Имя пользователя уже занято', 'danger')
        else:
            user = User(username=username, password=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            flash('Регистрация успешна!', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            user.status = 'online'
            user.last_seen = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('chat'))
        flash('Неверное имя пользователя или пароль', 'danger')
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
            file = request.files['avatar']
            if file and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                filename = f"avatar_{current_user.id}_{uuid.uuid4().hex}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER_AVATARS'], filename)
                file.save(filepath)
                current_user.avatar = filename
                db.session.commit()
                flash('Аватар обновлён!', 'success')
        return redirect(url_for('profile'))
    return render_template('profile.html', user=current_user)

@app.route('/upload_file', methods=['POST'])
@login_required
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'Нет файла'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Файл не выбран'}), 400
        
        if file and allowed_file(file.filename):
            original_filename = file.filename
            ext = original_filename.rsplit('.', 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER_FILES'], filename)
            file.save(filepath)
            
            if ext in ['png', 'jpg', 'jpeg', 'gif']:
                file_type = 'image'
            else:
                file_type = 'document'
            
            return jsonify({
                'file_path': f'/static/uploads/{filename}',
                'file_name': original_filename,
                'file_type': file_type
            })
        
        return jsonify({'error': 'Неподдерживаемый формат'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/create_group', methods=['POST'])
@login_required
def create_group():
    name = request.form['name']
    group = Group(name=name, created_by=current_user.id)
    db.session.add(group)
    db.session.commit()
    
    member = GroupMember(user_id=current_user.id, group_id=group.id)
    db.session.add(member)
    db.session.commit()
    
    flash(f'Группа "{name}" создана!', 'success')
    return redirect(url_for('chat'))

@app.route('/add_member/<int:group_id>', methods=['POST'])
@login_required
def add_member(group_id):
    group = Group.query.get_or_404(group_id)
    
    if group.created_by != current_user.id:
        flash('Только создатель группы может добавлять участников', 'danger')
        return redirect(url_for('group_chat', group_id=group_id))
    
    username = request.form['username']
    user = User.query.filter_by(username=username).first()
    
    if not user:
        flash('Пользователь не найден', 'danger')
    elif user.id == current_user.id:
        flash('Нельзя добавить самого себя', 'danger')
    else:
        existing = GroupMember.query.filter_by(user_id=user.id, group_id=group_id).first()
        if existing:
            flash(f'Пользователь {username} уже в группе', 'danger')
        else:
            member = GroupMember(user_id=user.id, group_id=group_id)
            db.session.add(member)
            db.session.commit()
            flash(f'Пользователь {username} добавлен в группу!', 'success')
    
    return redirect(url_for('group_chat', group_id=group_id))

@app.route('/group/<int:group_id>')
@login_required
def group_chat(group_id):
    group = Group.query.get_or_404(group_id)
    member = GroupMember.query.filter_by(user_id=current_user.id, group_id=group_id).first()
    if not member:
        flash('Вы не участник этой группы', 'danger')
        return redirect(url_for('chat'))
    
    messages = GroupMessage.query.filter_by(group_id=group_id).order_by(GroupMessage.timestamp).all()
    members = GroupMember.query.filter_by(group_id=group_id).all()
    return render_template('group_chat.html', group=group, messages=messages, members=members, current_user=current_user)

@app.route('/send_group_message', methods=['POST'])
@login_required
def send_group_message():
    group_id = request.form['group_id']
    content = request.form.get('content', '')
    file_path = request.form.get('file_path', '')
    file_name = request.form.get('file_name', '')
    file_type = request.form.get('file_type', '')
    
    msg = GroupMessage(
        content=content if content.strip() else None,
        file_path=file_path if file_path else None,
        file_name=file_name if file_name else None,
        file_type=file_type if file_type else None,
        sender_id=current_user.id,
        group_id=group_id
    )
    db.session.add(msg)
    db.session.commit()
    return redirect(url_for('group_chat', group_id=group_id))

@app.route('/chat')
@login_required
def chat():
    current_user.last_seen = datetime.utcnow()
    db.session.commit()
    
    users = User.query.filter(User.id != current_user.id).all()
    groups = Group.query.join(GroupMember).filter(GroupMember.user_id == current_user.id).all()
    
    conversations = []
    for user in users:
        last_msg = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == user.id)) |
            ((Message.sender_id == user.id) & (Message.receiver_id == current_user.id))
        ).order_by(Message.timestamp.desc()).first()
        
        unread = Message.query.filter(
            Message.sender_id == user.id,
            Message.receiver_id == current_user.id,
            Message.is_read == False
        ).count()
        
        conversations.append({
            'type': 'private',
            'id': user.id,
            'name': user.username,
            'avatar': user.avatar,
            'status': user.status,
            'last_message': last_msg,
            'unread_count': unread
        })
    
    for group in groups:
        last_msg = GroupMessage.query.filter_by(group_id=group.id).order_by(GroupMessage.timestamp.desc()).first()
        conversations.append({
            'type': 'group',
            'id': group.id,
            'name': group.name,
            'avatar': None,
            'status': 'group',
            'last_message': last_msg,
            'unread_count': 0
        })
    
    conversations.sort(key=lambda x: x['last_message'].timestamp if x['last_message'] else datetime.min, reverse=True)
    
    return render_template('chat.html', conversations=conversations, current_user=current_user)

@app.route('/get_messages/<int:user_id>')
@login_required
def get_messages(user_id):
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp).all()
    
    unread = Message.query.filter(Message.sender_id == user_id, Message.receiver_id == current_user.id, Message.is_read == False).all()
    for msg in unread:
        msg.is_read = True
    db.session.commit()
    
    return render_template('messages.html', messages=messages, other_user=User.query.get(user_id), current_user=current_user)

@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    receiver_id = request.form['receiver_id']
    content = request.form.get('content', '')
    file_path = request.form.get('file_path', '')
    file_name = request.form.get('file_name', '')
    file_type = request.form.get('file_type', '')
    
    msg = Message(
        content=content if content.strip() else None,
        file_path=file_path if file_path else None,
        file_name=file_name if file_name else None,
        file_type=file_type if file_type else None,
        sender_id=current_user.id,
        receiver_id=receiver_id
    )
    db.session.add(msg)
    db.session.commit()
    return redirect(url_for('get_messages', user_id=receiver_id))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)