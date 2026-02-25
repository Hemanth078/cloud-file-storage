from flask import Flask, request, redirect, url_for, render_template_string, send_file, session
import boto3
import io
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "mysecret123"

# S3
s3 = boto3.client('s3')
BUCKET = "my-cloud-project-1"   # ⚠️ Put your bucket name


# Database
def init_db():
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    conn.commit()
    conn.close()


init_db()


# Login Required
def login_required(func):
    def wrapper(*args, **kwargs):
        if 'user' not in session:
            return redirect('/login')
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper


# ================== UI TEMPLATES ==================

base_css = """
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
"""


login_html = base_css + """
<div class="container mt-5" style="max-width:400px">

<h3 class="text-center mb-4">☁️ Cloud Login</h3>

<form method="post">

<input class="form-control mb-3" name="username" placeholder="Username" required>

<input type="password" class="form-control mb-3" name="password" placeholder="Password" required>

<button class="btn btn-primary w-100">Login</button>

</form>

<p class="text-center mt-3">
<a href="/register">Create Account</a>
</p>

</div>
"""


register_html = base_css + """
<div class="container mt-5" style="max-width:400px">

<h3 class="text-center mb-4">📝 Register</h3>

<form method="post">

<input class="form-control mb-3" name="username" placeholder="Username" required>

<input type="password" class="form-control mb-3" name="password" placeholder="Password" required>

<button class="btn btn-success w-100">Register</button>

</form>

<p class="text-center mt-3">
<a href="/login">Back to Login</a>
</p>

</div>
"""


# ================== ROUTES ==================

@app.route('/login', methods=['GET','POST'])
def login():

    if request.method == 'POST':

        u = request.form['username']
        p = request.form['password']

        conn = sqlite3.connect("users.db")
        c = conn.cursor()

        c.execute("SELECT password FROM users WHERE username=?", (u,))
        user = c.fetchone()

        conn.close()

        if user and check_password_hash(user[0], p):

            session['user'] = u
            return redirect('/')

        return "Invalid login!"

    return render_template_string(login_html)


@app.route('/register', methods=['GET','POST'])
def register():

    if request.method == 'POST':

        u = request.form['username']
        p = request.form['password']

        hash_pass = generate_password_hash(p)

        try:

            conn = sqlite3.connect("users.db")
            c = conn.cursor()

            c.execute("INSERT INTO users VALUES (NULL,?,?)",(u,hash_pass))
            conn.commit()
            conn.close()

            return redirect('/login')

        except:
            return "Username already exists!"

    return render_template_string(register_html)


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/')
@login_required
def dashboard():

    files = []

    data = s3.list_objects_v2(Bucket=BUCKET)

    if 'Contents' in data:

        for obj in data['Contents']:
            files.append(obj['Key'])


    html = base_css + f"""

<div class="container mt-4">

<div class="d-flex justify-content-between align-items-center mb-3">

<h4>☁️ Cloud Dashboard</h4>

<div>
Welcome <b>{session['user']}</b>
<a href="/logout" class="btn btn-sm btn-danger ms-3">Logout</a>
</div>

</div>


<div class="card p-3 mb-4">

<form action="/upload" method="post" enctype="multipart/form-data">

<div class="input-group">

<input type="file" name="file" class="form-control" required>

<button class="btn btn-primary">Upload</button>

</div>

</form>

</div>


<table class="table table-bordered table-striped">

<tr>
<th>File Name</th>
<th>Actions</th>
</tr>
"""


    for f in files:

        html += f"""

<tr>
<td>{f}</td>

<td>
<a href="/download/{f}" class="btn btn-sm btn-success">Download</a>

<a href="/delete/{f}" class="btn btn-sm btn-danger"
onclick="return confirm('Delete file?')">Delete</a>
</td>
</tr>
"""


    html += "</table></div>"

    return html


@app.route('/upload', methods=['POST'])
@login_required
def upload():

    file = request.files['file']

    s3.upload_fileobj(file, BUCKET, file.filename)

    return redirect('/')


@app.route('/download/<filename>')
@login_required
def download(filename):

    obj = s3.get_object(Bucket=BUCKET, Key=filename)

    stream = io.BytesIO(obj['Body'].read())

    return send_file(stream, as_attachment=True, download_name=filename)


@app.route('/delete/<filename>')
@login_required
def delete(filename):

    s3.delete_object(Bucket=BUCKET, Key=filename)

    return redirect('/')


if __name__ == '__main__':

    app.run(host='0.0.0.0', port=80, debug=True)    
