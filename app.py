from flask import Flask, render_template, url_for, g, request, redirect, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from DB import FDataBase
import sqlite3
from UserLogin import UserLogin
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

DATABASE = os.path.join(app.root_path, 'blog.db')
SECRET_KEY = 'fdgfh78@#5?>gfhf89dx,v06k'

app.config.from_object(__name__)

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = "Авторизуйтесь для доступа к закрытым страницам"
login_manager.login_message_category = "success"


def connect_db():
    conn = sqlite3.connect(app.config['DATABASE'])
    conn.row_factory = sqlite3.Row
    return conn


class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    intro = db.Column(db.String(300), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    text = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    author_id = db.Column(db.String, db.ForeignKey('profiles.id'))
    author_name = db.Column(db.String, db.ForeignKey('profiles.name'))
    category = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return '<Article %r>' % self.id


class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(500), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"user {self.id}"


class Profiles(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    number_of_articles = db.Column(db.Integer)

    def __repr__(self):
        return f"user {self.id}"


def get_db():
    '''Соединение с БД, если оно еще не установлено'''
    if not hasattr(g, 'link_db'):
        g.link_db = connect_db()
    return g.link_db


dbase = None


@app.before_request
def before_request():
    global dbase
    db1 = get_db()
    dbase = FDataBase(db1)


@login_manager.user_loader
def load_user(user_id):
    print("load_user")
    return UserLogin().fromDB(user_id, dbase)



@app.route('/post/<id>')
@login_required
def post(id):
    article = Article.query.filter(Article.id == id).first()
    return render_template("one_post.html", article=article)


@app.route('/post/redit/<id>', methods=['POST', 'GET'])
@login_required
def edit(id):
    if request.method == 'POST':
        title = request.form['title']
        intro = request.form['intro']
        text = request.form['text']
        category = request.form['category']
        article = Article.query.get(id)
        article.title = title
        article.intro = intro
        article.text = text
        article.category = category
        try:
            db.session.commit()
            return redirect(url_for('profile'))
        except:
            return "При изменении статьи произошла ошибка"
    else:
        article = Article.query.filter(Article.id == id).first()
        return render_template("redit.html", article=article)


@app.route('/post/delete/<id>')
@login_required
def delete(id):
    try:
        db.session.query(Article).filter(Article.id == id).delete()
        db.session.commit()
    except:
        return "При удалении статьи произошла ошибка"

    return redirect(url_for('profile'))


@app.route('/posts/<category>')
@login_required
def posts(category):
    if category == 'all':
        articles = Article.query.order_by(Article.date.desc()).all()
    else:
        articles = Article.query.filter(Article.category == category).order_by(Article.date.desc()).all()

    return render_template("post.html", articles=articles)


@app.route('/sign-up', methods=['POST', 'GET'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('profile'))
    msg = ""
    if request.method == 'POST':
        email = request.form['email']
        name = request.form['name']
        psw = request.form['password']
        if Users.query.filter(Users.email == email).all():
            msg = "Пользователь с таким логином уже существует"
        else:
            try:
                hash = generate_password_hash(psw)
                u = Users(email=email, password=hash)
                db.session.add(u)
                db.session.flush()

                p = Profiles(user_id=u.id, name=name, number_of_articles=0)
                db.session.add(p)
                db.session.commit()
            except:
                db.session.rollback()
                msg = 'Ошибка добавления в бд'
    return render_template("register.html", title="Регистрация", msg=msg)


@app.route('/')
@app.route('/home')
@app.route("/login", methods=["POST", "GET"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('profile'))

    if request.method == "POST":
        user = dbase.getUserByEmail(request.form['email'])
        if user and check_password_hash(user['password'], request.form['password']):
            userlogin = UserLogin().create(user)
            rm = True if request.form.get('remainme') else False
            login_user(userlogin, remember=rm)
            return redirect(request.args.get("next") or url_for("profile"))

        flash("Неверная пара логин/пароль", "error")

    return render_template("login.html", title="Авторизация")


@app.route('/create', methods=['POST', 'GET'])
@login_required
def create_article():
    if request.method == 'POST':
        title = request.form['title']
        intro = request.form['intro']
        text = request.form['text']
        category = request.form['category']
        res = Profiles.query.filter(Profiles.user_id == current_user.get_id()).first()
        article = Article(title=title, intro=intro, text=text, author_id=res.id, category=category,
                          author_name=res.name)
        try:
            db.session.add(article)
            db.session.commit()
            return redirect('/')
        except:
            return "При добавлении статьи произошла ошибка"
    else:
        return render_template("create.html")


@app.route('/logout')
def logout():
    logout_user()
    flash("Вы вышли из аккаунта", "success")
    return redirect(url_for("profile"))


@app.route('/profile')
@login_required
def profile():
    profile = Profiles.query.filter(Profiles.user_id == current_user.get_id()).first()
    articles = Article.query.filter(Article.author_id == profile.id).all()
    user = Users.query.filter(Users.id == current_user.get_id()).first()
    return render_template("profile.html", profile=profile, user=user, articles=articles)


if __name__ == "__main__":
    app.run(debug=True)
