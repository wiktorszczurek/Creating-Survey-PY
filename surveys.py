from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    session,
)
from flask_login import (
    LoginManager,
    login_required,
    login_user,
    logout_user,
    UserMixin,
    current_user,
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm, CSRFProtect
from wtforms import (
    StringField,
    SubmitField,
    HiddenField,
    FieldList,
    FormField,
    PasswordField,
    TextAreaField,
    RadioField,
    BooleanField,
)
from wtforms.validators import DataRequired
from datetime import timedelta, datetime, date
from wtforms import SelectField
import pytz
from pytz import timezone


app = Flask(__name__)
csrf = CSRFProtect(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = None


app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
db = SQLAlchemy(app)

app.config["SECRET_KEY"] = "tajne_haslo"


users = {
    "user": {"password": "11111111", "role": "user"},
    "admin": {"password": "11111111", "role": "admin"},
}


class User(UserMixin):
    def __init__(self, id):
        self.id = id
        self.name = id
        self.password = users[id]["password"]
        self.role = users[id]["role"]


class Survey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    questions = db.relationship("Question", backref="survey", lazy=True)
    notes = db.relationship("Note", backref="survey", lazy=True)


class CreateSurveyForm(FlaskForm):
    title = StringField("Tytuł", validators=[DataRequired()])
    submit = SubmitField("Utwórz ankietę")


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=False)
    survey_id = db.Column(db.Integer, db.ForeignKey("survey.id"), nullable=False)


class CompletedSurvey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    survey_id = db.Column(db.Integer, db.ForeignKey("survey.id"), nullable=False)
    answers = db.relationship("Answer", backref="completed_survey", lazy=True)


class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    completed_survey_id = db.Column(
        db.Integer, db.ForeignKey("completed_survey.id"), nullable=False
    )
    question_id = db.Column(db.Integer, db.ForeignKey("question.id"), nullable=False)
    response_tak = db.Column(db.Boolean, nullable=False)
    response_nie = db.Column(db.Boolean, nullable=False)
    explanation = db.Column(db.String(500), nullable=True)
    question = db.relationship("Question", backref="answers")


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Zapamiętaj mnie")
    submit = SubmitField("Zaloguj się")


class QuestionForm(FlaskForm):
    content = StringField(
        "Pytanie",
        validators=[DataRequired()],
        render_kw={"placeholder": "Napisz pytanie"},
    )
    submit = SubmitField("Dodaj pytanie")


class SingleAnswerForm(FlaskForm):
    response_tak = BooleanField("Tak")
    response_nie = BooleanField("Nie")
    explanation = TextAreaField(
        "Jeśli nie, to dlaczego", render_kw={"placeholder": "Jeśli nie, dlaczego?"}
    )


class AnswerForm(FlaskForm):
    name = StringField("Imię i nazwisko", validators=[DataRequired()])
    answers = FieldList(FormField(SingleAnswerForm))
    submit = SubmitField("Zapisz odpowiedź")


class PageView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    page_name = db.Column(db.String(100), nullable=False)
    views = db.Column(db.Integer, nullable=False, default=0)
    last_view_date = db.Column(db.Date, nullable=False, default=date.today)


class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    survey_id = db.Column(db.Integer, db.ForeignKey("survey.id"), nullable=False)


class NoteForm(FlaskForm):
    content = StringField("Notatka", validators=[DataRequired()])
    submit = SubmitField("Dodaj notatkę")


@login_manager.user_loader
def load_user(user_id):
    return User(user_id)


@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        if username in users and form.password.data == users[username]["password"]:
            login_user(User(username), remember=form.remember.data)
            return redirect(url_for("index"))
        else:
            flash("Nieprawidłowe dane logowania.")
    return render_template("login.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    surveys = Survey.query.all()
    page_view = PageView.query.filter_by(page_name="success").first()
    views = page_view.views if page_view is not None else 0
    return render_template("index.html", surveys=surveys, views=views)


@app.route("/create_survey", methods=["GET", "POST"])
@login_required
def create_survey():
    if current_user.role != "admin":
        return "Brak uprawnień"
    form = CreateSurveyForm()
    if form.validate_on_submit():
        survey = Survey(title=form.title.data)
        db.session.add(survey)
        db.session.commit()
        return redirect(url_for("add_question_to_survey", survey_id=survey.id))
    return render_template("create_survey.html", form=form)


@app.route("/add_question_to_survey/<int:survey_id>", methods=["GET", "POST"])
@login_required
def add_question_to_survey(survey_id):
    if current_user.role != "admin":
        return "Brak uprawnień"
    survey = Survey.query.get(survey_id)
    form = QuestionForm()
    if form.validate_on_submit():
        question = Question(content=form.content.data, survey_id=survey_id)
        db.session.add(question)
        db.session.commit()

        form.content.data = ""
    questions = Question.query.filter_by(survey_id=survey_id).all()
    return render_template(
        "add_question_to_survey.html", form=form, survey=survey, questions=questions
    )


@app.route("/survey/<int:survey_id>", methods=["GET", "POST"])
@login_required
def survey(survey_id):
    survey = Survey.query.get(survey_id)
    form = NoteForm()
    return render_template("survey.html", survey=survey, form=form)


@app.route("/survey/<int:survey_id>/fill", methods=["GET", "POST"])
@login_required
def fill_survey(survey_id):
    survey = Survey.query.get(survey_id)
    form = AnswerForm()

    if request.method == "GET":
        for question in survey.questions:
            form.answers.append_entry()

    if form.validate_on_submit():
        completed_survey = CompletedSurvey(
            user_id=current_user.id,
            name=form.name.data,
            timestamp=datetime.now(pytz.timezone("Europe/Warsaw")),
            survey_id=survey_id,
        )
        db.session.add(completed_survey)
        for question, answer_form in zip(survey.questions, form.answers.entries):
            response_tak = answer_form.response_tak.data
            response_nie = answer_form.response_nie.data

            answer = Answer(
                completed_survey_id=completed_survey.id,
                question_id=question.id,
                response_tak=response_tak,
                response_nie=response_nie,
                explanation=answer_form.explanation.data,
            )
            db.session.add(answer)
        db.session.commit()

        return redirect(url_for("success"))

    question_answer_forms = list(zip(survey.questions, form.answers.entries))

    return render_template(
        "fill_survey.html",
        survey=survey,
        question_answer_forms=question_answer_forms,
        form=form,
    )


@app.route("/completed_surveys/<int:survey_id>")
@login_required
def completed_surveys(survey_id):
    survey = Survey.query.get(survey_id)
    completed_surveys = CompletedSurvey.query.filter_by(survey_id=survey_id).all()
    return render_template(
        "completed_surveys.html", survey=survey, completed_surveys=completed_surveys
    )


@app.route("/completed_surveys/view/<int:completed_survey_id>")
@login_required
def view_completed_survey(completed_survey_id):
    completed_survey = CompletedSurvey.query.get(completed_survey_id)
    return render_template(
        "view_completed_survey.html", completed_survey=completed_survey
    )


@app.route("/delete_survey/<int:survey_id>", methods=["GET", "POST"])
@login_required
def delete_survey(survey_id):
    if current_user.role != "admin":
        return "Brak uprawnień"
    survey = Survey.query.get(survey_id)

    for question in survey.questions:
        for answer in question.answers:
            db.session.delete(answer)
        db.session.commit()
        db.session.delete(question)
    db.session.commit()

    db.session.delete(survey)
    db.session.commit()

    return redirect(url_for("index"))


@app.route("/delete_question/<int:question_id>", methods=["GET", "POST"])
@login_required
def delete_question(question_id):
    if current_user.role != "admin":
        return "Brak uprawnień"
    question = Question.query.get(question_id)
    db.session.delete(question)
    db.session.commit()

    return redirect(request.referrer)


@app.route("/edit_survey/<int:survey_id>", methods=["GET", "POST"])
@login_required
def edit_survey(survey_id):
    if current_user.role != "admin":
        return "Brak uprawnień"

    survey = Survey.query.get(survey_id)
    questions = survey.questions

    form = QuestionForm()

    if request.method == "POST":
        for question in questions:
            question.content = request.form.get(f"question_{question.id}")

        for key, value in request.form.items():
            if key.startswith("question_new_"):
                new_question = Question(content=value, survey_id=survey_id)
                db.session.add(new_question)

        for key in request.form.keys():
            if key.startswith("delete_"):
                question_id = int(key.split("_")[1])
                question = Question.query.get(question_id)
                Answer.query.filter_by(question_id=question_id).delete()
                db.session.delete(question)

        db.session.commit()

        return redirect(url_for("survey", survey_id=survey_id))

    return render_template(
        "edit_survey.html", survey=survey, questions=questions, form=form
    )


@app.route("/success")
@login_required
def success():
    local_tz = timezone("Europe/Warsaw")
    current_date = datetime.now(local_tz).date()
    page_view = PageView.query.filter_by(page_name="success").first()
    if page_view is None:
        page_view = PageView(page_name="success", views=1, last_view_date=current_date)
        db.session.add(page_view)
    else:
        last_view_date = page_view.last_view_date
        if last_view_date != current_date:
            page_view.views = 1
            page_view.last_view_date = current_date
        else:
            page_view.views += 1
    db.session.commit()
    return render_template("success.html")


@app.route("/survey/<int:survey_id>/add_note", methods=["GET", "POST"])
@login_required
def add_note_to_survey(survey_id):
    form = NoteForm()
    survey = Survey.query.get(survey_id)
    if form.validate_on_submit():
        note = Note(content=form.content.data, survey_id=survey_id)
        db.session.add(note)
        db.session.commit()

        return redirect(url_for("survey", survey_id=survey_id))
    return render_template("add_note_to_survey.html", form=form, survey=survey)


@app.route("/delete_note/<int:note_id>", methods=["POST", "DELETE"])
@csrf.exempt
@login_required
def delete_note(note_id):
    if current_user.role != "admin":
        return "Brak uprawnień"

    if request.method in ["POST", "DELETE"]:
        note = Note.query.get(note_id)
        if note:
            db.session.delete(note)
            db.session.commit()

    return redirect(request.referrer)


@app.route("/view_count")
@login_required
def view_count():
    page_view = PageView.query.filter_by(page_name="success").first()
    if page_view is not None:
        return jsonify(views=page_view.views)
    else:
        return jsonify(views=0)


@app.before_first_request
def create_tables():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
