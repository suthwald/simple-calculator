import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import snowflake.connector
import google.generativeai as genai
from dotenv import load_dotenv

# --- Load environment variables ---
load_dotenv()

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY not set")

genai.configure(api_key=GEMINI_API_KEY)

# --- FastAPI App ---
app = FastAPI(title="Text-to-SQL API (Gemini + Snowflake)")


# --- Snowflake Connection ---
def get_connection():
    try:
        return snowflake.connector.connect(
            account=os.getenv("account"),
            user=os.getenv("user"),
            password=os.getenv("password"),
            role=os.getenv("role"),
            warehouse=os.getenv("warehouse"),
            database=os.getenv("database"),
            schema=os.getenv("schema"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Snowflake connection failed: {e}")


# --- Data Model ---
class QueryRequest(BaseModel):
    question: str


# --- Execute SQL Safely ---
def execute_sql(sql: str):
    if not sql.strip().lower().startswith("select"):
        raise HTTPException(status_code=400, detail="Only SELECT queries are allowed.")

    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description]
        cur.close()
        conn.close()
        return {"columns": cols, "rows": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SQL execution error: {e}")


# --- Schema Context ---
SCHEMA_CONTEXT = """
Database schema (for LLM reference):
TABLE Students (student_id INT AUTOINCREMENT PRIMARY KEY, first_name STRING NOT NULL, last_name STRING NOT NULL, dob DATE NOT NULL, gender STRING, email STRING UNIQUE NOT NULL, phone STRING, address STRING);
TABLE Courses (course_id INT AUTOINCREMENT PRIMARY KEY, course_name STRING NOT NULL, course_code STRING UNIQUE NOT NULL, credits INT NOT NULL, department STRING);
TABLE Instructors (instructor_id INT AUTOINCREMENT PRIMARY KEY, first_name STRING NOT NULL, last_name STRING NOT NULL, email STRING UNIQUE NOT NULL, phone STRING, department STRING);
TABLE Classrooms (classroom_id INT AUTOINCREMENT PRIMARY KEY, building STRING, room_number STRING, capacity INT);
TABLE Course_Schedule (schedule_id INT AUTOINCREMENT PRIMARY KEY, course_id INT, instructor_id INT, classroom_id INT, day_of_week STRING, start_time TIME, end_time TIME, FOREIGN KEY (course_id) REFERENCES Courses(course_id), FOREIGN KEY (instructor_id) REFERENCES Instructors(instructor_id), FOREIGN KEY (classroom_id) REFERENCES Classrooms(classroom_id));
TABLE Enrollments (enrollment_id INT AUTOINCREMENT PRIMARY KEY, student_id INT, course_id INT, enrollment_date DATE DEFAULT CURRENT_DATE, grade STRING, FOREIGN KEY (student_id) REFERENCES Students(student_id), FOREIGN KEY (course_id) REFERENCES Courses(course_id));
TABLE Attendance (attendance_id INT AUTOINCREMENT PRIMARY KEY, student_id INT, schedule_id INT, attendance_date DATE NOT NULL, status STRING, FOREIGN KEY (student_id) REFERENCES Students(student_id), FOREIGN KEY (schedule_id) REFERENCES Course_Schedule(schedule_id));
TABLE Fees (fee_id INT AUTOINCREMENT PRIMARY KEY, student_id INT, amount NUMBER(10,2) NOT NULL, due_date DATE, paid_date DATE, status STRING DEFAULT 'Pending', FOREIGN KEY (student_id) REFERENCES Students(student_id));
"""


# --- Endpoint ---
@app.post("/query")
def text_to_sql(request: QueryRequest):
    system_prompt = f"""
You are a Text-to-SQL generator. Use Snowflake SQL syntax. Output **only** SQL — no explanations or natural language.
{SCHEMA_CONTEXT}
"""

    prompt = f"{system_prompt}\nUser question: {request.question}"

    gen_config = genai.types.GenerationConfig(
        temperature=0.0,
    )

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        resp = model.generate_content(
            prompt,
            generation_config=gen_config,
        )

        sql = resp.text.strip()

        # Clean possible markdown formatting
        if sql.startswith("```"):
            sql = sql.strip("`").replace("sql", "").strip()

        if not sql.lower().startswith("select"):
            raise HTTPException(
                status_code=400, detail="Generated SQL is not a SELECT query."
            )

        sql = sql.rstrip(";") + ";"

        print("Generated SQL:", sql)
        result = execute_sql(sql)
        return {"sql": sql, "result": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "appp:app",  # <--- replace 'main' with your filename (without .py)
        host="0.0.0.0",  # accessible on your local network
        port=8000,  # change if needed
        reload=True,  # auto-reload on code changes (dev mode)
    )
