from flask import Flask, render_template, redirect, url_for, request, flash, session, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin
from flask_socketio import SocketIO
import pdfkit
import os
import qrcode
from werkzeug.utils import secure_filename
from datetime import datetime
import pytz

# -------------------- Flask App --------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restaurant.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Upload folders
UPLOAD_FOLDER = os.path.join(app.static_folder, 'images')
QRCODE_FOLDER = os.path.join(app.static_folder, 'qrcodes')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(QRCODE_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['QRCODE_FOLDER'] = QRCODE_FOLDER

# LAN Host for QR
BASE_HOST_FOR_QR = "http://192.168.29.118:5000"

# DB
db = SQLAlchemy(app)

# SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'

# -------------------- PDFKIT CONFIG --------------------
WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

# -------------------- Models --------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True)
    password = db.Column(db.String(80))

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    price = db.Column(db.Float)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    image = db.Column(db.String(100))
    category = db.relationship('Category')

class Table(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    table_id = db.Column(db.Integer, db.ForeignKey('table.id'))
    status = db.Column(db.String(20), default='pending')
    table = db.relationship('Table')
    order_items = db.relationship('OrderItem', backref='order', cascade="all, delete-orphan")
    created_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(pytz.timezone("Asia/Kolkata"))
    )

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    qty = db.Column(db.Integer)
    price = db.Column(db.Float)
    product = db.relationship('Product')

# -------------------- Load User --------------------
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# -------------------- Helper: QR generation --------------------
def generate_table_qr(table_id):
    host = BASE_HOST_FOR_QR
    qr_url = f"{host}/menu/{table_id}"
    qr_folder = app.config['QRCODE_FOLDER']
    os.makedirs(qr_folder, exist_ok=True)
    qr_path = os.path.join(qr_folder, f"table_{table_id}.png")

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=6, border=4)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(qr_path)
    return f"qrcodes/table_{table_id}.png"

def remove_table_qr(table_id):
    qr_path = os.path.join(app.config['QRCODE_FOLDER'], f"table_{table_id}.png")
    if os.path.exists(qr_path):
        try:
            os.remove(qr_path)
        except OSError:
            pass

