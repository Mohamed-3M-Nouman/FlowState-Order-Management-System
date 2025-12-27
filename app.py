from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import random
import json
import os

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

database_url = os.environ.get('DATABASE_URL')

if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///restaurant.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ============================================================================
# DATABASE MODELS
# ============================================================================

class User(db.Model):
    """User model for customers, admins, and drivers"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='customer')  # 'customer', 'admin', 'driver'
    addresses = db.Column(db.Text, default='[]')  # JSON string of addresses list
    loyalty_points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    orders = db.relationship('Order', backref='customer', lazy=True)
    
    def set_password(self, password):
        """Create hashed password"""
        self.password = generate_password_hash(password)
        
    def check_password(self, password):
        """Check hashed password"""
        return check_password_hash(self.password, password)
    
    def get_addresses_list(self):
        """Get addresses as a Python list"""
        try:
            return json.loads(self.addresses) if self.addresses else []
        except:
            return []
    
    def set_addresses_list(self, addresses_list):
        """Set addresses from a Python list"""
        self.addresses = json.dumps(addresses_list)
    
    def to_dict(self):
        """Convert user to dictionary for session storage"""
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'role': self.role,
            'phone': self.phone
        }


class MenuItem(db.Model):
    """Menu item model"""
    __tablename__ = 'menu_items'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    image_url = db.Column(db.String(500))
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert menu item to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'category': self.category,
            'image_url': self.image_url,
            'is_available': self.is_available
        }


class Order(db.Model):
    """Order model"""
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    delivery_fee = db.Column(db.Float, default=0)
    status = db.Column(db.String(50), nullable=False, default='New')  # 'New', 'Preparing', 'Ready', 'Out for Delivery', 'Delivered'
    order_type = db.Column(db.String(20), nullable=False)  # 'Delivery', 'Takeaway', 'Dine-in'
    delivery_address = db.Column(db.String(500))
    pickup_code = db.Column(db.String(10))  # For Takeaway orders
    estimated_pickup_time = db.Column(db.String(50))  # For Takeaway and Dine-in
    reservation_time = db.Column(db.String(100))  # For Dine-in orders
    guest_count = db.Column(db.Integer)  # For Dine-in orders
    items_summary = db.Column(db.Text, nullable=False)  # JSON string of order items
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def get_items_list(self):
        """Get order items as a Python list"""
        try:
            return json.loads(self.items_summary) if self.items_summary else []
        except:
            return []
    
    def set_items_list(self, items_list):
        """Set order items from a Python list"""
        self.items_summary = json.dumps(items_list)
    
    def to_dict(self):
        """Convert order to dictionary"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'customer_name': self.customer.name if self.customer else 'Unknown',
            'total': self.total_price,
            'subtotal': self.subtotal,
            'delivery_fee': self.delivery_fee,
            'status': self.status,
            'order_type': self.order_type,
            'address': self.delivery_address,
            'pickup_code': self.pickup_code,
            'estimated_pickup_time': self.estimated_pickup_time,
            'reservation_time': self.reservation_time,
            'guests': self.guest_count,
            'items': self.get_items_list(),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }


class SystemConfig(db.Model):
    """System configuration model"""
    __tablename__ = 'system_config'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String(500), nullable=False)
    
    @staticmethod
    def get_value(key, default=None):
        """Get config value by key"""
        config = SystemConfig.query.filter_by(key=key).first()
        return config.value if config else default
    
    @staticmethod
    def set_value(key, value):
        """Set config value by key"""
        config = SystemConfig.query.filter_by(key=key).first()
        if config:
            config.value = str(value)
        else:
            config = SystemConfig(key=key, value=str(value))
            db.session.add(config)
        db.session.commit()
    
    @staticmethod
    def get_delivery_fee():
        """Get delivery fee as float"""
        fee = SystemConfig.get_value('delivery_fee', '20.0')
        try:
            return float(fee)
        except:
            return 20.0
    
    @staticmethod
    def is_delivery_active():
        """Check if delivery is active"""
        active = SystemConfig.get_value('is_delivery_active', 'True')
        return active.lower() == 'true'


