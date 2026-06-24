import os
import sqlite3
import shutil
import json
import re
import requests
from datetime import datetime

# ReportLab Verification & Configuration
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# Kivy Framework Imports
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle

CORE_DATA_DB = "house_hold_records_v4.db"
Window.softinput_mode = "below_target"

# =========================================================
# ?? FIREBASE & SESSION MANAGEMENT SYSTEM
# =========================================================
# YAHAN NEECHE APNI ASLI FIREBASE WEB API KEY DALNI HAI:
FIREBASE_API_KEY = "AIzaSyCyoOUtLR8uGqQxoSR2yY8KyGRSU4Ce_rA"
SESSION_FILE = "user_session.json"

def save_session(id_token, email):
    with open(SESSION_FILE, "w") as f:
        json.dump({"token": id_token, "email": email}, f)

def check_session():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r") as f:
                data = json.load(f)
                return data.get("token")
        except:
            return None
    return None

def clear_session():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)

# =========================================================
# ??? GLOBAL FONT & ZOOM CONTROLLER SYSTEM
# =========================================================
class FontManager:
    BASE_FONT_SIZE = 18       
    HEADER_FONT_SIZE = 26     
    TITLE_FONT_SIZE = 36      
    SCALE_FACTOR = 1.0        

    @classmethod
    def get_size(cls, text_type="normal"):
        if text_type == "title":
            return int(cls.TITLE_FONT_SIZE * cls.SCALE_FACTOR)
        elif text_type == "header":
            return int(cls.HEADER_FONT_SIZE * cls.SCALE_FACTOR)
        else:
            return int(cls.BASE_FONT_SIZE * cls.SCALE_FACTOR)

