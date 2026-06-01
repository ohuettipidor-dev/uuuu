from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import uuid
import re
import json
import hashlib
import base64
import requests
import hmac
import random
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend
import json
import requests
import zipfile
import firebase_admin
from firebase_admin import credentials, messaging


YOOMONEY_WALLET = '4100119522166446'
YOOMONEY_TOKEN = '4100119522166446.E6966B58F022F5CC1E6F3AC9E9409E17676AE12DA3DB68F69885448E192A538ACB87CEE93D045E643159D6C9AACE07098E3F5FDF895F77FE268ED68CD358FDBDE1F97AF0D56F6B2D55D87AA2D29B02983119D7E2797D0B481D7F900571BF15812229EC1F6A1430AF29AD6DB07EFAA51D4BBC680293CF0065B00E1C6047AFA6EC'
VAPID_PRIVATE_KEY = "MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQg_gjCYMlsnEqEwve9-aPTyOGeCr7FSMk8N1pyVjjr0LShRANCAARlre50Affy8pB2MI1Qu5sFIHVsdEbSMubEuYigcTXaW_e49z7UjMjggoRUody6Fbpuz_x3NngMjDlQSSApYIrE"
VAPID_PUBLIC_KEY = "BGWt7nQB9_LykHYwjVC7mwUgdWx0RtIy5sS5iKBxNdpb97j3PtSMyOCChFSh3LoVum7P_Hc2eAyMOVBJIClgisQ="
app = Flask(__name__)
@app.after_request
def allow_iframe(response):
    response.headers.pop('X-Frame-Options', None)  # убираем запрет
    response.headers['Content-Security-Policy'] = "frame-ancestors 'self' *"
    return response
app.config['SECRET_KEY'] = 'beargram-secret-key-2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///messenger.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
import json

@app.template_filter('json_decode')
def json_decode_filter(s):
    """Преобразует JSON-строку из базы в объект Python для шаблона"""
    return json.loads(s)
AVATAR_FOLDER = 'static/avatars'
FILE_FOLDER = 'static/uploads'
VOICE_FOLDER = 'static/voices'
STICKER_FOLDER = 'static/stickers'
CUSTOM_STICKER_FOLDER = 'static/stickers/custom'
os.makedirs(AVATAR_FOLDER, exist_ok=True)
os.makedirs(FILE_FOLDER, exist_ok=True)
os.makedirs(VOICE_FOLDER, exist_ok=True)
os.makedirs(STICKER_FOLDER, exist_ok=True)
os.makedirs(CUSTOM_STICKER_FOLDER, exist_ok=True)

app.config['AVATAR_FOLDER'] = AVATAR_FOLDER
app.config['FILE_FOLDER'] = FILE_FOLDER
app.config['VOICE_FOLDER'] = VOICE_FOLDER
app.config['STICKER_FOLDER'] = STICKER_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
os.makedirs('/app/data', exist_ok=True)
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
    if not message:
        return ""
    key = generate_secret_key(user_id, other_id)
    iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(message.encode()) + padder.finalize()
    encrypted = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(iv + encrypted).decode('utf-8')

def decrypt_message(encrypted_message, user_id, other_id):
    if not encrypted_message:
        return ""
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
    birthday = db.Column(db.Date, nullable=True)
    gender = db.Column(db.String(10), default=None)  # 'male', 'female' или None
    sticker_generations_free = db.Column(db.Integer, default=0)   
    daily_likes_count = db.Column(db.Integer, default=0)
    last_likes_reset = db.Column(db.Date, nullable=True)
    last_daily_bonus = db.Column(db.Date, nullable=True)
    phone_number = db.Column(db.String(20), unique=True, nullable=True)
    phone_verified = db.Column(db.Boolean, default=False)
    rating = db.Column(db.Float, default=0.0)
    refund_count = db.Column(db.Integer, default=0)  # счётчик возвратов
    is_private = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    referral_code = db.Column(db.String(20), unique=True, nullable=True)
    invited_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    push_subscription = db.Column(db.Text, nullable=True)
    fcm_token = db.Column(db.String(500), nullable=True)


class SupportTicket(db.Model):
    __tablename__ = 'support_ticket'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='open')  # open, resolved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', foreign_keys=[user_id])

class UserGame(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default='')
    icon = db.Column(db.String(10), default='🎮')
    file_path = db.Column(db.String(500), nullable=False)
    plays_count = db.Column(db.Integer, default=0)
    rating = db.Column(db.Float, default=0.0)
    ratings_count = db.Column(db.Integer, default=0)
    is_approved = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', foreign_keys=[user_id])

class GameSkin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    game_id = db.Column(db.Integer, db.ForeignKey('user_game.id'), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, default='')
    price = db.Column(db.Integer, nullable=False)
    css_content = db.Column(db.Text, nullable=False)
    preview_color = db.Column(db.String(7), default='#f9ca24')
    sales_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.relationship('User', foreign_keys=[author_id])
    game = db.relationship('UserGame', foreign_keys=[game_id])

class SkinPurchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    skin_id = db.Column(db.Integer, db.ForeignKey('game_skin.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    price_paid = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    skin = db.relationship('GameSkin', foreign_keys=[skin_id])
    buyer = db.relationship('User', foreign_keys=[buyer_id])


class Referral(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inviter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    invited_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    referral_code = db.Column(db.String(20), unique=True, nullable=False)
    status = db.Column(db.String(20), default='pending')
    reward_claimed = db.Column(db.Boolean, default=False)
    reward_amount = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    inviter = db.relationship('User', foreign_keys=[inviter_id])
    invited = db.relationship('User', foreign_keys=[invited_id])

class BEARInvoice(db.Model):
    __tablename__ = 'bear_invoice'
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    amount = db.Column(db.Integer, nullable=False)
    description = db.Column(db.String(200), default='')
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    seller = db.relationship('User', foreign_keys=[seller_id])
    buyer = db.relationship('User', foreign_keys=[buyer_id])

class BEARStake(db.Model):
    __tablename__ = 'bear_stake'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(10), default='coins')
    level = db.Column(db.String(20), nullable=False)
    annual_rate = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ends_at = db.Column(db.DateTime, nullable=False)
    last_payout_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    user = db.relationship('User', foreign_keys=[user_id])

class BEARNode(db.Model):
    __tablename__ = 'bear_node'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    level = db.Column(db.String(20), nullable=False)
    annual_rate = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_payout_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    user = db.relationship('User', foreign_keys=[user_id])

class RegistrationAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45))
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow)

class Blacklist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    blocked_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class MusicTrack(db.Model):
    __tablename__ = 'music_track'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), default='Без названия')
    file_path = db.Column(db.String(500), nullable=False)
    listens = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.relationship('User', backref=db.backref('tracks', lazy=True))

class GRRRWithdrawal(db.Model):
    __tablename__ = 'grrr_withdrawal'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    fee = db.Column(db.Float, default=0)
    net_amount = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default='pending')  # pending, sent, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', foreign_keys=[user_id])

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
    sender = db.relationship('User', foreign_keys=[sender_id])
    secret_chat = db.relationship('SecretChat', foreign_keys=[secret_chat_id])

class UserReport(db.Model):
    __tablename__ = 'user_report'
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reported_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='open')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    reporter = db.relationship('User', foreign_keys=[reporter_id])
    reported = db.relationship('User', foreign_keys=[reported_id])

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

class GameReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('user_game.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', foreign_keys=[user_id])
    game = db.relationship('UserGame', foreign_keys=[game_id])

class UserProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True)
    city = db.Column(db.String(100))
    interests = db.Column(db.String(300))
    bio = db.Column(db.Text)
    photo = db.Column(db.String(200))
    preference = db.Column(db.String(10), default='all')  # 'male', 'female', 'all'

class MiningSession(db.Model):
    __tablename__ = 'mining_session'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    hours = db.Column(db.Integer, default=0)
    reward = db.Column(db.Float, default=0.0)
    is_active = db.Column(db.Boolean, default=True)
    user = db.relationship('User', foreign_keys=[user_id])

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    liker_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    liked_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    is_match = db.Column(db.Boolean, default=False)

class GRRRToken(db.Model):
    __tablename__ = 'grrr_token'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    balance = db.Column(db.Float, default=0.0)
    user = db.relationship('User', foreign_keys=[user_id])

