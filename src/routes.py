from flask import Flask, render_template, request, redirect, url_for, session, flash
from src import db
from src.models import User, Question, Answer
from werkzeug.security import check_password_hash
import base64
from . import auth
from werkzeug.utils import secure_filename
import os

# Разрешенные расширения для аватарок
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def init_app(app):
    app.register_blueprint(auth.bp)  # Регистрируем blueprint
    # Создание директории для загрузок, если ее нет
    uploads_dir = os.path.join(app.root_path, 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)  # создаем папку, если ее нет
    app.config['UPLOAD_FOLDER'] = uploads_dir  # Сохраняем путь в конфигурации

    # Функция для проверки расширения файла
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

    @app.route('/')
    @app.route('/main')
    def main():
        if 'email' not in session:
            return redirect(url_for('login'))

        # Получаем все вопросы из базы данных
        user = User.query.filter_by(email=session['email']).first()
        return render_template('main.html', user=user)

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            email = request.form.get('email')
            username = request.form.get('username')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            description = request.form.get('description')

            # Проверка длины пароля
            if len(password) < 8:
                flash('Пароль должен содержать минимум 8 символов.', 'error')
                return redirect(url_for('register'))
            if len(password) > 64:
                flash('Пароль не должен превышать 64 символа.', 'error')
                return redirect(url_for('register'))

            # Проверка паролей
            if password != confirm_password:
                flash('Пароли не совпадают.', 'error')
                return redirect(url_for('register'))

            # Проверка, существует ли пользователь
            if User.query.filter_by(email=email).first():
                flash('Пользователь с таким логином уже существует!', 'error')
                return redirect(url_for('register'))

            # Создаем нового пользователя
            new_user = User(email=email, username=username, description=description)
            new_user.set_password(password)

            # Обработка аватарки
            if 'avatar' in request.files:
                avatar_file = request.files['avatar']
                if avatar_file.filename != '':
                    if not allowed_file(avatar_file.filename):
                        flash('Недопустимый формат файла. Разрешены только изображения.', 'error')
                        return redirect(url_for('register'))

                    filename = secure_filename(avatar_file.filename)
                    avatar_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    avatar_file.save(avatar_path)
                    new_user.avatar = filename  # Сохраняем имя файла

            db.session.add(new_user)
            db.session.commit()

            flash('Вы успешно зарегистрировались!', 'success')
            return redirect(url_for('login'))

        return render_template('register.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')
            user = User.query.filter_by(email=email).first()

            if user and user.check_password(password):
                session['username'] = user.username
                session['email'] = user.email
                return redirect(url_for('main'))
            else:
                flash('Неверный логин или пароль.', 'error')  # Flash error
                return redirect(url_for('login'))  # Redirect back to login

        return render_template('login.html')

    @app.route('/forgot_password', methods=['GET', 'POST'])
    def forgot_password():
        if request.method == 'POST':
            email = request.form.get('email')
            user = User.query.filter_by(email=email).first()

            if user:
                # Генерация токена для восстановления пароля
                reset_token = user.generate_reset_token()
                db.session.commit()

                # Отправка email с ссылкой для восстановления
                reset_link = url_for('reset_password', token=reset_token, _external=True)
                message = MIMEText(f'Для восстановления пароля перейдите по ссылке: {reset_link}')
                message['Subject'] = 'Восстановление пароля'
                message['From'] = EMAIL_FROM
                message['To'] = email

                try:
                    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                        server.starttls()
                        server.login(SMTP_USERNAME, SMTP_PASSWORD)
                        server.sendmail(EMAIL_FROM, [email], message.as_string())
                    flash('Ссылка для восстановления пароля отправлена на ваш email.', 'success')
                except Exception as e:
                    flash('Ошибка при отправке email.', 'error')
                    print(f"Error sending email: {e}")

                return redirect(url_for('login'))
            else:
                flash('Пользователь с таким email не найден.', 'error')
                return redirect(url_for('forgot_password'))

        return render_template('forgot_password.html')

    @app.route('/answer_question/<int:question_id>', methods=['GET', 'POST'])
    def answer_question(question_id):
        # Получаем вопрос из базы данных
        question = Question.query.get_or_404(question_id)

        if request.method == 'POST':
            user_answer = request.form.get('answer')  # Ответ пользователя

            # Проверяем, правильный ли ответ
            is_correct = (user_answer == question.correct_answer)

            # Сохраняем ответ в базе данных
            new_answer = Answer(
                user_name=session['username'],
                question_id=question.id,
                user_answer=user_answer,
                is_correct=is_correct
            )
            db.session.add(new_answer)
            db.session.commit()

            # Сообщаем пользователю, правильный ли ответ
            if is_correct:
                flash('Правильный ответ!', 'success')
            else:
                flash('Неправильный ответ. Попробуйте еще раз.', 'error')

            return redirect(url_for('main'))

        return render_template('answer_question.html', question=question)

    @app.route('/upload_avatar', methods=['GET', 'POST'])
    def upload_avatar():
        if 'email' not in session:
            return redirect(url_for('login'))

        if request.method == 'POST':
            # Проверяем, что файл был отправлен
            if 'avatar' not in request.files:
                flash('Файл не выбран.', 'error')
                return redirect(url_for('upload_avatar'))

            avatar_file = request.files['avatar']

            # Проверяем, что файл имеет допустимое имя
            if avatar_file.filename == '':
                flash('Файл не выбран.', 'error')
                return redirect(url_for('upload_avatar'))

            # Проверяем, что файл имеет допустимое расширение
            if not allowed_file(avatar_file.filename):
                flash('Недопустимый формат файла. Разрешены только изображения.', 'error')
                return redirect(url_for('upload_avatar'))

            # Сохраняем файл
            filename = secure_filename(avatar_file.filename)
            avatar_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            avatar_file.save(avatar_path)

            # Обновляем аватар пользователя в базе данных
            user = User.query.filter_by(email=session['email']).first()

            # Удаляем старую аватарку, если она есть
            if user.avatar and isinstance(user.avatar, str):
                old_avatar_path = os.path.join(app.config['UPLOAD_FOLDER'], user.avatar)
                if os.path.exists(old_avatar_path):
                    os.remove(old_avatar_path)

            user.avatar = avatar_path
            db.session.commit()

            flash('Аватар успешно загружен!', 'success')
            return redirect(url_for('main'))

        return render_template('upload_avatar.html')

    @app.route('/answer/<text>/<fromm>')
    def answer(text, fromm):
        return render_template('answer.html', text=text, fromm=fromm)
