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
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
from flask_mail import Mail, Message




app = Flask(__name__)

mail = Mail(app)

custom_pdfs = []

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)


app.config["SESSION_TYPE"] = 'filesystem'
app.config["SESSION_PERMANENT"] = False
app.config['SESSION_COOKIE_NAME'] = 'my_custom_session'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key')
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'hyphen_survey:'
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = os.getenv('MAIL_PORT')
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() in ['true', '1', 't']
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')
app.config['PREFERRED_URL_SCHEME'] = os.getenv('PREFERRED_URL_SCHEME')

Session(app)


conn_str = os.getenv('AZURE_SQL_CONNECTION_STRING')
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()
serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])


@app.route('/health')
def health_check():
    return "Healthy", 200

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        token = serializer.dumps(email, salt='password-reset-salt')
        
        # Generate the reset URL
        reset_url = url_for('reset_password', token=token, _external=True)
        
        # Send the reset email
        msg = Message('Password Reset Request', recipients=[email])
        msg.body = f"Please click the link to reset your password: {reset_url}"
        
        try:
            mail.send(msg)
            flash('A password reset link has been sent to your email.', 'info')
        except Exception as e:
            flash(f'Error sending email: {str(e)}', 'danger')
        
        return redirect('/login')

    return render_template('forgot_password.html')


