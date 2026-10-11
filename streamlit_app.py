import streamlit as st
import sqlite3
import requests

# ==========================================
# 1. การจัดการฐานข้อมูล SQLite
# ==========================================
def init_db():
    conn = sqlite3.connect("attendance_system.db")
    c = conn.cursor()
    
    # ตารางผู้ใช้งาน
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password TEXT, discord_webhook TEXT)''')
    
    # ตารางรายวิชา
    c.execute('''CREATE TABLE IF NOT EXISTS subjects
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, subject_code TEXT, 
                  max_absences INTEGER, leaves_per_absence INTEGER, 
                  current_absences INTEGER DEFAULT 0, current_leaves INTEGER DEFAULT 0)''')
    
    conn.commit()
    return conn

conn = init_db()

# ==========================================
# 2. ฟังก์ชันแจ้งเตือน Discord Webhook
# ==========================================
def send_discord_alert(webhook_url, subject_code, msg_type="warning"):
    if not webhook_url:
        return False
    
    if msg_type == "warning":
        payload = {
            "content": f"⚠️ **คำเตือนสิทธิ์สอบ!**\nวิชา **{subject_code}** ของคุณใกล้/หมดสิทธิ์สอบแล้ว กรุณาตรวจสอบจำนวนวันขาดเรียนโดยด่วน!"
        }
    else:
        payload = {
            "content": f"ℹ️ **อัปเดตการเข้าเรียน:** วิชา **{subject_code}** มีการบันทึกขาด/ลา เพิ่มเติม"
        }
        
    try:
        requests.post(webhook_url, json=payload)
        return True
    except Exception:
        return False

# ==========================================
# 3. หน้าจอหลักและการตั้งค่า Streamlit
# ==========================================
st.set_page_config(page_title="ระบบติดตามและเตือนหมดสิทธิ์สอบ", page_icon="🚨", layout="centered")

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

# ------------------------------------------
# ระบบ ล็อกอิน / สมัครสมาชิก
# ------------------------------------------
if not st.session_state.logged_in:
    st.title("🔒 เข้าสู่ระบบ / สร้างบัญชี")
    
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
        new_user = st.text_input("ชื่อผู้ใช้ใหม่ (Username)", key="reg_user")
        new_pass = st.text_input("รหัสผ่านใหม่ (Password)", type="password", key="reg_pass")
        webhook = st.text_input("Discord Webhook URL (ใส่หรือไม่ใส่ก็ได้)", key="reg_webhook")
        
        if st.button("สมัครสมาชิก"):
            if new_user and new_pass:
                c = conn.cursor()
                try:
                    c.execute("INSERT INTO users VALUES (?, ?, ?)", (new_user, new_pass, webhook))
                    conn.commit()
                    st.success("ลงทะเบียนสำเร็จ! กรุณาเข้าสู่ระบบ")
                except sqlite3.IntegrityError:
                    st.error("ชื่อผู้ใช้นี้มีอยู่ในระบบแล้ว")
            else:
                st.warning("กรุณากรอกข้อมูลให้ครบถ้วน")

# ------------------------------------------
# หน้าจัดการรายวิชาและวันขาดเรียน
# ------------------------------------------
else:
    st.sidebar.title(f"👤 สวัสดี: {st.session_state.username}")
    
    # ดึง Webhook ของผู้ใช้
    c = conn.cursor()
    c.execute("SELECT discord_webhook FROM users WHERE username=?", (st.session_state.username,))
    user_info = c.fetchone()
    user_webhook = user_info[0] if user_info else ""

    if st.sidebar.button("ออกจากระบบ"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()

    st.title("📚 ระบบติดตามวันขาดเรียน & เตือนหมดสิทธิ์สอบ")

    # ฟอร์มเพิ่มวิชาใหม่
    with st.expander("➕ เพิ่มรายวิชาใหม่"):
        with st.form("add_subject_form"):
            subject_code = st.text_input("ชื่อวิชา / รหัสวิชา")
            max_absences = st.number_input("จำกัดขาดเรียนได้สูงสุด (ครั้ง)", min_value=1, value=3)
            leaves_per_absence = st.number_input("จำนวนครั้งที่ 'ลา' เท่ากับขาด 1 ครั้ง", min_value=1, value=2)
            submit = st.form_submit_button("บันทึกวิชา")
            
            if submit and subject_code:
                c.execute("""INSERT INTO subjects (username, subject_code, max_absences, leaves_per_absence) 
                             VALUES (?, ?, ?, ?)""", 
                          (st.session_state.username, subject_code, max_absences, leaves_per_absence))
                conn.commit()
                st.success(f"เพิ่มวิชา {subject_code} เรียบร้อยแล้ว")
                st.rerun()

    # แสดงรายการวิชา
    st.subheader("📋 รายวิชาที่กำลังติดตาม")
    c.execute("SELECT * FROM subjects WHERE username=?", (st.session_state.username,))
    subjects = c.fetchall()

    if not subjects:
        st.info("ยังไม่มีรายวิชาที่บันทึกไว้ ให้กด 'เพิ่มรายวิชาใหม่' ด้านบนครับ")
    else:
        for sub in subjects:
            sub_id, _, sub_code, max_abs, leaves_ratio, curr_abs, curr_leaves = sub
            
            # คำนวณขาดเรียนสุทธิจากการลา
            effective_absences = curr_abs + (curr_leaves // leaves_ratio)
            rem_abs = max_abs - effective_absences

            with st.container():
                col1, col2, col3 = st.columns([3, 2, 2])
                
                with col1:
                    st.markdown(f"### 📘 {sub_code}")
                    st.write(f"ขาดได้สูงสุด: **{max_abs}** ครั้ง | ลา {leaves_ratio} ครั้ง = ขาด 1 ครั้ง")
                    st.write(f"บันทึกแล้ว: ขาด **{curr_abs}** ครั้ง | ลา **{curr_leaves}** ครั้ง (รวมคิดเป็นขาด **{effective_absences}** ครั้ง)")
                
                with col2:
                    if rem_abs <= 0:
                        st.error("🚨 หมดสิทธิ์สอบ!")
                    elif rem_abs == 1:
                        st.warning("⚠️ เตือน: ขาดได้อีก 1 ครั้ง")
                    else:
                        st.success(f"✅ ขาดได้อีก {rem_abs} ครั้ง")

                with col3:
                    # ปุ่มเพิ่มขาด/ลา
                    if st.button("➕ ขาดเรียน", key=f"abs_{sub_id}"):
                        new_abs = curr_abs + 1
                        c.execute("UPDATE subjects SET current_absences=? WHERE id=?", (new_abs, sub_id))
                        conn.commit()
                        
                        # แจ้งเตือน Discord
                        new_effective = new_abs + (curr_leaves // leaves_ratio)
                        if (max_abs - new_effective) <= 1:
                            send_discord_alert(user_webhook, sub_code, "warning")
                        st.rerun()

                    if st.button("➕ ลาเรียน", key=f"leave_{sub_id}"):
                        new_leaves = curr_leaves + 1
                        c.execute("UPDATE subjects SET current_leaves=? WHERE id=?", (new_leaves, sub_id))
                        conn.commit()
                        st.rerun()

                    if st.button("🗑️ ลบวิชา", key=f"del_{sub_id}"):
                        c.execute("DELETE FROM subjects WHERE id=?", (sub_id,))
                        conn.commit()
                        st.rerun()
                
                st.divider()