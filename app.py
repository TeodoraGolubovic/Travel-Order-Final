import streamlit as st
import pandas as pd
import os
import sqlite3
import datetime
from PIL import Image
from fpdf import FPDF
from PyPDF2 import PdfMerger
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import datetime

# Konfiguracija stranice
st.set_page_config(page_title="Obračun dnevnice i refundacija", layout="wide")

# Konekcija sa SQLite bazom
DB_FILE = "troskovi.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS troskovi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ime TEXT,
            odobrio TEXT,
            kategorija TEXT,
            iznos REAL,
            valuta TEXT,
            fajlovi TEXT
        )
    ''')
    conn.commit()
    conn.close()

def reset_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM troskovi")  # Briše sve podatke iz tabele
    conn.commit()
    conn.close()
    st.session_state.troskovi = pd.DataFrame(columns=["kategorija", "Ukupno Iznos", "Fajlovi"])
    st.session_state.app_started = True
    st.session_state.dnevnica_dodata = False  # Dodato da spreči dupliranje dnevnice

init_db()

# Inicijalizacija sesije
if "app_started" not in st.session_state:
    st.session_state.app_started = False
if "troskovi" not in st.session_state:
    st.session_state.troskovi = pd.DataFrame(columns=["kategorija", "Ukupno Iznos", "Fajlovi"])
if "dnevnica" not in st.session_state:
    st.session_state.dnevnica = 0
if "dnevnica_dodata" not in st.session_state:
    st.session_state.dnevnica_dodata = False

# Dugme za pokretanje aplikacije
if st.button("Pokreni aplikaciju"):
    reset_db()
    st.success("Aplikacija je uspešno pokrenuta! Baza je resetovana.")

# Sakrivanje polja dok se aplikacija ne pokrene
if st.session_state.app_started:
    st.title("Obračun dnevnice")
    
    pocetak = st.date_input("Datum početka putovanja")
    vreme_pocetka = st.time_input("Vreme početka putovanja")
    
    kraj = st.date_input("Datum kraja putovanja")
    vreme_kraja = st.time_input("Vreme kraja putovanja")
    
    if st.button("Obračunaj dnevnicu"):
        pocetak_datetime = datetime.datetime.combine(pocetak, vreme_pocetka)
        kraj_datetime = datetime.datetime.combine(kraj, vreme_kraja)
        trajanje = (kraj_datetime - pocetak_datetime).total_seconds() / 3600  # Trajanje u satima
        
        pune_dnevnice = int(trajanje // 24) * 3012
        preostali_sati = trajanje % 24
        
        if preostali_sati < 8:
            dodatna_dnevnica = 0
        elif preostali_sati < 12:
            dodatna_dnevnica = 1506
        else:
            dodatna_dnevnica = 3012
        
        ukupna_dnevnica = pune_dnevnice + dodatna_dnevnica
        
        if not st.session_state.dnevnica_dodata:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute(
                "INSERT INTO troskovi (ime, odobrio, kategorija, iznos, valuta, fajlovi) VALUES (?, ?, ?, ?, ?, ?)",
                ("", "", "Dnevnica (52902)", ukupna_dnevnica, "RSD", "")
            )
            conn.commit()
            conn.close()
            st.session_state.dnevnica_dodata = True  # Obeleži da je dnevnica dodata
        
        
	   # Osvežavanje podataka nakon dodavanja dnevnice
        df_conn = sqlite3.connect(DB_FILE)
        st.session_state.troskovi = pd.read_sql_query("SELECT id, kategorija, iznos as 'Ukupno Iznos', fajlovi FROM troskovi", df_conn)
        df_conn.close()
	
        st.rerun()  # Osveži aplikaciju da prikaže ažurirane podatke
        

        
    
    st.title("Zahtev za refundiranje troškova")
    
    ime_prezime = st.text_input("Ime i prezime")
    odobrio = st.text_input("Osoba koja je odobrila", placeholder="Obavezno polje")
    
    kategorija = st.selectbox("Kategorija troška:", [
        "Prevoz, taxi (529111)",
        "Gorivo (51300)",
        "Putarine (53940)",
        "Reprezentacija, kurirska dostava (55100)",
        "Ostali troškovi - npr. parking, hotel (55900)"
    ])
    
    iznos_str = st.text_input("Iznos", value="", placeholder="Unesite iznos u RSD")
    
    try:
        iznos = float(iznos_str) if iznos_str.strip() else None  # None znači da korisnik mora uneti broj
    except ValueError:
        st.warning("Unesite validan broj za iznos.")
        iznos = None
    valuta = "RSD"
    
    # Upload jednog fajla
    uploaded_file = st.file_uploader("Otpremite račun", type=["pdf", "jpg", "png"], accept_multiple_files=False)
    
    # Dodavanje troška
    if st.button("Dodaj trošak"):
        if not odobrio or not uploaded_file:
            st.warning("Morate uneti osobu koja je odobrila i dodati račun.")
        else:
            file_path = os.path.join("uploads", uploaded_file.name)
            os.makedirs("uploads", exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute(
                "INSERT INTO troskovi (ime, odobrio, kategorija, iznos, valuta, fajlovi) VALUES (?, ?, ?, ?, ?, ?)",
                (ime_prezime, odobrio, kategorija, iznos, valuta, file_path)
            )
            conn.commit()
            conn.close()
            
           # Osvježavanje podataka
            df_conn = sqlite3.connect(DB_FILE)
            st.session_state.troskovi = pd.read_sql_query("SELECT id, kategorija, iznos as 'Ukupno Iznos', fajlovi FROM troskovi", df_conn)
            df_conn.close()
            
            st.success("Trošak dodat!")

    # Prikaz tabele troškova sa dugmetom za brisanje
    df = st.session_state.troskovi.copy()
    
    if not df.empty:
        for index, row in df.iterrows():
            col1, col2 = st.columns([4, 1])  # Postavljanje kolona, prva za podatke, druga za dugme za brisanje
            with col1:
                st.write(f"{row['kategorija']} - {row['Ukupno Iznos']} RSD")
            with col2:
                if st.button("❌", key=f"remove_{row['id']}"):
                    conn = sqlite3.connect(DB_FILE)
                    c = conn.cursor()
                    c.execute("DELETE FROM troskovi WHERE id = ?", (row["id"],))
                    conn.commit()
                    conn.close()
                    
                    df_conn = sqlite3.connect(DB_FILE)
                    st.session_state.troskovi = pd.read_sql_query("SELECT id, kategorija, iznos as 'Ukupno Iznos', fajlovi FROM troskovi", df_conn)
                    df_conn.close()
                    st.rerun()
    
    # Prikaz finalne tabele bez dodatnog dupliranja
    st.dataframe(st.session_state.troskovi)
else:
    st.warning("Kliknite na 'Pokreni aplikaciju' da biste započeli unos podataka.")


from hashlib import md5
from PIL import Image
from fpdf import FPDF
import os

# Dozvoliti učitavanje velikih slika
Image.MAX_IMAGE_PIXELS = None

# Funkcija za dobijanje hash vrednosti slike
def get_image_hash(image_path):
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGB") 
            return md5(img.tobytes()).hexdigest()
    except:
        return None  # Ako postoji greska, preskoci sliku

if st.button("Preuzmi PDF"):
    if df.empty:
        st.warning("Nema podataka za izveštaj.")
    else:
        pdf_path = f"uploads/izvestaj_{datetime.date.today()}.pdf"

        # Kreiranje PDF-a sa troškovima
        c = canvas.Canvas(pdf_path, pagesize=letter)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, 750, "ZAHTEV ZA REFUNDIRANJE TROŠKOVA")
        c.setFont("Helvetica", 12)
        c.drawString(50, 730, f"Podnosilac zahteva: {ime_prezime}")
        c.drawString(50, 710, f"Odobrio: {odobrio}")
        c.drawString(50, 690, f"Datum zahteva: {datetime.date.today()}")

        y = 660
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, "Sumirani troškovi po kategorijama:")
        y -= 20

        for _, row in df.iterrows():
            c.setFont("Helvetica", 11)
            c.drawString(50, y, f"{row['kategorija']}: {row['Ukupno Iznos']} RSD")
            y -= 20

        ukupno = df["Ukupno Iznos"].sum()
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, y, f"UKUPNO: {ukupno} RSD")

        c.save()

        # **Dodavanje slika i PDF računa u jedan PDF**
        merger = PdfMerger()
        merger.append(pdf_path)

        seen_hashes = set()  # Skup za praćenje hash vrednosti slika

        for _, row in df.iterrows():
            if row["fajlovi"]:
                for file_path in row["fajlovi"].split(","):
                    file_path = file_path.strip()

                    if file_path.endswith((".jpg", ".jpeg", ".png")):
                        try:
                            img_hash = get_image_hash(file_path)
                            if img_hash is None or img_hash in seen_hashes:
                                continue  # Preskačemo ako ne može da se otvori ili ako je duplikat

                            seen_hashes.add(img_hash)

                            img = Image.open(file_path).convert("RGB")

                            # **Provera i ispravljanje orijentacije slike**
                            try:
                                exif = img._getexif()
                                if exif is not None:
                                    orientation = exif.get(0x0112)
                                    if orientation == 3:
                                        img = img.rotate(180, expand=True)
                                    elif orientation == 6:
                                        img = img.rotate(270, expand=True)
                                    elif orientation == 8:
                                        img = img.rotate(90, expand=True)
                            except AttributeError:
                                pass  # Ako nema EXIF podataka, ne rotiramo

                            # **Priprema za PDF**
                            img_width, img_height = img.size
                            a4_width, a4_height = 210, 297  # A4 format u mm

                            # Ako je slika veća od A4, smanji je proporcionalno
                            scale = min(a4_width / img_width, a4_height / img_height, 1)  # Maksimalno 1 (ne povećavaj)
                            new_width = img_width * scale
                            new_height = img_height * scale

                            # Čuvaj optimizovanu sliku
                            optimized_img_path = f"uploads/optimized_{os.path.basename(file_path)}.jpg"
                            img.save(optimized_img_path, "JPEG", quality=90)

                            # Kreiranje PDF-a sa originalnim dimenzijama
                            img_pdf_path = f"uploads/temp_{os.path.basename(file_path)}.pdf"
                            pdf = FPDF(unit="mm", format="A4")
                            pdf.add_page()

                            # Centriranje slike na A4 strani
                            x_offset = (a4_width - new_width) / 2
                            y_offset = (a4_height - new_height) / 2

                            pdf.image(optimized_img_path, x=x_offset, y=y_offset, w=new_width, h=new_height)
                            pdf.output(img_pdf_path, "F")

                            merger.append(img_pdf_path)

                        except:
                            continue  # Ako slika ne može da se učita, preskačemo


        merger.write(pdf_path)
        merger.close()

        with open(pdf_path, "rb") as f:
            st.download_button("Preuzmi PDF izveštaj", f, file_name=f"izvestaj_{datetime.date.today()}.pdf")