# ==========================================================================
# File: app.py (Section 1: Imports & Database Bridge Configuration)
# ==========================================================================
import paramiko
if not hasattr(paramiko, 'DSSKey'):
    # Patches paramiko dynamically to handle sshtunnel lifecycle updates
    paramiko.DSSKey = paramiko.RSAKey

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from sshtunnel import SSHTunnelForwarder
import mysql.connector

# Streamlit is used to host this project on the web.
import streamlit as st

# Points to your custom asset directories and templates folder location
app = Flask(__name__, static_url_path='', static_folder='.', template_folder='pages')
app.secret_key = 'adelphi_secure_session_token_key'

def get_db_connection():
    """Opens a secure SSH tunnel bridge and returns an active MySQL connection."""
    tunnel = SSHTunnelForwarder(
        ('compsci.adelphi.edu', 22),
        ssh_username=st.secrets.db_credentials.ssh_username, 
        ssh_password=st.secrets.db_credentials.ssh_password,
        remote_bind_address=('127.0.0.1', 3306)
    )
    tunnel.start()
    return mysql.connector.connect(
        host='127.0.0.1',
        port=tunnel.local_bind_port,
        user=st.secrets.db_credentials.user,
        password=st.secrets.db_credentials.password,
        database='ALESSANDROFIORELLA',
        autocommit=True
    )

# ==========================================================================
# File: app.py (Section 2: Security & Session Authentication Controllers)
# ==========================================================================

