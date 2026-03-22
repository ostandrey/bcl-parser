"""Generates assets/icon.ico for use with PyInstaller."""
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QLinearGradient
from PyQt6.QtCore import Qt, QRect

app = QApplication(sys.argv)

px = QPixmap(256, 256)
px.fill(Qt.GlobalColor.transparent)
p = QPainter(px)
p.setRenderHint(QPainter.RenderHint.Antialiasing)

grad = QLinearGradient(0, 0, 256, 256)
grad.setColorAt(0.0, QColor('#7965AF'))
grad.setColorAt(1.0, QColor('#5B3F96'))
p.setBrush(grad)
p.setPen(Qt.PenStyle.NoPen)
p.drawRoundedRect(0, 0, 256, 256, 36, 36)

p.setPen(QColor('#FFFFFF'))
p.setFont(QFont('Segoe UI', 122, QFont.Weight.Bold))
p.drawText(QRect(0, 0, 256, 256), Qt.AlignmentFlag.AlignCenter, 'B')
p.end()

Path('assets').mkdir(exist_ok=True)
ok = px.save('assets/icon.ico', 'ICO')
print('icon.ico saved.' if ok else 'ERROR: could not save icon.ico')
sys.exit(0 if ok else 1)
