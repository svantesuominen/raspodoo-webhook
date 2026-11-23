import pigpio
import time
from flask import Flask, request
import random

# --- LAITTEISTOASETUKSET ---
# GPIO 18 (Fyysinen pinni 12) = Servo
# GPIO 13 (Fyysinen pinni 33) = Piezo (Summeri)
# GPIO 23 (Fyysinen pinni 16) = This Is Fine trigger
SERVO_PIN = 18
PIEZO_PIN = 13
THISISFINE_PIN = 23
SERVO_FREQ = 50
THISISFINE_PULSE_S = 0.4 

# --- KALIBROINTI (Testattu toimivaksi) ---
LEPO_ASENTO = 50000   # Ylhäällä
ISKU_ASENTO = 100000  # Alhaalla (lyönti)

pi = pigpio.pi()
app = Flask(__name__)

# Browser soundboard (Cloudflare Pages / localhost) needs CORS + OPTIONS preflight.
# Custom header ngrok-skip-browser-warning forces a preflight that curl never sends.
@app.after_request
def apply_cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, ngrok-skip-browser-warning'
    return response


@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def cors_preflight(path):
    return ('', 204)

# --- APUFUNKTIOT ---

def soita_kelloa(toistot):
    """ Liikuttaa servoa lepo- ja iskuasentojen välillä """
    
    # LIIKENOPEUS: 0.3s antaa servolle aikaa tehdä laaja liike
    sleep_time = 0.3
    
    print(f"[SERVO] Lyödään {toistot} kertaa...")
    
    for _ in range(toistot):
        # 1. Isku (Alas)
        pi.hardware_PWM(SERVO_PIN, SERVO_FREQ, ISKU_ASENTO) 
        time.sleep(sleep_time)
        
        # 2. Palautus (Ylös)
        pi.hardware_PWM(SERVO_PIN, SERVO_FREQ, LEPO_ASENTO)
        time.sleep(sleep_time)
        
        # Tauko lyöntien välissä (jotta ehtii palautua ja soida)
        if toistot > 1:
            time.sleep(0.5)
    
    # Lopuksi rentoutus (virta pois servosta)
    pi.hardware_PWM(SERVO_PIN, 0, 0)

