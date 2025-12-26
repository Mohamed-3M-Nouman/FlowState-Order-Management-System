"""
Comprehensive Test Suite for Flask Restaurant Ordering System
Tests database models, authentication, admin logic, order workflows, and role protection.
"""

import pytest
import json
from datetime import datetime
from app import app, db, User, MenuItem, Order, SystemConfig


# ============================================================================
# PYTEST FIXTURES
# ============================================================================

@pytest.fixture
def client():
    """
    Create a test client with in-memory database.
    This ensures tests don't affect the real database.
    """
    # Configure app for testing
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'  # In-memory DB
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    
    with app.test_client() as client:
        with app.app_context():
            # Drop all tables first (in case they exist)
            db.drop_all()
            
            # Create all tables
            db.create_all()
            
            # Seed test data
            seed_test_data()
            
            yield client
            
            # Clean up after test
            db.session.remove()
            db.drop_all()


def seed_test_data():
    """Seed the test database with initial data"""
    # Create test users
    admin = User(
        email='admin@test.com',
        password='admin123',
        name='Test Admin',
        phone='555-0001',
        role='admin',
        addresses='[]'
    )
    
    customer = User(
        email='customer@test.com',
        password='customer123',
        name='Test Customer',
        phone='555-1234',
        role='customer'
    )
    customer.set_addresses_list(['123 Test St', '456 Demo Ave'])
    
    driver = User(
        email='driver@test.com',
        password='driver123',
        name='Test Driver',
        phone='555-9999',
        role='driver',
        addresses='[]'
    )
    
    db.session.add_all([admin, customer, driver])
    
    # Create test menu items
    menu_items = [
        MenuItem(
            name='Test Burger',
            description='Delicious test burger',
            price=10.99,
            category='Sandwiches',
            image_url='https://example.com/burger.jpg',
            is_available=True
        ),
        MenuItem(
            name='Test Pizza',
            description='Amazing test pizza',
            price=15.99,
            category='Meals',
            image_url='https://example.com/pizza.jpg',
            is_available=True
        ),
        MenuItem(
            name='Unavailable Item',
            description='This item is not available',
            price=5.99,
            category='Drinks',
            image_url='https://example.com/drink.jpg',
            is_available=False
        )
    ]
    
    db.session.add_all(menu_items)
    
    # Create system config
    config_items = [
        SystemConfig(key='delivery_fee', value='20.0'),
        SystemConfig(key='is_delivery_active', value='True')
    ]
    
    db.session.add_all(config_items)
    
    db.session.commit()


def login(client, email, password):
    """Helper function to login a user"""
    return client.post('/login', data={
        'email': email,
        'password': password
    }, follow_redirects=True)


def logout(client):
    """Helper function to logout"""
    return client.get('/logout', follow_redirects=True)


# ============================================================================
# TEST 1: DATABASE MODELS & CONSTRAINTS
# ============================================================================

