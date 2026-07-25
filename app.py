#-------------------- Imports --------------------#
# Paramiko and Flask are required for my front and back-ends to communicate with one another. 
import paramiko
if not hasattr(paramiko, 'DSSKey'):
    # Patches paramiko dynamically to handle sshtunnel lifecycle updates
    paramiko.DSSKey = paramiko.RSAKey
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
# SSHTunnel and MySQL Connector are required to actually connect to the secure compsci.adelphi.edu server.
from sshtunnel import SSHTunnelForwarder
import mysql.connector
# OS is required for use with Render.com and allows me to obscure my login information.
import os

# Customizing the template folder (though it's not really necessary).
app = Flask(__name__, static_url_path='', static_folder='.', template_folder='pages')
app.secret_key = 'adelphi_secure_session_token_key'

#-------------------- Database Connection --------------------#
def get_db_connection():
    """Opens a secure SSH tunnel bridge and returns an active MySQL connection."""
    tunnel = SSHTunnelForwarder(
        #Replace with your system's SSH server and port.
        ('compsci.adelphi.edu', 22),
        #Replace with your system's SSH username and password if running locally, otherwise set these as environment variables on Render.com.
        ssh_username=os.environ.get("ssh_username"), 
        ssh_password=os.environ.get("ssh_password"),
        remote_bind_address=('127.0.0.1', 3306)
    )
    tunnel.start()
    return mysql.connector.connect(
        host='127.0.0.1',
        port=tunnel.local_bind_port,
        #Replace with your system's username and password if running locally, otherwise set these as environment variables on Render.com.
        user=os.environ.get("user"),
        password=os.environ.get("password"),
        database='ALESSANDROFIORELLA',
        autocommit=True
    )

#--------------------App Routes --------------------#
#========== Login Route ==========#
# This route handles the "demo" login system for this application.
# Note that in it's current form this system is not secure, nor is it meant to be.
# The main dashboard of this application should be connected to your existing infrustructure's authentication system (ex: eCampus). 

# To log into the application and view demo data, input any existing user's email address and the word "password". 
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

            # Query the ExamUser table to find the user by their email.
            cursor.execute("SELECT * FROM ExamUser WHERE email = %s", (email_input,))
            user_record = cursor.fetchone()

            if not user_record:
                cursor.close()
                conn.close()
                return render_template('login.html', error="User email address not found.")

            # Check the roles that this user has.
            cursor.execute("""
                SELECT ExamRole_idExamRole 
                FROM ExamPossibleRoles 
                WHERE ExamUser_idExamUser = %s
            """, (user_record['idExamUser'],))
            
            roles_fetched = cursor.fetchall()
            user_roles = [str(r['ExamRole_idExamRole']).strip().lower() for r in roles_fetched]

            # Store the user's information and roles.
            session['user_id'] = user_record['idExamUser']
            session['first_name'] = user_record['firstName']
            session['last_name'] = user_record['lastName']
            session['email'] = user_record['email']
            
            session['has_student_role'] = 'student' in user_roles
            session['has_faculty_role'] = 'faculty' in user_roles
            session['has_proctor_role'] = 'proctor' in user_roles

            # We need to see if the user has muiltiple roles and assign them accordingly.
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

#========== Logout Route ==========#
@app.route('/logout')
def logout_action():
    session.clear() 
    return redirect(url_for('login_page'))

