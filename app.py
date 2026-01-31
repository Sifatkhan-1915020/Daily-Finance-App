import streamlit as st
import pandas as pd
import sqlite3
import hashlib
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from fpdf import FPDF
import base64

# --- CONFIGURATION & STYLING ---
st.set_page_config(page_title="FinTrack Pro", page_icon="💰", layout="wide")

# Custom CSS for "Super Cool" look
st.markdown("""
<style>
    .stMetric {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 10px;
        border-left: 5px solid #ff4b4b;
    }
    .css-1d391kg {
        padding-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# --- DATABASE MANAGEMENT ---
def init_db():
    conn = sqlite3.connect('finance.db')
    c = conn.cursor()
    # User Table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password TEXT)''')
    # Transactions Table
    c.execute('''CREATE TABLE IF NOT EXISTS transactions
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  username TEXT, 
                  date TEXT, 
                  type TEXT, 
                  category TEXT, 
                  amount REAL, 
                  note TEXT)''')
    conn.commit()
    conn.close()

def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    if make_hashes(password) == hashed_text:
        return True
    return False

def add_user(username, password):
    conn = sqlite3.connect('finance.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO users(username, password) VALUES (?,?)', (username, password))
        conn.commit()
        return True
    except:
        return False
    finally:
        conn.close()

def login_user(username, password):
    conn = sqlite3.connect('finance.db')
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE username =? AND password = ?', (username, password))
    data = c.fetchall()
    conn.close()
    return data

def add_transaction(username, date, type_, category, amount, note):
    conn = sqlite3.connect('finance.db')
    c = conn.cursor()
    c.execute('INSERT INTO transactions(username, date, type, category, amount, note) VALUES (?,?,?,?,?,?)', 
              (username, date, type_, category, amount, note))
    conn.commit()
    conn.close()

def get_data(username):
    conn = sqlite3.connect('finance.db')
    df = pd.read_sql_query("SELECT * FROM transactions WHERE username = ?", conn, params=(username,))
    conn.close()
    return df

# --- PDF GENERATOR ---
class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Financial Statement Report', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_pdf(df, username):
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    pdf.cell(200, 10, txt=f"User: {username}", ln=1, align='L')
    pdf.cell(200, 10, txt=f"Date Generated: {datetime.now().strftime('%Y-%m-%d')}", ln=1, align='L')
    pdf.ln(10)

    # Table Header
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(30, 10, 'Date', 1)
    pdf.cell(25, 10, 'Type', 1)
    pdf.cell(40, 10, 'Category', 1)
    pdf.cell(30, 10, 'Amount', 1)
    pdf.cell(60, 10, 'Note', 1)
    pdf.ln()

    # Table Rows
    pdf.set_font("Arial", size=10)
    for index, row in df.iterrows():
        # Handle potentially missing values or types for PDF
        d = str(row['date'])
        t = str(row['type'])
        c = str(row['category'])
        a = str(row['amount'])
        n = str(row['note'])
        
        pdf.cell(30, 10, d, 1)
        pdf.cell(25, 10, t, 1)
        pdf.cell(40, 10, c, 1)
        pdf.cell(30, 10, a, 1)
        pdf.cell(60, 10, n, 1)
        pdf.ln()
        
    return pdf.output(dest='S').encode('latin-1')

# --- MAIN APP ---
def main():
    init_db()
    
    # Session State for Login
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
        st.session_state['username'] = ''

    # --- AUTHENTICATION VIEW ---
    if not st.session_state['logged_in']:
        st.title("🔐 FinTrack Pro")
        menu = ["Login", "SignUp"]
        choice = st.sidebar.selectbox("Menu", menu)

        if choice == "Login":
            st.subheader("Welcome Back!")
            username = st.text_input("User Name")
            password = st.text_input("Password", type='password')
            if st.button("Login"):
                hashed_pswd = make_hashes(password)
                result = login_user(username, hashed_pswd)
                if result:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username
                    st.success(f"Logged In as {username}")
                    st.rerun()
                else:
                    st.warning("Incorrect Username/Password")

        elif choice == "SignUp":
            st.subheader("Create New Account")
            new_user = st.text_input("User Name")
            new_password = st.text_input("Password", type='password')
            if st.button("Signup"):
                if new_user and new_password:
                    hashed_new_password = make_hashes(new_password)
                    if add_user(new_user, hashed_new_password):
                        st.success("You have successfully created an account")
                        st.info("Go to Login Menu to login")
                    else:
                        st.warning("Username already taken")
                else:
                    st.warning("Please fill all fields")

    # --- DASHBOARD VIEW ---
    else:
        st.sidebar.title(f"👤 {st.session_state['username']}")
        
        # Navigation
        app_mode = st.sidebar.radio("Navigate", ["Dashboard", "Add Transaction", "Report & Download"])
        
        # Logout
        if st.sidebar.button("Logout"):
            st.session_state['logged_in'] = False
            st.rerun()

        # Load Data
        df = get_data(st.session_state['username'])
        
        # ---- 1. ADD TRANSACTION ----
        if app_mode == "Add Transaction":
            st.title("💸 Add New Transaction")
            with st.form("transaction_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    date = st.date_input("Date")
                    amount = st.number_input("Amount", min_value=0.0, format="%.2f")
                    trans_type = st.selectbox("Type", ["Expense", "Income", "Deposit/Savings"])
                with col2:
                    category = st.text_input("Category (e.g., Food, Salary, Rent)")
                    note = st.text_area("Note/Description")
                
                submitted = st.form_submit_button("Save Transaction")
                if submitted:
                    add_transaction(st.session_state['username'], date, trans_type, category, amount, note)
                    st.success("Transaction Saved!")

        # ---- 2. DASHBOARD ----
        elif app_mode == "Dashboard":
            st.title("📊 Financial Overview")
            
            if df.empty:
                st.info("No data found. Go to 'Add Transaction' to get started!")
            else:
                # Calculations
                total_income = df[df['type'].isin(['Income', 'Deposit/Savings'])]['amount'].sum()
                total_expense = df[df['type'] == 'Expense']['amount'].sum()
                balance = total_income - total_expense
                
                # Metrics
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Income", f"${total_income:,.2f}", delta="Inflow")
                col2.metric("Total Expense", f"${total_expense:,.2f}", delta="-Outflow", delta_color="inverse")
                col3.metric("Current Balance", f"${balance:,.2f}")
                
                st.markdown("---")
                
                # Charts Area
                c1, c2 = st.columns([2, 1])
                
                with c1:
                    st.subheader("Trend Over Time")
                    df['date'] = pd.to_datetime(df['date'])
                    daily_data = df.groupby(['date', 'type'])['amount'].sum().reset_index()
                    fig_line = px.line(daily_data, x='date', y='amount', color='type', 
                                       title='Daily Financial Activity', markers=True,
                                       color_discrete_map={"Expense": "red", "Income": "green", "Deposit/Savings": "blue"})
                    st.plotly_chart(fig_line, use_container_width=True)
                
                with c2:
                    st.subheader("Expense Breakdown")
                    expense_df = df[df['type'] == 'Expense']
                    if not expense_df.empty:
                        # FIX IS HERE: Changed px.donut to px.pie with hole parameter
                        fig_pie = px.pie(expense_df, values='amount', names='category', hole=0.4,
                                         title="Spending by Category")
                        st.plotly_chart(fig_pie, use_container_width=True)
                    else:
                        st.write("No expenses recorded yet.")

                # Recent Transactions
                st.subheader("Recent Transactions")
                st.dataframe(df.sort_values(by='date', ascending=False).head(5), use_container_width=True)

        # ---- 3. REPORT & DOWNLOAD ----
        elif app_mode == "Report & Download":
            st.title("📄 Reports")
            if df.empty:
                st.warning("No data to download.")
            else:
                st.dataframe(df)
                
                # Filter Logic
                st.subheader("Filter Data")
                unique_types = df['type'].unique()
                filter_type = st.multiselect("Filter by Type", unique_types, default=unique_types)
                
                if filter_type:
                    filtered_df = df[df['type'].isin(filter_type)]
                    st.write(f"Showing {len(filtered_df)} records.")
                    
                    # PDF Download
                    st.markdown("### Download")
                    if st.button("Generate PDF Report"):
                        pdf_bytes = generate_pdf(filtered_df, st.session_state['username'])
                        st.download_button(
                            label="📥 Download PDF",
                            data=pdf_bytes,
                            file_name="financial_report.pdf",
                            mime="application/pdf"
                        )
                else:
                    st.warning("Please select at least one transaction type.")

if __name__ == '__main__':
    main()
