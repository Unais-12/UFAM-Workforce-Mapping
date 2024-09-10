from flask import session, redirect, render_template, Flask, request
import os
from helpers import apology
import sqlite3
import pandas as pd
import pyodbc
from flask_session import Session


app = Flask(__name__)


app.config["SESSION_TYPE"] = 'filesystem'
app.config["SESSION_PERMANENT"] = 'False'
Session(app)

conn = pyodbc.connect(
    'DRIVER={ODBC DRIVER 18 FOR SQL SERVER};'
    'SERVER=LITERALLYME\\SQLSERVER_DEV;'
    'DATABASE=survey;'
    'Trusted_Connection=yes;'
    'TrustServerCertificate=yes;'
    'Encrypt=yes;'
)

cursor = conn.cursor()

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        country = [c[0] for c in cursor.execute("SELECT Name FROM Countries ORDER BY ID").fetchall()]
        industry = [i[0] for i in cursor.execute("SELECT Name FROM industries ORDER BY id").fetchall()]

        if not request.form.get("Name"):
            return "Enter a Name"
        elif not request.form.get("Industry"):
            return "Enter an Industry"
        elif not request.form.get("Country"):
            return "Enter a Country"
        elif not request.form.get("Internal_Audit"):
            return "Have to enter the number of members in IA department"
        elif not request.form.get("Company_Size"):
            return "Enter company size"
        elif not request.form.get("Using_Solution"):
            return "Have to mention if using solution or not"
        elif not request.form.get("Email"):
            return "Have to enter email"
        elif request.form.get("Industry") not in industry:
            return "Invalid Industry"
        elif request.form.get("Country") not in country:
            return "Invalid Country"
        emails = [email[0] for email in cursor.execute("SELECT email FROM users").fetchall()]
        if request.form.get("Email") in emails:
            return "Email must be unique"
        cursor.execute("INSERT INTO users(Name, Industry, Country, Internal_Audit, Company_Size, Using_Solution, Email) VALUES(?,?,?,?,?,?,?)", request.form.get("Name"), request.form.get("Industry"), request.form.get("Country"), request.form.get("Internal_Audit"), request.form.get("Company_Size"), request.form.get("Using_Solution").strip(), request.form.get("Email"))
        conn.commit()
        rows = cursor.execute("SELECT * FROM users WHERE Name = ?", request.form.get("Name"))
        session["id"] = rows[0]["id"]

        return redirect("/")
    else:
        return render_template("register.html")

@app.route("/")
def index():
    return render_template("index.html")
        
        
        

    


        
        

        

