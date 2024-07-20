from flask import Flask, request, render_template, redirect, url_for, flash, send_file, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import pandas as pd
import os
from datetime import datetime
import dash
from dash import dcc, html
import plotly.express as px
import plotly.graph_objects as go
from dash.dependencies import Output, Input
import dash_bootstrap_components as dbc
from xhtml2pdf import pisa
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///task_tracker.db'
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

EXCEL_FILE = 'task_data.xlsx'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user')

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(300), nullable=False)
    start_date = db.Column(db.String(10), nullable=False)
    end_date = db.Column(db.String(10))
    status = db.Column(db.String(50), nullable=False)
    challenges = db.Column(db.String(300))
    type = db.Column(db.String(50), nullable=False)
    site = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('tasks', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
@login_required
def index():
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    is_admin = current_user.role == 'admin'
    return render_template('index.html', tasks=tasks, is_admin=is_admin)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user:
            if user.password == password:
                login_user(user)
                flash('Login Successful', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid password', 'danger')
        else:
            flash('Username not found', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form.get('role', 'user')

        user_by_username = User.query.filter_by(username=username).first()
        user_by_email = User.query.filter_by(email=email).first()

        if user_by_username:
            flash('Username already exists', 'danger')
        elif user_by_email:
            flash('Email already registered', 'danger')
        else:
            new_user = User(username=username, email=email, password=password, role=role)
            db.session.add(new_user)
            db.session.commit()
            flash('Account created successfully', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/submit', methods=['POST'])
@login_required
def submit():
    type = request.form['type']
    site = request.form['site']
    title = request.form['title']
    description = request.form['description']
    start_date = request.form['start_date']
    end_date = request.form['end_date']
    status = request.form['status']
    challenges = request.form['challenges']

    new_task = Task(title=title, description=description, start_date=start_date, end_date=end_date, status=status, challenges=challenges, type=type, site=site, user_id=current_user.id)
    db.session.add(new_task)
    db.session.commit()

    if os.path.exists(EXCEL_FILE):
        df = pd.read_excel(EXCEL_FILE)
    else:
        df = pd.DataFrame(columns=['ID', 'User', 'Type', 'Site', 'Title', 'Description', 'Start Date', 'End Date', 'Status', 'Challenges', 'Timestamp'])

    new_row = pd.DataFrame([{
        'ID': new_task.id,
        'User': current_user.username,
        'Type': type,
        'Site': site,
        'Title': title,
        'Description': description,
        'Start Date': start_date,
        'End Date': end_date,
        'Status': status,
        'Challenges': challenges,
        'Timestamp': new_task.timestamp
    }])
    df = pd.concat([df, new_row], ignore_index=True)
    df.to_excel(EXCEL_FILE, index=False)

    return redirect(url_for('index'))

@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
@login_required
def edit(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        flash('You do not have permission to edit this task', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        task.type = request.form['type']
        task.site = request.form['site']
        task.title = request.form['title']
        task.description = request.form['description']
        task.start_date = request.form['start_date']
        task.end_date = request.form['end_date']
        task.status = request.form['status']
        task.challenges = request.form['challenges']
        db.session.commit()

        df = pd.read_excel(EXCEL_FILE)
        df.loc[df['ID'] == task.id, ['Type', 'Site', 'Title', 'Description', 'Start Date', 'End Date', 'Status', 'Challenges']] = [task.type, task.site, task.title, task.description, task.start_date, task.end_date, task.status, task.challenges]
        df.to_excel(EXCEL_FILE, index=False)

        return redirect(url_for('index'))

    return render_template('edit.html', task=task)

@app.route('/delete/<int:task_id>')
@login_required
def delete(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        flash('You do not have permission to delete this task', 'danger')
        return redirect(url_for('index'))

    db.session.delete(task)
    db.session.commit()

    df = pd.read_excel(EXCEL_FILE)
    df = df[df['ID'] != task.id]
    df.to_excel(EXCEL_FILE, index=False)

    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role != 'admin':
        flash('You do not have permission to view this page', 'danger')
        return redirect(url_for('index'))
    return redirect('/dash')

@app.route('/export_excel')
@login_required
def export_excel():
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action', 'danger')
        return redirect(url_for('index'))

    return send_file(EXCEL_FILE, as_attachment=True)

@app.route('/export_pdf')
@login_required
def export_pdf():
    if current_user.role != 'admin':
        flash('You do not have permission to perform this action', 'danger')
        return redirect(url_for('index'))

    rendered = render_template('charts_only.html')
    pdf = io.BytesIO()
    
    pisa_status = pisa.CreatePDF(
        io.StringIO(rendered),
        dest=pdf
    )

    if pisa_status.err:
        return "PDF generation error"

    response = make_response(pdf.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "inline; filename=exported_charts.pdf"
    
    return response

external_stylesheets = [dbc.themes.BOOTSTRAP]
dash_app = dash.Dash(__name__, server=app, url_base_pathname='/dash/', external_stylesheets=external_stylesheets)

dash_app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H1("Environmental and Sustainability Sector"), width=6),
        dbc.Col([
            html.A("Export as Excel", href="/export_excel", className="btn btn-primary mx-2"),
            html.A("Export Charts as PDF", href="/export_pdf", className="btn btn-secondary mx-2")
        ], className="text-right", width=6)
    ], className='custom-header'),
    dcc.Interval(id='interval-component', interval=60*1000, n_intervals=0),
    dbc.Row([
        dbc.Col(dbc.Card(
            dbc.CardBody([
                html.H4('Total Tasks and Projects', className='card-title'),
                dcc.Graph(id='total-tasks-projects')
            ])
        ), width=3, className='mb-4'),
        dbc.Col(dbc.Card(
            dbc.CardBody([
                html.H4('Current Tasks and Projects', className='card-title'),
                dcc.Graph(id='current-tasks-projects')
            ])
        ), width=3, className='mb-4'),
        dbc.Col(dbc.Card(
            dbc.CardBody([
                html.H4('Completed Tasks and Projects', className='card-title'),
                dcc.Graph(id='completed-tasks-projects')
            ])
        ), width=3, className='mb-4'),
        dbc.Col(dbc.Card(
            dbc.CardBody([
                html.H4('Overdue Tasks and Projects', className='card-title'),
                dcc.Graph(id='overdue-tasks-projects')
            ])
        ), width=3, className='mb-4'),
    ]),
    dbc.Row([
        dbc.Col(dbc.Card(
            dbc.CardBody([
                html.H4('Gantt Chart', className='card-title'),
                dcc.Graph(id='gantt-chart')
            ])
        ), width=12)
    ], className='mb-4'),
    dbc.Row([
        dbc.Col(dbc.Card(
            dbc.CardBody([
                html.H4('User Contribution (Pie)', className='card-title'),
                dcc.Graph(id='user-contribution-pie')
            ])
        ), width=6),
        dbc.Col(dbc.Card(
            dbc.CardBody([
                html.H4('User Contribution (Bar)', className='card-title'),
                dcc.Graph(id='user-contribution-bar')
            ])
        ), width=6),
    ], className='mb-4'),
    dbc.Row([
        dbc.Col(dbc.Card(
            dbc.CardBody([
                html.H4('Site Task Distribution (Heatmap)', className='card-title'),
                dcc.Graph(id='site-distribution-heatmap')
            ])
        ), width=6),
        dbc.Col(dbc.Card(
            dbc.CardBody([
                html.H4('Site Performance (Bar)', className='card-title'),
                dcc.Graph(id='site-performance-bar')
            ])
        ), width=6),
    ], className='mb-4'),
    dbc.Row([
        dbc.Col(dbc.Card(
            dbc.CardBody([
                html.H4('Challenges (Pie)', className='card-title'),
                dcc.Graph(id='challenges-pie')
            ])
        ), width=12),
    ])
], fluid=True)

@dash_app.callback(
    [Output('total-tasks-projects', 'figure'),
     Output('current-tasks-projects', 'figure'),
     Output('completed-tasks-projects', 'figure'),
     Output('overdue-tasks-projects', 'figure'),
     Output('gantt-chart', 'figure'),
     Output('user-contribution-pie', 'figure'),
     Output('user-contribution-bar', 'figure'),
     Output('site-distribution-heatmap', 'figure'),
     Output('site-performance-bar', 'figure'),
     Output('challenges-pie', 'figure')],
    [Input('interval-component', 'n_intervals')]
)
def update_dashboard(n):
    tasks = Task.query.all()

    task_data = [{
        'ID': task.id,
        'User': task.user.username,
        'Type': task.type,
        'Site': task.site,
        'Title': task.title,
        'Description': task.description,
        'Start Date': task.start_date,
        'End Date': task.end_date,
        'Status': task.status,
        'Challenges': task.challenges,
        'Timestamp': task.timestamp
    } for task in tasks]

    df = pd.DataFrame(task_data)

    total_tasks_projects = len(df)
    current_tasks_projects = len(df[df['Status'] == 'in progress'])
    completed_tasks_projects = len(df[df['Status'] == 'completed'])
    overdue_tasks_projects = len(df[df['Status'] == 'overdue'])

    fig_gantt = px.timeline(df, x_start="Start Date", x_end="End Date", y="Title", color="Status")
    user_contribution_pie = px.pie(df, names='User', title='User Contribution')
    user_contribution_bar = px.bar(df, x='User', y='ID', color='Status', title='User Task Completion')
    site_distribution_heatmap = px.density_heatmap(df, x='Site', y='Type', title='Site Task Distribution')
    site_performance_bar = px.bar(df, x='Site', y='ID', color='Status', title='Site Performance')
    challenges_pie = px.pie(df, names='Status', title='Task Status')

    fig_total = go.Figure(go.Indicator(
        mode="number",
        value=total_tasks_projects,
        title={"text": "Total Tasks and Projects"}
    ))

    fig_current = go.Figure(go.Indicator(
        mode="number",
        value=current_tasks_projects,
        title={"text": "Current Tasks and Projects"}
    ))

    fig_completed = go.Figure(go.Indicator(
        mode="number",
        value=completed_tasks_projects,
        title={"text": "Completed Tasks and Projects"}
    ))

    fig_overdue = go.Figure(go.Indicator(
        mode="number",
        value=overdue_tasks_projects,
        title={"text": "Overdue Tasks and Projects"}
    ))

    return fig_total, fig_current, fig_completed, fig_overdue, fig_gantt, user_contribution_pie, user_contribution_bar, site_distribution_heatmap, site_performance_bar, challenges_pie

dash_app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        <meta charset="UTF-8">
        <title>Dashboard</title>
        <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
        <style>
            @media print {
                .btn { display: none; }
            }
            .card {
                min-height: 75px; /* Adjust card height */
            }
            .card-title {
                font-size: 14px;
                font-weight: bold;
            }
            .card-body {
                padding: 10px;
            }
            .custom-header {
                background-color: #009688; /* Change to match logo color */
                color: white;
                padding: 10px 0;
                align-items: center;
            }
            h1, h3 {
                margin: 0;
            }
            h1 {
                font-size: 1.5rem; /* Adjust font size */
            }
            h3 {
                font-size: 1.25rem; /* Adjust font size */
            }
        </style>
        {%metas%}
        {%css%}
    </head>
    <body>
        <div class="container">
            {%app_entry%}
        </div>
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

if __name__ == "__main__":
    app.run(debug=True)