# -------------------- Admin Login/Logout --------------------
@app.route('/admin/login', methods=['GET','POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            login_user(user)
            return redirect(url_for('admin_index'))
        else:
            flash("Invalid credentials", "danger")
    return render_template('admin_login.html')

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for('admin_login'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('admin_login'))

# -------------------- Admin Dashboard --------------------
@app.route('/admin/')
@login_required
def admin_index():
    return render_template('admin_index.html')

# -------------------- CRUD: Categories --------------------
@app.route('/admin/categories')
@login_required
def admin_categories():
    categories = Category.query.all()
    return render_template('admin_categories.html', categories=categories)

@app.route('/admin/categories/add', methods=['GET','POST'])
@login_required
def add_category():
    if request.method == 'POST':
        db.session.add(Category(name=request.form['name']))
        db.session.commit()
        return redirect(url_for('admin_categories'))
    return render_template('admin_add_category.html')

@app.route('/admin/categories/edit/<int:id>', methods=['GET','POST'])
@login_required
def edit_category(id):
    category = Category.query.get_or_404(id)
    if request.method == 'POST':
        category.name = request.form['name']
        db.session.commit()
        return redirect(url_for('admin_categories'))
    return render_template('admin_edit_category.html', category=category)

@app.route('/admin/categories/delete/<int:id>')
@login_required
def delete_category(id):
    category = Category.query.get_or_404(id)
    db.session.delete(category)
    db.session.commit()
    return redirect(url_for('admin_categories'))

# -------------------- CRUD: Products --------------------
@app.route('/admin/products')
@login_required
def admin_products():
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category_id', type=int)
    sort_by = request.args.get('sort_by', 'newest')

    query = Product.query
    if category_id:
        query = query.filter_by(category_id=category_id)

    if sort_by == 'name_asc':
        query = query.order_by(Product.name.asc())
    elif sort_by == 'name_desc':
        query = query.order_by(Product.name.desc())
    elif sort_by == 'price_asc':
        query = query.order_by(Product.price.asc())
    elif sort_by == 'price_desc':
        query = query.order_by(Product.price.desc())
    elif sort_by == 'newest':
        query = query.order_by(Product.id.desc())
    else:
        query = query.order_by(Product.id.asc())

    products = query.paginate(page=page, per_page=10)
    categories = Category.query.all()
    return render_template('admin_products.html', products=products, categories=categories,
                           category_id=category_id, sort_by=sort_by)

@app.route('/admin/products/add', methods=['GET','POST'])
@login_required
def add_product():
    categories = Category.query.all()
    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        category_id = request.form['category_id']
        image_file = request.files.get('image')

        filename = None
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        product = Product(name=name, price=price, category_id=category_id, image=filename)
        db.session.add(product)
        db.session.commit()
        return redirect(url_for('admin_products'))

    return render_template('admin_add_product.html', categories=categories)

@app.route('/admin/products/edit/<int:id>', methods=['GET','POST'])
@login_required
def edit_product(id):
    product = Product.query.get_or_404(id)
    categories = Category.query.all()
    if request.method == 'POST':
        product.name = request.form['name']
        product.price = request.form['price']
        product.category_id = request.form['category_id']

        image_file = request.files.get('image')
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            product.image = filename

        db.session.commit()
        return redirect(url_for('admin_products'))

    return render_template('admin_edit_product.html', product=product, categories=categories)

@app.route('/admin/products/delete/<int:id>')
@login_required
def delete_product(id):
    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    return redirect(url_for('admin_products'))

# -------------------- CRUD: Tables --------------------
@app.route('/admin/tables')
@login_required
def admin_tables():
    tables = Table.query.all()
    return render_template('admin_tables.html', tables=tables)

@app.route('/admin/tables/add', methods=['GET','POST'])
@login_required
def add_table():
    if request.method == 'POST':
        table = Table(name=request.form['name'])
        db.session.add(table)
        db.session.commit()
        generate_table_qr(table.id)
        return redirect(url_for('admin_tables'))
    return render_template('admin_add_table.html')

@app.route('/admin/tables/edit/<int:id>', methods=['GET','POST'])
@login_required
def edit_table(id):
    table = Table.query.get_or_404(id)
    if request.method == 'POST':
        table.name = request.form['name']
        db.session.commit()
        generate_table_qr(table.id)
        return redirect(url_for('admin_tables'))
    return render_template('admin_edit_table.html', table=table)

@app.route('/admin/tables/delete/<int:id>')
@login_required
def delete_table(id):
    table = Table.query.get_or_404(id)
    remove_table_qr(table.id)
    db.session.delete(table)
    db.session.commit()
    return redirect(url_for('admin_tables'))

# -------------------- Admin Orders --------------------
@app.route('/admin/orders')
@login_required
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin_orders.html', orders=orders)

# -------------------- Customer Menu --------------------
@app.route('/menu/<int:table_id>', methods=['GET', 'POST'])
def menu(table_id):
    table = Table.query.get_or_404(table_id)
    categories = Category.query.all()
    products = Product.query.all()

    if 'cart' not in session:
        session['cart'] = {}

    if request.method == 'POST':
        action = request.form.get('action')
        pid = request.form.get('product_id')

        if pid:
            pid = str(pid)
            if action == 'increase':
                session['cart'][pid] = session['cart'].get(pid, 0) + 1
            elif action == 'decrease':
                if session['cart'].get(pid, 0) > 1:
                    session['cart'][pid] -= 1
                else:
                    session['cart'].pop(pid, None)
            session.modified = True

        if action == 'go_to_cart':
            return redirect(url_for('cart', table_id=table_id))

        if action == 'place_order':
            cart = session.get('cart', {})
            if not cart:
                flash("Cart is empty!", "warning")
                return redirect(url_for('menu', table_id=table_id))

            order = Order.query.filter_by(table_id=table.id).filter(Order.status.in_(['pending','preparing'])).first()
            if not order:
                order = Order(table_id=table.id)
                db.session.add(order)
                db.session.commit()

            for pid_str, qty in cart.items():
                if not qty:
                    continue
                existing = OrderItem.query.filter_by(order_id=order.id, product_id=product.id).first()
                if existing:
                    existing.qty = (existing.qty or 0) + qty
                    existing.price = existing.qty * product.price
                else:
                    db.session.add(OrderItem(order_id=order.id,
                                             product_id=product.id,
                                             qty=qty,
                                             price=product.price * qty))
            db.session.commit()

            try:
                socketio.emit('new_order', {
                    'order_id': order.id,
                    'table_id': order.table_id,
                    'status': order.status,
                    'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }, broadcast=True)
            except Exception:
                pass

            session['cart'] = {}
            session.modified = True
            flash("Order placed successfully!", "success")
            return redirect(url_for('my_orders', table_id=table_id))

    cart_items = {}
    for pid, qty in session.get('cart', {}).items():
        product = Product.query.get(int(pid))
        if product:
            cart_items[pid] = {'product': product, 'qty': qty}

    return render_template('menu.html', table=table, categories=categories,
                           products=products, cart=session.get('cart', {}), cart_items=cart_items)

# -------------------- Cart --------------------
@app.route('/cart/<int:table_id>', methods=['GET','POST'])
def cart(table_id):
    table = Table.query.get_or_404(table_id)
    cart = session.get('cart', {})
    cart_items, total_price = [], 0

    for pid, qty in cart.items():
        product = Product.query.get(int(pid))
        if product:
            subtotal = product.price * qty
            cart_items.append({'product': product, 'qty': qty, 'subtotal': subtotal})
            total_price += subtotal

    if request.method == 'POST':
        action = request.form.get('action')
        pid = request.form.get('product_id')

        if pid:
            pid = str(pid)
            if action == 'increase':
                session['cart'][pid] = session['cart'].get(pid, 0) + 1
            elif action == 'decrease' and session['cart'].get(pid, 0) > 1:
                session['cart'][pid] -= 1
            elif action == 'remove':
                session['cart'].pop(pid, None)
            session.modified = True
            return redirect(url_for('cart', table_id=table_id))

        if action == 'place_order' and cart_items:
            order = Order.query.filter_by(table_id=table.id).filter(Order.status.in_(['pending','preparing'])).first()
            if not order:
                order = Order(table_id=table.id)
                db.session.add(order)
                db.session.commit()

            for item in cart_items:
                product = item['product']
                existing = OrderItem.query.filter_by(order_id=order.id, product_id=product.id).first()
                if existing:
                    existing.qty = (existing.qty or 0) + item['qty']
                    existing.price = existing.qty * product.price
                else:
                    db.session.add(OrderItem(order_id=order.id,
                                             product_id=product.id,
                                             qty=item['qty'],
                                             price=item['subtotal']))
            db.session.commit()

            try:
                socketio.emit('new_order', {
                    'order_id': order.id,
                    'table_id': order.table_id,
                    'status': order.status,
                    'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }, broadcast=True)
            except Exception:
                pass

            session['cart'] = {}
            session.modified = True
            flash(f"Order placed! Total ₹{total_price}", "success")
            return redirect(url_for('my_orders', table_id=table_id))

    return render_template('cart.html', table=table, cart_items=cart_items, total_price=total_price)

# -------------------- My Orders --------------------
@app.route('/my_orders/<int:table_id>')
def my_orders(table_id):
    table = Table.query.get_or_404(table_id)
    orders = Order.query.filter_by(table_id=table.id).filter(Order.status != 'completed').order_by(Order.created_at.desc()).all()
    return render_template('my_orders.html', table=table, orders=orders)

# -------------------- Bill Generation --------------------
@app.route('/admin/bill/view/<int:order_id>')
@login_required
def view_bill(order_id):
    order = Order.query.get_or_404(order_id)
    total_price = sum(item.price for item in order.order_items)
    return render_template('bill.html', order=order, order_items=order.order_items, total_price=total_price)


@app.route('/admin/bill/download/<int:order_id>')
@login_required
def download_bill(order_id):
    order = Order.query.get_or_404(order_id)
    order_items = OrderItem.query.filter_by(order_id=order.id).all()
    total_price = sum(item.price for item in order_items)

    # 🔹 Ab hum wahi bill.html ko render karenge jo view karta hai
    rendered_html = render_template(
        "bill.html",
        order=order,
        order_items=order_items,
        total_price=total_price
    )

    # 🔹 HTML ko PDF me convert karo
    pdf = pdfkit.from_string(
        rendered_html,
        False,
        options={"enable-local-file-access": ""},
        configuration=config
    )

    if pdf:
        # Status complete kar do
        order.status = "completed"
        db.session.commit()

        try:
            socketio.emit('order_completed', {
                'order_id': order.id,
                'table_id': order.table_id
            }, broadcast=True)
        except Exception:
            pass

        # 🔹 PDF return karo as download
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=bill_{order.id}.pdf'
        return response

    flash("Could not generate PDF.", "danger")
    return redirect(url_for('view_bill', order_id=order.id))



# -------------------- SocketIO --------------------
@socketio.on('update_order_status')
def handle_update_order_status(data):
    order = Order.query.get(data.get('order_id'))
    if order:
        order.status = data.get('status', order.status)
        db.session.commit()
        socketio.emit('order_status_updated', {'order_id': order.id, 'status': order.status}, broadcast=True)

# -------------------- Run App --------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.first():
            db.session.add(User(username='owner', password='owner'))
            db.session.commit()
        for t in Table.query.all():
            qr_file = os.path.join(app.config['QRCODE_FOLDER'], f"table_{t.id}.png")
            if not os.path.exists(qr_file):
                generate_table_qr(t.id)

    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
