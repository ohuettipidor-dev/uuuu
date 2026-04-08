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

db = SQLAlchemy