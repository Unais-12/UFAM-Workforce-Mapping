from flask import session, redirect, render_template, Flask, request, jsonify,flash, send_file
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





def generate_custom_pdf(c, title, row_data, max_score=20, y_position=770):
    """Generate a custom header on the current PDF page with centered title and styled score using ReportLab."""

    page_width, _ = letter

    c.setFont("Helvetica-Bold", 16)
    title_width = c.stringWidth(title, "Helvetica-Bold", 16)
    

    title_x_position = (page_width - title_width) / 2
    
    c.drawString(title_x_position, y_position, title)  
    
  
    score = row_data[3] 
    max_score = max_score  
    
   
    y_position -= 50
    
    # Set the font size and colors for the score (e.g., 13/20)
    c.setFont("Helvetica-Bold", 24)  # Bold and larger for the score
    
    # Set a softer yellow color for the score part
    c.setFillColorRGB(1, 0.85, 0.3)  # Softer shade of yellow
    
    # Draw the score part dynamically
    c.drawString(150, y_position, f"{score}")
    
    # Set a softer green color for the max score part
    c.setFont("Helvetica", 18)
    c.setFillColorRGB(0.3, 0.85, 0.3)  # Softer green
    
    # Draw the max score part
    c.drawString(180, y_position, f"/{max_score}")
    
    # Reset the color back to black for any subsequent text
    c.setFillColorRGB(0, 0, 0)

    return y_position - 50  # Update y_position after adding content
  




def wrap_text(text, max_width, c):
    """Utility function to wrap text based on max width for PDF."""
    # Initialize a list to hold the wrapped lines
    wrapped_lines = []

    # Use the PDF canvas object to calculate text width and split lines accordingly
    lines = text.split('\n')
    for line in lines:
        words = line.split(' ')
        current_line = ""

        for word in words:
            test_line = current_line + word + " "
            if c.stringWidth(test_line, "Helvetica", 12) <= max_width:
                current_line = test_line
            else:
                wrapped_lines.append(current_line.strip())
                current_line = word + " "

        wrapped_lines.append(current_line.strip())

    return wrapped_lines

from docx.shared import RGBColor

def get_rgb_color(color):
    # Check if color is None or has no 'rgb' attribute (indicating no color is set)
    if color is None or not hasattr(color, 'rgb') or color.rgb is None:
        return (0, 0, 0)  # Default to black if no color is set

    # Extract the RGB values from the color object (if available)
    rgb_value = color.rgb  # This returns a `RGBColor` object with raw bytes

    # Convert the RGB value (which is in bytes) to hexadecimal string
    red = rgb_value[0]
    green = rgb_value[1]
    blue = rgb_value[2]

    # Return RGB values normalized to the range 0-1 for ReportLab's setFillColorRGB
    return (red / 255.0, green / 255.0, blue / 255.0)




def add_styled_text_to_pdf(c, doc_paragraphs, y_position, is_first_page=False):
    """Add styled text (bold, italic, underline, font size, color) from a Word document to the PDF."""
    for paragraph in doc_paragraphs:
        for run in paragraph.runs:  # 'runs' are sections with specific formatting
            text = run.text

            # Determine font size; default to 12 if not specified
            font_size = run.font.size.pt if run.font.size else 12

            # Determine font style (bold, italic, etc.)
            if run.bold and run.italic:
                c.setFont("Helvetica-BoldOblique", font_size)  # Bold and Italic
            elif run.bold:
                c.setFont("Helvetica-Bold", font_size)  # Bold
            elif run.italic:
                c.setFont("Helvetica-Oblique", font_size)  # Italic
            else:
                c.setFont("Helvetica", font_size)  # Regular text

            # Set underline if it's applied in the Word doc
            if run.underline:
                c.setLineWidth(1)
                underline_text = True
            else:
                underline_text = False

            # Set the font color based on the Word document
            color = get_rgb_color(run.font.color)
            c.setFillColorRGB(*color)  # Set the fill color for the PDF

            # Wrap the text based on the max width
            wrapped_lines = wrap_text(text, 450, c)

            # Insert the wrapped text into the PDF
            for line in wrapped_lines:
                if y_position < 100:
                    c.showPage()  # Create a new page if the position is too low
                    y_position = 770  # Reset y_position for the new page

                c.drawString(72, y_position, line)
                
                # Add underline for underlined text
                if underline_text:
                    underline_width = c.stringWidth(line, c._fontname, c._fontsize)
                    c.line(72, y_position - 2, 72 + underline_width, y_position - 2)

                y_position -= 14  # Adjust y_position after each line

        # Add extra spacing between paragraphs
        y_position -= 10

    return y_position


