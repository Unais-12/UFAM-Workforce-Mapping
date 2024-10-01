from flask import session, redirect, render_template, Flask, request, jsonify,flash
from flask_session import Session
import os
import pyodbc
import csv
import datetime
import urllib
import uuid
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import pdfkit

app = Flask(__name__)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)


app.config["SESSION_TYPE"] = 'filesystem'
app.config["SESSION_PERMANENT"] = False
app.config['SESSION_COOKIE_NAME'] = 'my_custom_session'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default_secret_key')
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'hyphen_survey:'
Session(app)


conn_str = os.getenv('AZURE_SQL_CONNECTION_STRING')
conn = pyodbc.connect(conn_str)
cursor = conn.cursor()


@app.route('/health')
def health_check():
    return "Healthy", 200


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





@app.route("/register", methods=["GET", "POST"])
def register():
    # Initialize session for the new user
    session['category'] = 'Values'  # Start with the first category
    session['total_score'] = 0
    session['category_scores'] = {}
    
    if request.method == "POST":
        # Fetch valid countries and industries from the database
        country = [c[0].lower().strip() for c in cursor.execute("SELECT Name FROM Countries ORDER BY ID").fetchall()]
        industry = [i[0].lower().strip() for i in cursor.execute("SELECT Name FROM industries ORDER BY id").fetchall()]

        # Retrieve form data
        Name = request.form.get("Name")
        Internal_Audit = request.form.get("Internal_Audit")
        Company_Size = request.form.get("Company_Size")
        Using_Solution = request.form.get("Using_Solution")
        Email = request.form.get("Email")
        Industry = request.form.get("Industry").strip().lower()
        Country = request.form.get("Country").strip().lower()

        # Input validation
        if not Name:
            flash("Enter a Name")
            return redirect(request.url)
        elif not Industry:
            flash("Enter an Industry")
            return redirect(request.url)
        elif not Country:
            flash("Enter a Country")
            return redirect(request.url)
        elif not Internal_Audit:
            flash("Have to enter the number of members in IA department")
            return redirect(request.url)
        elif not Company_Size:
            flash("Enter company size")
            return redirect(request.url)
        elif not Using_Solution:
            flash("Have to mention if using solution or not")
            return redirect(request.url)
        elif not Email:
            flash("Have to enter email")
            return redirect(request.url)
        elif Industry not in industry:
            flash("Invalid Industry")
            return redirect(request.url)
        elif Country not in country:
            flash("Invalid Country")
            return redirect(request.url)

        # Check if email is unique
        emails = [email[0] for email in cursor.execute("SELECT email FROM users").fetchall()]
        if Email in emails:
            flash("Email must be unique")
            return redirect(request.url)

        # Insert the user into the database
        try:
            cursor.execute(
                """INSERT INTO Users (Name, Industry, Country, Internal_Audit, Company_Size, Using_Solution, Email)
                VALUES(?,?,?,?,?,?,?)""", (Name, Industry, Country, Internal_Audit, Company_Size, Using_Solution, Email)
            )
            conn.commit()
        except pyodbc.ProgrammingError as e:
            print(f"Database Error: {e}")
            return "There was an error with the database operation."
        
        # Fetch the user's ID after insertion
        rows = cursor.execute("SELECT id FROM users WHERE Name = ?", Name).fetchall()
        if rows:
            session["id"] = rows[0][0]  # Save the user ID to the session
        else:
            conn.close()
            return "Failed to retrieve user ID after registration."

        return redirect("/questions")
    else:
        return render_template("register.html")



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
        current_category = session.get("category", "Values")
        questions = questions_data.get(current_category, [])
        user_answers = request.form.to_dict()
        total_score = ("total_score", 0)
        category_scores = session.get('category_scores', {})

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
            """UPDATE Users SET Score = ? WHERE id = ?""",
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
        return render_template("questions.html",current_category=current_category, questions=questions)

    
