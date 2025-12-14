from flask import session, redirect, render_template, Flask, request, jsonify,flash, send_file, url_for
from flask_session import Session
import os
import pyodbc
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
from docx import Document
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import pdfkit
import fitz
from reportlab.lib import colors
from pdfrw import PdfReader, PdfWriter, PageMerge
import bcrypt
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from itsdangerous import SignatureExpired, URLSafeTimedSerializer



app = Flask(__name__)


custom_pdfs = []

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)


app.config["SESSION_TYPE"] = 'filesystem'
app.config["SESSION_PERMANENT"] = False
app.config['SESSION_COOKIE_NAME'] = 'my_custom_session'
app.config['SECRET_KEY'] = 'bdkfhjdfgdnjgiohijrogjeiougekjnkjndbgkvndkjbgkdfngjb'
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'gias_survey:'
app.config['SENDGRID_API_KEY'] = os.getenv('SENDGRID_API_KEY')

serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
Session(app)

conn_str = (
    r'DRIVER={SQL Server};'
    r'SERVER=LITERALLYME;'
    r'DATABASE=Survey;'
    r'trusted_connection = yes'
)
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()


@app.route('/health')
def health_check():
    return "Healthy", 200

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        
        if not email:  # Check if the email field is empty
            flash('Email is required!', 'danger')
            return redirect('/forgot_password')
        
        token = serializer.dumps(email, salt='password-reset-salt')
        
        # Generate the reset URL
        reset_url = url_for('reset_password', token=token, _external=True)
        
        # Send the reset email using SendGrid
        message = Mail(
            from_email=('unais.faheem@hyphenconsultancy.com'),
            to_emails=email,
            subject='Password Reset Request',
            html_content=f"""
            <html>
                <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                    <div style="background-color: #ffffff; padding: 20px; border-radius: 5px; max-width: 600px; margin: auto;">
                        <h2 style="color: #FF5F15;">Password Reset Request</h2>
                        <p style="color: #555555;">We received a request to reset your password. Please click the button below to proceed:</p>
                        <a href="{reset_url}" style="display: inline-block; padding: 10px 20px; color: #ffffff; background-color: #FF5F15; text-decoration: none; border-radius: 5px;">Reset Password</a>
                        <p style="color: #555555; margin-top: 20px;">If you did not request a password reset, please ignore this email.</p>
                        <p style="color: #555555;">Best regards,<br>Hyphen Consultancy</p>
                    </div>
                </body>
            </html> """
        )

        try:
            sg = SendGridAPIClient(app.config['SENDGRID_API_KEY'])
            response = sg.send(message)
            print(response.status_code)
            print(response.body)
            print(response.headers)
            flash('A password reset link has been sent to your email.', 'info')
        except Exception as e:
            flash(f'Error sending email: {str(e)}', 'danger')
            app.logger.error(f'Error sending email: {str(e)}')  # Log the error for debugging
            print(str(e))
            
        return redirect('/login')

    return render_template('forgot_password.html')