class GoldenDonation(db.Model):
    __tablename__ = 'golden_donation'
    id = db.Column(db.Integer, primary_key=True)
    content_id = db.Column(db.Integer, db.ForeignKey('golden_content.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', foreign_keys=[user_id])
    content = db.relationship('GoldenContent', foreign_keys=[content_id])

class PrivateRoom(db.Model):
    __tablename__ = 'private_room'
    id = db.Column(db.Integer, primary_key=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    guest_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    price_per_minute = db.Column(db.Integer, nullable=False, default=100)  # 💎 за минуту
    duration = db.Column(db.Integer, nullable=False, default=10)  # минут
    status = db.Column(db.String(20), default='waiting')  # waiting, active, finished, reported
    started_at = db.Column(db.DateTime, nullable=True)
    ends_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    creator = db.relationship('User', foreign_keys=[creator_id])
    guest = db.relationship('User', foreign_keys=[guest_id])

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

class ShopItem(db.Model):
    __tablename__ = 'shop_item'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    category = db.Column(db.String(50), nullable=False)  # stickers, themes, sounds, premium
    item_type = db.Column(db.String(50), nullable=False)  # sticker_pack, theme, sound, premium
    item_id = db.Column(db.Integer, nullable=True)  # ID связанного объекта
    price = db.Column(db.Integer, nullable=False)
    preview = db.Column(db.String(500), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    sales_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.relationship('User', foreign_keys=[author_id])
    file_path = db.Column(db.String(500), nullable=True)
    stock = db.Column(db.Integer, default=0)
class ShopPurchase(db.Model):
    __tablename__ = 'shop_purchase'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('shop_item.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    price_paid = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    item = db.relationship('ShopItem', foreign_keys=[item_id])
    user = db.relationship('User', foreign_keys=[user_id])

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
    max_users = db.Column(db.Integer, default=0)
    is_private = db.Column(db.Boolean, default=False)
    creator = db.relationship('User', foreign_keys=[created_by])
    group = db.relationship('Group', foreign_keys=[group_id])
    yoomoney_wallet = db.Column(db.String(20), nullable=True)
    is_paid = db.Column(db.Boolean, default=False)
    price_coins = db.Column(db.Integer, default=0)

class GoldenComment(db.Model):
    __tablename__ = 'golden_comment'
    id = db.Column(db.Integer, primary_key=True)
    content_id = db.Column(db.Integer, db.ForeignKey('golden_content.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', foreign_keys=[user_id])
    content = db.relationship('GoldenContent', foreign_keys=[content_id])

class VoiceChannelDonation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('voice_channel.id'), nullable=False)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    message = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    from_user = db.relationship('User', foreign_keys=[from_user_id])
    channel = db.relationship('VoiceChannel', foreign_keys=[channel_id])

class VoiceChannelMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('voice_channel.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_speaking = db.Column(db.Boolean, default=False)
    muted = db.Column(db.Boolean, default=False)
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

class GoldenContent(db.Model):
    __tablename__ = 'golden_content'
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(200), nullable=True)
    views_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.relationship('User', foreign_keys=[author_id])

class GoldenContentView(db.Model):
    __tablename__ = 'golden_content_view'
    id = db.Column(db.Integer, primary_key=True)
    content_id = db.Column(db.Integer, db.ForeignKey('golden_content.id'), nullable=False)
    viewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)

class GoldenFund(db.Model):
    __tablename__ = 'golden_fund'
    id = db.Column(db.Integer, primary_key=True)
    total_pool = db.Column(db.Integer, default=0)
    platform_fee = db.Column(db.Integer, default=0)
    distributed_pool = db.Column(db.Integer, default=0)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    is_distributed = db.Column(db.Boolean, default=False)

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
    yoomoney_wallet = db.Column(db.String(20), nullable=True)
    donation_balance = db.Column(db.Float, default=0.0)
    is_paid = db.Column(db.Boolean, default=False)
    price_coins = db.Column(db.Integer, default=0)
class ChannelSubscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    channel_id = db.Column(db.Integer, db.ForeignKey('channel.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subscribed_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_muted = db.Column(db.Boolean, default=False)
    channel = db.relationship('Channel', foreign_keys=[channel_id])
    user = db.relationship('User', foreign_keys=[user_id])
    subscription_expires = db.Column(db.DateTime, nullable=True)
    channel = db.relationship('Channel', foreign_keys=[channel_id])
    user = db.relationship('User', foreign_keys=[user_id])

class ShopReview(db.Model):
    __tablename__ = 'shop_review'
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('shop_purchase.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    buyer = db.relationship('User', foreign_keys=[buyer_id])
    seller = db.relationship('User', foreign_keys=[seller_id])

class GoldenLike(db.Model):
    __tablename__ = 'golden_like'
    id = db.Column(db.Integer, primary_key=True)
    content_id = db.Column(db.Integer, db.ForeignKey('golden_content.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    content = db.relationship('GoldenContent', foreign_keys=[content_id])
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

class ChannelPostLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('channel_post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    post = db.relationship('ChannelPost', foreign_keys=[post_id])
    user = db.relationship('User', foreign_keys=[user_id])

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', foreign_keys=[user_id])
    contact = db.relationship('User', foreign_keys=[contact_id])

class ChannelCommentLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('channel_comment.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    comment = db.relationship('ChannelComment', foreign_keys=[comment_id])
    user = db.relationship('User', foreign_keys=[user_id])

class ChannelPostView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('channel_post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)
    post = db.relationship('ChannelPost', foreign_keys=[post_id])
    user = db.relationship('User', foreign_keys=[user_id])

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

class WithdrawalRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount_coins = db.Column(db.Integer, nullable=False)
    gross_rub = db.Column(db.Float, nullable=False)
    platform_fee = db.Column(db.Float, default=0.0)
    tax_amount = db.Column(db.Float, default=0.0)
    net_rub = db.Column(db.Float, nullable=False)
    tax_rate = db.Column(db.Float, default=13.0)
    method = db.Column(db.String(50), default='yoomoney')
    wallet = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)
    admin_comment = db.Column(db.Text, default='')
    user = db.relationship('User', foreign_keys=[user_id])

# ========== СТИКЕРЫ И МОНЕТИЗАЦИЯ ==========
class StickerPack(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_premium = db.Column(db.Boolean, default=False)
    price_coins = db.Column(db.Integer, default=0)
    preview = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    author = db.relationship('User', foreign_keys=[author_id])

class Sticker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pack_id = db.Column(db.Integer, db.ForeignKey('sticker_pack.id'), nullable=False)
    emoji = db.Column(db.String(10), default='🐻')
    file_path = db.Column(db.String(500), nullable=False)
    order_num = db.Column(db.Integer, default=0)
    pack = db.relationship('StickerPack', backref='stickers')

class CustomSticker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    emoji = db.Column(db.String(10), default='🐻')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', foreign_keys=[user_id])

class UserStickerPack(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pack_id = db.Column(db.Integer, db.ForeignKey('sticker_pack.id'), nullable=False)
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', foreign_keys=[user_id])
    pack = db.relationship('StickerPack', foreign_keys=[pack_id])

class UserCoins(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    balance = db.Column(db.Integer, default=0)
    user = db.relationship('User', foreign_keys=[user_id])

class AIGeneration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', foreign_keys=[user_id])
# ========== STORIES (ИСТОРИИ) ==========
class Story(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(20), default='image')
    caption = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    views_count = db.Column(db.Integer, default=0)
    user = db.relationship('User', foreign_keys=[user_id])

class StoryView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    story_id = db.Column(db.Integer, db.ForeignKey('story.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)
    story = db.relationship('Story', foreign_keys=[story_id])
    user = db.relationship('User', foreign_keys=[user_id])

# ========== ПЛАТЕЖИ И ЗАКАЗЫ ==========
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_type = db.Column(db.String(50), nullable=False)  # 'premium' или 'coins'
    amount_rub = db.Column(db.Float, nullable=False)       # Цена в рублях
    coins_amount = db.Column(db.Integer, default=0)        # Сколько монет дать
    status = db.Column(db.String(20), default='pending')   # pending, paid, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime, nullable=True)
    user = db.relationship('User', foreign_keys=[user_id])

signaling_store = {}
voice_signals = {}
def get_grrr_balance(user_id):
    grrr = GRRRToken.query.filter_by(user_id=user_id).first()
    if not grrr:
        grrr = GRRRToken(user_id=user_id, balance=0)
        db.session.add(grrr)
        db.session.commit()
    return grrr.balance
        
       
def add_grrr(user_id, amount):
    grrr = GRRRToken.query.filter_by(user_id=user_id).first()
    if not grrr:
        grrr = GRRRToken(user_id=user_id, balance=amount)
        db.session.add(grrr)
    else:
        grrr.balance += amount
    db.session.commit()
    return grrr.balance

def get_user_coins(user_id):
    coins = UserCoins.query.filter_by(user_id=user_id).first()
    if not coins:
        coins = UserCoins(user_id=user_id, balance=100)
        db.session.add(coins)
        db.session.commit()
    return coins

def get_premium_status(user_id):
    sub = Subscription.query.filter_by(user_id=user_id).first()
    if sub and sub.plan == 'premium' and sub.expires_at and sub.expires_at > datetime.utcnow():
        return True
    return False

def activate_premium(user_id, months=1):
    user = db.session.get(User, user_id)
    if not user:
        return False
    
    sub = Subscription.query.filter_by(user_id=user_id).first()
    if not sub:
        sub = Subscription(user_id=user_id)
        db.session.add(sub)
    
    if sub.expires_at and sub.expires_at > datetime.utcnow():
        sub.expires_at = sub.expires_at + timedelta(days=30 * months)
    else:
        sub.expires_at = datetime.utcnow() + timedelta(days=30 * months)
    
    sub.plan = 'premium'
    sub.auto_renew = False
    db.session.commit()
    return True

@login_manager.user_loader
def load_user(uid):
    user = db.session.get(User, uid)
    if user and not user.is_active:
        return None
    return user
with app.app_context():
    db.create_all()
    # Создаём премиум-темы, если их ещё нет
    if not CustomTheme.query.filter_by(name='Золотой медведь').first():
        gold = CustomTheme(
            name='Золотой медведь',
            author_id=1,
            primary_color='#FFD700',
            secondary_color='#FFA500',
            bubble_color_sent='#DAA520',
            bubble_color_received='#FFF8DC',
            text_color='#2C1810',
            is_premium=True,
            price=0
        )
        db.session.add(gold)
    if not CustomTheme.query.filter_by(name='Неоновая ночь').first():
        neon = CustomTheme(
            name='Неоновая ночь',
            author_id=1,
            primary_color='#FF00FF',
            secondary_color='#00FFFF',
            bubble_color_sent='#FF1493',
            bubble_color_received='#191970',
            text_color='#FFFFFF',
            is_premium=True,
            price=0
        )
        db.session.add(neon)
    db.session.commit()
    print("✅ База данных и премиум-темы готовы")

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
        phone = request.form.get('phone', '').strip()

        if p != confirm:
            flash('Пароли не совпадают', 'danger')
            return render_template('register.html')
        if len(p) < 6:
            flash('Пароль должен быть не менее 6 символов', 'danger')
            return render_template('register.html')
        if len(u) < 2 or len(u) > 32:
            flash('Имя пользователя должно быть от 2 до 32 символов', 'danger')
            return render_template('register.html')
        if not re.match(r'^[a-zA-Z0-9_]+$', u):
            flash('Имя пользователя может содержать только буквы, цифры и _', 'danger')
            return render_template('register.html')

        existing_user = User.query.filter_by(username=u).first()
        if existing_user:
            flash('Пользователь с таким именем уже существует', 'danger')
            return render_template('register.html')

        if phone:
            existing_phone = User.query.filter_by(phone_number=phone).first()
            if existing_phone:
                flash('Этот номер телефона уже привязан к другому аккаунту', 'danger')
                return render_template('register.html')

        ip = request.remote_addr
        recent = RegistrationAttempt.query.filter(
            RegistrationAttempt.ip_address == ip,
            RegistrationAttempt.attempted_at > datetime.utcnow() - timedelta(hours=24)
        ).count()
        if recent >= 5:
            flash('Слишком много регистраций с вашего адреса. Попробуйте позже.', 'danger')
            return render_template('register.html')

        import random, string
        ref_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        user = User(username=u, username_link=ul if ul else None,
                   password=generate_password_hash(p),
                   phone_number=phone if phone else None,
                   phone_verified=False,
                   referral_code=ref_code)
        db.session.add(user)
        db.session.commit()

        attempt = RegistrationAttempt(ip_address=ip)
        db.session.add(attempt)
        db.session.commit()

        coins = UserCoins(user_id=user.id, balance=100)
        db.session.add(coins)
        db.session.commit()

        # Начисление заработанного в играх $GRRR после регистрации
        earned = request.args.get('earned', 0)
        if earned:
            try:
                earned_amount = int(earned)
                if earned_amount > 0 and earned_amount <= 10000:
                    grrr = GRRRToken.query.filter_by(user_id=user.id).first()
                    if not grrr:
                        grrr = GRRRToken(user_id=user.id, balance=earned_amount)
                        db.session.add(grrr)
                    else:
                        grrr.balance += earned_amount
                    db.session.commit()
            except:
                pass

        # Обработка реферала
        ref = request.args.get('ref', '')
        if ref:
            inviter = User.query.filter_by(referral_code=ref).first()
            if inviter:
                referral = Referral(
                    inviter_id=inviter.id,
                    invited_id=user.id,
                    referral_code=f"{ref}_{user.id}",
                    status='registered'
                )
                db.session.add(referral)
                coins.balance += 10
                user.invited_by = inviter.id
                db.session.commit()

        flash('Регистрация успешна! +100 кристалайзеров (разблокируйте в профиле).', 'success')
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
@app.route('/verify_phone', methods=['POST'])
@login_required
def verify_phone():
    phone = request.form.get('phone', '').strip()
    code = request.form.get('code', '').strip()

    if 'send_code' in request.form:
        if phone:
            # Проверка, не занят ли номер другим пользователем
            existing = User.query.filter_by(phone_number=phone).first()
            if existing and existing.id != current_user.id:
                flash('Этот номер телефона уже привязан к другому аккаунту', 'danger')
            else:
                current_user.phone_number = phone
                db.session.commit()
                flash('Код отправлен на номер ' + phone, 'info')
        else:
            flash('Введите номер телефона', 'danger')

    elif 'verify_code' in request.form:
        if code == '1234':   # тестовый код
            if not current_user.phone_number:
                flash('Сначала введите номер и отправьте код', 'danger')
            else:
                existing = User.query.filter_by(phone_number=current_user.phone_number).first()
                if existing and existing.id != current_user.id:
                    flash('Этот номер телефона уже привязан к другому аккаунту', 'danger')
                else:
                    current_user.phone_verified = True
                    db.session.commit()
                    flash('Номер подтверждён! Кристаллайзеры разблокированы.', 'success')
        else:
            flash('Неверный код', 'danger')

    return redirect(url_for('profile'))
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
            UserStickerPack.query.filter_by(user_id=current_user.id).delete()
            UserTheme.query.filter_by(user_id=current_user.id).delete()
            CloudStorage.query.filter_by(user_id=current_user.id).delete()
            Gift.query.filter((Gift.from_user_id == current_user.id) | (Gift.to_user_id == current_user.id)).delete()
            FamilyMember.query.filter_by(user_id=current_user.id).delete()
            FamilyAccount.query.filter_by(owner_id=current_user.id).delete()
            CustomSticker.query.filter_by(user_id=current_user.id).delete()
            UserCoins.query.filter_by(user_id=current_user.id).delete()
            AIGeneration.query.filter_by(user_id=current_user.id).delete()
            Order.query.filter_by(user_id=current_user.id).delete()
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
    
    coins = get_user_coins(current_user.id)
    is_premium = get_premium_status(current_user.id)
    sub = Subscription.query.filter_by(user_id=current_user.id).first()
    expires_at = sub.expires_at.strftime('%d.%m.%Y') if sub and sub.expires_at else None

    # Ежедневный бонус премиум-пользователям
    if is_premium:
        today = datetime.utcnow().date()
        if current_user.last_daily_bonus != today:
            coins = get_user_coins(current_user.id)
            coins.balance += 5   # бонус каждый день
            current_user.last_daily_bonus = today
            db.session.commit()
            flash('🎁 Вы получили ежедневные 5 Кристаллайзеров за премиум!', 'success')
    
    grrr_balance = get_grrr_balance(current_user.id)
    
    # ===== ИСПРАВЛЕНО: заменил profile_user на current_user =====
    tracks = MusicTrack.query.filter_by(user_id=current_user.id).order_by(MusicTrack.created_at.desc()).all()
    
    return render_template('profile.html', 
                           user=current_user, 
                           coins=coins, 
                           grrr_balance=grrr_balance, 
                           is_premium=is_premium, 
                           expires_at=expires_at, 
                           tracks=tracks)   # не забудь передать tracks
@app.route('/profile/<int:uid>')
@login_required
def profile_by_id(uid):
    user = db.session.get(User, uid)
    if not user:
        flash('Пользователь не найден', 'danger')
        return redirect(url_for('chat'))
    is_blocked = Blacklist.query.filter_by(user_id=current_user.id, blocked_user_id=uid).first() is not None
    is_contact = Contact.query.filter_by(user_id=current_user.id, contact_id=uid).first() is not None
    profile = UserProfile.query.filter_by(user_id=uid).first()
    tracks = MusicTrack.query.filter_by(user_id=user.id).order_by(MusicTrack.created_at.desc()).all()
    return render_template('profile_public.html', profile_user=user, is_blocked=is_blocked, is_contact=is_contact, profile=profile, tracks=tracks)
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
    flash(f'🔒 Секретный чат с {other_user.username} создан! Сообщения зашифрованы AES-256', 'success')
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
    file_path = request.form.get('file_path')
    file_name = request.form.get('file_name')
    file_type = request.form.get('file_type')
    voice_duration = request.form.get('voice_duration', 0)
    burn_after_read = request.form.get('burn_after_read') == 'true'
    encrypted_content = encrypt_message(content, current_user.id, other_user_id) if content else None
    msg = SecretMessage(
        encrypted_content=encrypted_content,
        file_path=file_path,
        file_name=file_name,
        file_type=file_type,
        sender_id=current_user.id,
        secret_chat_id=chat_id,
        voice_duration=voice_duration,
        is_burn_after_read=burn_after_read
    )
    db.session.add(msg)
    db.session.commit()
    
    if request.form.get('_from_ajax') == 'true':
        return jsonify({'success': True, 'msg_id': msg.id})
    return redirect(url_for('secret_chat', chat_id=chat_id))
@app.route('/golden/comments/<int:content_id>')
@login_required
def golden_comments(content_id):
    comments = GoldenComment.query.filter_by(content_id=content_id).order_by(GoldenComment.created_at.desc()).limit(50).all()
    return jsonify([{
        'id': c.id,
        'username': c.user.username,
        'text': c.text,
        'created_at': c.created_at.strftime('%H:%M')
    } for c in comments])

@app.route('/golden/comment/<int:content_id>', methods=['POST'])
@login_required
def add_golden_comment(content_id):
    text = request.form.get('text', '').strip()
    if not text:
        return jsonify({'error': 'Введите текст'}), 400
    comment = GoldenComment(content_id=content_id, user_id=current_user.id, text=text)
    db.session.add(comment)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/golden/comments_count/<int:content_id>')
@login_required
def golden_comments_count(content_id):
    count = GoldenComment.query.filter_by(content_id=content_id).count()
    return jsonify({'count': count})

@app.route('/upload_secret_file', methods=['POST'])
@login_required
def upload_secret_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Нет файла'}), 400
    f = request.files['file']
    if f.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    if allowed_file(f.filename):
        ext = f.filename.rsplit('.', 1)[1].lower()
        name = f"secret_{current_user.id}_{uuid.uuid4().hex}.{ext}"
        f.save(os.path.join(FILE_FOLDER, name))
        if ext in ['png','jpg','jpeg','gif','webp','bmp']: ft = 'image'
        elif ext in ['mp3','wav','ogg','flac','m4a']: ft = 'audio'
        elif ext in ['mp4','avi','mov','mkv','webm']: ft = 'video'
        else: ft = 'document'
        return jsonify({'path': f'/static/uploads/{name}', 'name': f.filename, 'type': ft})
    return jsonify({'error': 'Формат не поддерживается'}), 400

@app.route('/upload_secret_voice', methods=['POST'])
@login_required
def upload_secret_voice():
    if 'audio' not in request.files:
        return jsonify({'error': 'Нет аудио'}), 400
    f = request.files['audio']
    name = f"secret_voice_{current_user.id}_{uuid.uuid4().hex}.webm"
    f.save(os.path.join(VOICE_FOLDER, name))
    duration = request.form.get('duration', 0)
    return jsonify({'path': f'/static/voices/{name}', 'duration': duration})

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
def secret_chats_list():
    secret_chats = SecretChat.query.filter(
        (SecretChat.user1_id == current_user.id) | (SecretChat.user2_id == current_user.id),
        SecretChat.is_active == True
    ).all()
    chats_data = []
    for sc in secret_chats:
        other_id = sc.user2_id if sc.user1_id == current_user.id else sc.user1_id
        other_user = db.session.get(User, other_id)
        last_msg = SecretMessage.query.filter_by(secret_chat_id=sc.id).order_by(SecretMessage.timestamp.desc()).first()
        chats_data.append({'id': sc.id, 'other_user': other_user, 'last_msg': last_msg})
    return render_template('secret_chats.html', secret_chats=chats_data)
@app.route('/api/secret/burn_message/<int:msg_id>', methods=['POST'])
@login_required
def burn_secret_message(msg_id):
    msg = SecretMessage.query.get(msg_id)
    if not msg:
        return jsonify({'error': 'Сообщение не найдено'}), 404
    
    secret_chat = msg.secret_chat
    if secret_chat.user1_id != current_user.id and secret_chat.user2_id != current_user.id:
        return jsonify({'error': 'Нет доступа'}), 403
    
    # Удаляем файл, если есть
    if msg.file_path:
        filepath = os.path.join(FILE_FOLDER, os.path.basename(msg.file_path))
        if os.path.exists(filepath):
            os.remove(filepath)
    
    db.session.delete(msg)
    db.session.commit()
    
    return jsonify({'success': True})

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
PLATFORM_FEE = 0.25  # если ещё нет

@app.route('/love/private/report/<int:room_id>', methods=['POST'])
@login_required
def report_private_room(room_id):
    room = PrivateRoom.query.get_or_404(room_id)
    if room.guest_id != current_user.id and room.creator_id != current_user.id:
        return jsonify({'error': 'Вы не участник'}), 403

    room.status = 'reported'
    db.session.commit()
    return jsonify({'success': True, 'message': 'Комната закрыта, жалоба отправлена'})

@app.route('/love/rooms/available')
@login_required
def available_private_rooms():
    rooms = PrivateRoom.query.filter_by(status='waiting').order_by(PrivateRoom.created_at.desc()).limit(20).all()
    result = []
    for r in rooms:
        result.append({
            'id': r.id,
            'creator': r.creator.username,
            'creator_avatar': r.creator.avatar,
            'price_per_minute': r.price_per_minute,
            'duration': r.duration,
            'total_cost': r.price_per_minute * r.duration,
            'created_at': r.created_at.isoformat()
        })
    return jsonify(result)

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
# ====================== ГРУППОВЫЕ ЧАТЫ ======================

@app.route('/send_group', methods=['POST'])
@login_required
def send_group():
    group_id = int(request.form['group_id'])
    group = Group.query.get(group_id)
    if not group:
        return jsonify({'error': 'Группа не найдена'}), 404

    # Проверка членства
    if not group.is_member(current_user):
        return jsonify({'error': 'Вы не участник этой группы'}), 403

    content = request.form.get('content', '')
    reply_to_id = request.form.get('reply_to_id', type=int)
    file_path = request.form.get('file_path')
    file_name = request.form.get('file_name')
    file_type = request.form.get('file_type')
    voice_duration = request.form.get('voice_duration', 0, type=int)

    # Обработка упоминаний (если есть функция render_mentions)
    # content, mentioned_ids = render_mentions(content, current_user.id)

    if not content and file_path:
        content = '📎 Файл'

    msg = Message(
        content=content,
        file_path=file_path,
        file_name=file_name,
        file_type=file_type,
        sender_id=current_user.id,
        group_id=group_id,
        receiver_id=None,
        voice_duration=voice_duration,
        reply_to_id=reply_to_id,
        status='sent'
        # mentions=json.dumps(mentioned_ids) если нужно
    )
    db.session.add(msg)
    db.session.commit()

    return jsonify({'success': True, 'message_id': msg.id})


@app.route('/get_new_group_messages/<int:group_id>/<int:last_id>')
@login_required
def get_new_group_messages(group_id, last_id):
    group = Group.query.get(group_id)
    if not group or not group.is_member(current_user):
        return jsonify([])

    msgs = Message.query.filter(
        Message.group_id == group_id,
        Message.id > last_id
    ).order_by(Message.id.asc()).all()

    result = []
    for m in msgs:
        result.append({
            'id': m.id,
            'content': m.content,
            'sender_id': m.sender_id,
            'sender_name': m.sender.username,
            'file_path': m.file_path,
            'file_name': m.file_name,
            'file_type': m.file_type,
            'voice_duration': m.voice_duration,
            'reply_to_id': m.reply_to_id,
            'timestamp': m.timestamp.isoformat() + 'Z',
            'is_own': m.sender_id == current_user.id,
            'status': m.status,
            'edited': m.edited,
            'is_favorite': m.is_favorite,
            'is_pinned': m.is_pinned,
            'forwarded_from_id': m.forwarded_from_id,
            'forwarded_from_name': m.forwarded_from.username if m.forwarded_from else None
        })
    return jsonify(result)


# --- Универсальные действия с сообщениями (поддержка 'group') ---

@app.route('/delete_message', methods=['POST'])
@login_required
def delete_message():
    data = request.get_json()
    msg_id = data['msg_id']
    delete_for_all = data.get('delete_for_all', False)
    msg_type = data.get('type', 'private')  # 'private' или 'group'

    msg = Message.query.get(msg_id)
    if not msg:
        return jsonify({'error': 'Сообщение не найдено'}), 404

    if msg_type == 'group':
        # Проверить, что пользователь участник группы
        group = Group.query.get(msg.group_id)
        if not group or not group.is_member(current_user):
            return jsonify({'error': 'Нет доступа'}), 403
    else:
        if msg.sender_id != current_user.id and msg.receiver_id != current_user.id:
            return jsonify({'error': 'Нет доступа'}), 403

    if delete_for_all and msg_type == 'group':
        # В группе удалить для всех может только автор или админ
        if msg.sender_id != current_user.id:
            member = GroupMember.query.filter_by(group_id=msg.group_id, user_id=current_user.id).first()
            if not member or member.role not in ['owner', 'admin']:
                return jsonify({'error': 'Недостаточно прав'}), 403
        db.session.delete(msg)
    elif delete_for_all and msg_type == 'private':
        if msg.sender_id != current_user.id:
            return jsonify({'error': 'Нельзя удалить чужое сообщение'}), 403
        db.session.delete(msg)
    else:
        # Удалить только у себя (для личных и групп) – можно добавить поле deleted_for
        # Пока просто удаляем сообщение (упрощённо)
        db.session.delete(msg)

    db.session.commit()
    return jsonify({'success': True})


@app.route('/edit_message', methods=['POST'])
@login_required
def edit_message():
    data = request.get_json()
    msg_id = data['msg_id']
    new_content = data['new_content']
    msg_type = data.get('type', 'private')

    msg = Message.query.get(msg_id)
    if not msg or msg.sender_id != current_user.id:
        return jsonify({'error': 'Нельзя редактировать'}), 403

    msg.content = new_content
    msg.edited = True
    db.session.commit()
    return jsonify({'success': True})


@app.route('/toggle_favorite', methods=['POST'])
@login_required
def toggle_favorite():
    data = request.get_json()
    msg_id = data['msg_id']
    msg = Message.query.get(msg_id)
    if not msg:
        return jsonify({'error': 'Сообщение не найдено'}), 404
    # можно добавить проверку, что пользователь имеет доступ к сообщению
    msg.is_favorite = not msg.is_favorite
    db.session.commit()
    return jsonify({'success': True, 'is_favorite': msg.is_favorite})


@app.route('/forward_message', methods=['POST'])
@login_required
def forward_message():
    data = request.get_json()
    msg_id = data['msg_id']
    target_type = data['target_type']  # 'private' или 'group'
    target_id = int(data['target_id'])
    msg_type = data.get('msg_type', 'private')  # тип исходного сообщения

    original = Message.query.get(msg_id)
    if not original:
        return jsonify({'error': 'Исходное сообщение не найдено'}), 404

    # Проверка доступа к исходному сообщению
    if msg_type == 'private':
        if original.sender_id != current_user.id and original.receiver_id != current_user.id:
            return jsonify({'error': 'Нет доступа'}), 403
    else:  # group
        group = Group.query.get(original.group_id)
        if not group or not group.is_member(current_user):
            return jsonify({'error': 'Нет доступа'}), 403

    new_msg = Message(
        content=original.content,
        file_path=original.file_path,
        file_name=original.file_name,
        file_type=original.file_type,
        sender_id=current_user.id,
        voice_duration=original.voice_duration,
        forwarded_from_id=original.id
    )

    if target_type == 'private':
        new_msg.receiver_id = target_id
    elif target_type == 'group':
        new_msg.group_id = target_id

    db.session.add(new_msg)
    db.session.commit()
    return jsonify({'success': True, 'new_msg_id': new_msg.id})


@app.route('/pin_message', methods=['POST'])
@login_required
def pin_message():
    data = request.get_json()
    msg_id = data['msg_id']
    msg_type = data.get('type', 'private')  # 'group' или 'private'

    msg = Message.query.get(msg_id)
    if not msg:
        return jsonify({'error': 'Сообщение не найдено'}), 404

    # Проверка прав
    if msg_type == 'group':
        group = Group.query.get(msg.group_id)
        if not group or not group.is_member(current_user):
            return jsonify({'error': 'Нет доступа'}), 403
        # Разрешить закреплять только админам/овнерам?
        # Пока разрешим всем
    else:
        if msg.sender_id != current_user.id and msg.receiver_id != current_user.id:
            return jsonify({'error': 'Нет доступа'}), 403

    msg.is_pinned = not msg.is_pinned
    db.session.commit()
    return jsonify({'success': True, 'is_pinned': msg.is_pinned})

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
        members_list.append({
            'user': user,
            'is_admin': m.is_admin or group.created_by == user.id
        })
    
    is_admin = member.is_admin or group.created_by == current_user.id
    
    return render_template('group_info.html', 
                         group=group, 
                         members=members_list, 
                         is_admin=is_admin,
                         current_user=current_user)

@app.route('/group/<int:gid>/upload_avatar', methods=['POST'])
@login_required
def upload_group_avatar(gid):
    group = db.session.get(Group, gid)
    if not group:
        flash('Группа не найдена', 'danger')
        return redirect(url_for('chat'))
    
    member = GroupMember.query.filter_by(user_id=current_user.id, group_id=gid).first()
    if not member or not member.is_admin:
        flash('Нет прав для изменения аватара', 'danger')
        return redirect(url_for('group_info', gid=gid))
    
    if 'avatar' in request.files:
        f = request.files['avatar']
        if f and allowed_file(f.filename):
            ext = f.filename.rsplit('.', 1)[1].lower()
            name = f"group_avatar_{gid}_{uuid.uuid4().hex}.{ext}"
            f.save(os.path.join(AVATAR_FOLDER, name))
            if group.avatar != 'group_default.png':
                old = os.path.join(AVATAR_FOLDER, group.avatar)
                if os.path.exists(old):
                    os.remove(old)
            group.avatar = name
            db.session.commit()
            flash('Аватар группы обновлён!', 'success')
    
    return redirect(url_for('group_info', gid=gid))
# Автоматическое создание фонда при запуске
def init_golden_fund():
    with app.app_context():
        active_fund = GoldenFund.query.filter_by(is_distributed=False).first()
        if not active_fund:
            fund = GoldenFund(
                total_pool=100000,
                platform_fee=25000,
                distributed_pool=75000,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=7)
            )
            db.session.add(fund)
            db.session.commit()
            print("✅ Золотой фонд создан автоматически")

# Вызови после создания всех таблиц
with app.app_context():
    db.create_all()
    init_golden_fund()

@app.route('/golden/fund_status')
@login_required
def golden_fund_status():
    fund = GoldenFund.query.filter_by(is_distributed=False).first()
    if not fund:
        return jsonify({'active': False})
    
    # Считаем, сколько уже "заработано" просмотрами
    total_views = db.session.query(db.func.sum(GoldenContent.views_count)).filter(
        GoldenContent.created_at >= fund.start_date,
        GoldenContent.created_at <= fund.end_date
    ).scalar() or 0
    
    # Прогресс — это доля просмотров от максимального (для примера)
    max_views = 10000  # максимальное ожидаемое количество просмотров
    progress = min(1.0, total_views / max_views)
    
    return jsonify({
        'active': True,
        'pool': fund.distributed_pool,
        'distributed': int(total_views),
        'progress': progress,
        'end_date': fund.end_date.isoformat()
    })

@app.route('/golden/donate_to_fund', methods=['POST'])
@login_required
def donate_to_fund():
    amount = int(request.form.get('amount', 0))
    if amount < 10:
        return jsonify({'error': 'Минимум 10 💎'}), 400
    
    coins = get_user_coins(current_user.id)
    if coins.balance < amount:
        return jsonify({'error': 'Недостаточно 💎'}), 402
    
    coins.balance -= amount
    
    fund = GoldenFund.query.filter_by(is_distributed=False).first()
    if not fund:
        # Создаём новый фонд, если нет активного
        fund = GoldenFund(
            total_pool=amount,
            platform_fee=int(amount * 0.25),
            distributed_pool=int(amount * 0.75),
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=7)
        )
        db.session.add(fund)
    else:
        fund.total_pool += amount
        fund.platform_fee += int(amount * 0.25)
        fund.distributed_pool += int(amount * 0.75)
    
    db.session.commit()
    return jsonify({
        'success': True,
        'new_balance': coins.balance,
        'fund_pool': fund.distributed_pool
    })

# Автоматическое распределение (вызывается раз в неделю)
def auto_distribute_fund():
    with app.app_context():
        fund = GoldenFund.query.filter_by(is_distributed=False).first()
        if not fund or fund.end_date > datetime.utcnow():
            return
        
        all_videos = GoldenContent.query.filter(
            GoldenContent.created_at >= fund.start_date,
            GoldenContent.created_at <= fund.end_date
        ).all()
        
        total_views = sum(v.views_count for v in all_videos)
        if total_views == 0:
            fund.is_distributed = True
            db.session.commit()
            return
        
        for video in all_videos:
            if video.views_count > 0:
                share = int(fund.distributed_pool * video.views_count / total_views)
                if share > 0:
                    author_coins = get_user_coins(video.author_id)
                    author_coins.balance += share
        
        fund.is_distributed = True
        db.session.commit()
        
        # Создаём новый фонд
        new_fund = GoldenFund(
            total_pool=100000,
            platform_fee=25000,
            distributed_pool=75000,
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=7)
        )
        db.session.add(new_fund)
        db.session.commit()
        print("✅ Фонд распределён и создан новый")
@app.route('/group/<int:gid>/edit', methods=['POST'])
@login_required
def edit_group(gid):
    group = db.session.get(Group, gid)
    if not group:
        return jsonify({'error': 'Группа не найдена'}), 404
    
    member = GroupMember.query.filter_by(user_id=current_user.id, group_id=gid).first()
    if not member or not member.is_admin:
        return jsonify({'error': 'Нет прав'}), 403
    
    data = request.get_json()
    if data.get('name'):
        group.name = data['name']
    if data.get('description') is not None:
        group.description = data['description']
    
    db.session.commit()
    return jsonify({'success': True})

@app.route('/group/<int:gid>/delete', methods=['POST'])
@login_required
def delete_group(gid):
    group = db.session.get(Group, gid)
    if not group:
        return jsonify({'error': 'Группа не найдена'}), 404
    
    if group.created_by != current_user.id:
        return jsonify({'error': 'Только создатель может удалить группу'}), 403
    
    GroupMessage.query.filter_by(group_id=gid).delete()
    GroupMember.query.filter_by(group_id=gid).delete()
    db.session.delete(group)
    db.session.commit()
    
    return jsonify({'success': True, 'redirect': '/chat'})

@app.route('/group/<int:gid>/add_member', methods=['POST'])
@login_required
def add_member_to_group(gid):
    group = db.session.get(Group, gid)
    if not group:
        return jsonify({'error': 'Группа не найдена'}), 404
    
    member = GroupMember.query.filter_by(user_id=current_user.id, group_id=gid).first()
    if not member or not member.is_admin:
        return jsonify({'error': 'Нет прав'}), 403
    
    username = request.form.get('username', '').strip()
    if not username:
        flash('Введите имя пользователя', 'danger')
        return redirect(url_for('group_info', gid=gid))
    
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('Пользователь не найден', 'danger')
        return redirect(url_for('group_info', gid=gid))
    
    existing = GroupMember.query.filter_by(user_id=user.id, group_id=gid).first()
    if existing:
        flash('Пользователь уже в группе', 'danger')
        return redirect(url_for('group_info', gid=gid))
    
    new_member = GroupMember(user_id=user.id, group_id=gid, is_admin=False)
    db.session.add(new_member)
    db.session.commit()
    
    flash(f'{user.username} добавлен в группу!', 'success')
    return redirect(url_for('group_info', gid=gid))

@app.route('/group/<int:gid>/remove_member/<int:uid>', methods=['POST'])
@login_required
def remove_member_from_group(gid, uid):
    group = db.session.get(Group, gid)
    if not group:
        flash('Группа не найдена', 'danger')
        return redirect(url_for('chat'))
    
    member = GroupMember.query.filter_by(user_id=current_user.id, group_id=gid).first()
    if not member or not member.is_admin:
        flash('Нет прав', 'danger')
        return redirect(url_for('group_info', gid=gid))
    
    if uid == group.created_by:
        flash('Нельзя удалить создателя группы', 'danger')
        return redirect(url_for('group_info', gid=gid))
    
    target = GroupMember.query.filter_by(user_id=uid, group_id=gid).first()
    if target:
        db.session.delete(target)
        db.session.commit()
        flash('Участник удалён', 'success')
    
    return redirect(url_for('group_info', gid=gid))

@app.route('/group/<int:gid>/leave', methods=['POST'])
@login_required
def leave_group(gid):
    group = db.session.get(Group, gid)
    if not group:
        return jsonify({'error': 'Группа не найдена'}), 404
    
    if group.created_by == current_user.id:
        return jsonify({'error': 'Создатель не может покинуть группу. Удалите группу.'}), 400
    
    member = GroupMember.query.filter_by(user_id=current_user.id, group_id=gid).first()
    if member:
        db.session.delete(member)
        db.session.commit()
    
    return jsonify({'success': True, 'redirect': '/chat'})

# ========== ЧАТ ==========
@app.route('/chat')
@login_required
def chat():
    current_user.last_seen = datetime.utcnow()
    db.session.commit()

    blocked_ids = [b.blocked_user_id for b in Blacklist.query.filter_by(user_id=current_user.id).all()]

    # ТОЛЬКО контакты
    contact_ids = [c.contact_id for c in Contact.query.filter_by(user_id=current_user.id).all()]
    users = User.query.filter(User.id.in_(contact_ids), ~User.id.in_(blocked_ids), User.is_active == True).all()

    # НО: добавляем тех кто реально написал (даже если не в контактах)
    users_who_wrote = db.session.query(Message.sender_id).filter(
        Message.receiver_id == current_user.id
    ).distinct().all()
    extra_ids = [u[0] for u in users_who_wrote if u[0] not in contact_ids and u[0] != current_user.id]
    extra_users = User.query.filter(User.id.in_(extra_ids), ~User.id.in_(blocked_ids), User.is_active == True).all()

    all_users = users + extra_users

    groups = Group.query.join(GroupMember).filter(GroupMember.user_id == current_user.id).all()
    secret_chats = SecretChat.query.filter(
        (SecretChat.user1_id == current_user.id) | (SecretChat.user2_id == current_user.id),
        SecretChat.is_active == True
    ).all()
    user_channels = Channel.query.join(ChannelSubscriber).filter(ChannelSubscriber.user_id == current_user.id).all()

    convs = []

    # Приватные чаты (только с теми, кто реально в переписке)
    private_users = User.query.filter(User.id != current_user.id).filter(
        User.id.in_(
            db.session.query(Message.receiver_id).filter(Message.sender_id == current_user.id)
            .union(db.session.query(Message.sender_id).filter(Message.receiver_id == current_user.id))
        )
    ).all()

    for u in private_users:
        last = Message.query.filter(
            ((Message.sender_id == current_user.id) & (Message.receiver_id == u.id)) |
            ((Message.sender_id == u.id) & (Message.receiver_id == current_user.id)),
            ~Message.deleted_for.contains(str(current_user.id))
        ).order_by(Message.timestamp.desc()).first()
        unread = Message.query.filter(
            Message.sender_id == u.id,
            Message.receiver_id == current_user.id,
            Message.is_read == False
        ).count()
        convs.append({
            'type': 'private', 'id': u.id, 'name': u.username,
            'avatar': u.avatar, 'status': u.status,
            'last': last, 'unread': unread
        })

    #   Группы
    for g in groups:
        last = Message.query.filter_by(receiver_id=g.id).order_by(Message.timestamp.desc()).first()
        unread = Message.query.filter_by(receiver_id=g.id, is_read=False).filter(Message.sender_id != current_user.id).count()
        convs.append({
            'type': 'group', 'id': g.id, 'name': g.name,
            'avatar': getattr(g, 'avatar', 'group_default.png'),
            'last': last, 'unread': unread
        })

    # Секретные чаты
    for sc in secret_chats:
        last = Message.query.filter_by(secret_chat_id=sc.id).order_by(Message.timestamp.desc()).first()
        unread = Message.query.filter_by(secret_chat_id=sc.id, is_read=False).filter(Message.sender_id != current_user.id).count()
        convs.append({
            'type': 'secret', 'id': sc.id, 'name': sc.user1_id == current_user.id and sc.user2.username or sc.user1.username,
            'last': last, 'unread': unread
        })

    # Сортировка по дате последнего сообщения
    convs.sort(key=lambda x: x['last'].timestamp if x['last'] else datetime.min, reverse=True)

    videos = []  # Пока пусто, чтобы не падало

    return render_template('chat.html', convs=convs, user_channels=user_channels, videos=videos)
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
@app.route('/withdraw', methods=['GET', 'POST'])
@login_required
def withdraw_page():
    if request.method == 'POST':
        amount_coins = int(request.form.get('amount_coins', 0))
        method = request.form.get('method', 'yoomoney')
        wallet = request.form.get('wallet', '').strip()

        if amount_coins < 1000:
            flash('Минимальная сумма вывода 1000 💎', 'danger')
            return redirect(url_for('withdraw_page'))

        coins = get_user_coins(current_user.id)
        if coins.balance < amount_coins:
            flash('Недостаточно кристаллайзеров', 'danger')
            return redirect(url_for('withdraw_page'))

        rub_per_coin = 1.0
        gross_rub = round(amount_coins * rub_per_coin, 2)
        platform_fee = round(gross_rub * 0.25, 2)
        after_platform = gross_rub - platform_fee
        tax_rate = 13.0
        tax_amount = round(after_platform * tax_rate / 100, 2)
        net_rub = round(after_platform - tax_amount, 2)

        coins.balance -= amount_coins

        req = WithdrawalRequest(
            user_id=current_user.id,
            amount_coins=amount_coins,
            gross_rub=gross_rub,
            platform_fee=platform_fee,
            tax_amount=tax_amount,
            net_rub=net_rub,
            tax_rate=tax_rate,
            method=method,
            wallet=wallet
        )
        db.session.add(req)
        db.session.commit()

        flash(f'Заявка создана! К выплате: {net_rub} ₽ (удержано: комиссия {platform_fee} ₽, налог {tax_amount} ₽)', 'success')
        return redirect(url_for('withdraw_page'))

    coins = get_user_coins(current_user.id)
    return render_template('withdraw.html', coins=coins)
@app.context_processor
def inject_theme():
    if current_user.is_authenticated:
        user_theme = UserTheme.query.filter_by(user_id=current_user.id).first()
        if user_theme:
            theme = CustomTheme.query.get(user_theme.theme_id)
            if theme:
                return {'active_theme': theme}
    return {'active_theme': None}
@app.route('/send', methods=['POST'])
@login_required
def send():
    receiver_id = int(request.form['receiver_id'])
    if Blacklist.query.filter_by(user_id=current_user.id, blocked_user_id=receiver_id).first():
        return jsonify({'error': 'Вы заблокировали этого пользователя'}), 403
    if Blacklist.query.filter_by(user_id=receiver_id, blocked_user_id=current_user.id).first():
        return jsonify({'error': 'Этот пользователь заблокировал вас'}), 403
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
    
    # Push-уведомление
    send_push_notification(receiver_id, f'💬 {current_user.username}', content[:100] if content else '📎 Файл', f'/messages/{receiver_id}')
    
    if request.form.get('_from_ajax') == 'true':
        return jsonify({'success': True, 'msg_id': msg.id})
    return redirect(url_for('messages', uid=receiver_id))



# ========== ВСПОМОГАТЕЛЬНЫЕ МАРШРУТЫ ==========
@app.route('/typing', methods=['POST'])
@login_required
def typing():
    data = request.get_json()
    receiver_id = data.get('receiver_id')
    is_typing = data.get('is_typing', False)
    if not hasattr(app, 'typing_status'):
        app.typing_status = {}
    key = f"typing_{current_user.id}_{receiver_id}"
    if is_typing:
        app.typing_status[key] = datetime.utcnow()
    else:
        app.typing_status.pop(key, None)
    return jsonify({'success': True})

@app.route('/get_typing/<int:receiver_id>')
@login_required
def get_typing(receiver_id):
    if not hasattr(app, 'typing_status'):
        return jsonify({'is_typing': False})
    key = f"typing_{receiver_id}_{current_user.id}"
    typing_time = app.typing_status.get(key)
    if typing_time and (datetime.utcnow() - typing_time).seconds < 3:
        return jsonify({'is_typing': True})
    return jsonify({'is_typing': False})

@app.route('/search_users')
@login_required
def search_users():
    query = request.args.get('q', '').lower().strip()
    if not query:
        return jsonify([])
    
    # Убираем @ из начала запроса, если есть
    clean_query = query[1:] if query.startswith('@') else query
    
    users = User.query.filter(
        User.id != current_user.id,
        db.or_(
            User.username.ilike(f'%{clean_query}%'),
            User.username_link.ilike(f'%@{clean_query}%')
        )
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
@app.route('/love/private/create', methods=['POST'])
@login_required
def create_private_room():
    if not current_user.phone_verified:
        return jsonify({'error': 'Подтвердите номер телефона'}), 403

    data = request.get_json()
    price = int(data.get('price_per_minute', 100))
    duration = int(data.get('duration', 10))

    if price < 50:
        return jsonify({'error': 'Минимальная цена 50 💎/мин'}), 400
    if duration < 5 or duration > 60:
        return jsonify({'error': 'Длительность от 5 до 60 минут'}), 400

    # Деактивируем старые ожидающие комнаты
    PrivateRoom.query.filter_by(creator_id=current_user.id, status='waiting').update({'status': 'finished'})

    room = PrivateRoom(
        creator_id=current_user.id,
        price_per_minute=price,
        duration=duration
    )
    db.session.add(room)
    db.session.commit()

    return jsonify({
        'success': True,
        'room_id': room.id,
        'total_cost': price * duration,
        'url': f'/love/room/{room.id}'
    })
@app.route('/love/private/join/<int:room_id>', methods=['POST'])
@login_required
def join_private_room(room_id):
    if not current_user.phone_verified:
        return jsonify({'error': 'Подтвердите номер телефона'}), 403

    room = PrivateRoom.query.get_or_404(room_id)
    if room.status != 'waiting':
        return jsonify({'error': 'Комната уже занята или завершена'}), 400
    if room.creator_id == current_user.id:
        return jsonify({'error': 'Нельзя войти в свою комнату'}), 400

    total_cost = room.price_per_minute * room.duration
    user_coins = get_user_coins(current_user.id)
    if user_coins.balance < total_cost:
        return jsonify({'error': f'Недостаточно 💎. Нужно {total_cost} кристаллайзеров'}), 402

    # Списываем 💎
    user_coins.balance -= total_cost

    # Начисляем создателю (за вычетом 25%)
    creator_coins = get_user_coins(room.creator_id)
    creator_coins.balance += int(total_cost * (1 - PLATFORM_FEE))

    room.guest_id = current_user.id
    room.status = 'active'
    room.started_at = datetime.utcnow()
    room.ends_at = room.started_at + timedelta(minutes=room.duration)

    db.session.commit()

    return jsonify({
        'success': True,
        'room_id': room.id,
        'ends_at': room.ends_at.isoformat(),
        'url': f'/love/room/{room.id}'
    })
@app.route('/love/private/extend/<int:room_id>', methods=['POST'])
@login_required
def extend_private_room(room_id):
    room = PrivateRoom.query.get_or_404(room_id)
    if room.status != 'active' or room.guest_id != current_user.id:
        return jsonify({'error': 'Нельзя продлить'}), 400

    extra_minutes = int(request.get_json().get('minutes', 5))
    if extra_minutes < 1 or extra_minutes > 30:
        return jsonify({'error': 'От 1 до 30 минут'}), 400

    cost = room.price_per_minute * extra_minutes
    user_coins = get_user_coins(current_user.id)
    if user_coins.balance < cost:
        return jsonify({'error': 'Недостаточно 💎'}), 402

    user_coins.balance -= cost
    creator_coins = get_user_coins(room.creator_id)
    creator_coins.balance += int(cost * (1 - PLATFORM_FEE))

    room.ends_at += timedelta(minutes=extra_minutes)
    room.duration += extra_minutes

    db.session.commit()

    return jsonify({
        'success': True,
        'new_end': room.ends_at.isoformat(),
        'total_paid': room.price_per_minute * room.duration
    })

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
        if m.receiver_id == current_user.id and not m.is_read:
            m.is_read = True
    db.session.commit()
    return jsonify(result)

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
@app.route('/golden/like/<int:content_id>', methods=['POST'])
@login_required
def toggle_golden_like(content_id):
    existing = GoldenLike.query.filter_by(content_id=content_id, user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'liked': False})
    else:
        like = GoldenLike(content_id=content_id, user_id=current_user.id)
        db.session.add(like)
        db.session.commit()
        return jsonify({'liked': True})

@app.route('/golden/likes_count/<int:content_id>')
@login_required
def golden_likes_count(content_id):
    count = GoldenLike.query.filter_by(content_id=content_id).count()
    user_liked = GoldenLike.query.filter_by(content_id=content_id, user_id=current_user.id).first() is not None
    return jsonify({'count': count, 'liked': user_liked})

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

@app.route('/pin_message', methods=['POST'])
@login_required
def pin_message():
    data = request.get_json()
    msg_id = data['msg_id']
    msg_type = data['type']
    if msg_type == 'private':
        msg = Message.query.get(msg_id)
        if msg and (msg.sender_id == current_user.id or msg.receiver_id == current_user.id):
            old_pinned = Message.query.filter(
                ((Message.sender_id == current_user.id) | (Message.receiver_id == current_user.id)),
                ((Message.sender_id == msg.receiver_id) | (Message.receiver_id == msg.sender_id)),
                Message.is_pinned == True
            ).first()
            if old_pinned:
                old_pinned.is_pinned = False
                old_pinned.pinned_at = None
            msg.is_pinned = not msg.is_pinned
            msg.pinned_at = datetime.utcnow() if msg.is_pinned else None
            db.session.commit()
            return jsonify({'success': True, 'is_pinned': msg.is_pinned})
    return jsonify({'error': 'Сообщение не найдено'}), 404

@app.route('/get_pinned_message/<int:chat_id>/<string:chat_type>')
@login_required
def get_pinned_message(chat_id, chat_type):
    if chat_type == 'private':
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
    return jsonify({'error': 'Нет закрепленных сообщений'}), 404

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

@app.route('/get_chats_list')
@login_required
def get_chats_list():
    blocked_ids = [b.blocked_user_id for b in Blacklist.query.filter_by(user_id=current_user.id).all()]
    users = User.query.filter(User.id != current_user.id, ~User.id.in_(blocked_ids)).all()
    groups = Group.query.join(GroupMember).filter(GroupMember.user_id == current_user.id).all()
    secret_chats = SecretChat.query.filter(
        (SecretChat.user1_id == current_user.id) | (SecretChat.user2_id == current_user.id),
        SecretChat.is_active == True
    ).all()
    chats = []
    for u in users:
        chats.append({'type': 'private', 'id': u.id, 'name': u.username, 'avatar': u.avatar})
    for g in groups:
        chats.append({'type': 'group', 'id': g.id, 'name': g.name, 'avatar': g.avatar})
    for sc in secret_chats:
        other_id = sc.user2_id if sc.user1_id == current_user.id else sc.user1_id
        other_user = db.session.get(User, other_id)
        chats.append({'type': 'secret', 'id': sc.id, 'name': f'🔒 {other_user.username}', 'avatar': other_user.avatar})
    return jsonify(chats)

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

# ========== КАНАЛЫ ==========

# Вспомогательная функция (если нет - оставь здесь)

def get_file_type(filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp']:
        return 'image'
    elif ext in ['mp3', 'wav', 'ogg', 'flac', 'm4a']:
        return 'audio'
    elif ext in ['mp4', 'avi', 'mov', 'mkv', 'webm']:
        return 'video'
    else:
        return 'document'
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
    has_access = True
    if channel.is_paid and not is_admin:
        sub = ChannelSubscriber.query.filter_by(channel_id=channel.id, user_id=current_user.id).first()
        if sub and sub.subscription_expires and sub.subscription_expires > datetime.utcnow():
            has_access = True
        else:
            has_access = False
    posts = ChannelPost.query.filter_by(channel_id=channel.id).order_by(ChannelPost.timestamp.desc()).all()
    for post in posts:
        post.comments = ChannelComment.query.filter_by(post_id=post.id).order_by(ChannelComment.timestamp.asc()).all()
        post.likes_count = ChannelPostLike.query.filter_by(post_id=post.id).count()
    return render_template('channel.html', channel=channel, posts=posts, is_subscribed=is_subscribed, is_admin=is_admin, has_access=has_access)

@app.route('/channels')
@login_required
def channels_list():
    my_channels = Channel.query.filter_by(created_by=current_user.id).all()
    subscribed = ChannelSubscriber.query.filter_by(user_id=current_user.id).all()
    subscribed_ids = [s.channel_id for s in subscribed]
    subscribed_channels = Channel.query.filter(Channel.id.in_(subscribed_ids)).all() if subscribed_ids else []
    popular = Channel.query.order_by(Channel.subscribers_count.desc()).limit(10).all()
    return render_template('channels.html', my_channels=my_channels, subscribed_channels=subscribed_channels, popular=popular)
@app.route('/channel/create', methods=['GET', 'POST'])
@login_required
def channel_create():
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username', '').strip()
        description = request.form.get('description', '')
        # Новые поля
        is_paid = request.form.get('is_paid') == 'on'
        price_coins = int(request.form.get('price_coins', 0)) if is_paid else 0
        is_private = request.form.get('is_private') == 'on'

        if not username:
            username = None
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
            created_by=current_user.id,
            is_paid=is_paid,
            price_coins=price_coins,
            is_private=is_private
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
    post = ChannelPost(content=content, author_id=current_user.id, channel_id=channel_id)
    db.session.add(post)
    db.session.commit()
    attachments = []
    for f in files:
        if f and f.filename and allowed_file(f.filename):
            ext = f.filename.rsplit('.', 1)[1].lower()
            name = f"channel_{channel_id}_{post.id}_{uuid.uuid4().hex}.{ext}"
            f.save(os.path.join(FILE_FOLDER, name))
            attachments.append({
                'path': f'/static/uploads/{name}',
                'name': f.filename,
                'type': get_file_type(f.filename)
            })
    post.attachments = json.dumps(attachments)
    db.session.commit()
    flash('Пост опубликован!', 'success')
    return redirect(url_for('channel_view', identifier=channel_id))
@app.route('/golden/donate_to_video/<int:content_id>', methods=['POST'])
@login_required
def donate_to_video(content_id):
    amount = int(request.form.get('amount', 0))
    if amount < 50:
        return jsonify({'error': 'Минимум 50 💎'}), 400
    
    coins = get_user_coins(current_user.id)
    if coins.balance < amount:
        return jsonify({'error': 'Недостаточно 💎'}), 402
    
    coins.balance -= amount
    
    # Автору 75%
    video = GoldenContent.query.get_or_404(content_id)
    author_coins = get_user_coins(video.author_id)
    author_coins.balance += int(amount * 0.75)
    
    # В фонд 5%
    fund = GoldenFund.query.filter_by(is_distributed=False).first()
    if fund:
        fund.total_pool += int(amount * 0.05)
        fund.distributed_pool += int(amount * 0.05)
        db.session.commit()
    
    donation = GoldenDonation(content_id=content_id, user_id=current_user.id, amount=amount)
    db.session.add(donation)
    db.session.commit()
    
    return jsonify({'success': True, 'amount': amount, 'new_balance': coins.balance})

@app.route('/golden/top_donors/<int:content_id>')
@login_required
def top_donors(content_id):
    donors = db.session.query(
        GoldenDonation.user_id,
        db.func.sum(GoldenDonation.amount).label('total')
    ).filter_by(content_id=content_id).group_by(GoldenDonation.user_id).order_by(db.desc('total')).limit(3).all()
    
    result = []
    for user_id, total in donors:
        user = User.query.get(user_id)
        result.append({'username': user.username, 'total': total})
    return jsonify(result)

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
    comment = ChannelComment(content=content, post_id=post_id, user_id=current_user.id)
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('channel_view', identifier=post.channel_id))
@app.route('/admin')
@login_required
def admin_panel():
    if current_user.id != 1:
        flash('Нет доступа', 'danger')
        return redirect(url_for('chat'))
    return render_template('admin_panel.html')
@app.route('/golden/donate_to_fund', methods=['POST'])
@login_required
# Автоматическое создание фонда каждую неделю
def auto_create_fund():
    with app.app_context():
        active_fund = GoldenFund.query.filter_by(is_distributed=False).first()
        if not active_fund:
            # Берём 10% от общего оборота платформы за неделю или фиксированную сумму
            fund = GoldenFund(
                total_pool=100000,
                platform_fee=25000,
                distributed_pool=75000,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=7)
            )
            db.session.add(fund)
            db.session.commit()
def donate_to_fund():
    amount = int(request.form.get('amount', 0))
    if amount < 10:
        return jsonify({'error': 'Минимум 10 💎'}), 400
    
    coins = get_user_coins(current_user.id)
    if coins.balance < amount:
        return jsonify({'error': 'Недостаточно 💎'}), 402
    
    coins.balance -= amount
    
    fund = GoldenFund.query.filter_by(is_distributed=False).first()
    if fund:
        fund.total_pool += amount
        fund.distributed_pool += int(amount * 0.75)
        fund.platform_fee += int(amount * 0.25)
    else:
        # Создаём новый фонд, если нет активного
        fund = GoldenFund(
            total_pool=amount,
            platform_fee=int(amount * 0.25),
            distributed_pool=int(amount * 0.75),
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=7)
        )
        db.session.add(fund)
    
    db.session.commit()
    return jsonify({'success': True, 'new_balance': coins.balance})
@app.route('/channel/donate/<int:channel_id>', methods=['POST'])
@login_required
def channel_donate_crystals(channel_id):
    channel = Channel.query.get_or_404(channel_id)
    data = request.get_json()
    amount = int(data.get('amount', 0))

    if amount < 10:
        return jsonify({'error': 'Минимальная сумма 10 кристалайзеров'}), 400

    user_coins = get_user_coins(current_user.id)
    if user_coins.balance < amount:
        return jsonify({'error': 'Недостаточно кристалайзеров'}), 402

    # Списываем с донатера
    user_coins.balance -= amount

    # Зачисляем владельцу канала (90%)
    creator_coins = get_user_coins(channel.created_by)
    creator_coins.balance += int(amount * 0.9)

    db.session.commit()
    return jsonify({'success': True, 'new_balance': user_coins.balance})
@app.route('/channel/subscribe_paid/<int:channel_id>', methods=['POST'])
@login_required
def channel_subscribe_paid(channel_id):
    channel = Channel.query.get_or_404(channel_id)
    if not channel.is_paid or channel.price_coins <= 0:
        return jsonify({'error': 'Канал не требует платной подписки'}), 400
    if channel.created_by == current_user.id:
        return jsonify({'error': 'Вы владелец канала'}), 400

    user_coins = get_user_coins(current_user.id)
    if user_coins.balance < channel.price_coins:
        return jsonify({'error': 'Недостаточно кристалайзеров'}), 402

    # Списываем монеты
    user_coins.balance -= channel.price_coins

    # Начисляем 90% владельцу канала
    creator_coins = get_user_coins(channel.created_by)
    creator_coins.balance += int(channel.price_coins * 0.9)

    # Активируем/продлеваем подписку
    sub = ChannelSubscriber.query.filter_by(channel_id=channel.id, user_id=current_user.id).first()
    if sub:
        if sub.subscription_expires and sub.subscription_expires > datetime.utcnow():
            sub.subscription_expires = sub.subscription_expires + timedelta(days=30)
        else:
            sub.subscription_expires = datetime.utcnow() + timedelta(days=30)
    else:
        sub = ChannelSubscriber(
            channel_id=channel.id,
            user_id=current_user.id,
            subscription_expires=datetime.utcnow() + timedelta(days=30)
        )
        db.session.add(sub)
        channel.subscribers_count += 1

    db.session.commit()
    return jsonify({'success': True, 'new_balance': user_coins.balance})

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

# ---- ЛАЙКИ, ПРОСМОТРЫ, РЕДАКТИРОВАНИЕ ----

@app.route('/channel/like_post/<int:post_id>', methods=['POST'])
@login_required
def like_channel_post(post_id):
    post = ChannelPost.query.get_or_404(post_id)
    existing = ChannelPostLike.query.filter_by(post_id=post_id, user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        like = ChannelPostLike(post_id=post_id, user_id=current_user.id)
        db.session.add(like)
        liked = True
    db.session.commit()
    likes_count = ChannelPostLike.query.filter_by(post_id=post_id).count()
    return jsonify({'success': True, 'liked': liked, 'likes_count': likes_count})

@app.route('/channel/like_comment/<int:comment_id>', methods=['POST'])
@login_required
def like_channel_comment(comment_id):
    comment = ChannelComment.query.get_or_404(comment_id)
    existing = ChannelCommentLike.query.filter_by(comment_id=comment_id, user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        like = ChannelCommentLike(comment_id=comment_id, user_id=current_user.id)
        db.session.add(like)
        liked = True
    db.session.commit()
    likes_count = ChannelCommentLike.query.filter_by(comment_id=comment_id).count()
    return jsonify({'success': True, 'liked': liked, 'likes_count': likes_count})

@app.route('/check_contact/<int:user_id>')
@login_required
def check_contact(user_id):
    is_contact = Contact.query.filter_by(user_id=current_user.id, contact_id=user_id).first() is not None
    return jsonify({'is_contact': is_contact})

@app.route('/channel/view_post/<int:post_id>', methods=['POST'])
@login_required
def view_channel_post(post_id):
    post = ChannelPost.query.get_or_404(post_id)
    post.views += 1
    db.session.commit()
    return jsonify({'success': True, 'views': post.views})

# ===== ЗАМЕНИ СТАРЫЙ edit_post НА ЭТОТ =====
@app.route('/channel/post/edit/<int:post_id>', methods=['POST'])
@login_required
def edit_post(post_id):
    post = ChannelPost.query.get_or_404(post_id)
    channel = post.channel
    if channel.created_by != current_user.id:
        return jsonify({'error': 'Нет прав'}), 403

    content = request.form.get('content', '')
    # Обработка переключения комментариев (если передан параметр)
    if 'comments_enabled' in request.form and content == 'keep':
        post.comments_enabled = request.form['comments_enabled'].lower() == 'true'
        db.session.commit()
        return jsonify({'success': True})

    if not content.strip():
        return jsonify({'error': 'Текст не может быть пустым'}), 400
    post.content = content

    # Список удаляемых файлов (пути, переданные как JSON)
    deleted_paths = json.loads(request.form.get('deleted_paths', '[]'))

    # Текущие вложения (из базы)
    current_attachments = []
    if post.attachments:
        try:
            current_attachments = json.loads(post.attachments)
        except:
            pass

    # Удаляем с диска и из списка
    keep = []
    for att in current_attachments:
        if att['path'] in deleted_paths:
            # Удаляем физический файл
            file_path = os.path.join(FILE_FOLDER, os.path.basename(att['path']))
            if os.path.exists(file_path):
                os.remove(file_path)
        else:
            keep.append(att)

    # Новые файлы
    files = request.files.getlist('files')
    new_files = []
    if any(f.filename for f in files):
        for f in files:
            if f.filename == '':
                continue
            fname = secure_filename(f.filename)
            uname = f"{current_user.id}_{uuid.uuid4().hex}_{fname}"
            fpath = os.path.join(FILE_FOLDER, uname)
            f.save(fpath)
            ftype = get_file_type(fname)
            new_files.append({
                'name': fname,
                'path': f'/static/uploads/{uname}',   # ← ВОТ ГЛАВНОЕ ИСПРАВЛЕНИЕ
                'type': ftype
            })

    # Объединяем оставшиеся + новые
    all_files = keep + new_files

    # Сохраняем в пост
    if len(all_files) == 0:
        post.file_path = None
        post.file_type = None
        post.file_name = None
        post.attachments = None
    elif len(all_files) == 1:
        post.file_path = all_files[0]['path']
        post.file_type = all_files[0]['type']
        post.file_name = all_files[0]['name']
        post.attachments = None
    else:
        post.attachments = json.dumps(all_files)
        post.file_path = None
        post.file_type = None
        post.file_name = None

    db.session.commit()
    return jsonify({'success': True})

@app.route('/channel/post/delete/<int:post_id>', methods=['POST'])
@login_required
def delete_channel_post(post_id):
    post = ChannelPost.query.get_or_404(post_id)
    if post.channel.created_by != current_user.id:
        return jsonify({'error': 'Нет прав'}), 403
    if post.attachments:
        try:
            attachments = json.loads(post.attachments)
            for att in attachments:
                file_path = os.path.join(FILE_FOLDER, os.path.basename(att['path']))
                if os.path.exists(file_path):
                    os.remove(file_path)
        except:
            pass
    if post.file_path:
        file_path = os.path.join(FILE_FOLDER, os.path.basename(post.file_path))
        if os.path.exists(file_path):
            os.remove(file_path)
    db.session.delete(post)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/channel/delete/<int:channel_id>', methods=['POST'])
@login_required
def delete_channel(channel_id):
    channel = Channel.query.get_or_404(channel_id)
    if channel.created_by != current_user.id:
        return jsonify({'error': 'Нет прав'}), 403
    posts = ChannelPost.query.filter_by(channel_id=channel_id).all()
    for post in posts:
        if post.attachments:
            try:
                attachments = json.loads(post.attachments)
                for att in attachments:
                    file_path = os.path.join(FILE_FOLDER, os.path.basename(att['path']))
                    if os.path.exists(file_path):
                        os.remove(file_path)
            except:
                pass
        if post.file_path:
            file_path = os.path.join(FILE_FOLDER, os.path.basename(post.file_path))
            if os.path.exists(file_path):
                os.remove(file_path)
        db.session.delete(post)
    ChannelComment.query.filter(ChannelComment.post_id.in_([p.id for p in posts])).delete(synchronize_session=False)
    ChannelSubscriber.query.filter_by(channel_id=channel_id).delete()
    db.session.delete(channel)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/channel/edit/<int:channel_id>', methods=['POST'])
@login_required
def edit_channel(channel_id):
    channel = Channel.query.get_or_404(channel_id)
    if channel.created_by != current_user.id:
        return jsonify({'error': 'Нет прав'}), 403
    data = request.get_json()
    if 'name' in data:
        channel.name = data['name']
    if 'username' in data:
        channel.username = data['username']
    if 'description' in data:
        channel.description = data['description']
    if 'yoomoney_wallet' in data:
        channel.yoomoney_wallet = data['yoomoney_wallet'] if data['yoomoney_wallet'] else None
    db.session.commit()
    return jsonify({'success': True})

# ---- ДОНАТЫ ----

@app.route('/api/yoomoney/hook', methods=['POST'])
def yoomoney_hook():
    notification_type = request.form.get('notification_type')
    if notification_type != 'p2p-incoming':
        return 'OK'

    amount = float(request.form.get('amount', 0))
    label = request.form.get('codepro') or request.form.get('label', '')

    # === Твоя текущая логика для каналов (donate_channel_) ===
    if label.startswith('donate_channel_'):
        channel_id = int(label.split('_')[-1])
        channel = Channel.query.get(channel_id)
        if channel:
            channel.donation_balance += amount
            db.session.commit()
        return 'OK'   # важно: выходим здесь, чтобы не начислить дважды

    # === Новые правила с комиссией ===
    platform_commission = 0.10   # по умолчанию 10%
    author_id = None

    if label.startswith('golden_'):
        platform_commission = 0.20
        content_id = label.split('_')[1]
        content = GoldenContent.query.get(int(content_id))
        if content:
            author_id = content.author_id
    elif label.startswith('donate_'):
        platform_commission = 0.10
        channel_id = label.split('_')[1]
        channel = Channel.query.get(int(channel_id))
        if channel:
            author_id = channel.created_by
    elif label.startswith('music_'):
        platform_commission = 0.20
        track_id = label.split('_')[1]
        track = MusicTrack.query.get(int(track_id))
        if track:
            author_id = track.user_id

    # Начисляем автору за вычетом комиссии
    if author_id:
        fee = int(amount * platform_commission)
        author_gets = amount - fee
        coins = get_user_coins(author_id)   # эта функция уже должна быть в коде
        if coins:
            coins.balance += author_gets
            db.session.commit()

    return 'OK'
@app.route('/channel/withdraw/<int:channel_id>', methods=['POST'])
@login_required
def withdraw_donations(channel_id):
    channel = Channel.query.get_or_404(channel_id)
    if channel.owner_id != current_user.id:
        abort(403)
    if channel.donation_balance <= 0:
        return jsonify({'error': 'Нет средств для вывода'}), 400
    wallet_to = channel.yoomoney_wallet
    if not wallet_to:
        return jsonify({'error': 'Не указан кошелёк автора'}), 400

    amount_with_commission = round(channel.donation_balance * 0.9, 2)

    headers = {'Authorization': f'Bearer {YOOMONEY_TOKEN}'}
    data = {
        'to': wallet_to,
        'amount': amount_with_commission,
        'comment': f'Выплата с канала {channel.name}',
        'protection_code': '',
    }
    try:
        response = requests.post('https://yoomoney.ru/api/transfer', headers=headers, json=data)
        if response.status_code == 200:
            channel.donation_balance = 0
            db.session.commit()
            return jsonify({'success': True, 'withdrawn': amount_with_commission})
        else:
            return jsonify({'error': 'Ошибка перевода'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ========== ГОЛОСОВЫЕ КАНАЛЫ ==========
@app.route('/voice/channels/list')
@login_required
def voice_channels_list_api():
    channels = VoiceChannel.query.filter_by(is_active=True).all()
    result = []
    for ch in channels:
        members = VoiceChannelMember.query.filter_by(channel_id=ch.id).all()
        member_count = len(members)
        is_joined = VoiceChannelMember.query.filter_by(channel_id=ch.id, user_id=current_user.id).first() is not None
        members_data = []
        for m in members[:10]:
            user = User.query.get(m.user_id)
            members_data.append({'id': user.id, 'username': user.username})
        result.append({
            'id': ch.id,
            'name': ch.name,
            'member_count': member_count,
            'max_users': ch.max_users,
            'is_joined': is_joined,
            'members': members_data
        })
    return jsonify(result)

@app.route('/voice_channels')
@login_required
def voice_channels_page():
    return render_template('voice_channels.html')
@app.route('/shop')
@login_required
def shop_page():
    shop_items = ShopItem.query.filter_by(is_active=True).filter(ShopItem.category != 'flea').order_by(ShopItem.sales_count.desc()).limit(50).all()
    flea_items = ShopItem.query.filter_by(is_active=True, category='flea').order_by(ShopItem.created_at.desc()).limit(50).all()
    flea_purchases = ShopPurchase.query.filter_by(user_id=current_user.id).join(ShopItem).filter(ShopItem.category == 'flea').order_by(ShopPurchase.created_at.desc()).limit(20).all()
    coins = get_user_coins(current_user.id)
    grrr_balance = get_grrr_balance(current_user.id)
    
    return render_template('shop.html', 
                         shop_items=shop_items, 
                         flea_items=flea_items, 
                         flea_purchases=flea_purchases,
                         coins=coins, 
                         grrr_balance=grrr_balance)

@app.route('/shop/buy/<int:item_id>', methods=['POST'])
@login_required
def buy_shop_item(item_id):
    item = ShopItem.query.get_or_404(item_id)
    if not item.is_active:
        return jsonify({'error': 'Товар недоступен'}), 400
    if item.category in ['drops', 'merch'] and item.stock > 0:
        if item.sales_count >= item.stock:
            return jsonify({'error': 'Товар распродан!'}), 400
    existing = ShopPurchase.query.filter_by(item_id=item_id, user_id=current_user.id).first()
    if existing:
        return jsonify({'error': 'Уже куплено'}), 400
    
    coins = get_user_coins(current_user.id)
    if coins.balance < item.price:
        return jsonify({'error': 'Недостаточно 💎'}), 402
    
    coins.balance -= item.price
    
    # Начисление автору (75%)
    if item.author_id:
        author_coins = get_user_coins(item.author_id)
        author_coins.balance += int(item.price * 0.75)
    
    # Активация товара
    if item.item_type == 'sticker_pack' or item.category == 'stickers':
        # Если есть файл товара — распаковываем его
        if item.file_path:
            zip_path = os.path.join(FILE_FOLDER, os.path.basename(item.file_path))
            if os.path.exists(zip_path):
                extract_dir = os.path.join(CUSTOM_STICKER_FOLDER, f"pack_{item.id}_{current_user.id}")
                os.makedirs(extract_dir, exist_ok=True)
                
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(extract_dir)
                    
                    for filename in os.listdir(extract_dir):
                        if filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                            sticker_file = os.path.join(extract_dir, filename)
                            sticker_name = f"shop_sticker_{current_user.id}_{uuid.uuid4().hex}.{filename.rsplit('.',1)[1]}"
                            sticker_dest = os.path.join(CUSTOM_STICKER_FOLDER, sticker_name)
                            shutil.copy(sticker_file, sticker_dest)
                            
                            sticker = CustomSticker(
                                user_id=current_user.id,
                                file_path=f'/static/stickers/custom/{sticker_name}',
                                emoji='📦'
                            )
                            db.session.add(sticker)
                except Exception as e:
                    print(f"Ошибка распаковки стикерпака: {e}")
        
        # Если есть связанный пака (item_id) — добавляем его
        if item.item_id:
            existing_pack = UserStickerPack.query.filter_by(user_id=current_user.id, pack_id=item.item_id).first()
            if not existing_pack:
                db.session.add(UserStickerPack(user_id=current_user.id, pack_id=item.item_id))
    
    elif item.item_type == 'theme' or item.category == 'themes':
        # Если есть файл темы — распаковываем
        if item.file_path:
            theme_zip = os.path.join(FILE_FOLDER, os.path.basename(item.file_path))
            if os.path.exists(theme_zip):
                extract_dir = os.path.join(FILE_FOLDER, f"theme_{current_user.id}_{item.id}")
                os.makedirs(extract_dir, exist_ok=True)
                try:
                    with zipfile.ZipFile(theme_zip, 'r') as zip_ref:
                        zip_ref.extractall(extract_dir)
                except Exception as e:
                    print(f"Ошибка распаковки темы: {e}")
        
        # Применяем тему
        if item.item_id:
            existing_theme = UserTheme.query.filter_by(user_id=current_user.id, theme_id=item.item_id).first()
            if not existing_theme:
                db.session.add(UserTheme(user_id=current_user.id, theme_id=item.item_id))
            current_user.current_theme_id = item.item_id
        else:
            # Если тема не привязана к существующей, просто активируем её как купленную
            current_user.current_theme_id = item.id
    
    elif item.item_type == 'premium' or item.category == 'premium':
        activate_premium(current_user.id, months=1)
    
    elif item.item_type == 'voicefx' or item.category == 'voicefx':
        # Распаковываем звуковой эффект
        if item.file_path:
            sound_zip = os.path.join(FILE_FOLDER, os.path.basename(item.file_path))
            if os.path.exists(sound_zip):
                extract_dir = os.path.join(FILE_FOLDER, f"sound_{current_user.id}_{item.id}")
                os.makedirs(extract_dir, exist_ok=True)
                try:
                    with zipfile.ZipFile(sound_zip, 'r') as zip_ref:
                        zip_ref.extractall(extract_dir)
                except Exception as e:
                    print(f"Ошибка распаковки звука: {e}")
    
    purchase = ShopPurchase(item_id=item_id, user_id=current_user.id, price_paid=item.price)
    db.session.add(purchase)
    item.sales_count += 1
    db.session.commit()
    
    return jsonify({'success': True, 'new_balance': coins.balance})
    
    # Создаём стикеры из файлов
    for filename in os.listdir(extract_dir):
        if filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
            sticker_file = os.path.join(extract_dir, filename)
            # Копируем в папку стикеров
            sticker_name = f"shop_sticker_{current_user.id}_{uuid.uuid4().hex}.{filename.rsplit('.',1)[1]}"
            sticker_dest = os.path.join(CUSTOM_STICKER_FOLDER, sticker_name)
            shutil.copy(sticker_file, sticker_dest)
            
            # Создаём запись в базе
            sticker = CustomSticker(
                user_id=current_user.id,
                file_path=f'/static/stickers/custom/{sticker_name}',
                emoji='📦'
            )
            db.session.add(sticker)
    coins = get_user_coins(current_user.id)
    if coins.balance < item.price:
        return jsonify({'error': 'Недостаточно 💎'}), 402
    
    coins.balance -= item.price
    
    # Начисление автору (75%)
    if item.author_id:
        author_coins = get_user_coins(item.author_id)
        author_coins.balance += int(item.price * 0.75)
    
    # Активация товара
    if item.item_type == 'sticker_pack' or item.category == 'stickers':
        existing_pack = UserStickerPack.query.filter_by(user_id=current_user.id, pack_id=item.item_id).first()
        if not existing_pack and item.item_id:
            db.session.add(UserStickerPack(user_id=current_user.id, pack_id=item.item_id))
    
    elif item.item_type == 'theme' or item.category == 'themes':
        existing_theme = UserTheme.query.filter_by(user_id=current_user.id, theme_id=item.item_id).first()
        if not existing_theme and item.item_id:
            db.session.add(UserTheme(user_id=current_user.id, theme_id=item.item_id))
        # Активируем тему
        current_user.current_theme_id = item.item_id
    
    elif item.item_type == 'premium' or item.category == 'premium':
        activate_premium(current_user.id, months=1)
    
    elif item.item_type == 'skin' or item.category == 'skins':
        # Здесь можно добавить логику скинов
        pass
    
    elif item.item_type == 'voicefx' or item.category == 'voicefx':
        # Добавляем звук в коллекцию
        pass
    
    elif item.item_type == 'badge' or item.category == 'badges':
        # Добавляем бейдж
        pass
    
    purchase = ShopPurchase(item_id=item_id, user_id=current_user.id, price_paid=item.price)
    db.session.add(purchase)
    item.sales_count += 1
    db.session.commit()
    
    return jsonify({'success': True, 'new_balance': coins.balance})
@app.route('/shop/upload', methods=['POST'])
@login_required
def upload_shop_item():
    name = request.form.get('name')
    category = request.form.get('category')
    item_type = request.form.get('item_type')
    price = float(request.form.get('price', 0))
    description = request.form.get('description', '')
    
    if not name or price < 10:
        return jsonify({'error': 'Название и цена обязательны (мин. 10 💎)'}), 400
    
    preview = None
    if 'preview' in request.files:
        f = request.files['preview']
        if f.filename:
            ext = f.filename.rsplit('.', 1)[1].lower()
            name_file = f"shop_prev_{current_user.id}_{uuid.uuid4().hex}.{ext}"
            f.save(os.path.join(FILE_FOLDER, name_file))
            preview = f'/static/uploads/{name_file}'
    
    file_path = None
    if 'item_file' in request.files:
        f = request.files['item_file']
        if f.filename:
            ext = f.filename.rsplit('.', 1)[1].lower()
            name_file = f"shop_file_{current_user.id}_{uuid.uuid4().hex}.{ext}"
            f.save(os.path.join(FILE_FOLDER, name_file))
            file_path = f'/static/uploads/{name_file}'
    
    item = ShopItem(
        name=name,
        description=description,
        category=category,
        item_type=item_type,
        price=price,
        preview=preview,
        file_path=file_path,
        author_id=current_user.id
    )
    db.session.add(item)
    db.session.commit()
    
    return jsonify({'success': True, 'item_id': item.id})
@app.route('/api/support/create', methods=['POST'])
@login_required
def create_support_ticket():
    subject = request.form.get('subject', '')
    description = request.form.get('description', '')
    
    # Проверяем, есть ли ID покупки в описании
    import re
    purchase_id_match = re.search(r'товар[а]?\s*(\d+)', description.lower())
    
    if purchase_id_match and ('возврат' in subject.lower() or 'вернуть' in description.lower()):
        purchase_id = int(purchase_id_match.group(1))
        purchase = ShopPurchase.query.get(purchase_id)
        
        if not purchase:
            return jsonify({'error': 'Покупка не найдена'}), 404
        
        if purchase.user_id != current_user.id:
            return jsonify({'error': 'Это не ваша покупка'}), 403
        
        # Возвращаем 💎
        coins = get_user_coins(current_user.id)
        coins.balance += purchase.price_paid
        
        # Списываем с автора (если есть)
        item = ShopItem.query.get(purchase.item_id)
        if item and item.author_id and item.author_id != current_user.id:
            author_coins = get_user_coins(item.author_id)
            author_coins.balance -= int(purchase.price_paid * 0.75)
            if author_coins.balance < 0:
                author_coins.balance = 0
        
        # Удаляем покупку
        db.session.delete(purchase)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'ticket_id': None,
            'message': f'✅ Возврат выполнен! {purchase.price_paid} 💎 возвращены на ваш баланс.'
        })
    
    # Обычный тикет
    ticket = SupportTicket(user_id=current_user.id, subject=subject, description=description)
    db.session.add(ticket)
    db.session.commit()
    
    return jsonify({'success': True, 'ticket_id': ticket.id})
@app.route('/api/support/refund/<int:purchase_id>', methods=['POST'])
@login_required
def request_refund(purchase_id):
    purchase = ShopPurchase.query.get_or_404(purchase_id)
    
    if purchase.user_id != current_user.id:
        return jsonify({'error': 'Не твоя покупка'}), 403
    
    if (datetime.utcnow() - purchase.created_at).days > 7:
        return jsonify({'error': 'Возврат возможен только в течение 7 дней'}), 400
    
    # Возвращаем 💎
    coins = get_user_coins(current_user.id)
    coins.balance += purchase.price_paid
    
    # Списываем с автора (если есть)
    item = ShopItem.query.get(purchase.item_id)
    if item and item.author_id:
        author_coins = get_user_coins(item.author_id)
        author_coins.balance -= purchase.price_paid
        if author_coins.balance < 0:
            author_coins.balance = 0
    
    purchase.status = 'refunded'
    db.session.commit()
    
    return jsonify({'success': True, 'new_balance': coins.balance})

@app.route('/voice/leave/<int:channel_id>', methods=['POST'])
@login_required
def voice_leave_channel(channel_id):
    member = VoiceChannelMember.query.filter_by(channel_id=channel_id, user_id=current_user.id).first()
    if member:
        db.session.delete(member)
        db.session.commit()
    other_memberships = VoiceChannelMember.query.filter_by(user_id=current_user.id).first()
    if not other_memberships:
        current_user.status = 'online'
        db.session.commit()
    return jsonify({'success': True})

@app.route('/voice/members/<int:channel_id>')
@login_required
def voice_members_api(channel_id):
    members = VoiceChannelMember.query.filter_by(channel_id=channel_id).all()
    result = []
    for m in members:
        user = User.query.get(m.user_id)
        result.append({
            'id': user.id,
            'username': user.username,
            'avatar': user.avatar,
            'status': user.status,
            'joined_at': m.joined_at.isoformat() if m.joined_at else None,
            'muted': m.muted,
            'is_speaking': m.is_speaking
        })
    return jsonify(result)

@app.route('/voice/mute/<int:channel_id>', methods=['POST'])
@login_required
def voice_mute_member(channel_id):
    member = VoiceChannelMember.query.filter_by(channel_id=channel_id, user_id=current_user.id).first()
    if member:
        member.muted = not member.muted
        db.session.commit()
        return jsonify({'success': True, 'muted': member.muted})
    return jsonify({'error': 'Не в канале'}), 403

@app.route('/voice/speaking/<int:channel_id>', methods=['POST'])
@login_required
def voice_speaking_status(channel_id):
    data = request.get_json()
    is_speaking = data.get('is_speaking', False)
    member = VoiceChannelMember.query.filter_by(channel_id=channel_id, user_id=current_user.id).first()
    if member:
        member.is_speaking = is_speaking
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Не в канале'}), 403

@app.route('/voice/signal', methods=['POST'])
@login_required
def voice_signal():
    data = request.get_json()
    channel_id = data.get('channel_id')
    to_user_id = data.get('to_user_id')
    if not hasattr(app, 'voice_signals'):
        app.voice_signals = {}
    key = f"voice_{channel_id}_{current_user.id}_{to_user_id}"
    if 'sdp' in data:
        if key not in app.voice_signals:
            app.voice_signals[key] = {}
        app.voice_signals[key]['sdp'] = data['sdp']
        app.voice_signals[key]['sdp_type'] = data.get('type', 'offer')
    elif 'ice' in data:
        if key not in app.voice_signals:
            app.voice_signals[key] = {}
        if 'ice_candidates' not in app.voice_signals[key]:
            app.voice_signals[key]['ice_candidates'] = []
        app.voice_signals[key]['ice_candidates'].append(data['ice'])
    return jsonify({'success': True})

@app.route('/voice/get_signals/<int:channel_id>/<int:from_user_id>')
@login_required
def voice_get_signals(channel_id, from_user_id):
    key = f"voice_{channel_id}_{from_user_id}_{current_user.id}"
    result = {}
    if hasattr(app, 'voice_signals') and key in app.voice_signals:
        signal = app.voice_signals[key]
        if 'sdp' in signal:
            result['sdp'] = signal['sdp']
            result['sdp_type'] = signal.get('sdp_type', 'offer')
            del signal['sdp']
            if 'sdp_type' in signal:
                del signal['sdp_type']
        if 'ice_candidates' in signal and signal['ice_candidates']:
            result['ice'] = signal['ice_candidates'].pop(0)
        if not signal:
            del app.voice_signals[key]
    return jsonify(result)

@app.route('/voice/delete_channel/<int:channel_id>', methods=['POST'])
@login_required
def voice_delete_channel(channel_id):
    channel = VoiceChannel.query.get(channel_id)
    if not channel or channel.created_by != current_user.id:
        return jsonify({'error': 'Нет прав'}), 403
    VoiceChannelMember.query.filter_by(channel_id=channel_id).delete()
    if hasattr(app, 'voice_signals'):
        keys_to_delete = [k for k in app.voice_signals.keys() if f"voice_{channel_id}" in k]
        for k in keys_to_delete:
            del app.voice_signals[k]
    db.session.delete(channel)
    db.session.commit()
    return jsonify({'success': True})
@app.route('/shop/drops')
@login_required
def shop_drops():
    shop_items = ShopItem.query.filter_by(category='drops', is_active=True).order_by(ShopItem.created_at.desc()).limit(20).all()
    flea_items = ShopItem.query.filter_by(is_active=True, category='flea').order_by(ShopItem.created_at.desc()).limit(50).all()
    flea_purchases = ShopPurchase.query.filter_by(user_id=current_user.id).join(ShopItem).filter(ShopItem.category == 'flea').order_by(ShopPurchase.created_at.desc()).limit(20).all()
    coins = get_user_coins(current_user.id)
    grrr_balance = get_grrr_balance(current_user.id)
    return render_template('shop.html', shop_items=shop_items, flea_items=flea_items, flea_purchases=flea_purchases, coins=coins, grrr_balance=grrr_balance, category='drops')

@app.route('/shop/merch')
@login_required
def shop_merch():
    shop_items = ShopItem.query.filter_by(category='merch', is_active=True).order_by(ShopItem.sales_count.desc()).limit(20).all()
    flea_items = ShopItem.query.filter_by(is_active=True, category='flea').order_by(ShopItem.created_at.desc()).limit(50).all()
    flea_purchases = ShopPurchase.query.filter_by(user_id=current_user.id).join(ShopItem).filter(ShopItem.category == 'flea').order_by(ShopPurchase.created_at.desc()).limit(20).all()
    coins = get_user_coins(current_user.id)
    grrr_balance = get_grrr_balance(current_user.id)
    return render_template('shop.html', shop_items=shop_items, flea_items=flea_items, flea_purchases=flea_purchases, coins=coins, grrr_balance=grrr_balance, category='merch')

@app.route('/shop/category/<category>')
@login_required
def shop_category(category):
    shop_items = ShopItem.query.filter_by(category=category, is_active=True).filter(ShopItem.category != 'flea').order_by(ShopItem.sales_count.desc()).all()
    flea_items = ShopItem.query.filter_by(is_active=True, category='flea').order_by(ShopItem.created_at.desc()).limit(50).all()
    flea_purchases = ShopPurchase.query.filter_by(user_id=current_user.id).join(ShopItem).filter(ShopItem.category == 'flea').order_by(ShopPurchase.created_at.desc()).limit(20).all()
    coins = get_user_coins(current_user.id)
    grrr_balance = get_grrr_balance(current_user.id)
    return render_template('shop.html', shop_items=shop_items, flea_items=flea_items, flea_purchases=flea_purchases, coins=coins, grrr_balance=grrr_balance, category=category)

@app.route('/voice/rename_channel/<int:channel_id>', methods=['POST'])
@login_required
def voice_rename_channel(channel_id):
    data = request.get_json()
    new_name = data.get('name', '').strip()
    if not new_name:
        return jsonify({'error': 'Имя не может быть пустым'}), 400
    channel = VoiceChannel.query.get(channel_id)
    if not channel or channel.created_by != current_user.id:
        return jsonify({'error': 'Нет прав'}), 403
    channel.name = new_name
    db.session.commit()
    return jsonify({'success': True})

@app.route('/create_voice_channel', methods=['POST'])
@login_required
def create_voice_channel():
    name = request.form.get('name', '').strip()
    max_users = int(request.form.get('max_users', 0))
    is_private = request.form.get('is_private') == 'on'
    is_paid = request.form.get('is_paid') == 'on'
    price_coins = int(request.form.get('price_coins', 0)) if is_paid else 0
    yoomoney_wallet = request.form.get('yoomoney_wallet', '').strip() or None

    if not name:
        flash('Введите название канала', 'danger')
        return redirect(url_for('voice_channels_page'))

    channel = VoiceChannel(
        name=name,
        created_by=current_user.id,
        max_users=max_users,
        is_private=is_private,
        is_paid=is_paid,
        price_coins=price_coins,
        yoomoney_wallet=yoomoney_wallet,
        created_at=datetime.utcnow(),
        is_active=True
    )
    db.session.add(channel)
    db.session.commit()
    flash(f'🎤 Голосовой канал "{name}" создан!', 'success')
    return redirect(url_for('voice_channels_page'))
@app.route('/voice/join/<int:channel_id>', methods=['POST'])
@login_required
def voice_join_channel(channel_id):
    channel = VoiceChannel.query.get(channel_id)
    if not channel:
        return jsonify({'error': 'Канал не найден'}), 404

    # Создатель канала может заходить бесплатно
    if channel.created_by != current_user.id:
        # Проверка платного входа
        if channel.is_paid and channel.price_coins > 0:
            user_coins = get_user_coins(current_user.id)
            if user_coins.balance < channel.price_coins:
                return jsonify({'error': f'Недостаточно монет. Нужно {channel.price_coins} 💎'}), 402
            # Списываем монеты
            user_coins.balance -= channel.price_coins
            # Начисляем 90% создателю канала
            creator_coins = get_user_coins(channel.created_by)
            commission = int(channel.price_coins * 0.1)
            creator_coins.balance += (channel.price_coins - commission)
            db.session.commit()

    if channel.max_users > 0:
        current_members = VoiceChannelMember.query.filter_by(channel_id=channel_id).count()
        if current_members >= channel.max_users:
            return jsonify({'error': 'Канал переполнен'}), 403

    existing = VoiceChannelMember.query.filter_by(channel_id=channel_id, user_id=current_user.id).first()
    if not existing:
        member = VoiceChannelMember(
            channel_id=channel_id,
            user_id=current_user.id,
            joined_at=datetime.utcnow(),
            is_speaking=False,
            muted=False
        )
        db.session.add(member)
        db.session.commit()

    return jsonify({'success': True, 'channel_id': channel_id})
@app.route('/voice/donate/<int:channel_id>', methods=['POST'])
@login_required
def voice_donate(channel_id):
    # Проверка телефона
    if not current_user.phone_verified:
        return jsonify({'error': 'Подтвердите номер телефона в профиле (требуется верификация)'}), 403

    channel = VoiceChannel.query.get_or_404(channel_id)
    data = request.get_json()
    amount = int(data.get('amount', 0))
    message = data.get('message', '').strip()

    if amount < 10:
        return jsonify({'error': 'Минимальный донат 10 💎'}), 400

    # Получаем кошелёк пользователя (таблица UserCoins)
    user_coins = UserCoins.query.filter_by(user_id=current_user.id).first()
    if not user_coins or user_coins.balance < amount:
        return jsonify({'error': 'Недостаточно кристалайзеров'}), 402

    # Списываем кристалайзеры
    user_coins.balance -= amount

    # Начисляем 90% создателю канала
    creator_coins = UserCoins.query.filter_by(user_id=channel.created_by).first()
    if creator_coins:
        creator_coins.balance += int(amount * 0.9)
    else:
        # Если у создателя ещё нет кошелька, создаём
        creator_coins = UserCoins(user_id=channel.created_by, balance=int(amount * 0.9))
        db.session.add(creator_coins)

    # Записываем донат
    donation = VoiceChannelDonation(
        channel_id=channel_id,
        from_user_id=current_user.id,
        amount=amount,
        message=message
    )
    db.session.add(donation)
    db.session.commit()

    return jsonify({
        'success': True,
        'donation': {
            'from_user': current_user.username,
            'amount': amount,
            'message': message
        },
        'new_balance': user_coins.balance
    })
@app.route('/voice/donations/<int:channel_id>')
@login_required
def voice_donations(channel_id):
    channel = VoiceChannel.query.get_or_404(channel_id)
    # Проверка, что пользователь в канале
    member = VoiceChannelMember.query.filter_by(channel_id=channel_id, user_id=current_user.id).first()
    if not member:
        return jsonify({'error': 'Вы не в канале'}), 403

    donations = VoiceChannelDonation.query.filter_by(channel_id=channel_id)\
        .order_by(VoiceChannelDonation.created_at.desc())\
        .limit(50).all()
    result = []
    for d in donations:
        result.append({
            'from_user': d.from_user.username,
            'amount': d.amount,
            'message': d.message,
            'created_at': d.created_at.strftime('%H:%M')
        })
    return jsonify(result)


# ========== СИСТЕМА СТИКЕРОВ ==========
@app.route('/api/stickers/all')
@login_required
def api_stickers_all():
    result = {'custom': [], 'packs': []}
    
    custom_stickers = CustomSticker.query.filter_by(user_id=current_user.id).order_by(CustomSticker.created_at.desc()).all()
    for s in custom_stickers:
        result['custom'].append({
            'id': s.id,
            'emoji': s.emoji,
            'url': s.file_path
        })
    
    is_premium = get_premium_status(current_user.id)
    all_packs = StickerPack.query.all()
    
    for pack in all_packs:
        if pack.is_premium and not is_premium:
            purchased = UserStickerPack.query.filter_by(user_id=current_user.id, pack_id=pack.id).first()
            if not purchased:
                continue
        
        stickers = Sticker.query.filter_by(pack_id=pack.id).order_by(Sticker.order_num).all()
        pack_data = {
            'id': pack.id,
            'title': pack.title,
            'is_premium': pack.is_premium,
            'stickers': [{'id': s.id, 'emoji': s.emoji, 'url': s.file_path} for s in stickers]
        }
        result['packs'].append(pack_data)
    
    return jsonify(result)

@app.route('/stickers/custom/upload', methods=['POST'])
@login_required
def upload_custom_sticker():
    if 'sticker' not in request.files:
        return jsonify({'error': 'Нет файла'}), 400
    
    f = request.files['sticker']
    if f.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    
    is_premium = get_premium_status(current_user.id)
    if not is_premium:
        count = CustomSticker.query.filter_by(user_id=current_user.id).count()
        if count >= 30:
            return jsonify({'error': 'Лимит 30 стикеров. Купите Premium для безлимита.'}), 403
    
    if '.' not in f.filename:
        return jsonify({'error': 'Неверный формат файла'}), 400
    
    ext = f.filename.rsplit('.', 1)[1].lower()
    if ext not in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
        return jsonify({'error': f'Формат .{ext} не поддерживается. Только PNG, JPG, GIF, WEBP'}), 400
    
    filename = f"custom_{current_user.id}_{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(CUSTOM_STICKER_FOLDER, filename)
    f.save(filepath)
    
    emoji = request.form.get('emoji', '🐻')
    if len(emoji) > 10:
        emoji = emoji[:10]
    
    sticker = CustomSticker(
        user_id=current_user.id,
        file_path=f'/static/stickers/custom/{filename}',
        emoji=emoji
    )
    db.session.add(sticker)
    db.session.commit()
    
    return jsonify({'success': True, 'id': sticker.id, 'url': sticker.file_path, 'emoji': sticker.emoji})

@app.route('/stickers/custom/delete/<int:sticker_id>', methods=['POST'])
@login_required
def delete_custom_sticker(sticker_id):
    sticker = CustomSticker.query.get(sticker_id)
    if not sticker or sticker.user_id != current_user.id:
        return jsonify({'error': 'Нет прав'}), 403
    
    filepath = os.path.join(CUSTOM_STICKER_FOLDER, os.path.basename(sticker.file_path))
    if os.path.exists(filepath):
        os.remove(filepath)
    
    db.session.delete(sticker)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/stickers/shop')
@login_required
def api_stickers_shop():
    is_premium = get_premium_status(current_user.id)
    if is_premium:
        return jsonify({'packs': [], 'message': 'У вас Premium — все паки доступны!'})
    
    packs = StickerPack.query.filter_by(is_premium=True).all()
    result = []
    user_coins = get_user_coins(current_user.id)
    
    for pack in packs:
        purchased = UserStickerPack.query.filter_by(user_id=current_user.id, pack_id=pack.id).first()
        if purchased:
            continue
        
        stickers_count = Sticker.query.filter_by(pack_id=pack.id).count()
        result.append({
            'id': pack.id,
            'title': pack.title,
            'price': pack.price_coins,
            'preview': pack.preview,
            'stickers_count': stickers_count,
            'can_afford': user_coins.balance >= pack.price_coins
        })
    
    return jsonify({'packs': result, 'balance': user_coins.balance})

@app.route('/stickers/buy/<int:pack_id>', methods=['POST'])
@login_required
def buy_sticker_pack(pack_id):
    if not current_user.phone_verified:
        return jsonify({'error': 'Подтвердите номер телефона в профиле, чтобы использовать кристаллайзеры'}), 403

    pack = StickerPack.query.get(pack_id)
    if not pack or not pack.is_premium:
        return jsonify({'error': 'Пак не найден или бесплатный'}), 404

    purchased = UserStickerPack.query.filter_by(user_id=current_user.id, pack_id=pack_id).first()
    if purchased:
        return jsonify({'error': 'Уже куплен'}), 400

    user_coins = get_user_coins(current_user.id)
    if user_coins.balance < pack.price_coins:
        return jsonify({'error': 'Недостаточно монет 💰'}), 403

    user_coins.balance -= pack.price_coins
    purchase = UserStickerPack(user_id=current_user.id, pack_id=pack_id)
    db.session.add(purchase)
    db.session.commit()

    return jsonify({'success': True, 'new_balance': user_coins.balance})

@app.route('/api/coins/balance')
@login_required
def api_coins_balance():
    coins = get_user_coins(current_user.id)
    custom_count = CustomSticker.query.filter_by(user_id=current_user.id).count()
    is_premium = get_premium_status(current_user.id)
    
    today = datetime.utcnow().date()
    ai_used_today = AIGeneration.query.filter(
        AIGeneration.user_id == current_user.id,
        db.func.date(AIGeneration.created_at) == today
    ).count()
    
    return jsonify({
        'balance': coins.balance,
        'is_premium': is_premium,
        'custom_stickers_count': custom_count,
        'max_custom': 30 if not is_premium else None,
        'ai_used_today': ai_used_today,
        'ai_limit': 3 if not is_premium else None
    })

@app.route('/stickers/send', methods=['POST'])
@login_required
def send_sticker_message():
    data = request.get_json()
    sticker_url = data.get('url')
    chat_type = data.get('chat_type', 'private')
    target_id = data.get('target_id')
    
    if not sticker_url or not target_id:
        return jsonify({'error': 'Нет данных'}), 400
    
    if chat_type == 'private':
        msg = Message(
            content='',
            file_path=sticker_url,
            file_name='sticker.png',
            file_type='sticker',
            sender_id=current_user.id,
            receiver_id=target_id
        )
    elif chat_type == 'group':
        msg = GroupMessage(
            content='',
            file_path=sticker_url,
            file_name='sticker.png',
            file_type='sticker',
            sender_id=current_user.id,
            group_id=target_id
        )
    elif chat_type == 'secret':
        msg = SecretMessage(
            encrypted_content=None,
            file_path=sticker_url,
            file_name='sticker.png',
            file_type='sticker',
            sender_id=current_user.id,
            secret_chat_id=target_id
        )
    else:
        return jsonify({'error': 'Неверный тип чата'}), 400
    
    db.session.add(msg)
    db.session.commit()
    
    return jsonify({'success': True})

# ========== AI ГЕНЕРАТОР СТИКЕРОВ ==========
@app.route('/stickers/ai/generate', methods=['POST'])
@login_required
def ai_generate_sticker():
    data = request.get_json()
    prompt = data.get('prompt', '').strip()

    if not prompt:
        return jsonify({'error': 'Введите описание стикера'}), 400

    if len(prompt) > 200:
        return jsonify({'error': 'Описание слишком длинное (макс 200 символов)'}), 400

    # Проверяем лимит бесплатных генераций (10 шт. всего)
    is_premium = get_premium_status(current_user.id)
    if not is_premium:
        if current_user.sticker_generations_free >= 10:
            return jsonify({
                'error': 'Лимит 10 бесплатных стикеров исчерпан. Купите Premium для безлимита.',
                'limit_reached': True,
                'generated_count': current_user.sticker_generations_free
            }), 403

    # --- ГЕНЕРАЦИЯ (твоя текущая логика) ---
    try:
        full_prompt = f"{prompt}, cute sticker style, kawaii, white background, simple clean lines, vector illustration"
        encoded_prompt = requests.utils.quote(full_prompt)

        urls = [
            f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=512&height=512&nologo=true",
            f"https://pollinations.ai/p/{encoded_prompt}?width=512&height=512&model=flux",
        ]

        response = None
        for url in urls:
            try:
                response = requests.get(url, timeout=60, headers={'User-Agent': 'Mozilla/5.0'})
                if response.status_code == 200 and len(response.content) > 5000:
                    break
            except:
                continue

        if not response or response.status_code != 200 or len(response.content) < 5000:
            return jsonify({'error': 'Сервис генерации временно недоступен. Попробуйте позже.'}), 500

        filename = f"ai_{current_user.id}_{uuid.uuid4().hex}.png"
        filepath = os.path.join(CUSTOM_STICKER_FOLDER, filename)

        with open(filepath, 'wb') as f:
            f.write(response.content)

        sticker = CustomSticker(
            user_id=current_user.id,
            file_path=f'/static/stickers/custom/{filename}',
            emoji='🤖'
        )
        db.session.add(sticker)

        gen = AIGeneration(user_id=current_user.id, prompt=prompt)
        db.session.add(gen)

        # Увеличиваем счётчик БЕСПЛАТНЫХ генераций (только если не Premium)
        if not is_premium:
            current_user.sticker_generations_free += 1

        db.session.commit()

        remaining = None if is_premium else (10 - current_user.sticker_generations_free)

        return jsonify({
            'success': True,
            'sticker': {
                'id': sticker.id,
                'url': sticker.file_path,
                'emoji': sticker.emoji
            },
            'remaining': remaining,
            'is_premium': is_premium
        })

    except Exception as e:
        print(f"AI generation error: {e}")
        return jsonify({'error': 'Ошибка при генерации. Попробуйте другой запрос.'}), 500




# ======================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ========================
def get_premium_status(user_id):
    sub = Subscription.query.filter_by(user_id=user_id).first()
    if sub and sub.expires_at and sub.expires_at > datetime.utcnow():
        return True
    return False

def get_user_coins(user_id):
    coins = UserCoins.query.filter_by(user_id=user_id).first()
    if not coins:
        coins = UserCoins(user_id=user_id, balance=0)
        db.session.add(coins)
        db.session.commit()
    return coins

def activate_premium(user_id, months=1):
    sub = Subscription.query.filter_by(user_id=user_id).first()
    now = datetime.utcnow()
    if sub:
        # Если подписка ещё активна, продлеваем с текущей даты окончания
        if sub.expires_at and sub.expires_at > now:
            sub.expires_at = sub.expires_at + timedelta(days=30 * months)
        else:
            sub.expires_at = now + timedelta(days=30 * months)
        sub.plan = 'premium'
    else:
        sub = Subscription(user_id=user_id, plan='premium',
                           expires_at=now + timedelta(days=30 * months))
        db.session.add(sub)
    db.session.commit()


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
        price = item.price_coins
    elif gift_type == 'premium_month':
        price = 299
    else:
        return jsonify({'error': 'Неверный тип подарка'}), 400
    gift = Gift(from_user_id=current_user.id, to_user_id=to_user_id, gift_type=gift_type, gift_id=gift_id, message=message)
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
        gifts_data.append({'id': g.id, 'from_user': from_user, 'gift': gift_info, 'created_at': g.created_at})
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
        existing = UserStickerPack.query.filter_by(user_id=current_user.id, pack_id=gift.gift_id).first()
        if not existing:
            user_pack = UserStickerPack(user_id=current_user.id, pack_id=gift.gift_id)
            db.session.add(user_pack)
    elif gift.gift_type == 'premium_month':
        activate_premium(current_user.id, months=1)
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

    is_premium = get_premium_status(current_user.id)

    return render_template('themes.html',
                           free_themes=free_themes,
                           premium_themes=premium_themes,
                           user_theme_ids=user_theme_ids,
                           current_theme=current_theme,
                           is_premium=is_premium)
# ======================== PREMIUM И МОНЕТИЗАЦИЯ ========================

@app.route('/premium')
@login_required
def premium_page():
    coins = get_user_coins(current_user.id)
    is_premium = get_premium_status(current_user.id)
    if is_premium:
        return render_template('premium_active.html')  # если есть отдельная страница для активных
    return render_template('premium.html', coins=coins, is_premium=is_premium)

@app.route('/api/create_premium_order', methods=['POST'])
@login_required
def create_premium_order():
    PRICE_RUB = 299.0

    existing = Subscription.query.filter_by(user_id=current_user.id).first()
    if existing and existing.expires_at and existing.expires_at > datetime.utcnow():
        return jsonify({'error': 'У вас уже активен Premium'}), 400

    order = Order(
        user_id=current_user.id,
        order_type='premium',
        amount_rub=PRICE_RUB,
        status='pending'
    )
    db.session.add(order)
    db.session.commit()

    payment_url = f"https://yoomoney.ru/to/4100119522166446?sum={PRICE_RUB}&label=order_{order.id}"

    return jsonify({
        'order_id': order.id,
        'amount': PRICE_RUB,
        'payment_url': payment_url
    })
@app.route('/api/activate_premium_coins', methods=['POST'])
@login_required
def activate_premium_coins():
    if not current_user.phone_verified:
        return jsonify({'error': 'Подтвердите номер телефона в профиле, чтобы использовать кристаллайзеры'}), 403

    PRICE_COINS = 250

    user_coins = get_user_coins(current_user.id)
    if user_coins.balance < PRICE_COINS:
        return jsonify({'error': f'Недостаточно Кристаллайзеров. Нужно {PRICE_COINS} 💎'}), 402

    existing = Subscription.query.filter_by(user_id=current_user.id).first()
    if existing and existing.expires_at and existing.expires_at > datetime.utcnow():
        return jsonify({'error': 'У вас уже активен премиум'}), 400

    user_coins.balance -= PRICE_COINS
    db.session.commit()
    activate_premium(current_user.id, months=1)

    return jsonify({'success': True, 'new_balance': user_coins.balance})

    # Проверяем, нет ли уже активного премиума
    existing = Subscription.query.filter_by(user_id=current_user.id).first()
    if existing and existing.expires_at and existing.expires_at > datetime.utcnow():
        return jsonify({'error': 'У вас уже активен премиум'}), 400

    # Списываем Кристаллайзеры
    user_coins.balance -= PRICE_COINS
    db.session.commit()

    # Активируем премиум
    activate_premium(current_user.id, months=1)

    return jsonify({
        'success': True,
        'new_balance': user_coins.balance
    })
@app.route('/api/shop/coins/packages')
@login_required
def get_coin_packages():
    packages = [
        {'id': 1, 'coins': 80,  'price_rub': 99,  'name': '🍯 Маленький горшочек', 'emoji': '🍯'},
        {'id': 2, 'coins': 400, 'price_rub': 399, 'name': '🐝 Пчелиный улей',       'emoji': '🐝', 'popular': True},
        {'id': 3, 'coins': 1000,'price_rub': 799, 'name': '👑 Медовый король',      'emoji': '👑', 'bonus': 200}
    ]
    return jsonify(packages)

@app.route('/api/create_coins_order', methods=['POST'])
@login_required
def create_coins_order():
    if not current_user.phone_verified:
        return jsonify({'error': 'Подтвердите номер телефона в профиле, чтобы использовать кристаллайзеры'}), 403

    data = request.get_json()
    package_id = data.get('package_id')
    packages = {
        1: {'coins': 80,  'price': 99},
        2: {'coins': 400, 'price': 399},
        3: {'coins': 1000, 'price': 799}
    }

    if package_id not in packages:
        return jsonify({'error': 'Пакет не найден'}), 404

    pkg = packages[package_id]
    order = Order(user_id=current_user.id, order_type='coins', amount_rub=pkg['price'],
                  coins_amount=pkg['coins'], status='pending')
    db.session.add(order)
    db.session.commit()

    payment_url = f"https://yoomoney.ru/to/4100119522166446?sum={pkg['price']}&label=order_{order.id}"

    return jsonify({
        'order_id': order.id,
        'amount': pkg['price'],
        'coins': pkg['coins'],
        'payment_url': payment_url
    })

@app.route('/api/user/premium_status')
@login_required
def api_premium_status():
    is_premium = get_premium_status(current_user.id)
    coins = get_user_coins(current_user.id)
    sub = Subscription.query.filter_by(user_id=current_user.id).first()

    expires_at = None
    if sub and sub.expires_at:
        expires_at = sub.expires_at.strftime('%d.%m.%Y')

    return jsonify({
        'is_premium': is_premium,
        'balance': coins.balance,
        'expires_at': expires_at,
        'plan': sub.plan if sub else 'free'
    })

@app.route('/api/payment_webhook', methods=['POST'])
def payment_webhook():
    data = request.get_json()

    order_id = data.get('order_id') or data.get('MERCHANT_ORDER_ID') or data.get('orderId')
    status = data.get('status') or data.get('STATE') or data.get('state')
    amount_paid = float(data.get('amount') or data.get('AMOUNT') or 0)

    if not order_id:
        return 'No order_id', 400

    if isinstance(order_id, str) and order_id.startswith('order_'):
        order_id = order_id[6:]
    try:
        order = Order.query.get(int(order_id))
    except ValueError:
        return 'Invalid order_id', 400

    if not order:
        return 'Order not found', 404

    if status in ['paid', 'success', 'COMPLETED', 'completed'] and amount_paid >= order.amount_rub:
        if order.status == 'pending':
            order.status = 'paid'
            order.paid_at = datetime.utcnow()

            if order.order_type == 'premium':
                activate_premium(order.user_id, months=1)
            elif order.order_type == 'coins':
                coins = get_user_coins(order.user_id)
                coins.balance += order.coins_amount

            db.session.commit()

    return 'OK', 200

@app.route('/shop/coins')
@login_required
def shop_coins():
    return render_template('shop_coins.html')

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
    return render_template('storage.html', storage=storage, user_files=user_files)

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
@app.route('/golden')
@login_required
def golden_feed():
    videos = GoldenContent.query.order_by(GoldenContent.created_at.desc()).limit(50).all()
    current_fund = GoldenFund.query.filter_by(is_distributed=False).first()
    return render_template('golden_feed.html', videos=videos, fund=current_fund)

@app.route('/golden/upload', methods=['POST'])
@login_required
def golden_upload():
    if 'video' not in request.files:
        return jsonify({'error': 'Нет файла'}), 400
    f = request.files['video']
    if f.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    title = request.form.get('title', '')
    ext = f.filename.rsplit('.', 1)[1].lower()
    name = f"golden_{current_user.id}_{uuid.uuid4().hex}.{ext}"
    
    # Сохраняем оригинал
    filepath = os.path.join(FILE_FOLDER, name)
    f.save(filepath)
    
    # Конвертируем в 720p минимум (если ffmpeg установлен)
    try:
        import subprocess
        output_name = f"golden_{current_user.id}_{uuid.uuid4().hex}_720p.mp4"
        output_path = os.path.join(FILE_FOLDER, output_name)
        subprocess.run([
            'ffmpeg', '-i', filepath,
            '-vf', 'scale=-1:720',
            '-c:v', 'libx264',
            '-crf', '23',
            '-preset', 'fast',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-movflags', '+faststart',
            output_path
        ], check=True, timeout=60)
        # Удаляем оригинал, оставляем 720p версию
        os.remove(filepath)
        filepath = output_path
        name = output_name
    except:
        pass  # Если ffmpeg нет, оставляем оригинал
    
    video = GoldenContent(
        author_id=current_user.id,
        file_path=f'/static/uploads/{name}',
        title=title
    )
    db.session.add(video)
    db.session.commit()
    return jsonify({'success': True, 'id': video.id})
@app.route('/golden/view/<int:content_id>', methods=['POST'])
@login_required
def golden_view(content_id):
    content = GoldenContent.query.get_or_404(content_id)
    existing = GoldenContentView.query.filter_by(
        content_id=content_id, viewer_id=current_user.id).first()
    
    if not existing:
        view = GoldenContentView(content_id=content_id, viewer_id=current_user.id)
        db.session.add(view)
        content.views_count += 1
        db.session.commit()
    
    return jsonify({'success': True, 'views': content.views_count})

@app.route('/golden/stats')
@login_required
def golden_stats():
    my_videos = GoldenContent.query.filter_by(author_id=current_user.id).order_by(GoldenContent.views_count.desc()).all()
    current_fund = GoldenFund.query.filter_by(is_distributed=False).first()
    total_views = sum(v.views_count for v in my_videos)
    
    return jsonify({
        'total_views': total_views,
        'fund_pool': current_fund.total_pool if current_fund else 0,
        'videos': [{'id': v.id, 'title': v.title, 'views': v.views_count} for v in my_videos]
    })

@app.route('/admin/create_fund', methods=['POST'])
@login_required
def create_fund():
    if current_user.id != 1:
        return jsonify({'error': 'Нет доступа'}), 403
    
    total = int(request.form.get('total_pool', 100000))
    fund = GoldenFund(
        total_pool=total,
        platform_fee=int(total * 0.25),
        distributed_pool=total - int(total * 0.25),
        start_date=datetime.utcnow(),
        end_date=datetime.utcnow() + timedelta(days=7)
    )
    db.session.add(fund)
    db.session.commit()
    return jsonify({'success': True, 'fund_id': fund.id})

@app.route('/admin/distribute_fund/<int:fund_id>', methods=['POST'])
@login_required
def distribute_fund(fund_id):
    if current_user.id != 1:
        return jsonify({'error': 'Нет доступа'}), 403
    
    fund = GoldenFund.query.get_or_404(fund_id)
    if fund.is_distributed:
        return jsonify({'error': 'Уже распределён'}), 400
    
    all_videos = GoldenContent.query.filter(
        GoldenContent.created_at >= fund.start_date,
        GoldenContent.created_at <= fund.end_date
    ).all()
    
    total_views = sum(v.views_count for v in all_videos)
    if total_views == 0:
        return jsonify({'error': 'Нет просмотров'}), 400
    
    for video in all_videos:
        if video.views_count > 0:
            share = int(fund.distributed_pool * video.views_count / total_views)
            if share > 0:
                author_coins = get_user_coins(video.author_id)
                author_coins.balance += share
    
    fund.is_distributed = True
    db.session.commit()
    
    return jsonify({'success': True, 'distributed': fund.distributed_pool})

@app.route('/storage/upgrade', methods=['POST'])
@login_required
def upgrade_storage():
    data = request.get_json()
    additional_gb = data.get('gb', 10)
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
# ========== STORIES API ==========
import os
from werkzeug.utils import secure_filename

@app.route('/api/stories/upload', methods=['POST'])
@login_required
def upload_story():
    if 'file' not in request.files:
        return jsonify({'error': 'Нет файла'}), 400
    
    f = request.files['file']
    if f.filename == '':
        return jsonify({'error': 'Файл не выбран'}), 400
    
    ext = f.filename.rsplit('.', 1)[1].lower() if '.' in f.filename else 'jpg'
    if ext not in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'mov', 'avi', 'webm']:
        return jsonify({'error': 'Только изображения и видео'}), 400
    
    file_type = 'video' if ext in ['mp4', 'mov', 'avi', 'webm'] else 'image'
    filename = f"story_{current_user.id}_{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(FILE_FOLDER, filename)
    f.save(filepath)
    
    caption = request.form.get('caption', '')
    
    story = Story(
        user_id=current_user.id,
        file_path=f'/static/uploads/{filename}',
        file_type=file_type,
        caption=caption,
        expires_at=datetime.utcnow() + timedelta(hours=24)
    )
    db.session.add(story)
    db.session.commit()
    
    return jsonify({'success': True, 'story_id': story.id})

@app.route('/api/stories/my')
@login_required
def api_my_stories():
    stories = Story.query.filter(
        Story.user_id == current_user.id,
        Story.expires_at > datetime.utcnow()
    ).order_by(Story.created_at.desc()).all()
    
    result = []
    for s in stories:
        result.append({
            'id': s.id,
            'file_path': s.file_path,
            'file_type': s.file_type,
            'caption': s.caption,
            'views': s.views_count,
            'created_at': s.created_at.isoformat(),
            'expires_in': int((s.expires_at - datetime.utcnow()).total_seconds())
        })
    return jsonify(result)

@app.route('/api/stories/feed')
@login_required
def api_stories_feed():
    # Получаем пользователей, с которыми есть переписка
    chat_users = db.session.query(User).join(
        Message,
        ((Message.sender_id == current_user.id) & (Message.receiver_id == User.id)) |
        ((Message.sender_id == User.id) & (Message.receiver_id == current_user.id))
    ).distinct().all()
    
    user_ids = [u.id for u in chat_users] + [current_user.id]
    
    stories = Story.query.filter(
        Story.user_id.in_(user_ids),
        Story.expires_at > datetime.utcnow()
    ).order_by(Story.user_id, Story.created_at.desc()).all()
    
    users_stories = {}
    for s in stories:
        if s.user_id not in users_stories:
            user = User.query.get(s.user_id)
            users_stories[s.user_id] = {
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'avatar': user.avatar
                },
                'stories': []
            }
        
        viewed = StoryView.query.filter_by(story_id=s.id, user_id=current_user.id).first()
        users_stories[s.user_id]['stories'].append({
            'id': s.id,
            'file_path': s.file_path,
            'file_type': s.file_type,
            'caption': s.caption,
            'views': s.views_count,
            'viewed': viewed is not None,
            'created_at': s.created_at.isoformat()
        })
    
    return jsonify(list(users_stories.values()))

@app.route('/api/stories/view/<int:story_id>', methods=['POST'])
@login_required
def view_story(story_id):
    story = Story.query.get(story_id)
    if not story or story.expires_at <= datetime.utcnow():
        return jsonify({'error': 'История не найдена'}), 404
    
    existing = StoryView.query.filter_by(story_id=story_id, user_id=current_user.id).first()
    if not existing:
        view = StoryView(story_id=story_id, user_id=current_user.id)
        db.session.add(view)
        story.views_count += 1
        db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/stories/delete/<int:story_id>', methods=['POST'])
@login_required
def delete_story(story_id):
    story = Story.query.get(story_id)
    if not story or story.user_id != current_user.id:
        return jsonify({'error': 'Нет прав'}), 403
    
    filepath = os.path.join(FILE_FOLDER, os.path.basename(story.file_path))
    if os.path.exists(filepath):
        os.remove(filepath)
    
    StoryView.query.filter_by(story_id=story_id).delete()
    db.session.delete(story)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/stories/has_unseen')
@login_required
def api_has_unseen_stories():
    chat_users = db.session.query(User).join(
        Message,
        ((Message.sender_id == current_user.id) & (Message.receiver_id == User.id)) |
        ((Message.sender_id == User.id) & (Message.receiver_id == current_user.id))
    ).distinct().all()
    
    user_ids = [u.id for u in chat_users]
    
    stories = Story.query.filter(
        Story.user_id.in_(user_ids),
        Story.user_id != current_user.id,
        Story.expires_at > datetime.utcnow()
    ).all()
    
    unseen_count = 0
    for s in stories:
        viewed = StoryView.query.filter_by(story_id=s.id, user_id=current_user.id).first()
        if not viewed:
            unseen_count += 1
    
    return jsonify({'has_unseen': unseen_count > 0, 'count': unseen_count})
# ========== ЗАПУСК ==========
# ---------- ЗВУКИ BEARGRAM (новая фича) ----------
@app.route('/soundlab')
@login_required
def soundlab():
    return render_template('soundlab.html')
from dating_routes import dating_bp
app.register_blueprint(dating_bp)
@app.route('/api/compatibility/<int:user_id>')
@login_required
def compatibility(user_id):
    other = User.query.get_or_404(user_id)
    if not current_user.birthday or not other.birthday:
        return jsonify({'error': 'У одного из вас не указана дата рождения'})
    def get_zodiac_sign(day, month):
        if (month == 3 and day >= 21) or (month == 4 and day <= 19): return 'Овен', '🔥'
        elif (month == 4 and day >= 20) or (month == 5 and day <= 20): return 'Телец', '🌍'
        elif (month == 5 and day >= 21) or (month == 6 and day <= 20): return 'Близнецы', '💨'
        elif (month == 6 and day >= 21) or (month == 7 and day <= 22): return 'Рак', '💧'
        elif (month == 7 and day >= 23) or (month == 8 and day <= 22): return 'Лев', '🔥'
        elif (month == 8 and day >= 23) or (month == 9 and day <= 22): return 'Дева', '🌍'
        elif (month == 9 and day >= 23) or (month == 10 and day <= 22): return 'Весы', '💨'
        elif (month == 10 and day >= 23) or (month == 11 and day <= 21): return 'Скорпион', '💧'
        elif (month == 11 and day >= 22) or (month == 12 and day <= 21): return 'Стрелец', '🔥'
        elif (month == 12 and day >= 22) or (month == 1 and day <= 19): return 'Козерог', '🌍'
        elif (month == 1 and day >= 20) or (month == 2 and day <= 18): return 'Водолей', '💨'
        else: return 'Рыбы', '💧'
    u1 = current_user.birthday; u2 = other.birthday
    s1, e1 = get_zodiac_sign(u1.day, u1.month)
    s2, e2 = get_zodiac_sign(u2.day, u2.month)
    comp = {('🔥','🔥'):80,('🔥','💨'):90,('🔥','🌍'):50,('🔥','💧'):30,('🌍','🌍'):85,('🌍','💧'):70,('🌍','💨'):40,('💨','💨'):75,('💨','💧'):45,('💧','💧'):95}
    pair = (e1,e2) if e1 <= e2 else (e2,e1)
    base = comp.get(pair,60)
    percent = min(98, max(30, base + random.randint(-5,8)))
    msg = '🔥 Идеальная пара!' if percent>=90 else '💫 Отлично!' if percent>=70 else '🌈 Возможно' if percent>=50 else '❄️ Сложно'
    return jsonify({'sign1':s1,'elem1':e1,'sign2':s2,'elem2':e2,'percent':percent,'message':msg})

# ---------- РУЧНОЙ БЭКАП (СКАЧАТЬ) ----------
import shutil
import os

@app.route('/admin/backup')
@login_required
def admin_backup():
    # Защита: только пользователь с ID = 1 может скачать бэкап
    if current_user.id != 1:
        flash('Нет доступа', 'danger')
        return redirect(url_for('chat'))
    
    db_path = '/app/data/messenger.db'
    if not os.path.exists(db_path):
        flash('База данных не найдена', 'danger')
        return redirect(url_for('chat'))

    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'messenger_backup_{timestamp}.db'
    backup_path = os.path.join('static', 'backups', backup_filename)
    os.makedirs('static/backups', exist_ok=True)
    shutil.copy2(db_path, backup_path)
    return send_file(backup_path, as_attachment=True)

# ---------- ВОССТАНОВЛЕНИЕ ИЗ БЭКАПА ----------
@app.route('/admin/restore', methods=['GET', 'POST'])
@login_required
def admin_restore():
    if current_user.id != 1:
        flash('Нет доступа', 'danger')
        return redirect(url_for('chat'))

    if request.method == 'POST':
        if 'backup_file' not in request.files:
            flash('Файл не выбран', 'danger')
            return redirect(request.url)
        file = request.files['backup_file']
        if file.filename == '':
            flash('Файл не выбран', 'danger')
            return redirect(request.url)
        if file and file.filename.endswith('.db'):
            db_path = '/app/data/messenger.db'
            if os.path.exists(db_path):
                os.remove(db_path)
            file.save(db_path)
            # ДАЁМ ПРАВА НА ЧТЕНИЕ И ЗАПИСЬ
            os.chmod(db_path, 0o666)
            flash('✅ База восстановлена! Перезапустите приложение.', 'success')
            return redirect(url_for('admin_restore'))
        else:
            flash('Только .db файлы', 'danger')

    return '''
    <!doctype html>
    <title>Восстановление базы</title>
    <h1>Загрузите файл бэкапа (.db)</h1>
    <form method=post enctype=multipart/form-data>
      <input type=file name=backup_file>
      <input type=submit value=Загрузить>
    </form>
    '''
# ---------- ДИАГНОСТИКА БАЗЫ (временно) ----------
@app.route('/admin/check_db')
@login_required
def admin_check_db():
    if current_user.id != 1:
        return 'Access denied', 403

    db_path = '/app/data/messenger.db'
    if not os.path.exists(db_path):
        return 'Файл базы данных не найден!', 404

    size = os.path.getsize(db_path)
    # получаем права в восьмеричном виде
    mode = oct(os.stat(db_path).st_mode)[-3:]
    return f'<p>Файл существует.</p><p>Размер: <b>{size}</b> байт</p><p>Права доступа: <b>{mode}</b></p>'

# ---------- СПИСОК ПОЛЬЗОВАТЕЛЕЙ (диагностика) ----------
@app.route('/admin/list_users')
@login_required
def admin_list_users():
    if current_user.id != 1:
        return 'Access denied', 403
    users = User.query.all()
    html = '<h2>Список пользователей в базе</h2><ul>'
    for u in users:
        html += f'<li>ID: {u.id}, Username: {u.username}</li>'
    html += '</ul>'
    return html
import base64

@app.route('/super-secret-backup-download')
def download_db():
    # Простейшая защита: проверяем токен в URL
    token = request.args.get('token', '')
    if token != 'MEGA_SECRET_TOKEN_123':
        return "Denied", 403

    db_path = app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')
    # Если путь не абсолютный, сделаем относительно корня проекта
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(__file__), db_path)

    if not os.path.exists(db_path):
        return "Database file not found", 404

    return send_file(db_path, as_attachment=True, download_name='messenger.db')
# ================= УМНОЕ ВОССТАНОВЛЕНИЕ БАЗЫ =================
import os, shutil, stat

with app.app_context():
    RESTORE_FILE = os.path.join('static', 'restore', 'restore.db')
    DB_FILE = '/app/data/messenger.db'   # путь, который у тебя в конфиге

    # Восстанавливаем только если базы нет или она пустая
    if not os.path.exists(DB_FILE) or os.path.getsize(DB_FILE) == 0:
        if os.path.exists(RESTORE_FILE):
            print(f"♻️  Восстанавливаю базу из {RESTORE_FILE} → {DB_FILE}")
            shutil.copy2(RESTORE_FILE, DB_FILE)
            # фиксим права, чтобы точно писалось
            os.chmod(DB_FILE, stat.S_IWRITE | stat.S_IREAD | stat.S_IWGRP | stat.S_IRGRP | stat.S_IROTH)
            print("✅ База восстановлена!")
        else:
            print("❌ Файл восстановления не найден – создаю чистую базу.")
            db.create_all()
    else:
        print("✅ База уже существует и не пуста – восстановление не требуется.")
@app.route('/api/ai/ask', methods=['POST'])
@login_required
def ask_ai():
    data = request.get_json()
    question = data.get('question', '').strip()
    
    if not question:
        return jsonify({'error': 'Пустой запрос'}), 400

    user_coins = get_user_coins(current_user.id)
    cost = 50

    if user_coins.balance < cost:
        return jsonify({'error': f'Недостаточно кристаллайзеров. Нужно {cost} 💎'}), 402

    OPENROUTER_API_KEY = "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"
    
    system_prompt = """Ты — Мишка из BearGram, дружелюбный и остроумный эксперт. 
Ты отвечаешь на сложные вопросы простым языком. Ты используешь молодёжный сленг, 
но при этом даёшь глубокие и развёрнутые ответы. 
В конце ответа всегда добавляешь что-то поддерживающее и мотивирующее. 
Твой ответ должен быть как от крутого друга-наставника. Используй эмодзи."""

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://127.0.0.1:5000",
                "X-Title": "BearGram"
            },
            json={
                "model": "meta-llama/llama-3.2-3b-instruct:free",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                "temperature": 0.9,
                "max_tokens": 300
            },
            timeout=30
        )

        if response.status_code == 200:
            answer = response.json()['choices'][0]['message']['content']
            user_coins.balance -= cost
            platform_coins = get_user_coins(1)
            if platform_coins:
                platform_coins.balance += cost
            db.session.commit()
            return jsonify({'success': True, 'answer': answer, 'new_balance': user_coins.balance})
        else:
            return jsonify({'error': f'Ошибка AI-сервера (код {response.status_code}). Попробуй позже.'}), 500

    except Exception as e:
        print(f"OpenRouter API error: {e}")
        return jsonify({'error': 'Не удалось связаться с AI. Попробуй позже.'}), 500
def init_shop_themes():
    with app.app_context():
        if ShopItem.query.filter_by(category='themes').count() == 0:
            themes = [
                ShopItem(name='Тёмная ночь BearGram', category='themes', item_type='theme', price=250, description='Официальная тёмная тема от BearGram. Тёмный фон, золотые акценты.', author_id=1),
                ShopItem(name='Синий океан', category='themes', item_type='theme', price=250, description='Глубокий синий цвет. Спокойствие и надёжность.', author_id=1),
                ShopItem(name='Зелёный лес', category='themes', item_type='theme', price=250, description='Природная зелень. Свежесть и энергия.', author_id=1),
                ShopItem(name='Розовые грёзы', category='themes', item_type='theme', price=350, description='Нежная тема с сердечками. Для романтиков.', author_id=1),
                ShopItem(name='Звёздное небо', category='themes', item_type='theme', price=350, description='Тёмная тема с мерцающими звёздами. Магия космоса.', author_id=1),
                ShopItem(name='Королевский пурпур', category='themes', item_type='theme', price=500, description='Премиальная тема с анимированными узорами. Для настоящих королей.', author_id=1)
            ]
            for theme in themes:
                db.session.add(theme)
            db.session.commit()
            print("✅ Темы для магазина созданы")
with app.app_context():
    db.create_all()
    init_golden_fund()
    init_shop_themes()
@app.route('/shop/author/<int:author_id>')
@login_required
def shop_author_items(author_id):
    items = ShopItem.query.filter_by(author_id=author_id, is_active=True).filter(
        ShopItem.category.in_(['drops', 'merch'])
    ).all()
    return jsonify([{
        'id': item.id,
        'name': item.name,
        'price': item.price,
        'preview': item.preview,
        'category': item.category,
        'stock': item.stock,
        'sales_count': item.sales_count
    } for item in items])
@app.route('/grrr/airdrop', methods=['POST'])
@login_required
def claim_grrr_airdrop():
    # Проверяем, получал ли уже пользователь аирдроп
    if get_grrr_balance(current_user.id) > 0:
        return jsonify({'error': 'Вы уже получили аирдроп!'}), 400
    
    # Начисляем 100 $GRRR
    add_grrr(current_user.id, 100)
    
    return jsonify({
        'success': True,
        'message': '🎉 Вы получили 100 $GRRR! Добро пожаловать в стаю хищников!',
        'new_balance': get_grrr_balance(current_user.id)
    })
@app.route('/grrr')
@login_required
def grrr_page():
    balance = get_grrr_balance(current_user.id)
    coins = get_user_coins(current_user.id)
    return render_template('grrr.html', grrr_balance=balance, coins_balance=coins.balance)

@app.route('/grrr/convert', methods=['POST'])
@login_required
def convert_to_grrr():
    amount = int(request.form.get('amount', 0))
    if amount < 1:
        flash('Минимальная сумма: 1 💎', 'danger')
        return redirect(url_for('grrr_page'))
    success, message = convert_coins_to_grrr(current_user.id, amount)
    flash(message, 'success' if success else 'danger')
    return redirect(url_for('grrr_page'))

def get_grrr_balance(user_id):
    grrr = GRRRToken.query.filter_by(user_id=user_id).first()
    if not grrr:
        grrr = GRRRToken(user_id=user_id, balance=0)
        db.session.add(grrr)
        db.session.commit()
    return grrr.balance

def add_grrr(user_id, amount):
    grrr = GRRRToken.query.filter_by(user_id=user_id).first()
    if not grrr:
        grrr = GRRRToken(user_id=user_id, balance=amount)
        db.session.add(grrr)
    else:
        grrr.balance += amount
    db.session.commit()
    return grrr.balance

def convert_coins_to_grrr(user_id, amount_coins):
    coins = get_user_coins(user_id)
    if coins.balance < amount_coins:
        return False, "Недостаточно кристаллайзеров"
    coins.balance -= amount_coins
    add_grrr(user_id, amount_coins)
    db.session.commit()
    return True, f"Конвертировано {amount_coins} 💎 → {amount_coins} $GRRR"
@app.route('/grrr/withdraw', methods=['POST'])
@login_required
def withdraw_grrr():
    address = request.form.get('address', '').strip()
    amount = float(request.form.get('amount', 0))
    
    # Проверки
    if not address or len(address) < 42:
        flash('Введите корректный адрес кошелька (0x...)', 'danger')
        return redirect(url_for('grrr_page'))
    
    if amount < 10:
        flash('Минимальная сумма вывода: 10 $GRRR', 'danger')
        return redirect(url_for('grrr_page'))
    
    grrr_balance = get_grrr_balance(current_user.id)
    if grrr_balance < amount:
        flash('Недостаточно $GRRR', 'danger')
        return redirect(url_for('grrr_page'))
    
    # Комиссия 10%
    fee = amount * 0.1
    net_amount = amount - fee
    
    # Списываем $GRRR
    grrr = GRRRToken.query.filter_by(user_id=current_user.id).first()
    grrr.balance -= amount
    
    # Комиссия платформе
    platform_grrr = GRRRToken.query.filter_by(user_id=1).first()
    if not platform_grrr:
        platform_grrr = GRRRToken(user_id=1, balance=fee)
        db.session.add(platform_grrr)
    else:
        platform_grrr.balance += fee
    
    # Здесь будет реальная отправка в блокчейн
    # Пока сохраняем заявку
    withdrawal = GRRRWithdrawal(
        user_id=current_user.id,
        address=address,
        amount=amount,
        fee=fee,
        net_amount=net_amount,
        status='pending'
    )
    db.session.add(withdrawal)
    db.session.commit()
    
    flash(f'Заявка на вывод {net_amount} $GRRR создана! Комиссия: {fee} $GRRR (10%)', 'success')
    return redirect(url_for('grrr_page'))
# ========== BEAR WALLET ==========
@app.route('/bearpay')
@login_required
def bear_wallet():
    tab = request.args.get('tab', 'send')
    coins = get_user_coins(current_user.id)
    grrr_balance = get_grrr_balance(current_user.id)
    
    available_invoices = BEARInvoice.query.filter_by(status='pending').filter(
        BEARInvoice.seller_id != current_user.id
    ).order_by(BEARInvoice.created_at.desc()).limit(20).all()
    
    my_invoices = BEARInvoice.query.filter_by(seller_id=current_user.id).order_by(
        BEARInvoice.created_at.desc()
    ).limit(20).all()
    
    stakes = BEARStake.query.filter_by(user_id=current_user.id, is_active=True).order_by(
        BEARStake.created_at.desc()
    ).all()
    
    total_staked = sum(s.amount for s in stakes)
    total_platform_staked = db.session.query(db.func.sum(BEARStake.amount)).filter_by(
        is_active=True
    ).scalar() or 0
    total_stakers = db.session.query(db.func.count(db.distinct(BEARStake.user_id))).filter_by(
        is_active=True
    ).scalar() or 0
    
    return render_template('bear_wallet.html',
                         tab=tab,
                         coins=coins,
                         grrr_balance=grrr_balance,
                         available_invoices=available_invoices,
                         my_invoices=my_invoices,
                         stakes=stakes,
                         total_staked=total_staked,
                         total_platform_staked=total_platform_staked,
                         total_stakers=total_stakers,
                         now=datetime.utcnow())

# ========== ОБМЕННИК 💎 → $GRRR (5% комиссия) ==========
@app.route('/bearpay/exchange', methods=['POST'])
@login_required
def bear_exchange():
    amount = int(request.form.get('amount', 0))
    if amount < 1:
        flash('Минимальная сумма: 1 💎', 'danger')
        return redirect(url_for('bear_wallet', tab='bank'))
    
    coins = get_user_coins(current_user.id)
    if coins.balance < amount:
        flash('Недостаточно кристаллайзеров', 'danger')
        return redirect(url_for('bear_wallet', tab='bank'))
    
    # Комиссия 5%
    commission = int(amount * 0.05)
    net_amount = amount - commission
    
    coins.balance -= amount
    add_grrr(current_user.id, net_amount)
    
    # Комиссия платформе (админ ID=1)
    platform_grrr = GRRRToken.query.filter_by(user_id=1).first()
    if not platform_grrr:
        platform_grrr = GRRRToken(user_id=1, balance=commission)
        db.session.add(platform_grrr)
    else:
        platform_grrr.balance += commission
    
    db.session.commit()
    flash(f'✅ Обменяно {amount} 💎 → {net_amount} $GRRR (комиссия 5%: {commission} 💎)', 'success')
    return redirect(url_for('bear_wallet', tab='bank'))

# ========== СОЗДАТЬ СЧЁТ ==========
@app.route('/bearpay/create_invoice', methods=['POST'])
@login_required
def bear_create_invoice():
    amount = int(request.form.get('amount', 0))
    description = request.form.get('description', '')
    
    if amount < 10:
        flash('Минимальная сумма счёта: 10 💎', 'danger')
        return redirect(url_for('bear_wallet', tab='pay'))
    
    invoice = BEARInvoice(
        seller_id=current_user.id,
        amount=amount,
        description=description,
        status='pending'
    )
    db.session.add(invoice)
    db.session.commit()
    
    flash(f'📤 Счёт на {amount} 💎 выставлен!', 'success')
    return redirect(url_for('bear_wallet', tab='pay'))

# ========== ОПЛАТИТЬ СЧЁТ ==========
@app.route('/bearpay/pay/<int:invoice_id>', methods=['GET', 'POST'])
@login_required
def bear_pay_invoice(invoice_id):
    invoice = BEARInvoice.query.get_or_404(invoice_id)
    
    if invoice.seller_id == current_user.id:
        flash('Нельзя оплатить свой же счёт', 'danger')
        return redirect(url_for('bear_wallet', tab='pay'))
    
    if invoice.status == 'paid':
        flash('Счёт уже оплачен', 'info')
        return redirect(url_for('bear_wallet', tab='pay'))
    
    if request.method == 'POST':
        coins = get_user_coins(current_user.id)
        if coins.balance < invoice.amount:
            flash('Недостаточно кристаллайзеров', 'danger')
            return redirect(url_for('bear_wallet', tab='pay'))
        
        coins.balance -= invoice.amount
        
        seller_coins = get_user_coins(invoice.seller_id)
        seller_coins.balance += invoice.amount
        
        invoice.buyer_id = current_user.id
        invoice.status = 'paid'
        db.session.commit()
        
        flash(f'✅ Счёт на {invoice.amount} 💎 оплачен! Продавец получил средства.', 'success')
        return redirect(url_for('bear_wallet', tab='pay'))
    
    seller = User.query.get(invoice.seller_id)
    coins = get_user_coins(current_user.id)
    return render_template('bear_pay.html', invoice=invoice, seller=seller, coins=coins)

# ========== ВКЛАД В $GRRR ==========
@app.route('/bearbank/stake_grrr', methods=['POST'])
@login_required
def bear_stake_grrr():
    level = request.form.get('level')
    amount = int(request.form.get('amount', 0))
    
    config = {
        'grrr_100': {'rate': 25, 'months': 3, 'min': 100},
        'grrr_500': {'rate': 40, 'months': 6, 'min': 500},
        'grrr_1000': {'rate': 60, 'months': 12, 'min': 1000},
        'grrr_2000': {'rate': 80, 'months': 18, 'min': 2000},
        'grrr_5000': {'rate': 100, 'months': 24, 'min': 5000}
    }
    
    if level not in config:
        flash('Неверный уровень вклада', 'danger')
        return redirect(url_for('bear_wallet', tab='bank'))
    
    cfg = config[level]
    if amount < cfg['min']:
        flash(f'Минимальная сумма: {cfg["min"]} $GRRR', 'danger')
        return redirect(url_for('bear_wallet', tab='bank'))
    
    grrr_balance = get_grrr_balance(current_user.id)
    if grrr_balance < amount:
        flash('Недостаточно $GRRR. Обменяйте кристаллайзеры в обменнике.', 'danger')
        return redirect(url_for('bear_wallet', tab='bank'))
    
    # Списываем $GRRR
    grrr = GRRRToken.query.filter_by(user_id=current_user.id).first()
    grrr.balance -= amount
    
    # Создаём вклад
    stake = BEARStake(
        user_id=current_user.id,
        amount=amount,
        currency='grrr',
        level=level,
        annual_rate=cfg['rate'],
        created_at=datetime.utcnow(),
        ends_at=datetime.utcnow() + timedelta(days=30 * cfg['months']),
        is_active=True
    )
    db.session.add(stake)
    db.session.commit()
    
    flash(f'✅ Вклад открыт! {amount} $GRRR под {cfg["rate"]}% на {cfg["months"]} мес.', 'success')
    return redirect(url_for('bear_wallet', tab='bank'))

# ========== ЗАБРАТЬ ПРОЦЕНТЫ ==========
@app.route('/bearbank/claim/<int:stake_id>', methods=['POST'])
@login_required
def bank_claim_interest(stake_id):
    stake = BEARStake.query.get_or_404(stake_id)
    
    if stake.user_id != current_user.id:
        return jsonify({'error': 'Не ваш вклад'}), 403
    
    if not stake.is_active:
        return jsonify({'error': 'Вклад завершён'}), 400
    
    now = datetime.utcnow()
    last = stake.last_payout_at or stake.created_at
    days_passed = (now - last).days
    
    if days_passed < 30:
        days_remaining = 30 - days_passed
        return jsonify({'error': f'Проценты можно забирать раз в 30 дней. Осталось {days_remaining} дн.'}), 400
    
    # Начисляем проценты
    months_passed = days_passed // 30
    monthly_rate = stake.annual_rate / 12 / 100
    reward = int(stake.amount * monthly_rate * months_passed)
    
    if reward > 0:
        add_grrr(current_user.id, reward)
        stake.last_payout_at = now
        db.session.commit()
        return jsonify({'success': True, 'message': f'✅ Начислено {reward} $GRRR! ({months_passed} мес. × {stake.annual_rate}%)'})
    
    return jsonify({'error': 'Нет доступных процентов'}), 400
# ========== BEAR NODE ==========
@app.route('/bearnode')
@login_required
def bear_node_page():
    grrr_balance = get_grrr_balance(current_user.id)
    
    nodes = BEARNode.query.filter_by(user_id=current_user.id, is_active=True).all()
    
    total_nodes = BEARNode.query.filter_by(is_active=True).count()
    total_network = db.session.query(db.func.sum(BEARNode.amount)).filter_by(is_active=True).scalar() or 0
    
    return render_template('bearnode.html',
                         grrr_balance=grrr_balance,
                         nodes=nodes,
                         total_nodes=total_nodes,
                         total_network=total_network)

@app.route('/bearnode/buy', methods=['POST'])
@login_required
def buy_bear_node():
    level = request.form.get('level')
    
    config = {
        'small': {'rate': 12, 'amount': 1000},
        'medium': {'rate': 25, 'amount': 5000},
        'large': {'rate': 50, 'amount': 10000}
    }
    
    if level not in config:
        flash('Неверный уровень ноды', 'danger')
        return redirect(url_for('bear_node_page'))
    
    cfg = config[level]
    grrr_balance = get_grrr_balance(current_user.id)
    
    if grrr_balance < cfg['amount']:
        flash(f'Недостаточно $GRRR. Нужно {cfg["amount"]} $GRRR', 'danger')
        return redirect(url_for('bear_node_page'))
    
    # Списываем $GRRR
    grrr = GRRRToken.query.filter_by(user_id=current_user.id).first()
    grrr.balance -= cfg['amount']
    
    # Создаём ноду
    node = BEARNode(
        user_id=current_user.id,
        amount=cfg['amount'],
        level=level,
        annual_rate=cfg['rate'],
        created_at=datetime.utcnow(),
        is_active=True
    )
    db.session.add(node)
    db.session.commit()
    
    flash(f'🔋 Нода "{level}" куплена! {cfg["amount"]} $GRRR заблокированы, доход {cfg["rate"]}% годовых.', 'success')
    return redirect(url_for('bear_node_page'))

@app.route('/bearnode/claim/<int:node_id>', methods=['POST'])
@login_required
def claim_node_reward(node_id):
    node = BEARNode.query.get_or_404(node_id)
    
    if node.user_id != current_user.id:
        return jsonify({'error': 'Не ваша нода'}), 403
    
    if not node.is_active:
        return jsonify({'error': 'Нода неактивна'}), 400
    
    now = datetime.utcnow()
    last = node.last_payout_at or node.created_at
    
    if (now - last).days < 30:
        days_left = 30 - (now - last).days
        return jsonify({'error': f'Проценты можно забирать раз в 30 дней. Осталось {days_left} дн.'}), 400
    
    monthly_rate = node.annual_rate / 12 / 100
    reward = int(node.amount * monthly_rate)
    
    if reward > 0:
        add_grrr(current_user.id, reward)
        node.last_payout_at = now
        db.session.commit()
        return jsonify({'success': True, 'message': f'✅ Начислено {reward} $GRRR! ({node.annual_rate}% годовых)'})
    
    return jsonify({'error': 'Нет доступных процентов'}), 400
# ========== МАЙНИНГ ==========
@app.route('/mining')
@login_required
def mining_page():
    grrr_balance = get_grrr_balance(current_user.id)
    
    # Активная сессия майнинга
    active_session = MiningSession.query.filter_by(user_id=current_user.id, is_active=True).first()
    
    # Если майнинг идёт дольше 24 часов — останавливаем
    if active_session:
        now = datetime.utcnow()
        if (now - active_session.started_at).total_seconds() > 86400:  # 24 часа
            active_session.is_active = False
            active_session.ended_at = now
            active_session.hours = int((active_session.ended_at - active_session.started_at).total_seconds() / 3600)
            # Начисляем за 24 часа макс
            reward = 24 * 0.5  # 0.5 GRRR в час
            commission = reward * 0.1  # 10% комиссия
            active_session.reward = reward - commission
            
            # Начисляем пользователю
            add_grrr(current_user.id, active_session.reward)
            
            # Комиссия платформе
            platform_grrr = GRRRToken.query.filter_by(user_id=1).first()
            if platform_grrr:
                platform_grrr.balance += commission
            
            db.session.commit()
            flash(f'⛏️ Майнинг завершён! +{active_session.reward} $GRRR за 24 часа (комиссия 10%)', 'success')
            active_session = None
    
    # Всего намайнено
    total_mined = db.session.query(db.func.sum(MiningSession.reward)).filter_by(user_id=current_user.id).scalar() or 0
    
    # Сколько пользователей майнит сейчас
    mining_active = MiningSession.query.filter_by(is_active=True).count()
    
    # Сессии пользователя
    mining_sessions = MiningSession.query.filter_by(user_id=current_user.id).order_by(MiningSession.started_at.desc()).limit(10).all()
    
    # Прогресс текущей сессии
    mining_progress = 0
    mining_hours = 0
    if active_session:
        now = datetime.utcnow()
        seconds_passed = (now - active_session.started_at).total_seconds()
        mining_progress = min(100, int(seconds_passed / 86400 * 100))
        mining_hours = int(seconds_passed / 3600)
    
    return render_template('mining.html',
                         grrr_balance=grrr_balance,
                         total_mined=total_mined,
                         mining_active=mining_active,
                         user_mining=active_session is not None,
                         mining_progress=mining_progress,
                         mining_hours=mining_hours,
                         mining_sessions=mining_sessions)

@app.route('/mining/start', methods=['POST'])
@login_required
def start_mining():
    active = MiningSession.query.filter_by(user_id=current_user.id, is_active=True).first()
    if active:
        return jsonify({'error': 'Майнинг уже запущен! Остановите текущий.'}), 400
    
    session = MiningSession(user_id=current_user.id)
    db.session.add(session)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '⛏️ Майнинг $GRRR запущен! +0.5 $GRRR/час (комиссия 10%). Не закрывайте мессенджер.'})

@app.route('/mining/stop', methods=['POST'])
@login_required
def stop_mining():
    session = MiningSession.query.filter_by(user_id=current_user.id, is_active=True).first()
    if not session:
        return jsonify({'error': 'Нет активного майнинга'}), 400
    
    now = datetime.utcnow()
    hours = (now - session.started_at).total_seconds() / 3600
    
    if hours < 1:
        # Минимум 1 час для начисления
        db.session.delete(session)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Майнинг остановлен. Минимум 1 час для начисления.'})
    
    # Начисляем
    reward = hours * 0.5  # 0.5 GRRR в час
    commission = reward * 0.1  # 10% комиссия
    net_reward = reward - commission
    
    session.is_active = False
    session.ended_at = now
    session.hours = int(hours)
    session.reward = net_reward
    
    add_grrr(current_user.id, net_reward)
    
    # Комиссия платформе
    platform_grrr = GRRRToken.query.filter_by(user_id=1).first()
    if platform_grrr:
        platform_grrr.balance += commission
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': f'✅ Намайнено {net_reward:.2f} $GRRR за {int(hours)} ч. (комиссия 10%: {commission:.2f} $GRRR)'})
# ========== БАРАХОЛКА $GRRR ==========
@app.route('/flea/buy/<int:item_id>', methods=['POST'])
@login_required
def buy_flea_item(item_id):
    item = ShopItem.query.get_or_404(item_id)
    
    if item.category != 'flea':
        return jsonify({'error': 'Этот товар не из барахолки'}), 400
    
    if item.stock > 0 and item.sales_count >= item.stock:
        return jsonify({'error': 'Товар распродан'}), 400
    
    if item.author_id == current_user.id:
        return jsonify({'error': 'Нельзя купить свой товар'}), 400
    
    grrr_balance = get_grrr_balance(current_user.id)
    if grrr_balance < item.price:
        return jsonify({'error': f'Недостаточно $GRRR. Нужно {item.price} $GRRR'}), 402
    
    # Списываем $GRRR с покупателя
    buyer_grrr = GRRRToken.query.filter_by(user_id=current_user.id).first()
    buyer_grrr.balance -= item.price
    
    # Начисляем продавцу (90%)
    seller_grrr = GRRRToken.query.filter_by(user_id=item.author_id).first()
    if not seller_grrr:
        seller_grrr = GRRRToken(user_id=item.author_id, balance=0)
        db.session.add(seller_grrr)
    seller_grrr.balance += int(item.price * 0.9)
    
    # Платформа (10%)
    platform_grrr = GRRRToken.query.filter_by(user_id=1).first()
    if platform_grrr:
        platform_grrr.balance += int(item.price * 0.1)
    
    # Запись покупки
    purchase = ShopPurchase(item_id=item_id, user_id=current_user.id, price_paid=item.price)
    db.session.add(purchase)
    item.sales_count += 1
    db.session.commit()
    
    return jsonify({
        'success': True,
        'new_balance': buyer_grrr.balance,
        'message': f'✅ Куплено! {item.price} $GRRR переведены продавцу.'
    })
# ========== ОТЗЫВЫ ==========
@app.route('/flea/reviews/<int:user_id>')
@login_required
def flea_reviews(user_id):
    reviews = ShopReview.query.filter_by(seller_id=user_id).order_by(ShopReview.created_at.desc()).limit(50).all()
    return jsonify({
        'reviews': [{
            'author': r.buyer.username,
            'rating': r.rating,
            'text': r.text,
            'date': r.created_at.strftime('%d.%m.%Y %H:%M')
        } for r in reviews]
    })

@app.route('/flea/review', methods=['POST'])
@login_required
def flea_review():
    purchase_id = int(request.form.get('purchase_id', 0))
    rating = int(request.form.get('rating', 5))
    text = request.form.get('text', '').strip()
    
    purchase = ShopPurchase.query.get(purchase_id)
    if not purchase:
        return jsonify({'error': 'Покупка не найдена'}), 404
    
    if purchase.user_id != current_user.id:
        return jsonify({'error': 'Не ваша покупка'}), 403
    
    existing = ShopReview.query.filter_by(purchase_id=purchase_id).first()
    if existing:
        return jsonify({'error': 'Отзыв уже оставлен'}), 400
    
    review = ShopReview(
        purchase_id=purchase_id,
        seller_id=purchase.item.author_id,
        buyer_id=current_user.id,
        rating=rating,
        text=text
    )
    db.session.add(review)
    
    # Обновляем рейтинг и счётчик продавца
    seller = User.query.get(purchase.item.author_id)
    if seller:
        all_reviews = ShopReview.query.filter_by(seller_id=seller.id).all()
        if all_reviews:
            avg_rating = sum(r.rating for r in all_reviews) / len(all_reviews)
            seller.rating = round(avg_rating, 1)
        seller.reviews_count = len(all_reviews)
    
    db.session.commit()
    
    return jsonify({'success': True, 'message': '✅ Отзыв отправлен! Рейтинг обновлён.'})
@app.route('/add_contact/<int:user_id>', methods=['POST'])
@login_required
def add_contact(user_id):
    if user_id == current_user.id:
        return jsonify({'error': 'Нельзя добавить себя'}), 400
    existing = Contact.query.filter_by(user_id=current_user.id, contact_id=user_id).first()
    if existing:
        return jsonify({'error': 'Уже в контактах'}), 400
    db.session.add(Contact(user_id=current_user.id, contact_id=user_id))
    db.session.commit()
    return jsonify({'success': True, 'message': '✅ Добавлен!'})

@app.route('/remove_contact/<int:user_id>', methods=['POST'])
@login_required
def remove_contact(user_id):
    contact = Contact.query.filter_by(user_id=current_user.id, contact_id=user_id).first()
    if contact:
        db.session.delete(contact)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'Не найден'}), 404
@app.route('/api/check_phones', methods=['POST'])
@login_required
def check_phones():
    data = request.get_json()
    phones = data.get('phones', [])
    
    users = User.query.filter(User.phone_number.in_(phones), User.phone_verified == True).all()
    
    return jsonify({
        'users': [{
            'id': u.id,
            'username': u.username,
            'phone': u.phone_number[-4:].rjust(len(u.phone_number), '*')
        } for u in users if u.id != current_user.id]
    })
# ========== МАРШРУТЫ (перед if __name__) ==========

  
# ========== API ДЛЯ МИШКИ ==========
@app.route('/api/my_balance')
@login_required
def api_my_balance():
    coins = get_user_coins(current_user.id)
    grrr = get_grrr_balance(current_user.id)
    return jsonify({'coins': coins.balance, 'grrr': grrr})

@app.route('/api/report_user', methods=['POST'])
@login_required
def api_report_user():
    username = request.form.get('username', '').strip().lstrip('@')
    reason = request.form.get('reason', '').strip()
    if not username:
        return jsonify({'error': 'Укажи @username'}), 400
    reported = User.query.filter_by(username=username).first()
    if not reported:
        reported = User.query.filter_by(username_link='@'+username).first()
    if not reported:
        return jsonify({'error': 'Пользователь не найден'}), 404
    if reported.id == current_user.id:
        return jsonify({'error': 'Нельзя жаловаться на себя'}), 400
    existing_report = UserReport.query.filter_by(reporter_id=current_user.id, reported_id=reported.id, status='open').first()
    if existing_report:
        return jsonify({'error': 'Вы уже отправили жалобу'}), 400
    report = UserReport(reporter_id=current_user.id, reported_id=reported.id, reason=reason, status='open')
    db.session.add(report)
    open_reports_count = db.session.query(db.func.count(db.distinct(UserReport.reporter_id))).filter_by(reported_id=reported.id, status='open').scalar()
    if open_reports_count >= 5:
        reported.is_active = False
        UserReport.query.filter_by(reported_id=reported.id, status='open').update({'status': 'resolved'})
        db.session.commit()
        return jsonify({'success': True, 'message': f'🚫 @{username} заблокирован! 5 жалоб.'})
    db.session.commit()
    return jsonify({'success': True, 'message': f'✅ Жалоба отправлена. Нужно ещё {5 - open_reports_count}.'})


@app.route('/api/send_grrr', methods=['POST'])
@login_required
def api_send_grrr():
    username = request.form.get('username', '').strip().lstrip('@')
    amount = float(request.form.get('amount', 0))
    if not username or amount < 0.01:
        return jsonify({'error': 'Укажи @username и сумму'}), 400
    receiver = User.query.filter_by(username=username).first() or User.query.filter_by(username_link='@'+username).first()
    if not receiver:
        return jsonify({'error': 'Пользователь не найден'}), 404
    if receiver.id == current_user.id:
        return jsonify({'error': 'Нельзя отправить себе'}), 400
    sender_grrr = get_grrr_balance(current_user.id)
    if sender_grrr < amount:
        return jsonify({'error': f'Недостаточно $GRRR. У вас {sender_grrr:.2f}'}), 402
    commission = amount * 0.1
    net = amount - commission
    grrr_sender = GRRRToken.query.filter_by(user_id=current_user.id).first()
    grrr_sender.balance -= amount
    grrr_receiver = GRRRToken.query.filter_by(user_id=receiver.id).first()
    if not grrr_receiver:
        grrr_receiver = GRRRToken(user_id=receiver.id, balance=0)
        db.session.add(grrr_receiver)
    grrr_receiver.balance += net
    platform_grrr = GRRRToken.query.filter_by(user_id=1).first()
    if not platform_grrr:
        platform_grrr = GRRRToken(user_id=1, balance=0)
        db.session.add(platform_grrr)
    platform_grrr.balance += commission
    db.session.commit()
    
    # Push-уведомление
    send_push_notification(receiver.id, f'💰 +{net:.2f} $GRRR', f'Перевод от {current_user.username}', '/grrr')
    
    return jsonify({'success': True, 'message': f'✅ {net:.2f} $GRRR → @{username}', 'new_balance': grrr_sender.balance})
# ========== РЕФЕРАЛЬНАЯ СИСТЕМА ==========
@app.route('/api/referral_stats')
@login_required
def referral_stats():
    invited_count = Referral.query.filter_by(inviter_id=current_user.id, status='registered').count()
    total_reward = db.session.query(db.func.sum(Referral.reward_amount)).filter_by(inviter_id=current_user.id, reward_claimed=True).scalar() or 0
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
    top_referrers = db.session.query(Referral.inviter_id, db.func.count(Referral.id).label('count')).filter(Referral.status=='registered', Referral.created_at>=month_start).group_by(Referral.inviter_id).order_by(db.desc('count')).limit(10).all()
    top_list = []
    for r in top_referrers:
        u = User.query.get(r.inviter_id)
        if u: top_list.append({'username': u.username, 'count': r.count})
    return jsonify({'invited_count': invited_count, 'total_reward': total_reward, 'top_referrers': top_list, 'referral_link': f'https://beargram.up.railway.app/register?ref={current_user.referral_code}'})

@app.route('/api/claim_referral_reward', methods=['POST'])
@login_required
def claim_referral_reward():
    code = request.form.get('code', '').strip()
    referral = Referral.query.filter_by(referral_code=code, inviter_id=current_user.id, reward_claimed=False, status='registered').first()
    if not referral:
        return jsonify({'error': 'Награда не найдена'}), 404
    coins = get_user_coins(current_user.id)
    coins.balance += 25
    referral.reward_claimed = True
    referral.reward_amount = 25
    db.session.commit()
    return jsonify({'success': True, 'message': '✅ +25 💎!', 'new_balance': coins.balance})
# ========== ИГРЫ ==========
# Страница всех игр
@app.route('/games')
@login_required
def games_page():
    user_games = UserGame.query.filter_by(is_approved=True).order_by(UserGame.plays_count.desc()).limit(20).all()
    return render_template('games/index.html', user_games=user_games)

# Загрузка игры
@app.route('/games/upload', methods=['POST'])
@login_required
def upload_game():
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    icon = request.form.get('icon', '🎮').strip()
    
    if not title:
        flash('Введи название игры', 'danger')
        return redirect(url_for('games_page'))
    
    is_premium = get_premium_status(current_user.id)
    if not is_premium:
        count = UserGame.query.filter_by(user_id=current_user.id).count()
        if count >= 1:
            flash('Бесплатно 1 игра. Premium — безлимитно.', 'danger')
            return redirect(url_for('games_page'))
    
    if 'game_file' not in request.files:
        flash('Выбери HTML-файл', 'danger')
        return redirect(url_for('games_page'))
    
    f = request.files['game_file']
    if f.filename == '' or not f.filename.endswith('.html'):
        flash('Только HTML-файлы', 'danger')
        return redirect(url_for('games_page'))
    
    filename = f"game_{current_user.id}_{uuid.uuid4().hex}.html"
    filepath = os.path.join('static/games', filename)
    os.makedirs('static/games', exist_ok=True)
    f.save(filepath)
    
    game = UserGame(
        user_id=current_user.id,
        title=title,
        description=description,
        icon=icon[:2],
        file_path=f'/static/games/{filename}'
    )
    db.session.add(game)
    db.session.commit()
    
    flash('✅ Игра опубликована!', 'success')
    return redirect(url_for('games_page'))

# Запуск игры
@app.route('/games/play/<int:game_id>')
@login_required
def play_game(game_id):
    game = UserGame.query.get_or_404(game_id)
    game.plays_count += 1
    db.session.commit()
    skins = GameSkin.query.filter((GameSkin.game_id == game_id) | (GameSkin.game_id == None)).all()
    return render_template('games/play.html', game=game, skins=skins)

# Оценка игры
@app.route('/games/rate/<int:game_id>', methods=['POST'])
@login_required
def rate_game(game_id):
    rating = int(request.form.get('rating', 5))
    game = UserGame.query.get_or_404(game_id)
    total = game.rating * game.ratings_count
    game.ratings_count += 1
    game.rating = round((total + rating) / game.ratings_count, 1)
    db.session.commit()
    return jsonify({'success': True})

# ========== МАСТЕРСКАЯ СКИНОВ ==========

# Страница скинов
@app.route('/games/skins')
@login_required
def skins_page():
    skins = GameSkin.query.order_by(GameSkin.sales_count.desc()).limit(50).all()
    return render_template('games/skins.html', skins=skins)

# Загрузка скина
@app.route('/games/skins/upload', methods=['POST'])
@login_required
def upload_skin():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    price = int(request.form.get('price', 50))
    css_content = request.form.get('css_content', '').strip()
    preview_color = request.form.get('preview_color', '#f9ca24').strip()
    game_id = request.form.get('game_id', type=int)
    
    if not name or not css_content:
        flash('Название и CSS обязательны', 'danger')
        return redirect(url_for('skins_page'))
    
    if price < 10 or price > 500:
        flash('Цена от 10 до 500 💎', 'danger')
        return redirect(url_for('skins_page'))
    
    skin = GameSkin(
        author_id=current_user.id,
        game_id=game_id,
        name=name,
        description=description,
        price=price,
        css_content=css_content,
        preview_color=preview_color
    )
    db.session.add(skin)
    db.session.commit()
    
    flash('✅ Скин опубликован!', 'success')
    return redirect(url_for('skins_page'))

# Покупка скина
@app.route('/games/skins/buy/<int:skin_id>', methods=['POST'])
@login_required
def buy_skin(skin_id):
    skin = GameSkin.query.get_or_404(skin_id)
    
    if skin.author_id == current_user.id:
        return jsonify({'error': 'Нельзя купить свой скин'}), 400
    
    existing = SkinPurchase.query.filter_by(skin_id=skin_id, buyer_id=current_user.id).first()
    if existing:
        return jsonify({'error': 'Скин уже куплен'}), 400
    
    coins = get_user_coins(current_user.id)
    if coins.balance < skin.price:
        return jsonify({'error': f'Недостаточно 💎. Нужно {skin.price}'}), 402
    
    coins.balance -= skin.price
    skin.sales_count += 1
    
    # Автору 50%
    author_coins = get_user_coins(skin.author_id)
    author_coins.balance += int(skin.price * 0.5)
    
    purchase = SkinPurchase(skin_id=skin_id, buyer_id=current_user.id, price_paid=skin.price)
    db.session.add(purchase)
    db.session.commit()
    
    return jsonify({'success': True, 'css': skin.css_content, 'message': '✅ Скин куплен!'})

# Мои скины
@app.route('/games/skins/my')
@login_required
def my_skins():
    my_skins = GameSkin.query.filter_by(author_id=current_user.id).all()
    purchases = SkinPurchase.query.filter_by(buyer_id=current_user.id).all()
    return render_template('games/my_skins.html', my_skins=my_skins, purchases=purchases)
@app.route('/games/review/<int:game_id>', methods=['POST'])
@login_required
def review_game(game_id):
    rating = int(request.form.get('rating', 5))
    text = request.form.get('text', '').strip()
    
    game = UserGame.query.get_or_404(game_id)
    
    review = GameReview(
        game_id=game_id,
        user_id=current_user.id,
        rating=rating,
        text=text
    )
    db.session.add(review)
    
    # Обновляем рейтинг игры
    total = game.rating * game.ratings_count
    game.ratings_count += 1
    game.rating = round((total + rating) / game.ratings_count, 1)
    db.session.commit()
    
    return jsonify({'success': True, 'message': '✅ Отзыв отправлен!'})

@app.route('/games/reviews/<int:game_id>')
@login_required
def game_reviews(game_id):
    reviews = GameReview.query.filter_by(game_id=game_id).order_by(GameReview.created_at.desc()).limit(50).all()
    return jsonify({
        'reviews': [{
            'author': r.user.username,
            'rating': r.rating,
            'text': r.text,
            'date': r.created_at.strftime('%d.%m.%Y %H:%M')
        } for r in reviews]
    })
@app.route('/api/spend_coins', methods=['POST'])
@login_required
def api_spend_coins():
    amount = int(request.form.get('amount', 0))
    coins = get_user_coins(current_user.id)
    if coins.balance < amount:
        return jsonify({'success': False, 'error': 'Недостаточно 💎'})
    coins.balance -= amount
    db.session.commit()
    return jsonify({'success': True, 'new_balance': coins.balance})
@app.route('/games/water-sort')
@login_required
def game_water_sort():
    return render_template('games/water_sort.html')

@app.route('/games/bubbles')
@login_required
def game_bubbles():
    return render_template('games/bubbles.html')

@app.route('/games/block-blast')
@login_required
def game_block_blast():
    return render_template('games/block_blast.html')

@app.route('/games/clicker')
@login_required
def game_clicker():
    return render_template('games/clicker.html')

@app.route('/games/honey-ninja')
@login_required
def game_honey_ninja():
    return render_template('games/honey_ninja.html')

@app.route('/games/flappy-bear')
@login_required
def game_flappy_bear():
    return render_template('games/flappy_bear.html')
# ========== МАРШРУТ /api/push/subscribe ==========
@app.route('/api/push/subscribe', methods=['POST'])
@login_required
def push_subscribe():
    subscription = request.get_json()
    current_user.push_subscription = json.dumps(subscription)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/push/vapid_public_key')
def vapid_public_key():
    return VAPID_PUBLIC_KEY

@app.route('/api/unread_count')
@login_required
def unread_count():
    count = 0
    
    # Непрочитанные сообщения
    count += Message.query.filter_by(receiver_id=current_user.id, is_read=False).count()
    
    # Непрочитанные групповые сообщения
    user_groups = [gm.group_id for gm in GroupMember.query.filter_by(user_id=current_user.id).all()]
    if user_groups:
        count += GroupMessage.query.filter(
            GroupMessage.group_id.in_(user_groups),
            GroupMessage.sender_id != current_user.id,
            ~GroupMessage.deleted_for.contains(str(current_user.id))
        ).count()
    
    # Новые переводы $GRRR (системные сообщения)
    system_user = User.query.filter_by(username='BearGram').first()
    if system_user:
        count += Message.query.filter_by(
            sender_id=system_user.id,
            receiver_id=current_user.id,
            is_read=False
        ).count()
    
    return jsonify({'count': count})


@app.route('/api/notify', methods=['POST'])
@login_required
def send_push_notification(user_id, title, body, url='/chat'):
    user = db.session.get(User, user_id)
    if not user or not user.push_subscription:
        return False
    try:
        import requests as http_requests
        import jwt, time
        subscription = json.loads(user.push_subscription)
        private_key = base64.urlsafe_b64decode(VAPID_PRIVATE_KEY.encode())
        private_key = serialization.load_der_private_key(private_key, password=None, backend=default_backend())
        claims = {"sub": "mailto:admin@beargram.com", "aud": subscription['endpoint'].split('/')[2], "exp": int(time.time()) + 86400}
        token = jwt.encode(claims, private_key, algorithm="ES256", headers={"typ":"JWT","alg":"ES256"})
        headers = {"Authorization": f"WebPush {token}", "Crypto-Key": f"p256ecdsa={VAPID_PUBLIC_KEY}", "Content-Type": "application/json", "TTL": "86400"}
        payload = json.dumps({"title": title, "body": body, "url": url})
        http_requests.post(subscription['endpoint'], data=payload, headers=headers, timeout=10)
        return True
    except Exception as e:
        print(f"Push error: {e}")
        return False

# Инициализация Firebase
cred = credentials.Certificate('firebase-key.json')
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

def send_push_notification(user_id, title, body, url='/chat'):
    user = db.session.get(User, user_id)
    if not user or not user.fcm_token:
        return False
    try:
        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data={'url': url},
            token=user.fcm_token
        )
        messaging.send(message)
        return True
    except Exception as e:
        print(f"FCM error: {e}")
        return False
@app.route('/api/fcm/subscribe', methods=['POST'])
@login_required
def fcm_subscribe():
    token = request.get_json().get('token')
    if token:
        current_user.fcm_token = token
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'error': 'no token'}), 400