# ============================================================================
# HELPER FUNCTIONS & DECORATORS
# ============================================================================

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('login'))
        if session['user']['role'] != 'admin':
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('menu'))
        return f(*args, **kwargs)
    return decorated_function

def driver_required(f):
    """Decorator to require driver role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('login'))
        if session['user']['role'] != 'driver':
            flash('Access denied. Driver privileges required.', 'danger')
            return redirect(url_for('menu'))
        return f(*args, **kwargs)
    return decorated_function

def get_config_dict():
    """Get system config as dictionary for templates"""
    return {
        'delivery_fee': SystemConfig.get_delivery_fee(),
        'is_delivery_active': SystemConfig.is_delivery_active()
    }

# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Query user from database
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            # Store user info in session
            session['user'] = user.to_dict()
            flash(f'Welcome back, {user.name}!', 'success')
            
            # Redirect based on role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'driver':
                return redirect(url_for('driver_dashboard'))
            else:
                return redirect(url_for('menu'))
        else:
            flash('Invalid email or password.', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        phone = request.form.get('phone', '').strip()
        
        # Validate phone number is provided
        if not phone:
            flash('Phone number is required.', 'danger')
            return render_template('register.html')
        
        # Check if email already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered.', 'danger')
            return render_template('register.html')
        
        # Create new user
        new_user = User(
            email=email,
            name=name,
            phone=phone,
            role='customer',
            addresses='[]'
        )
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Account created! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot password - simulated email verification"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        # Check if email exists in database
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Simulate email verification success
            flash('Email verified! Please enter your new password.', 'success')
            return redirect(url_for('reset_password', email=email))
        else:
            flash('Email not found. Please check and try again.', 'danger')
    
    return render_template('forgot_password.html')

@app.route('/reset_password/<email>', methods=['GET', 'POST'])
def reset_password(email):
    """Reset password for verified email"""
    if request.method == 'POST':
        new_password = request.form.get('new_password', '').strip()
        
        # Validate password
        if not new_password and len(new_password) < 3:
            flash('Password must be at least 3 characters long.', 'danger')
            return render_template('reset_password.html', email=email)
        
        # Find user and update password
        user = User.query.filter_by(email=email).first()
        
        if user:
            user.set_password(new_password)
            db.session.commit()
            flash('Password updated successfully! Please login with your new password.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Invalid reset link. Please try again.', 'danger')
            return redirect(url_for('forgot_password'))
    
    return render_template('reset_password.html', email=email)


# ============================================================================
# CUSTOMER ROUTES
# ============================================================================

@app.route('/')
@login_required
def menu():
    """Homepage displaying the menu"""
    # Query available menu items from database
    available_items = MenuItem.query.filter_by(is_available=True).all()
    
    # Group menu items by category
    menu_by_category = {}
    categories_order = ['Sandwiches', 'Meals', 'Drinks', 'Desserts']
    
    for item in available_items:
        category = item.category
        if category not in menu_by_category:
            menu_by_category[category] = []
        menu_by_category[category].append(item.to_dict())
    
    # Sort categories in preferred order
    sorted_categories = []
    for cat in categories_order:
        if cat in menu_by_category:
            sorted_categories.append(cat)
    
    # Add any other categories not in the predefined order
    for cat in menu_by_category.keys():
        if cat not in sorted_categories:
            sorted_categories.append(cat)
    
    # Get cart item counts for display on menu
    cart_item_counts = {}
    if 'cart' in session and session['cart']:
        for item_id in session['cart']:
            cart_item_counts[item_id] = cart_item_counts.get(item_id, 0) + 1
    
    # Convert to dict format for template
    menu_items_list = [item.to_dict() for item in available_items]
    
    return render_template('menu.html', 
                         menu_by_category=menu_by_category,
                         categories=sorted_categories,
                         menu_items=menu_items_list,
                         cart_item_counts=cart_item_counts)

@app.route('/add_to_cart/<int:item_id>')
@login_required
def add_to_cart(item_id):
    """Add item to session cart"""
    item = MenuItem.query.get(item_id)
    
    if not item:
        flash('Item not found.', 'danger')
        return redirect(url_for('menu'))
    
    # Initialize cart if it doesn't exist
    if 'cart' not in session:
        session['cart'] = []
    
    # Add item to cart (store item ID)
    cart = session['cart']
    cart.append(item_id)
    session['cart'] = cart  # Update session
    
    flash(f'{item.name} added to cart!', 'success')
    return redirect(url_for('menu'))

@app.route('/cart/increase/<int:item_id>')
@login_required
def increase_cart_quantity(item_id):
    """Increase item quantity in cart by 1"""
    item = MenuItem.query.get(item_id)
    
    if not item:
        flash('Item not found.', 'danger')
        return redirect(request.referrer or url_for('menu'))
    
    # Initialize cart if it doesn't exist
    if 'cart' not in session:
        session['cart'] = []
    
    # Add one more of this item
    cart = session['cart']
    cart.append(item_id)
    session['cart'] = cart
    
    return redirect(request.referrer or url_for('menu'))

@app.route('/cart/decrease/<int:item_id>')
@login_required
def decrease_cart_quantity(item_id):
    """Decrease item quantity in cart by 1, remove if quantity becomes 0"""
    if 'cart' not in session or not session['cart']:
        flash('Your cart is empty.', 'warning')
        return redirect(request.referrer or url_for('menu'))
    
    cart = session['cart']
    
    # Remove one instance of this item
    if item_id in cart:
        cart.remove(item_id)
        session['cart'] = cart
        
        # Check if item is completely removed
        if item_id not in cart:
            item = MenuItem.query.get(item_id)
            if item:
                flash(f'{item.name} removed from cart.', 'info')
    else:
        flash('Item not found in cart.', 'warning')
    
    return redirect(request.referrer or url_for('menu'))


@app.route('/cart')
@login_required
def cart():
    """Display cart contents"""
    cart_items = []
    total = 0
    
    if 'cart' in session and session['cart']:
        # Get full item details for each item in cart
        item_counts = {}
        for item_id in session['cart']:
            item_counts[item_id] = item_counts.get(item_id, 0) + 1
        
        for item_id, quantity in item_counts.items():
            item = MenuItem.query.get(item_id)
            if item:
                cart_items.append({
                    'item': item.to_dict(),
                    'quantity': quantity,
                    'subtotal': item.price * quantity
                })
                total += item.price * quantity
    
    # Get user's saved addresses from database
    user = User.query.get(session['user']['id'])
    user_addresses = user.get_addresses_list() if user else []
    
    return render_template('cart.html', cart_items=cart_items, total=total, config=get_config_dict(), 
                           now=datetime.now().strftime('%Y-%m-%dT%H:%M'), user_addresses=user_addresses)

@app.route('/place_order', methods=['POST'])
@login_required
def place_order():
    """Save cart to database and clear cart"""
    if 'cart' not in session or not session['cart']:
        flash('Your cart is empty.', 'warning')
        return redirect(url_for('menu'))
    
    # Build order items list
    item_counts = {}
    for item_id in session['cart']:
        item_counts[item_id] = item_counts.get(item_id, 0) + 1
    
    order_items = []
    subtotal = 0
    for item_id, quantity in item_counts.items():
        item = MenuItem.query.get(item_id)
        if item:
            order_items.append({
                'name': item.name,
                'quantity': quantity,
                'price': item.price
            })
            subtotal += item.price * quantity
    
    # Get order type from form
    order_type = request.form.get('order_type', 'Delivery')
    
    # Get delivery address
    address = request.form.get('address', '').strip()
    
    # Validate address for delivery orders
    if order_type == 'Delivery' and not address:
        flash('Address is required for delivery orders.', 'danger')
        return redirect(url_for('cart'))
    
    # Calculate delivery fee and total
    delivery_fee = 0
    if order_type == 'Delivery':
        if SystemConfig.is_delivery_active():
            delivery_fee = SystemConfig.get_delivery_fee()
            total = subtotal + delivery_fee
        else:
            flash('Delivery service is currently unavailable. Please choose Takeaway or Dine-in.', 'warning')
            return redirect(url_for('cart'))
    else:
        total = subtotal
    
    # Generate pickup code for Takeaway orders
    pickup_code = None
    estimated_pickup_time = None
    
    if order_type == 'Takeaway':
        pickup_code = f"#{random.randint(100, 999)}"
        
        # Calculate estimated pickup time
        total_items = sum(item['quantity'] for item in order_items)
        base_time = 20
        extra_time = 2 * total_items
        total_minutes = base_time + extra_time
        
        estimated_time = datetime.now() + timedelta(minutes=total_minutes)
        estimated_pickup_time = estimated_time.strftime('%I:%M %p')
    
    # Handle Dine-in reservations
    reservation_time = None
    guests = None
    
    if order_type == 'Dine-in':
        reservation_time = request.form.get('reservation_time', '').strip()
        guests_str = request.form.get('guests', '').strip()
        
        if not reservation_time:
            flash('Reservation date and time are required for dine-in orders.', 'danger')
            return redirect(url_for('cart'))
        
        if not guests_str:
            flash('Number of guests is required for dine-in orders.', 'danger')
            return redirect(url_for('cart'))
        
        try:
            guests = int(guests_str)
            if guests < 1 or guests > 20:
                flash('Number of guests must be between 1 and 20.', 'danger')
                return redirect(url_for('cart'))
        except ValueError:
            flash('Invalid number of guests.', 'danger')
            return redirect(url_for('cart'))
        
        try:
            reservation_dt = datetime.strptime(reservation_time, '%Y-%m-%dT%H:%M')
            estimated_pickup_time = reservation_dt.strftime('%I:%M %p on %B %d, %Y')
        except ValueError:
            flash('Invalid reservation time format.', 'danger')
            return redirect(url_for('cart'))
    
    # Create order in database
    new_order = Order(
        user_id=session['user']['id'],
        total_price=total,
        subtotal=subtotal,
        delivery_fee=delivery_fee,
        status='New',
        order_type=order_type,
        delivery_address=address if address else None,
        pickup_code=pickup_code,
        estimated_pickup_time=estimated_pickup_time,
        reservation_time=reservation_time,
        guest_count=guests
    )
    new_order.set_items_list(order_items)
    
    db.session.add(new_order)
    db.session.commit()
    
    # Clear cart
    session['cart'] = []
    
    flash(f'Order #{new_order.id} placed successfully!', 'success')
    return redirect(url_for('my_orders'))

@app.route('/my_orders')
@login_required
def my_orders():
    """Show orders for logged-in customer"""
    user_orders = Order.query.filter_by(user_id=session['user']['id']).order_by(Order.created_at.desc()).all()
    orders_list = [order.to_dict() for order in user_orders]
    return render_template('my_orders.html', orders=orders_list)

@app.route('/profile')
@login_required
def profile():
    """Display user profile with saved addresses"""
    user = User.query.get(session['user']['id'])
    
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('menu'))
    
    # Convert user to dict and add addresses
    user_data = user.to_dict()
    user_data['addresses'] = user.get_addresses_list()
    
    return render_template('profile.html', user=user_data)

@app.route('/profile/add_address', methods=['POST'])
@login_required
def add_address():
    """Add a new address to user's address book"""
    address = request.form.get('address', '').strip()
    
    if not address:
        flash('Address cannot be empty.', 'danger')
        return redirect(url_for('profile'))
    
    # Fetch user from database using modern SQLAlchemy 2.0 syntax
    user = db.session.get(User, session['user']['id'])
    
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('menu'))
    
    # Get current addresses and add new one
    addresses = user.get_addresses_list()
    addresses.append(address)
    
    # Update user's addresses in database
    user.set_addresses_list(addresses)
    db.session.commit()
    
    flash('Address saved successfully!', 'success')
    
    return redirect(url_for('profile'))