def soita_melodia(tyyppi):
    """ Soittaa ääniä piezolla """
    print(f"[PIEZO] Soitetaan ääni: {tyyppi}")
    VOL = 500000 # 50% duty cycle (max volume)
    
    if tyyppi == 'success':
        # Fanfaari
        nuotit = [523, 659, 784, 1046] 
        for nuotti in nuotit:
            pi.hardware_PWM(PIEZO_PIN, nuotti, VOL)
            time.sleep(0.1)
        time.sleep(0.2)

    elif tyyppi == 'coin':
        # Super Mario Coin
        pi.hardware_PWM(PIEZO_PIN, 988, VOL)
        time.sleep(0.08)
        pi.hardware_PWM(PIEZO_PIN, 1319, VOL)
        time.sleep(0.3)

    elif tyyppi == 'alert':
        # Sireeni
        for f in range(500, 1500, 50):
            pi.hardware_PWM(PIEZO_PIN, f, VOL)
            time.sleep(0.01)
        for f in range(1500, 500, -50):
            pi.hardware_PWM(PIEZO_PIN, f, VOL)
            time.sleep(0.01)

    elif tyyppi == 'r2d2':
        # Robotti
        for _ in range(8):
            taajuus = random.randint(1000, 3000)
            kesto = random.uniform(0.05, 0.15)
            pi.hardware_PWM(PIEZO_PIN, taajuus, VOL)
            time.sleep(kesto)
            pi.hardware_PWM(PIEZO_PIN, 0, 0)
            time.sleep(0.05)

    elif tyyppi == 'startup':
        # Nouseva liuku (Super Mario Power Up tyyliin)
        for f in range(200, 2000, 40):
            pi.hardware_PWM(PIEZO_PIN, f, VOL)
            time.sleep(0.01)

    elif tyyppi == 'birthday':
        # Happy Birthday -nuotit (Hz) ja kestot (s)
        # G4, G4, A4, G4, C5, B4...
        birthday = [
            (392, 0.15), (392, 0.15), (440, 0.3), (392, 0.3), (523, 0.3), (494, 0.6), # "Happy birthday to you"
            (392, 0.15), (392, 0.15), (440, 0.3), (392, 0.3), (587, 0.3), (523, 0.6), # "Happy birthday to you"
            (392, 0.15), (392, 0.15), (784, 0.3), (659, 0.3), (523, 0.3), (494, 0.3), (440, 0.3), # "Happy birthday dear [Odoo]"
            (698, 0.15), (698, 0.15), (659, 0.3), (523, 0.3), (587, 0.3), (523, 0.6)  # "Happy birthday to you"
        ]
        
        for freq, kesto in birthday:
            pi.hardware_PWM(PIEZO_PIN, freq, VOL)
            time.sleep(kesto)
            # Katkaistaan ääni hetkeksi, jotta nuotit erottuvat
            pi.hardware_PWM(PIEZO_PIN, 0, 0)
            time.sleep(0.05)

    elif tyyppi == 'startreck':
        # Star Trek Theme (TNG)
        # Säädä tempoa tarvittaessa (120-150 on hyvä)
        tempo = 140
        wholenote = (60 / tempo) * 4
        notes = {
            'C4': 262, 'G3': 196, 'F4': 349, 'E4': 330, 'A3': 220, 
            'D4': 294, 'G4': 392, 'A4': 440, 'B4': 494, 'C5': 523
        }
        melody = [
            (notes['C4'], 4), (notes['G3'], 8), (notes['C4'], 4), (notes['F4'], 8),
            (notes['E4'], 4), (notes['C4'], 8), (notes['A3'], 4), (notes['D4'], 8),
            (notes['G3'], 2), (notes['C4'], 4), (notes['G3'], 8), (notes['C4'], 4),
            (notes['F4'], 8), (notes['E4'], 4), (notes['C4'], 8), (notes['A3'], 4),
            (notes['D4'], 8), (notes['G3'], 2), (notes['C5'], 4), (notes['B4'], 8),
            (notes['G4'], 4), (notes['E4'], 8), (notes['A4'], 4), (notes['G4'], 8),
            (notes['E4'], 4), (notes['C4'], 8), (notes['D4'], 2), (notes['C4'], 4),
            (notes['G3'], 8), (notes['C4'], 4), (notes['F4'], 8), (notes['E4'], 4),
            (notes['C4'], 8), (notes['A3'], 4), (notes['D4'], 8), (notes['G3'], 2)
        ]
        for freq, duration in melody:
            note_duration = wholenote / duration
            pi.hardware_PWM(PIEZO_PIN, freq, VOL)
            time.sleep(note_duration * 0.8)
            pi.hardware_PWM(PIEZO_PIN, 0, 0)
            time.sleep(note_duration * 0.2)

    elif tyyppi == 'imperial':
        # Star Wars - Imperial March
        # Nuotit (Hz) ja kestot (s)
        march = [
            (392, 0.4), (392, 0.4), (392, 0.4), (311, 0.3), (466, 0.1),
            (392, 0.4), (311, 0.3), (466, 0.1), (392, 0.7),
            (587, 0.4), (587, 0.4), (587, 0.4), (622, 0.3), (466, 0.1),
            (370, 0.4), (311, 0.3), (466, 0.1), (392, 0.7)
        ]
        for freq, kesto in march:
            pi.hardware_PWM(PIEZO_PIN, freq, VOL)
            time.sleep(kesto)
            pi.hardware_PWM(PIEZO_PIN, 0, 0)
            time.sleep(0.05)

    elif tyyppi == 'jingle':
        # Jingle Bells - chorus
        # E4=330, G4=392, C4=262, D4=294, F4=349, C5=523
        jingle = [
            (330, 0.2), (330, 0.2), (330, 0.4),
            (330, 0.2), (330, 0.2), (330, 0.4),
            (330, 0.2), (392, 0.2), (262, 0.3), (294, 0.1), (330, 0.6),
            (349, 0.2), (349, 0.2), (349, 0.2), (349, 0.2),
            (349, 0.2), (330, 0.2), (330, 0.2), (330, 0.1), (330, 0.1),
            (330, 0.2), (294, 0.2), (294, 0.2), (330, 0.2), (294, 0.4), (392, 0.4),
            (330, 0.2), (330, 0.2), (330, 0.4),
            (330, 0.2), (330, 0.2), (330, 0.4),
            (330, 0.2), (392, 0.2), (262, 0.3), (294, 0.1), (330, 0.6),
            (349, 0.2), (349, 0.2), (349, 0.2), (349, 0.2),
            (349, 0.2), (330, 0.2), (330, 0.2), (330, 0.1), (330, 0.1),
            (392, 0.2), (392, 0.2), (349, 0.2), (294, 0.2), (262, 0.6),
        ]
        for freq, kesto in jingle:
            pi.hardware_PWM(PIEZO_PIN, freq, VOL)
            time.sleep(kesto)
            pi.hardware_PWM(PIEZO_PIN, 0, 0)
            time.sleep(0.04)

    elif tyyppi == 'maamme':
        # Maamme (Finnish national anthem) - opening phrases
        # Bb4=466, C5=523, D5=587, Eb5=622, A4=440, F4=349, G4=392
        maamme = [
            (466, 0.35), (466, 0.35), (523, 0.35), (587, 0.7),
            (622, 0.35), (587, 0.35), (523, 0.35), (466, 0.7),
            (440, 0.35), (466, 0.35), (523, 0.35), (349, 0.7),
            (466, 0.9),
            (466, 0.35), (466, 0.35), (523, 0.35), (587, 0.7),
            (622, 0.35), (587, 0.35), (523, 0.35), (466, 0.7),
            (440, 0.35), (466, 0.35), (523, 0.35), (349, 0.7),
            (466, 1.0),
        ]
        for freq, kesto in maamme:
            pi.hardware_PWM(PIEZO_PIN, freq, VOL)
            time.sleep(kesto)
            pi.hardware_PWM(PIEZO_PIN, 0, 0)
            time.sleep(0.05)

    elif tyyppi == 'finlandia':
        # Sibelius Finlandia - hymn motif
        # F4=349, G4=392, Ab4=415, Bb4=466, C5=523, E4=330, Eb4=311
        finlandia = [
            (349, 0.4), (349, 0.4), (392, 0.4), (415, 0.8),
            (466, 0.4), (415, 0.4), (392, 0.4), (349, 0.8),
            (330, 0.4), (349, 0.4), (392, 0.4), (262, 0.8),
            (349, 1.0),
            (349, 0.4), (349, 0.4), (392, 0.4), (415, 0.8),
            (466, 0.4), (415, 0.4), (392, 0.4), (349, 0.8),
            (311, 0.4), (349, 0.4), (392, 0.4), (523, 0.8),
            (349, 1.2),
        ]
        for freq, kesto in finlandia:
            pi.hardware_PWM(PIEZO_PIN, freq, VOL)
            time.sleep(kesto)
            pi.hardware_PWM(PIEZO_PIN, 0, 0)
            time.sleep(0.05)
    
    # Hiljennys
    pi.hardware_PWM(PIEZO_PIN, 0, 0)