@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        # Validate the token (expires after 1 hour)
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except SignatureExpired:
        flash('The password reset link has expired.', 'danger')
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        new_password = request.form['password']
        
        # Hash the new password using bcrypt
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
        
        # Update the user's password in the database
        with cursor:
            cursor.execute("""
                UPDATE Users SET hashed_password = ? WHERE Email = ?
            """, (hashed_password, email))
            cursor.commit()
        
        flash('Your password has been successfully reset.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password.html')



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
    session['category'] = 'Values'
    session['total_score'] = 0
    session['category_scores'] = {}

    if request.method == "POST":
        Email = request.form.get("Email")
        Password = request.form.get("Password")
        re_password = request.form.get("re_password")
        hashed_password = bcrypt.hashpw(Password.encode('utf-8'), bcrypt.gensalt())
        hashed_re_password = bcrypt.hashpw(re_password.encode('utf-8'), bcrypt.gensalt())
        
        

        # Input validation
        if not Email:
            flash("You have to enter an Email")
            return render_template("start.html")
        elif not Password:
            flash("You have to enter a Password")
            return render_template("start.html")
        elif not re_password:
            flash("You have to Re-Enter Your Password")
            return render_template("start.html")
        elif Password != re_password:
            flash("Both passwords have to match")
            return render_template("start.html")

        # Check for unique email
        existing_email = cursor.execute("SELECT email FROM Users WHERE email = ?", (Email,)).fetchone()
        if existing_email:
            flash("Email must be unique")
            return render_template("start.html")

        # Check for password quality
        if len(Password) < 8:  # Example condition for password quality
            flash("Your Password is too weak")
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
            industry = [i[0].lower().strip() for i in cursor.execute("SELECT Name FROM industries ORDER BY id").fetchall()]
        except Exception as e:
            print(f"Error fetching countries or industries: {e}")
            return "There was an error fetching valid countries or industries."

        # Retrieve form data
        Name = request.form.get("Name")
        Internal_Audit = request.form.get("Internal_Audit")
        Company_Size = request.form.get("Company_Size")
        Using_Solution = request.form.get("Using_Solution")
        Industry = request.form.get("Industry").strip().lower()
        Country = request.form.get("Country").strip().lower()

        form_data = {
            "Name": Name,
            "Industry": Industry,
            "Country": Country,
            "Internal_Audit": Internal_Audit,
            "Company_Size": Company_Size,
            "Using_Solution": Using_Solution,
        }

        # Input validation
        if not Name:
            flash("Enter a Name")
        elif not Industry:
            flash("Enter an Industry")
        elif not Country:
            flash("Enter a Country")
        elif not Internal_Audit:
            flash("Enter the number of members in the IA department")
        elif not Company_Size:
            flash("Enter company size")
        elif not Using_Solution:
            flash("Mention whether using a solution or not")
        elif Industry not in industry:
            flash("Invalid Industry")
        elif Country not in country:
            flash("Invalid Country")
        else:
            # Check if user_id is present and update or insert accordingly
            try:
                if user_id:  # If user_id is available, update the existing user
                    cursor.execute(
                        """UPDATE Users
                        SET Name = ?, Industry = ?, Country = ?, Internal_Audit = ?, Company_Size = ?, Using_Solution = ?
                        WHERE Id = ?""",
                        (Name, Industry, Country, Internal_Audit, Company_Size, Using_Solution, user_id)
                    )
                else:  # If user_id is not available, insert a new user
                    cursor.execute(
                        """INSERT INTO Users (Name, Industry, Country, Internal_Audit, Company_Size, Using_Solution)
                        VALUES(?,?,?,?,?,?)""",
                        (Name, Industry, Country, Internal_Audit, Company_Size, Using_Solution)
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
    if user_id:
        return redirect("/questions")  # Redirect if already logged in

    if request.method == "POST":
        Email = request.form.get("Email")
        Password = request.form.get("Password")

        # Validate input
        if not Email:
            flash("Enter an Email Address")
            return render_template("login.html", Email = "")
        elif not Password:
            flash("Enter an Email Address")
            return render_template("login.html", Password = "")

        # Fetch the user from the database
        cursor.execute("SELECT Id, Hashed_password FROM Users WHERE Email = ?", (Email,))
        row = cursor.fetchone()

        # Check if user exists
        if row:
            user_id, hashed_password = row  # Unpack ID and hashed password

            # Check if the provided password matches the hashed password
            if bcrypt.checkpw(Password.encode('utf-8'), hashed_password.encode('utf-8')):
                session["Id"] = user_id  # Store the integer user ID in session
                return redirect("/questions")  # Redirect to questions page
            else:
                flash("Invalid Password")
        else:
            flash("Invalid Email Address")
    else:
        return render_template("login.html", Email="", Password="")




@app.route("/")
def index():
    return render_template("index.html")



@app.route("/questions", methods=["GET", "POST"])
def questions():
    categories = {
        'Values': {'A': 0, 'B': 1, 'C': 3, 'D': 4},
        'Methodology': {'A': 0, 'B': 1, 'C': 3, 'D': 4},
        'Stakeholder Management': {'A': 0, 'B': 1, 'C': 3, 'D': 4},
        'Resource Management': {'A': 0, 'B': 1, 'C': 3, 'D': 4},
    }
    
    questions_per_category = {
        'Values': 5,
        'Methodology': 11,
        'Stakeholder Management': 6,
        'Resource Management': 9,
    }
    questions_data = {
        'Values' : [
            {'id': 'q1', 'text': "Question 1: On the scale of 1 -4 how  would you rate the Internal Audit department's ability to always do the right thing and tell the truth even when it is uncomfortable or difficult. (1 being lowest and 4 highest)", 'options':[
                {'label': '1', 'value': 'A'},
                {'label': '2', 'value': 'B'},
                {'label': '3', 'value': 'C'},
                {'label': '4', 'value': 'D'},
            ]},
            {'id': 'q2', 'text': 'Question 2: On a scale of 1-4  how would you rate the environment created by CAE where Internal Auditors feel supported when expressing legitimate, evidence-based engagement results.' , 'options': [
                {'label': '1', 'value': 'A'},
                {'label': '2', 'value': 'B'},
                {'label': '3', 'value': 'C'},
                {'label': '4', 'value': 'D'},
            ]},
            {'id': 'q3', 'text': 'Question 3: Is there a practice in place to document the disclosure of potential conflict of interest (of internal audit team member) or other impairments to objectivity', 'options':[
                {'label': 'No', 'value': 'A'},
                {'label': 'Very Rare', 'value': 'B'},
                {'label': 'Ocassioanlly', 'value': 'C'},
                {'label': 'Always', 'value': 'D'},
            ]},
            {'id': 'q4', 'text': 'Question 4: How often do you assess ethical related risks and controls during individual engagements', 'options':[
                {'label': 'Never', 'value': 'A'},
                {'label': 'Very Rare', 'value': 'B'},
                {'label': 'Ocassionally', 'value': 'C'},
                {'label': 'Always considered where relevant', 'value': 'D'},
            ]},
            {'id': 'q5', 'text': 'Question 5: Is there  a documented methodology established by an Internal Audit function for handling illegal and discreditable behavior by Internal Auditors', 'options':[
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Development', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]}
        ],
        'Methodology': [
            {'id' : 'q1', 'text': 'Question 6: As part of your audit engagements or otherwise in addition to providing assurance and insight do you also provide the foresight to better protect and create value for the entity.', 'options': [
                {'label': 'Never', 'value': 'A'},
                {'label': 'Very Rare', 'value': 'B'},
                {'label': 'Occasionally', 'value': 'C'},
                {'label': 'Always considered where relevant', 'value': 'D'},
            ]},
            {'id': 'q2', 'text' : 'Question 7: Is the internal audit strategy developed in line with charter, organization strategy and expectation of board and senior management', 'options':[
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
            {'id': 'q3', 'text': 'Question 8: Has the Internal Audit function established Internal Audit methodology  according to the Global internal audit standards', 'options': [
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},     
            ]},
            {'id': 'q4', 'text': 'Question 9: Has the Internal Audit function identified any requirement of Global Internal Audit Standards that is not in conformance with any application regulation.', 'options':[
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'}, 
            ]},
            {'id': 'q5', 'text': 'Question 10: Is there a mechanism in place whereby CAE document and communicate the circumstances, alternative action taken and their impact, if internal auditor cannot meet the standard requirement', 'options':[
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
            {'id': 'q6', 'text': 'Question 11: Does the internal audit charter comply with global internal audit standards?', 'options': [
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
            {'id': 'q7', 'text': 'Questions 12: Does Internal Audit function conduct Surveys, interviews and workshops for the input on fraud and risks from internal stakeholders?', 'options': [
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
            {'id': 'q8', 'text': 'Question 13: Does the CAE evaluate, update and train auditors on methodology', 'options': [
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
            {'id': 'q9', 'text': 'Question 14 : Is there a mechanism in place through which maturity of organization’s governance structure, risk management and control processes is assessed in comparison with leading principles and globally accepted framework.', 'options': [
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
            {'id': 'q10', 'text': "Question 15: Is the Audit plan developed based on assessment of organization’s strategy, objectives and risks", 'options': [
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
            {'id': 'q11', 'text': 'Question 16: Are there controls in place that restrict information access and its disclosure to unauthorized party?', 'options': [
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
        ],
        'Stakeholder Management': [
            {'id': 'q1', 'text': 'Question 17: Does the internal audit function has unrestricted access to the board as well as to all the activities across the organization', 'options': [
                {'label' : 'No', 'value': 'A'},
                {'label' : 'Partly', 'value': 'B'},
                {'label' : 'On most occasions', 'value': 'C'},
                {'label' : 'Absolute', 'value': 'D'},
            ]},
            {'id' : 'q2', 'text': 'Question 18: Has the CAE held a meeting with the Board apprising it of the way Board should support Internal Audit Functions as per the Global Internal Audit Standards', 'options': [
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
            {'id': 'q3', 'text': 'Question 19: Is the board helped by CAE in order to understand qualification requirements of CAE?', 'options':[
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
            {'id': 'q4', 'text': 'Question 20: Is there a practice in place whereby the CAE conduct Meetings with senior executives and board members to build relationship and identify their concerns?', 'options': [
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
            {'id': 'q5', 'text': 'Question 21: Does Internal Audit Function use Newsletters, presentations and other form of communication for sharing internal audit role and benefit with stakeholders', 'options': [
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
            {'id': 'q6', 'text': 'Question 22: For the development of Internal Audit performance objectives, does CAE incorporate input from board and senior management', 'options': [
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
        ],
        'Resource Management': [
            {'id': 'q1', 'text': 'Question 23: Is there a practice in place through which further Education plans of chief audit executive are developed?', 'options': [
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
            {'id': 'q2', 'text': 'Question 24: Does CAE allocate Sufficient budget for the successful implementation of audit plan including training and acquisition of technological tools?', 'options': [
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
            {'id': 'q3', 'text': 'Question 25: Has the CAE developed approach to recruit, develop and retain competent internal auditors?','options': [
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
            {'id': 'q4', 'text': 'Questions 26: Is there a practice in place whereby Gap analysis between competency of internal auditor on staff and those required is carried out?', 'options': [
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
            {'id': 'q5', 'text': 'Question 27: Does CAE collaborate with internal auditors to develop individual competencies through trainings?', 'options': [
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
            {'id': 'q6', 'text': 'Question 28: Is there a practice in place, whereby, In case of insufficient resources, the board is timely informed about the impact of limitations?', 'options': [
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
            {'id': 'q7', 'text': 'Question 29: Does the CAE evaluate the technology used by internal audit function and ensure that it support internal audit process?', 'options': [
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
            {'id': 'q8', 'text': 'Question 30:  Does CAE collaborate with organization’s IT and IS to implement technological resources properly?', 'options': [
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
            {'id': 'q9', 'text': 'Question 31: Does Internal Audit function use any Software to track progress of auditors recommendations?', 'options':[
                {'label': 'No', 'value': 'A'},
                {'label': 'Under Consideration', 'value': 'B'},
                {'label': 'Under Implementation', 'value': 'C'},
                {'label': 'Yes', 'value': 'D'},
            ]},
        ] 
    }
    if request.method == "POST":
        user_id = session.get("id")
        if not user_id:
            return "User not logged in or session expired", 403  # Handle the case where user is not logged in

        current_category = session.get("category", "Values")
        questions = questions_data.get(current_category, [])
        user_answers = request.form.to_dict()
        total_score = ("total_score", 0)
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
            return redirect("/wait")

    else:
        current_category = session.get("category", "Values")
        questions = questions_data.get(current_category, [])
        return render_template("questions.html", current_category=current_category, questions=questions)


    
@app.route("/thankyoufreeresults")
@app.route("/thankyoupremiumresults")
def thankyou():
    total_cat_score = {
        'Values': {'total': 20},
        'Methodology': {'total': 44},
        'Stakeholder Management': {'total': 24},
        'Resource Management': {'total': 36},
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

    # Determine the template based on the route
    if request.path == "/thankyoufreeresults":
        template_name = "thankyou_freeresults.html"
    else:
        template_name = "thankyou_premiumresults.html"

    return render_template(template_name, total_score=total_score, category_scores=scores_by_category, total_cat_score=total_cat_score)

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