@app.route('/games/2048')
@login_required
def game_2048():
    return render_template('games/2048.html')
@app.route('/games/wordle')
@login_required
def game_wordle():
    return render_template('games/wordle.html')
@app.route('/api/feed')
@login_required
def api_feed():
    subscribed_ids = [sub.channel_id for sub in ChannelSubscriber.query.filter_by(user_id=current_user.id).all()]
    
    if not subscribed_ids:
        posts = ChannelPost.query.join(Channel).filter(
            Channel.is_private == False
        ).order_by(ChannelPost.timestamp.desc()).limit(30).all()
    else:
        posts = ChannelPost.query.filter(
            ChannelPost.channel_id.in_(subscribed_ids)
        ).order_by(ChannelPost.timestamp.desc()).limit(30).all()

    def popularity(post):
        likes = ChannelPostLike.query.filter_by(post_id=post.id).count()
        comments = ChannelComment.query.filter_by(post_id=post.id).count()
        views = post.views or 0
        return (likes * 1.5) + (comments * 2) + (views * 0.1)

    posts = sorted(posts, key=popularity, reverse=True)

    result = []
    for p in posts:
        channel = p.channel
        likes = ChannelPostLike.query.filter_by(post_id=p.id).count()
        comments = ChannelComment.query.filter_by(post_id=p.id).count()

        # Собираем вложения
        attachments = []
        if p.attachments:
            try:
                attachments = json.loads(p.attachments)
            except:
                pass
        elif p.file_path:
            attachments = [{
                'path': p.file_path,
                'type': p.file_type or 'document',
                'name': p.file_name or 'file'
            }]

        result.append({
            'id': p.id,
            'content': p.content[:500] if p.content else '',
            'timestamp': p.timestamp.strftime('%d.%m.%Y %H:%M'),
            'views': p.views or 0,
            'likes': likes,
            'comments': comments,
            'channel_name': channel.name,
            'channel_avatar': channel.avatar,
            'channel_id': channel.id,
            'attachments': attachments
        })

    return jsonify({'posts': result})
