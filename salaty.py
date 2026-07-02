#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""صلاتي  |  Salaty — مواقيت الصلاة"""

from __future__ import annotations

import sys, datetime, json, os, math, urllib.request, wave, struct
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QDialog, QComboBox,
    QDoubleSpinBox, QCheckBox, QSizePolicy, QSpinBox, QGridLayout,
    QStackedWidget, QButtonGroup, QSystemTrayIcon, QMenu,
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QRectF, QPointF, QProcess, QLockFile,
)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtGui import (QFont, QFontDatabase, QCursor, QColor,
                          QPainter, QPen, QPainterPath, QPixmap, QIcon,
                          QAction)

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════

APP_DIR     = os.path.dirname(os.path.abspath(__file__))
APP_ICON    = os.path.join(APP_DIR, 'assets', 'salaty.png')
CONFIG_DIR  = os.path.expanduser('~/.config/salaty/')
CONFIG_FILE = os.path.join(CONFIG_DIR, 'settings.json')
CACHE_FILE  = os.path.join(CONFIG_DIR, 'cache.json')
IQAMA_DEF   = {'Fajr': 20, 'Dhuhr': 15, 'Asr': 15, 'Maghrib': 5, 'Isha': 15}

def load_cfg():
    d = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, encoding='utf-8') as f:
                d = json.load(f)
        except Exception:
            pass
    return {
        'method': d.get('method', 3), 'school': d.get('school', 0),
        'manual_loc': d.get('manual_loc', False),
        'lat': d.get('lat'), 'lng': d.get('lng'),
        'city_ar': d.get('city_ar', ''), 'city_en': d.get('city_en', ''),
        'city_display': d.get('city_display', ''),
        'iqama': {**IQAMA_DEF, **d.get('iqama', {})},
        'sound_mode': d.get('sound_mode', 'adhan'),
        'notifications_muted': d.get('notifications_muted', False),
    }

def save_cfg(d):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

def sound_path(mode):
    if mode in ('adhan', 'takbir'):
        return os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 'sounds',
            'takbir.ogg' if mode == 'takbir' else 'adhan.ogg')

    path = os.path.join(CONFIG_DIR, 'chime.wav')
    if os.path.exists(path):
        return path
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        rate, duration = 44100, 1.8
        frames = []
        for i in range(int(rate * duration)):
            t = i / rate
            # Three soft bell notes with a natural exponential fade.
            value = 0.0
            for start, freq in ((0.0, 659.25), (0.42, 783.99), (0.84, 987.77)):
                dt = t - start
                if 0 <= dt < 0.75:
                    env = math.exp(-4.5 * dt)
                    value += math.sin(2 * math.pi * freq * dt) * env
                    value += math.sin(2 * math.pi * freq * 2 * dt) * env * 0.18
            frames.append(struct.pack('<h', int(max(-1, min(1, value * 0.22)) * 32767)))
        with wave.open(path, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate)
            wav.writeframes(b''.join(frames))
    except Exception:
        return ''
    return path

def audio_command(path):
    """Return the first available Linux audio player and its arguments."""
    candidates = (
        ('/usr/bin/gst-play-1.0', ['--no-interactive', path]),
        ('/usr/bin/pw-play', [path]),
        ('/usr/bin/canberra-gtk-play', ['-f', path]),
        ('/usr/bin/aplay', [path]),
    )
    for program, args in candidates:
        if os.path.exists(program):
            return program, args
    return '', []

# ══════════════════════════════════════════════════════════════════════════════
#  HIJRI
# ══════════════════════════════════════════════════════════════════════════════

