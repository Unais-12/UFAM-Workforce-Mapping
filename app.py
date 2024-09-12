from flask import session, redirect, render_template, Flask, request
from helpers import apology
import sqlite3
import pyodbc
from flask_session import Session


app = Flask(__name__)


app.config["SESSION_TYPE"] = 'filesystem'
app.config["SESSION_PERMANENT"] = 'False'
Session(app)


conn_str = (
    r'DRIVER={ODBC Driver 18 For Sql Server};'
    r'SERVER=LITERALLYME\SQLSERVER_DEV;'
    'DATABASE=Hyphen_Survey;'
    'Trusted_Connection=yes;'
    'TrustServerCertificate=yes;'
    'Encrypt=yes;'
)

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Fetch valid countries and industries from the database
        country = [c[0].lower().strip() for c in cursor.execute("SELECT Name FROM Countries ORDER BY ID").fetchall()]
        industry = [i[0].lower().strip() for i in cursor.execute("SELECT Name FROM industries ORDER BY id").fetchall()]

        # Retrieve form data
        Name = request.form.get("Name")
        Industry = request.form.get("Industry").lower().strip()
        Country = request.form.get("Country").lower().strip()
        Internal_Audit = request.form.get("Internal_Audit")
        Company_Size = request.form.get("Company_Size")
        Using_Solution = request.form.get("Using_Solution")
        Email = request.form.get("Email")

        # Input validation
        if not Name:
            return "Enter a Name"
        elif not Industry:
            return "Enter an Industry"
        elif not Country:
            return "Enter a Country"
        elif not Internal_Audit:
            return "Have to enter the number of members in IA department"
        elif not Company_Size:
            return "Enter company size"
        elif not Using_Solution:
            return "Have to mention if using solution or not"
        elif not Email:
            return "Have to enter email"
        elif Industry not in industry:
            return "Invalid Industry"
        elif Country not in country:
            return "Invalid Country"

        # Check if email is unique
        emails = [email[0] for email in cursor.execute("SELECT email FROM users").fetchall()]
        if Email in emails:
            return "Email must be unique"

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
            session["id"] = rows[0][0]
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
    option_scores = {
        'A':0,
        'B':1,
        'C':3,
        'D':4
    }
    if request.method == "POST":
        user_id = session.get("id")
        user_answers = request.form.to_dict()
        total_score = 0
        for question, option in user_answers.items():
            score = option_scores.get(option, 0)
            total_score += score
            cursor.execute(
                """INSERT INTO Questions(Question, Answer) VALUES (?,?)""", (question, option)
            )
            conn.commit()
        cursor.execute(
            """UPDATE Users SET score = ? WHERE id = ?""", (total_score, user_id)
        )
        conn.commit()
        return redirect("/thankyou")
    else:
        return render_template("questions.html")
    
@app.route("/thankyou")
def thankyou():
    if "id" not in session:
        return redirect("/register")
    
    user_id = session["id"]
    cursor.execute("""SELECT score FROM Users WHERE id = ?""", (user_id))
    row = cursor.fetchone()

    if row:
        user_score = row[0]
    else:
        user_score = None
    
    return render_template("thankyou.html", score = user_score)


        
        

    


        
        

        

