from flask import Flask, request, render_template, session, redirect, url_for, flash, send_file
import pandas as pd
import numpy as np
import pickle
import os
import re
import ast
import base64
import io
import logging
import difflib
from datetime import datetime
try:
    from report_pdf import build_pdf_report  # needs: python -m pip install reportlab
except ImportError:
    build_pdf_report = None
from functools import wraps

# ---------- Paths (FIX: absolute paths so the app works from any working directory) ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def path(*parts):
    return os.path.join(BASE_DIR, *parts)


logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
log = logging.getLogger('medicine_recommendation')

app = Flask(__name__)
# FIX: a random key on every start logged everyone out whenever the server restarted / auto-reloaded.
app.secret_key = os.environ.get('MEDREC_SECRET_KEY', 'change-this-secret-key-in-production')
# FIX: cap upload size so a huge photo cannot exhaust memory.
app.config['MAX_CONTENT_LENGTH'] = 3 * 1024 * 1024  # 3 MB request limit

# ---------- Credentials (override with environment variables) ----------
USERNAME = os.environ.get('MEDREC_USERNAME', 'admin')
PASSWORD = os.environ.get('MEDREC_PASSWORD', 'admin')

# ---------- Load Model ----------
with open(path('models', 'svc_model.pkl'), 'rb') as f:
    model, encoder, feature_names = pickle.load(f)
# FIX: feature_names may be a numpy array / pandas Index, which has no .index() method.
feature_names = [str(n).strip().lower() for n in list(feature_names)]

# ---------- Load Databases ----------
description_df = pd.read_csv(path('data', 'description.csv'))
precautions_df = pd.read_csv(path('data', 'precautions.csv'))
medications_df = pd.read_csv(path('data', 'medications.csv'))
workout_df = pd.read_csv(path('data', 'workout.csv'))
diet_df = pd.read_csv(path('data', 'diet.csv'))

# ---------- Load Reference Data ----------
ref_df = pd.read_csv(path('data', 'symptoms_reference.csv'))
ref_df.columns = ref_df.columns.str.lower().str.strip()
ref_df = ref_df.fillna('')

# Clean unnamed columns
for df in [description_df, precautions_df, medications_df, workout_df, diet_df]:
    df.drop(columns=[c for c in df.columns if 'Unnamed' in c], inplace=True, errors='ignore')

# Lowercase / strip columns and disease names
# FIX: stray spaces in disease names ("Diabetes " vs "Diabetes") made lookups silently fail.
for df in [description_df, precautions_df, medications_df, workout_df, diet_df]:
    df.columns = df.columns.str.lower().str.strip()
    if 'disease' in df.columns:
        df['disease'] = df['disease'].astype(str).str.strip()

# Group medications / workout / diet
if 'medication' in medications_df.columns:
    medications_df = medications_df.groupby('disease')['medication'].apply(list).reset_index()
if 'workout' in workout_df.columns:
    workout_df = workout_df.groupby('disease')['workout'].apply(list).reset_index()
if 'diet' in diet_df.columns:
    diet_df = diet_df.groupby('disease')['diet'].apply(list).reset_index()

# Common everyday words (used by the quick-add symptom chips) -> dataset symptom names
SYMPTOM_ALIASES = {
    'fever': 'high_fever', 'sneeze': 'continuous_sneezing', 'sneezing': 'continuous_sneezing',
    'cold': 'continuous_sneezing', 'rash': 'skin_rash', 'tiredness': 'fatigue',
    'breathlessness': 'breathlessness', 'shortness of breath': 'breathlessness',
    'diarrhoea': 'diarrhoea', 'diarrhea': 'diarrhoea', 'sore throat': 'throat_irritation',
    'body pain': 'muscle_pain', 'dizziness': 'dizziness', 'nausea': 'nausea',
}

ALLOWED_PHOTO_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
GENDERS = ['Male', 'Female', 'Other', 'Prefer not to say']
BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-', 'Unknown']