class Hijri:
    MN = ['محرم','صفر','ربيع الأول','ربيع الثاني','جمادى الأولى',
          'جمادى الثانية','رجب','شعبان','رمضان','شوال','ذو القعدة','ذو الحجة']
    DN = ['الأحد','الإثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت']
    GM = ['يناير','فبراير','مارس','أبريل','مايو','يونيو',
          'يوليو','أغسطس','سبتمبر','أكتوبر','نوفمبر','ديسمبر']

    @classmethod
    def fmt(cls, date=None):
        d = date or datetime.date.today()
        y, m, dd = d.year, d.month, d.day
        if m <= 2: y -= 1; m += 12
        A = y//100; B = 2 - A + A//4
        JD = int(365.25*(y+4716)) + int(30.6001*(m+1)) + dd + B - 1524
        L  = JD - 1948440 + 10632; N = (L-1)//10631; L -= 10631*N - 354
        J  = ((10985-L)//5316)*((50*L)//17719) + (L//5670)*((43*L)//15238)
        L -= ((30-J)//15)*((17719*J)//50) + (J//16)*((15238*J)//43) - 29
        hm = (24*L)//709; hd = L - (709*hm)//24; hy = 30*N + J - 30
        dow = d.isoweekday() % 7
        return f"{cls.DN[dow]}،  {hd}  {cls.MN[hm-1]}  {hy} هـ"

    @classmethod
    def gregorian_fmt(cls, date=None):
        d = date or datetime.date.today()
        return f'{d.day} {cls.GM[d.month-1]} {d.year} م'

# ══════════════════════════════════════════════════════════════════════════════
#  TRANSLATIONS
# ══════════════════════════════════════════════════════════════════════════════

CITY_AR = {
    'Riyadh':'الرياض','Jeddah':'جدة','Mecca':'مكة المكرمة',
    'Medina':'المدينة المنورة','Dammam':'الدمام','Tabuk':'تبوك',
    'Abha':'أبها','Khobar':'الخبر','Cairo':'القاهرة',
    'Alexandria':'الإسكندرية','Dubai':'دبي','Abu Dhabi':'أبوظبي',
    'Sharjah':'الشارقة','Kuwait City':'الكويت','Doha':'الدوحة',
    'Muscat':'مسقط','Manama':'المنامة','Baghdad':'بغداد',
    'Amman':'عمّان','Beirut':'بيروت','Damascus':'دمشق',
    'Tunis':'تونس','Algiers':'الجزائر','Casablanca':'الدار البيضاء',
    'Istanbul':'إسطنبول','Tehran':'طهران','Karachi':'كراتشي',
    'London':'لندن','Paris':'باريس','New York City':'نيويورك',
    'New York':'نيويورك','Toronto':'تورنتو',
}
COUNTRY_AR = {
    'Saudi Arabia':'السعودية','Egypt':'مصر',
    'United Arab Emirates':'الإمارات','Kuwait':'الكويت','Qatar':'قطر',
    'Bahrain':'البحرين','Oman':'عُمان','Iraq':'العراق',
    'Jordan':'الأردن','Lebanon':'لبنان','Syria':'سوريا',
    'Libya':'ليبيا','Tunisia':'تونس','Algeria':'الجزائر',
    'Morocco':'المغرب','Sudan':'السودان','Turkey':'تركيا',
    'Iran':'إيران','Pakistan':'باكستان','Malaysia':'ماليزيا',
    'Indonesia':'إندونيسيا','United Kingdom':'بريطانيا',
    'France':'فرنسا','Germany':'ألمانيا',
    'United States':'أمريكا','Canada':'كندا','Australia':'أستراليا',
}

# ══════════════════════════════════════════════════════════════════════════════
#  CALCULATION METHODS
# ══════════════════════════════════════════════════════════════════════════════

METHODS = {
    3:  'رابطة العالم الإسلامي',
    4:  'أم القرى – مكة المكرمة',
    2:  'الجمعية الإسلامية – أمريكا الشمالية',
    5:  'الهيئة المصرية للمساحة',
    9:  'الكويت', 10: 'قطر',
    1:  'جامعة العلوم – كراتشي',
    13: 'رئاسة الشؤون الدينية – تركيا',
}

# ══════════════════════════════════════════════════════════════════════════════
#  NETWORK THREADS
# ══════════════════════════════════════════════════════════════════════════════

class LocationFetcher(QThread):
    ok   = pyqtSignal(dict)
    fail = pyqtSignal(str)
    def run(self):
        try:
            url = 'http://ip-api.com/json/?fields=status,city,country,lat,lon,timezone'
            req = urllib.request.Request(url, headers={'User-Agent':'Salaty/3'})
            with urllib.request.urlopen(req, timeout=7) as r:
                d = json.loads(r.read())
            (self.ok if d.get('status') == 'success' else self.fail).emit(
                d if d.get('status') == 'success' else 'fail')
        except Exception as e:
            self.fail.emit(str(e))

class TimeFetcher(QThread):
    ok   = pyqtSignal(dict)
    fail = pyqtSignal(str)
    def __init__(self, lat, lng, method=3, school=0):
        super().__init__()
        self.lat, self.lng = lat, lng
        self.method, self.school = method, school
    def run(self):
        try:
            d = datetime.date.today()
            url = (f'https://api.aladhan.com/v1/timings/{d.day}-{d.month}-{d.year}'
                   f'?latitude={self.lat}&longitude={self.lng}'
                   f'&method={self.method}&school={self.school}')
            req = urllib.request.Request(url, headers={'User-Agent':'Salaty/3'})
            with urllib.request.urlopen(req, timeout=14) as r:
                self.ok.emit(json.loads(r.read())['data']['timings'])
        except Exception as e:
            self.fail.emit(str(e))

# ══════════════════════════════════════════════════════════════════════════════
#  DESIGN TOKENS
# ══════════════════════════════════════════════════════════════════════════════

BG       = '#071311'
SURFACE  = '#0B1B18'
CARD_BG  = '#102521'
BORDER   = '#234039'
GOLD     = '#D5A94E'
GOLD_L   = '#F2CF7A'
GOLD_DIM = 'rgba(213,169,78,0.48)'
GREEN    = '#2FAF7D'
GREEN_L  = '#62D4A7'
GREEN_DIM= 'rgba(47,175,125,0.48)'
WHITE    = '#F3F6F0'
MUTED    = '#9AACA5'
DIM      = '#52645E'
AMBER    = '#D69B45'

ACTIVE_PRAY = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']
PRAYER_AR   = {
    'Fajr':'الفجر','Sunrise':'الشروق','Dhuhr':'الظهر',
    'Asr':'العصر','Maghrib':'المغرب','Isha':'العشاء',
}

# ══════════════════════════════════════════════════════════════════════════════
#  FONTS  (Cairo variable, bundled)
# ══════════════════════════════════════════════════════════════════════════════

_CAIRO: str | None = None

def _load_fonts():
    global _CAIRO
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
    for n in ('Cairo-Variable.ttf', 'Cairo.ttf'):
        p = os.path.join(d, n)
        if not os.path.exists(p): continue
        fid = QFontDatabase.addApplicationFont(p)
        if fid >= 0:
            fams = QFontDatabase.applicationFontFamilies(fid)
            if fams: _CAIRO = fams[0]; return

def F(size=12, bold=False, semi=False):
    fam = _CAIRO
    if not fam:
        for f in ('Noto Naskh Arabic','Noto Sans Arabic','Amiri'):
            if f in QFontDatabase.families(): fam = f; break
    f = QFont(fam or '', size)
    if bold: f.setWeight(QFont.Weight.Bold)
    elif semi: f.setWeight(QFont.Weight.DemiBold)
    return f

# ══════════════════════════════════════════════════════════════════════════════
#  MONOCHROMATIC ICONS
# ══════════════════════════════════════════════════════════════════════════════

class PrayerIcon(QWidget):
    def __init__(self, name: str, size=20, parent=None):
        super().__init__(parent)
        self._n, self._c = name, QColor(MUTED)
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet('background:transparent;')

    def set_color(self, c: str): self._c = QColor(c); self.update()
    def set_name(self, n: str):  self._n = n;        self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = float(self.width()), float(self.height())
        cx, cy = w*.5, h*.5; r = min(w,h)*.40; lw = max(1.4, min(w,h)*.09)
        st = QPen(self._c, lw, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

        def ln(x1,y1,x2,y2): p.drawLine(QPointF(x1,y1), QPointF(x2,y2))

        nm = self._n
        if nm == 'Fajr':
            o = QPainterPath(); o.addEllipse(QRectF(cx-r,cy-r,2*r,2*r))
            c = QPainterPath(); c.addEllipse(QRectF(cx-r+r*.42,cy-r,2*r,2*r))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(self._c)
            p.drawPath(o.subtracted(c))
        elif nm == 'Sunrise':
            hy = cy+r*.55; p.setPen(st); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(cx-r,hy-r,2*r,2*r), 0, 180*16)
            ln(cx-r*1.5,hy, cx+r*1.5,hy)
            for deg in (-60,-90,-120):
                a=math.radians(deg); r1=r+lw; r2=r+r*.55
                ln(cx+r1*math.cos(a),hy+r1*math.sin(a), cx+r2*math.cos(a),hy+r2*math.sin(a))
        elif nm == 'Dhuhr':
            sr=r*.52; p.setPen(st); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx-sr,cy-sr,2*sr,2*sr))
            for i in range(8):
                a=math.radians(i*45); r1=sr+lw; r2=sr+r*.48
                ln(cx+r1*math.cos(a),cy+r1*math.sin(a), cx+r2*math.cos(a),cy+r2*math.sin(a))
        elif nm == 'Asr':
            sr=r*.50; sy=cy-r*.15; p.setPen(st); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx-sr,sy-sr,2*sr,2*sr))
            for i in range(6):
                a=math.radians(i*60+30); r1=sr+lw; r2=sr+r*.44
                ln(cx+r1*math.cos(a),sy+r1*math.sin(a), cx+r2*math.cos(a),sy+r2*math.sin(a))
            th=QPen(self._c,lw*.7,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap)
            p.setPen(th); ln(cx-r*.3,cy+r*.7, cx+r*1.1,cy+r*.7)
        elif nm == 'Maghrib':
            hy=cy+r*.10; p.setPen(st); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawArc(QRectF(cx-r*.85,hy-r*.85,2*r*.85,2*r*.85), 0, 180*16)
            ln(cx-r*1.3,hy, cx+r*1.3,hy)
            th=QPen(self._c,lw*.75,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap)
            p.setPen(th)
            for deg in (60,90,120):
                a=math.radians(deg); r1=r*.85+lw; r2=r*.85+r*.35
                ln(cx+r1*math.cos(a),hy+r1*math.sin(a), cx+r2*math.cos(a),hy+r2*math.sin(a))
        elif nm == 'Isha':
            sc=.82
            o=QPainterPath(); o.addEllipse(QRectF(cx-r*sc,cy-r*sc+1,2*r*sc,2*r*sc))
            c=QPainterPath(); c.addEllipse(QRectF(cx-r*sc+r*.5,cy-r*sc+1,2*r*sc,2*r*sc))
            p.setPen(Qt.PenStyle.NoPen); p.setBrush(self._c)
            p.drawPath(o.subtracted(c))
            sr=r*.20; p.drawEllipse(QRectF(cx+r*.65-sr, cy-r*.75-sr, 2*sr, 2*sr))
        p.end()

# ══════════════════════════════════════════════════════════════════════════════
#  PRAYER COLUMN  — one of five horizontal cards
# ══════════════════════════════════════════════════════════════════════════════

class PrayerColumn(QWidget):
    def __init__(self, name: str):
        super().__init__()
        self._name  = name
        self._state = ''
        self._build()

    def _build(self):
        self.setMinimumWidth(90)
        self.setMinimumHeight(118)
        self.setObjectName('colCard')
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 16, 8, 15)
        lay.setSpacing(6)
        lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # icon container
        iw = QWidget(); iw.setObjectName('iw')
        iw.setFixedHeight(32)
        il = QHBoxLayout(iw); il.setContentsMargins(0,2,0,2)
        self._ico = PrayerIcon(self._name, size=24)
        il.addWidget(self._ico, 0, Qt.AlignmentFlag.AlignHCenter)

        # prayer name
        self._nm_lbl = QLabel(PRAYER_AR.get(self._name, self._name))
        self._nm_lbl.setObjectName('nmLbl')
        self._nm_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._nm_lbl.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._nm_lbl.setFont(F(11))

        # time
        self._tm_lbl = QLabel('--:--')
        self._tm_lbl.setObjectName('tmLbl')
        self._tm_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tm_lbl.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._tm_lbl.setFont(F(16, bold=True))

        lay.addWidget(iw)
        lay.addWidget(self._nm_lbl)
        lay.addWidget(self._tm_lbl)
        self.set_state('normal')

    def set_time(self, hhmm: str):
        try:
            h, m = map(int, hhmm.strip().split(' ')[0].split(':')[:2])
            self._tm_lbl.setText(f'{h:02d}:{m:02d}')
        except Exception:
            self._tm_lbl.setText('--:--')

    def set_state(self, state: str):
        if self._state == state: return
        self._state = state

        # #colCard targets only this widget (not children), so labels keep their own styles
        if state == 'next':
            self.setStyleSheet(f"""
                #colCard {{
                    background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 rgba(213,169,78,0.25), stop:1 rgba(213,169,78,0.08));
                    border-radius:17px; border:1.5px solid {GOLD_DIM};
                }}
                #iw, #nmLbl, #tmLbl {{ background:transparent; border:none; }}
                #nmLbl {{ color:{GOLD_L}; }}
                #tmLbl {{ color:{GOLD_L}; }}
            """)
            self._ico.set_color(GOLD_L)

        elif state == 'iqama':
            self.setStyleSheet(f"""
                #colCard {{
                    background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 rgba(47,175,125,0.25), stop:1 rgba(47,175,125,0.08));
                    border-radius:17px; border:1.5px solid {GREEN_DIM};
                }}
                #iw, #nmLbl, #tmLbl {{ background:transparent; border:none; }}
                #nmLbl {{ color:{GREEN_L}; }}
                #tmLbl {{ color:{GREEN_L}; }}
            """)
            self._ico.set_color(GREEN_L)

        elif state == 'past':
            self.setStyleSheet(f"""
                #colCard {{
                    background:rgba(255,255,255,0.018);
                    border-radius:17px; border:1px solid rgba(255,255,255,0.045);
                }}
                #iw, #nmLbl, #tmLbl {{ background:transparent; border:none; }}
                #nmLbl {{ color:{DIM}; }}
                #tmLbl {{ color:{DIM}; }}
            """)
            self._ico.set_color(DIM)

        else:  # normal (future)
            self.setStyleSheet(f"""
                #colCard {{
                    background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                        stop:0 rgba(255,255,255,0.065), stop:1 rgba(255,255,255,0.025));
                    border-radius:17px; border:1px solid rgba(255,255,255,0.09);
                }}
                #iw, #nmLbl, #tmLbl {{ background:transparent; border:none; }}
                #nmLbl {{ color:{MUTED}; }}
                #tmLbl {{ color:{WHITE}; }}
            """)
            self._ico.set_color(MUTED)