@app.route('/api/feed/like/<int:post_id>', methods=['POST'])
@login_required
def api_feed_like(post_id):
    existing = ChannelPostLike.query.filter_by(post_id=post_id, user_id=current_user.id).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        like = ChannelPostLike(post_id=post_id, user_id=current_user.id)
        db.session.add(like)
        liked = True
    db.session.commit()
    likes = ChannelPostLike.query.filter_by(post_id=post_id).count()
    return jsonify({'success': True, 'liked': liked, 'likes': likes})
@app.route('/api/music/add', methods=['POST'])
@login_required
def add_music():
    url = request.form.get('url', '').strip()
    title = request.form.get('title', '').strip() or 'Без названия'
    if not url:
        return jsonify({'success': False, 'error': 'Нужна ссылка'})
    track = MusicTrack(user_id=current_user.id, title=title, file_path=url)
    db.session.add(track)
    db.session.commit()
    return jsonify({'success': True, 'track_id': track.id})

@app.route('/api/music/listen/<int:track_id>', methods=['POST'])
def listen_music(track_id):
    track = MusicTrack.query.get(track_id)
    if track:
        track.listens += 1
        db.session.commit()
    return jsonify({'success': True, 'listens': track.listens if track else 0})

@app.route('/music/top')
def music_top():
    top_artists = db.session.query(User.username, db.func.sum(MusicTrack.listens).label('total_listens')) \
        .join(MusicTrack).group_by(User.id).order_by(db.desc('total_listens')).limit(10).all()
    top_uploaders = db.session.query(User.username, db.func.count(MusicTrack.id).label('track_count')) \
        .join(MusicTrack).group_by(User.id).order_by(db.desc('track_count')).limit(10).all()
    return render_template('music_top.html', top_artists=top_artists, top_uploaders=top_uploaders)
