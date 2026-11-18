import os
import sys
import sqlite3
import zipfile
import io
import platform
import base64
import uuid
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, send_from_directory, send_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "clinic_secret_key"

# --- UNIVERSAL PATH CONFIGURATION ---
if getattr(sys, 'frozen', False):
    # If it is running as a PyInstaller .exe, look directly at the USB folder!
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # If it is running normally in VS Code, look at the normal folder.
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'Clinic_Data')

os.makedirs(DATA_DIR, exist_ok=True)

UPLOAD_FOLDER = os.path.join(DATA_DIR, 'patient_lab_results')
DB_NAME = os.path.join(DATA_DIR, 'clinic_records.db')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS patients_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            last_name TEXT NOT NULL,
            first_name TEXT NOT NULL,
            middle_initial TEXT,
            suffix TEXT,
            address TEXT,
            sex TEXT,
            age INTEGER,
            status TEXT,
            lab_result_image TEXT
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            visit_date TEXT NOT NULL,
            history TEXT,
            physical_exam TEXT,
            prescription TEXT,
            visit_image TEXT,
            FOREIGN KEY(patient_id) REFERENCES patients_v2(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS visit_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visit_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            FOREIGN KEY(visit_id) REFERENCES visits(id)
        )
    ''')
    
    try:
        c.execute("SELECT visit_image FROM visits LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE visits ADD COLUMN visit_image TEXT")
        conn.commit()

    conn.commit()
    conn.close()

init_db()

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- HELPER: SAVE HTML5 CAMERA IMAGE ---
def save_b64_image(b64_str, prefix="cam"):
    if not b64_str: return None
    try:
        header, encoded = b64_str.split(",", 1)
        file_data = base64.b64decode(encoded)
        filename = f"{prefix}_{uuid.uuid4().hex[:8]}.jpg"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        with open(filepath, "wb") as f:
            f.write(file_data)
        return filename
    except Exception as e:
        print(f"Error saving base64 image: {e}")
        return None

# --- HTML TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dr. Atok's Clinic</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.5/font/bootstrap-icons.css">
    <style>
        :root {
            --primary-color: #98FB98;  
            --secondary-color: #3CB371; 
            --accent-color: #F0FFF0;   
            --bg-color: #F5FFFA;       
            --text-dark: #2F4F4F;      
            --card-bg: #ffffff;
        }
        body { background-color: var(--bg-color); font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; padding-bottom: 60px; color: var(--text-dark); }
        .navbar { background: linear-gradient(135deg, var(--secondary-color), var(--primary-color)) !important; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        .navbar-brand { font-weight: 700; letter-spacing: 0.5px; color: white !important; text-shadow: 1px 1px 2px rgba(0,0,0,0.2); }
        .btn-dashboard { height: 140px; border-radius: 20px; border: none; display: flex; flex-direction: column; justify-content: center; align-items: center; font-weight: 600; font-size: 1.1rem; transition: all 0.3s ease; box-shadow: 0 8px 15px rgba(0,0,0,0.05); background: white; color: var(--text-dark); }
        .btn-dashboard i { font-size: 3.5rem; margin-bottom: 15px; color: var(--secondary-color); transition: 0.3s; }
        .btn-dashboard:hover { transform: translateY(-5px); box-shadow: 0 12px 25px rgba(0,0,0,0.1); background-color: var(--accent-color); }
        .card { border: none; border-radius: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.03); background: var(--card-bg); overflow: hidden; }
        .card-header-custom { background-color: white; border-bottom: 2px solid var(--primary-color); padding: 15px 20px; }
        .profile-img-lg { width: 120px; height: 120px; object-fit: cover; border-radius: 50%; border: 4px solid var(--primary-color); }
        .profile-img-sm { width: 50px; height: 50px; object-fit: cover; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .form-control, .form-select { border-radius: 10px; padding: 10px 15px; border: 1px solid #c8e6c9; background-color: #fafafa; }
        .form-control:focus { border-color: var(--secondary-color); box-shadow: 0 0 0 3px rgba(152,251,152,0.4); background-color: white; }
        .patient-card { margin-bottom: 12px; border-left: 6px solid var(--secondary-color); transition: 0.2s; background-color: white; }
        .patient-card:hover { background-color: var(--accent-color); transform: translateX(3px); }
        .old-record-item { background-color: #fff; border: 1px solid var(--primary-color); border-radius: 12px; padding: 12px; margin-bottom: 12px; }
        .old-record-img-thumb { height: 100px; width: auto; border-radius: 8px; border: 1px solid #ddd; margin-top: 5px; display: block; cursor: zoom-in; }
        .timeline-date { color: var(--text-dark); font-weight: 700; font-size: 1.1rem; margin: 25px 0 10px 0; display: flex; align-items: center; }
        .timeline-date::after { content: ''; flex: 1; height: 2px; background: var(--primary-color); margin-left: 15px; }
        .visit-card { background: white; border-radius: 12px; border-left: 5px solid var(--secondary-color); padding: 20px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.03); }
        .visit-img-thumb { height: 100px; width: auto; border-radius: 8px; border: 1px solid #ddd; cursor: zoom-in; margin-right: 5px; margin-bottom: 5px; }
        .btn-primary { background-color: var(--secondary-color); border-color: var(--secondary-color); }
        .btn-primary:hover { background-color: #2E8B57; border-color: #2E8B57; }
        .text-primary { color: var(--secondary-color) !important; }
        .bg-light { background-color: #f8fdf9 !important; }
    </style>
</head>
<body>

<nav class="navbar navbar-expand-lg navbar-dark">
  <div class="container">
    <a class="navbar-brand" href="/"><i class="bi bi-heart-pulse-fill me-2"></i> Dr. Atok's Clinic</a>
    <div class="d-flex">
        <a href="/download_backup" class="btn btn-light btn-sm fw-bold text-success rounded-pill px-3 shadow-sm"><i class="bi bi-cloud-arrow-down-fill"></i> Backup Data</a>
    </div>
  </div>
</nav>

<div class="container mt-5 mb-5">

    {% if page == 'dashboard' %}
    <div class="row justify-content-center">
        <div class="col-12 text-center mb-5">
            <h1 class="display-5 fw-bold" style="color: #2E8B57;">Welcome, DR. ATOK</h1>
            <p class="lead text-secondary">What would you like to do today?</p>
        </div>
        
        <div class="col-md-4 mb-3">
            <a href="/add" class="btn-dashboard btn-add text-decoration-none">
                <i class="bi bi-person-plus-fill"></i>
                <span>Add New Patient</span>
            </a>
        </div>
        <div class="col-md-4 mb-3">
            <a href="/patients" class="btn-dashboard btn-view text-decoration-none">
                <i class="bi bi-people-fill"></i>
                <span>View All Patients</span>
            </a>
        </div>
        <div class="col-md-4 mb-3">
            <a href="/search" class="btn-dashboard btn-search text-decoration-none">
                <i class="bi bi-search"></i>
                <span>Search Records</span>
            </a>
        </div>
    </div>

    {% elif page == 'add' %}
    <div class="row justify-content-center">
        <div class="col-lg-9">
            <div class="card shadow-lg">
                <div class="card-header-custom d-flex justify-content-between align-items-center">
                    <h4 class="mb-0 fw-bold text-primary"><i class="bi bi-person-plus"></i> New Patient Registration</h4>
                    <a href="/" class="btn btn-outline-secondary rounded-pill px-4">Cancel</a>
                </div>
                <div class="card-body p-4">
                    <form action="/add" method="post" enctype="multipart/form-data">
                        
                        <div class="row">
                            <div class="col-md-4 text-center mb-4">
                                <div class="p-4 bg-light rounded-3 border border-dashed border-success">
                                    <i class="bi bi-camera display-4 text-muted mb-2"></i>
                                    <p class="small fw-bold mb-2">Patient Photo</p>
                                    
                                    <input type="file" name="profile_pic" class="form-control form-control-sm mb-2" accept="image/*">
                                    
                                    <div class="text-muted small mb-2 fw-bold">OR</div>
                                    
                                    <button type="button" class="btn btn-outline-success btn-sm w-100" onclick="openSingleCamera('profile_cam', 'prof_preview')">
                                        <i class="bi bi-camera"></i> Use Tablet Camera
                                    </button>
                                    
                                    <input type="hidden" name="profile_cam" id="profile_cam">
                                    <img id="prof_preview" class="mt-3" style="display:none; width: 100%; border-radius: 8px; border: 2px solid var(--primary-color);">
                                </div>
                            </div>
                            
                            <div class="col-md-8">
                                <h6 class="text-uppercase text-muted fw-bold mb-3">Personal Information</h6>
                                <div class="row g-2 mb-3">
                                    <div class="col-md-5"><div class="form-floating"><input type="text" name="last_name" class="form-control" id="ln" required placeholder="Last"><label for="ln">Last Name *</label></div></div>
                                    <div class="col-md-5"><div class="form-floating"><input type="text" name="first_name" class="form-control" id="fn" required placeholder="First"><label for="fn">First Name *</label></div></div>
                                    <div class="col-md-2"><div class="form-floating"><input type="text" name="middle_initial" class="form-control" id="mi" maxlength="2" placeholder="M.I."><label for="mi">M.I.</label></div></div>
                                </div>
                                <div class="row g-2 mb-3">
                                    <div class="col-md-4"><div class="form-floating"><input type="number" name="age" class="form-control" id="age" required placeholder="Age"><label for="age">Age *</label></div></div>
                                    <div class="col-md-4"><div class="form-floating"><select name="sex" class="form-select" id="sex"><option>Male</option><option>Female</option></select><label for="sex">Sex</label></div></div>
                                    <div class="col-md-4"><div class="form-floating"><input type="text" name="suffix" class="form-control" id="suf" placeholder="Jr"><label for="suf">Suffix</label></div></div>
                                </div>
                                <div class="form-floating mb-3">
                                    <input type="text" name="address" class="form-control" id="addr" placeholder="Address">
                                    <label for="addr">Home Address</label>
                                </div>
                            </div>
                        </div>

                        <hr class="my-4">
                        
                        <div class="bg-light p-3 rounded-3 border">
                            <h6 class="text-primary fw-bold mb-3"><i class="bi bi-folder-plus"></i> Initial Medical Entry / Old Record</h6>
                            
                            <div class="row mb-3">
                                <div class="col-md-6">
                                    <label class="form-label small fw-bold text-muted">What are you uploading?</label>
                                    <select name="visit_type" class="form-select">
                                        <option value="new_visit">Current Lab Result / New Visit</option>
                                        <option value="old_record">Old Patient Record (Goes to Old Records)</option>
                                    </select>
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label small fw-bold text-muted">Record Date</label>
                                    <input type="date" name="visit_date" class="form-control" value="{{ today_date }}">
                                </div>
                            </div>

                            <div class="mb-3 p-3 bg-white rounded border border-success">
                                <label class="form-label small fw-bold text-success"><i class="bi bi-images"></i> Attach Lab Results or Photos</label>
                                
                                <input type="file" name="visit_pics" class="form-control mb-2" accept="image/*" multiple>
                                
                                <button type="button" class="btn btn-outline-success btn-sm" onclick="openMultiCamera('add_cam_container', 'add_cam_previews')">
                                    <i class="bi bi-camera"></i> Take Photos with Tablet
                                </button>
                                
                                <div id="add_cam_container"></div>
                                <div id="add_cam_previews" class="mt-2 d-flex flex-wrap"></div>
                            </div>

                            <div class="form-floating mb-2"><textarea name="history" class="form-control" placeholder="History" id="hist" style="height: 100px"></textarea><label for="hist">History / Chief Complaint</label></div>
                            <div class="form-floating mb-2"><textarea name="physical_exam" class="form-control" placeholder="PE" id="pe" style="height: 100px"></textarea><label for="pe">Physical Examination</label></div>
                            <div class="form-floating mb-2"><textarea name="prescription" class="form-control" placeholder="Rx" id="rx" style="height: 100px"></textarea><label for="rx">Prescribed Medicine</label></div>
                        </div>

                        <div class="mt-4">
                            <div class="d-grid gap-2">
                                <button type="submit" class="btn btn-primary btn-lg rounded-pill shadow-sm">Save Patient Record</button>
                            </div>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>

    {% elif page == 'list' or page == 'search' %}
    <div class="row justify-content-center">
        <div class="col-lg-10">
            <div class="d-flex justify-content-between align-items-center mb-4">
                <h3 class="fw-bold text-dark mb-0">{% if page == 'search' %}Search Results{% else %}All Patients{% endif %}</h3>
                {% if page == 'list' %}
                <span class="badge bg-secondary rounded-pill">Total Patients: {{ total_patients }}</span>
                {% endif %}
                <a href="/" class="btn btn-outline-dark rounded-pill px-4"><i class="bi bi-house-door-fill"></i> Home</a>
            </div>

            {% if page == 'search' %}
            <div class="card p-4 mb-4 bg-light border-0">
                <form action="/search" method="get" class="d-flex gap-2">
                    <input type="text" name="q" class="form-control form-control-lg border-0 shadow-sm" placeholder="Type a name to search..." value="{{ query }}">
                    <button type="submit" class="btn btn-primary btn-lg px-4 rounded-3 shadow-sm"><i class="bi bi-search"></i></button>
                </form>
            </div>
            {% endif %}

            <div class="row">
                {% if patients %}
                    {% for p in patients %}
                    <div class="col-12">
                        <div class="card patient-card p-3 shadow-sm" onclick="window.location.href='/patient/{{ p[0] }}'" style="cursor: pointer;">
                            <div class="d-flex align-items-center">
                                <div class="flex-shrink-0">
                                    {% if p[9] %}
                                        <img src="{{ url_for('uploaded_file', filename=p[9]) }}" class="profile-img-sm">
                                    {% else %}
                                        <div class="profile-img-sm bg-secondary text-white d-flex align-items-center justify-content-center"><i class="bi bi-person-fill"></i></div>
                                    {% endif %}
                                </div>
                                <div class="flex-grow-1 ms-3">
                                    <h5 class="fw-bold text-dark mb-0">{{ p[1] }}, {{ p[2] }} {{ p[3] }}</h5>
                                    <small class="text-muted">{{ p[6] }} | {{ p[7] }} yrs old</small>
                                    <div class="text-truncate text-muted small" style="max-width: 300px;"><i class="bi bi-geo-alt"></i> {{ p[5] }}</div>
                                </div>
                                <div class="ms-auto"><i class="bi bi-chevron-right text-muted"></i></div>
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="col-12 text-center py-5">
                        <i class="bi bi-inbox display-1 text-muted opacity-25"></i>
                        <h4 class="text-muted mt-3">No patients found.</h4>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>

    {% elif page == 'detail' %}
    <div class="row">
        <div class="col-12 mb-4 d-flex justify-content-between align-items-center">
            <h3 class="fw-bold text-dark"><i class="bi bi-person-lines-fill text-primary"></i> Patient Record</h3>
            <a href="/patients" class="btn btn-outline-dark rounded-pill px-4"><i class="bi bi-arrow-left"></i> Back</a>
        </div>

        <div class="col-lg-4 mb-4">
            
            <div class="card shadow-sm mb-4 text-center p-4">
                <div class="position-absolute top-0 end-0 p-3">
                    <button class="btn btn-sm btn-light rounded-circle" type="button" data-bs-toggle="collapse" data-bs-target="#editProfileForm"><i class="bi bi-pencil"></i></button>
                    <button class="btn btn-sm btn-danger rounded-circle ms-1" type="button" data-bs-toggle="modal" data-bs-target="#deleteModal"><i class="bi bi-trash"></i></button>
                </div>
                
                <div class="d-flex justify-content-center mb-3">
                    {% if patient[9] %}
                        <img src="{{ url_for('uploaded_file', filename=patient[9]) }}" class="profile-img-lg">
                    {% else %}
                        <div class="profile-img-lg bg-light d-flex align-items-center justify-content-center text-muted"><i class="bi bi-person display-4"></i></div>
                    {% endif %}
                </div>
                
                <h3 class="fw-bold mb-1">{{ patient[1] }}, {{ patient[2] }}</h3>
                <span class="badge bg-secondary rounded-pill mb-3" style="background-color: var(--secondary-color) !important;">{{ patient[6] }} | {{ patient[7] }} yrs old</span>
                <p class="text-muted small"><i class="bi bi-geo-alt-fill text-danger"></i> {{ patient[5] }}</p>

                <div class="collapse mt-3 text-start" id="editProfileForm">
                    <hr>
                    <form action="/patient/{{ patient[0] }}/update" method="post">
                        <div class="mb-2"><label class="small fw-bold">Last Name</label><input type="text" name="last_name" class="form-control form-control-sm" value="{{ patient[1] }}"></div>
                        <div class="mb-2"><label class="small fw-bold">First Name</label><input type="text" name="first_name" class="form-control form-control-sm" value="{{ patient[2] }}"></div>
                        <div class="mb-2"><label class="small fw-bold">Age</label><input type="number" name="age" class="form-control form-control-sm" value="{{ patient[7] }}"></div>
                        <div class="mb-3"><label class="small fw-bold">Address</label><input type="text" name="address" class="form-control form-control-sm" value="{{ patient[5] }}"></div>
                        <button type="submit" class="btn btn-primary btn-sm w-100 rounded-pill">Save Changes</button>
                    </form>
                </div>
            </div>

            <div class="card shadow-sm border-0 mb-4" style="background: linear-gradient(to bottom right, #f1f8e9, #c8e6c9);">
                <div class="card-body">
                    <h6 class="fw-bold text-dark mb-3"><i class="bi bi-cloud-upload-fill text-success"></i> Upload Old Record</h6>
                    <form action="/patient/{{ patient[0] }}/add_visit" method="post" enctype="multipart/form-data">
                        <input type="hidden" name="type" value="old_record">
                        <div class="mb-2">
                            <label class="small text-muted fw-bold">Date of Record</label>
                            <input type="date" name="visit_date" class="form-control form-control-sm bg-white border-0" value="{{ today_date }}" required>
                        </div>
                        <div class="mb-3">
                            <input type="file" name="visit_pics" class="form-control form-control-sm bg-white border-0 mb-2" accept="image/*" multiple>
                            <button type="button" class="btn btn-outline-success btn-sm w-100 bg-white" onclick="openMultiCamera('old_cam_container', 'old_cam_previews')"><i class="bi bi-camera"></i> Take Photos with Tablet</button>
                            <div id="old_cam_container"></div>
                            <div id="old_cam_previews" class="mt-2 d-flex flex-wrap"></div>
                        </div>
                        <button type="submit" class="btn btn-success btn-sm w-100 rounded-pill fw-bold shadow-sm" style="background-color: #2E8B57; border-color: #2E8B57;">Save Record</button>
                    </form>
                </div>
            </div>

            <div class="card shadow-sm">
                <div class="card-header bg-white fw-bold text-dark border-bottom">
                    <i class="bi bi-folder-fill text-warning me-2"></i> OLD PATIENT RECORDS
                </div>
                <div class="card-body p-2" style="max-height: 400px; overflow-y: auto; background-color: #fafafa;">
                    {% if old_records %}
                        {% for rec in old_records %}
                        <div class="old-record-item shadow-sm position-relative">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <span class="badge bg-light text-dark border">{{ rec['date'] }}</span>
                                <button class="btn btn-sm btn-outline-danger border-0" onclick="if(confirm('Delete this record?')) window.location.href='/visit/'+{{ rec['id'] }}+'/delete'"><i class="bi bi-trash"></i></button>
                            </div>
                            
                            {% if rec['legacy_image'] %}
                            <a href="{{ url_for('uploaded_file', filename=rec['legacy_image']) }}" target="_blank">
                                <img src="{{ url_for('uploaded_file', filename=rec['legacy_image']) }}" class="old-record-img-thumb mb-2">
                            </a>
                            {% endif %}

                            {% if photos_by_visit[rec['id']] %}
                                <div class="d-flex flex-wrap gap-2">
                                {% for photo in photos_by_visit[rec['id']] %}
                                    <a href="{{ url_for('uploaded_file', filename=photo) }}" target="_blank">
                                        <img src="{{ url_for('uploaded_file', filename=photo) }}" class="old-record-img-thumb">
                                    </a>
                                {% endfor %}
                                </div>
                            {% endif %}
                        </div>
                        {% endfor %}
                    {% else %}
                        <div class="text-center py-4 text-muted small"><i class="bi bi-folder-x display-6"></i><br>No old records.</div>
                    {% endif %}
                </div>
            </div>
        </div>

        <div class="col-lg-8">
            <div class="card shadow-sm h-100">
                <div class="card-header bg-white border-bottom p-0">
                    <ul class="nav nav-pills p-3" id="myTab" role="tablist">
                        <li class="nav-item me-2"><button class="nav-link active rounded-pill fw-bold" id="history-tab" data-bs-toggle="tab" data-bs-target="#history" type="button"><i class="bi bi-clock-history"></i> Medical History</button></li>
                        <li class="nav-item"><button class="nav-link rounded-pill fw-bold text-dark bg-light" id="add-tab" data-bs-toggle="tab" data-bs-target="#add" type="button"><i class="bi bi-plus-lg"></i> New Consultation</button></li>
                    </ul>
                </div>
                
                <div class="card-body bg-light">
                    <div class="tab-content" id="myTabContent">
                        
                        <div class="tab-pane fade show active" id="history">
                            {% if visits %}
                                {% for v in visits %}
                                    <div class="timeline-date">
                                        <span class="me-2">{{ v['date'] }}</span>
                                        <div>
                                            <button class="btn btn-sm btn-outline-secondary border-0" data-bs-toggle="modal" data-bs-target="#editVisitModal{{ v['id'] }}"><i class="bi bi-pencil-square"></i></button>
                                            <button class="btn btn-sm btn-outline-danger border-0" onclick="if(confirm('Delete this medical history entry?')) window.location.href='/visit/'+{{ v['id'] }}+'/delete'"><i class="bi bi-trash"></i></button>
                                        </div>
                                    </div>
                                    <div class="visit-card">
                                        {% if v['legacy_image'] or photos_by_visit[v['id']] %}
                                            <div class="mb-3 p-2 bg-light rounded border">
                                                <span class="badge bg-success mb-2">Lab Results / Photos</span>
                                                <div class="d-flex flex-wrap gap-2">
                                                    {% if v['legacy_image'] %}
                                                        <a href="{{ url_for('uploaded_file', filename=v['legacy_image']) }}" target="_blank">
                                                            <img src="{{ url_for('uploaded_file', filename=v['legacy_image']) }}" class="visit-img-thumb shadow-sm">
                                                        </a>
                                                    {% endif %}
                                                    {% if photos_by_visit[v['id']] %}
                                                        {% for photo in photos_by_visit[v['id']] %}
                                                            <a href="{{ url_for('uploaded_file', filename=photo) }}" target="_blank">
                                                                <img src="{{ url_for('uploaded_file', filename=photo) }}" class="visit-img-thumb shadow-sm">
                                                            </a>
                                                        {% endfor %}
                                                    {% endif %}
                                                </div>
                                            </div>
                                        {% endif %}
                                        
                                        {% if v['history'] %}<div class="mb-3"><h6 class="fw-bold text-dark mb-1">History / CC:</h6><p class="mb-0 text-secondary">{{ v['history'] }}</p></div>{% endif %}
                                        {% if v['pe'] %}<div class="mb-3"><h6 class="fw-bold text-dark mb-1">Physical Exam:</h6><p class="mb-0 text-secondary">{{ v['pe'] }}</p></div>{% endif %}
                                        
                                        {% if v['rx'] %}
                                        <div class="mt-3 p-3 bg-danger-subtle rounded border border-danger-subtle" style="background-color: #ffebee !important; border-color: #ffcdd2 !important;">
                                            <h6 class="fw-bold text-danger mb-1"><i class="bi bi-prescription2"></i> Prescription:</h6>
                                            <p class="mb-0 text-dark fw-bold" style="white-space: pre-line;">{{ v['rx'] }}</p>
                                        </div>
                                        {% endif %}
                                    </div>

                                    <div class="modal fade" id="editVisitModal{{ v['id'] }}" tabindex="-1">
                                        <div class="modal-dialog">
                                            <div class="modal-content">
                                                <div class="modal-header"><h5 class="modal-title">Edit Consultation</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
                                                <div class="modal-body">
                                                    <form action="/visit/{{ v['id'] }}/update" method="post">
                                                        <input type="hidden" name="patient_id" value="{{ patient[0] }}">
                                                        <div class="mb-2"><label class="small fw-bold">History / CC</label><textarea name="history" class="form-control" rows="3">{{ v['history'] }}</textarea></div>
                                                        <div class="mb-2"><label class="small fw-bold">Physical Exam</label><textarea name="physical_exam" class="form-control" rows="3">{{ v['pe'] }}</textarea></div>
                                                        <div class="mb-2"><label class="small fw-bold">Prescription</label><textarea name="prescription" class="form-control" rows="3">{{ v['rx'] }}</textarea></div>
                                                        <button type="submit" class="btn btn-primary w-100">Save Changes</button>
                                                    </form>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                {% endfor %}
                            {% else %}
                                <div class="text-center py-5"><i class="bi bi-journal-medical display-4 text-muted opacity-25"></i><p class="mt-3 text-muted">No consultation history found.</p></div>
                            {% endif %}
                        </div>

                        <div class="tab-pane fade" id="add">
                            <div class="bg-white p-4 rounded-3 shadow-sm border">
                                <form action="/patient/{{ patient[0] }}/add_visit" method="post" enctype="multipart/form-data">
                                    <input type="hidden" name="type" value="new_visit">
                                    
                                    <div class="d-flex justify-content-between align-items-center mb-4">
                                        <h5 class="fw-bold text-primary mb-0">New Consultation</h5>
                                        <input type="date" name="visit_date" class="form-control form-control-sm w-auto fw-bold" value="{{ today_date }}" required>
                                    </div>

                                    <div class="mb-3"><label class="form-label fw-bold small text-muted">HISTORY / CHIEF COMPLAINT</label><textarea name="history" class="form-control bg-light" rows="3"></textarea></div>
                                    <div class="mb-3"><label class="form-label fw-bold small text-muted">PHYSICAL EXAMINATION</label><textarea name="physical_exam" class="form-control bg-light" rows="3"></textarea></div>
                                    <div class="mb-4"><label class="form-label fw-bold small text-danger">PRESCRIPTION / PLAN</label><textarea name="prescription" class="form-control border-danger-subtle" rows="3"></textarea></div>
                                    
                                    <div class="mb-4 p-3 border rounded border-success">
                                        <label class="form-label fw-bold small text-success"><i class="bi bi-images"></i> ATTACH PHOTOS / LABS</label>
                                        <input type="file" name="visit_pics" class="form-control mb-2" accept="image/*" multiple>
                                        <button type="button" class="btn btn-outline-success btn-sm" onclick="openMultiCamera('new_cam_container', 'new_cam_previews')"><i class="bi bi-camera"></i> Take Photos with Tablet</button>
                                        <div id="new_cam_container"></div>
                                        <div id="new_cam_previews" class="mt-2 d-flex flex-wrap"></div>
                                    </div>

                                    <button type="submit" class="btn btn-primary w-100 py-2 rounded-pill fw-bold shadow-sm">Save Consultation Record</button>
                                </form>
                            </div>
                        </div>

                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="deleteModal" tabindex="-1">
      <div class="modal-dialog">
        <div class="modal-content">
          <div class="modal-header"><h5 class="modal-title text-danger fw-bold">Confirm Deletion</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
          <div class="modal-body">Are you sure you want to delete the record for <strong>{{ patient[1] }}</strong>?</div>
          <div class="modal-footer"><button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancel</button><a href="/patient/{{ patient[0] }}/delete" class="btn btn-danger">Delete Record</a></div>
        </div>
      </div>
    </div>
    {% endif %}

</div>

<div class="modal fade" id="cameraModal" tabindex="-1" data-bs-backdrop="static">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title"><i class="bi bi-camera text-success"></i> Tablet Camera</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal" onclick="stopCamera()"></button>
      </div>
      <div class="modal-body text-center bg-dark">
        <video id="webcam-video" autoplay playsinline style="width: 100%; max-height: 60vh; border-radius: 8px; border: 2px solid #555;"></video>
        <canvas id="webcam-canvas" style="display: none;"></canvas>
        <img id="webcam-preview" style="display: none; width: 100%; border-radius: 8px; border: 2px solid #2E8B57;" />
      </div>
      <div class="modal-footer justify-content-between">
        <button type="button" class="btn btn-secondary" onclick="retakePhoto()" id="btn-retake" style="display: none;">Retake</button>
        <button type="button" class="btn btn-primary w-100 py-2 fw-bold" onclick="takePhoto()" id="btn-capture"><i class="bi bi-circle-fill text-danger"></i> CAPTURE</button>
        <button type="button" class="btn btn-success w-100 py-2 fw-bold" onclick="savePhoto()" id="btn-save" style="display: none;" data-bs-dismiss="modal">Use This Photo</button>
      </div>
    </div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
    let cameraMode = null; 
    let singleTargetInput = null;
    let singleTargetPreview = null;
    let multiTargetContainer = null;
    let multiTargetPreview = null;
    let stream = null;

    function showCameraModal() {
        document.getElementById('webcam-video').style.display = 'block';
        document.getElementById('webcam-preview').style.display = 'none';
        document.getElementById('btn-capture').style.display = 'block';
        document.getElementById('btn-retake').style.display = 'none';
        document.getElementById('btn-save').style.display = 'none';

        var myModal = new bootstrap.Modal(document.getElementById('cameraModal'));
        myModal.show();

        navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
            .then(s => {
                stream = s;
                document.getElementById('webcam-video').srcObject = stream;
            })
            .catch(err => {
                alert("Camera error! Make sure you are using 127.0.0.1:5000 in Chrome, and Chrome has Camera permissions.");
            });
    }

    function openSingleCamera(inputId, previewId) {
        cameraMode = 'single';
        singleTargetInput = inputId;
        singleTargetPreview = previewId;
        showCameraModal();
    }

    function openMultiCamera(containerId, previewContainerId) {
        cameraMode = 'multiple';
        multiTargetContainer = containerId;
        multiTargetPreview = previewContainerId;
        showCameraModal();
    }

    function stopCamera() {
        if(stream) { stream.getTracks().forEach(track => track.stop()); stream = null; }
    }

    function takePhoto() {
        const video = document.getElementById('webcam-video');
        const canvas = document.getElementById('webcam-canvas');
        const context = canvas.getContext('2d');
        
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
        document.getElementById('webcam-preview').src = dataUrl;
        
        video.style.display = 'none';
        document.getElementById('webcam-preview').style.display = 'block';
        
        document.getElementById('btn-capture').style.display = 'none';
        document.getElementById('btn-retake').style.display = 'block';
        document.getElementById('btn-save').style.display = 'block';
    }

    function retakePhoto() {
        document.getElementById('webcam-video').style.display = 'block';
        document.getElementById('webcam-preview').style.display = 'none';
        document.getElementById('btn-capture').style.display = 'block';
        document.getElementById('btn-retake').style.display = 'none';
        document.getElementById('btn-save').style.display = 'none';
    }

    function savePhoto() {
        const dataUrl = document.getElementById('webcam-preview').src;
        
        if (cameraMode === 'multiple') {
            const container = document.getElementById(multiTargetContainer);
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'visit_cam_b64';
            input.value = dataUrl;
            container.appendChild(input);
            
            const img = document.createElement('img');
            img.src = dataUrl;
            img.style.height = '80px';
            img.style.margin = '5px';
            img.style.borderRadius = '5px';
            img.style.border = '2px solid #3CB371';
            document.getElementById(multiTargetPreview).appendChild(img);

        } else if (cameraMode === 'single') {
            document.getElementById(singleTargetInput).value = dataUrl;
            const preview = document.getElementById(singleTargetPreview);
            preview.src = dataUrl;
            preview.style.display = 'block';
        }
        stopCamera();
    }
</script>
</body>
</html>
"""

# --- ROUTES ---

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE, page='dashboard')

@app.route('/patients')
def list_patients():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM patients_v2 ORDER BY last_name ASC, first_name ASC")
    patients = c.fetchall()
    conn.close()
    return render_template_string(HTML_TEMPLATE, page='list', patients=patients, total_patients=len(patients))

@app.route('/add', methods=['GET', 'POST'])
def add_patient():
    if request.method == 'POST':
        profile_filename = None
        
        # 1. Check Standard Upload
        file_prof = request.files.get('profile_pic')
        if file_prof and allowed_file(file_prof.filename):
            filename = secure_filename(file_prof.filename)
            profile_filename = f"prof_{uuid.uuid4().hex[:8]}_{filename}"
            file_prof.save(os.path.join(app.config['UPLOAD_FOLDER'], profile_filename))
            
        # 2. Check HTML5 Camera
        profile_cam = request.form.get('profile_cam')
        if profile_cam:
            profile_filename = save_b64_image(profile_cam, "prof")

        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        c.execute("""
            INSERT INTO patients_v2 (last_name, first_name, middle_initial, suffix, address, sex, age, status, lab_result_image) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (request.form['last_name'], request.form['first_name'], request.form.get('middle_initial',''), request.form.get('suffix',''), 
              request.form['address'], request.form['sex'], request.form['age'], "", profile_filename))
        
        new_patient_id = c.lastrowid
        
        visit_date = request.form.get('visit_date')
        history = request.form.get('history', '')
        physical_exam = request.form.get('physical_exam', '')
        prescription = request.form.get('prescription', '')
        visit_type = request.form.get('visit_type', 'new_visit')
        
        if visit_type == 'old_record':
            history = "TYPE_OLD_RECORD"
        
        files = request.files.getlist('visit_pics')
        single_file = request.files.get('visit_pic')
        all_files = [f for f in files if f.filename]
        if single_file and single_file.filename:
            all_files.append(single_file)

        cam_pics = request.form.getlist('visit_cam_b64')

        if (visit_type == 'old_record' and (all_files or cam_pics)) or (visit_type == 'new_visit' and (history or physical_exam or prescription or all_files or cam_pics)):
            if not visit_date: visit_date = datetime.now().strftime('%Y-%m-%d')
            
            c.execute("""
                INSERT INTO visits (patient_id, visit_date, history, physical_exam, prescription, visit_image)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (new_patient_id, visit_date, history, physical_exam, prescription, ""))
            new_visit_id = c.lastrowid

            for file in all_files:
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    visit_filename = f"visit_{uuid.uuid4().hex[:8]}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], visit_filename))
                    c.execute("INSERT INTO visit_photos (visit_id, file_path) VALUES (?, ?)", (new_visit_id, visit_filename))
                    
            for b64 in cam_pics:
                visit_filename = save_b64_image(b64, "visit")
                if visit_filename:
                    c.execute("INSERT INTO visit_photos (visit_id, file_path) VALUES (?, ?)", (new_visit_id, visit_filename))

        conn.commit()
        conn.close()
        return redirect(url_for('list_patients'))
    
    today_date = datetime.now().strftime('%Y-%m-%d')
    return render_template_string(HTML_TEMPLATE, page='add', today_date=today_date)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    patients = []
    if query:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        search_term = f"%{query}%"
        c.execute("SELECT * FROM patients_v2 WHERE last_name LIKE ? OR first_name LIKE ? ORDER BY last_name ASC", (search_term, search_term))
        patients = c.fetchall()
        conn.close()
    return render_template_string(HTML_TEMPLATE, page='search', patients=patients, query=query)

@app.route('/patient/<int:id>')
def patient_detail(id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM patients_v2 WHERE id = ?", (id,))
    patient = c.fetchone()
    if not patient: return "Patient not found", 404
        
    c.execute("SELECT * FROM visits WHERE patient_id = ? ORDER BY visit_date DESC", (id,))
    all_visits = c.fetchall()
    
    history_visits = []
    old_records = []
    
    if all_visits:
        visit_ids = [str(v[0]) for v in all_visits]
        query = f"SELECT visit_id, file_path FROM visit_photos WHERE visit_id IN ({','.join(visit_ids)})"
        c.execute(query)
        photos = c.fetchall()
    else:
        photos = []

    photos_by_visit = {}
    for p in photos:
        vid, path = p[0], p[1]
        if vid not in photos_by_visit: photos_by_visit[vid] = []
        photos_by_visit[vid].append(path)

    for v in all_visits:
        v_dict = {
            'id': v[0],
            'date': v[2],
            'history': v[3],
            'pe': v[4],
            'rx': v[5],
            'legacy_image': v[6]
        }
        
        try:
            date_obj = datetime.strptime(v_dict['date'], '%Y-%m-%d')
            v_dict['date'] = date_obj.strftime("%B %d, %Y")
        except ValueError: pass 
        
        if v_dict['history'] == "TYPE_OLD_RECORD":
            old_records.append(v_dict)
        else:
            history_visits.append(v_dict)

    conn.close()
    today_date = datetime.now().strftime('%Y-%m-%d')
    return render_template_string(HTML_TEMPLATE, page='detail', patient=patient, visits=history_visits, old_records=old_records, photos_by_visit=photos_by_visit, today_date=today_date)

@app.route('/patient/<int:id>/update', methods=['POST'])
def update_patient(id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE patients_v2 SET last_name=?, first_name=?, address=?, age=? WHERE id=?", 
              (request.form['last_name'], request.form['first_name'], request.form['address'], request.form['age'], id))
    conn.commit()
    conn.close()
    return redirect(url_for('patient_detail', id=id))

@app.route('/visit/<int:visit_id>/update', methods=['POST'])
def update_visit(visit_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        UPDATE visits 
        SET history=?, physical_exam=?, prescription=? 
        WHERE id=?
    """, (request.form['history'], request.form['physical_exam'], request.form['prescription'], visit_id))
    conn.commit()
    conn.close()
    return redirect(url_for('patient_detail', id=request.form['patient_id']))

@app.route('/visit/<int:visit_id>/delete')
def delete_visit(visit_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT patient_id FROM visits WHERE id=?", (visit_id,))
    res = c.fetchone()
    if res:
        pid = res[0]
        c.execute("DELETE FROM visit_photos WHERE visit_id=?", (visit_id,))
        c.execute("DELETE FROM visits WHERE id=?", (visit_id,))
        conn.commit()
        conn.close()
        return redirect(url_for('patient_detail', id=pid))
    conn.close()
    return "Error: Visit not found"

@app.route('/patient/<int:id>/add_visit', methods=['POST'])
def add_visit(id):
    form_type = request.form.get('type', 'new_visit')
    
    if form_type == 'old_record':
        history_val = "TYPE_OLD_RECORD"
        pe_val = ""
        rx_val = ""
    else:
        history_val = request.form.get('history', '')
        pe_val = request.form.get('physical_exam', '')
        rx_val = request.form.get('prescription', '')

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("""
        INSERT INTO visits (patient_id, visit_date, history, physical_exam, prescription, visit_image)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (id, request.form['visit_date'], history_val, pe_val, rx_val, ""))
    new_visit_id = c.lastrowid

    files = request.files.getlist('visit_pics')
    single_file = request.files.get('visit_pic')
    if single_file and single_file.filename:
        files.append(single_file)

    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            import uuid
            visit_filename = f"visit_{uuid.uuid4().hex[:8]}_{filename}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], visit_filename))
            c.execute("INSERT INTO visit_photos (visit_id, file_path) VALUES (?, ?)", (new_visit_id, visit_filename))

    cam_pics = request.form.getlist('visit_cam_b64')
    for b64 in cam_pics:
        visit_filename = save_b64_image(b64, "visit")
        if visit_filename:
            c.execute("INSERT INTO visit_photos (visit_id, file_path) VALUES (?, ?)", (new_visit_id, visit_filename))

    conn.commit()
    conn.close()
    return redirect(url_for('patient_detail', id=id))

@app.route('/patient/<int:id>/delete')
def delete_patient(id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM visit_photos WHERE visit_id IN (SELECT id FROM visits WHERE patient_id=?)", (id,))
    c.execute("DELETE FROM visits WHERE patient_id=?", (id,))
    c.execute("DELETE FROM patients_v2 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('list_patients'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    folder = app.config['UPLOAD_FOLDER']
    
    # Check exact match
    exact_path = os.path.join(folder, filename)
    if os.path.exists(exact_path):
        return send_from_directory(folder, filename)
        
    # Check fuzzy match (fixes case-sensitive issues)
    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.lower() == filename.lower():
                return send_from_directory(folder, f)
                
    return "Image not found", 404

@app.route('/download_backup')
def download_backup():
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        if os.path.exists(DB_NAME): zf.write(DB_NAME, os.path.basename(DB_NAME))
        for root, dirs, files in os.walk(app.config['UPLOAD_FOLDER']):
            for file in files:
                file_path = os.path.join(root, file)
                zf.write(file_path, os.path.join(os.path.basename(app.config['UPLOAD_FOLDER']), file))
    memory_file.seek(0)
    return send_file(memory_file, download_name='clinic_backup.zip', as_attachment=True)

if __name__ == '__main__':
    from waitress import serve
    import os
    
    print("=========================================")
    print("🏥 DR. ATOK'S CLINIC SERVER IS RUNNING!")
    print(f"📂 LOOKING FOR DATABASE AT: {DB_NAME}")
    print(f"📂 DOES REAL DATABASE EXIST HERE? {os.path.exists(DB_NAME)}")
    print("📡 Waiting for tablet connection on Port 8080...")
    print("=========================================")
    
    try:
        # We are bumping the workers from 4 to 12!
        serve(app, host='0.0.0.0', port=8080, threads=12)
    except Exception as e:
        import traceback
        error_path = os.path.join(BASE_DIR, "CRASH_REPORT.txt")
        with open(error_path, "w") as f:
            f.write(traceback.format_exc())