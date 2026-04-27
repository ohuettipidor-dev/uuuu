# dating_routes.py — дейтинг с Premium-лимитами (исправленная версия)
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date, timedelta
import os

dating_bp = Blueprint('dating', __name__)

DAILY_LIKES_LIMIT = 50   # бесплатных лайков в сутки

# Вспомогательная функция для получения статуса Premium (чтобы не дублировать код)
def _get_premium_status(user_id):
    from app import Subscription
    sub = Subscription.query.filter_by(user_id=user_id).first()
    if sub and sub.expires_at and sub.expires_at > datetime.utcnow():
        return True
    return False

# ====================== СТРАНИЦЫ ======================
@dating_bp.route('/dating')
@login_required
def dating():
    return render_template('dating.html')

@dating_bp.route('/my_likes')
@login_required
def my_likes():
    from app import db, User, Like
    incoming = Like.query.filter_by(liked_id=current_user.id).all()
    outgoing = Like.query.filter_by(liker_id=current_user.id).all()
    matches = [l for l in incoming if l.is_match]

    def user_info(uid):
        u = User.query.get(uid)
        return {'id': u.id, 'username': u.username, 'avatar': u.avatar} if u else None

    return render_template('my_likes.html',
                           incoming=[{'user': user_info(l.liker_id), 'is_match': l.is_match} for l in incoming],
                           outgoing=[{'user': user_info(l.liked_id), 'is_match': l.is_match} for l in outgoing],
                           matches=[{'user': user_info(l.liker_id)} for l in matches])

# ====================== API ======================
@dating_bp.route('/api/next_profile')
@login_required
def next_profile():
    from app import db, User, UserProfile, Like

    liked_ids = [l.liked_id for l in Like.query.filter_by(liker_id=current_user.id).all()]
    exclude = set(liked_ids) | {current_user.id}

    my_profile = UserProfile.query.filter_by(user_id=current_user.id).first()
    preference = my_profile.preference if my_profile else 'all'

    query = UserProfile.query.filter(UserProfile.user_id.notin_(exclude))

    if preference != 'all':
        suitable_user_ids = [u.id for u in User.query.filter_by(gender=preference).all()]
        if suitable_user_ids:
            query = query.filter(UserProfile.user_id.in_(suitable_user_ids))
        else:
            return jsonify(None)

    profile = query.order_by(db.func.random()).first()
    if not profile:
        return jsonify(None)

    user = User.query.get(profile.user_id)
    birthday = getattr(user, 'birthday', None)
    return jsonify({
        'id': user.id,
        'username': user.username,
        'avatar': user.avatar,
        'city': profile.city,
        'interests': profile.interests,
        'bio': profile.bio,
        'photo': profile.photo,
        'birthday': birthday.isoformat() if birthday else None
    })

@dating_bp.route('/api/like/<int:liked_id>', methods=['POST'])
@login_required
def like_user(liked_id):
    from app import db, User, Like

    if not _get_premium_status(current_user.id):
        today = date.today()
        if current_user.last_likes_reset != today:
            current_user.daily_likes_count = 0
            current_user.last_likes_reset = today
            db.session.commit()

        if current_user.daily_likes_count >= DAILY_LIKES_LIMIT:
            return jsonify({'error': 'Лимит лайков на сегодня исчерпан.', 'limit_reached': True}), 403

    existing = Like.query.filter_by(liker_id=current_user.id, liked_id=liked_id).first()
    if existing:
        return jsonify({'status': 'already_liked'})

    like = Like(liker_id=current_user.id, liked_id=liked_id)
    db.session.add(like)
    current_user.daily_likes_count += 1
    db.session.commit()

    mutual = Like.query.filter_by(liker_id=liked_id, liked_id=current_user.id).first()
    if mutual:
        like.is_match = True
        mutual.is_match = True
        db.session.commit()
        return jsonify({'status': 'match', 'partner': liked_id})

    remaining = DAILY_LIKES_LIMIT - current_user.daily_likes_count if not _get_premium_status(current_user.id) else None
    return jsonify({'status': 'liked', 'remaining_likes': remaining})

@dating_bp.route('/api/dislike/<int:liked_id>', methods=['POST'])
@login_required
def dislike_user(liked_id):
    from app import db, User, Like
    existing = Like.query.filter_by(liker_id=current_user.id, liked_id=liked_id).first()
    if not existing:
        like = Like(liker_id=current_user.id, liked_id=liked_id, is_match=False)
        db.session.add(like)
        db.session.commit()
    return jsonify({'status': 'disliked'})

@dating_bp.route('/api/who_liked_me')
@login_required
def who_liked_me():
    if not _get_premium_status(current_user.id):
        return jsonify({'error': 'Требуется Premium'}), 403

    from app import db, User, Like
    likers = Like.query.filter_by(liked_id=current_user.id, is_match=False).all()
    result = []
    for like in likers:
        user = User.query.get(like.liker_id)
        result.append({'id': user.id, 'username': user.username, 'avatar': user.avatar})
    return jsonify(result)

@dating_bp.route('/update_profile', methods=['POST'])
@login_required
def update_profile():
    from app import db, User, UserProfile
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

    if photo_file and photo_file.filename:
        from werkzeug.utils import secure_filename
        filename = secure_filename(photo_file.filename)
        upload_folder = os.path.join('static', 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        filepath = os.path.join(upload_folder, filename)
        photo_file.save(filepath)
        photo_path = f'/static/uploads/{filename}'

    profile = UserProfile.query.filter_by(user_id=current_user.id).first()
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