@app.route('/', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        email_input = request.form.get('username', '').strip()
        password_input = request.form.get('password', '')

        if not email_input or not password_input:
            return render_template('login.html', error="Please fill out all fields.")

        try:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # 1. Lookup user in your main user table directory
            cursor.execute("SELECT * FROM ExamUser WHERE email = %s", (email_input,))
            user_record = cursor.fetchone()

            if not user_record:
                cursor.close()
                conn.close()
                return render_template('login.html', error="User email address not found.")

            # 2. Query separate role authorization strings independently
            cursor.execute("""
                SELECT ExamRole_idExamRole 
                FROM ExamPossibleRoles 
                WHERE ExamUser_idExamUser = %s
            """, (user_record['idExamUser'],))
            
            roles_fetched = cursor.fetchall()
            user_roles = [str(r['ExamRole_idExamRole']).strip().lower() for r in roles_fetched]

            # 3. Formulate true/false visibility matrix tags
            session['user_id'] = user_record['idExamUser']
            session['first_name'] = user_record['firstName']
            session['last_name'] = user_record['lastName']
            session['email'] = user_record['email']
            
            session['has_student_role'] = 'student' in user_roles
            session['has_faculty_role'] = 'faculty' in user_roles
            session['has_proctor_role'] = 'proctor' in user_roles

            # Calculate composite role token identity
            simulated_role = "student"
            if session['has_student_role'] and session['has_faculty_role'] and session['has_proctor_role']:
                simulated_role = "superuser"
            elif session['has_faculty_role'] and session['has_proctor_role']:
                simulated_role = "faculty_proctor"
            elif session['has_faculty_role']:
                simulated_role = "faculty"
            elif session['has_proctor_role']:
                simulated_role = "proctor"

            session['portal_role'] = simulated_role
            
            cursor.close()
            conn.close()
            return redirect(url_for('dashboard_page'))

        except Exception as e:
            return render_template('login.html', error=f"Auth Warning: {str(e)}")

    return render_template('login.html', error=None)

@app.route('/logout')
def logout_action():
    session.clear() # Completely flushes cookies
    return redirect(url_for('login_page'))

# ==========================================================================
# File: app.py (Section 3: Main Dashboard Relational Query Hub)
# ==========================================================================

@app.route('/dashboard')
def dashboard_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # A. Query ONLY active classes for this student where today's date matches running boundaries
        cursor.execute("""
            SELECT ec.idExamCourse, ec.courseName, ec.meetingDays, ec.courseStart, ec.courseEnd, ec.meetingStart
            FROM ExamCourseRegistrant ecr
            JOIN ExamCourse ec ON ecr.registrantCourse = ec.idExamCourse
            WHERE ecr.registrantUser = %s AND ecr.registrantRole = 'Student'
              AND %s BETWEEN ec.courseStart AND ec.courseEnd
        """, (session['user_id'], '2026-07-20'))
        active_student_courses = cursor.fetchall()

        for course in active_student_courses:
            course['courseStartStr'] = course['courseStart'].strftime('%Y-%m-%d') if course['courseStart'] else '2026-06-01'
            course['courseEndStr'] = course['courseEnd'].strftime('%Y-%m-%d') if course['courseEnd'] else '2026-08-30'
            course['meetingStart'] = str(course['meetingStart']) if course['meetingStart'] else '09:00:00'

        # B. Query approved accommodation lookups this user possesses
        cursor.execute("""
            SELECT opt.accommodationID, opt.accommodationName 
            FROM ExamAccommodationsApproved app
            JOIN ExamAccommodationOptions opt ON app.accommodationApproved = opt.accommodationID
            WHERE app.userAccommodated = %s
        """, (session['user_id'],))
        approved_accomm_options = cursor.fetchall()

        cursor.execute("SELECT accommodationID, accommodationName FROM ExamAccommodationOptions")
        opt_map = {str(row['accommodationID']): row['accommodationName'] for row in cursor.fetchall()}

        # C. Query isolated student feed cards
        cursor.execute("""
            SELECT er.idExamRequest, er.requestedDate, er.requestedTime, er.actualDate, er.actualTime, 
                   er.actualLength, er.accommodations as raw_accomm_ids, er.timeExtension, er.comments, er.statusID,
                   ec.courseName, ec.idExamCourse, eu.firstName as studentFirstName, eu.lastName as studentLastName, eu.email as studentEmail
            FROM ExamRequest er
            LEFT JOIN ExamCourse ec ON er.courseID = ec.idExamCourse
            INNER JOIN ExamDetails ed ON er.idExamRequest = ed.detailExam
            INNER JOIN ExamUser eu ON ed.detailUser = eu.idExamUser
            WHERE ed.detailRole = 'Student' AND ed.detailUser = %s
        """, (session['user_id'],))
        student_exams = cursor.fetchall()

        # D. Query faculty feed tracking lines (Restricted to courses they teach)
        cursor.execute("""
            SELECT er.idExamRequest, er.requestedDate, er.requestedTime, er.actualDate, er.actualTime, 
                   er.actualLength, er.accommodations as raw_accomm_ids, er.timeExtension, er.comments, er.statusID,
                   ec.courseName, ec.idExamCourse,
                   (SELECT u.firstName FROM ExamDetails d JOIN ExamUser u ON d.detailUser = u.idExamUser WHERE d.detailExam = er.idExamRequest AND d.detailRole = 'Student' LIMIT 1) as studentFirstName,
                   (SELECT u.lastName FROM ExamDetails d JOIN ExamUser u ON d.detailUser = u.idExamUser WHERE d.detailExam = er.idExamRequest AND d.detailRole = 'Student' LIMIT 1) as studentLastName,
                   (SELECT u.email FROM ExamDetails d JOIN ExamUser u ON d.detailUser = u.idExamUser WHERE d.detailExam = er.idExamRequest AND d.detailRole = 'Student' LIMIT 1) as studentEmail
            FROM ExamRequest er
            INNER JOIN ExamCourse ec ON er.courseID = ec.idExamCourse
            INNER JOIN ExamCourseRegistrant ecr ON ec.idExamCourse = ecr.registrantCourse
            WHERE ecr.registrantUser = %s AND ecr.registrantRole = 'Faculty'
        """, (session['user_id'],))
        faculty_exams = cursor.fetchall()

        # E. Query comprehensive Proctor dashboard market track
        cursor.execute("""
            SELECT 
                er.idExamRequest, er.requestedDate, er.requestedTime,
                er.actualDate, er.actualTime, er.actualLength,
                er.accommodations as raw_accomm_ids, er.timeExtension, er.comments, er.statusID,
                ec.courseName, ec.idExamCourse, er.ExamRequestcol as testingLocation,
                eu.firstName as studentFirstName, eu.lastName as studentLastName, eu.email as studentEmail,
                -- FIXED: Added an explicit subquery string to fetch the user ID of the assigned proctor
                (SELECT p_ed.detailUser FROM ExamDetails p_ed WHERE p_ed.detailExam = er.idExamRequest AND p_ed.detailRole = 'Proctor' LIMIT 1) as assignedProctorID,
                (SELECT CONCAT(p_u.firstName, ' ', p_u.lastName) FROM ExamDetails p_ed JOIN ExamUser p_u ON p_ed.detailUser = p_u.idExamUser WHERE p_ed.detailExam = er.idExamRequest AND p_ed.detailRole = 'Proctor' LIMIT 1) as proctorName,
                (SELECT p_u.email FROM ExamDetails p_ed JOIN ExamUser p_u ON p_ed.detailUser = p_u.idExamUser WHERE p_ed.detailExam = er.idExamRequest AND p_ed.detailRole = 'Proctor' LIMIT 1) as proctorEmail
            FROM ExamRequest er
            LEFT JOIN ExamCourse ec ON er.courseID = ec.idExamCourse
            LEFT JOIN ExamDetails ed ON er.idExamRequest = ed.detailExam AND ed.detailRole = 'Student'
            LEFT JOIN ExamUser eu ON ed.detailUser = eu.idExamUser
        """)
        proctor_exams = cursor.fetchall()


        # Python Date parsing loops
        for dataset in [student_exams, faculty_exams, proctor_exams]:
            for exam in dataset:
                raw_ids = exam.get('raw_accomm_ids')
                if raw_ids and raw_ids.strip():
                    exam['accommodations'] = ", ".join([opt_map.get(rid, f"Option #{rid}") for rid in raw_ids.split()])
                else:
                    exam['accommodations'] = "None Requested"

                exam['pref_date'] = exam['requestedDate'].strftime('%Y-%m-%d') if exam['requestedDate'] else '2026-07-20'
                exam['sub_date'] = exam['pref_date']
                exam['actualDate'] = exam['actualDate'].strftime('%Y-%m-%d') if exam['actualDate'] else ''
                exam['requestedTime'] = str(exam['requestedTime'])[:5] if exam['requestedTime'] else '00:00'
                exam['actualTime'] = str(exam['actualTime'])[:5] if exam['actualTime'] else ''

        cursor.close()
        conn.close()

                # File: app.py - Update the return line at the bottom of /dashboard route
        return render_template('dashboard.html', 
                               student_exams=student_exams, 
                               faculty_exams=faculty_exams, 
                               proctor_exams=proctor_exams,
                               courses=active_student_courses,
                               approved_accomm_options=approved_accomm_options,
                               is_student=session.get('has_student_role'), 
                               is_faculty=session.get('has_faculty_role'), 
                               is_proctor=session.get('has_proctor_role'),
                               user_role=session.get('portal_role'), 
                               first_name=session.get('first_name'), 
                               last_name=session.get('last_name'), 
                               email=session.get('email'),
                               # FIXED: Passes the logged-in user integer ID down to the HTML frontend template
                               current_user_id=session.get('user_id'))

    except Exception as e:
        return f"Dashboard Fetch Failure: {str(e)}", 500

# ==========================================================================
# File: app.py (Section 4: Data Entry Form Submission & Update Action Handlers)
# ==========================================================================

@app.route('/submit-registration', methods=['POST'])
def submit_registration():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    course_id = request.form.get('selected_course_id')
    exam_date = request.form.get('start_date')
    accomm_id_list = request.form.getlist('selected_accomm_ids[]')
    space_delimited_accomm_str = " ".join(accomm_id_list) if accomm_id_list else ""

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT meetingStart FROM ExamCourse WHERE idExamCourse = %s", (course_id,))
        course_data = cursor.fetchone()
        course_start_time = str(course_data['meetingStart']) if (course_data and course_data['meetingStart']) else "09:00:00"

        cursor.execute("""
            INSERT INTO ExamRequest (statusID, courseID, ExamRequestcol, requestedDate, requestedTime, actualDate, actualTime, actualLength, accommodations, timeExtension, comments)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, ('Requested', course_id, 'TBD by Proctor', exam_date, course_start_time, exam_date, course_start_time, 60, space_delimited_accomm_str, 0, ''))
        
        new_request_id = cursor.lastrowid
        cursor.execute("INSERT INTO ExamDetails (detailUser, detailRole, detailExam) VALUES (%s, 'Student', %s)", (session['user_id'], new_request_id))
        cursor.close(); conn.close()
        return redirect(url_for('dashboard_page'))
    except Exception as e:
        return f"Entry Failure: {str(e)}", 500

# --- ROUTE 4: FACULTY ACTION CONTROLLER (UPDATED FOR DENY & CANCEL LIFECYCLES) ---
@app.route('/faculty/update-request', methods=['POST'])
def faculty_update_request():
    if 'user_id' not in session: 
        return redirect(url_for('login_page'))
        
    request_id = request.form.get('request_id')
    assigned_date = request.form.get('assigned_exam_date')
    action_type = request.form.get('action_type')
    base_length = int(request.form.get('exam_duration_minutes') or 60)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Fetch current request metadata for accommodation verification loops
        cursor.execute("SELECT accommodations, requestedTime FROM ExamRequest WHERE idExamRequest = %s", (request_id,))
        exam_row = cursor.fetchone()
        
        final_length = int(base_length * 1.5) if (exam_row and exam_row['accommodations'] and '1' in exam_row['accommodations'].split()) else base_length
        time_diff = final_length - base_length

        # FIXED ROUTING MATRIX: Maps your new button actions directly to your updated status table constraints
        if action_type == 'approve_request':
            new_status = 'Approved By Faculty (Initial)'
            cursor.execute("""
                UPDATE ExamRequest 
                SET actualDate = %s, actualTime = %s, actualLength = %s, timeExtension = %s, statusID = %s 
                WHERE idExamRequest = %s
            """, (assigned_date, exam_row['requestedTime'], final_length, time_diff, new_status, request_id))
            
        elif action_type == 'approve_proctor':
            new_status = 'Approved By Faculty (Final)'
            cursor.execute("UPDATE ExamRequest SET statusID = %s WHERE idExamRequest = %s", (new_status, request_id))
            
        elif action_type == 'deny_request':
            # FIXED: New action handler for denying newly submitted requests
            new_status = 'Denied'
            cursor.execute("UPDATE ExamRequest SET statusID = %s WHERE idExamRequest = %s", (new_status, request_id))
            
        elif action_type == 'cancel_request':
            # FIXED: New action handler for canceling already approved active requests
            new_status = 'Canceled'
            # Wipes proctor testing location data out alongside status transitions
            cursor.execute("UPDATE ExamRequest SET statusID = %s, ExamRequestcol = 'Canceled' WHERE idExamRequest = %s", (new_status, request_id))
            
        else:
            new_status = 'Under Review'
            cursor.execute("UPDATE ExamRequest SET statusID = %s WHERE idExamRequest = %s", (new_status, request_id))
            
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard_page'))
    except Exception as e:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()
        return f"Faculty Workflow Processing Error: {str(e)}", 500


@app.route('/proctor/claim-request', methods=['POST'])
def proctor_claim_request():
    if 'user_id' not in session: return redirect(url_for('login_page'))
    request_id, location_room = request.form.get('request_id'), request.form.get('proctor_location')
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE ExamRequest SET statusID = 'Approved By Proctor', ExamRequestcol = %s WHERE idExamRequest = %s", (location_room, request_id))
    cursor.execute("INSERT INTO ExamDetails (detailUser, detailRole, detailExam) VALUES (%s, 'Proctor', %s)", (session['user_id'], request_id))
    cursor.close(); conn.close()
    return redirect(url_for('dashboard_page'))

# --- ROUTE 6: PROCTOR DROP CONTROLLER (UPDATED FOR ANYTIME LIFE-CYCLE Pool RESET) ---
@app.route('/proctor/drop-request', methods=['POST'])
def proctor_drop_request():
    if 'user_id' not in session: 
        return redirect(url_for('login_page'))

    request_id = request.form.get('request_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 1. FIXED STATUS CODE: Resets the request row back to the exact initial faculty approval state
        # and forcefully wipes out the room assignment string data to allow re-entry
        cursor.execute("""
            UPDATE ExamRequest 
            SET statusID = 'Approved By Faculty (Initial)',
                ExamRequestcol = 'TBD by Proctor'
            WHERE idExamRequest = %s
        """, (request_id,))

        # 2. Deletes the active proctor relationship row mapping from the junction table
        cursor.execute("""
            DELETE FROM ExamDetails 
            WHERE detailUser = %s 
              AND detailExam = %s 
              AND detailRole = 'Proctor'
        """, (session['user_id'], request_id))

        cursor.close()
        conn.close()
        return redirect(url_for('dashboard_page'))
        
    except Exception as e:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()
        return f"Proctor Resignation Processing Failure: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