@app.route("/thankyou")
def thankyou():
    total_cat_score = {
        'Values' : {'total': 20},
        'Methodology': {'total': 44},
        'Stakeholder Management' : {'total': 24},
        'Resource Management': {'total': 36},
    }
    if "id" not in session:
        return redirect("/register")

    user_id = session["id"]

    # Retrieve total score
    cursor.execute("""SELECT Score FROM Users WHERE Id = ?""", (user_id))
    row = cursor.fetchone()
    total_score = row[0] if row else None

    # Retrieve category-wise scores
    cursor.execute("""SELECT category, score FROM UserScores WHERE user_id = ?""", (user_id,))
    category_scores = cursor.fetchall()

    scores_by_category = {row[0]: row[1] for row in category_scores}

    return render_template("thankyou.html", total_score=total_score, category_scores=scores_by_category, total_cat_score=total_cat_score)

@app.route("/wait")
def wait():
    return render_template("wait.html")

def get_data(user_id):
    cursor.execute("SELECT * FROM Users WHERE id = ?", (user_id,))
    data = cursor.fetchone()
    #conn.close()
    return data


def make_comparisons(data):
    comparison_result = {}
    try:
        if data[8] <= 31:
            comparison_result['status'] = "Bad"
            comparison_result['message'] = (
                "You are amazing just the way you are. But seriously bro you need to lock in. "
                "Things won't work out like this. Your company will die and you will be a sad loser forever. "
                "So yeah lock in unlike the Pakistani Government"
            )
        elif data[8] >= 31:
            comparison_result['status'] = "Good"
            comparison_result['message'] = (
                "You're doing well my boy you know what's up so I won't bore you with anything else"
            )
    except IndexError as e:
        print(f"Error in comparison: {e}")
        comparison_result['status'] = "Error"
        comparison_result['message'] = "Error during comparison."

    return comparison_result

def generate_and_send_pdf(data, to_email):
    try:
        # Make comparisons and prepare content for the PDF
        comparisons = make_comparisons(data)

        # Create a PDF document
        content = f"""
        <h1>User Report</h1>
        <p>Name: {data[1]}</p>
        <p>Status: {comparisons['status']}</p>
        <p>Message: {comparisons['message']}</p>
        """

        # Use pdfkit to generate the PDF
        try:
            pdf = pdfkit.from_string(content, False)
        except Exception as e:
            print(f"Error generating PDF: {e}")
            return "Error generating PDF."

        # Send PDF via SendGrid
        message = Mail(
            from_email='unaisbinfaheem@gmail.com',
            to_emails=to_email,
            subject="Your PDF Report",
            html_content="Please find your PDF report attached."
        )
        
        # Attach the PDF
        message.add_attachment(
            file_content=pdf,
            file_name="report.pdf",
            file_type="application/pdf",
            disposition="attachment"
        )

        # Send email using SendGrid
        try:
            sg = SendGridAPIClient(os.environ.get('SENDGRID_API_KEY'))
            response = sg.send(message)
            print(f"Email sent: {response.status_code}")
        except Exception as e:
            print(f"Error sending email: {e}")
            return "Error sending email."

    except Exception as e:
        print(f"Error in generating and sending PDF: {e}")
        return "An error occurred during the PDF generation or email process."


@app.route("/choice")
def choice():
    try:
        user_id = session.get('id') 
        email = session.get('email') 
        return render_template("choice.html", user_id=user_id, email=email)
    except Exception as e:
        print(f"Error in rendering choice page: {e}")
        return "Error in loading the page."

@app.route("/send_pdf", methods=["POST"])
def send_pdf():
    try:
        user_id = session.get('id')  # Get the user ID from the session
        email = session.get('email')  # Get email from the session

        if user_id is None:
            return "User not registered. Please register first."

        # Fetch user data from the database
        try:
            data = get_data(user_id)
            if data is None:
                print("No data found for the user.")
                return "No data found for the user."
        except Exception as e:
            print(f"Error fetching data: {e}")
            return "Error fetching data from the database."

        # Generate and send PDF
        result = generate_and_send_pdf(data, email)
        if "Error" in result:
            return result

        return "PDF sent successfully."
    except Exception as e:
        print(f"Error in send_pdf route: {e}")
        return "An error occurred while sending the PDF."



@app.route("/premium")
def premium():
    return render_template("premium.html")