# ---------- Helper Functions ----------
def clean_list(values, fallback):
    """Flatten list-like strings (e.g. "['a', 'b']"), drop NaN / empty values."""
    if values is None:
        return [fallback]
    if not isinstance(values, (list, tuple, np.ndarray, pd.Series)):
        values = [values]
    out = []
    for v in values:
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        s = str(v).strip()
        if not s or s.lower() == 'nan':
            continue
        # FIX: medications/diet CSVs store Python-style lists as text -> shown as "['A', 'B']".
        if s.startswith('[') and s.endswith(']'):
            try:
                parsed = ast.literal_eval(s)
                if isinstance(parsed, (list, tuple)):
                    out.extend(str(p).strip() for p in parsed if str(p).strip())
                    continue
            except (ValueError, SyntaxError):
                pass
        out.append(s)
    return out or [fallback]


def get_predicted_value(patient_symptoms):
    input_vector = np.zeros(len(feature_names))
    matched = []

    for symptom in patient_symptoms:
        symptom_clean = symptom.strip().lower().replace(' ', '_')
        candidates = [symptom_clean, symptom.strip().lower(), SYMPTOM_ALIASES.get(symptom.strip().lower(), '')]
        hit = next((c for c in candidates if c in feature_names), None)
        if hit is None:
            matches = difflib.get_close_matches(symptom_clean, feature_names, n=1, cutoff=0.6)
            hit = matches[0] if matches else None
            if hit:
                log.info("Mapped '%s' -> '%s'", symptom, hit)  # FIX: emoji prints crashed Windows consoles
        if hit:
            input_vector[feature_names.index(hit)] = 1
            matched.append(hit)
        else:
            log.warning("'%s' not found and no close match.", symptom)

    # FIX: with zero recognised symptoms the model still returned a (random) disease.
    if not matched:
        return None, []

    pred_int = model.predict([input_vector])[0]
    disease_name = encoder.inverse_transform([pred_int])[0]
    return str(disease_name).strip(), matched


def helper(disease):
    desc_row = description_df[description_df['disease'] == disease]
    description = str(desc_row['description'].values[0]) if not desc_row.empty else "No description available."

    prec_row = precautions_df[precautions_df['disease'] == disease]
    prec_cols = [c for c in precautions_df.columns if c.startswith('precaution_')]
    precautions = prec_row[prec_cols].iloc[0].tolist() if (not prec_row.empty and prec_cols) else None

    med_row = medications_df[medications_df['disease'] == disease]
    medications = med_row['medication'].iloc[0] if not med_row.empty else None

    work_row = workout_df[workout_df['disease'] == disease]
    if not work_row.empty:
        if 'workout' in workout_df.columns:
            workout = work_row['workout'].iloc[0]
        else:
            work_cols = [c for c in workout_df.columns if c.startswith('workout_')]
            workout = work_row[work_cols].iloc[0].tolist() if work_cols else None
    else:
        workout = None

    diet_row = diet_df[diet_df['disease'] == disease]
    if not diet_row.empty:
        if 'diet' in diet_df.columns:
            diet = diet_row['diet'].iloc[0]
        else:
            diet_cols = [c for c in diet_df.columns if c.startswith('diet_')]
            diet = diet_row[diet_cols].iloc[0].tolist() if diet_cols else None
    else:
        diet = None

    return (description,
            clean_list(precautions, "No precautions available."),
            clean_list(medications, "No medications available."),
            clean_list(workout, "No workout suggestions."),
            clean_list(diet, "No diet suggestions."))


def ref_value(row, col):
    # FIX: a missing column in symptoms_reference.csv raised KeyError and crashed the page.
    return str(row[col]).strip() if col in row.index else ''


def lookup_reference(symptom):
    """Exact match first, then literal (non-regex) substring match."""
    if 'symptom' not in ref_df.columns:
        return None
    col = ref_df['symptom'].astype(str).str.lower().str.strip()
    exact = ref_df[col == symptom]
    if not exact.empty:
        return exact.iloc[0]
    # FIX: str.contains() treated input as a regex -> "(" or "+" crashed the app,
    # and 1-2 letter inputs like "a" matched almost every row.
    if len(symptom) >= 3:
        partial = ref_df[col.str.contains(symptom, na=False, regex=False)]
        if not partial.empty:
            return partial.iloc[0]
    return None