@app.route('/api/music/upload', methods=['POST'])
@login_required
def upload_music():
    f = request.files.get('file')
    if not f:
        return jsonify({'success': False, 'error': 'Нет файла'})
    title = request.form.get('title', 'Без названия')
    # сохраняем файл
    filename = f"music_{current_user.id}_{uuid.uuid4().hex}.mp3"
    save_path = os.path.join('static/music', filename)
    os.makedirs('static/music', exist_ok=True)
    f.save(save_path)
    track = MusicTrack(user_id=current_user.id, title=title, file_path='/static/music/' + filename)
    db.session.add(track)
    db.session.commit()
    return jsonify({'success': True, 'track_id': track.id})

@app.route('/api/music/delete/<int:track_id>', methods=['POST'])
@login_required
def delete_music(track_id):
    track = MusicTrack.query.get_or_404(track_id)
    if track.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Не твой трек'}), 403
    # удаляем файл, если хранится локально
    full_path = os.path.join(app.root_path, track.file_path.lstrip('/'))
    if os.path.exists(full_path):
        os.remove(full_path)
    db.session.delete(track)
    db.session.commit()
    return jsonify({'success': True})
@app.route('/api/music/search')
def search_music():
    q = request.args.get('q', '').strip()
    if len(q) < 1:
        return jsonify({'tracks': []})
    # ищем публичные треки, у которых автор не приватный
    tracks = MusicTrack.query.join(User).filter(
        User.is_private == False,
        MusicTrack.title.ilike(f'%{q}%')
    ).order_by(MusicTrack.listens.desc()).limit(10).all()
    result = [{'id': t.id, 'title': t.title, 'file_path': t.file_path, 'author': t.author.username} for t in tracks]
    return jsonify({'tracks': result})
@app.route('/api/tab/golden')
@login_required
def tab_golden():
    videos = GoldenContent.query.order_by(GoldenContent.created_at.desc()).limit(20).all()
    # Рендерим только внутренний блок (без основного шаблона)
    return render_template('golden_content.html', videos=videos)

@app.route('/api/tab/voice')
@login_required
def tab_voice():
    # Просто перенаправляем на список каналов, который уже умеет работать
    return redirect(url_for('voice_channels'))

@app.route('/api/tab/dating')
@login_required
def tab_dating():
    return render_template('dating_content.html')

@app.route('/api/tab/games')
@login_required
def tab_games():
    # Отдаём список игр (без основного layout)
    user_games = UserGame.query.filter_by(is_approved=True).order_by(UserGame.plays_count.desc()).all()
    return render_template('games_content.html', user_games=user_games)
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
