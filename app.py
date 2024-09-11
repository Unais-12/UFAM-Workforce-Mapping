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
        country = [c[0] for c in cursor.execute("SELECT Name FROM Countries ORDER BY ID").fetchall()]
        industry = [i[0] for i in cursor.execute("SELECT Name FROM industries ORDER BY id").fetchall()]

        # Retrieve form data
        Name = request.form.get("Name")
        Industry = request.form.get("Industry")
        Country = request.form.get("Country")
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

        return redirect("/")
    else:
        return render_template("register.html")


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/question1", methods=["GET", "POST"])
def questions():
    if request.method == "POST":
        Option1 = request.method.get("Option1")
        Option2 = request.method.get("Option2")
        Option3 = request.method.get("Option3")
        Option4 = request.method.get("Option4")

        if not (Option1 and Option2 and Option3 and Option4):
            return "You have to enter atleast one value"
        elif Option1:
            



        
        
        

    


        
        

        

