from kivy.config import Config
Config.set('input', 'mouse', 'mouse,multitouch_on_demand')
Config.set('graphics', 'fullscreen', '0') 
Config.set('graphics', 'width', '1000')
Config.set('graphics', 'height', '700')

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse, Rectangle, Line
from kivy.core.text import Label as CoreLabel
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.utils import platform  # Hangi cihazda çalıştığımızı anlamak için
import socketio
import math

sio = socketio.Client()
SAHA_W = 2400
SAHA_H = 1400

# !!! TELEFONDAN BAĞLANIRKEN BURAYA BİLGİSAYARININ IP ADRESİNİ YAZMALISIN !!!
SUNUCU_URL = 'http://192.168.1.103:5000'

class GirisEkrani(BoxLayout):
    def __init__(self, switch_callback, **kwargs):
        super(GirisEkrani, self).__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 40
        self.spacing = 10

        self.add_widget(Label(text="HAXBALL HYBRID PRO", font_size=32, bold=True, color=(1, 0.7, 0, 1)))

        self.isim_input = TextInput(hint_text='Oyuncu Adi...', multiline=False, font_size=20, size_hint_y=None, height=50)
        self.add_widget(self.isim_input)

        self.add_widget(Label(text="TAKIM:", font_size=14, bold=True))
        self.takim_box = BoxLayout(spacing=10, size_hint_y=None, height=45)
        self.btn_mavi = Button(text="MAVI", background_color=(0.2, 0.4, 1, 1), bold=True)
        self.btn_kirmizi = Button(text="KIRMIZI", background_color=(1, 0.2, 0.2, 1), bold=True)
        self.btn_mavi.bind(on_press=lambda x: self.set_takim("Mavi"))
        self.btn_kirmizi.bind(on_press=lambda x: self.set_takim("Kirmizi"))
        self.takim_box.add_widget(self.btn_mavi)
        self.takim_box.add_widget(self.btn_kirmizi)
        self.add_widget(self.takim_box)

        self.add_widget(Label(text="MEVKI:", font_size=14, bold=True))
        self.mevki_box = BoxLayout(spacing=10, size_hint_y=None, height=45)
        self.btn_forvet = Button(text="FORVET", background_color=(0.8, 0.8, 0, 1), bold=True)
        self.btn_defans = Button(text="DEFANS", background_color=(0, 0.7, 0.7, 1), bold=True)
        self.btn_forvet.bind(on_press=lambda x: self.set_mevki("Forvet"))
        self.btn_defans.bind(on_press=lambda x: self.set_mevki("Defans"))
        self.mevki_box.add_widget(self.btn_forvet)
        self.mevki_box.add_widget(self.btn_defans)
        self.add_widget(self.mevki_box)

        self.secilen_takim = "Mavi"
        self.secilen_mevki = "Forvet"

        self.btn_giris = Button(text='SAHAYA GİR', font_size=22, background_color=(0, 0.6, 0, 1), bold=True, size_hint_y=None, height=55)
        self.btn_giris.bind(on_press=lambda x: switch_callback(self.isim_input.text, self.secilen_takim, self.secilen_mevki))
        self.add_widget(self.btn_giris)

    def set_takim(self, t):
        self.secilen_takim = t
        self.btn_mavi.text = "=> MAVI <=" if t == "Mavi" else "MAVI"
        self.btn_kirmizi.text = "=> KIRMIZI <=" if t == "Kirmizi" else "KIRMIZI"

    def set_mevki(self, m):
        self.secilen_mevki = m
        self.btn_forvet.text = "=> FORVET <=" if m == "Forvet" else "FORVET"
        self.btn_defans.text = "=> DEFANS <=" if m == "Defans" else "DEFANS"


