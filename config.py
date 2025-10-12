import os
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-secret')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'restaurant.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    QRCODE_FOLDER = os.path.join(BASE_DIR, 'static', 'qrcodes')
    BILL_WIDTH_MM = int(os.environ.get('BILL_WIDTH_MM', 80))  # thermal width default 80 mm
