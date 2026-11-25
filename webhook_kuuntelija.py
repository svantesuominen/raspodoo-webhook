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

# --- KALIBROINTI (asteet → pigpio duty 0–1_000_000 @ 50Hz) ---
# REST = painovoiman ripustusasento (PWM pois idleissä).
# STRIKE = gongin lyöntikulma. Hienosäädä REST_DEG /servo/goto?deg=N&relax=0 -lla.
SERVO_MIN_DUTY = 50000   # sweep low end (entinen LEPO)
SERVO_MAX_DUTY = 100000  # sweep high end / full strike (entinen ISKU)
SERVO_MIN_DEG = 0
SERVO_MAX_DEG = 90
# Soft 0° ≈ mid (~45° physical). Full hang = PWM off. Soft 90° = gong.
REST_DEG = 0             # wind-up / return mid (not full gravity hang)
STRIKE_DEG = 90          # gong hit
SOFT_STRIKE_DEG = 55
WINDUP_HOLD_S = 0.30
STRIKE_HOLD_S = 0.55
RETURN_HOLD_S = 0.25
SOFT_STRIKE_HOLD_S = 0.40
DOUBLE_STRIKE_HOLD_S = 0.22

def deg_to_duty(deg):
    deg = max(SERVO_MIN_DEG, min(SERVO_MAX_DEG, float(deg)))
    t = (deg - SERVO_MIN_DEG) / (SERVO_MAX_DEG - SERVO_MIN_DEG)
    return int(SERVO_MIN_DUTY + t * (SERVO_MAX_DUTY - SERVO_MIN_DUTY))

LEPO_ASENTO = deg_to_duty(REST_DEG)
ISKU_ASENTO = deg_to_duty(STRIKE_DEG)

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

def servo_set(deg, hold_s=0):
    """ Asettaa servon annettuun kulmaan (asteet). """
    duty = deg_to_duty(deg)
    print(f"[SERVO] goto {deg}° (duty={duty})")
    pi.hardware_PWM(SERVO_PIN, SERVO_FREQ, duty)
    if hold_s > 0:
        time.sleep(hold_s)

def servo_relax():
    """ Katkaisee PWM:n (ei liikuta). """
    pi.hardware_PWM(SERVO_PIN, 0, 0)

def servo_park():
    """ Idle = PWM pois; kapula tippuu painovoimalla hangiin (ei jarruta). """
    print("[SERVO] Park → PWM off (gravity hang)")
    servo_relax()

def servo_home(relax=True, hold_s=0.25):
    """ Unstick: aja midiin, sitten PWM off → gravity hang. ?relax=0 pitää midissä. """
    print(f"[SERVO] Home → mid {REST_DEG}° (relax={relax})")
    servo_set(REST_DEG, hold_s=hold_s)
    if relax:
        servo_park()

def _lyo_kerta(strike_deg, strike_hold_s, windup=True):
    """ Kaksivaihe: mid → strike → mid → PWM off. """
    if windup:
        servo_set(REST_DEG, hold_s=WINDUP_HOLD_S)
    servo_set(strike_deg, hold_s=strike_hold_s)
    servo_set(REST_DEG, hold_s=RETURN_HOLD_S)
    servo_park()

def _parse_relax_flag(default=True):
    """ ?relax=0 pitää PWM:n päällä; muuten rentoutetaan. """
    raw = request.args.get('relax')
    data = request.get_json(silent=True) or {}
    if raw is None and isinstance(data, dict) and 'relax' in data:
        raw = data.get('relax')
    if raw is None:
        return default
    return str(raw).lower() not in ('0', 'false', 'no', 'off')