class OyunEkrani(FloatLayout):
    def __init__(self, oyuncu_adi, takim, mevki, **kwargs):
        super(OyunEkrani, self).__init__(**kwargs)
        self.oyuncu_adi = oyuncu_adi
        self.takim = takim
        self.mevki = mevki
        self.oyuncular_listesi = {}
        self.top_konum = {'x': SAHA_W/2, 'y': SAHA_H/2}
        
        self.mavi_skor = 0
        self.kirmizi_skor = 0
        self.sure_str = "00:00"
        self.gol_aktif = False
        self.gol_atan = ""

        # PC Klavye Kontrolleri
        self.hareket_tuslari = {'w': False, 's': False, 'a': False, 'd': False, 'space': False}

        # Mobil Kontrol Değişkenleri
        self.joystick_merkez = (150, 150)
        self.joystick_some = (150, 150)
        self.joystick_aktif = False
        self.sut_basili = False
        self.joy_dx = 0
        self.joy_dy = 0

        # Cihaz Tespiti: Eğer android veya ios değilse PC'deyiz demektir
        self.is_mobile = platform in ('android', 'ios')

        self.p_x = 800 if self.takim == "Mavi" else SAHA_W - 800
        if self.mevki == "Defans": self.p_x = 300 if self.takim == "Mavi" else SAHA_W - 300
        self.p_y = SAHA_H / 2
        
        self.cam_x = 0
        self.cam_y = 0

        # Sadece mobildeyse ŞUT butonunu ekrana ekle
        if self.is_mobile:
            self.sut_butonu = Button(text="ŞUT", font_size=28, bold=True,
                                     size_hint=(None, None), size=(140, 140),
                                     background_color=(1, 0.3, 0.3, 0.8))
            self.sut_butonu.bind(on_press=self.sut_basla, on_release=self.sut_bitir)
            self.add_widget(self.sut_butonu)

        @sio.on('oyun_durumu')
        def on_status(data):
            Clock.schedule_once(lambda dt: self.verileri_guncelle(data))

        # PC Klavye Dinleyicilerini Bağla
        self._keyboard = Window.request_keyboard(self._keyboard_closed, self)
        self._keyboard.bind(on_key_down=self._on_keyboard_down, on_key_up=self._on_keyboard_up)

        Clock.schedule_interval(self.oyun_guncelle, 1.0 / 60.0)

    def verileri_guncelle(self, data):
        self.oyuncular_listesi = data['oyuncular']
        self.top_konum = data['top']
        self.mavi_skor = data['mavi_skor']
        self.kirmizi_skor = data['kirmizi_skor']
        self.sure_str = data['sure']
        self.gol_aktif = data['gol_aktif']
        self.gol_atan = data['gol_atan']

    def sut_basla(self, instance):
        self.sut_basili = True

    def sut_bitir(self, instance):
        self.sut_basili = False

    def _keyboard_closed(self):
        self._keyboard.unbind(on_key_down=self._on_keyboard_down, on_key_up=self._on_keyboard_up)
        self._keyboard = None

    def _on_keyboard_down(self, keyboard, keycode, text, modifiers):
        tus = keycode[1]
        if tus in ['w', 'up']:    self.hareket_tuslari['w'] = True
        if tus in ['s', 'down']:  self.hareket_tuslari['s'] = True
        if tus in ['a', 'left']:  self.hareket_tuslari['a'] = True
        if tus in ['d', 'right']: self.hareket_tuslari['d'] = True
        if tus == 'spacebar':     self.hareket_tuslari['space'] = True
        return True

    def _on_keyboard_up(self, keyboard, keycode):
        tus = keycode[1]
        if tus in ['w', 'up']:    self.hareket_tuslari['w'] = False
        if tus in ['s', 'down']:  self.hareket_tuslari['s'] = False
        if tus in ['a', 'left']:  self.hareket_tuslari['a'] = False
        if tus in ['d', 'right']: self.hareket_tuslari['d'] = False
        if tus == 'spacebar':     self.hareket_tuslari['space'] = False
        return True

    def on_touch_down(self, touch):
        if super(OyunEkrani, self).on_touch_down(touch):
            return True
        
        # Sadece mobilde (veya PC'de fareyle test ederken) sol ekrana dokunulduğunda joystick aç
        if touch.x < Window.width / 2:
            self.joystick_merkez = (touch.x, touch.y)
            self.joystick_some = (touch.x, touch.y)
            self.joystick_aktif = True
            return True
        return False

    def on_touch_move(self, touch):
        if self.joystick_aktif and touch.x < Window.width / 2:
            mx, my = self.joystick_merkez
            dx = touch.x - mx
            dy = touch.y - my
            mesafe = math.sqrt(dx**2 + dy**2)
            
            max_mesafe = 60
            if mesafe > max_mesafe:
                dx = (dx / mesafe) * max_mesafe
                dy = (dy / mesafe) * max_mesafe
            
            self.joystick_some = (mx + dx, my + dy)
            self.joy_dx = dx / max_mesafe
            self.joy_dy = dy / max_mesafe
            return True
        return False

    def on_touch_up(self, touch):
        if self.joystick_aktif and touch.x < Window.width / 2:
            self.joystick_aktif = False
            self.joy_dx = 0
            self.joy_dy = 0
            return True
        return False

    def oyun_guncelle(self, dt):
        if sio.connected:
            hiz = 3.8 if self.mevki == "Forvet" else 3.2
            if self.gol_aktif:
                hiz = 0

            if sio.sid in self.oyuncular_listesi:
                self.p_x = self.oyuncular_listesi[sio.sid]['x']
                self.p_y = self.oyuncular_listesi[sio.sid]['y']
            
            # --- 1. PC KLAVYE HAREKET HESABI ---
            if self.hareket_tuslari['w']: self.p_y += hiz
            if self.hareket_tuslari['s']: self.p_y -= hiz
            if self.hareket_tuslari['a']: self.p_x -= hiz
            if self.hareket_tuslari['d']: self.p_x += hiz
            
            # --- 2. MOBİL JOYSTICK HAREKET HESABI ---
            self.p_x += self.joy_dx * hiz
            self.p_y += self.joy_dy * hiz
            
            # Şut durumunu birleştir (İster Space'e basılsın ister mobilde butona)
            sut_aktif = self.hareket_tuslari['space'] or self.sut_basili
            
            sio.emit('hareket', {'x': self.p_x, 'y': self.p_y, 'sut': sut_aktif})

            self.cam_x = (Window.width / 2) - self.p_x
            self.cam_y = (Window.height / 2) - self.p_y

        if self.is_mobile:
            self.sut_butonu.pos = (Window.width - 180, 40)
            
        self.ekrani_ciz()

    def ekrani_ciz(self):
        self.canvas.clear()
        cx, cy = self.cam_x, self.cam_y
        
        with self.canvas:
            # Saha Çimi
            Color(0.15, 0.55, 0.15, 1)
            Rectangle(pos=(0, 0), size=(Window.width, Window.height))
            
            # Çizgiler
            Color(1, 1, 1, 0.4) 
            Line(rectangle=(cx, cy, SAHA_W, SAHA_H), width=4) 
            Line(points=[cx + SAHA_W/2, cy, cx + SAHA_W/2, cy + SAHA_H], width=3) 
            Line(circle=(cx + SAHA_W/2, cy + SAHA_H/2, 160), width=3) 
            
            # Kaleler
            Line(rectangle=(cx, cy + SAHA_H/2 - 300, 250, 600), width=3)
            Color(1, 1, 1, 0.8)
            Rectangle(pos=(cx - 40, cy + SAHA_H/2 - 120), size=(40, 240)) 
            
            Color(1, 1, 1, 0.4)
            Line(rectangle=(cx + SAHA_W - 250, cy + SAHA_H/2 - 300, 250, 600), width=3)
            Color(1, 1, 1, 0.8)
            Rectangle(pos=(cx + SAHA_W, cy + SAHA_H/2 - 120), size=(40, 240)) 

            # Oyuncular
            for sid, p in list(self.oyuncular_listesi.items()):
                Color(0.1, 0.5, 1, 1) if p['takim'] == 'Mavi' else Color(1, 0.2, 0.2, 1)
                Ellipse(pos=(cx + p['x'] - 25, cy + p['y'] - 25), size=(50, 50))
                
                if p.get('sut_cekiyor', False):
                    Color(1, 1, 1, 1)
                    Line(circle=(cx + p['x'], cy + p['y'], 28), width=5)

            # Top
            Color(1, 1, 1, 1)
            Ellipse(pos=(cx + self.top_konum['x'] - 15, cy + self.top_konum['y'] - 15), size=(30, 30))

            # SKORBOARD
            Color(0, 0, 0, 0.7)
            Rectangle(pos=(Window.width / 2 - 200, Window.height - 90), size=(400, 80))

            skor_text = f"MAVI  {self.mavi_skor}  -  {self.kirmizi_skor}  KIRMIZI"
            lbl_skor = CoreLabel(text=skor_text, font_size=24, bold=True)
            lbl_skor.refresh()
            Color(1, 1, 1, 1)
            Rectangle(texture=lbl_skor.texture, pos=(Window.width / 2 - lbl_skor.texture.size[0] / 2, Window.height - 50), size=lbl_skor.texture.size)

            lbl_sure = CoreLabel(text=self.sure_str, font_size=16, bold=True)
            lbl_sure.refresh()
            Color(0.9, 0.9, 0.9, 1)
            Rectangle(texture=lbl_sure.texture, pos=(Window.width / 2 - lbl_sure.texture.size[0] / 2, Window.height - 80), size=lbl_sure.texture.size)

            # GOL EKRANI
            if self.gol_aktif:
                Color(0, 0, 0, 0.85)
                Rectangle(pos=(0, Window.height / 2 - 80), size=(Window.width, 160))

                lbl_gol_baslik = CoreLabel(text="GOL !!", font_size=46, bold=True)
                lbl_gol_baslik.refresh()
                Color(1, 0.8, 0, 1)
                Rectangle(texture=lbl_gol_baslik.texture, pos=(Window.width / 2 - lbl_gol_baslik.texture.size[0] / 2, Window.height / 2 + 10), size=lbl_gol_baslik.texture.size)

                atan_text = f"{self.gol_atan} topu aglara gonderdi!"
                lbl_gol_atan = CoreLabel(text=atan_text, font_size=20, bold=False)
                lbl_gol_atan.refresh()
                Color(1, 1, 1, 1)
                Rectangle(texture=lbl_gol_atan.texture, pos=(Window.width / 2 - lbl_gol_atan.texture.size[0] / 2, Window.height / 2 - 40), size=lbl_gol_atan.texture.size)

            # DOKUNMATİK JOYSTICK GÖRSELİ (Yalnızca joystick tetiklendiyse)
            if self.joystick_aktif:
                Color(1, 1, 1, 0.2)
                Ellipse(pos=(self.joystick_merkez[0] - 60, self.joystick_merkez[1] - 60), size=(120, 120))
                Color(1, 1, 1, 0.5)
                Ellipse(pos=(self.joystick_some[0] - 20, self.joystick_some[1] - 20), size=(40, 40))

class HaxballApp(App):
    def build(self):
        return GirisEkrani(switch_callback=self.oyuna_basla)

    def oyuna_basla(self, oyuncu_adi, takim, mevki):
        if not oyuncu_adi: oyuncu_adi = "Oyuncu"
        try:
            sio.connect(SUNUCU_URL)
            sio.emit('giris_yap', {'isim': oyuncu_adi, 'takim': takim, 'mevki': mevki})
        except:
            print("Sunucu baglanti hatasi!")

        self.root.clear_widgets()
        oyun = OyunEkrani(oyuncu_adi=oyuncu_adi, takim=takim, mevki=mevki)
        self.root.add_widget(oyun)

if __name__ == '__main__':
    HaxballApp().run()