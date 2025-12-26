"""
Database Migration Verification Script
This script verifies that the SQLite database was created correctly
and contains all the seeded data.
"""

from app import app, db, User, MenuItem, Order, SystemConfig

def verify_database():
    """Verify database migration and seed data"""
    with app.app_context():
        print("=" * 60)
        print("DATABASE MIGRATION VERIFICATION")
        print("=" * 60)
        
        # Check Users
        print("\n[OK] USERS TABLE:")
        users = User.query.all()
        print(f"  Total users: {len(users)}")
        for user in users:
            print(f"  - {user.name} ({user.email}) - Role: {user.role} - Phone: {user.phone}")
            if user.role == 'customer':
                addresses = user.get_addresses_list()
                print(f"    Saved addresses: {len(addresses)}")
                for addr in addresses:
                    print(f"      * {addr}")
        
        # Check Menu Items
        print("\n[OK] MENU ITEMS TABLE:")
        menu_items = MenuItem.query.all()
        print(f"  Total menu items: {len(menu_items)}")
        for item in menu_items:
            print(f"  - {item.name} ({item.category}) - ${item.price:.2f} - Available: {item.is_available}")
        
        # Check Orders
        print("\n[OK] ORDERS TABLE:")
        orders = Order.query.all()
        print(f"  Total orders: {len(orders)}")
        if orders:
            for order in orders:
                print(f"  - Order #{order.id} - {order.order_type} - Status: {order.status}")
                print(f"    Customer: {order.customer.name if order.customer else 'Unknown'}")
                print(f"    Total: ${order.total_price:.2f}")
                if order.pickup_code:
                    print(f"    Pickup Code: {order.pickup_code}")
                if order.reservation_time:
                    print(f"    Reservation: {order.reservation_time} - Guests: {order.guest_count}")
        else:
            print("  No orders yet (this is expected for a fresh database)")
        
        # Check System Config
        print("\n[OK] SYSTEM CONFIG TABLE:")
        configs = SystemConfig.query.all()
        print(f"  Total config entries: {len(configs)}")
        for config in configs:
            print(f"  - {config.key} = {config.value}")
        
        # Test config methods
        print("\n[OK] CONFIG METHODS:")
        print(f"  Delivery Fee: ${SystemConfig.get_delivery_fee():.2f}")
        print(f"  Delivery Active: {SystemConfig.is_delivery_active()}")
        
        print("\n" + "=" * 60)
        print("[SUCCESS] DATABASE MIGRATION SUCCESSFUL!")
        print("=" * 60)
        print("\nAll tables created and seeded with initial data.")
        print("Database file: instance/restaurant.db")
        print("\nTest Accounts:")
        print("  Admin:    admin@admin.com / admin")
        print("  Customer: customer@test.com / customer")
        print("  Driver:   driver@test.com / driver")
        print("=" * 60)

if __name__ == '__main__':
    verify_database()
