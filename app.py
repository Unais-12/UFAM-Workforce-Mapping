from flask import session, redirect, render_template, Flask, request, jsonify,flash, send_file
from flask_session import Session
import os
import pyodbc
from reportlab.pdfgen import canvas
from io import BytesIO
from docx import Document
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import pdfkit

config = pdfkit.configuration(wkhtmltopdf='C:\Program Files\wkhtmltopdf\bin')

app = Flask(__name__)

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

        form_data = {
        "Name": Name,
        "Industry": Industry,
        "Country": Country,
        "Internal_Audit": Internal_Audit,
        "Company_Size": Company_Size,
        "Using_Solution": Using_Solution,
        "Email": Email
        }

        # Input validation
        if not Name:
            flash("Enter a Name")
            form_data['Name'] = ''  # Clear the specific field
            return render_template("register.html", **form_data)
        elif not Industry:
            flash("Enter an Industry")
            form_data['Industry'] = ''  # Clear the specific field
            return render_template("register.html", **form_data)
        elif not Country:
            flash("Enter a Country")
            form_data['Country'] = ''  # Clear the specific field
            return render_template("register.html", **form_data)
        elif not Internal_Audit:
            flash("Enter the number of members in the IA department")
            form_data['Internal_Audit'] = ''  # Clear the specific field
            return render_template("register.html", **form_data)
        elif not Company_Size:
            flash("Enter company size")
            form_data['Company_Size'] = ''  # Clear the specific field
            return render_template("register.html", **form_data)
        elif not Using_Solution:
            flash("Mention whether using a solution or not")
            form_data['Using_Solution'] = ''  # Clear the specific field
            return render_template("register.html", **form_data)
        elif not Email:
            flash("Enter an email")
            form_data['Email'] = ''  # Clear the specific field
            return render_template("register.html", **form_data)
        elif Industry not in industry:
            flash("Invalid Industry")
            form_data['Industry'] = ''  # Clear the specific field
            return render_template("register.html", **form_data)
        elif Country not in country:
            flash("Invalid Country")
            form_data['Country'] = ''  # Clear the specific field
            return render_template("register.html", **form_data)

        # Check if email is unique
        emails = [email[0] for email in cursor.execute("SELECT email FROM users").fetchall()]
        if Email in emails:
            flash("Email must be unique")
            form_data['Email'] = ''  # Clear the specific field
            return render_template("register.html", **form_data)

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



@app.route("/choice")
def choice():
    return render_template("choice.html")

@app.route("/wait")
def wait():
    return render_template("wait.html")

@app.route("/premium")
def premium():
    return render_template("premium.html")

def generate_custom_pdf(title, row_data):
    """Generate a custom PDF using ReportLab and save it to memory."""
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer)

    # Add custom header and content to the PDF
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 800, title)  # Custom title (e.g., "Marketing Content")

    # Add dynamic content from the database
    c.setFont("Helvetica", 12)
    c.drawString(100, 770, f"User Data: {row_data[3]}")  # Example of dynamic content

    # Finalize and save the PDF
    c.showPage()
    c.save()

    # Add the generated PDF to the list for merging later
    pdf_buffer.seek(0)
    custom_pdfs.append(pdf_buffer)  # Store the PDF in the custom_pdfs list


@app.route("/download-pdf", methods = ["POST"])
def download_pdf():
    selected_documents = []
    cursor.execute("SELECT * FROM UserScores")
    rows = cursor.fetchall()

    document_list = ['Word Docs/Document 1.docx', 'Word Docs/Document 2.docx', 'Word Docs/Document 3.docx','Word Docs/Document 4.docx'
                     ,'Word Docs/Document 5.docx','Word Docs/Document 6.docx','Word Docs/Document 7.docx','Word Docs/Document 8.docx'
                     ,'Word Docs/Document 9.docx','Word Docs/Document 10.docx','Word Docs/Document 11.docx','Word Docs/Document 12.docx']

    for row in rows:
        if row[2] == "Values":
            generate_custom_pdf("Your Score:", row)
            if row[3] <= 6:
                selected_documents.append(document_list[0])
            elif row[3] > 6 and row[3] <= 15:
                selected_documents.append(document_list[1])
            elif row[3] > 15 and row[3] <=20:
                selected_documents.append(document_list[2])
        elif row[2] == "Methodology":
            generate_custom_pdf("Your Score:", row)
            if row[3] <= 13:
                selected_documents.append(document_list[3])
            elif row[3] > 13 and row[3] <= 33:
                selected_documents.append(document_list[4])
            elif row[3] > 33 and row[3] <= 44:
                selected_documents.append(document_list[5])
        elif row[2] == "Stakeholder Management":
            generate_custom_pdf("Your Score:", row)
            if row[3] <= 7:
                selected_documents.append(document_list[6])
            elif row[3] > 7 and row[3] <= 18:
                selected_documents.append(document_list[7])
            elif row[3] > 18 and row[3] <= 24:
                selected_documents.append(document_list[8])
        elif row[2] == "Resource Management":
            generate_custom_pdf("Your Score:", row)
            if row[3] < 11:
                selected_documents.append(document_list[9])
            elif row[3] >11 and row[3] <= 27:
                selected_documents.append(document_list[10])
            elif row[3] > 27 and row[3] <= 36:
                selected_documents.append(document_list[11])

    pdf_files = []
    for doc in selected_documents:
        pdf_file = doc.replace('.docx', '.pdf')
        pdfkit.from_file(doc, pdf_file, configuration=config)
        pdf_files.append(pdf_file)
    
    merger = PdfMerger()
    for pdf in pdf_files:
        merger.append(pdf)

    for custom_pdf in custom_pdfs:
        merger.append(custom_pdf)
    
    pdf_output = BytesIO()
    merger.write(pdf_output)
    merger.close()

    pdf_output.seek(0)
    return send_file(pdf_output, as_attachment=True, download_name='Assessment_Report.pdf', mimetype='application/pdf')

    