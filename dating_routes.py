# dating_routes.py — финальная версия (без relationship, с гарантией)
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from datetime import datetime
import os
from werkzeug.utils import secure_filename

dating_bp = Blueprint('dating', __name__)

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'mp4', 'webm'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def ensure_tables():
    db = current_app.extensions['sqlalchemy']
    try:
        db.engine.execute("CREATE TABLE IF NOT EXISTS user_profile (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE, city TEXT, interests TEXT, bio TEXT, photo TEXT, preference TEXT DEFAULT 'all')")
        db.engine.execute("CREATE TABLE IF NOT EXISTS like (id INTEGER PRIMARY KEY, liker_id INTEGER, liked_id INTEGER, is_match BOOLEAN DEFAULT 0)")
        db.engine.execute("ALTER TABLE user ADD COLUMN birthday DATE")
        db.engine.execute("ALTER TABLE user ADD COLUMN gender TEXT")
        db.engine.execute("ALTER TABLE user_profile ADD COLUMN preference TEXT DEFAULT 'all'")
    except:
        pass

@dating_bp.route('/dating')
@login_required
def dating():
    return render_template('dating.html')

@dating_bp.route('/api/next_profile')
@login_required
def next_profile():
    ensure_tables()
    db = current_app.extensions['sqlalchemy']
    from app import User, UserProfile, Like

    liked_ids = [l.liked_id for l in db.session.query(Like).filter_by(liker_id=current_user.id).all()]
    exclude = set(liked_ids) | {current_user.id}

    my_profile = db.session.query(UserProfile).filter_by(user_id=current_user.id).first()
    preference = my_profile.preference if my_profile else 'all'

    query = db.session.query(UserProfile).filter(UserProfile.user_id.notin_(exclude))

    if preference != 'all':
        suitable_user_ids = db.session.query(User.id).filter(User.gender == preference).subquery()
        query = query.filter(UserProfile.user_id.in_(suitable_user_ids))

    profile = query.order_by(db.func.random()).first()
    if not profile:
        return jsonify(None)

    user = db.session.query(User).get(profile.user_id)
    birthday = getattr(user, 'birthday', None)
    return jsonify({
        'id': user.id,
        'username': user.username,
        'city': profile.city,
        'interests': profile.interests,
        'bio': profile.bio,
        'photo': profile.photo,
        'birthday': birthday.isoformat() if birthday else None
    })

@dating_bp.route('/api/like/<int:liked_id>', methods=['POST'])
@login_required
def like_user(liked_id):
    ensure_tables()
    db = current_app.extensions['sqlalchemy']
    from app import Like

    existing = db.session.query(Like).filter_by(liker_id=current_user.id, liked_id=liked_id).first()
    if existing:
        return jsonify({'status': 'already_liked'})
    like = Like(liker_id=current_user.id, liked_id=liked_id)
    db.session.add(like)
    mutual = db.session.query(Like).filter_by(liker_id=liked_id, liked_id=current_user.id).first()
    if mutual:
        like.is_match = True
        mutual.is_match = True
        db.session.commit()
        return jsonify({'status': 'match', 'partner': liked_id})
    db.session.commit()
    return jsonify({'status': 'liked'})

@dating_bp.route('/api/dislike/<int:liked_id>', methods=['POST'])
@login_required
def dislike_user(liked_id):
    ensure_tables()
    db = current_app.extensions['sqlalchemy']
    from app import Like

    existing = db.session.query(Like).filter_by(liker_id=current_user.id, liked_id=liked_id).first()
    if not existing:
        like = Like(liker_id=current_user.id, liked_id=liked_id, is_match=False)
        db.session.add(like)
        db.session.commit()
    return jsonify({'status': 'disliked'})

@dating_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    ensure_tables()
    db = current_app.extensions['sqlalchemy']
    from app import UserProfile

    city = request.form.get('city', '')
    interests = request.form.get('interests', '')
    bio = request.form.get('bio', '')
    birthday_str = request.form.get('birthday', '')
    gender = request.form.get('gender', '')
    preference = request.form.get('preference', 'all')
    photo_file = request.files.get('photo')
    photo_path = None

    if birthday_str:
        try:
            current_user.birthday = datetime.strptime(birthday_str, '%Y-%m-%d').date()
        except:
            pass

    if gender:
        current_user.gender = gender

    if photo_file and photo_file.filename and allowed_file(photo_file.filename):
        filename = secure_filename(photo_file.filename)
        upload_folder = os.path.join('static', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, filename)
        photo_file.save(filepath)
        photo_path = f'/static/uploads/{filename}'

    profile = db.session.query(UserProfile).filter_by(user_id=current_user.id).first()
    if not profile:
        profile = UserProfile(user_id=current_user.id)
        db.session.add(profile)
    profile.city = city
    profile.interests = interests
    profile.bio = bio
    profile.preference = preference
    if photo_path:
        profile.photo = photo_path
    db.session.commit()
    flash('Анкета обновлена!', 'success')
    return redirect(url_for('profile'))

@dating_bp.route('/my_likes')
@login_required
def my_likes():
    db = current_app.extensions['sqlalchemy']
    from app import Like, User

    incoming = db.session.query(Like).filter_by(liked_id=current_user.id).all()
    outgoing = db.session.query(Like).filter_by(liker_id=current_user.id).all()
    matches = [l for l in incoming if l.is_match]

    def user_info(uid):
        u = db.session.query(User).get(uid)
        return {'id': u.id, 'username': u.username, 'avatar': u.avatar} if u else None

    return render_template('my_likes.html',
                           incoming=[{'user': user_info(l.liker_id), 'is_match': l.is_match} for l in incoming],
                           outgoing=[{'user': user_info(l.liked_id), 'is_match': l.is_match} for l in outgoing],
                           matches=[{'user': user_info(l.liker_id)} for l in matches])