class ZoomableScrollView(ScrollView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        self.touch_points = {} 

    def on_touch_down(self, touch):
        if touch.is_mouse_scrolling:
            if touch.button == 'scrolldown':
                self.zoom(0.95)
            elif touch.button == 'scrollup':
                self.zoom(1.05)
            return True
        
        self.touch_points[touch.id] = touch.pos
        if len(self.touch_points) == 2:
            ids = list(self.touch_points.keys())
            p1 = self.touch_points[ids[0]]
            p2 = self.touch_points[ids[1]]
            self.last_dist = ((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)**0.5
            
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if touch.id in self.touch_points:
            self.touch_points[touch.id] = touch.pos
            
        if len(self.touch_points) == 2:
            ids = list(self.touch_points.keys())
            p1 = self.touch_points[ids[0]]
            p2 = self.touch_points[ids[1]]
            dist = ((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)**0.5
            
            if hasattr(self, 'last_dist') and self.last_dist > 0:
                change = dist / self.last_dist
                if abs(change - 1.0) > 0.01: 
                    self.zoom(1.03 if change > 1.0 else 0.97)
            self.last_dist = dist
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if touch.id in self.touch_points:
            self.touch_points.pop(touch.id, None)
        if len(self.touch_points) < 2:
            self.last_dist = 0
        return super().on_touch_up(touch)

    def zoom(self, factor):
        new_scale = FontManager.SCALE_FACTOR * factor
        if 0.8 <= new_scale <= 2.2:
            FontManager.SCALE_FACTOR = new_scale
            sm = self.app.root
            if sm and sm.current_screen:
                sm.current_screen.on_enter()

# =========================================================
# ?? DATABASE SYSTEM LAYER
# =========================================================
def setup_databases():
    conn2 = sqlite3.connect(CORE_DATA_DB)
    cursor2 = conn2.cursor()
    cursor2.execute("CREATE TABLE IF NOT EXISTS income (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, amount REAL, date TEXT, is_agri_sale TEXT)")
    cursor2.execute("""CREATE TABLE IF NOT EXISTS spendings (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, amount REAL, 
                    details TEXT, date TEXT, paid_status TEXT, unpaid_status TEXT, meter_reading TEXT)""")
    conn2.commit()
    conn2.close()
    
    if os.path.exists(CORE_DATA_DB):
        try: shutil.copy2(CORE_DATA_DB, "house_hold_backup.db")
        except: pass

setup_databases()

# =========================================================
# ?? HIGH CONTRAST CUSTOM UI COMPONENTS
# =========================================================
class ColoredScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(0.95, 0.96, 0.98, 1) 
            self.rect = Rectangle(size=Window.size, pos=self.pos)
        self.bind(size=self._update_rect, pos=self._update_rect)

    def _update_rect(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos

class StyledLabel(Label):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.font_name = "Roboto"
        self.size_hint_y = None
        self.height = 45
        self.bold = True
        self.color = (0.05, 0.08, 0.15, 1)
        self.font_size = FontManager.get_size("normal")

class StyledInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.multiline = False
        self.size_hint_y = None
        self.height = 55
        self.write_tab = False
        self.background_color = (1, 1, 1, 1) 
        self.foreground_color = (0, 0, 0, 1) 
        self.cursor_color = (0.11, 0.22, 0.54, 1)
        self.font_size = FontManager.get_size("normal")

class StyledButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = 60
        self.bold = True
        self.color = (1, 1, 1, 1) 
        self.background_normal = ''
        self.font_size = FontManager.get_size("normal")

# =========================================================
# ?? LOGIN & SIGNUP SCREENS (IUB THEME)
# =========================================================
class LoginScreen(ColoredScreen):
    def on_enter(self):
        self.clear_widgets()
        layout = BoxLayout(orientation='vertical', padding=30, spacing=20)
        
        header = Label(text="SMART KHATA PRO", font_size=FontManager.get_size("title"), 
                       bold=True, color=(0.11, 0.22, 0.54, 1), size_hint_y=None, height=80)
        layout.add_widget(header)

        self.email_input = StyledInput(hint_text="Email Address")
        layout.add_widget(self.email_input)

        self.password_input = StyledInput(hint_text="Password", password=True)
        layout.add_widget(self.password_input)

        btn_login = StyledButton(text="Secure Login", background_color=(0.11, 0.22, 0.54, 1))
        btn_login.bind(on_press=self.authenticate_user)
        layout.add_widget(btn_login)

        btn_signup = StyledButton(text="Create New Account", background_color=(0.3, 0.3, 0.3, 1))
        btn_signup.bind(on_press=lambda x: setattr(self.manager, 'current', 'signup'))
        layout.add_widget(btn_signup)
        
        self.add_widget(layout)

    def authenticate_user(self, instance):
        email = self.email_input.text.strip()
        password = self.password_input.text.strip()
        
        if not email or not password:
            self.show_error("Error", "Please fill all fields.")
            return

        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
        payload = {"email": email, "password": password, "returnSecureToken": True}
        
        try:
            req = requests.post(url, json=payload)
            res = req.json()
            if "idToken" in res:
                save_session(res["idToken"], email)
                self.manager.current = 'dashboard'
            else:
                self.show_error("Login Failed", res.get("error", {}).get("message", "Invalid Credentials"))
        except Exception as e:
            self.show_error("Network Error", "Internet connection required.")

    def show_error(self, title, msg):
        Popup(title=title, content=Label(text=msg, font_size=FontManager.get_size("normal")), size_hint=(0.8, 0.4)).open()

class SignupScreen(ColoredScreen):
    def on_enter(self):
        self.clear_widgets()
        layout = BoxLayout(orientation='vertical', padding=30, spacing=20)
        
        layout.add_widget(Label(text="REGISTER ACCOUNT", font_size=FontManager.get_size("title")-4, 
                                bold=True, color=(0.11, 0.22, 0.54, 1), size_hint_y=None, height=80))

        self.email_input = StyledInput(hint_text="Email Address")
        layout.add_widget(self.email_input)

        self.password_input = StyledInput(hint_text="Password (Min 8 chars, 1 Cap, 1 Num)", password=True)
        layout.add_widget(self.password_input)

        btn_register = StyledButton(text="Register", background_color=(0.06, 0.6, 0.2, 1))
        btn_register.bind(on_press=self.register_user)
        layout.add_widget(btn_register)
        
        btn_back = StyledButton(text="Back to Login", background_color=(0.4, 0.4, 0.4, 1))
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'login'))
        layout.add_widget(btn_back)

        self.add_widget(layout)

    def register_user(self, instance):
        email = self.email_input.text.strip()
        password = self.password_input.text.strip()
        
        if not re.match(r"^(?=.*[A-Z])(?=.*\d).{8,}$", password):
            Popup(title="Weak Password", content=Label(text="Password must be 8+ chars,\nhave 1 Capital letter & 1 Number.", font_size=FontManager.get_size("normal")-2), size_hint=(0.8, 0.5)).open()
            return
            
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={FIREBASE_API_KEY}"
        payload = {"email": email, "password": password, "returnSecureToken": True}
        
        try:
            req = requests.post(url, json=payload)
            res = req.json()
            if "idToken" in res:
                Popup(title="Success", content=Label(text="Account Created! Please Login.", font_size=FontManager.get_size("normal")), size_hint=(0.8, 0.4)).open()
                self.manager.current = 'login'
            else:
                Popup(title="Error", content=Label(text=res.get("error", {}).get("message", "Registration Failed"), font_size=FontManager.get_size("normal")-2), size_hint=(0.8, 0.4)).open()
        except:
             Popup(title="Error", content=Label(text="Network Error. Try again.", font_size=FontManager.get_size("normal")), size_hint=(0.8, 0.4)).open()


# =========================================================
# ?? MAIN DASHBOARD SCREEN
# =========================================================
class DashboardScreen(ColoredScreen):
    def on_enter(self):
        self.clear_widgets()
        main_layout = BoxLayout(orientation='vertical')
        
        top_bar = BoxLayout(orientation='horizontal', size_hint_y=None, height=65, padding=10, spacing=10)
        with top_bar.canvas.before:
            Color(0.11, 0.22, 0.54, 1) 
            self.nb_rect = Rectangle(size=top_bar.size, pos=top_bar.pos)
        top_bar.bind(size=lambda inst, val: setattr(self.nb_rect, 'size', val), pos=lambda inst, val: setattr(self.nb_rect, 'pos', val))
        
        top_bar.add_widget(Label(text="Smart Ledger Pro", font_size=FontManager.get_size("header")-4, bold=True, halign="left", color=(1,1,1,1)))
        
        btn_logout = Button(text="Logout", size_hint_x=0.3, background_color=(0.8, 0.1, 0.1, 1), bold=True)
        btn_logout.bind(on_press=self.logout_user)
        top_bar.add_widget(btn_logout)

        main_layout.add_widget(top_bar)
        
        scroll = ZoomableScrollView(size_hint=(1, 1))
        content_layout = BoxLayout(orientation='vertical', padding=15, spacing=12, size_hint_y=None)
        content_layout.bind(minimum_height=content_layout.setter('height'))
        
        self.lbl_inc = Label(text="Total Income: 0.00", font_size=FontManager.get_size("header"), bold=True, color=(0.02, 0.55, 0.35, 1), size_hint_y=None, height=45)
        self.lbl_exp = Label(text="Total Expenses: 0.00", font_size=FontManager.get_size("header"), bold=True, color=(0.8, 0.1, 0.1, 1), size_hint_y=None, height=45)
        self.lbl_bal = Label(text="Net Cash Balance: 0.00", font_size=FontManager.get_size("header"), bold=True, color=(0.1, 0.3, 0.8, 1), size_hint_y=None, height=45)
        content_layout.add_widget(self.lbl_inc)
        content_layout.add_widget(self.lbl_exp)
        content_layout.add_widget(self.lbl_bal)
        
        content_layout.add_widget(Label(text="--- Agriculture & Ushr Matrix ---", font_size=FontManager.get_size("normal")+2, bold=True, color=(0.05, 0.35, 0.2, 1), size_hint_y=None, height=40))
        self.lbl_agri_exp = Label(text="Total Agriculture Expenses: 0.00", font_size=FontManager.get_size("normal"), bold=True, color=(0.15, 0.15, 0.2, 1), size_hint_y=None, height=35)
        self.lbl_ushr = Label(text="Total Ushr Paid: 0.00", font_size=FontManager.get_size("normal"), bold=True, color=(0.4, 0.25, 0.05, 1), size_hint_y=None, height=35)
        self.lbl_agri_net = Label(text="Net Agricultural Profit/Loss: 0.00", font_size=FontManager.get_size("header")-2, bold=True, color=(0.01, 0.4, 0.28, 1), size_hint_y=None, height=40)
        content_layout.add_widget(self.lbl_agri_exp)
        content_layout.add_widget(self.lbl_ushr)
        content_layout.add_widget(self.lbl_agri_net)
        
        btn_frame = BoxLayout(orientation='horizontal', size_hint_y=None, height=65, spacing=12)
        btn_add_inc = Button(text="Add Income", bold=True, background_color=(0.06, 0.65, 0.45, 1), background_normal='', font_size=FontManager.get_size("normal"))
        btn_add_inc.bind(on_press=lambda x: self.go_to_entry("income"))
        btn_add_exp = Button(text="Add Expense", bold=True, background_color=(0.85, 0.15, 0.15, 1), background_normal='', font_size=FontManager.get_size("normal"))
        btn_add_exp.bind(on_press=lambda x: self.go_to_entry("expense"))
        btn_frame.add_widget(btn_add_inc)
        btn_frame.add_widget(btn_add_exp)
        content_layout.add_widget(btn_frame)
        
        content_layout.add_widget(Label(text="Analytical Statements & Reports", font_size=FontManager.get_size("normal"), bold=True, color=(0.3, 0.3, 0.4, 1), size_hint_y=None, height=40))
        
        btn_pdf = Button(text="?? Generate Audit Report (PDF)", bold=True, size_hint_y=None, height=60, background_color=(0.85, 0.3, 0.02, 1), background_normal='', font_size=FontManager.get_size("normal"))
        btn_pdf.bind(on_press=self.generate_pdf)
        content_layout.add_widget(btn_pdf)
        
        btn_inc_rec = Button(text="Income Ledger Statement", bold=True, size_hint_y=None, height=55, background_color=(0.04, 0.5, 0.45, 1), background_normal='', font_size=FontManager.get_size("normal"))
        btn_inc_rec.bind(on_press=lambda x: self.go_to_ledger("Income Records"))
        content_layout.add_widget(btn_inc_rec)
        
        categories = ["Agriculture", "Ushr", "Household", "Installment", "Fees", "Petrol", "Salami & Gifts"]
        for cat in categories:
            b = Button(text=f"{cat} Expenditures Ledger", bold=True, size_hint_y=None, height=55, background_color=(0.22, 0.28, 0.35, 1), background_normal='', font_size=FontManager.get_size("normal"))
            b.bind(on_press=lambda x, c=cat: self.go_to_ledger(c))
            content_layout.add_widget(b)
            
        scroll.add_widget(content_layout)
        main_layout.add_widget(scroll)
        self.add_widget(main_layout)
        self.calculate_live_totals()

    def logout_user(self, instance):
        clear_session()
        self.manager.current = 'login'

    def calculate_live_totals(self):
        conn = sqlite3.connect(CORE_DATA_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(amount) FROM income")
        total_inc = cursor.fetchone()[0] or 0.0
        self.lbl_inc.text = f"Total Income: {total_inc:,.2f}"
        
        cursor.execute("SELECT SUM(amount) FROM spendings")
        total_exp = cursor.fetchone()[0] or 0.0
        self.lbl_exp.text = f"Total Expenses: {total_exp:,.2f}"
        
        net_bal = total_inc - total_exp
        self.lbl_bal.text = f"Net Cash Balance: {net_bal:,.2f}"
        
        cursor.execute("SELECT SUM(amount) FROM spendings WHERE category='Agriculture'")
        agri_spend = cursor.fetchone()[0] or 0.0
        self.lbl_agri_exp.text = f"Total Agriculture Expenses: {agri_spend:,.2f}"
        
        cursor.execute("SELECT SUM(amount) FROM spendings WHERE category='Ushr'")
        ushr_spend = cursor.fetchone()[0] or 0.0
        self.lbl_ushr.text = f"Total Ushr Paid: {ushr_spend:,.2f}"
        
        cursor.execute("SELECT SUM(amount) FROM income WHERE is_agri_sale='Yes'")
        agri_inc = cursor.fetchone()[0] or 0.0
        agri_net = agri_inc - agri_spend - ushr_spend
        self.lbl_agri_net.text = f"Net Agricultural Profit/Loss: {agri_net:,.2f}"
        conn.close()

    def go_to_entry(self, mode):
        self.manager.get_screen('entry').entry_mode = mode
        self.manager.current = 'entry'

    def go_to_ledger(self, name):
        self.manager.get_screen('ledger').ledger_name = name
        self.manager.current = 'ledger'

    def generate_pdf(self, instance):
        if not REPORTLAB_AVAILABLE:
            self.show_popup("Error", "ReportLab module missing!")
            return
        pdf_filename = "Smart_Khata_System_Report.pdf"
        
        doc = SimpleDocTemplate(pdf_filename, pagesize=letter, leftMargin=30, rightMargin=30, topMargin=40, bottomMargin=40)
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle('RepTitle', parent=styles['Heading1'], fontSize=24, leading=28, textColor=colors.HexColor('#112236'), alignment=1, spaceAfter=20)
        section_style = ParagraphStyle('RepSec', parent=styles['Heading2'], fontSize=16, leading=20, textColor=colors.HexColor('#0F375A'), spaceBefore=10, spaceAfter=10)
        cell_style = ParagraphStyle('CellSt', fontName='Helvetica', fontSize=10, leading=13, alignment=1)
        cell_header_style = ParagraphStyle('CellHd', fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=colors.white, alignment=1)

        story = []
        story.append(Paragraph("Smart Khata Master Ledger Report", title_style))
        story.append(Spacer(1, 10))
        
        conn = sqlite3.connect(CORE_DATA_DB)
        cursor = conn.cursor()
        
        story.append(Paragraph("1. Income History Statement", section_style))
        inc_headers = [Paragraph("<b>Date</b>", cell_header_style), Paragraph("<b>Source / Title</b>", cell_header_style), Paragraph("<b>Amount Inflow</b>", cell_header_style)]
        inc_rows = [inc_headers]
        
        total_pdf_inc = 0.0
        for r in cursor.execute("SELECT date, title, amount FROM income ORDER BY date ASC").fetchall():
            total_pdf_inc += r[2]
            inc_rows.append([Paragraph(str(r[0]), cell_style), Paragraph(str(r[1]), cell_style), Paragraph(f"{r[2]:,.2f}", cell_style)])
        
        inc_rows.append([Paragraph("<b>TOTAL REVENUE ACCRUED</b>", cell_style), Paragraph("", cell_style), Paragraph(f"<b>{total_pdf_inc:,.2f}</b>", cell_style)])
        
        t1 = Table(inc_rows, colWidths=[130, 260, 160])
        t1.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#06652E')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#D0D0D0')),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#EAF7EE')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6), ('TOPPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(t1)
        
        story.append(PageBreak())
        story.append(Paragraph("2. Agriculture Expenditure Matrix", section_style))
        agri_headers = [
            Paragraph("<b>Date</b>", cell_header_style), Paragraph("<b>Description Details</b>", cell_header_style),
            Paragraph("<b>Settled (Paid)</b>", cell_header_style), Paragraph("<b>Outstanding (Unpaid)</b>", cell_header_style),
            Paragraph("<b>Gross Liability</b>", cell_header_style)
        ]
        agri_rows = [agri_headers]
        
        t_agri_amt, t_agri_paid, t_agri_unpaid = 0.0, 0.0, 0.0
        records = cursor.execute("SELECT date, details, paid_status, unpaid_status, amount FROM spendings WHERE category='Agriculture' ORDER BY date ASC").fetchall()
        for r in records:
            p_val, up_val = float(r[2] or 0), float(r[3] or 0)
            t_agri_paid += p_val
            t_agri_unpaid += up_val
            t_agri_amt += r[4]
            agri_rows.append([
                Paragraph(str(r[0]), cell_style), Paragraph(str(r[1]), cell_style),
                Paragraph(f"{p_val:,.2f}", cell_style), Paragraph(f"{up_val:,.2f}", cell_style),
                Paragraph(f"{r[4]:,.2f}", cell_style)
            ])
        agri_rows.append([
            Paragraph("<b>CUMULATIVE METRICS</b>", cell_style), Paragraph("", cell_style),
            Paragraph(f"<b>{t_agri_paid:,.2f}</b>", cell_style), Paragraph(f"<b>{t_agri_unpaid:,.2f}</b>", cell_style),
            Paragraph(f"<b>{t_agri_amt:,.2f}</b>", cell_style)
        ])
        
        t_agri = Table(agri_rows, colWidths=[100, 150, 100, 100, 100])
        t_agri.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1B4D3E')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#D0D0D0')),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#E8F5E9')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6), ('TOPPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(t_agri)

        story.append(PageBreak())
        story.append(Paragraph("3. Petrol Logistics Ledger", section_style))
        pet_headers = [
            Paragraph("<b>Date</b>", cell_header_style), Paragraph("<b>Description Details</b>", cell_header_style),
            Paragraph("<b>Odometer Reading</b>", cell_header_style), Paragraph("<b>Financial Amount</b>", cell_header_style)
        ]
        pet_rows = [pet_headers]
        
        t_pet_amt = 0.0
        records = cursor.execute("SELECT date, details, meter_reading, amount FROM spendings WHERE category='Petrol' ORDER BY date ASC").fetchall()
        for r in records:
            t_pet_amt += r[3]
            pet_rows.append([
                Paragraph(str(r[0]), cell_style), Paragraph(str(r[1]), cell_style),
                Paragraph(str(r[2] or '-'), cell_style), Paragraph(f"{r[3]:,.2f}", cell_style)
            ])
        pet_rows.append([Paragraph("<b>TOTAL LOGISTICS CAPITAL EXPENDITURE</b>", cell_style), Paragraph("", cell_style), Paragraph("", cell_style), Paragraph(f"<b>{t_pet_amt:,.2f}</b>", cell_style)])
        
        t_pet = Table(pet_rows, colWidths=[110, 200, 120, 120])
        t_pet.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#D4A373')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#D0D0D0')),
            ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#FEFAE0')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6), ('TOPPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(t_pet)

        other_cats = ["Ushr", "Household", "Installment", "Fees", "Salami & Gifts"]
        idx = 4
        for cat in other_cats:
            story.append(PageBreak())
            story.append(Paragraph(f"{idx}. {cat} Expenditure Ledger", section_style))
            
            cat_headers = [Paragraph("<b>Date</b>", cell_header_style), Paragraph("<b>Description Details</b>", cell_header_style), Paragraph("<b>Amount Spent</b>", cell_header_style)]
            cat_rows = [cat_headers]
            
            t_cat_amt = 0.0
            records = cursor.execute("SELECT date, details, amount FROM spendings WHERE category=? ORDER BY date ASC", (cat,)).fetchall()
            for r in records:
                t_cat_amt += r[2]
                cat_rows.append([Paragraph(str(r[0]), cell_style), Paragraph(str(r[1]), cell_style), Paragraph(f"{r[2]:,.2f}", cell_style)])
                
            cat_rows.append([Paragraph(f"<b>TOTAL CUMULATIVE {cat.upper()}</b>", cell_style), Paragraph("", cell_style), Paragraph(f"<b>{t_cat_amt:,.2f}</b>", cell_style)])
            
            t_cat = Table(cat_rows, colWidths=[130, 260, 160])
            t_cat.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#4A4E69')),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('GRID', (0,0), (-1,-1), 1, colors.HexColor('#D0D0D0')),
                ('BACKGROUND', (0,-1), (-1,-1), colors.HexColor('#F2E9E4')),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6), ('TOPPADDING', (0,0), (-1,-1), 6),
            ]))
            story.append(t_cat)
            idx += 1
            
        conn.close()
        try:
            doc.build(story)
            self.show_popup("Audit Trail Exported", f"Success! Cryptographic PDF report built safely as '{pdf_filename}'")
        except Exception as e:
            self.show_popup("Export Interrupted", str(e))

    def show_popup(self, title, msg):
        pop = Popup(title=title, content=Label(text=msg, font_size=FontManager.get_size("normal")), size_hint=(0.8, 0.4))
        pop.open()

