from app import app, db, User, MenuItem, Order, SystemConfig
from datetime import datetime

def simulate_order_flow():
    """Simulate a full order lifecycle programmatically."""
    with app.app_context():
        print("\n--- Starting Order Flow Simulation ---\n")

        # 1. Setup: Fetch Users and Menu Item
        customer = User.query.filter_by(role='customer').first()
        admin = User.query.filter_by(role='admin').first()
        driver = User.query.filter_by(role='driver').first()
        item = MenuItem.query.first()

        if not all([customer, admin, driver, item]):
            print("[x] Error: Missing required data (users or menu items). Please seed the DB first.")
            return

        print(f"[+] Found Customer: {customer.name} ({customer.email})")
        print(f"[+] Found Admin:    {admin.name} ({admin.email})")
        print(f"[+] Found Driver:   {driver.name} ({driver.email})")
        print(f"[+] Found Item:     {item.name} ({item.price} LE)")
        print("-" * 40)

        # 2. Step 1: Customer Places Order
        # Create order items list
        order_items = [{
            'name': item.name,
            'quantity': 2,
            'price': item.price
        }]
        subtotal = item.price * 2
        delivery_fee = SystemConfig.get_delivery_fee()
        total = subtotal + delivery_fee

        new_order = Order(
            user_id=customer.id,
            total_price=total,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            status='New',
            order_type='Delivery',
            delivery_address='123 Test Lane',
            items_summary='' # Will set via method
        )
        new_order.set_items_list(order_items)
        
        db.session.add(new_order)
        db.session.commit()
        
        # Refresh order ID
        print(f"[v] Customer {customer.name} placed Order #{new_order.id} with total {total} LE.")

        # 3. Step 2: Admin Updates Status
        # Fetch order again to be safe (though we have the object)
        order = Order.query.get(new_order.id)
        
        # 'New' -> 'Preparing'
        order.status = 'Preparing'
        db.session.commit()
        
        # 'Preparing' -> 'Ready'
        order.status = 'Ready'
        db.session.commit()
        
        print(f"[v] Admin {admin.name} updated Order #{order.id} to 'Ready'.")

        # 4. Step 3: Driver Updates Status
        # Driver picks up
        order.status = 'Out for Delivery'
        db.session.commit()
        
        # Driver delivers
        order.status = 'Delivered'
        db.session.commit()
        
        print(f"[v] Driver {driver.name} picked up and Delivered Order #[{order.id}].")

        # 5. Final Verification
        final_order = Order.query.get(new_order.id)
        print("-" * 40)
        print(f"[*] Final Order Status Verification: '{final_order.status}'")
        
        if final_order.status == 'Delivered':
            print("[SUCCESS] Full Order Lifecycle Completed Successfully!")
        else:
            print("[FAILURE] Order did not reach 'Delivered' status.")

if __name__ == "__main__":
    simulate_order_flow()
