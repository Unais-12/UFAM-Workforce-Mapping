# UFAM Workforce Mapping

## Overview

UFAM Workforce Mapping is a Flask-based web application designed to assess users through a structured survey and map them to suitable career domains and job roles. The system evaluates users across **four core dimensions**, calculates weighted scores, and generates **free** or **premium** results, including a dynamically generated **PDF report** for premium users.

The application includes full user authentication, session-based progress tracking, scoring logic, role-matching algorithms, and PDF generation.

---

## Tech Stack

* **Backend**: Python, Flask
* **Database**: Microsoft SQL Server (via `pyodbc`)
* **Authentication & Security**:

  * Password hashing using `bcrypt`
  * Tokenized password reset using `itsdangerous`
  * Server-side sessions using `Flask-Session`
* **Email Service**: SendGrid Web API
* **PDF Handling**:

  * `PyPDF2`, `fitz (PyMuPDF)`, `reportlab`
* **Frontend**:

  * HTML, CSS (inline and file-based)
  * JavaScript
  * Jinja2 templating

---

## Application Flow

### 1. Landing Page (`/`)

* Displays an introduction to the UFAM Workforce Mapping assessment.
* Explains what users will gain from completing the survey.

### 2. Registration & Survey Start (`/start`)

* Users register using **email and password**.
* Passwords are validated and securely hashed using **bcrypt**.
* Each user is assigned a unique `user_id`, stored in the session.
* Survey progress is initialized using session variables.

### 3. Questionnaire (`/questions`)

The survey consists of **4 categories**, each containing **5 questions**:

1. **Skills and Career Orientation**
2. **Soft Skills**
3. **Professional Expectations**
4. **Physchological Profile**

* Each question has four options (A–D), mapped to a predefined score.
* Scores are calculated per category and stored in the `UserScores` table.
* The cumulative score is stored in the `Users` table.
* Survey navigation is handled category-by-category using session state.
* Once completed, the user is marked as finished (`Last_Page = 0`).

---

## Session Management

User progress is maintained using **Flask sessions**, including:

* Logged-in user ID
* Current question category
* Category-wise scores
* Total score
* Selected result type (free or premium)

This ensures users can resume progress securely and prevents data mismatches.

---

## Waiting & Choice Flow

### 4. Wait Page (`/wait`)

* Displayed immediately after completing the questionnaire.

### 5. Result Choice (`/choice`)

* Users choose between:

  * **Free Results**
  * **Premium Results**

---

## Secondary Registration (`/register`)

After choosing a result type, users provide additional information:

* Name
* Age
* Country (validated against database)
* Qualification
* Job preference

This data is stored in the same `Users` table row created during initial registration.

---

## Results Processing

### Free & Premium Results (`/thankyoufreeresults`, `/thankyoupremiumresults`)

* Category scores are normalized.
* A **weighted role-matching algorithm** determines:

  * Best broader career category
  * Top 3 job roles within that category

### Broader Career Categories

* Technology and Development
* Product and Design
* Business & Strategy
* Marketing & Sales
* Support & Operations

### Stored Outputs

* `UserResults`: total score + selected broader category
* `UserTopRoles`: top 3 recommended roles with ranking

---

## PDF Generation

### Free Results

* Displayed directly on the results page.

### Premium Results (`/download-pdf`)

* A personalized PDF report is generated dynamically:

  * A base cover PDF is customized with the user’s name.
  * A category-specific PDF is selected based on results.
  * PDFs are merged into a single final report.

* Delivered as a downloadable file: `UFAM_Premium_Report.pdf`

---

## Authentication System

### Login (`/login`)

* Validates credentials using bcrypt password comparison.
* Redirects users based on completion state.

### Forgot Password (`/forgot_password`)

* Users request a reset link via email.
* A time-limited token (1 hour) is generated.

### Reset Password (`/reset_password/<token>`)

* Token is verified securely.
* Password is re-hashed and updated in the database.

---

## Database Overview

Key tables used in the system:

* `Users` – account details, hashed passwords, total score
* `UserScores` – category-wise scores
* `Questions` – stored responses
* `UserResults` – final evaluation outcome
* `UserTopRoles` – ranked job role recommendations
* `Countries` – country validation and autocomplete

---

## Additional Endpoints

* `/health` – health check endpoint
* `/autocomplete/countries` – country search for forms
* `/payment` – placeholder for payment integration

---

## Key Features Summary

* Secure authentication & password recovery
* Session-based survey progression
* Dynamic question rendering
* Weighted career role matching
* Free and premium result flows
* Automated PDF generation
* SQL Server–backed persistent storage

---

## Notes

* All sensitive credentials (e.g., SendGrid API key) are loaded via environment variables.
* The application is designed to be extensible, allowing additional questions, categories, and role mappings to be added easily.

---

**UFAM Workforce Mapping** provides a complete, data-driven career assessment pipeline—from user onboarding to actionable career insights.