@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        # Validate the token (expires after 1 hour)
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except SignatureExpired:
        flash('The password reset link has expired.', 'danger')
        return redirect('/forgot_password')

    if request.method == 'POST':
        new_password = request.form.get('password')

        # Hash the new password using bcrypt (ensure it's in UTF-8 format for storage)
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())

        try:
            # Update the user's password in the database
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE Users SET hashed_password = ? WHERE Email = ?
                """, (hashed_password.decode('utf-8'), email))  # Convert hashed_password to a string
                conn.commit()
        except Exception as e:
            # Handle any potential database errors
            flash(f"An error occurred: {str(e)}", 'danger')
            return redirect('/forgot_password')
        # Flash success message and redirect to the login page
        flash('Your password has been successfully reset.', 'success')
        return redirect('/login')

    return render_template('reset_password.html', token=token)




def determine_next_category(current_category, current_question_index, questions_per_category):
    categories = list(questions_per_category.keys())
    current_index = categories.index(current_category)
    
    # If there's a next category, return it
    if current_index < len(categories) - 1:
        next_category = categories[current_index + 1]
        return next_category, 0  # Start with the first question of the next category
    
    # No more categories
    return None, None


@app.route("/autocomplete/countries", methods=["GET"])
def autocomplete_countries():
    query = request.args.get("q", "").lower().strip()
    if query:
        result = cursor.execute(
            "SELECT Name FROM Countries WHERE LOWER(Name) LIKE ? ORDER BY ID",
            ('%' + query + '%',)
        ).fetchall()
        countries = [r[0] for r in result]
        return jsonify(countries)
    return jsonify([])

@app.route("/autocomplete/industries", methods=["GET"])
def autocomplete_industries():
    query = request.args.get("q", "").lower().strip()
    if query:
        result = cursor.execute(
            "SELECT Name FROM Industries WHERE LOWER(Name) LIKE ? ORDER BY ID",
            ('%' + query + '%',)
        ).fetchall()
        industries = [r[0] for r in result]
        return jsonify(industries)
    return jsonify([])


@app.route("/start", methods=["POST", "GET"])
def start():
    session['category'] = 'Skills and Career Orientation'
    session['total_score'] = 0
    session['category_scores'] = {}

    if request.method == "POST":
        Email = request.form.get("Email")
        Password = request.form.get("Password")
        RePassword = request.form.get("RePassword")

        # Input validation
        if not Email:
            flash("You have to enter an Email")
            return render_template("start.html")
        elif not Password:
            flash("You have to enter a Password")
            return render_template("start.html")
        elif not RePassword:
            flash("You have to Re-Enter Your Password")
            return render_template("start.html")

        if Password != RePassword:
            flash("Passwords must match")
            return render_template("start.html")

        # Check for password quality
        if len(Password) < 8:  # Example condition for password quality
            flash("Your Password is too weak")
            return render_template("start.html")

        # Hash the password (only after password validation)
        hashed_password = bcrypt.hashpw(Password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Check for unique email
        existing_email = cursor.execute("SELECT email FROM Users WHERE email = ?", (Email,)).fetchone()
        if existing_email:
            flash("Email must be unique")
            return render_template("start.html")

        try:
            # Insert new user into the database
            cursor.execute("INSERT INTO Users (Email, hashed_password) VALUES (?, ?)", (Email, hashed_password))

            # Fetch the newly created user's ID
            rows = cursor.execute("SELECT Id FROM Users WHERE Email = ?", (Email,)).fetchall()
            if rows:
                session["id"] = rows[0][0]  # Save the user ID to the session
            else:
                return "Failed to retrieve user ID after registration."

            conn.commit()  # Commit changes to the database
            return redirect("/questions")
        except Exception as e:
            conn.rollback()  # Rollback on error
            app.logger.error(f"An error occurred: {str(e)}")
            return f"An error occurred: {str(e)}"

    return render_template("start.html")




@app.route("/register", methods=["GET", "POST"])
def register():
    # Check if the result type (free or premium) is passed as a query parameter
    result_type = request.args.get("result")
    
    # Store the result type in session if it's passed as a query parameter
    if result_type:
        session['result_type'] = result_type
    
    
    
    if request.method == "POST":
        user_id = session.get("id")
        # Fetch valid countries and industries from the database
        try:
            country = [c[0].lower().strip() for c in cursor.execute("SELECT Name FROM Countries ORDER BY ID").fetchall()]
        except Exception as e:
            print(f"Error fetching countries or industries: {e}")
            return "There was an error fetching valid countries or industries."

        # Retrieve form data
        Name = request.form.get("Name")
        Age = request.form.get("Age")
        Qualification = request.form.get("Qualification")
        Job = request.form.get("Job")
        Country = request.form.get("Country").strip().lower()


        form_data = {
            "Name": Name,
            "Country": Country,
            "Age" : Age,
            "Qualification" : Qualification,
            "Job": Job,

        }

        # Input validation
        if not Name:
            flash("Enter a Name")
        elif not Country:
            flash("Enter a Country")
        elif not Age:
            flash("Enter Your Age")
        elif not Qualification:
            flash("Select a Qualification")
        elif Country not in country:
            flash("Invalid Country")
        elif not Job:
            flash("Choose an Option"),
        else:
            # Check if user_id is present and update or insert accordingly
            try:
                if user_id:  # If user_id is available, update the existing user
                    cursor.execute(
                        """UPDATE Users
                        SET Name = ?, Country = ?, Age = ?, Qualification = ?, Job = ?
                        WHERE Id = ?""",
                        (Name, Country, Age, Qualification ,Job, user_id)
                    )
                else:  # If user_id is not available, insert a new user
                    cursor.execute(
                        """INSERT INTO Users (Name, Country, Age, Qualification, Job)
                        VALUES(?,?,?,?,?,?)""",
                        (Name, Country, Age, Qualification, Job)
                    )

                conn.commit()

                # Redirect to different results pages based on the result type stored in the session
                result_type = session.get('result_type', 'free')  # Default to 'free' if not found
                if result_type == 'free':
                    return redirect("/thankyou_freeresults.html")
                elif result_type == 'premium':
                    return redirect("/thankyou_premiumresults.html")
            except pyodbc.ProgrammingError as e:
                print(f"Database Error: {e}")
                return "There was an error with the database operation."
            except Exception as e:
                print(f"Unexpected Error: {e}")
                return "An unexpected error occurred."

        # Render the registration page with error messages
        return render_template("register.html", **form_data)
    
    # Render the registration page for GET request
    return render_template("register.html")





@app.route("/login", methods=["POST", "GET"])
def login():
    # Clear session if redirecting to login
    user_id = session.get("id")

    if request.method == "POST":
        Email = request.form.get("Email")
        Password = request.form.get("Password")

        # Validate input
        if not Email:
            flash("Enter an Email Address")
            print("No email provided")
            return render_template("login.html", Email="")
        elif not Password:
            flash("Enter a Password")
            print("No password provided")
            return render_template("login.html", Email=Email)

        # Fetch the user from the database
        cursor.execute("SELECT Id, hashed_password, Last_Page FROM Users WHERE Email = ?", (Email,))
        row = cursor.fetchone()

        # Check if user exists
        if row is None:
            flash("Invalid Email Address")
            print(f"No user found with email: {Email}")
            return render_template("login.html", Email=Email)

        # Unpack ID, hashed password, and Last_Page status
        user_id, hashed_password, last_page = row
        print(f"User found: {user_id}, hashed_password: {hashed_password}, last_page: {last_page}")

        # Check if hashed_password is valid
        if not hashed_password:
            flash("Error: password not found.")
            print("Hashed password not found")
            return render_template("login.html", Email=Email)

        # Check if the provided password matches the hashed password
        if bcrypt.checkpw(Password.encode('utf-8'), hashed_password.encode('utf-8')):
            session["id"] = user_id  # Store the integer user ID in session
            print(f"Login successful for user {user_id}")

            # Redirect based on Last_Page (whether they completed the questionnaire)
            if last_page == 0:
                print(f"User {user_id} has completed the questionnaire, redirecting to /freeresults")
                return redirect("/thankyoufreeresults")
            else:
                print(f"User {user_id} has not completed the questionnaire, redirecting to /questions")
                return redirect("/questions")  # Redirect to questions page
        else:
            flash("Invalid Password")
            print("Password does not match")
            return render_template("login.html", Email=Email)

    # Render login page for GET request
    print("Rendering login page")
    return render_template("login.html", Email="", Password="")







@app.route("/")
def index():
    return render_template("index.html")



@app.route("/questions", methods=["GET", "POST"])
def questions():
    categories = {
        'Skills and Career Orientation': {'A': 4, 'B': 3, 'C': 2, 'D': 1},
        'Soft Skills': {'A': 4, 'B': 3, 'C': 2, 'D': 1},
        'Professional Expectations': {'A': 4, 'B': 3, 'C': 2, 'D': 1},
        'Physchological Profile': {'A': 4, 'B': 3, 'C': 2, 'D': 1},
    }
    
    questions_per_category = {
        'Skills and Career Orientation': 5,
        'Soft Skills': 5,
        'Professional Expectations': 5,
        'Physchological Profile': 5,
    }
    questions_data = {
    'Skills and Career Orientation': [
        {'id': 'q1', 'text': 'Question 1: Which field do you feel most confident working in?', 'options': [
            {'label': 'Coding/Programming', 'value': 'A'},
            {'label': 'Design (UI/UX, Graphics)', 'value': 'B'},
            {'label': 'Business/Management', 'value': 'C'},
            {'label': 'Marketing/Content Creation', 'value': 'D'},
        ]},
        {'id': 'q2', 'text': 'Question 2: How comfortable are you with learning new software or technical tools?', 'options': [
            {'label': 'Very comfortable, I enjoy exploring new tech', 'value': 'A'},
            {'label': 'Comfortable, I can learn when needed', 'value': 'B'},
            {'label': 'Somewhat comfortable, prefer familiar tools', 'value': 'C'},
            {'label': 'Not very comfortable, I prefer non-technical work', 'value': 'D'},
        ]},
        {'id': 'q3', 'text': 'Question 3: What is your dominant strength?', 'options': [
            {'label': 'Solving logical problems & analyzing data', 'value': 'A'},
            {'label': 'Building/creating things (products, systems)', 'value': 'B'},
            {'label': 'Dealing with people & communication', 'value': 'C'},
            {'label': 'Creative thinking & ideation', 'value': 'D'},
        ]},
        {'id': 'q4', 'text': 'Question 4: How frequently do you take initiative in projects or tasks?', 'options': [
            {'label': 'Always – I lead and drive projects forward', 'value': 'A'},
            {'label': 'Often – I volunteer when I see opportunities', 'value': 'B'},
            {'label': 'Sometimes – when asked or necessary', 'value': 'C'},
            {'label': 'Rarely – I prefer following established plans', 'value': 'D'},
        ]},
        {'id': 'q5', 'text': 'Question 5: What is your ideal working state?', 'options': [
            {'label': 'Behind a computer, coding/analyzing', 'value': 'A'},
            {'label': 'In a meeting room, collaborating on projects', 'value': 'B'},
            {'label': 'Meeting clients, presenting solutions', 'value': 'C'},
            {'label': 'On-site, hands-on field work', 'value': 'D'},
        ]},
    ],

    'Soft Skills': [
        {'id': 'q1', 'text': 'Question 6: How would you react if a coworker disagrees with your idea during a meeting?', 'options': [
            {'label': 'Present data/logic to support my position', 'value': 'A'},
            {'label': 'Listen and find a middle ground solution', 'value': 'B'},
            {'label': 'Discuss openly and ask for team input', 'value': 'C'},
            {'label': 'Defer to their experience or seniority', 'value': 'D'},
        ]},
        {'id': 'q2', 'text': 'Question 7: What would you do if you have multiple tasks to finish in limited time?', 'options': [
            {'label': 'Prioritize by impact, use productivity systems', 'value': 'A'},
            {'label': 'Break down tasks and tackle systematically', 'value': 'B'},
            {'label': 'Ask for help or delegate where possible', 'value': 'C'},
            {'label': 'Work on what feels most urgent first', 'value': 'D'},
        ]},
        {'id': 'q3', 'text': 'Question 8: If a team member is not completing their part of the work, how do you handle it?', 'options': [
            {'label': 'Address it directly and find the root cause', 'value': 'A'},
            {'label': 'Offer help and see if they need support', 'value': 'B'},
            {'label': 'Discuss with the team to redistribute work', 'value': 'C'},
            {'label': 'Report to supervisor or wait for instructions', 'value': 'D'},
        ]},
        {'id': 'q4', 'text': 'Question 9: How do you usually deal with sudden changes in plans or deadlines?', 'options': [
            {'label': 'Quickly reassess and create a new action plan', 'value': 'A'},
            {'label': 'Stay calm and adapt my approach', 'value': 'B'},
            {'label': 'Consult with team on how to adjust', 'value': 'C'},
            {'label': 'Feel stressed but try to manage', 'value': 'D'},
        ]},
        {'id': 'q5', 'text': 'Question 10: If you make a mistake at work, what is your first response?', 'options': [
            {'label': 'Analyze what went wrong and fix it immediately', 'value': 'A'},
            {'label': 'Inform relevant people and propose solutions', 'value': 'B'},
            {'label': 'Apologize and ask for guidance', 'value': 'C'},
            {'label': 'Feel bad and try to avoid similar situations', 'value': 'D'},
        ]},
    ],

    'Professional Expectations': [
        {'id': 'q1', 'text': 'Question 11: What salary package are you looking for in your first job?', 'options': [
            {'label': 'PKR 80,000+ (High expectations)', 'value': 'A'},
            {'label': 'PKR 60,000–80,000', 'value': 'B'},
            {'label': 'PKR 40,000–60,000', 'value': 'C'},
            {'label': 'PKR 25,000–40,000', 'value': 'D'},
        ]},
        {'id': 'q2', 'text': 'Question 12: What job type do you prefer?', 'options': [
            {'label': 'Remote job', 'value': 'A'},
            {'label': 'Hybrid job', 'value': 'B'},
            {'label': 'On-site job', 'value': 'C'},
            {'label': 'Flexible / no strong preference', 'value': 'D'},
        ]},
        {'id': 'q3', 'text': 'Question 13: How many weekly working hours do you feel comfortable with?', 'options': [
            {'label': '45+ hours', 'value': 'A'},
            {'label': '40–45 hours', 'value': 'B'},
            {'label': '35–40 hours', 'value': 'C'},
            {'label': 'Less than 35 hours', 'value': 'D'},
        ]},
        {'id': 'q4', 'text': 'Question 14: Do you want a job with:', 'options': [
            {'label': 'Strong growth opportunities', 'value': 'A'},
            {'label': 'Both growth and stability', 'value': 'B'},
            {'label': 'Stable, predictable role', 'value': 'C'},
            {'label': 'Fresh experience to start', 'value': 'D'},
        ]},
        {'id': 'q5', 'text': 'Question 15: What is most important in terms of benefits?', 'options': [
            {'label': 'Performance bonuses & stock options', 'value': 'A'},
            {'label': 'Healthcare & insurance', 'value': 'B'},
            {'label': 'Paid leaves & work-life balance', 'value': 'C'},
            {'label': 'Basic benefits are fine', 'value': 'D'},
        ]},
    ],

    'Physchological Profile': [
        {'id': 'q1', 'text': 'Question 16: What is your favorite color?', 'options': [
            {'label': 'Blue/Black', 'value': 'A'},
            {'label': 'Green/Purple', 'value': 'B'},
            {'label': 'Red/Orange', 'value': 'C'},
            {'label': 'Yellow/Pink', 'value': 'D'},
        ]},
        {'id': 'q2', 'text': 'Question 17: First thing that comes to mind when your boss asks for an answer?', 'options': [
            {'label': 'Think about logic/data first', 'value': 'A'},
            {'label': 'Provide a structured response', 'value': 'B'},
            {'label': 'Check what others think', 'value': 'C'},
            {'label': 'Hope I understood correctly', 'value': 'D'},
        ]},
        {'id': 'q3', 'text': 'Question 18: What is your ideal work environment?', 'options': [
            {'label': 'Quiet, focused space', 'value': 'A'},
            {'label': 'Collaborative with quiet areas', 'value': 'B'},
            {'label': 'Lively office', 'value': 'C'},
            {'label': 'Flexible, casual environment', 'value': 'D'},
        ]},
        {'id': 'q4', 'text': 'Question 19: Which emotion do you experience most during work?', 'options': [
            {'label': 'Focused determination / flow state', 'value': 'A'},
            {'label': 'Calm confidence', 'value': 'B'},
            {'label': 'Excitement & energy', 'value': 'C'},
            {'label': 'Mix of stress and satisfaction', 'value': 'D'},
        ]},
        {'id': 'q5', 'text': 'Question 20: What do you rely on while making decisions?', 'options': [
            {'label': 'Logic, data, systematic analysis', 'value': 'A'},
            {'label': 'Logic + experience', 'value': 'B'},
            {'label': 'Others’ advice and consensus', 'value': 'C'},
            {'label': 'Instinct and gut feeling', 'value': 'D'},
        ]},
    ],
}

    if request.method == "POST":
        user_id = session.get("id")
        if not user_id:
            return "User not logged in or session expired", 403  # Handle case where user is not logged in

        current_category = session.get("category", "Skills and Career Orientation")
        questions = questions_data.get(current_category, [])
        user_answers = request.form.to_dict()
        total_score = session.get("total_score", 0)
        category_scores = session.get('category_scores', {})

        # Calculate scores
        for question, option in user_answers.items():
            score = categories[current_category].get(option, 0)
            category_scores[current_category] = category_scores.get(current_category, 0) + score

        session['category_scores'] = category_scores
        total_score = sum(category_scores.values())
        session['total_score'] = total_score

        # Insert user's answers into the Questions table
        for question, option in user_answers.items():
            cursor.execute(
                """INSERT INTO Questions(Question, Answer, Category) VALUES (?,?,?)""",
                (question, option, current_category)
            )
            conn.commit()

        # Update or insert the category score into the UserScores table
        cursor.execute(
            """
            MERGE INTO UserScores AS target
            USING (VALUES (?, ?, ?)) AS source (user_id, category, Score)
            ON target.user_id = source.user_id AND target.category = source.category
            WHEN MATCHED THEN 
                UPDATE SET Score = source.Score
            WHEN NOT MATCHED THEN 
                INSERT (user_id, category, Score) 
                VALUES (source.user_id, source.category, source.Score);
            """, (user_id, current_category, category_scores[current_category])
        )
        conn.commit()

        # Update total score for the user in Users table
        cursor.execute(
            """UPDATE Users SET Score = ? WHERE Id = ?""",
            (total_score, user_id)
        )
        conn.commit()

        # Determine next category (if applicable)
        next_category, next_question = determine_next_category(current_category, 1, questions_per_category)

        if next_category:
            session['category'] = next_category
            return redirect("/questions")
        else:
            # Mark the questionnaire as completed in the Users table (Last_Page = 1)
            cursor.execute(
                """UPDATE Users SET Last_Page = 0 WHERE Id = ?""",
                (user_id,)
            )
            conn.commit()
            return redirect("/wait")

    else:
        current_category = session.get("category", "Values")
        questions = questions_data.get(current_category, [])
        return render_template("questions.html", current_category=current_category, questions=questions)



    
@app.route("/thankyoufreeresults")
@app.route("/thankyoupremiumresults")
def thankyou():
    top_3_roles = []
    role_weights = {
        "Technology and Developement" : {
            "Software Developer" : {
                "Skills and Career Orientation": 0.40,
                "Soft Skills": 0.15,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.20,
            },
            "Frontend Developer": {
                "Skills and Career Orientation": 0.35,
                "Soft Skills": 0.20,
                "Professional Expectations": 0.20,
                "Physchological Profile": 0.25,
            },
            "Backend Developer": {
                "Skills and Career Orientation": 0.45,
                "Soft Skills": 0.10,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.20,
            },
            "Mobile App Developer": {
                "Skills and Career Orientation": 0.35,
                "Soft Skills": 0.20,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.20,
            },
            "Data Analyst": {
                "Skills and Career Orientation": 0.45,
                "Soft Skills": 0.10,
                "Professional Expectations": 0.20,
                "Physchological Profile": 0.25,
            },
            "Data Scientist": {
                "Skills and Career Orientation": 0.50,
                "Soft Skills": 0.10,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.15,
            },
            "DevOps Engineer": {
                "Skills and Career Orientation": 0.40,
                "Soft Skills": 0.15,
                "Professional Expectations": 0.30,
                "Physchological Profile": 0.15,
            },
            "QA/Testing Engineer": {
                "Skills and Career Orientation": 0.35,
                "Soft Skills": 0.20,
                "Professional Expectations": 0.15,
                "Physchological Profile": 0.30,
            },
            "Database Administrator": {
                "Skills and Career Orientation": 0.45,
                "Soft Skills": 0.10,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.20,
            },
            "Cloud Solutions Architect": {
                "Skills and Career Orientation": 0.40,
                "Soft Skills": 0.20,
                "Professional Expectations": 0.30,
                "Physchological Profile": 0.10,
            },
        },
        "Product and Design": {
            "Product Manager": {
                "Skills and Career Orientation": 0.30,
                "Soft Skills": 0.30,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.15,
            },
            "UI/UX Designer": {
                "Skills and Career Orientation": 0.35,
                "Soft Skills": 0.25,
                "Professional Expectations": 0.15,
                "Physchological Profile": 0.25,
            },
            "Product Designer": {
                "Skills and Career Orientation": 0.40,
                "Soft Skills": 0.20,
                "Professional Expectations": 0.15,
                "Physchological Profile": 0.25,
            },
            "UX Researcher": {
                "Skills and Career Orientation": 0.35,
                "Soft Skills": 0.20,
                "Professional Expectations": 0.15,
                "Physchological Profile": 0.30,
            },
            "Graphic Designer":{
                "Skills and Career Orientation": 0.30,
                "Soft Skills": 0.15,
                "Professional Expectations": 0.10,
                "Physchological Profile": 0.45,
            },
            "Motion Graphic Designer": {
                "Skills and Career Orientation": 0.35,
                "Soft Skills": 0.10,
                "Professional Expectations": 0.15,
                "Physchological Profile": 0.40,
            },
            "Game Designer": {
                "Skills and Career Orientation": 0.35,
                "Soft Skills": 0.20,
                "Professional Expectations": 0.15,
                "Physchological Profile": 0.30,
            },
            "3D Designer/Animator": {
                "Skills and Career Orientation": 0.40,
                "Soft Skills": 0.10,
                "Professional Expectations": 0.15,
                "Physchological Profile": 0.35,
            },
        },
        "Business & Strategy": {
            "Business Analyst": {
                "Skills and Career Orientation": 0.40,
                "Soft Skills": 0.20,
                "Professional Expectations": 0.20,
                "Physchological Profile": 0.20,
            },
            "Management Consultant": {
                "Skills and Career Orientation": 0.30,
                "Soft Skills": 0.30,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.15,
            },
            "Project Manager": {
                "Skills and Career Orientation": 0.30,
                "Soft Skills": 0.35,
                "Professional Expectations": 0.20,
                "Physchological Profile": 0.15,
            },
            "Operations Manager": {
                "Skills and Career Orientation": 0.35,
                "Soft Skills": 0.20,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.20,
            },
            "Financial Analyst": {
                "Skills and Career Orientation": 0.45,
                "Soft Skills": 0.10,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.20,
            },
            "Business Development Executive": {
                "Skills and Career Orientation": 0.25,
                "Soft Skills": 0.40,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.10,
            },
            "Strategy Analyst": {
                "Skills and Career Orientation": 0.45,
                "Soft Skills": 0.15,
                "Professional Expectations": 0.20,
                "Physchological Profile": 0.20,
            },
            "Market Research Analyst": {
                "Skills and Career Orientation": 0.40,
                "Soft Skills": 0.15,
                "Professional Expectations": 0.15,
                "Physchological Profile": 0.30,
            },
        },
        "Marketing & Sales": {
            "Digital Marketing Specialist": {
                "Skills and Career Orientation": 0.25,
                "Soft Skills": 0.35,
                "Professional Expectations": 0.20,
                "Physchological Profile": 0.20,
            },
            "Social Media Manager": {
                "Skills and Career Orientation": 0.20,
                "Soft Skills": 0.40,
                "Professional Expectations": 0.20,
                "Physchological Profile": 0.20,
            },
            "Content Marketing Manager": {
                "Skills and Career Orientation": 0.20,
                "Soft Skills": 0.35,
                "Professional Expectations": 0.20,
                "Physchological Profile": 0.25,
            },
            "SEO/SEM Specialist": {
                "Skills and Career Orientation": 0.30,
                "Soft Skills": 0.30,
                "Professional Expectations": 0.20,
                "Physchological Profile": 0.20,
            },
            "Brand Manager": {
                "Skills and Career Orientation": 0.25,
                "Soft Skills": 0.35,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.15,
            },
            "Sales Executive": {
                "Skills and Career Orientation": 0.20,
                "Soft Skills": 0.40,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.15,
            },
            "Account Manager": {
                "Skills and Career Orientation": 0.20,
                "Soft Skills": 0.40,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.15,
            },
            "Customer Success Manager": {
                "Skills and Career Orientation": 0.20,
                "Soft Skills": 0.40,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.15,
            },
            "Public Relations Specialist": {
                "Skills and Career Orientation": 0.15,
                "Soft Skills": 0.45,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.15,
            },
            "Growth Hacker": {
                "Skills and Career Orientation": 0.30,
                "Soft Skills": 0.30,
                "Professional Expectations": 0.20,
                "Physchological Profile": 0.20,
            },
        },
        "Support & Operations": {
            "HR Specialist/Coordinator": {
                "Skills and Career Orientation": 0.20,
                "Soft Skills": 0.40,
                "Professional Expectations": 0.20,
                "Physchological Profile": 0.20,
            },
            "Administrative Manager": {
                "Skills and Career Orientation": 0.25,
                "Soft Skills": 0.35,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.15,
            },
            "Office Manager": {
                "Skills and Career Orientation": 0.25,
                "Soft Skills": 0.35,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.15,
            },
            "Customer Support Specialist": {
                "Skills and Career Orientation": 0.20,
                "Soft Skills": 0.40,
                "Professional Expectations": 0.20,
                "Physchological Profile": 0.20,
            },
            "Content Writer/Creator": {
                "Skills and Career Orientation": 0.25,
                "Soft Skills": 0.35,
                "Professional Expectations": 0.15,
                "Physchological Profile": 0.25,
            },
            "Executive Assistant": {
                "Skills and Career Orientation": 0.20,
                "Soft Skills": 0.40,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.15,
            },
            "Operations Coordinator": {
                "Skills and Career Orientation": 0.25,
                "Soft Skills": 0.35,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.15,
            },
            "Talent Acquisition Specialist": {
                "Skills and Career Orientation": 0.20,
                "Soft Skills": 0.40,
                "Professional Expectations": 0.25,
                "Physchological Profile": 0.15,
            }
        }

    }
    total_cat_score = {
        'Skills and Career Orientation': {'total': 20},
        'Soft Skills': {'total': 20},
        'Professional Expectations': {'total': 20},
        'Physchological Profile': {'total': 20},
    }
    
    if "id" not in session:
        return redirect("/register")

    user_id = session["id"]

    # Retrieve total score
    cursor.execute("""SELECT Score FROM Users WHERE Id = ?""", (user_id,))
    row = cursor.fetchone()
    total_score = row[0] if row else None


    # Retrieve category-wise scores
    cursor.execute("""SELECT category, score FROM UserScores WHERE user_id = ?""", (user_id,))
    category_scores = cursor.fetchall()

    scores_by_category = {row[0]: row[1] for row in category_scores}
    skills_score = scores_by_category.get('Skills and Career Orientation', 0) / total_cat_score['Skills and Career Orientation']['total']
    soft_skills_score = scores_by_category.get('Soft Skills', 0) / total_cat_score['Soft Skills']['total']
    professional_score = scores_by_category.get('Professional Expectations', 0) / total_cat_score['Professional Expectations']['total']
    psych_score = scores_by_category.get('Physchological Profile', 0) / total_cat_score['Physchological Profile']['total']


    


    broader_category_scores = {}
    for category_name, roles in role_weights.items():
        temp_scores = []
        for role, weights in roles.items():
            score = (
                skills_score * weights["Skills and Career Orientation"] +
                soft_skills_score * weights["Soft Skills"] +
                professional_score * weights["Professional Expectations"] +
                psych_score * weights["Physchological Profile"]
            )
            temp_scores.append(score)
        # Average over all roles in the category
        broader_category_scores[category_name] = sum(temp_scores) / len(temp_scores)

    # Step 2: Determine best broader category
    best_broader_category = max(broader_category_scores, key=broader_category_scores.get)
    

        
    role_scores = {}
    for role, weights in role_weights[best_broader_category].items():
        role_scores[role] = (
            skills_score * weights["Skills and Career Orientation"] +
            soft_skills_score * weights["Soft Skills"] +
            professional_score * weights["Professional Expectations"] +
            psych_score * weights["Physchological Profile"]
        )

    # Step 4: Pick top 3 roles
    best_weights = role_weights[best_broader_category]

    top_3_roles = sorted(
        role_scores.items(),
        key=lambda x: (
            x[1],  # main weighted score
            # tie-breakers: multiply each category score by the role's weights
            scores_by_category.get('Skills and Career Orientation', 0) * role_weights[best_broader_category][x[0]]["Skills and Career Orientation"],
            scores_by_category.get('Soft Skills', 0) * role_weights[best_broader_category][x[0]]["Soft Skills"],
            scores_by_category.get('Professional Expectations', 0) * role_weights[best_broader_category][x[0]]["Professional Expectations"],
            scores_by_category.get('Physchological Profile', 0) * role_weights[best_broader_category][x[0]]["Physchological Profile"]
        ),
        reverse=True
    )[:3]



    # Determine the template based on the route
    if request.path == "/thankyoufreeresults":
        template_name = "thankyou_freeresults.html"
    else:
        template_name = "thankyou_premiumresults.html"

    return render_template(template_name, total_score=total_score, category_scores=scores_by_category, total_cat_score=total_cat_score, broader_category=best_broader_category,
        top_3_roles=top_3_roles)

@app.route("/thankyou_freeresults.html")
def redirect_free():
    return redirect("/thankyoufreeresults")

@app.route("/thankyou_premiumresults.html")
def redirect_premium():
    return redirect("/thankyoupremiumresults")

@app.route("/choice")
def choice():
    return render_template("choice.html")

@app.route("/wait")
def wait():
    return render_template("wait.html")

@app.route("/premium")
def premium():
    return render_template("premium.html")


@app.route("/download-pdf", methods=["POST"])
def download_pdf():
    selected_documents = []
    user_id = session.get("id")
    if not user_id:
        return "User not logged in"

    # Fetch user's name from the database
    cursor.execute("SELECT Name FROM Users WHERE id = ?", (user_id,))
    user_name_row = cursor.fetchone()
    user_name = user_name_row[0] if user_name_row else "User"

    # Load the base document (PDF) that contains the placeholder 'xxxx' for the name
    selected_documents.append(r'PDF Docs/Document 13.pdf')

    cursor.execute("SELECT * FROM UserScores WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()

    document_list = [
        r'PDF Docs/Document 1.pdf', r'PDF Docs/Document 2.pdf', r'PDF Docs/Document 3.pdf',
        r'PDF Docs/Document 4.pdf', r'PDF Docs/Document 5.pdf', r'PDF Docs/Document 6.pdf',
        r'PDF Docs/Document 7.pdf', r'PDF Docs/Document 8.pdf', r'PDF Docs/Document 9.pdf',
        r'PDF Docs/Document 10.pdf', r'PDF Docs/Document 11.pdf', r'PDF Docs/Document 12.pdf'
    ]

    pdf_files = []

    # Modify and merge the first PDF (Document 13) to replace 'xxxx' with the user's name
    if selected_documents:
        # Open the base PDF (Document 13) using PyMuPDF
        pdf_document = fitz.open(selected_documents[0])

        # Iterate through the pages
        for page in pdf_document:
            # Search for the placeholder text 'xxxx' and replace it
            text_instances = page.search_for('xxxx')
            for inst in text_instances:
                # Replace the text at the found location
                page.insert_text(inst[:2], user_name, fontsize=11, color=(0, 0, 0))  # Adjust fontsize and color as needed

        # Save the modified PDF to a BytesIO object
        pdf_bytes = BytesIO()
        pdf_document.save(pdf_bytes)
        pdf_bytes.seek(0)
        pdf_files.append(pdf_bytes)

        # Close the PDF document
        pdf_document.close()

        # Remove the first document so it's not added again later
        selected_documents.pop(0)

    # Now add the custom PDF sections based on UserScores
    for row in rows:
        if row[2] == "Values":
            if row[3] <= 6:
                selected_documents.append(document_list[0])
            elif row[3] > 6 and row[3] <= 15:
                selected_documents.append(document_list[1])
            elif row[3] > 15 and row[3] <= 20:
                selected_documents.append(document_list[2])
        elif row[2] == "Methodology":
            if row[3] <= 13:
                selected_documents.append(document_list[3])
            elif row[3] > 13 and row[3] <= 33:
                selected_documents.append(document_list[4])
            elif row[3] > 33 and row[3] <= 44:
                selected_documents.append(document_list[5])
        elif row[2] == "Stakeholder Management":
            if row[3] <= 7:
                selected_documents.append(document_list[6])
            elif 7 < row[3] <= 18:
                selected_documents.append(document_list[7])
            elif 18 < row[3] <= 24:
                selected_documents.append(document_list[8])
        elif row[2] == "Resource Management":
            if row[3] < 11:
                selected_documents.append(document_list[9])
            elif 11 < row[3] <= 27:
                selected_documents.append(document_list[10])
            elif 27 < row[3] <= 36:
                selected_documents.append(document_list[11])

    # Add selected documents to the merge list
    for doc in selected_documents:
        with open(doc, "rb") as pdf_file:
            pdf_files.append(BytesIO(pdf_file.read()))

    # Merging all PDFs into one
    merger = PdfMerger()
    for pdf in pdf_files:
        merger.append(pdf)

    # Final output to the user
    final_pdf = BytesIO()
    merger.write(final_pdf)
    merger.close()

    final_pdf.seek(0)
    return send_file(final_pdf, as_attachment=True, download_name='Assessment_Report.pdf', mimetype='application/pdf')