# ══════════════════════════════════════════════════════════════════════════════
#  SETTINGS DIALOG
# ══════════════════════════════════════════════════════════════════════════════

class SettingsDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self._cfg = {**cfg, 'iqama': dict(cfg.get('iqama', IQAMA_DEF))}
        self._preview_process = None
        self.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setWindowTitle('الإعدادات')
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(460, screen.width() - 32), min(455, screen.height() - 80))
        self.setMinimumSize(min(400, screen.width() - 24),
                            min(400, screen.height() - 48))
        self.setMaximumWidth(480)
        self.setStyleSheet(f"""
            QDialog {{ background:{BG}; color:{WHITE}; }}
            QLabel  {{ background:transparent; border:none; }}
            QComboBox, QDoubleSpinBox, QSpinBox {{
                background:#0B1B18; color:{WHITE};
                border:1px solid {BORDER}; border-radius:11px;
                padding:7px 12px; min-height:34px; font-size:11pt;
            }}
            QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus {{
                border:1.5px solid {GOLD}; background:#0D211D;
            }}
            QComboBox:disabled, QDoubleSpinBox:disabled, QSpinBox:disabled {{
                color:{DIM}; background:#091512; border-color:#172B26;
            }}
            QComboBox::drop-down {{ border:none; width:26px; }}
            QComboBox QAbstractItemView {{
                background:{CARD_BG}; color:{WHITE};
                selection-background-color:rgba(213,169,78,0.24);
                border:1px solid {BORDER}; outline:none;
            }}
            QCheckBox {{ color:{WHITE}; spacing:10px; font-size:11pt; }}
            QCheckBox::indicator {{
                width:20px; height:20px; border-radius:6px;
                border:1.5px solid {BORDER}; background:{CARD_BG};
            }}
            QCheckBox::indicator:checked {{
                background:{GOLD}; border-color:{GOLD};
            }}
            QSpinBox::up-button, QSpinBox::down-button,
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                background:transparent; border:none; width:16px;
            }}
            QPushButton#ok {{
                background:{GOLD}; color:#142019; border-radius:11px;
                padding:11px 32px; font-size:12pt; font-weight:bold; border:none;
            }}
            QPushButton#ok:hover {{ background:{GOLD_L}; }}
            QPushButton#cancel {{
                background:rgba(255,255,255,0.05); color:{MUTED};
                border-radius:11px; padding:10px 24px;
                font-size:11pt; border:1px solid {BORDER};
            }}
            QPushButton#cancel:hover {{ background:rgba(255,255,255,0.12); color:{WHITE}; }}
            QPushButton#preview {{
                background:rgba(213,169,78,0.10); color:{GOLD_L};
                border:1px solid rgba(213,169,78,0.32);
                border-radius:10px; padding:7px 12px;
            }}
            QPushButton#preview:hover {{ background:rgba(213,169,78,0.18); }}
            QPushButton#preview[playing="true"] {{
                color:#FFB7A9; background:rgba(220,90,70,0.12);
                border-color:rgba(220,90,70,0.42);
            }}
            QPushButton#preview:disabled {{ color:{DIM}; border-color:{BORDER}; }}
        """)
        self._build()

    def _sec(self, title, subtitle=''):
        """Compact section heading with an optional explanation."""
        w = QWidget(); w.setStyleSheet('background:transparent;')
        hl = QHBoxLayout(w); hl.setContentsMargins(0,0,0,0); hl.setSpacing(10)
        bar = QFrame(); bar.setFixedSize(4, 34)
        bar.setStyleSheet(f'background:{GOLD}; border-radius:2px;')
        text = QWidget(); text.setStyleSheet('background:transparent;')
        tl = QVBoxLayout(text); tl.setContentsMargins(0,0,0,0); tl.setSpacing(0)
        lbl = QLabel(title); lbl.setFont(F(11, semi=True))
        lbl.setStyleSheet(f'color:{WHITE};')
        tl.addWidget(lbl)
        if subtitle:
            sub = QLabel(subtitle); sub.setFont(F(8))
            sub.setStyleSheet(f'color:{MUTED};')
            tl.addWidget(sub)
        hl.addWidget(bar); hl.addWidget(text); hl.addStretch()
        return w

    def _panel(self):
        w = QFrame(); w.setObjectName('settingsPanel')
        w.setStyleSheet(f"""
            QFrame#settingsPanel {{
                background:{SURFACE}; border:1px solid {BORDER}; border-radius:16px;
            }}
            QFrame#settingsPanel QLabel {{ border:none; }}
        """)
        return w

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setSpacing(10); outer.setContentsMargins(20,16,20,16)

        head = QHBoxLayout(); head.setSpacing(12)
        title_box = QWidget(); title_box.setStyleSheet('background:transparent;')
        title_lay = QVBoxLayout(title_box)
        title_lay.setContentsMargins(0,0,0,0); title_lay.setSpacing(1)
        ttl = QLabel('إعدادات صلاتي'); ttl.setFont(F(16, bold=True))
        ttl.setStyleSheet(f'color:{WHITE};')
        sub = QLabel('اختر القسم الذي تريد تعديله')
        sub.setFont(F(8)); sub.setStyleSheet(f'color:{MUTED};')
        title_lay.addWidget(ttl); title_lay.addWidget(sub)
        close = QPushButton('×'); close.setFixedSize(32,32); close.setFont(F(17))
        close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        close.setStyleSheet(f"""
            QPushButton {{ color:{MUTED}; background:rgba(255,255,255,0.05);
                border:1px solid {BORDER}; border-radius:16px; }}
            QPushButton:hover {{ color:{WHITE}; background:rgba(255,255,255,0.10); }}
        """)
        close.clicked.connect(self.reject)
        head.addWidget(title_box, 1); head.addWidget(close)
        outer.addLayout(head)

        stack = QStackedWidget()
        stack.setStyleSheet('QStackedWidget { background:transparent; border:none; }')
        self._stack = stack

        tabs = QFrame(); tabs.setObjectName('sectionTabs')
        tabs.setStyleSheet(f"""
            QFrame#sectionTabs {{
                background:{SURFACE}; border:1px solid {BORDER}; border-radius:13px;
            }}
            QPushButton#sectionTab {{
                color:{MUTED}; background:transparent; border:none;
                border-radius:10px; padding:8px 5px; font-size:9pt;
            }}
            QPushButton#sectionTab:hover {{
                color:{WHITE}; background:rgba(255,255,255,0.05);
            }}
            QPushButton#sectionTab:checked {{
                color:#172019; background:{GOLD}; font-weight:600;
            }}
        """)
        tabs_lay = QHBoxLayout(tabs)
        tabs_lay.setContentsMargins(3,3,3,3); tabs_lay.setSpacing(3)
        self._section_group = QButtonGroup(self)
        self._section_group.setExclusive(True)
        self._section_buttons = []
        for index, text in enumerate(
                ('حساب المواقيت', 'مواعيد الإقامة', 'الموقع الجغرافي')):
            button = QPushButton(text); button.setObjectName('sectionTab')
            button.setCheckable(True); button.setFont(F(9, semi=True))
            button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            button.clicked.connect(
                lambda checked=False, page=index: stack.setCurrentIndex(page))
            self._section_group.addButton(button, index)
            self._section_buttons.append(button)
            tabs_lay.addWidget(button, 1)
        self._section_buttons[0].setChecked(True)
        outer.addWidget(tabs)

        calc = self._panel(); calc_l = QVBoxLayout(calc)
        calc_l.setContentsMargins(16,12,16,14); calc_l.setSpacing(8)
        calc_l.addWidget(self._sec(
            'حساب المواقيت', 'اختر الجهة المعتمدة ومذهب حساب صلاة العصر'))
        self._method = QComboBox(); self._method.setFont(F(11))
        self._method.setMaxVisibleItems(5)
        self._method.setFixedWidth(350)
        for mid, mn in METHODS.items():
            self._method.addItem(mn, mid)
            if mid == self._cfg.get('method', 3):
                self._method.setCurrentIndex(self._method.count()-1)
        method_lbl = QLabel('طريقة الحساب'); method_lbl.setFont(F(9))
        method_lbl.setStyleSheet(f'color:{MUTED};')
        calc_l.addWidget(method_lbl)
        method_row = QWidget(); method_row.setStyleSheet('background:transparent;')
        method_row.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        method_row_lay = QHBoxLayout(method_row)
        method_row_lay.setContentsMargins(0,0,0,0); method_row_lay.setSpacing(0)
        method_row_lay.addStretch(); method_row_lay.addWidget(self._method)
        calc_l.addWidget(method_row)

        self._school = QComboBox(); self._school.setFont(F(11))
        self._school.setMaxVisibleItems(5)
        self._school.setFixedWidth(350)
        self._school.addItem('الشافعي / المالكي / الحنبلي', 0)
        self._school.addItem('الحنفي', 1)
        self._school.setCurrentIndex(0 if self._cfg.get('school',0)==0 else 1)
        slbl = QLabel('مذهب العصر'); slbl.setFont(F(9))
        slbl.setStyleSheet(f'color:{MUTED};')
        calc_l.addWidget(slbl)
        school_row = QWidget(); school_row.setStyleSheet('background:transparent;')
        school_row.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        school_row_lay = QHBoxLayout(school_row)
        school_row_lay.setContentsMargins(0,0,0,0); school_row_lay.setSpacing(0)
        school_row_lay.addStretch(); school_row_lay.addWidget(self._school)
        calc_l.addWidget(school_row)
        popup_style = f"""
            QAbstractItemView {{
                background:{CARD_BG}; color:{WHITE};
                border:1px solid {BORDER}; border-radius:8px;
                padding:4px; outline:none; selection-background-color:{GOLD};
                selection-color:#172019;
            }}
        """
        self._method.view().setStyleSheet(popup_style)
        self._school.view().setStyleSheet(popup_style)
        calc_l.addStretch()
        stack.addWidget(calc)

        iq_panel = self._panel(); iq_lay = QVBoxLayout(iq_panel)
        iq_lay.setContentsMargins(16,12,16,14); iq_lay.setSpacing(8)
        iq_lay.addWidget(self._sec(
            'مدة انتظار الإقامة', 'عدد الدقائق بين الأذان والإقامة لكل صلاة'))
        ig_w = QWidget(); ig_w.setStyleSheet('background:transparent;')
        ig_l = QGridLayout(ig_w); ig_l.setContentsMargins(0,0,0,0)
        ig_l.setHorizontalSpacing(6); ig_l.setVerticalSpacing(0)
        self._iq = {}
        for index, nm in enumerate(ACTIVE_PRAY):
            col = QFrame()
            col.setObjectName('iqamaCard')
            col.setStyleSheet(f"""
                QFrame#iqamaCard {{
                    background:#0B1B18; border:1px solid {BORDER}; border-radius:11px;
                }}
                QFrame#iqamaCard QLabel {{
                    background:transparent; border:none; color:{MUTED};
                }}
            """)
            cl = QVBoxLayout(col); cl.setContentsMargins(5,6,5,6); cl.setSpacing(3)
            lb  = QLabel(PRAYER_AR.get(nm, nm)); lb.setFont(F(9))
            lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lb.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            lb.setWordWrap(False)
            lb.setStyleSheet(f'color:{MUTED}; border:none; background:transparent;')
            sp = QSpinBox(); sp.setRange(0, 35); sp.setValue(min(self._cfg['iqama'].get(nm, 15), 35))
            sp.setFont(F(11, bold=True)); sp.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sp.setSuffix(' د'); sp.setMinimumWidth(62)
            sp.setStyleSheet('border-radius:8px; padding-left:2px; padding-right:2px;')
            cl.addWidget(lb); cl.addWidget(sp)
            ig_l.addWidget(col, 0, index)
            self._iq[nm] = sp
        iq_lay.addWidget(ig_w)

        sound_row = QWidget(); sound_row.setStyleSheet('background:transparent;')
        sound_lay = QHBoxLayout(sound_row)
        sound_lay.setContentsMargins(0,2,0,0); sound_lay.setSpacing(8)
        self._mute = QCheckBox('كتم الإشعارات والأصوات')
        self._mute.setFont(F(9))
        self._mute.setChecked(self._cfg.get('notifications_muted', False))
        self._sound_mode = QComboBox(); self._sound_mode.setFont(F(9))
        self._sound_mode.addItem('أذان الحرم المكي', 'adhan')
        self._sound_mode.addItem('التكبير فقط', 'takbir')
        self._sound_mode.addItem('رنين بسيط', 'chime')
        mode_index = self._sound_mode.findData(
            self._cfg.get('sound_mode', 'adhan'))
        self._sound_mode.setCurrentIndex(max(0, mode_index))
        self._sound_mode.setFixedWidth(145)
        self._preview = QPushButton('تجربة')
        self._preview.setObjectName('preview'); self._preview.setFont(F(9))
        self._preview.setProperty('playing', False)
        self._preview.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self._preview.clicked.connect(self._preview_sound)
        self._sound_mode.currentIndexChanged.connect(self._stop_preview)
        self._mute.toggled.connect(self._mute_changed)
        self._sound_mode.setEnabled(not self._mute.isChecked())
        self._preview.setEnabled(not self._mute.isChecked())
        sound_lay.addWidget(self._mute, 1)
        sound_lay.addWidget(self._sound_mode)
        sound_lay.addWidget(self._preview)
        iq_lay.addWidget(sound_row)
        iq_lay.addStretch()
        stack.addWidget(iq_panel)

        loc_panel = self._panel(); loc_lay = QVBoxLayout(loc_panel)
        loc_lay.setContentsMargins(16,12,16,14); loc_lay.setSpacing(8)
        loc_lay.addWidget(self._sec(
            'الموقع الجغرافي', 'يُكتشف تلقائياً، ويمكنك إدخال إحداثيات أدق'))
        self._manual = QCheckBox('إدخال الإحداثيات يدوياً'); self._manual.setFont(F(11))
        self._manual.setChecked(self._cfg.get('manual_loc', False))
        self._manual.toggled.connect(lambda on: (self._lat.setEnabled(on), self._lng.setEnabled(on)))
        loc_lay.addWidget(self._manual)

        coord_w = QWidget(); coord_w.setStyleSheet('background:transparent;')
        cl = QGridLayout(coord_w); cl.setContentsMargins(0,2,0,0); cl.setSpacing(8)
        for (key, ltext, rng, val) in [
            ('lat','خط العرض',(-90,90), self._cfg.get('lat') or 24.6877),
            ('lng','خط الطول',(-180,180), self._cfg.get('lng') or 46.7219),
        ]:
            sp = QDoubleSpinBox(); sp.setRange(*rng); sp.setDecimals(4); sp.setValue(val)
            sp.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            sp.setFont(F(10)); lbl = QLabel(ltext); lbl.setFont(F(10))
            lbl.setStyleSheet(f'color:{MUTED};')
            column = 0 if key == 'lat' else 1
            cl.addWidget(lbl, 0, column); cl.addWidget(sp, 1, column)
            if key == 'lat': self._lat = sp
            else:            self._lng = sp
        loc_lay.addWidget(coord_w); loc_lay.addStretch()
        stack.addWidget(loc_panel)
        self._lat.setEnabled(self._manual.isChecked())
        self._lng.setEnabled(self._manual.isChecked())

        outer.addWidget(stack, 1)

        br = QHBoxLayout(); br.setSpacing(10)
        c = QPushButton('إلغاء'); c.setObjectName('cancel'); c.setFont(F(11))
        c.clicked.connect(self.reject)
        s = QPushButton('حفظ التغييرات'); s.setObjectName('ok'); s.setFont(F(12, bold=True))
        s.setDefault(True)
        s.clicked.connect(self._save)
        br.addWidget(c); br.addWidget(s, 1); outer.addLayout(br)

    def _save(self):
        self._cfg['method']     = self._method.currentData()
        self._cfg['school']     = self._school.currentData()
        self._cfg['manual_loc'] = self._manual.isChecked()
        self._cfg['sound_mode'] = self._sound_mode.currentData()
        self._cfg['notifications_muted'] = self._mute.isChecked()
        for nm, sp in self._iq.items(): self._cfg['iqama'][nm] = sp.value()
        if self._manual.isChecked():
            self._cfg['lat'] = self._lat.value()
            self._cfg['lng'] = self._lng.value()
        self.accept()

    def _preview_sound(self):
        if (self._preview_process is not None
                and self._preview_process.state() != QProcess.ProcessState.NotRunning):
            self._stop_preview()
            return
        path = sound_path(self._sound_mode.currentData())
        program, args = audio_command(path)
        if program and path and os.path.exists(path):
            process = QProcess(self)
            process.setProgram(program); process.setArguments(args)
            process.finished.connect(
                lambda exit_code=0, exit_status=None:
                    self._preview_finished(process))
            process.start()
            self._preview_process = process
            self._preview.setText('إيقاف')
            self._preview.setProperty('playing', True)
            self._preview.style().unpolish(self._preview)
            self._preview.style().polish(self._preview)

    def _preview_finished(self, process):
        if self._preview_process is process:
            self._preview_process = None
            self._preview.setText('تجربة')
            self._preview.setProperty('playing', False)
            self._preview.style().unpolish(self._preview)
            self._preview.style().polish(self._preview)
        process.deleteLater()

    def _stop_preview(self, *_):
        process = self._preview_process
        if process is not None:
            self._preview_process = None
            if process.state() != QProcess.ProcessState.NotRunning:
                process.kill()
                process.waitForFinished(400)
            process.deleteLater()
        self._preview.setText('تجربة')
        self._preview.setProperty('playing', False)
        self._preview.style().unpolish(self._preview)
        self._preview.style().polish(self._preview)

    def _mute_changed(self, muted):
        if muted:
            self._stop_preview()
        self._sound_mode.setEnabled(not muted)
        self._preview.setEnabled(not muted)

    def done(self, result):
        self._stop_preview()
        super().done(result)

    def result(self): return self._cfg

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._cfg      = load_cfg()
        self._times    = {}
        self._next_nm  = ''
        self._next_dt  = None
        self._iq_nm    = ''
        self._iq_end   = None
        self._in_iq    = False
        self._online   = False
        self._last_day = datetime.date.today()
        self._tray = None
        self._tray_menu = None
        self._last_notice = ''
        self._allow_quit = False
        self._tray_hint_shown = False
        self._sound_process = None
        self._syncing = False
        self._sync_pending = False
        self._setup()
        self._build()
        self._setup_tray()
        self._load_cache()
        self._fetch_all()
        self._timers()

    # ── window ────────────────────────────────────────────────────────────────

    def _setup(self):
        self.setWindowTitle('صلاتي')
        if os.path.exists(APP_ICON):
            self.setWindowIcon(QIcon(APP_ICON))
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setStyleSheet(f"""
            QMainWindow,#central {{
                background: qradialgradient(
                    cx:0.5, cy:0.18, radius:0.9,
                    fx:0.5, fy:0.18,
                    stop:0 #12312A,
                    stop:1 {BG}
                );
            }}
        """)
        self.setMinimumSize(600, 560)
        self.resize(720, 610)
        self.setMaximumWidth(900)
        scr = QApplication.primaryScreen().availableGeometry()
        self.move(scr.x() + (scr.width()-self.width())//2,
                  scr.y() + (scr.height()-self.height())//2)

    # ── UI BUILD ──────────────────────────────────────────────────────────────

    def _build(self):
        cw = QWidget(); cw.setObjectName('central')
        cw.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCentralWidget(cw)
        root = QVBoxLayout(cw); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        root.addWidget(self._topbar())
        body = QWidget(); body.setStyleSheet('background:transparent;')
        bl = QVBoxLayout(body); bl.setContentsMargins(24,16,24,18); bl.setSpacing(14)
        bl.addWidget(self._header())
        bl.addWidget(self._card_widget())
        bl.addWidget(self._schedule_header())
        bl.addWidget(self._cols_row())
        bl.addWidget(self._footer())
        root.addWidget(body)
        cw.setFocus()

    # ── TOP BAR ───────────────────────────────────────────────────────────────

    def _topbar(self):
        bar = QWidget(); bar.setFixedHeight(58)
        bar.setStyleSheet(f"""
            QWidget {{
                background: rgba(7,19,17,0.92);
                border-bottom: 1px solid {BORDER};
            }}
            QLabel  {{ color:{WHITE}; background:transparent; border:none; }}
        """)
        lay = QHBoxLayout(bar); lay.setContentsMargins(24,0,24,0); lay.setSpacing(10)
        brand = QWidget(); brand.setStyleSheet('background:transparent;border:none;')
        brand_l = QVBoxLayout(brand)
        brand_l.setContentsMargins(0,0,0,0); brand_l.setSpacing(0)
        ttl = QLabel('صلاتي'); ttl.setFont(F(17, bold=True))
        strap = QLabel('مواقيت الصلاة'); strap.setFont(F(7))
        strap.setStyleSheet(f'color:{MUTED};')
        brand_l.addWidget(ttl); brand_l.addWidget(strap)
        mark = QLabel('✦'); mark.setFixedSize(36,36)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter); mark.setFont(F(15))
        mark.setStyleSheet(f"""
            color:{GOLD_L}; background:rgba(213,169,78,0.12);
            border:1px solid rgba(213,169,78,0.35); border-radius:18px;
        """)
        self._refresh_btn = self._btn('تحديث', 'تحديث مواقيت الصلاة (Ctrl+R)', 66)
        self._refresh_btn.setShortcut('Ctrl+R')
        self._refresh_btn.clicked.connect(self._fetch_all)
        s_btn = self._btn('الإعدادات', 'فتح الإعدادات (Ctrl+,)', 78)
        s_btn.setShortcut('Ctrl+,')
        s_btn.clicked.connect(lambda: self._settings(s_btn))
        lay.addWidget(mark); lay.addWidget(brand); lay.addStretch()
        for w in (self._refresh_btn, s_btn): lay.addWidget(w)
        return bar

    # ── HEADER (city + date) ──────────────────────────────────────────────────

    def _header(self):
        w = QWidget(); w.setStyleSheet('background:transparent;')
        lay = QHBoxLayout(w); lay.setContentsMargins(0,0,0,0); lay.setSpacing(16)
        left_line = QFrame(); left_line.setFixedHeight(1)
        left_line.setStyleSheet(
            'background:qlineargradient(x1:0,y1:0,x2:1,y2:0,'
            'stop:0 transparent,stop:1 rgba(213,169,78,0.32));')
        right_line = QFrame(); right_line.setFixedHeight(1)
        right_line.setStyleSheet(
            'background:qlineargradient(x1:0,y1:0,x2:1,y2:0,'
            'stop:0 rgba(213,169,78,0.32),stop:1 transparent);')
        center = QWidget(); center.setStyleSheet('background:transparent;')
        center_lay = QVBoxLayout(center)
        center_lay.setContentsMargins(0,0,0,0); center_lay.setSpacing(3)
        self._city = QLabel('جاري التحديد…')
        self._city.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._city.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._city.setFont(F(18, bold=True))
        self._city.setStyleSheet(f'color:{WHITE};')
        self._hijri = QLabel(Hijri.fmt())
        self._hijri.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hijri.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._hijri.setFont(F(10))
        self._hijri.setStyleSheet(f"""
            color:{GOLD_L}; background:rgba(213,169,78,0.08);
            border-radius:9px; padding:2px 10px;
        """)
        self._gregorian = QLabel(Hijri.gregorian_fmt())
        self._gregorian.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._gregorian.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._gregorian.setFont(F(8))
        self._gregorian.setStyleSheet(f'color:{MUTED};')
        center_lay.addWidget(self._city)
        center_lay.addWidget(self._hijri)
        center_lay.addWidget(self._gregorian)
        lay.addWidget(left_line, 1); lay.addWidget(center); lay.addWidget(right_line, 1)
        return w

    # ── NEXT PRAYER CARD ──────────────────────────────────────────────────────

    def _card_widget(self):
        self._card = QFrame(); self._card.setObjectName('nextCard')
        self._card.setFixedHeight(146)
        self._card_mode = None

        # Outer VBox: accent bar at top + content row below
        ov = QVBoxLayout(self._card); ov.setContentsMargins(0,0,0,0); ov.setSpacing(0)

        self._card_accent = QFrame(); self._card_accent.setObjectName('cardAccent')
        self._card_accent.setFixedHeight(3)
        ov.addWidget(self._card_accent)

        content = QWidget(); content.setObjectName('cardContent')
        content.setStyleSheet('background:transparent;')
        # Use the application's natural RTL flow: prayer details stay on the
        # right and the countdown stays on the opposite side.
        content.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        ov.addWidget(content)

        lay = QHBoxLayout(content)
        lay.setContentsMargins(26, 10, 26, 16); lay.setSpacing(0)

        # ── LEFT zone: countdown ──────────────────────────────────────────────
        lz = QWidget(); lz.setObjectName('cardLz')
        lz.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        lz.setFixedWidth(210)
        ll = QVBoxLayout(lz); ll.setContentsMargins(0,0,22,0); ll.setSpacing(5)
        ll.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self._c_cd_lbl = QLabel('يتبقى')
        self._c_cd_lbl.setObjectName('cCdLbl')
        self._c_cd_lbl.setFont(F(8, semi=True))
        self._c_cd_lbl.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._c_cd_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._cd = QLabel('——:——:——')
        self._cd.setObjectName('cCd')
        self._cd.setFont(F(29, bold=True))
        self._cd.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._cd.setAlignment(Qt.AlignmentFlag.AlignLeft)

        ll.addWidget(self._c_cd_lbl)
        ll.addWidget(self._cd)

        # ── VERTICAL DIVIDER ─────────────────────────────────────────────────
        div = QFrame(); div.setFrameShape(QFrame.Shape.VLine)
        div.setFixedWidth(1)
        div.setStyleSheet('background:rgba(255,255,255,0.16); border:none;')
        div.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        # ── RIGHT zone: prayer info (RTL, visual right) ───────────────────────
        # Right zone — addWidget(w, 0, AlignRight) is the only reliable way
        # to right-align items in a QVBoxLayout
        rz = QWidget(); rz.setObjectName('cardRz')
        rz.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        rz.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        rl = QVBoxLayout(rz); rl.setContentsMargins(18,0,0,0); rl.setSpacing(4)

        # "الصلاة القادمة" tag
        self._c_tag = QLabel('الصلاة القادمة')
        self._c_tag.setObjectName('cTag')
        self._c_tag.setFont(F(8, semi=True))
        self._c_tag.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._c_tag.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._c_tag.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        tag_row = QWidget(); tag_row.setStyleSheet('background:transparent; border:none;')
        tag_row.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        tag_lay = QHBoxLayout(tag_row)
        tag_lay.setContentsMargins(0,0,0,0); tag_lay.setSpacing(0)
        tag_lay.addStretch(1); tag_lay.addWidget(self._c_tag)

        # icon + name row
        nr = QWidget(); nr.setObjectName('cardNr')
        nr.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        nr.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        nrl = QHBoxLayout(nr); nrl.setContentsMargins(0,0,0,0); nrl.setSpacing(10)
        self._card_ico = PrayerIcon('Fajr', size=24)
        self._c_name = QLabel('—')
        self._c_name.setObjectName('cName')
        self._c_name.setFont(F(29, bold=True))
        self._c_name.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._c_name.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._c_name.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        nrl.addWidget(self._card_ico)
        nrl.addWidget(self._c_name)

        # prayer time label
        self._c_time = QLabel('موعد الأذان  •  —')
        self._c_time.setObjectName('cTime')
        self._c_time.setFont(F(10))
        self._c_time.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._c_time.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        # addWidget(w, stretch=0, AlignRight) → VBoxLayout places each widget at right edge
        AR = Qt.AlignmentFlag.AlignRight
        rl.addStretch(1)
        rl.addWidget(tag_row)
        rl.addWidget(nr,          0, AR)
        rl.addWidget(self._c_time, 0, AR)
        rl.addStretch(1)

        lay.addWidget(rz, 1)
        lay.addWidget(div, 0)
        lay.addWidget(lz)

        self._set_card('next')
        return self._card

    def _set_card(self, mode: str):
        if self._card_mode == mode: return
        self._card_mode = mode
        tr = 'QWidget,QLabel,QFrame{background:transparent;border:none;}'
        if mode == 'iqama':
            self._card.setStyleSheet(f"""
                #nextCard{{
                    background:qlineargradient(x1:1,y1:0,x2:0,y2:0,
                        stop:0 rgba(47,175,125,0.28),
                        stop:0.55 rgba(47,175,125,0.10),
                        stop:1 rgba(47,175,125,0.02));
                    border:1px solid rgba(47,175,125,0.45);
                    border-radius:18px;
                }}
                #cardAccent{{
                    background:rgba(98,212,167,0.90);
                    border-top-left-radius:18px; border-top-right-radius:18px;
                }}
                {tr}
            """)
        else:
            self._card.setStyleSheet(f"""
                #nextCard{{
                    background:qlineargradient(x1:1,y1:0,x2:0,y2:0,
                        stop:0 rgba(213,169,78,0.28),
                        stop:0.55 rgba(213,169,78,0.10),
                        stop:1 rgba(213,169,78,0.02));
                    border:1px solid rgba(213,169,78,0.44);
                    border-radius:18px;
                }}
                #cardAccent{{
                    background:qlineargradient(x1:1,y1:0,x2:0,y2:0,
                        stop:0 {GOLD_L}, stop:1 rgba(213,169,78,0.28));
                    border-top-left-radius:18px; border-top-right-radius:18px;
                }}
                {tr}
            """)

    # ── PRAYER COLUMNS ────────────────────────────────────────────────────────

    def _schedule_header(self):
        w = QWidget(); w.setStyleSheet('background:transparent;')
        lay = QHBoxLayout(w); lay.setContentsMargins(2,0,2,0); lay.setSpacing(8)

        title_box = QWidget(); title_box.setStyleSheet('background:transparent;')
        title_lay = QVBoxLayout(title_box)
        title_lay.setContentsMargins(0,0,0,0); title_lay.setSpacing(0)
        title = QLabel('مواقيت اليوم'); title.setFont(F(12, semi=True))
        title.setStyleSheet(f'color:{WHITE};')
        hint = QLabel('حسب موقعك الحالي'); hint.setFont(F(8))
        hint.setStyleSheet(f'color:{DIM};')
        title_lay.addWidget(title); title_lay.addWidget(hint)

        sunrise = QFrame(); sunrise.setObjectName('sunriseChip')
        sunrise.setStyleSheet(f"""
            QFrame#sunriseChip {{
                background:rgba(213,169,78,0.08);
                border:1px solid rgba(213,169,78,0.22);
                border-radius:13px;
            }}
            QFrame#sunriseChip QLabel {{ background:transparent; border:none; }}
        """)
        sunrise_lay = QHBoxLayout(sunrise)
        sunrise_lay.setContentsMargins(10,5,10,5); sunrise_lay.setSpacing(7)
        sunrise_icon = PrayerIcon('Sunrise', size=17)
        sunrise_icon.set_color(GOLD_L)
        sunrise_text = QLabel('الشروق'); sunrise_text.setFont(F(8))
        sunrise_text.setStyleSheet(f'color:{MUTED};')
        self._sunrise = QLabel('--:--'); self._sunrise.setFont(F(9, semi=True))
        self._sunrise.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._sunrise.setStyleSheet(f'color:{GOLD_L};')
        sunrise_lay.addWidget(sunrise_icon)
        sunrise_lay.addWidget(sunrise_text)
        sunrise_lay.addWidget(self._sunrise)

        lay.addWidget(title_box); lay.addStretch(); lay.addWidget(sunrise)
        return w

    def _cols_row(self):
        w = QWidget(); w.setStyleSheet('background:transparent;')
        lay = QHBoxLayout(w); lay.setContentsMargins(0,0,0,0); lay.setSpacing(8)
        self._cols = {}
        for nm in ACTIVE_PRAY:
            col = PrayerColumn(nm); self._cols[nm] = col; lay.addWidget(col, 1)
        return w

    # ── FOOTER ────────────────────────────────────────────────────────────────

    def _footer(self):
        w = QWidget(); w.setStyleSheet('background:transparent;')
        lay = QHBoxLayout(w); lay.setContentsMargins(2,0,2,0); lay.setSpacing(8)
        self._mth_lbl = QLabel(METHODS.get(self._cfg.get('method',3),''))
        self._mth_lbl.setFont(F(8)); self._mth_lbl.setStyleSheet(f'color:{DIM};')
        self._mth_lbl.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._net = QLabel('●  جارٍ التحميل'); self._net.setFont(F(8, semi=True))
        self._net.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._net.setStyleSheet(f"""
            color:{DIM}; background:rgba(255,255,255,0.04);
            border:1px solid rgba(255,255,255,0.07);
            border-radius:10px; padding:3px 9px;
        """)
        self._net.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        lay.addWidget(self._mth_lbl); lay.addStretch(); lay.addWidget(self._net)
        return w

    def _btn(self, text, tip='', width=34):
        b = QPushButton(text); b.setFixedSize(width,34); b.setToolTip(tip)
        b.setFont(F(9, semi=True))
        b.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        b.setStyleSheet(f"""
            QPushButton{{background:rgba(255,255,255,0.07);color:{MUTED};
                border:1px solid {BORDER};border-radius:17px;padding:0 10px;}}
            QPushButton:hover{{background:rgba(255,255,255,0.14);color:{WHITE};}}
            QPushButton:pressed{{background:rgba(213,169,78,0.24);}}
            QPushButton:focus{{border:1px solid {GOLD};color:{WHITE};}}
            QPushButton:disabled{{color:{DIM};background:rgba(255,255,255,0.03);}}
        """)
        return b

    # ── SYSTEM TRAY ──────────────────────────────────────────────────────────

    def _tray_icon(self):
        """Create a crisp tray icon without depending on an external asset."""
        if os.path.exists(APP_ICON):
            return QIcon(APP_ICON)
        pix = QPixmap(64, 64); pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(BORDER), 2))
        p.setBrush(QColor(SURFACE))
        p.drawEllipse(QRectF(3, 3, 58, 58))

        outer = QPainterPath(); outer.addEllipse(QRectF(16, 13, 34, 38))
        cut = QPainterPath(); cut.addEllipse(QRectF(25, 9, 34, 38))
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(GOLD_L))
        p.drawPath(outer.subtracted(cut))
        p.drawEllipse(QRectF(45, 16, 5, 5))
        p.end()
        return QIcon(pix)

    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(self._tray_icon(), self)
        self._tray_menu = QMenu()
        self._tray_menu.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._tray_menu.setFont(F(10))
        self._tray_menu.setStyleSheet(f"""
            QMenu {{
                background:{SURFACE}; color:{WHITE};
                border:1px solid {BORDER}; border-radius:10px;
                padding:7px;
            }}
            QMenu::item {{ padding:7px 18px; border-radius:7px; }}
            QMenu::item:selected {{ background:rgba(213,169,78,0.18); color:{GOLD_L}; }}
            QMenu::item:disabled {{ color:{MUTED}; }}
            QMenu::separator {{ height:1px; background:{BORDER}; margin:6px 10px; }}
        """)
        self._tray.setContextMenu(self._tray_menu)
        self._tray.activated.connect(self._tray_activated)
        self._refresh_tray()
        self._tray.show()
        QApplication.instance().setQuitOnLastWindowClosed(False)

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show()
            self.raise_()
            self.activateWindow()

    def _refresh_tray(self):
        if self._tray is None or self._tray_menu is None:
            return

        city = (self._cfg.get('city_display') or self._cfg.get('city_ar')
                or self._cfg.get('city_en') or 'الموقع الحالي')
        next_name = PRAYER_AR.get(self._next_nm, '—')
        next_time = ''
        if self._next_dt:
            next_time = f'{self._next_dt.hour:02d}:{self._next_dt.minute:02d}'

        tooltip_lines = [f'صلاتي — {city}']
        if self._next_nm:
            tooltip_lines.append(f'القادمة: {next_name}  {next_time}')
        for nm in ('Fajr','Sunrise','Dhuhr','Asr','Maghrib','Isha'):
            if nm in self._times:
                tooltip_lines.append(f'{PRAYER_AR[nm]}: {self._times[nm]}')
        self._tray.setToolTip('\n'.join(tooltip_lines))

        menu = self._tray_menu
        menu.clear()
        title = QAction(f'صلاتي  •  {city}', menu)
        title.setEnabled(False); menu.addAction(title)
        if self._next_nm:
            upcoming = QAction(f'القادمة: {next_name}  —  {next_time}', menu)
            upcoming.setEnabled(False); menu.addAction(upcoming)
        menu.addSeparator()
        for nm in ('Fajr','Sunrise','Dhuhr','Asr','Maghrib','Isha'):
            if nm in self._times:
                action = QAction(
                    f'{PRAYER_AR[nm]}                         {self._times[nm]}',
                    menu)
                action.setEnabled(False); menu.addAction(action)
        menu.addSeparator()
        show_action = menu.addAction('إظهار صلاتي')
        show_action.triggered.connect(self._show_from_tray)
        refresh_action = menu.addAction('تحديث المواقيت')
        refresh_action.triggered.connect(self._fetch_all)
        settings_action = menu.addAction('الإعدادات')
        settings_action.triggered.connect(lambda: self._settings())
        menu.addSeparator()
        quit_action = menu.addAction('خروج')
        quit_action.triggered.connect(self._quit_from_tray)

    def _show_from_tray(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _quit_from_tray(self):
        self._allow_quit = True
        QApplication.instance().quit()

    def _check_prayer_notification(self):
        if (self._tray is None or not self._times
                or self._cfg.get('notifications_muted', False)):
            return
        now = datetime.datetime.now()
        minute = now.replace(second=0, microsecond=0)
        iq_cfg = self._cfg.get('iqama', IQAMA_DEF)
        for nm in ACTIVE_PRAY:
            if nm not in self._times:
                continue
            adhan = self._parse(self._times[nm])
            iqama = adhan + datetime.timedelta(
                minutes=int(iq_cfg.get(nm, 15)))
            if minute == adhan:
                key = f'{now.date()}:{nm}:adhan'
                if key != self._last_notice:
                    self._last_notice = key
                    delay = int(iq_cfg.get(nm, 15))
                    iqama_text = (
                        'الإقامة الآن' if delay == 0
                        else f'متبقي على الإقامة {delay} دقيقة')
                    self._tray.showMessage(
                        'حان وقت الصلاة',
                        f'حان الآن وقت صلاة {PRAYER_AR[nm]} • {iqama_text}',
                        QSystemTrayIcon.MessageIcon.Information, 8000)
                    self._play_sound(self._cfg.get('sound_mode', 'adhan'))
                return
            if minute == iqama:
                key = f'{now.date()}:{nm}:iqama'
                if key != self._last_notice:
                    self._last_notice = key
                    self._tray.showMessage(
                        'موعد الإقامة',
                        f'حان الآن موعد إقامة صلاة {PRAYER_AR[nm]}',
                        QSystemTrayIcon.MessageIcon.Information, 8000)
                    self._play_sound('chime')
                return

    def _play_sound(self, mode):
        path = sound_path(mode)
        program, args = audio_command(path)
        if not program or not path or not os.path.exists(path):
            return
        if self._sound_process is not None:
            self._sound_process.kill()
            self._sound_process.deleteLater()
        process = QProcess(self)
        process.setProgram(program); process.setArguments(args)
        process.finished.connect(lambda: self._sound_finished(process))
        process.start()
        self._sound_process = process

    def _sound_finished(self, process):
        if self._sound_process is process:
            self._sound_process = None
        process.deleteLater()

    def closeEvent(self, event):
        if self._tray is not None and not self._allow_quit:
            event.ignore()
            self.hide()
            if not self._tray_hint_shown:
                self._tray_hint_shown = True
                self._tray.showMessage(
                    'صلاتي يعمل في الخلفية',
                    'يمكنك فتح المواقيت أو الخروج من أيقونة شريط النظام.',
                    QSystemTrayIcon.MessageIcon.Information, 5000)
            return
        super().closeEvent(event)

    # ── NETWORK ───────────────────────────────────────────────────────────────

    def _fetch_all(self):
        if self._syncing:
            return
        self._syncing = True
        self._refresh_btn.setEnabled(False)
        self._refresh_btn.setText('يحدّث…')
        self._set_sync_status('loading')
        if self._cfg.get('manual_loc') and self._cfg.get('lat'):
            self._fetch_times(self._cfg['lat'], self._cfg['lng'])
        else:
            lf = LocationFetcher()
            lf.ok.connect(self._on_loc); lf.fail.connect(self._on_loc_fail)
            lf.finished.connect(lf.deleteLater); self._lf = lf; lf.start()

    def _on_loc(self, d):
        lat, lng = d.get('lat',0), d.get('lon',0)
        ce, coe  = d.get('city',''), d.get('country','')
        ca  = CITY_AR.get(ce, ce)
        coa = COUNTRY_AR.get(coe, '')
        disp = f'{ca}  ·  {coa}' if coa else ca
        self._cfg.update({'lat':lat,'lng':lng,'city_en':ce,
                          'city_ar':ca,'city_display':disp})
        self._city.setText(disp)
        self.setWindowTitle(f'صلاتي  —  {ca or ce}')
        self._fetch_times(lat, lng)

    def _on_loc_fail(self, _):
        if self._cfg.get('lat'): self._fetch_times(self._cfg['lat'], self._cfg['lng'])
        else:
            self._sync_finished()
            self._set_sync_status('error', 'تعذّر تحديد الموقع')

    def _fetch_times(self, lat, lng):
        tf = TimeFetcher(lat, lng, self._cfg.get('method',3), self._cfg.get('school',0))
        tf.ok.connect(self._on_times); tf.fail.connect(self._on_fail)
        tf.finished.connect(tf.deleteLater); self._tf = tf; tf.start()

    def _on_times(self, raw):
        self._times = {k: raw[k].split(' ')[0].split('(')[0].strip()
                       for k in ('Fajr','Sunrise','Dhuhr','Asr','Maghrib','Isha')
                       if k in raw}
        self._online = True
        self._sync_finished()
        self._set_sync_status('online')
        disp = (self._cfg.get('city_display') or self._cfg.get('city_ar')
                or self._cfg.get('city_en',''))
        if disp: self._city.setText(disp); self.setWindowTitle(f'صلاتي  —  {self._cfg.get("city_ar") or disp}')
        self._save_cache(); self._refresh()

    def _on_fail(self, _):
        self._online = False
        self._sync_finished()
        if self._times:
            self._set_sync_status('cached')
        else:
            self._set_sync_status('error', 'لا يوجد اتصال')

    def _sync_finished(self):
        self._syncing = False
        self._refresh_btn.setEnabled(True)
        self._refresh_btn.setText('تحديث')
        if self._sync_pending:
            self._sync_pending = False
            QTimer.singleShot(0, self._fetch_all)

    def _set_sync_status(self, state, text=''):
        styles = {
            'loading': (DIM, 'rgba(255,255,255,0.04)', 'جارٍ التحديث'),
            'online': (GREEN_L, 'rgba(47,175,125,0.10)', 'محدّث الآن'),
            'cached': (GOLD_L, 'rgba(213,169,78,0.10)', 'بيانات محفوظة'),
            'error': (AMBER, 'rgba(214,155,69,0.10)', text or 'تعذّر التحديث'),
        }
        color, background, label = styles.get(state, styles['loading'])
        self._net.setText(f'●  {label}')
        self._net.setToolTip({
            'online': 'تم جلب المواقيت بنجاح',
            'cached': 'تُعرض آخر مواقيت محفوظة لهذا اليوم',
            'loading': 'يجري الاتصال بخدمة المواقيت',
            'error': label,
        }.get(state, ''))
        self._net.setStyleSheet(f"""
            color:{color}; background:{background};
            border:1px solid {color}; border-radius:10px; padding:3px 9px;
        """)

    # ── CACHE ─────────────────────────────────────────────────────────────────

    def _save_cache(self):
        save_cfg(self._cfg)
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CACHE_FILE,'w',encoding='utf-8') as f:
            json.dump({'date':datetime.date.today().isoformat(),
                       'city_ar':self._cfg.get('city_ar',''),
                       'city_en':self._cfg.get('city_en',''),
                       'city_display':self._cfg.get('city_display',''),
                       'lat':self._cfg.get('lat'),'lng':self._cfg.get('lng'),
                       'times':self._times}, f, ensure_ascii=False, indent=2)

    def _load_cache(self):
        if not os.path.exists(CACHE_FILE): return
        try:
            with open(CACHE_FILE,encoding='utf-8') as f: c=json.load(f)
            if c.get('date') != datetime.date.today().isoformat(): return
            if not c.get('times'): return
            self._times = c['times']
            for k in ('lat','lng','city_ar','city_en','city_display'):
                if c.get(k): self._cfg[k] = c[k]
            disp = c.get('city_display') or c.get('city_ar') or c.get('city_en','')
            if disp:
                self._city.setText(disp)
                self.setWindowTitle(f'صلاتي  —  {c.get("city_ar") or disp}')
            self._set_sync_status('cached')
            self._refresh()
        except Exception: pass

    # ── REFRESH ───────────────────────────────────────────────────────────────

    def _refresh(self):
        self._hijri.setText(Hijri.fmt())
        self._gregorian.setText(Hijri.gregorian_fmt())
        self._sunrise.setText(self._times.get('Sunrise', '--:--'))
        for nm, col in self._cols.items():
            if nm in self._times: col.set_time(self._times[nm])
        self._mth_lbl.setText(METHODS.get(self._cfg.get('method',3),''))
        self._update()

    def _parse(self, hhmm: str) -> datetime.datetime:
        h, m = map(int, hhmm.split(':')[:2])
        d = datetime.date.today()
        return datetime.datetime(d.year, d.month, d.day, h, m)

    def _update(self):
        if not self._times: return
        now    = datetime.datetime.now()
        iq_cfg = self._cfg.get('iqama', IQAMA_DEF)

        prayers = []
        for nm in ACTIVE_PRAY:
            if nm not in self._times: continue
            az = self._parse(self._times[nm])
            iq = az + datetime.timedelta(minutes=int(iq_cfg.get(nm, 15)))
            prayers.append((nm, az, iq))
        prayers.sort(key=lambda x: x[1])

        states: dict[str,str] = {}
        self._in_iq  = False
        self._iq_nm  = ''
        self._iq_end = None
        self._next_nm = ''
        self._next_dt = None
        nxt_found = False

        for nm, az, iq in prayers:
            if now >= iq:
                states[nm] = 'past'
            elif now >= az:
                states[nm]  = 'iqama'
                self._in_iq = True
                self._iq_nm = nm
                self._iq_end = iq
            else:
                if not nxt_found and not self._in_iq:
                    states[nm] = 'next'
                    self._next_nm = nm
                    self._next_dt = az
                    nxt_found = True
                else:
                    states[nm] = 'normal'

        # After iqama: find next prayer
        if self._in_iq and not self._next_nm:
            found = False
            for nm, az, _ in prayers:
                if found and now < az: self._next_nm = nm; self._next_dt = az; break
                if nm == self._iq_nm: found = True

        # All passed today → next Fajr tomorrow
        if not self._in_iq and not self._next_nm and 'Fajr' in self._times:
            tom = datetime.date.today() + datetime.timedelta(days=1)
            h, m = map(int, self._times['Fajr'].split(':')[:2])
            self._next_nm = 'Fajr'
            self._next_dt = datetime.datetime(tom.year, tom.month, tom.day, h, m)

        for nm, col in self._cols.items():
            col.set_state(states.get(nm, 'normal'))

        tr = 'background:transparent;border:none;'
        if self._in_iq:
            self._set_card('iqama')
            self._card_ico.set_name(self._iq_nm or 'Fajr')
            self._card_ico.set_color(GREEN_L)
            self._c_tag.setText('إقامة الصلاة')
            self._c_tag.setStyleSheet(f"""
                color:{GREEN_L}; background:rgba(47,175,125,0.18);
                border-radius:9px; padding:2px 9px; {tr}
            """)
            self._c_name.setText(PRAYER_AR.get(self._iq_nm,''))
            self._c_name.setStyleSheet(f'color:{GREEN_L};{tr}')
            self._c_time.setText(
                f'موعد الأذان  •  {self._times.get(self._iq_nm, "—")}')
            self._c_time.setStyleSheet(f'color:rgba(98,212,167,0.68);{tr}')
            self._c_cd_lbl.setText('يتبقى على الإقامة')
            self._c_cd_lbl.setStyleSheet(f"""
                color:{GREEN}; background:rgba(47,175,125,0.14);
                border-radius:8px; padding:1px 7px; {tr}
            """)
            self._cd.setStyleSheet(f'color:{GREEN_L};{tr}')
        else:
            self._set_card('next')
            self._card_ico.set_name(self._next_nm or 'Fajr')
            self._card_ico.set_color(GOLD_L)
            self._c_tag.setText('الصلاة القادمة')
            self._c_tag.setStyleSheet(f"""
                color:{GOLD_L}; background:rgba(213,169,78,0.18);
                border-radius:9px; padding:2px 9px; {tr}
            """)
            self._c_name.setText(PRAYER_AR.get(self._next_nm, '—'))
            self._c_name.setStyleSheet(f'color:{WHITE};{tr}')
            t = self._next_dt
            prayer_time = f'{t.hour:02d}:{t.minute:02d}' if t else '—'
            self._c_time.setText(f'موعد الأذان  •  {prayer_time}')
            self._c_time.setStyleSheet(f'color:rgba(240,190,74,0.70);{tr}')
            self._c_cd_lbl.setText('يتبقى')
            self._c_cd_lbl.setStyleSheet(f"""
                color:{MUTED}; background:rgba(255,255,255,0.07);
                border-radius:8px; padding:1px 7px; {tr}
            """)
            self._cd.setStyleSheet(f'color:{GOLD_L};{tr}')
        self._paint_countdown()
        self._refresh_tray()

    # ── TIMERS ────────────────────────────────────────────────────────────────

    def _timers(self):
        QTimer(self).setInterval(1000); t=QTimer(self); t.timeout.connect(self._tick); t.start(1000)
        d=QTimer(self); d.timeout.connect(self._day_chk); d.start(30_000)
        a=QTimer(self); a.timeout.connect(self._fetch_all); a.start(3_600_000)

    def _tick(self):
        self._check_prayer_notification()
        if self._paint_countdown() == 0:
            self._update()

    def _paint_countdown(self):
        target = self._iq_end if self._in_iq else self._next_dt
        if not target: return None
        rem = max(0, int((target - datetime.datetime.now()).total_seconds()))
        if rem == 0:
            self._cd.setText('00:00:00')
            return 0
        h=rem//3600; m=(rem%3600)//60; s=rem%60
        self._cd.setText(f'{h:02d}:{m:02d}:{s:02d}')
        return rem

    def _day_chk(self):
        t = datetime.date.today()
        if t != self._last_day: self._last_day = t; self._fetch_all()

    # ── SETTINGS ──────────────────────────────────────────────────────────────

    def _settings(self, anchor=None):
        dlg = SettingsDialog(self._cfg, self)
        if anchor is not None:
            screen = anchor.screen().availableGeometry()
            point = anchor.mapToGlobal(anchor.rect().bottomLeft())
            x = max(screen.left() + 12,
                    min(point.x(), screen.right() - dlg.width() - 12))
            y = point.y() + 8
            if y + dlg.height() > screen.bottom() - 12:
                y = max(screen.top() + 12,
                        anchor.mapToGlobal(anchor.rect().topLeft()).y()
                        - dlg.height() - 8)
            dlg.move(x, y)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._cfg = dlg.result()
            save_cfg(self._cfg)
            if (self._cfg.get('notifications_muted', False)
                    and self._sound_process is not None):
                self._sound_process.kill()
            self._mth_lbl.setText(METHODS.get(self._cfg.get('method',3),''))
            if os.path.exists(CACHE_FILE): os.remove(CACHE_FILE)
            if self._syncing:
                self._sync_pending = True
            else:
                self._fetch_all()

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    start_in_background = '--background' in sys.argv
    qt_args = [arg for arg in sys.argv if arg != '--background']
    app = QApplication(qt_args)
    app.setApplicationName('Salaty')
    app.setDesktopFileName('salaty')

    # Keep exactly one Salaty process per user. A later manual launch asks the
    # running process to show its window instead of starting another copy.
    server_name = f'salaty-{os.getuid()}'
    existing = QLocalSocket()
    existing.connectToServer(server_name)
    if existing.waitForConnected(500):
        existing.write(b'background' if start_in_background else b'show')
        existing.waitForBytesWritten(500)
        return

    os.makedirs(CONFIG_DIR, exist_ok=True)
    instance_lock = QLockFile(os.path.join(CONFIG_DIR, 'instance.lock'))
    if not instance_lock.tryLock(500):
        # The first copy may still be starting and not listening yet.
        existing.abort()
        existing.connectToServer(server_name)
        if existing.waitForConnected(1000):
            existing.write(b'background' if start_in_background else b'show')
            existing.waitForBytesWritten(500)
        return

    server = QLocalServer(app)
    if not server.listen(server_name):
        # A crashed process can leave a stale local socket behind.
        QLocalServer.removeServer(server_name)
        if not server.listen(server_name):
            print('تعذّر إنشاء قفل النسخة الواحدة لصلاتي.', file=sys.stderr)

    if os.path.exists(APP_ICON):
        app.setWindowIcon(QIcon(APP_ICON))
    _load_fonts()
    app.setFont(F(11))
    win = MainWindow()
    # Autostart stays out of the way when a tray is available. On desktops
    # without tray support, keep the window visible so the app is not hidden
    # with no way to reopen it.
    if not start_in_background or win._tray is None:
        win.show()

    def handle_new_instance():
        connection = server.nextPendingConnection()
        if connection is None:
            return

        def handle_request():
            request = bytes(connection.readAll())
            if request == b'show':
                win._show_from_tray()
            connection.disconnectFromServer()
            connection.deleteLater()

        if connection.bytesAvailable():
            handle_request()
        else:
            connection.readyRead.connect(handle_request)

    server.newConnection.connect(handle_new_instance)
    if server.hasPendingConnections():
        handle_new_instance()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