#========== Dashboard Route ==========#
# The main dashboard; a bulk of the actual application is in here.
@app.route('/dashboard')
def dashboard_page():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))

    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        #------ Student Courses -----#
        # Pulling all currently running courses that the user is registered for as a student.
        cursor.execute("""
            SELECT ec.idExamCourse, ec.courseName, ec.meetingDays, ec.courseStart, ec.courseEnd, ec.meetingStart
            FROM ExamCourseRegistrant ecr
            JOIN ExamCourse ec ON ecr.registrantCourse = ec.idExamCourse
            WHERE ecr.registrantUser = %s AND ecr.registrantRole = 'Student'
              AND %s BETWEEN ec.courseStart AND ec.courseEnd
        """, (session['user_id'], '2026-07-20'))
        active_student_courses = cursor.fetchall()

        # Looping through all courses to format accordingly.
        for course in active_student_courses:
            course['courseStartStr'] = course['courseStart'].strftime('%Y-%m-%d') if course['courseStart'] else '2026-06-01'
            course['courseEndStr'] = course['courseEnd'].strftime('%Y-%m-%d') if course['courseEnd'] else '2026-08-30'
            course['meetingStart'] = str(course['meetingStart']) if course['meetingStart'] else '09:00:00'

        # Checking all of their approved exam accommodations; in an actual system these would likely be stored in a seperate database entirely.
        cursor.execute("""
            SELECT opt.accommodationID, opt.accommodationName 
            FROM ExamAccommodationsApproved app
            JOIN ExamAccommodationOptions opt ON app.accommodationApproved = opt.accommodationID
            WHERE app.userAccommodated = %s
        """, (session['user_id'],))
        approved_accomm_options = cursor.fetchall()

        cursor.execute("SELECT accommodationID, accommodationName FROM ExamAccommodationOptions")
        opt_map = {str(row['accommodationID']): row['accommodationName'] for row in cursor.fetchall()}

        #------ Student Exam Requests (for Students) -----#
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

         #------ Exam Requests (for Faculty) -----#
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

         #------ Exam Requests (for Proctors) -----#
        cursor.execute("""
            SELECT 
                er.idExamRequest, er.requestedDate, er.requestedTime,
                er.actualDate, er.actualTime, er.actualLength,
                er.accommodations as raw_accomm_ids, er.timeExtension, er.comments, er.statusID,
                ec.courseName, ec.idExamCourse, er.ExamRequestcol as testingLocation,
                eu.firstName as studentFirstName, eu.lastName as studentLastName, eu.email as studentEmail,
                (SELECT p_ed.detailUser FROM ExamDetails p_ed WHERE p_ed.detailExam = er.idExamRequest AND p_ed.detailRole = 'Proctor' LIMIT 1) as assignedProctorID,
                (SELECT CONCAT(p_u.firstName, ' ', p_u.lastName) FROM ExamDetails p_ed JOIN ExamUser p_u ON p_ed.detailUser = p_u.idExamUser WHERE p_ed.detailExam = er.idExamRequest AND p_ed.detailRole = 'Proctor' LIMIT 1) as proctorName,
                (SELECT p_u.email FROM ExamDetails p_ed JOIN ExamUser p_u ON p_ed.detailUser = p_u.idExamUser WHERE p_ed.detailExam = er.idExamRequest AND p_ed.detailRole = 'Proctor' LIMIT 1) as proctorEmail
            FROM ExamRequest er
            LEFT JOIN ExamCourse ec ON er.courseID = ec.idExamCourse
            LEFT JOIN ExamDetails ed ON er.idExamRequest = ed.detailExam AND ed.detailRole = 'Student'
            LEFT JOIN ExamUser eu ON ed.detailUser = eu.idExamUser
        """)
        proctor_exams = cursor.fetchall()


        # Formatting dates and times for readability.
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

        # Render the dashboard template with all the data that's been fetched and formatted.
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
                               current_user_id=session.get('user_id'))

    # Just in case!
    except Exception as e:
        return f"Dashboard Fetch Failure: {str(e)}", 500


