import streamlit as st
import sqlite3
import requests
from datetime import datetime
import pytz

# ==========================================
# 1. การจัดการฐานข้อมูล SQLite (โครงสร้างใหม่)
# ==========================================
def init_db():
    conn = sqlite3.connect("attendance_system.db")
    c = conn.cursor()
    
    # ตารางผู้ใช้งาน (เพิ่ม ชื่อ และ รหัสนักศึกษา)
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password TEXT, name TEXT, student_id TEXT, discord_webhook TEXT)''')
    
    # ตารางรายวิชา (เพิ่ม หน่วยกิต และ ช่องทางติดต่อผู้สอน)
    c.execute('''CREATE TABLE IF NOT EXISTS subjects
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, subject_code TEXT, 
                  credits INTEGER, max_absences INTEGER, leaves_per_absence INTEGER, teacher_contact TEXT)''')
    
    # ตารางประวัติการบันทึก (ใหม่: เก็บประวัติรายวัน)
    c.execute('''CREATE TABLE IF NOT EXISTS attendance_records
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, subject_id INTEGER, record_date TEXT, status TEXT)''')
    
    conn.commit()
    return conn

conn = init_db()

def get_current_time():
    tz = pytz.timezone('Asia/Bangkok')
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")

# ==========================================
# 2. ฟังก์ชันแจ้งเตือน Discord Webhook
# ==========================================
def send_discord_alert(webhook_url, subject_code, risk_level):
    if not webhook_url:
        return False
    
    if risk_level == "red":
        msg = f"🚨 **วิกฤต (ต้องตรวจสอบ)!**\nวิชา **{subject_code}** ของคุณโควตาขาดเรียนหมดแล้ว มีความเสี่ยงหมดสิทธิ์สอบสูง กรุณาติดต่อผู้สอน!"
    elif risk_level == "yellow":
        msg = f"⚠️ **เฝ้าระวัง!**\nวิชา **{subject_code}** ของคุณขาดเรียนใกล้ถึงเกณฑ์แล้ว (เหลือโควตา 1-2 ครั้ง)"
    else:
        msg = f"ℹ️ **อัปเดต:** มีการบันทึกประวัติใหม่ในวิชา **{subject_code}**"
        
    try:
        requests.post(webhook_url, json={"content": msg})
        return True
    except Exception:
        return False

# ==========================================
# 3. หน้าจอหลักและการตั้งค่า Streamlit
# ==========================================
st.set_page_config(page_title="ระบบติดตามและเตือนความเสี่ยงหมดสิทธิ์สอบ", page_icon="📊", layout="wide")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

# ------------------------------------------
# ระบบ ล็อกอิน / สมัครสมาชิก
# ------------------------------------------
if not st.session_state.logged_in:
    st.title("🔒 เข้าสู่ระบบ / สร้างบัญชี")
    st.markdown("ระบบติดตามและเตือนความเสี่ยงหมดสิทธิ์สอบ")
    
    tab1, tab2 = st.tabs(["เข้าสู่ระบบ", "สร้างบัญชีใหม่"])
    
    with tab1:
        username = st.text_input("ชื่อผู้ใช้ (Username)", key="login_user")
        password = st.text_input("รหัสผ่าน (Password)", type="password", key="login_pass")
        if st.button("เข้าสู่ระบบ"):
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
            user = c.fetchone()
            if user:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("เข้าสู่ระบบสำเร็จ!")
                st.rerun()
            else:
                st.error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")
                
    with tab2:
        new_user = st.text_input("ชื่อผู้ใช้ (Username)")
        new_pass = st.text_input("รหัสผ่าน (Password)", type="password")
        new_name = st.text_input("ชื่อ-นามสกุล")
        new_student_id = st.text_input("รหัสนักศึกษา")
        webhook = st.text_input("Discord Webhook URL (เพื่อรับแจ้งเตือน)")
        
        if st.button("สมัครสมาชิก"):
            if new_user and new_pass and new_name:
                c = conn.cursor()
                try:
                    c.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", (new_user, new_pass, new_name, new_student_id, webhook))
                    conn.commit()
                    st.success("ลงทะเบียนสำเร็จ! กรุณาเข้าสู่ระบบ")
                except sqlite3.IntegrityError:
                    st.error("ชื่อผู้ใช้นี้มีอยู่ในระบบแล้ว")
            else:
                st.warning("กรุณากรอกข้อมูลให้ครบถ้วน")

# ------------------------------------------
# หน้าแดชบอร์ดหลัก (Dashboard)
# ------------------------------------------
else:
    c = conn.cursor()
    c.execute("SELECT name, student_id, discord_webhook FROM users WHERE username=?", (st.session_state.username,))
    user_info = c.fetchone()
    user_name, user_student_id, user_webhook = user_info if user_info else ("Unknown", "Unknown", "")

    st.sidebar.title(f"👤 {user_name}")
    st.sidebar.caption(f"รหัสนักศึกษา: {user_student_id}")
    
    if st.sidebar.button("ออกจากระบบ"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

    st.title("📊 แดชบอร์ดติดตามความเสี่ยงหมดสิทธิ์สอบ")

    # ฟอร์มเพิ่มวิชาใหม่
    with st.expander("➕ เพิ่มรายวิชาใหม่"):
        with st.form("add_subject_form"):
            col1, col2 = st.columns(2)
            with col1:
                subject_code = st.text_input("รหัสวิชา / ชื่อวิชา")
                credits = st.number_input("หน่วยกิต", min_value=1, value=3)
                max_absences = st.number_input("จำกัดขาดเรียนได้สูงสุด (ครั้ง)", min_value=1, value=3)
            with col2:
                leaves_per_absence = st.number_input("ลาเรียนกี่ครั้ง = ขาด 1 ครั้ง", min_value=1, value=2)
                teacher_contact = st.text_input("ช่องทางติดต่อผู้สอน (อีเมล, เบอร์, Line)")
            submit = st.form_submit_button("บันทึกข้อมูลวิชา")
            
            if submit and subject_code:
                c.execute("""INSERT INTO subjects (username, subject_code, credits, max_absences, leaves_per_absence, teacher_contact) 
                             VALUES (?, ?, ?, ?, ?, ?)""", 
                          (st.session_state.username, subject_code, credits, max_absences, leaves_per_absence, teacher_contact))
                conn.commit()
                st.success(f"เพิ่มวิชา {subject_code} เรียบร้อยแล้ว")
                st.rerun()

    st.divider()
    st.subheader("📋 สถานะรายวิชาทั้งหมด")
    
    c.execute("SELECT * FROM subjects WHERE username=?", (st.session_state.username,))
    subjects = c.fetchall()

    if not subjects:
        st.info("ยังไม่มีข้อมูลรายวิชา กรุณาเพิ่มรายวิชาด้านบน")
    else:
        for sub in subjects:
            sub_id, _, sub_code, credits, max_abs, leaves_ratio, teacher_contact = sub
            
            # คำนวณจากประวัติรายวัน
            c.execute("SELECT count(*) FROM attendance_records WHERE subject_id=? AND status='ขาด'", (sub_id,))
            curr_abs = c.fetchone()[0]
            c.execute("SELECT count(*) FROM attendance_records WHERE subject_id=? AND status='ลา'", (sub_id,))
            curr_leaves = c.fetchone()[0]
            
            # หาระยะเวลาอัปเดตล่าสุด
            c.execute("SELECT MAX(record_date) FROM attendance_records WHERE subject_id=?", (sub_id,))
            last_update = c.fetchone()[0]
            last_update_str = last_update if last_update else "ยังไม่มีการบันทึก"

            # ประเมินความเสี่ยง 3 ระดับ
            effective_absences = curr_abs + (curr_leaves // leaves_ratio)
            rem_abs = max_abs - effective_absences

            if rem_abs > 2:
                risk_status = "🟢 ปกติ (เข้าเรียนสม่ำเสมอ)"
                card_color = "success"
                alert_type = "green"
            elif rem_abs > 0:
                risk_status = "🟡 เฝ้าระวัง (ขาดเรียนใกล้ถึงเกณฑ์)"
                card_color = "warning"
                alert_type = "yellow"
            else:
                risk_status = "🔴 ต้องตรวจสอบ (เสี่ยงหมดสิทธิ์สอบ)"
                card_color = "error"
                alert_type = "red"

            # สร้างการ์ดแสดงผล
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"### 📘 {sub_code} ({credits} หน่วยกิต)")
                    st.markdown(f"**สถานะ:** {risk_status}")
                    st.caption(f"อัปเดตล่าสุด: {last_update_str}")
                with c2:
                    st.metric(label="โควตาขาดได้อีก (ครั้ง)", value=rem_abs if rem_abs > 0 else 0, delta=f"ขาดไปแล้ว {effective_absences} ครั้ง", delta_color="inverse")

                with st.expander("รายละเอียด / ประวัติการเรียน / แจ้งวันลา"):
                    c_det1, c_det2 = st.columns([1, 1])
                    
                    with c_det1:
                        st.markdown(f"**ช่องทางติดต่อผู้สอน:** {teacher_contact if teacher_contact else 'ไม่ได้ระบุ'}")
                        st.markdown(f"**เกณฑ์วิชา:** ขาดได้สูงสุด {max_abs} ครั้ง (ลา {leaves_ratio} ครั้ง = ขาด 1)")
                        
                        st.markdown("#### บันทึกการเข้าเรียน")
                        col_btn1, col_btn2 = st.columns(2)
                        with col_btn1:
                            if st.button("บันทึก 'ขาด'", key=f"abs_{sub_id}", use_container_width=True):
                                c.execute("INSERT INTO attendance_records (subject_id, record_date, status) VALUES (?, ?, ?)", (sub_id, get_current_time(), "ขาด"))
                                conn.commit()
                                # เช็คสถานะหลังเพิ่ม เพื่อแจ้งเตือน
                                new_eff = (curr_abs + 1) + (curr_leaves // leaves_ratio)
                                new_rem = max_abs - new_eff
                                if new_rem <= 0:
                                    send_discord_alert(user_webhook, sub_code, "red")
                                elif new_rem in [1, 2]:
                                    send_discord_alert(user_webhook, sub_code, "yellow")
                                st.rerun()
                        with col_btn2:
                            if st.button("บันทึก 'ลา'", key=f"leave_{sub_id}", use_container_width=True):
                                c.execute("INSERT INTO attendance_records (subject_id, record_date, status) VALUES (?, ?, ?)", (sub_id, get_current_time(), "ลา"))
                                conn.commit()
                                st.rerun()
                        
                        if st.button("🗑️ ลบรายวิชานี้", key=f"del_{sub_id}", type="primary"):
                            c.execute("DELETE FROM subjects WHERE id=?", (sub_id,))
                            c.execute("DELETE FROM attendance_records WHERE subject_id=?", (sub_id,))
                            conn.commit()
                            st.rerun()

                    with c_det2:
                        st.markdown("#### ประวัติรายวัน")
                        c.execute("SELECT record_date, status FROM attendance_records WHERE subject_id=? ORDER BY record_date DESC", (sub_id,))
                        records = c.fetchall()
                        if not records:
                            st.write("ยังไม่มีประวัติการบันทึก")
                        else:
                            import pandas as pd
                            df = pd.DataFrame(records, columns=["วันเวลา", "สถานะ"])
                            st.dataframe(df, use_container_width=True, hide_index=True)