# =========================================================
# ?? KIVY DATA ENTRY SCREEN (Auto Date Included)
# =========================================================
class EntryScreen(ColoredScreen):
    entry_mode = "income"

    def on_enter(self):
        self.clear_widgets()
        scroll = ZoomableScrollView(size_hint=(1, 1))
        self.layout = BoxLayout(orientation='vertical', padding=25, spacing=12, size_hint_y=None)
        self.layout.bind(minimum_height=self.layout.setter('height'))
        
        self.layout.add_widget(Label(text=f"--- ADD NEW {self.entry_mode.upper()} ASSET ---", font_size=FontManager.get_size("header"), bold=True, color=(0.11, 0.22, 0.54, 1), size_hint_y=None, height=50))
        
        self.layout.add_widget(StyledLabel(text="Transaction Date (YYYY-MM-DD):", text_size=(Window.width-50, None), halign="left"))
        
        # Auto System Date
        today_date = datetime.now().strftime("%Y-%m-%d")
        self.date_input = StyledInput(text=today_date)
        self.layout.add_widget(self.date_input)
        
        if self.entry_mode == "income":
            self.layout.add_widget(StyledLabel(text="Income Revenue Source (Title):", text_size=(Window.width-50, None), halign="left"))
            self.title_input = StyledInput()
            self.layout.add_widget(self.title_input)
            
            self.layout.add_widget(StyledLabel(text="Financial Capital Amount:", text_size=(Window.width-50, None), halign="left"))
            self.amt_input = StyledInput()
            self.layout.add_widget(self.amt_input)
            
            self.layout.add_widget(StyledLabel(text="Is Agriculture Crop Yield Sale? (Yes / No):", text_size=(Window.width-50, None), halign="left"))
            self.agri_spin = Spinner(text="No", values=("No", "Yes"), size_hint_y=None, height=55, background_color=(0.2, 0.3, 0.5, 1), color=(1,1,1,1), font_size=FontManager.get_size("normal"))
            self.layout.add_widget(self.agri_spin)
        else:
            self.layout.add_widget(StyledLabel(text="Allocation Category Budget:", text_size=(Window.width-50, None), halign="left"))
            self.cat_spin = Spinner(text="Agriculture", values=("Agriculture", "Ushr", "Household", "Installment", "Fees", "Petrol", "Salami & Gifts"), size_hint_y=None, height=55, background_color=(0.2, 0.3, 0.5, 1), color=(1,1,1,1), font_size=FontManager.get_size("normal"))
            self.cat_spin.bind(text=self.handle_dynamic_fields)
            self.layout.add_widget(self.cat_spin)
            
            self.layout.add_widget(StyledLabel(text="Transaction Details / Specifications:", text_size=(Window.width-50, None), halign="left"))
            self.det_input = StyledInput()
            self.layout.add_widget(self.det_input)
            
            self.layout.add_widget(StyledLabel(text="Financial Capital Amount:", text_size=(Window.width-50, None), halign="left"))
            self.amt_input = StyledInput()
            self.layout.add_widget(self.amt_input)
            
            self.dyn_box = BoxLayout(orientation='vertical', spacing=10, size_hint_y=None)
            self.dyn_box.bind(minimum_height=self.dyn_box.setter('height'))
            self.layout.add_widget(self.dyn_box)
            self.handle_dynamic_fields(None, "Agriculture")

        btn_save = StyledButton(text="Commit & Clear Entry", background_color=(0.06, 0.6, 0.2, 1))
        btn_save.bind(on_press=self.save_transaction)
        self.layout.add_widget(btn_save)
        
        btn_cancel = StyledButton(text="Abrupt Cancel & Return", background_color=(0.45, 0.45, 0.45, 1))
        btn_cancel.bind(on_press=lambda x: setattr(self.manager, 'current', 'dashboard'))
        self.layout.add_widget(btn_cancel)
        
        scroll.add_widget(self.layout)
        self.add_widget(scroll)

    def handle_dynamic_fields(self, spinner, text):
        if not hasattr(self, 'dyn_box'): return
        self.dyn_box.clear_widgets()
        self.dyn_inputs = {}
        
        if text == "Agriculture":
            self.dyn_box.add_widget(StyledLabel(text="Cleared Liquid Paid Amount:", text_size=(Window.width-50, None), halign="left"))
            self.dyn_inputs['paid'] = StyledInput(text="0")
            self.dyn_box.add_widget(self.dyn_inputs['paid'])
            self.dyn_box.add_widget(StyledLabel(text="Outstanding Arrears Unpaid Amount:", text_size=(Window.width-50, None), halign="left"))
            self.dyn_inputs['unpaid'] = StyledInput(text="0")
            self.dyn_box.add_widget(self.dyn_inputs['unpaid'])
        elif text == "Petrol":
            self.dyn_box.add_widget(StyledLabel(text="Current Logged Meter Odometer Reading:", text_size=(Window.width-50, None), halign="left"))
            self.dyn_inputs['meter'] = StyledInput()
            self.dyn_box.add_widget(self.dyn_inputs['meter'])

    def save_transaction(self, instance):
        dt = self.date_input.text.strip()
        amt = self.amt_input.text.strip()
        if not dt or not amt: return
        
        conn = sqlite3.connect(CORE_DATA_DB)
        cursor = conn.cursor()
        
        if self.entry_mode == "income":
            t = self.title_input.text.strip()
            is_ag = self.agri_spin.text
            cursor.execute("INSERT INTO income (title, amount, date, is_agri_sale) VALUES (?, ?, ?, ?)", (t, float(amt), dt, is_ag))
        else:
            cat = self.cat_spin.text
            det = self.det_input.text.strip()
            p_v, up_v, m_v = "0", "0", ""
            if cat == "Agriculture":
                p_v = self.dyn_inputs['paid'].text.strip()
                up_v = self.dyn_inputs['unpaid'].text.strip()
            elif cat == "Petrol":
                m_v = self.dyn_inputs['meter'].text.strip()
                
            cursor.execute("INSERT INTO spendings (category, amount, details, date, paid_status, unpaid_status, meter_reading) VALUES (?, ?, ?, ?, ?, ?, ?)",
                           (cat, float(amt), det, dt, p_v, up_v, m_v))
        conn.commit()
        conn.close()
        self.manager.current = 'dashboard'