@app.route('/profile/delete_address/<int:index>')
@login_required
def delete_address(index):
    """Delete an address from user's address book"""
    # Fetch user from database using modern SQLAlchemy 2.0 syntax
    user = db.session.get(User, session['user']['id'])
    
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('menu'))
    
    # Get addresses as Python list
    addresses = user.get_addresses_list()
    
    # Validate index
    if 0 <= index < len(addresses):
        deleted_address = addresses.pop(index)
        
        # Update user's addresses in database
        user.set_addresses_list(addresses)
        db.session.commit()
        
        flash(f'Address "{deleted_address}" deleted successfully!', 'success')
    else:
        flash('Address not found.', 'danger')
    
    return redirect(url_for('profile'))


# ============================================================================
# ADMIN ROUTES
# ============================================================================

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """Admin dashboard showing all orders"""
    all_orders = Order.query.order_by(Order.created_at.desc()).all()
    orders_list = [order.to_dict() for order in all_orders]
    return render_template('dashboard.html', orders=orders_list, config=get_config_dict())

@app.route('/admin/update_status/<int:order_id>/<new_status>')
@admin_required
def update_order_status(order_id, new_status):
    """Update order status"""
    order = Order.query.get(order_id)
    
    if not order:
        flash('Order not found.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    # Validate status
    valid_statuses = ['New', 'Preparing', 'Ready', 'Delivered']
    if new_status not in valid_statuses:
        flash('Invalid status.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    # Update status
    order.status = new_status
    db.session.commit()
    flash(f'Order #{order_id} status updated to {new_status}.', 'success')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update_settings', methods=['POST'])
@admin_required
def update_settings():
    """Update system settings"""
    delivery_fee = request.form.get('delivery_fee', '').strip()
    
    # Validate delivery fee
    try:
        delivery_fee = float(delivery_fee)
        if delivery_fee < 0:
            raise ValueError
    except ValueError:
        flash('Delivery fee must be a valid positive number.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    # Update system config
    SystemConfig.set_value('delivery_fee', delivery_fee)
    flash(f'Delivery fee updated to {delivery_fee} LE successfully!', 'success')
    
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/menu')
@admin_required
def admin_menu():
    """Admin menu management page"""
    all_items = MenuItem.query.all()
    menu_items_list = [item.to_dict() for item in all_items]
    return render_template('admin_menu.html', menu_items=menu_items_list, config=get_config_dict())

@app.route('/admin/add_item', methods=['POST'])
@admin_required
def add_menu_item():
    """Add new menu item"""
    # Get form data
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    price = request.form.get('price', '').strip()
    category = request.form.get('category', '').strip()
    image_url = request.form.get('image_url', '').strip()
    
    # Validate required fields
    if not name or not price or not category:
        flash('Name, price, and category are required.', 'danger')
        return redirect(url_for('admin_menu'))
    
    # Validate price
    try:
        price = float(price)
        if price <= 0:
            raise ValueError
    except ValueError:
        flash('Price must be a positive number.', 'danger')
        return redirect(url_for('admin_menu'))
    
    # Create new menu item
    new_item = MenuItem(
        name=name,
        description=description if description else 'No description provided',
        price=price,
        category=category,
        image_url=image_url if image_url else 'https://via.placeholder.com/400x300?text=No+Image',
        is_available=True
    )
    
    db.session.add(new_item)
    db.session.commit()
    
    flash(f'Menu item "{name}" added successfully!', 'success')
    return redirect(url_for('admin_menu'))

@app.route('/admin/delete_item/<int:item_id>')
@admin_required
def delete_menu_item(item_id):
    """Delete menu item"""
    item = MenuItem.query.get(item_id)
    
    if item:
        item_name = item.name
        db.session.delete(item)
        db.session.commit()
        flash(f'Menu item "{item_name}" deleted successfully!', 'success')
    else:
        flash('Menu item not found.', 'danger')
    
    return redirect(url_for('admin_menu'))

@app.route('/admin/edit_item/<int:item_id>', methods=['GET', 'POST'])
@admin_required
def edit_menu_item(item_id):
    """Edit existing menu item"""
    item = MenuItem.query.get(item_id)
    
    if not item:
        flash('Menu item not found.', 'danger')
        return redirect(url_for('admin_menu'))
    
    if request.method == 'POST':
        # Get form data
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        price = request.form.get('price', '').strip()
        category = request.form.get('category', '').strip()
        image_url = request.form.get('image_url', '').strip()
        is_available = request.form.get('is_available') == 'on'
        
        # Validate required fields
        if not name or not price or not category:
            flash('Name, price, and category are required.', 'danger')
            return render_template('edit_menu.html', item=item.to_dict())
        
        # Validate price
        try:
            price = float(price)
            if price <= 0:
                raise ValueError
        except ValueError:
            flash('Price must be a positive number.', 'danger')
            return render_template('edit_menu.html', item=item.to_dict())
        
        # Update item
        item.name = name
        item.description = description if description else 'No description provided'
        item.price = price
        item.category = category
        item.image_url = image_url if image_url else 'https://via.placeholder.com/400x300?text=No+Image'
        item.is_available = is_available
        
        db.session.commit()
        
        flash(f'Menu item "{name}" updated successfully!', 'success')
        return redirect(url_for('admin_menu'))
    
    # GET request - render edit form
    return render_template('edit_menu.html', item=item.to_dict())

@app.route('/admin/update_delivery_price', methods=['POST'])
@admin_required
def update_delivery_price():
    """Update delivery fee price"""
    delivery_fee = request.form.get('delivery_fee', '').strip()
    
    # Validate delivery fee
    try:
        delivery_fee = float(delivery_fee)
        if delivery_fee < 0:
            raise ValueError
    except ValueError:
        flash('Delivery fee must be a valid positive number.', 'danger')
        return redirect(url_for('admin_menu'))
    
    # Update system config
    SystemConfig.set_value('delivery_fee', delivery_fee)
    flash(f'Delivery fee updated to {delivery_fee} LE successfully!', 'success')
    
    return redirect(url_for('admin_menu'))

@app.route('/admin/toggle_delivery')
@admin_required
def toggle_delivery():
    """Toggle delivery service availability"""
    # Get current status and flip it
    current_status = SystemConfig.is_delivery_active()
    new_status = not current_status
    
    SystemConfig.set_value('is_delivery_active', str(new_status))
    
    status = "activated" if new_status else "deactivated"
    flash(f'Delivery service {status} successfully!', 'success')
    
    return redirect(url_for('admin_menu'))

# ============================================================================
# DRIVER ROUTES
# ============================================================================

@app.route('/driver/dashboard')
@driver_required
def driver_dashboard():
    """Driver dashboard showing orders ready for pickup and delivery"""
    # Filter orders with status 'Ready' or 'Out for Delivery' AND order_type 'Delivery'
    driver_orders = Order.query.filter(
        Order.status.in_(['Ready', 'Out for Delivery']),
        Order.order_type == 'Delivery'
    ).order_by(Order.created_at.desc()).all()
    
    orders_list = [order.to_dict() for order in driver_orders]
    return render_template('driver_dashboard.html', orders=orders_list)

@app.route('/driver/update_status/<int:order_id>/<new_status>')
@driver_required
def driver_update_status(order_id, new_status):
    """Update order status from driver dashboard"""
    order = Order.query.get(order_id)
    
    if not order:
        flash('Order not found.', 'danger')
        return redirect(url_for('driver_dashboard'))
    
    # Validate status (drivers can only update to these statuses)
    valid_statuses = ['Out for Delivery', 'Delivered']
    if new_status not in valid_statuses:
        flash('Invalid status.', 'danger')
        return redirect(url_for('driver_dashboard'))
    
    # Update status
    order.status = new_status
    db.session.commit()
    flash(f'Order #{order_id} status updated to {new_status}.', 'success')
    
    return redirect(url_for('driver_dashboard'))

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def init_db():
    """Initialize database with tables and seed data"""
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Check if any admin exists (role-based check)
        if not User.query.filter_by(role='admin').first():
            print("--- Seeding Unified Data ---")
            
            # 1. Admin User
            admin = User(
                email='admin@app.com',
                name='admin',
                phone='01000000000',
                role='admin',
                addresses='[]'
            )
            admin.set_password('123')
            db.session.add(admin)

            # 2. Customer User
            customer = User(
                email='user@app.com',
                name='user',
                phone='01222222222',
                role='customer'
            )
            customer.set_password('123')
            # Add sample addresses
            customer.set_addresses_list(['Home: 12 El-Tahrir St.', 'Work: Tech Company HQ'])
            db.session.add(customer)

            # 3. Delivery Driver
            driver = User(
                email='driver@app.com',
                name='driver',
                phone='01111111111',
                role='driver',
                addresses='[]'
            )
            driver.set_password('123')
            db.session.add(driver)
            
            # Add Menu Items only if table is empty
            if not MenuItem.query.first():
                menu_items = [
                    # --- Sandwiches ---
                    MenuItem(
                        name='Alexandrian Liver Sandwich (Kebda)',
                        description='Spicy beef liver with garlic, peppers, and tahini in fresh Fino bread.',
                        price=45.0,
                        category='Sandwiches',
                        image_url='https://images.unsplash.com/photo-1626806509420-22d7653606b2?auto=format&fit=crop&w=800&q=80',
                        is_available=True
                    ),
                    MenuItem(
                        name='Hawawshi (Baladi Bread)',
                        description='Crispy Baladi bread stuffed with spiced minced meat and herbs.',
                        price=75.0,
                        category='Sandwiches',
                        image_url='https://images.unsplash.com/photo-1606756269527-b089c8a9f3d9?auto=format&fit=crop&w=800&q=80',
                        is_available=True
                    ),
                    MenuItem(
                        name='Falafel Special Sandwich',
                        description='Crispy Falafel with salad, pickles, and tahini in Shami bread.',
                        price=20.0,
                        category='Sandwiches',
                        image_url='https://images.unsplash.com/photo-1593001874117-c99c800e3eb7?auto=format&fit=crop&w=800&q=80',
                        is_available=True
                    ),
                    
                    # --- Meals ---
                    MenuItem(
                        name='Koshary Bowl (Large)',
                        description="Egypt's national dish: Rice, pasta, lentils, topped with tomato sauce and crispy onions.",
                        price=50.0,
                        category='Meals',
                        image_url='https://images.unsplash.com/photo-1544473244-f6895e679c6d?auto=format&fit=crop&w=800&q=80',
                        is_available=True
                    ),
                    MenuItem(
                        name='Mix Grill (Kofta & Kebab)',
                        description='Charcoal grilled Kofta and Kebab served with rice and salad.',
                        price=220.0,
                        category='Meals',
                        image_url='https://images.unsplash.com/photo-1555939594-58d7cb561ad1?auto=format&fit=crop&w=800&q=80',
                        is_available=True
                    ),
                    MenuItem(
                        name='Fattah with Meat',
                        description='Layered rice and toasted bread with garlic-vinegar tomato sauce and beef chunks.',
                        price=180.0,
                        category='Meals',
                        image_url='https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?auto=format&fit=crop&w=800&q=80',
                        is_available=True
                    ),
                    
                    # --- Desserts ---
                    MenuItem(
                        name='Om Ali (With Nuts)',
                        description='Traditional Egyptian bread pudding with hot milk, cream, and nuts.',
                        price=65.0,
                        category='Desserts',
                        image_url='https://images.unsplash.com/photo-1582235925396-857e4e89f783?auto=format&fit=crop&w=800&q=80',
                        is_available=True
                    ),
                    MenuItem(
                        name='Rice Pudding (Roz Bel Laban)',
                        description='Creamy rice pudding topped with cinnamon and raisins.',
                        price=35.0,
                        category='Desserts',
                        image_url='https://images.unsplash.com/photo-1595855726207-63556f82736b?auto=format&fit=crop&w=800&q=80',
                        is_available=True
                    )
                ]
                db.session.add_all(menu_items)
            
            # Seed Config (Check existence first)
            if not SystemConfig.query.filter_by(key='delivery_fee').first():
                db.session.add(SystemConfig(key='delivery_fee', value='20.0'))
            
            if not SystemConfig.query.filter_by(key='is_delivery_active').first():
                db.session.add(SystemConfig(key='is_delivery_active', value='True'))
            
            # Commit all changes
            db.session.commit()
            
            print("--- Data Seeded Successfully: All passwords are '123' ---")
        else:
            print("Database already initialized.")

# ============================================================================
# RUN APPLICATION 
# ============================================================================

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)