def soita_kelloa(toistot, style='hard'):
    """ Lyö kelloa; style: hard|soft|double|linger. Kaksivaihe + park. """
    style = (style or 'hard').lower()
    if style not in ('hard', 'soft', 'double', 'linger'):
        style = 'hard'
    toistot = max(1, int(toistot))
    print(f"[SERVO] Lyödään {toistot}x style={style}")

    for i in range(toistot):
        if style == 'hard':
            _lyo_kerta(STRIKE_DEG, STRIKE_HOLD_S, windup=True)
        elif style == 'soft':
            _lyo_kerta(SOFT_STRIKE_DEG, SOFT_STRIKE_HOLD_S, windup=True)
        elif style == 'double':
            for _ in range(2):
                _lyo_kerta(STRIKE_DEG, DOUBLE_STRIKE_HOLD_S, windup=True)
            time.sleep(0.15)
        elif style == 'linger':
            servo_set(REST_DEG, hold_s=WINDUP_HOLD_S)
            servo_set(STRIKE_DEG, hold_s=STRIKE_HOLD_S)
            time.sleep(0.25)
            servo_set(REST_DEG, hold_s=RETURN_HOLD_S)
            servo_park()

        if toistot > 1 and i < toistot - 1:
            time.sleep(0.5)

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
    # Älä aja powered parkia bootissa: kapula on jo hangissa → jarrutusääni.
    print("[BOOT] Käynnistyssekvenssi: relax → gong + thisisfine + piezo")
    servo_relax()
    soita_kelloa(1)
    time.sleep(0.3)
    laukaise_thisisfine()
    time.sleep(0.3)
    soita_melodia('startup')

# --- REITIT (ENDPOINTS) ---

def _servo_style_from_request(data=None):
    style = request.args.get('style')
    if not style and data and 'style' in data:
        style = data['style']
    return style or 'hard'

@app.route('/servo', methods=['POST'])
def servo_control():
    # Lukee Odoon datan ja päättää lyöntien määrän
    data = request.get_json(silent=True)
    summa = 0
    if data and 'amount_untaxed' in data:
        summa = data['amount_untaxed']

    style = _servo_style_from_request(data)
    print(f"[SERVO] Kauppa: {summa} eur style={style}")

    if summa < 20000:
        toistot = 1
    else:
        toistot = int(summa // 10000)

    soita_kelloa(toistot, style=style)
    viesti = f"Kauppa vahvistettu ({toistot}x, {style})"
    return f"Servo: {viesti}", 200

@app.route('/servo/home', methods=['POST'])
def servo_home_control():
    request.get_json(silent=True)
    relax = _parse_relax_flag(default=True)
    if relax:
        servo_park()
    else:
        servo_home(relax=False, hold_s=0.5)
    return f"Servo: hang {REST_DEG}° (relax={relax})", 200

@app.route('/servo/goto', methods=['POST'])
def servo_goto_control():
    data = request.get_json(silent=True) or {}
    raw = request.args.get('deg')
    if raw is None and 'deg' in data:
        raw = data['deg']
    if raw is None:
        return "Servo: missing deg", 400
    try:
        deg = float(raw)
    except (TypeError, ValueError):
        return "Servo: invalid deg", 400
    relax = _parse_relax_flag(default=True)
    servo_set(deg, hold_s=0.5)
    if relax:
        servo_relax()
    return f"Servo: goto {deg}° (relax={relax})", 200

@app.route('/servo/strike', methods=['POST'])
def servo_strike_control():
    data = request.get_json(silent=True) or {}
    raw_hits = request.args.get('hits')
    if raw_hits is None and 'hits' in data:
        raw_hits = data['hits']
    try:
        hits = int(raw_hits) if raw_hits is not None else 1
    except (TypeError, ValueError):
        return "Servo: invalid hits", 400
    style = _servo_style_from_request(data)
    soita_kelloa(hits, style=style)
    return f"Servo: strike {hits}x style={style}", 200

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
    """ Alias → /servo/home (gravity hang + relax) """
    request.get_json(silent=True)
    relax = _parse_relax_flag(default=True)
    print("Komento: Servo hang-asentoon (park)")
    if relax:
        servo_park()
    else:
        servo_home(relax=False, hold_s=0.5)
    return f"Servo nollattu (hang {REST_DEG}°, relax={relax})", 200

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