def read_patient_form():
    """Collect and validate patient details. Returns (patient_dict, errors_list)."""
    f = request.form
    p = {
        'name': f.get('name', '').strip(),
        'age': f.get('age', '').strip(),
        'phone': f.get('phone', '').strip(),
        'email': f.get('email', '').strip(),
        'gender': f.get('gender', '').strip(),
        'blood_group': f.get('blood_group', '').strip(),
        'weight': f.get('weight', '').strip(),
        'height': f.get('height', '').strip(),
        'current_medications': f.get('current_medications', '').strip(),
        'history': f.get('history', '').strip(),
        'allergies': f.get('allergies', '').strip(),
        'photo': f.get('photo_data', '').strip(),  # keeps an already-uploaded photo across re-submits
    }
    errors = []

    if not p['name']:
        errors.append("Patient name is required.")
    elif len(p['name']) > 100:
        errors.append("Patient name is too long.")

    if not p['age']:
        errors.append("Age is required.")
    else:
        try:
            age = int(p['age'])
            if not 0 <= age <= 130:
                raise ValueError
        except ValueError:
            errors.append("Age must be a whole number between 0 and 130.")

    # ---- Phone: value arrives as "<country_code><local_digits>" e.g. "+919876543210" ----
    digits_only = re.sub(r'\D', '', p['phone'])   # strip everything except digits
    if not p['phone']:
        errors.append("Contact number is required.")
    elif not p['phone'].startswith('+') or len(digits_only) < 7 or len(digits_only) > 15:
        errors.append("Enter a valid contact number (country code + number).")

    # ---- Email: value arrives pre-assembled as "username@domain.com" ----
    if p['email'] and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', p['email']):
        errors.append("Enter a valid email address.")

    if p['gender'] and p['gender'] not in GENDERS:
        errors.append("Please choose a valid gender.")
    if p['blood_group'] and p['blood_group'] not in BLOOD_GROUPS:
        errors.append("Please choose a valid blood group.")

    for key, label, lo, hi in [('weight', 'Weight (kg)', 0.5, 500), ('height', 'Height (cm)', 20, 280)]:
        if p[key]:
            try:
                v = float(p[key])
                if not lo <= v <= hi:
                    raise ValueError
            except ValueError:
                errors.append(f"{label} must be between {lo:g} and {hi:g}.")

    # Photo upload (optional) - stored in memory only, never written to disk
    file = request.files.get('photo')
    if file and file.filename:
        if file.mimetype not in ALLOWED_PHOTO_TYPES:
            errors.append("Photo must be a JPG, PNG, WEBP or GIF image.")
        else:
            data = file.read()
            if len(data) > 2 * 1024 * 1024:
                errors.append("Photo must be smaller than 2 MB.")
            else:
                p['photo'] = f"data:{file.mimetype};base64,{base64.b64encode(data).decode()}"
    if p['photo'] and not re.match(r'^data:image/(jpeg|png|webp|gif);base64,[A-Za-z0-9+/=]+$', p['photo']):
        p['photo'] = ''  # FIX: never echo back an arbitrary string into an <img src>

    return p, errors


def render_index(**ctx):
    ctx.setdefault('patient', {})
    ctx.setdefault('user_input', '')
    return render_template('index.html', genders=GENDERS, blood_groups=BLOOD_GROUPS,
                           report_time=datetime.now().strftime('%d %b %Y, %I:%M %p'), **ctx)


# ---------- Login Required Decorator ----------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# ---------- Routes ----------
@app.route('/')
@login_required
def index():
    return render_index()


@app.route('/about')
@login_required
def about():
    return render_template('about.html')


@app.route('/contact')
@login_required
def contact():
    return render_template('contact.html')


@app.route('/developer')
@login_required
def developer():
    return render_template('developer.html')


@app.route('/blog')
@login_required
def blog():
    return render_template('blog.html')