def paivita_naytto(teksti, summa=None):
    print("--------------------------------")
    print(f"[DISPLAY] UUSI VIESTI:")
    print(f">> {teksti}")
    if summa:
        print(f">> Summa: {summa} EUR")
    print("--------------------------------")

def laukaise_thisisfine():
    """ Lähettää ~0.4s HIGH-pulssin This Is Fine -lelulle """
    print("[THISISFINE] This is fine...")
    pi.set_mode(THISISFINE_PIN, pigpio.OUTPUT)
    pi.write(THISISFINE_PIN, 1)
    time.sleep(THISISFINE_PULSE_S)
    pi.write(THISISFINE_PIN, 0)

def kaynnistyssekvenssi():
    """ Soittaa valmiussignaalin kun palvelu on käynnissä """
    print("[BOOT] Käynnistyssekvenssi: gong + thisisfine + piezo")
    soita_kelloa(1)
    time.sleep(0.3)
    laukaise_thisisfine()
    time.sleep(0.3)
    soita_melodia('startup')

# --- REITIT (ENDPOINTS) ---

@app.route('/servo', methods=['POST'])
def servo_control():
    # Lukee Odoon datan ja päättää lyöntien määrän
    data = request.get_json(silent=True)
    summa = 0
    if data and 'amount_untaxed' in data:
        summa = data['amount_untaxed']
    
    print(f"[SERVO] Kauppa: {summa} eur")
    
    viesti = ""
    if summa < 20000:
        toistot = 1
    else:
        toistot = int(summa // 10000)
    
    soita_kelloa(toistot)
    viesti = f"Kauppa vahvistettu ({toistot}x)"
        
    return f"Servo: {viesti}", 200

@app.route('/piezo', methods=['POST'])
def piezo_control():
    # Ensisijaisesti URL-parametrista: .../piezo?sound=coin
    sound_type = request.args.get('sound')
    
    # Varalta JSONista (silent: älä 415 jos Content-Type ei ole JSON)
    data = request.get_json(silent=True)
    if not sound_type and data and 'sound' in data:
        sound_type = data['sound']
    
    if not sound_type: sound_type = 'success'
        
    soita_melodia(sound_type)
    return f"Piezo: {sound_type}", 200

@app.route('/display', methods=['POST'])
def display_control():
    # Viesti URL-parametrista: .../display?msg=Teksti
    message = request.args.get('msg')
    
    data = request.get_json(silent=True)
    amount = None
    
    # Jos ei URL-viestiä, katsotaan Odoon dataa
    if not message and data and 'name' in data: 
        message = f"Tilaus {data['name']}"
    
    if data and 'amount_untaxed' in data:
        amount = data['amount_untaxed']
    
    if not message: message = "Odoo Webhook"

    paivita_naytto(message, amount)
    return f"Display: Päivitetty", 200

@app.route('/reset', methods=['POST'])
def reset_servo():
    print("Komento: Servo nolla-asentoon")
    pi.hardware_PWM(SERVO_PIN, SERVO_FREQ, LEPO_ASENTO)
    time.sleep(1.0) 
    pi.hardware_PWM(SERVO_PIN, 0, 0)
    return "Servo nollattu", 200

@app.route('/thisisfine', methods=['POST'])
def thisisfine_control():
    request.get_json(silent=True)
    laukaise_thisisfine()
    return "This is fine", 200

if __name__ == '__main__':
    if not pi.connected:
        print("VIRHE: Pigpio ei ole käynnissä! Aja 'sudo systemctl start pigpiod'.")
    else:
        # Alustus hiljaiseksi
        pi.hardware_PWM(SERVO_PIN, 0, 0)
        pi.hardware_PWM(PIEZO_PIN, 0, 0)
        pi.set_mode(THISISFINE_PIN, pigpio.OUTPUT)
        pi.write(THISISFINE_PIN, 0)
        kaynnistyssekvenssi()
        app.run(host='0.0.0.0', port=5000)