def test_user_model_creation(client):
    """Test User model creation with all required fields"""
    with app.app_context():
        # Create a new user
        new_user = User(
            email='newuser@test.com',
            password='password123',
            name='New User',
            phone='555-5555',
            role='customer',
            addresses='[]',
            loyalty_points=100
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        # Query the user
        user = User.query.filter_by(email='newuser@test.com').first()
        
        # Assertions
        assert user is not None
        assert user.email == 'newuser@test.com'
        assert user.phone == '555-5555'  # Critical field
        assert user.name == 'New User'
        assert user.role == 'customer'
        assert user.loyalty_points == 100
        assert user.get_addresses_list() == []


def test_user_addresses_json_storage(client):
    """Test that user addresses are stored and retrieved as JSON"""
    with app.app_context():
        user = User.query.filter_by(email='customer@test.com').first()
        
        # Check addresses
        addresses = user.get_addresses_list()
        assert len(addresses) == 2
        assert '123 Test St' in addresses
        assert '456 Demo Ave' in addresses
        
        # Add new address
        addresses.append('789 New Rd')
        user.set_addresses_list(addresses)
        db.session.commit()
        
        # Verify it was saved
        user = User.query.filter_by(email='customer@test.com').first()
        assert len(user.get_addresses_list()) == 3


def test_menuitem_defaults(client):
    """Test MenuItem model defaults"""
    with app.app_context():
        # Create menu item without specifying is_available
        item = MenuItem(
            name='Default Item',
            description='Test default values',
            price=9.99,
            category='Test'
        )
        
        db.session.add(item)
        db.session.commit()
        
        # Check defaults
        assert item.is_available is True  # Should default to True
        assert item.created_at is not None


def test_order_model_with_all_fields(client):
    """Test Order model with all conditional fields"""
    with app.app_context():
        customer = User.query.filter_by(email='customer@test.com').first()
        
        # Create order with all fields
        order = Order(
            user_id=customer.id,
            total_price=50.99,
            subtotal=30.99,
            delivery_fee=20.0,
            status='New',
            order_type='Dine-in',
            delivery_address=None,
            pickup_code=None,
            estimated_pickup_time='7:00 PM',
            reservation_time='2025-12-10T19:00',
            guest_count=4
        )
        order.set_items_list([
            {'name': 'Test Burger', 'quantity': 2, 'price': 10.99},
            {'name': 'Test Pizza', 'quantity': 1, 'price': 15.99}
        ])
        
        db.session.add(order)
        db.session.commit()
        
        # Verify
        saved_order = Order.query.get(order.id)
        assert saved_order.order_type == 'Dine-in'
        assert saved_order.guest_count == 4
        assert saved_order.reservation_time == '2025-12-10T19:00'
        assert len(saved_order.get_items_list()) == 2


def test_systemconfig_model(client):
    """Test SystemConfig model and helper methods"""
    with app.app_context():
        # Test get_value
        delivery_fee = SystemConfig.get_value('delivery_fee')
        assert delivery_fee == '20.0'
        
        # Test set_value
        SystemConfig.set_value('delivery_fee', '25.0')
        assert SystemConfig.get_value('delivery_fee') == '25.0'
        
        # Test get_delivery_fee (returns float)
        assert SystemConfig.get_delivery_fee() == 25.0
        
        # Test is_delivery_active
        assert SystemConfig.is_delivery_active() is True
        
        # Test setting new config
        SystemConfig.set_value('new_config', 'test_value')
        assert SystemConfig.get_value('new_config') == 'test_value'


# ============================================================================
# TEST 2: AUTHENTICATION
# ============================================================================

def test_user_registration_success(client):
    """Test successful user registration"""
    response = client.post('/register', data={
        'name': 'Brand New User',
        'email': 'brandnew@test.com',
        'password': 'newpass123',
        'phone': '555-7777'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Account created' in response.data or b'Please login' in response.data
    
    # Verify user was created in database
    with app.app_context():
        user = User.query.filter_by(email='brandnew@test.com').first()
        assert user is not None
        assert user.name == 'Brand New User'
        assert user.phone == '555-7777'
        assert user.role == 'customer'


def test_user_registration_duplicate_email(client):
    """Test registration with duplicate email fails"""
    response = client.post('/register', data={
        'name': 'Duplicate User',
        'email': 'customer@test.com',  # Already exists
        'password': 'password123',
        'phone': '555-8888'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Email already registered' in response.data


def test_user_registration_without_phone(client):
    """Test registration without phone number fails"""
    response = client.post('/register', data={
        'name': 'No Phone User',
        'email': 'nophone@test.com',
        'password': 'password123',
        'phone': ''  # Empty phone
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Phone number is required' in response.data


def test_login_success(client):
    """Test successful login"""
    response = login(client, 'customer@test.com', 'customer123')
    
    assert response.status_code == 200
    assert b'Welcome back' in response.data or b'Our Menu' in response.data


def test_login_wrong_password(client):
    """Test login with wrong password fails"""
    response = login(client, 'customer@test.com', 'wrongpassword')
    
    assert response.status_code == 200
    assert b'Invalid email or password' in response.data


def test_login_nonexistent_user(client):
    """Test login with non-existent email fails"""
    response = login(client, 'nonexistent@test.com', 'password123')
    
    assert response.status_code == 200
    assert b'Invalid email or password' in response.data


def test_logout(client):
    """Test logout functionality"""
    # Login first
    login(client, 'customer@test.com', 'customer123')
    
    # Then logout
    response = logout(client)
    
    assert response.status_code == 200
    assert b'logged out' in response.data


# ============================================================================
# TEST 3: ADMIN LOGIC
# ============================================================================

def test_admin_add_menu_item(client):
    """Test admin can add new menu item"""
    # Login as admin
    login(client, 'admin@test.com', 'admin123')
    
    # Add new menu item
    response = client.post('/admin/add_item', data={
        'name': 'New Admin Item',
        'description': 'Added by admin',
        'price': '12.50',
        'category': 'Meals',
        'image_url': 'https://example.com/new.jpg'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'added successfully' in response.data
    
    # Verify in database
    with app.app_context():
        item = MenuItem.query.filter_by(name='New Admin Item').first()
        assert item is not None
        assert item.price == 12.50
        assert item.category == 'Meals'


def test_admin_update_delivery_fee(client):
    """Test admin can update delivery fee in SystemConfig"""
    # Login as admin
    login(client, 'admin@test.com', 'admin123')
    
    # Update delivery fee
    response = client.post('/admin/update_delivery_price', data={
        'delivery_fee': '30.0'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'updated' in response.data
    
    # Verify in database
    with app.app_context():
        fee = SystemConfig.get_delivery_fee()
        assert fee == 30.0


def test_admin_toggle_delivery_service(client):
    """Test admin can toggle delivery service"""
    # Login as admin
    login(client, 'admin@test.com', 'admin123')
    
    # Get initial status
    with app.app_context():
        initial_status = SystemConfig.is_delivery_active()
    
    # Toggle delivery
    response = client.get('/admin/toggle_delivery', follow_redirects=True)
    
    assert response.status_code == 200
    
    # Verify status changed
    with app.app_context():
        new_status = SystemConfig.is_delivery_active()
        assert new_status != initial_status


def test_admin_delete_menu_item(client):
    """Test admin can delete menu item"""
    # Login as admin
    login(client, 'admin@test.com', 'admin123')
    
    # Get an item ID
    with app.app_context():
        item = MenuItem.query.filter_by(name='Test Burger').first()
        item_id = item.id
    
    # Delete the item
    response = client.get(f'/admin/delete_item/{item_id}', follow_redirects=True)
    
    assert response.status_code == 200
    assert b'deleted successfully' in response.data
    
    # Verify it's gone
    with app.app_context():
        item = MenuItem.query.get(item_id)
        assert item is None


def test_admin_edit_menu_item(client):
    """Test admin can edit menu item"""
    # Login as admin
    login(client, 'admin@test.com', 'admin123')
    
    # Get an item ID
    with app.app_context():
        item = MenuItem.query.filter_by(name='Test Pizza').first()
        item_id = item.id
    
    # Edit the item
    response = client.post(f'/admin/edit_item/{item_id}', data={
        'name': 'Updated Pizza',
        'description': 'Updated description',
        'price': '19.99',
        'category': 'Meals',
        'image_url': 'https://example.com/updated.jpg',
        'is_available': 'on'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'updated successfully' in response.data
    
    # Verify changes
    with app.app_context():
        item = MenuItem.query.get(item_id)
        assert item.name == 'Updated Pizza'
        assert item.price == 19.99


# ============================================================================
# TEST 4: ORDER WORKFLOWS (CORE LOGIC)
# ============================================================================

def test_delivery_order_workflow(client):
    """Test complete delivery order workflow"""
    # Login as customer
    login(client, 'customer@test.com', 'customer123')
    
    # Add items to cart
    with app.app_context():
        item = MenuItem.query.filter_by(name='Test Burger').first()
        item_id = item.id
    
    client.get(f'/add_to_cart/{item_id}')
    client.get(f'/add_to_cart/{item_id}')  # Add 2 burgers
    
    # Place delivery order
    response = client.post('/place_order', data={
        'order_type': 'Delivery',
        'address': '789 Delivery St'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Order' in response.data and b'placed successfully' in response.data
    
    # Verify order in database
    with app.app_context():
        customer = User.query.filter_by(email='customer@test.com').first()
        orders = Order.query.filter_by(user_id=customer.id).all()
        assert len(orders) > 0
        
        order = orders[-1]  # Get latest order
        assert order.order_type == 'Delivery'
        assert order.delivery_address == '789 Delivery St'
        assert order.delivery_fee == 20.0  # Should include delivery fee
        assert order.total_price == order.subtotal + order.delivery_fee
        assert order.pickup_code is None  # Not for delivery
        assert order.reservation_time is None  # Not for delivery


def test_takeaway_order_workflow(client):
    """Test takeaway order with pickup code generation"""
    # Login as customer
    login(client, 'customer@test.com', 'customer123')
    
    # Add items to cart
    with app.app_context():
        item = MenuItem.query.filter_by(name='Test Pizza').first()
        item_id = item.id
    
    client.get(f'/add_to_cart/{item_id}')
    
    # Place takeaway order
    response = client.post('/place_order', data={
        'order_type': 'Takeaway'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Order' in response.data and b'placed successfully' in response.data
    
    # Verify order in database
    with app.app_context():
        customer = User.query.filter_by(email='customer@test.com').first()
        orders = Order.query.filter_by(user_id=customer.id).all()
        order = orders[-1]
        
        assert order.order_type == 'Takeaway'
        assert order.pickup_code is not None  # CRITICAL: Pickup code generated
        assert order.pickup_code.startswith('#')  # Format: #123
        assert order.estimated_pickup_time is not None
        assert order.delivery_fee == 0  # No delivery fee for takeaway
        assert order.delivery_address is None  # No address for takeaway


def test_dinein_order_workflow(client):
    """Test dine-in order with reservation details"""
    # Login as customer
    login(client, 'customer@test.com', 'customer123')
    
    # Add items to cart
    with app.app_context():
        item = MenuItem.query.filter_by(name='Test Burger').first()
        item_id = item.id
    
    client.get(f'/add_to_cart/{item_id}')
    
    # Place dine-in order with reservation
    response = client.post('/place_order', data={
        'order_type': 'Dine-in',
        'reservation_time': '2025-12-15T19:30',
        'guests': '6'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Order' in response.data and b'placed successfully' in response.data
    
    # Verify order in database
    with app.app_context():
        customer = User.query.filter_by(email='customer@test.com').first()
        orders = Order.query.filter_by(user_id=customer.id).all()
        order = orders[-1]
        
        assert order.order_type == 'Dine-in'
        assert order.reservation_time == '2025-12-15T19:30'  # CRITICAL: Reservation saved
        assert order.guest_count == 6  # CRITICAL: Guest count saved
        assert order.delivery_fee == 0  # No delivery fee
        assert order.pickup_code is None  # No pickup code for dine-in
        assert order.delivery_address is None  # No address for dine-in


def test_order_items_snapshot(client):
    """Test that order items are saved as snapshot (JSON)"""
    # Login as customer
    login(client, 'customer@test.com', 'customer123')
    
    # Add items to cart
    with app.app_context():
        burger = MenuItem.query.filter_by(name='Test Burger').first()
        pizza = MenuItem.query.filter_by(name='Test Pizza').first()
    
    client.get(f'/add_to_cart/{burger.id}')
    client.get(f'/add_to_cart/{burger.id}')
    client.get(f'/add_to_cart/{pizza.id}')
    
    # Place order
    client.post('/place_order', data={
        'order_type': 'Takeaway'
    }, follow_redirects=True)
    
    # Verify items snapshot
    with app.app_context():
        customer = User.query.filter_by(email='customer@test.com').first()
        order = Order.query.filter_by(user_id=customer.id).first()
        
        items = order.get_items_list()
        assert len(items) == 2  # 2 different items
        
        # Check burger
        burger_item = next((item for item in items if item['name'] == 'Test Burger'), None)
        assert burger_item is not None
        assert burger_item['quantity'] == 2
        assert burger_item['price'] == 10.99
        
        # Check pizza
        pizza_item = next((item for item in items if item['name'] == 'Test Pizza'), None)
        assert pizza_item is not None
        assert pizza_item['quantity'] == 1
        assert pizza_item['price'] == 15.99


def test_delivery_order_without_address_fails(client):
    """Test that delivery order without address fails"""
    # Login as customer
    login(client, 'customer@test.com', 'customer123')
    
    # Add item to cart
    with app.app_context():
        item = MenuItem.query.filter_by(name='Test Burger').first()
    
    client.get(f'/add_to_cart/{item.id}')
    
    # Try to place delivery order without address
    response = client.post('/place_order', data={
        'order_type': 'Delivery',
        'address': ''  # Empty address
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Address is required' in response.data


def test_dinein_order_without_reservation_fails(client):
    """Test that dine-in order without reservation details fails"""
    # Login as customer
    login(client, 'customer@test.com', 'customer123')
    
    # Add item to cart
    with app.app_context():
        item = MenuItem.query.filter_by(name='Test Burger').first()
    
    client.get(f'/add_to_cart/{item.id}')
    
    # Try to place dine-in order without reservation time
    response = client.post('/place_order', data={
        'order_type': 'Dine-in',
        'guests': '4'
        # Missing reservation_time
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Reservation' in response.data and b'required' in response.data


# ============================================================================
# TEST 5: ROLE PROTECTION
# ============================================================================

def test_customer_cannot_access_admin_dashboard(client):
    """Test that customer role cannot access admin dashboard"""
    # Login as customer
    login(client, 'customer@test.com', 'customer123')
    
    # Try to access admin dashboard
    response = client.get('/admin/dashboard', follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Access denied' in response.data or b'Admin privileges required' in response.data


def test_customer_cannot_access_admin_menu(client):
    """Test that customer cannot access admin menu management"""
    # Login as customer
    login(client, 'customer@test.com', 'customer123')
    
    # Try to access admin menu
    response = client.get('/admin/menu', follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Access denied' in response.data or b'Admin privileges required' in response.data


def test_driver_cannot_access_admin_dashboard(client):
    """Test that driver role cannot access admin dashboard"""
    # Login as driver
    login(client, 'driver@test.com', 'driver123')
    
    # Try to access admin dashboard
    response = client.get('/admin/dashboard', follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Access denied' in response.data or b'Admin privileges required' in response.data


def test_customer_cannot_access_driver_dashboard(client):
    """Test that customer cannot access driver dashboard"""
    # Login as customer
    login(client, 'customer@test.com', 'customer123')
    
    # Try to access driver dashboard
    response = client.get('/driver/dashboard', follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Access denied' in response.data or b'Driver privileges required' in response.data


def test_unauthenticated_user_redirected_to_login(client):
    """Test that unauthenticated users are redirected to login"""
    # Try to access protected route without login
    response = client.get('/cart', follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Please login' in response.data or b'Login' in response.data


def test_admin_can_access_admin_dashboard(client):
    """Test that admin role can access admin dashboard"""
    # Login as admin
    login(client, 'admin@test.com', 'admin123')
    
    # Access admin dashboard
    response = client.get('/admin/dashboard')
    
    assert response.status_code == 200
    assert b'Admin Dashboard' in response.data or b'dashboard' in response.data.lower()


def test_driver_can_access_driver_dashboard(client):
    """Test that driver role can access driver dashboard"""
    # Login as driver
    login(client, 'driver@test.com', 'driver123')
    
    # Access driver dashboard
    response = client.get('/driver/dashboard')
    
    assert response.status_code == 200
    assert b'Driver Dashboard' in response.data or b'driver' in response.data.lower()


# ============================================================================
# TEST 6: ADDITIONAL BUSINESS LOGIC
# ============================================================================

def test_order_status_update(client):
    """Test admin can update order status"""
    # Create an order first
    with app.app_context():
        customer = User.query.filter_by(email='customer@test.com').first()
        order = Order(
            user_id=customer.id,
            total_price=25.99,
            subtotal=25.99,
            delivery_fee=0,
            status='New',
            order_type='Takeaway',
            pickup_code='#123'
        )
        order.set_items_list([{'name': 'Test Item', 'quantity': 1, 'price': 25.99}])
        db.session.add(order)
        db.session.commit()
        order_id = order.id
    
    # Login as admin
    login(client, 'admin@test.com', 'admin123')
    
    # Update order status
    response = client.get(f'/admin/update_status/{order_id}/Preparing', follow_redirects=True)
    
    assert response.status_code == 200
    assert b'updated' in response.data
    
    # Verify status changed
    with app.app_context():
        order = Order.query.get(order_id)
        assert order.status == 'Preparing'


def test_cart_functionality(client):
    """Test cart add, increase, decrease functionality"""
    # Login as customer
    login(client, 'customer@test.com', 'customer123')
    
    with app.app_context():
        item = MenuItem.query.filter_by(name='Test Burger').first()
        item_id = item.id
    
    # Add to cart
    response = client.get(f'/add_to_cart/{item_id}', follow_redirects=True)
    assert response.status_code == 200
    assert b'added to cart' in response.data
    
    # Increase quantity
    response = client.get(f'/cart/increase/{item_id}', follow_redirects=True)
    assert response.status_code == 200
    
    # Decrease quantity
    response = client.get(f'/cart/decrease/{item_id}', follow_redirects=True)
    assert response.status_code == 200


def test_profile_address_management(client):
    """Test customer can add and delete addresses"""
    # Login as customer
    login(client, 'customer@test.com', 'customer123')
    
    # Add new address
    response = client.post('/profile/add_address', data={
        'address': '999 New Address Ln'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b'Address saved' in response.data
    
    # Verify in database
    with app.app_context():
        user = User.query.filter_by(email='customer@test.com').first()
        addresses = user.get_addresses_list()
        assert '999 New Address Ln' in addresses
        
        # Delete address (index 2 - the one we just added)
        address_count = len(addresses)
    
    response = client.get(f'/profile/delete_address/{address_count - 1}', follow_redirects=True)
    assert response.status_code == 200
    assert b'deleted' in response.data


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