@app.route("/download-pdf", methods=["POST"])
def download_pdf():
    selected_documents = []
    user_id = session.get("id")
    if not user_id:
        return "User not logged in"
    
    cursor.execute("SELECT * FROM Users Where Id = ?", (user_id,))
    user_data = cursor.fetchone()
    if user_data:
        if user_data[8] <= 30:
            selected_documents.append('Word Docs/Document 13.docx')
        elif user_data[8] > 30 and user_data[8] <= 76:
            selected_documents.append('Word Docs/Document 14.docx')
        elif user_data[8] > 76 and user_data[8] <= 124:
            selected_documents.append('Word Docs/Document 15.docx')

    cursor.execute("SELECT * FROM UserScores WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()

    document_list = [
        'Word Docs/Document 1.docx', 'Word Docs/Document 2.docx', 'Word Docs/Document 3.docx',
        'Word Docs/Document 4.docx', 'Word Docs/Document 5.docx', 'Word Docs/Document 6.docx',
        'Word Docs/Document 7.docx', 'Word Docs/Document 8.docx', 'Word Docs/Document 9.docx',
        'Word Docs/Document 10.docx', 'Word Docs/Document 11.docx', 'Word Docs/Document 12.docx'
    ]

    pdf_files = []
    pdf_buffer = BytesIO()  # Buffer for the final merged PDF

    # Initialize the ReportLab canvas for the combined PDF
    c = canvas.Canvas(pdf_buffer)

    y_position = 770  # Starting y_position for drawing text

    # Add the text from Document 13, 14, or 15 to the first page
    if selected_documents:
        word_document = Document(selected_documents[0])
        y_position = add_styled_text_to_pdf(c, word_document.paragraphs, y_position, is_first_page=True)
        c.showPage()  # End the first page after adding the initial document

        # Remove the first document so it's not added again later
        selected_documents.pop(0)

    # Now add the custom PDF sections
    for row in rows:
        if row[2] == "Values":
            y_position = generate_custom_pdf(c, "Values:", row, 20, y_position)
            if row[3] <= 6:
                selected_documents.append(document_list[0])
            elif row[3] > 6 and row[3] <= 15:
                selected_documents.append(document_list[1])
            elif row[3] > 15 and row[3] <= 20:
                selected_documents.append(document_list[2])
        elif row[2] == "Methodology":
            y_position = generate_custom_pdf(c, "Methodology:", row, 44, y_position)
            if row[3] <= 13:
                selected_documents.append(document_list[3])
            elif row[3] > 13 and row[3] <= 33:
                selected_documents.append(document_list[4])
            elif row[3] > 33 and row[3] <= 44:
                selected_documents.append(document_list[5])
        elif row[2] == "Stakeholder Management":
            y_position = generate_custom_pdf(c, "Stakeholder Management:", row, 24, y_position)
            if row[3] <= 7:
                selected_documents.append(document_list[6])
            elif 7 < row[3] <= 18:
                selected_documents.append(document_list[7])
            elif 18 < row[3] <= 24:
                selected_documents.append(document_list[8])
        elif row[2] == "Resource Management":
            y_position = generate_custom_pdf(c, "Resource Management:", row, 36, y_position)
            if row[3] < 11:
                selected_documents.append(document_list[9])
            elif 11 < row[3] <= 27:
                selected_documents.append(document_list[10])
            elif 27 < row[3] <= 36:
                selected_documents.append(document_list[11])

        # Check if y_position is getting too low, and add a new page if necessary
        if y_position < 100:
            c.showPage()  # Create a new page
            y_position = 770  # Reset y_position for the new page

    for doc in selected_documents:
        # Open the Word document
        word_document = Document(doc)
        
        # Add styled text from Word to PDF
        y_position = add_styled_text_to_pdf(c, word_document.paragraphs, y_position)

    # Finalize and save the PDF after inserting all text
    c.showPage()
    c.save()

    # Add the generated PDF to the list for merging later
    pdf_buffer.seek(0)
    pdf_files.append(pdf_buffer)

    # Merging PDFs (if needed)
    merger = PdfMerger()
    for pdf in pdf_files:
        merger.append(pdf)

    # Final output to the user
    final_pdf = BytesIO()
    merger.write(final_pdf)
    merger.close()

    final_pdf.seek(0)
    return send_file(final_pdf, as_attachment=True, download_name='Assessment_Report.pdf', mimetype='application/pdf')
