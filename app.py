from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import random
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-in-production'

# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restaurant.db'
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
            admin.set_password('admin')
            db.session.add(admin)

            # 2. Customer User
            customer = User(
                email='customer@app.com',
                name='customer test',
                phone='01222222222',
                role='customer'
            )
            customer.set_password('customer')
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
            driver.set_password('driver')
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
                        image_url='data:image/jpeg;base64,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',
                        is_available=True
                    ),
                    MenuItem(
                        name='Hawawshi (Baladi Bread)',
                        description='Crispy Baladi bread stuffed with spiced minced meat and herbs.',
                        price=75.0,
                        category='Sandwiches',
                            image_url='data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxMTEhUTEhMWFhUXFxgaFxgYFxgXHhcXGBcXFxgXHRgYHSggGB0lGxUXITEhJSkrLi4uFx8zODMtNygtLisBCgoKDg0OGxAQGy8mICUtLS8tLS0zLS8tLy8tLS0tLS0wNS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAM0A9gMBIgACEQEDEQH/xAAcAAABBQEBAQAAAAAAAAAAAAAFAQIDBAYABwj/xAA+EAABAgQEAwUFBgUEAwEAAAABAhEAAwQhBRIxQVFhcQYTIoGRMqGxwdEUI0JS4fAVYnKC8QczotI0ksIW/8QAGgEAAgMBAQAAAAAAAAAAAAAAAQMAAgQFBv/EADERAAICAQMCAwcDBAMAAAAAAAABAhEDBCExEkETMlEUIkJhcZGhBYHRUsHh8CNDsf/aAAwDAQACEQMRAD8AwP21KlLBcvYQyXIO0MpsMyqcrtE/2pCFBKlHLu0YGk+DO/kVJ1OokAXJ2EX19l5ikuogHgIP4JToUO8At+HpxgyshtIyZNQ4OogTZ5zLwsyVPM8oSpnTCfAqNb2gloUgOLHfgYp09ClOhBh+PJ1rqYHIyVdJmBiUkv5x04nu0pOsaTFphSGA134CM/NnpSdMx9whvVfCLJlCXMWlYyvz6QTxOtUGILEJtu1o4T0ZdbnQNDJ9MQhSjwi3VbVoN2wdh9OVXzX+cEVyARfWKVNPZtoN0q0q113g5ZOySYD7sg2i3IWZanIflBGfQZfEGIiCdhjnMSWbbRor1qXILsX+I96bS28tosTkS1pKMpBax5wzvEBLJPKLFLSJH3pmZmLM+52hf02K2BO5YFKhFzD6BDB033iWrpSuY4Folp3QWykwzrbRay5T4YlN9uER4kpEtj3bvYAceMSCdMAdSd4HYhiZQQGueO0UipOQFbYQpsNsFcv28WJ2Jz8olGarux+F7fvlAnB8VUVZTcGL1Sl1ODEbkpbkd3uDk02aalCCylKYXZjHqfYXtBUJUuineJUsWU7kjrvHkmIHxvGs7EVAXWSggkFSDmJLuoAW16xohfJZHuFIPDE4gFgXaGVMWqQo5ZySxQbPzHEQfaNKdjORDDSIeRDFGCQaRDTDgl4kSiCQgyR0WWjolkPmiqpJuyT0gYqhmlWjHnHpsilMuYNFh/KFrsNJdZSlnezWjkY898I7mT9JguJV9TLUUifTIzKWlXBL6Q1OKz1nXKxLMPcYKy5QVqkh94bUyEoYJJL6AB4u4Re7W556dRk1dglSJpBBmOCXIgjQyWAKyw0AGqolTTlJGcAPtqfOHU8wFd9eHCF5H0rYpdgztNIKgAjROo6xkZiC7CNtjwyrSoaFLGAkyhCbi4Nx5xbFOolk6RnlJI1sRHLnTCMpUWMF59BmIdCj0STF6V2fmKYJlLL6eE/OH+NGrYxW+EZfNxhZdaU6aRsz2DqjogDkpQEPV2CWn2psgb+07conj4u7HLDkl8LMxh+MHMy/ZPug/JnBrCxjh2MlhyapAI0CfFFs9mJ+V5akzQNw6T6GFyy435WCekypX0gbEKZPtItxH0ilKmZXLEngOMG14dNCSSlQCSyiQbHhA2bKKFZgHa7CLJ2Z6fcjNZMQEkh1H8O8FaOepTEpyjgYAU9Uc6pswgdbnoIbUYnMmlkeFPvi7xXsguFmqly1zS0tLt+9YnqOx86Ym6Qk8zEPZ3G0pQEAAFOvPmYNVPatMtnBJLbPaMU55YSqMTrYdDhcFJyM9K7CVKCCmaiDkns+Ej76cM38ogxR9t6YeGZvopvjwg1KXSz05kqSocLOITk1ObvEdHR4G99zLL7MyVkEnMAGifDsEEmdKmSyAJZ04uCNfOC9XhiU+w8MVSTALh23EUWsyR5Y/wBhwte6ivjmGd7UqqEKKDkGVtc4dv3yjddk62bNkAzwnOLHKdeo2MYkFfH1ET09ROlnMmx5FrfONOL9QfV725myfpyXl2PSCIZleMRQdsJuYiZLdveI02G9oJE22bIr8qrf5jpw1GOfcw5NNkhu0FQmOhUh93hSIeIIiqOhkxUdEJR55PppYBCVF9XJb0gJPzqcA29xi5VTAfaVYaCBVZXkjKiwjzeNSi7k9z3nsryxcZcPkqTKgpsXUduETUOcEKUb7Dg8LTSCspCLndg7frBrCsPT/uzDllp/Nu1nPJ9o6DmoRuTPDajT9WoljxRpX3LlBgBnAKJCXuSfpEVVgtHTKzzVrUVFizgW3ttFypxtCMjEErYoTsLamM7V1E2cvIVOpL2yl73sdGhVua3NePR44fP6haqxOgDFpdgwKik/GIZeNy/CpFOFoLgFO99uUDcK7PEFapn3qizlYsB0MF6XDUSnYhKixZL68uA5NCpQxLvZrgmuFRFTdqZKHJQCoH2Rq2wbeLiu2Ugj2FhewKCgP1PxDxFVU0uU8xVjuW0MDZNUgl1pMxIDDKhm8zF8cYdOyZJW3bOn4pPqSrMEplNohRKlcHVZhxaGUuDyLFSQ25Bs/MamCRUgpyykolkhsxAcDh4dTFOmyOpSVoUlO6vxcQDd+jQV1NbIv7l/2IxISkAplILkv5bxNRzZkq6UFOa1wSm25eJqHEKaYrxp7u+5A/exgpPwpMwAoWVp/CCdusRzXfYji1sCajElKSqVPl5nue7dlDV22MZ2t7B5wJ1LOLKvlma+vyjUYjL7qW5zJfXMSTw3e0R4XXqVN7uT4kpSM7i2Z7X4kGCm4bxEThCaqR5/XYGXyLSUqSbk/i6QgoUhLAR6PUUIqQp5SkqCiHs4bfmOUCkdh5sx2mJHAsQfSDHU9pbMwZtHOL9zdHm9dS90QpNr6weokJmyxe434fSDVV/pnPWHM4HgGt6QNR2UqafXxcCI0qcMqpS3Q3Ep4fPG0yCswidmdIEwAaCx9IqiVOQXSlaFaG1+kH6WtWiygQYMYbiCFKDt04mEynkh5o2jdCGHIrg6foA6HtLPQEpV4mvf2iNx1jT4f26kLZMxJSdDm+sDq3BJcxefKRd7HeI0dkkKF1KF7m0Z5rBLd7DVjzL0ZtaTEaecPCQ40donl0KHYFzyjHU3ZRLBPfr1sQwIHCCOC0c+UpSftBKUqIBWlyU+R0jNKOLmLLVPgOKoy/Fogm06dxFkVJ1Kkno4hJtUDqBFYyrgDhKxKKoXKuhZbhqD5RoqXExMHA7j6Rl8qdtYcARoY2YNW8b+Rmzabq+prkJeOgDTYxMQGICo6OktZia5ML02RPg81mKJhtNIzKAdnID8IvDDZyx4JKzzyn5wf7P9kFllVCu6GuVxmLfCMWLTtntdZ+o4scH72/oi+aGTISlAVlD2/mPEw2rowtGVYUUkmwBvffeCmMpRLCfGkoBAZeo6Ea9IzfaLtYZTolsFNZRIYcwPT0hEodMunv8Ac83GbyLqBFf2fkUszvVqUhBDhGZ2OxD3ERTu0yC/2WRmUQHWoG3Mt8IzEytNRMeatSjxJfTXraNH2cUCLCxIQwc3L+7jGjw73myvUo8BSTKqJ2VS5hQnXLLGUm25IMNkkoUQVKUpRcKVqw4swIiVeLop5RTMZw7Ab3LW2hlHSKmZFTimUV6ABiUm4F7k35QEqfCoHVfLK+Izu+WAwOVyQDZ/Lzbg8Q0dUtKiEKOUHhqSA4+T8oP1WBICSZZaZxAKgfg0UKWjnBChkJU7pK7Achu3lBU0lSD5mDauaFIACWcta12uLa6++LQ7NTJMnvWGU7cGs/XX0i/IwSbleYpIJGjZgl76hn68hBGTOm/Z1U61oLpICy5YWHs8We/SK+NBXGTC1NTUoLazIqpZakTEzNQoEKPtXGzXa20NpAuW4p1zCAP5mT1BfWL1NKpZUxRXN7xYFkswvs5sdoiou065RaWlCEObBIIL7nizQuWaDVVZoeCcpOXH1CicRrVMg0neobxOhmZruqxB5X5RqqXDwEBpUuUdSEh9dXAZj6xhKjtLNUQrN7JBA0HoItL7bz/5G6H6xRZL+FlJ6driSN8ilAGl9mcW9Yr1a0S1Jc2NlEeoP74xg5naiom2zAX1AgrhGGz6pyZigkD2vPQA284bGEsjUYxEzjHFFznI1UmulaB1bMBqeMOOEZkkalRJ6cobQ9mUoYla1dS3uEaOUkBgNhHQw6fo3lyc3Ln6to8GTPYtKwQsjyF4gR/pnTFyVLB5Fo2iFPEg0vGmkuwm297ZiZv+nyEf7VROT1UFfEQ1XZCcn2ah/wCpAPwaNu8NW28UlihLlIYss48SZ5+MBrNPuiz38SfrFWfh1Yh/uElt0qf3Fo9Jb0hhVdmhfsmJ9i3tWVfEeRzquYCy0FB5gj4xVXXhNytvOPXqyilzAUTEBQPEPGPxLsLLcqkeaTf0MKloo/Caceva2kYpPaRJLMu2hym8GqfFkEDxfKL6ezCh+B+YvBGh7Np3DQp6OL7DvbX6gtNUFDwl46NvR4XLQGCRHQxaGIn21+hLWBQlq7sDM3hHEwBw6qDEliQb6uGsXfeNGpUZntDhuclcuy2uBbN+sX1WGU6lF7rsL0+SKuMu/cq1FHTTioLTfjmLjoXtFab2Ow9aGUl7vm705tGZ305RmqxKgohWZJ5uPjFOYSNHjBGOReh0HGD4bNRO7HYeEhJUQE/zs78TvDqakpZCconBKRsFZn5nnzECMP7OTZjGYe7Sb8VHbTbUawfo8MppNwnMoPdTlXroBroIVkc33/8Af5DFY4+v4KWD0NItRVLHeFyyiCS3n0tBidTBwcjqT7KlDR7Fjs4iKqxtEtI8KQ2loEz+3D+ESlqHEDL6KH1gxUmqsElvaQWkUtQ/iWgAuQkC/vI+EWTh+hUsl+gb4xl6vtNNnE9whaS5GZaQAG87wEnUtUlZmTpyylT5kIWU2VchKSbnm7wY4PUkpPk2OJYxRylBKpoMzZCSVKLt+FOvpAOq7QzVzMkiUhKEglSlAu9/CyspA0uRAaoWjIPs6QpRJB2W7OVa6sRE9NIKZYMy4LZgFOQkDc3L3IYRdYordoW570i5Rdp1r8EynQ93ID89wkfpDxjVO4TNpE31KcqgPS/u84Z3iSe8QsBJsALPsNdWY8IgMoDMqbqWbQFg4AYczvB8LG96GJySqwtLo8PnpOVKkqtdBbK/G7eogHX9mlpSVyVpmp9FD+3fy9InpqhLAZfFcDYa7kMPWDNLSy6eWE52AJLnmSbDqbAQjLLwkmvsMhHqbTYG7M4SqYUghQdTEm19xePX8Op0y0CWkWAtbXrGMw6cCQpNwNCQQ3qAYLyahayHKynrb0eNWDXRjGundmLUaac531bI1CWEMXUDhGf+yJHifnr89ovU0xSkAqDEvbzt7mMa8epc3TVfkyzwKKtO/wAF01B6QnenjEBG0c8X6mLom78jeFM0mIDHExOphpE6ZxiRM94rNHNEU2gdKLM1Taf5hFKa/K8Ry5h0hZlxrDoyTQppoRSgPFsdfrDwoGIFG1ul+G8Nluw/ekM5Vgi6dF0R0QhcdFS5HOXaKM2aAM0T1nugVikz8I0gSkoq2FJt0gViI766gG0c7fOIZRpqVLjxzPzKYEcg9hElTSJcBShfUaW+MYzHlSFzlSpaCcvtEF77sNOXWOVlyPLLbg6eHGoRpl3H8aqM6SlITYs5JcG10p3txitL7R1BSoKQlVvaDgp2uOET0+EKdl1BWrKAAfwixBy6aWdt46bhSM6ZeZmZaijwPlOiiL6l9btFY4versBud3YykpUqymYUrJzO5IA/pD398XquUgA7uwBct/KWNnMSUsyWF5jlSbpCjYkB7XtaJ5UqSgKGXK90hxwcFtAPEr3wx8De5To8MUvMVHI4ZklyRzSxSfMRDWIlhHdqmKmKbKygcxYuXWbecXKSYq6lWSSwdkqPT9YpVlRlUkZ0EgEgksLkOnM1yGPqfKb0Vku1/wAFGmoZmZwoXHsOwIZtdrDXW0Ek1AUyALcXBBTooXu+xf1iaTkAKUpU5uSTu+gf4Q2Zhr5iUnMtnT7SQQSBrb0EUcq8xMMGo0Up0ggqUCx4m4SQG3PDjwiOSCoAAhyWHhGhN7cHDxfqu4lD7+ZlIYhBULnRmFzyhP4qZheTTKJ2UrwC3lmPkIQ9R/SjT4V8l3DsESEnOpydQNCNfKH1KpErxLUkK4lnbhd+kVRhVbODqm5EnaUlv+Srn0h0nsKg3WFKPFS1EnyFoRJzm/ef2RZdEOGQ1HbOSkASwVqO5ZIHnGywemmrRnmzEpcAhKA7D+tXyEZ2X2MkgN3aW536dYL01P3bI70obRIUSAB8BDsMsMH5G38zNmjOXEkg/Ip0Avc9ST+kSmYyuukB+/bSeTy8J+UR1WKZQMyvUXfoI1xzwS4r7GR4Jt82HQd4ekQMpMYQu7W4pv7oJomBQcEEQ6GWE/KxU8cococIRoQrhwHGGFDiI4JhTCRACRy1mOMRVR0AgxdMEuDlLu+g35xako8IfXX1vAtc06QQpJtmjW9lXczwfVLq7EuWOh4EdFRpRqmYvtGbnFZXmQQ+jHSNFiiglClHRrxlEpmKDoORzqobPwhGoniUamx+CM3K4/4Mv2sRVGYkr7kZVOkDxKbW/AWvo7wLwbD1kzJiyStZUSQHAcvolmdzZxG5qJMhypZSVFnU7vs7aaRSWqnB8K0gPsAH52H7eOY88I+U6UccmtwZOCs3hdBUXUsJ2FlFWo04vBCRLyoZITlckkAFypRUpTHiSb8zFaoqaYKBC3KdPa1+Y6xSRPp3KpZUjdYBKUHMXUW42GnHd4Hj3H/Bfwt9iljeNKzKRJmABLZR3YuH8QKjt0fhCUteqaUnwqVYMpJLJ0ccxeFTidIkkst1BiAHdy7X1vE1JhiluUoKApnKmc8PDoByhjzRoWsUlK7JpFT3pJmlImAME5gdNzsTY6RGU06QUKcqKgUgXObkBf3bwQl9npfm34XSG/t2tFKpWiWsokJSABdaX18muOLwrqlPysZ0xW0twmZ84jwS03/MrfiyRxioaWum2XMKU8JbD/kbxBKXMBChULC/wheUpY8UgOX6jrFSnVXgsagBTkgsVgjZPiSCN+UBaeT5dkeVLhGow/s+iUyikBXGxUf7j9YMy6Rh7QHBmjATKmrmr/8AJYoAsmWEgl7ghWtwz6cIL06JhT3k6ZdDgBDynJGhIU5GnS0CWmfdlFl6uApiWOU8k92uae81y6e9vQRVm9rJSE5lpmo8ObxPoehIHm0BK2rkSzaUFLcFgA/VSiLM3uEKtcyclS8qUpSzpK8xPEO1ybE23PWLRwQ+YW5VbLiu1qp3/i05VcOtS7eiVZjvy6wEGH1Spi5k6s9pQCkSlZWGmhcMDteNEZksIZKcyiAkmXlISCLAHRh5mKdSCGStlFT2LB2Lk2Fi/CGxSUWooU7b3YHqZM4DJIUVLmJUlSyHVlF38Oiho490EafCRlCjNmKmZPxqUUp8ABIOjE3Y/KJ8KkKM10sDLsgl/FmT4ncX4ekFKXCVgl1FQOo0RzDbmBKSgtyQUntJkfZqjmKzEmYEjKUAlieJI2HstvrGxwZXiILjN01Gun7tDaelKUjaM1iPaoSpuWnR3igSFFLkDikEPcaGJiSc1KqK5W3Brk9B7uEaMRI7XVJ1kN1UB8on/wD0878SEj+4n5Rvc8S+Nfn+DAoZn/1v8fya/KYatYAuYyA7QTFXIboR8zEkvG5X4yr0cf8AEtEjPA/j/wB/cjxaj+j/AH9rNMqrGibmKqySefwirQ4hLmMELSH20J9WgvLktGiEo/B9zPLHK/8Ak+3CKiZLRJTrYtE80RSK2UILLoMIVHRFJVaOiBshxCUFJKSHBBjzzFZU0nKJpABZidB6R6POVGJ7U4flVmTofnCsuKE/MrHYcsoP3WZefhixrMSfMn5RTm0h3UI0FNhWa5JiKrpJaTlupXAHTrGWcI41b2RrhlyZHSdsylTLazxUkYfMmqCEAknqw6mNhKoQ7lI98FaUiQCvKDtqODs4jL7TFuoo0PBJK5S/YGYF2TTJZa3Wt7aW6ObdYbiuJVRBTJCZab6lJL83+AfrBf8AiqlZj3ZYC7Mb8AdIzdSEqZalGW5/ExdzoEgEceMSMLdsHyKmI1M1CQpClL0T4lCyQbeEtckjxFzbWJaIlMtWXxJLAZGUxuFOdiD5W8oi+0SzOTLB7xRIzOknLfU5g2m99Iu1OKS5SMqPEp9EjT0Fm4CLOXS0ukX1tyKSqu/eabMQbZTfxHRrl9S5ghUzQLy1GwGnO/z04dYGzpq5n3aGBVc6ObNYE3H6PrDF1CUpTLCX7vICcwANg4BG9tobyyRaSaNIlYI8NteZc2NhoTlfyEQ/wrvjnM0XBAORLMP6rFy+m2kBqLEgsrC193mCikIudNHULkgamDNIETAHzABKUoToE6DaxNorL3d2GLU1sQ4rSLlzUpUoLlqJCCS3dqZwDspwCHVwjpsqaogLAysfZy+EDUEtoeW/u0FFhypr28PE/rrDKuTTo8KlmYB+FAcWLsSLbaKMKeRVYyKflKEumlpT7OYJYgBZsRc2DPo+7vE1FTLJMxMolag2ZQLM5s5Fjcw0VYUr7uUlO4zuST0SfnE82XOUi8xTEaBkhuHhDiM8tUO9npU/yT01DLktMqFJC/wjMLbFuNovL7RSyGkylTPLIPVWumwgHJowLsH466c4npkMb+QjP7TXCGSwJu5Ox+KVVROGVasiN0Is44KVqfJoqyZCQGShukXZiS9j6fCOpKNSi7dOULlllLljIxjFcUU1ynuAA27w+TRlRckHha5gyjDSm6hZ3a+mvzhZ9bIlozFkgalRZibNfzi6hkl8vqLeaK4BiMGfRwdR+9oecGs1tOOnWIartOlaT3RcXcpFhpv+sUv4qst3ZVmJYhYDNxBNx+92jRHTP1FPNIMysFcbHzb4axfpFzZFgtx+VTkeXCMdMx2sSklpSUh2UczqYXAzEMwfUXHDeTEcclzJAE05VLYWdwr+XieTN8YdjwuDtOhU5PIt1aN4jF0myxlPHb12hql+IRnMLxOnmJSjvVDkssbbOePB94MUIGcJToPOOlp55JeamvXuc7PjhF7Wg/KV8o6Kap7LV+9AI6NRnLs74wOxCmE2URuIMKECMUCwWRZwbjUtsOGsUyzUI9RfHDqlRkVVikJKB7WnTjENHJIHs6xopFAhI8SQVatx9W4iH/Z30A98cLUPNnlbVHYwyx4o1H92B1yw7AEq4AP/AIgdjVctEtKEoCytYBIuEgu5N+Ibz8oPo7PnvO8VMWo3s7AuwFvKKGH9lE0xWZZAMx9S5JfmdnPrF8WLw1b3KzyqWxiq/EVy0HuEkrcAm/3YuHI0O0V6DD5hYzJgJA8KSDYlrE6e4x6IvAg2VSrEOosL/vlyivSdn5bgrWGBdi4drXf92jQsu1UUajJ22ZOdWtUD7pLqSACfCygGIJNla+/eL8vAyoKmL8CilkhB0J0sQAAHfRy22h1dRhtJm8ZQTwPi2/CNm+URT8cpJV1TU6+yllkdQl4HV9ypl8P7M1BXmKyGLAkO6eDBgLN74MVnY5E1ICswyk3DA31JOh0eKuI/6gy0gpkSVKOuY+AE9A5I6xnajtZX1JyIUJQ3EtLW/qUSR5NBcZVbdFVUn0pGqqOz9JTpSZi0pAv4lhOtnvcnlEcrHJBOWkkqmkfiW6E9XIzHkGjOUfZslWecoqUdSo5ifM3JjUUlCiWlkj3axiy5o9tzdDC1yNnTZ8xQTMUWI9hAyp6HjpuY6ZTE6KSG9BC1RZrF2b3+8XiIpOgck36X0vGGUpSe7NkYqKVCTCCoMPELuBr5GCFOh7M3WFoaXLdV+cWJQUVWfo2zaxTqfCKTpnIpRmYD3+sPTQsbnXSKeLdo5dMlQU0xaW8Asz38R2ttGCm45PqSe/moly1MPygXcJclx6tG3FpHJXIxS1FS6Uz09KZSRmKkkNa7i2ukUpnaOSMxCnIYZWYlzskgW58o8/oJipczJTzUADirOlRJYskBubuHeDc5Ym5JgWjvEKDBKbKcZCL3F1eUbIaaMeBMskn8y5ieOz5xAkHKLeLqLpINrHe7twgZiFItQHjC1PoSGAHI2DnpF+XJQQwBc76aanNt5QyfLl6hkqI8RSbltCXudIdGKW6DvwQYTREJmAnKo2IBHh4Hw6mOXh0xwhYQp1OCSxBCXBSOIZ9YeqaZJdYPibTYB9Ax1J0fho0cuZ9yq+ZUsMh28Sm8OpJ6Rat7K9ipSJnTkGUpDSUk+I6KazDNcDU+5+Jjs3Klu4T42AAJslhqkbAsTxiLCUTVpZRUlLlwSScpD6kuL8oOYfhYYFI6rN9dgTra0Vlb2huySain1EEvDJSZjH7xSjchn4knbeDuAUWQEi42+kVZFMnN3cu5PtK39Y0VLJAAA0HvMadPp+h9T5MefO5quxSXIL8YWCJRvCxsozWTPENTTpWzhyC41DHyiXNCPAaTVMKbW6BddnSCUgKPDTz3eMV2j7Q18m4koQn87Ffm+g8xHoc8OOcVSlKgUqAKTqDv0hDwRsasrPHx2rrySe/VfYIQ3plhf4zWqL98vyZPoEgNG1xDsglBMySHRujdPT6QlJhks/QxPBsPimIWuqX7U2aeq1fWI04Us7GPTJWEJiyjCk8IPgsHjHmIwNfCJ5fZ5XCPS04YmJU4enhE8F+oPGPNh2aLO0T4FSJSHtxje19O0tWUXylurWjE4QQkcX5P+/0jn/qa6YxS7nS/TfecpBggm36Rz216HWFYHje+hvyfSLMoJ9m457Rx9jc7QLqZLsN/e/SLuFUYSHOpO/wi0KVNyNy78eV4AdoMZ7gJQm8xQygbJezvo4cGDHHKU+mIJZUobh2vxSTLLTJiQWdrP7vnGRxntoFJy0rpUospTO3Q6P8ArGdSfCsTPvJigTmc22OtjxB4wyRIJVlEuzPZgc3C3IiOpj0sI7vdmB5W+CxS0ud+8clXtKfUu7/WCdPh6B4FhKkfic7DiN/hA37KJi0AOlQWGIvl0c7OG/zBOtwsqCimcrOwuhkspO29tbONYfKu7KOFvgtTcNRNWgqSAkezbKSWNunWHVuSnWgheVBBQoMPCXKgS3EqZtneBtHUTZSQlV1X8RISlizEMb9We5gsuhmKyFZQo7ghtRZtS4I+MVtLZsvXdckFLivfzFSJYCUpSWUm9wH/ALQQCL7tApc6YpRytlWPa0IN+HF40aey9YykoKAhSs2UlvI2fbjBDB+xRA++WU6eFBtuTc6u8aFil2Qjxopbv7ACTTVKinvDkGUhJytYhPiD6m0GMOwNKgnOhS5gLFevhL+68bWnlJlICBoON/jCGoeyA/QWgvTSfcX7R8in/DEADMcoA0Gv/tDSTM8EoMkbxOtF/Gcx/KnbqYmkyibWCfyjT9YdjxRhwJnklLkShpQkZUf3K49PrBRCWAERypbRMBDkqFHNHQpjogSOEMPjmiBISYgmy+EXCiI1SoBCkiflN/WEqKNEzxeyr8w+Yh9TSkwPWqZLNrj97wOCEipcyXqMw4iJZNUDCUmKIVZ2PDT3Gx8onXKlq1DHim3u/wAwVIDQ5MwQ8Kit9lP4VA8jYxxzDVJ+MGwUOqw6THn6iZS1o0vY8v2Y3hmgiMj2ko2UFgf4jJrcPiY/obdBmWPJT4ZJSLBALkn9+6CbpSMyjzeK2F0wXLzBTDh0+URTqRSg6lABtj8eccBYZcnWyZIN0mS1eJINk3L8bdYES6QKUSoOPzEWc2IfyirPnS0KIzjqCVH0D7xbk4ghsqcxHAJWflDscZxdqL+wvJ0NVZQn4EJqjkUUtYjVrDyAtHUvZzK+Zbk7JLAcNDy84MUkiar2EKvuoZR9fdBWTgC1F5kxuSQPiY1QhqcnCr6meU8GPvf0BdDhaJKTpzUrfjFiTQAk5UOWcAJIBPDMeUaKkw6VL2c8VFz74t9+Nh6CNEdBe+SRnlrH8KAiMHWoBwlI4HxH1sIISMJlpLl1HifptFtSlalkjiS0QqmI3UVchYesa8enx4+EZp5pz5ZIuaBDVFRvZI4qLe6ITVNoAkep9Yrmc9w556+8w6xVFglO7rPPwj6mOMwmzsOAsPqYSVIJubRZlU4ESmGxKeRytFyXLaETYQueDQCVJhXiLPHFcQhI8dEQXHRCEghzwwQrxCDoUQkdACKREapYMSRzRCAqtwaXMGjHiIET6Wok+we8TwVr6xrGhi0QKCmZOXjg0mBSDzDj1EEZGIP7KnHIv7onrMPQo3SIFTsF3TEpktBM1YOoB6iIp0qSsMqXbkr/ABA00k1PsqUeRv8AGHDvgPElJ9RAISjBKdiEmcgH8sw/9jFWb2UplNmmzi2gNx8I5desH/bPkf0jpWLqJAEmYo8gD84p0R9C/VL1LVLgFMjT3oJ+UX5dNKTopv7D9I6kRNUHMoo/qKf/AJeLCqSZwT/7H/rDELGOj8yvJMMM1H859BEcymmv7I65v0ivUUs9vCmX5rP/AFibkLJqkjRA8yTES69X5m6ACBwoKlRuAOn1JieVgCz7ZfqfpEoIkyuTxKj6wz7QtVkpb3wTk4KBrBGRQhOgAg0CwFKw1arqc9foIJ0+HhOpf3QREmHiXEAVUyhEgSYsZYVoJCuUx3dxM0c0QhB3cL3YiZoaREIRGWIWJI6IQhCoeDEMPBiEJEmHGGPHPECSCFhghYBB8IYa8LEIRzEcYqKDGL8RTJQMEhCAIXI+0SolCHgRLBRWTQo3DxZlyQNBCwqTACOAjlqjobEINyxyUQoMK8Qh2WOCYUw6IQaBDwIiUuECHiEJiocYaJyeMcJYioUeJucQhaM1PGEMwRClAiVKYhBe8hM8KBCNEIdmMI8K8KIIBrx0cTHRCH//2Q==',
                        is_available=True
                    ),
                    MenuItem(
                        name='Falafel Special Sandwich',
                        description='Crispy Falafel with salad, pickles, and tahini in Shami bread.',
                        price=20.0,
                        category='Sandwiches',
                        image_url='data:image/jpeg;base64,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',
                        is_available=True
                    ),
                    
                    # --- Meals ---
                    MenuItem(
                        name='Koshary Bowl (Large)',
                        description="Egypt's national dish: Rice, pasta, lentils, topped with tomato sauce and crispy onions.",
                        price=50.0,
                        category='Meals',
                        image_url='data:image/jpeg;base64,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',
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
                        image_url='data:image/jpeg;base64,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',
                        is_available=True
                    ),
                    
                    # --- Desserts ---
                    MenuItem(
                        name='Om Ali (With Nuts)',
                        description='Traditional Egyptian bread pudding with hot milk, cream, and nuts.',
                        price=65.0,
                        category='Desserts',
                        image_url= 'data:image/jpeg;base64,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' ,
                        is_available=True
                    ),
                    MenuItem(
                        name='Rice Pudding (Roz Bel Laban)',
                        description='Creamy rice pudding topped with cinnamon and raisins.',
                        price=35.0,
                        category='Desserts',
                        image_url='data:image/jpeg;base64,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',
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


with app.app_context():
    db.create_all()
    print("Database tables created successfully!")
    
    if not User.query.filter_by(email='admin@app.com').first():
        print("Seeding initial data...")
        init_db() 
    else:
        print("Database already initialized with data.")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)