@app.route('/how-to-use')
@login_required
def how_to_use():
    return render_template('how_to_use.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session and request.method == 'GET':
        return redirect(url_for('index'))  # FIX: logged-in users no longer see the login form again
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if username == USERNAME and password == PASSWORD:
            session['user'] = username
            flash('Logged in successfully.', 'success')
            return redirect(url_for('index'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))


def compute_assessment():
    """Validate the form and run the prediction. Returns a template context dict."""
    patient, errors = read_patient_form()
    symptoms_str = request.form.get('symptoms', '').strip()
    # FIX: deduplicate symptoms and ignore empty entries such as "fever,,cough,"
    user_symptoms = list(dict.fromkeys(s.strip().lower() for s in symptoms_str.split(',') if s.strip()))

    if not user_symptoms:
        errors.append("Please enter at least one symptom.")
    if errors:
        return dict(errors=errors, patient=patient, user_input=symptoms_str)

    # STEP 1: reference data (single symptom)
    if len(user_symptoms) == 1:
        row = lookup_reference(user_symptoms[0])
        if row is not None:
            prec_raw = ref_value(row, 'precautions').replace('\n', '<br>')
            return dict(
                predicted_disease=ref_value(row, 'possible disease') or 'Unknown',
                disease_description=ref_value(row, 'description') or 'No description available.',
                disease_precautions=clean_list([p for p in prec_raw.split('<br>')], "No precautions available."),
                disease_medications=clean_list(ref_value(row, 'medications'), "No medications available."),
                disease_workout=clean_list(ref_value(row, 'workout'), "No workout suggestions."),
                disease_diet=clean_list(ref_value(row, 'diet'), "No diet suggestions."),
                matched_symptoms=user_symptoms,
                patient=patient, user_input=symptoms_str)

    # STEP 2: ML model
    predicted_disease, matched = get_predicted_value(user_symptoms)
    if predicted_disease is None:
        return dict(
            errors=["None of the entered symptoms were recognised. Try common terms such as "
                    "'itching', 'headache', 'vomiting' or 'high fever'."],
            patient=patient, user_input=symptoms_str)

    description, precautions, medications, workout, diet = helper(predicted_disease)
    return dict(
        predicted_disease=predicted_disease,
        disease_description=description,
        disease_precautions=precautions,
        disease_medications=medications,
        disease_workout=workout,
        disease_diet=diet,
        matched_symptoms=[m.replace('_', ' ') for m in matched],
        patient=patient, user_input=symptoms_str)


@app.route('/predict', methods=['GET', 'POST'])
@login_required
def predict():
    # FIX: refreshing / bookmarking /predict gave "405 Method Not Allowed".
    if request.method == 'GET':
        return redirect(url_for('index'))
    return render_index(**compute_assessment())


@app.route('/report', methods=['GET', 'POST'])
@login_required
def report():
    """Download the patient assessment as a PDF."""
    if request.method == 'GET':
        return redirect(url_for('index'))
    ctx = compute_assessment()
    if ctx.get('errors'):
        return render_index(**ctx)
    if build_pdf_report is None:
        # App keeps working without ReportLab; only the PDF download is unavailable.
        ctx.setdefault('errors', []).append(
            "PDF download needs the 'reportlab' package. Install it with: python -m pip install reportlab "
            "and restart the app.")
        return render_index(**ctx)
    pdf = build_pdf_report(ctx)
    safe_name = re.sub(r'[^A-Za-z0-9]+', '_', ctx['patient'].get('name', 'patient')).strip('_') or 'patient'
    filename = f"Patient_Report_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    return send_file(io.BytesIO(pdf), mimetype='application/pdf', as_attachment=True, download_name=filename)


@app.errorhandler(413)
def too_large(_e):
    flash('Upload too large. Please use a photo smaller than 2 MB.', 'danger')
    return redirect(url_for('index'))


if __name__ == '__main__':
    # FIX: debug mode is now opt-in (set FLASK_DEBUG=1) - never expose the debugger publicly.
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1', port=5000)
