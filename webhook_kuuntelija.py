import pigpio
import time
from flask import Flask, request
import random

# --- LAITTEISTOASETUKSET ---
# GPIO 18 (Fyysinen pinni 12) = Servo
# GPIO 13 (Fyysinen pinni 33) = Piezo (Summeri)
SERVO_PIN = 18
PIEZO_PIN = 13
SERVO_FREQ = 50 

# --- KALIBROINTI (Testattu toimivaksi) ---
LEPO_ASENTO = 50000   # Ylhäällä
ISKU_ASENTO = 100000  # Alhaalla (lyönti)

pi = pigpio.pi()
app = Flask(__name__)

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
    
    # Hiljennys
    pi.hardware_PWM(PIEZO_PIN, 0, 0)

def paivita_naytto(teksti, summa=None):
    print("--------------------------------")
    print(f"[DISPLAY] UUSI VIESTI:")
    print(f">> {teksti}")
    if summa:
        print(f">> Summa: {summa} EUR")
    print("--------------------------------")

# --- REITIT (ENDPOINTS) ---

@app.route('/servo', methods=['POST'])
def servo_control():
    # Lukee Odoon datan ja päättää lyöntien määrän
    data = request.json
    summa = 0
    if data and 'amount_untaxed' in data:
        summa = data['amount_untaxed']
    
    print(f"[SERVO] Kauppa: {summa} eur")
    
    viesti = ""
    if summa > 50000:
        soita_kelloa(3)
        viesti = "Jättikauppa! (3x)"
    elif summa > 10000:
        soita_kelloa(2)
        viesti = "Iso kauppa! (2x)"
    else:
        soita_kelloa(1)
        viesti = "Kauppa vahvistettu (1x)"
        
    return f"Servo: {viesti}", 200

@app.route('/piezo', methods=['POST'])
def piezo_control():
    # Ensisijaisesti URL-parametrista: .../piezo?sound=coin
    sound_type = request.args.get('sound')
    
    # Varalta JSONista
    data = request.json
    if not sound_type and data and 'sound' in data:
        sound_type = data['sound']
    
    if not sound_type: sound_type = 'success'
        
    soita_melodia(sound_type)
    return f"Piezo: {sound_type}", 200

@app.route('/display', methods=['POST'])
def display_control():
    # Viesti URL-parametrista: .../display?msg=Teksti
    message = request.args.get('msg')
    
    data = request.json
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

if __name__ == '__main__':
    if not pi.connected:
        print("VIRHE: Pigpio ei ole käynnissä! Aja 'sudo systemctl start pigpiod'.")
    else:
        # Alustus hiljaiseksi
        pi.hardware_PWM(SERVO_PIN, 0, 0)
        pi.hardware_PWM(PIEZO_PIN, 0, 0)
        app.run(host='0.0.0.0', port=5000)