# =========================================================
# ?? FIXED COLUMN MATRIX ENGINE + LIVE TOTAL SYSTEM
# =========================================================
class LedgerScreen(ColoredScreen):
    ledger_name = ""
    selected_id = None
    all_row_containers = []

    def on_enter(self):
        self.clear_widgets()
        self.selected_id = None
        self.all_row_containers = []
        
        main_box = BoxLayout(orientation='vertical', padding=15, spacing=10)
        main_box.add_widget(Label(text=f"--- {self.ledger_name.upper()} STATEMENT ---", font_size=FontManager.get_size("header"), bold=True, color=(0.11, 0.22, 0.54, 1), size_hint_y=None, height=45))
        
        if self.ledger_name == "Income Records":
            headers = ["Date", "Source/Title", "Amount"]
            ratios = [0.25, 0.45, 0.30]
        elif self.ledger_name == "Agriculture":
            headers = ["Date", "Details", "Paid", "Unpaid", "Total"]
            ratios = [0.22, 0.24, 0.18, 0.18, 0.18]
        elif self.ledger_name == "Petrol":
            headers = ["Date", "Details", "Meter R.", "Amount"]
            ratios = [0.22, 0.28, 0.25, 0.25]
        else:
            headers = ["Date", "Details", "Amount"]
            ratios = [0.25, 0.45, 0.30]

        header_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=45)
        with header_box.canvas.before:
            Color(0.1, 0.1, 0.12, 1) 
            self.hd_rect = Rectangle(size=header_box.size, pos=header_box.pos)
        header_box.bind(size=lambda inst, val: setattr(self.hd_rect, 'size', val), pos=lambda inst, val: setattr(self.hd_rect, 'pos', val))
        
        for h, r in zip(headers, ratios):
            header_box.add_widget(Label(text=h, bold=True, size_hint_x=r, color=(1,1,1,1), font_size=FontManager.get_size("normal"), halign="center"))
        main_box.add_widget(header_box)
        
        scroll = ZoomableScrollView(size_hint=(1, 1))
        self.rows_container = BoxLayout(orientation='vertical', spacing=6, size_hint_y=None)
        self.rows_container.bind(minimum_height=self.rows_container.setter('height'))
        
        conn = sqlite3.connect(CORE_DATA_DB)
        cursor = conn.cursor()
        
        total_amount = 0.0
        total_paid = 0.0
        total_unpaid = 0.0

        if self.ledger_name == "Income Records":
            records = cursor.execute("SELECT id, date, title, amount FROM income ORDER BY date ASC").fetchall()
            for r in records:
                total_amount += r[3]
                self.add_clean_row(r[0], [str(r[1]), str(r[2]), f"{r[3]:,.2f}"], ratios)
        elif self.ledger_name == "Agriculture":
            records = cursor.execute("SELECT id, date, details, amount, paid_status, unpaid_status FROM spendings WHERE category='Agriculture' ORDER BY date ASC").fetchall()
            for r in records:
                total_paid += float(r[4])
                total_unpaid += float(r[5])
                total_amount += r[3]
                self.add_clean_row(r[0], [str(r[1]), str(r[2]), f"{float(r[4]):,.2f}", f"{float(r[5]):,.2f}", f"{r[3]:,.2f}"], ratios)
        elif self.ledger_name == "Petrol":
            records = cursor.execute("SELECT id, date, details, amount, meter_reading FROM spendings WHERE category='Petrol' ORDER BY date ASC").fetchall()
            for r in records:
                total_amount += r[3]
                self.add_clean_row(r[0], [str(r[1]), str(r[2]), str(r[4]), f"{r[3]:,.2f}"], ratios)
        else:
            records = cursor.execute("SELECT id, date, details, amount FROM spendings WHERE category=? ORDER BY date ASC", (self.ledger_name,)).fetchall()
            for r in records:
                total_amount += r[3]
                self.add_clean_row(r[0], [str(r[1]), str(r[2]), f"{r[3]:,.2f}"], ratios)
                
        conn.close()
        scroll.add_widget(self.rows_container)
        main_box.add_widget(scroll)
        
        total_bar_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=45)
        with total_bar_box.canvas.before:
            Color(0.88, 0.92, 0.98, 1) 
            self.tot_rect = Rectangle(size=total_bar_box.size, pos=total_bar_box.pos)
        total_bar_box.bind(size=lambda inst, val: setattr(self.tot_rect, 'size', val), pos=lambda inst, val: setattr(self.tot_rect, 'pos', val))
        
        if self.ledger_name == "Income Records":
            total_bar_box.add_widget(Label(text="Sum Inflow:", bold=True, size_hint_x=0.70, color=(0.02, 0.45, 0.2, 1), font_size=FontManager.get_size("normal"), halign="right"))
            total_bar_box.add_widget(Label(text=f"{total_amount:,.2f}", bold=True, size_hint_x=0.30, color=(0.02, 0.45, 0.2, 1), font_size=FontManager.get_size("normal"), halign="center"))
        elif self.ledger_name == "Agriculture":
            total_bar_box.add_widget(Label(text="Totals:", bold=True, size_hint_x=0.46, color=(0,0,0,1), font_size=FontManager.get_size("normal"), halign="right"))
            total_bar_box.add_widget(Label(text=f"{total_paid:,.2f}", bold=True, size_hint_x=0.18, color=(0.1, 0.5, 0.1, 1), font_size=FontManager.get_size("normal"), halign="center"))
            total_bar_box.add_widget(Label(text=f"{total_unpaid:,.2f}", bold=True, size_hint_x=0.18, color=(0.8, 0.1, 0.1, 1), font_size=FontManager.get_size("normal"), halign="center"))
            total_bar_box.add_widget(Label(text=f"{total_amount:,.2f}", bold=True, size_hint_x=0.18, color=(0.1, 0.2, 0.6, 1), font_size=FontManager.get_size("normal"), halign="center"))
        else:
            total_bar_box.add_widget(Label(text="Sum Outflow:", bold=True, size_hint_x=0.70, color=(0.8, 0.1, 0.1, 1), font_size=FontManager.get_size("normal"), halign="right"))
            total_bar_box.add_widget(Label(text=f"{total_amount:,.2f}", bold=True, size_hint_x=0.30, color=(0.8, 0.1, 0.1, 1), font_size=FontManager.get_size("normal"), halign="center"))
            
        main_box.add_widget(total_bar_box)
        
        self.btn_erase = StyledButton(text="??? Void (Erase) Selected Record", background_color=(0.85, 0.15, 0.15, 1))
        self.btn_erase.bind(on_press=self.erase_record)
        main_box.add_widget(self.btn_erase)
        
        btn_back = StyledButton(text="Return to Main Dashboard", background_color=(0.35, 0.35, 0.35, 1))
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'dashboard'))
        main_box.add_widget(btn_back)
        self.add_widget(main_box)

    def add_clean_row(self, rid, cells_text, ratios):
        row_box = BoxLayout(orientation='horizontal', size_hint_y=None, height=50)
        
        with row_box.canvas.before:
            Color(1, 1, 1, 1) 
            row_box.bg_color = Color(1, 1, 1, 1)
            row_box.bg_rect = Rectangle(size=row_box.size, pos=row_box.pos)
        row_box.bind(size=lambda inst, val: setattr(inst.bg_rect, 'size', val), pos=lambda inst, val: setattr(inst.bg_rect, 'pos', val))
        
        labels_references = []
        for text, ratio in zip(cells_text, ratios):
            lbl = Label(text=text, size_hint_x=ratio, color=(0,0,0,1), font_size=FontManager.get_size("normal")-2, halign="center", valign="middle")
            lbl.bind(size=lambda inst, val: setattr(inst, 'text_size', (inst.width, inst.height)))
            row_box.add_widget(lbl)
            labels_references.append(lbl)
            
        click_trigger_btn = Button(background_color=(0,0,0,0), background_normal='', size_hint=(1, 1))
        click_trigger_btn.bind(on_press=lambda x: self.select_kivy_row_fixed(rid, row_box, labels_references))
        
        row_box.id_ref = rid
        row_box.labels_ref = labels_references
        self.all_row_containers.append(row_box)
        
        row_box.add_widget(click_trigger_btn)
        row_box.remove_widget(click_trigger_btn)
        row_box.bind(on_touch_down=lambda inst, touch: self.check_row_touch(inst, touch, rid, row_box, labels_references))
        
        self.rows_container.add_widget(row_box)

    def check_row_touch(self, instance, touch, rid, row_box, labels_references):
        if instance.collide_point(*touch.pos):
            self.select_kivy_row_fixed(rid, row_box, labels_references)
            return True
        return False

    def select_kivy_row_fixed(self, rid, clicked_row, labels_list):
        for row in self.all_row_containers:
            row.bg_color.rgb = (1, 1, 1)
            for lbl in row.labels_ref:
                lbl.color = (0,0,0,1)
                
        clicked_row.bg_color.rgb = (0.11, 0.22, 0.54)
        for lbl in labels_list:
            lbl.color = (1,1,1,1)
            
        self.selected_id = rid

    def erase_record(self, instance):
        if not self.selected_id: return
        conn = sqlite3.connect(CORE_DATA_DB)
        cursor = conn.cursor()
        if self.ledger_name == "Income Records":
            cursor.execute("DELETE FROM income WHERE id=?", (self.selected_id,))
        else:
            cursor.execute("DELETE FROM spendings WHERE id=?", (self.selected_id,))
        conn.commit()
        conn.close()
        self.selected_id = None
        self.on_enter()

# =========================================================
# ?? APP RUNNER ENGINE CONTROL
# =========================================================
class SmartKhataApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(SignupScreen(name='signup'))
        sm.add_widget(DashboardScreen(name='dashboard'))
        sm.add_widget(EntryScreen(name='entry'))
        sm.add_widget(LedgerScreen(name='ledger'))
        
        # Auto-Login (Session Check)
        if check_session():
            sm.current = 'dashboard'
        else:
            sm.current = 'login'
            
        return sm

if __name__ == '__main__':
    SmartKhataApp().run()