#========== Exam Request Form Route (Student Tab) ==========#
@app.route('/submit-request', methods=['POST'])
def submit_registration():
    # Make sure we're logged in and ready.
    if 'user_id' not in session: 
        return redirect(url_for('login_page'))

    # Grab all of the input data from the form submission.
    course_id = request.form.get('selected_course_id')
    exam_date = request.form.get('start_date')
    accomm_id_list = request.form.getlist('selected_accomm_ids[]')
    space_delimited_accomm_str = " ".join(accomm_id_list) if accomm_id_list else ""

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # All exams are set to start at the same time as the rest of class; instructors can change this later if they want to.
        cursor.execute("SELECT meetingStart FROM ExamCourse WHERE idExamCourse = %s", (course_id,))
        course_data = cursor.fetchone()
        course_start_time = str(course_data['meetingStart']) if (course_data and course_data['meetingStart']) else "09:00:00"

        # Push to the database.
        cursor.execute("""
            INSERT INTO ExamRequest (statusID, courseID, ExamRequestcol, requestedDate, requestedTime, actualDate, actualTime, actualLength, accommodations, timeExtension, comments)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, ('Requested', course_id, 'TBD by Proctor', exam_date, course_start_time, exam_date, course_start_time, 60, space_delimited_accomm_str, 0, ''))
        
        new_request_id = cursor.lastrowid
        cursor.execute("INSERT INTO ExamDetails (detailUser, detailRole, detailExam) VALUES (%s, 'Student', %s)", (session['user_id'], new_request_id))
        cursor.close(); conn.close()
        return redirect(url_for('dashboard_page'))

    # Just in case!
    except Exception as e:
        return f"Entry Failure: {str(e)}", 500

#========== Exam Request Update Route (Faculty Tab)==========#
@app.route('/faculty/update-request', methods=['POST'])
def faculty_update_request():
    # Make sure we're logged in and ready.
    if 'user_id' not in session: 
        return redirect(url_for('login_page'))

    # Grab all of the input data that user has potentially changed about the request.
    request_id = request.form.get('request_id')
    assigned_date = request.form.get('assigned_exam_date')
    action_type = request.form.get('action_type')
    base_length = int(request.form.get('exam_duration_minutes') or 60)

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Handling time-extension; this is more of a "proof of concept", and parties interested in full-integration will need to contend with other potential extension amounhts.
        cursor.execute("SELECT accommodations, requestedTime FROM ExamRequest WHERE idExamRequest = %s", (request_id,))
        exam_row = cursor.fetchone()
        
        final_length = int(base_length * 1.5) if (exam_row and exam_row['accommodations'] and '1' in exam_row['accommodations'].split()) else base_length
        time_diff = final_length - base_length

        # Approving a request confirms the details and makes it available for proctors.
        if action_type == 'approve_request':
            new_status = 'Approved By Faculty (Initial)'
            cursor.execute("""
                UPDATE ExamRequest 
                SET actualDate = %s, actualTime = %s, actualLength = %s, timeExtension = %s, statusID = %s 
                WHERE idExamRequest = %s
            """, (assigned_date, exam_row['requestedTime'], final_length, time_diff, new_status, request_id))

        # Approving a proctor confirms the exam is happening.            
        elif action_type == 'approve_proctor':
            new_status = 'Approved By Faculty (Final)'
            cursor.execute("UPDATE ExamRequest SET statusID = %s WHERE idExamRequest = %s", (new_status, request_id))

        # Denying a request prevents it from being scheduled and removes it from the active pool.
        #  Denied requests are ones that were never planned or approved.
        elif action_type == 'deny_request':
            new_status = 'Denied'
            cursor.execute("UPDATE ExamRequest SET statusID = %s WHERE idExamRequest = %s", (new_status, request_id))

        # Canceling a request prevents it from being scheduled and removes it from the active pool.
        #  Canceled requests are ones that *were* planned/approved and then canceled (for whatever reason outside of the form).
        elif action_type == 'cancel_request':
            new_status = 'Canceled'
            cursor.execute("UPDATE ExamRequest SET statusID = %s, ExamRequestcol = 'Canceled' WHERE idExamRequest = %s", (new_status, request_id))

        # Under review just means that a request has not been approved or denied yet.
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

#========== Exam Request Claim Route (Proctor Tab)==========#
@app.route('/proctor/claim-request', methods=['POST'])
def proctor_claim_request():
    # Make sure we're logged in and ready.
    if 'user_id' not in session: 
        return redirect(url_for('login_page'))
    
    # Claiming a request puts your name on it (as the proctor), pulling it from the pool.
    request_id, location_room = request.form.get('request_id'), request.form.get('proctor_location')
    conn = get_db_connection(); cursor = conn.cursor()
    cursor.execute("UPDATE ExamRequest SET statusID = 'Approved By Proctor', ExamRequestcol = %s WHERE idExamRequest = %s", (location_room, request_id))
    cursor.execute("INSERT INTO ExamDetails (detailUser, detailRole, detailExam) VALUES (%s, 'Proctor', %s)", (session['user_id'], request_id))
    cursor.close(); conn.close()
    return redirect(url_for('dashboard_page'))

#========== Exam Request Drop Route (Proctor Tab)==========#
# Proctors may need to "drop" a request in the event that something comes up.
# Dropped requests need to be handled so that they can be picked-up by someone else.
@app.route('/proctor/drop-request', methods=['POST'])
def proctor_drop_request():
    if 'user_id' not in session: 
        return redirect(url_for('login_page'))

    request_id = request.form.get('request_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Reverts the request back to a "claimable" state (removes location & proctor).
        cursor.execute("""
            UPDATE ExamRequest 
            SET statusID = 'Approved By Faculty (Initial)',
                ExamRequestcol = 'TBD by Proctor'
            WHERE idExamRequest = %s
        """, (request_id,))

        cursor.execute("""
            DELETE FROM ExamDetails 
            WHERE detailUser = %s 
              AND detailExam = %s 
              AND detailRole = 'Proctor'
        """, (session['user_id'], request_id))

        cursor.close()
        conn.close()
        return redirect(url_for('dashboard_page'))

    # Just in case!
    except Exception as e:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()
        return f"Proctor Resignation Processing Failure: {str(e)}", 500

#---------- Main Application Runner ----------#
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
