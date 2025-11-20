from flask import Flask, render_template, request, jsonify
import oracledb
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# Oracle database connection configuration
DB_USER = "system"
DB_PASSWORD = "neelesh"
DB_DSN = "localhost:1521/XEPDB1"

# Try to initialize Oracle client (if Thick mode is available).
# If not, it will continue in Thin mode.
try:
    oracledb.init_oracle_client()
except oracledb.Error:
    print("Oracle client could not be initialized; using Thin mode if available.")

def get_db_connection():
    return oracledb.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        dsn=DB_DSN
    )

# ----------------------------
# Password validation
# ----------------------------
def validate_password(password):
    """Validate password meets security requirements"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    # Check for at least one uppercase letter
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    
    # Check for at least one lowercase letter
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    
    # Check for at least one digit
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    
    # Check for at least one special character
    special_chars = "!@#$%^&*()_+-=[]{}|;:,<>?"
    if not any(c in special_chars for c in password):
        return False, "Password must contain at least one special character"
    
    return True, "Password is valid"

# ----------------------------
# AUTH & PAGES
# ----------------------------

@app.route('/')
def index():
    # Landing/login page
    return render_template('login.html')

@app.route('/login')
def login_page():
    # Used by logout redirect from dashboard JS: window.location.href = '/login'
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    # Dashboard page (inventory, orders, profile...)
    return render_template('index.html')

@app.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        name = data['name']
        email = data['email']
        password = data['password']

        # Validate password
        is_valid, message = validate_password(password)
        if not is_valid:
            return jsonify({
                'success': False,
                'message': message
            }), 400

        # Hash the password before storing
        hashed_password = generate_password_hash(password)

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                # First check if the table exists
                try:
                    cursor.execute("""
                        SELECT 1 FROM users WHERE ROWNUM = 1
                    """)
                except oracledb.DatabaseError as e:
                    error, = e.args
                    if error.code == 942:  # ORA-00942: table or view does not exist
                        # Create the table if it doesn't exist
                        cursor.execute("""
                            CREATE TABLE users (
                                full_name VARCHAR2(100) NOT NULL,
                                email VARCHAR2(100) PRIMARY KEY,
                                password VARCHAR2(255) NOT NULL,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                            )
                        """)
                        connection.commit()

                # Insert the user
                try:
                    cursor.execute("""
                        INSERT INTO users (full_name, email, password)
                        VALUES (:1, :2, :3)
                    """, [name, email, hashed_password])
                    connection.commit()
                except oracledb.DatabaseError as e:
                    print(f"Database error during insert: {str(e)}")
                    raise
        
        return jsonify({
            'success': True,
            'message': 'Registration successful',
            'name': name
        })

    except oracledb.IntegrityError:
        return jsonify({
            'success': False,
            'message': 'Email already exists'
        }), 400
    
    except Exception as e:
        print(f"Registration error: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data['email']
        password = data['password']

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                # First check if the table exists and has any records
                cursor.execute("""
                    SELECT COUNT(*) 
                    FROM users
                """)
                count = cursor.fetchone()[0]
                
                if count == 0:
                    return jsonify({
                        'success': False,
                        'message': 'No users exist in the system'
                    }), 401

                # Get user details including the hashed password
                cursor.execute("""
                    SELECT full_name, password 
                    FROM users 
                    WHERE email = :email
                """, [email])
                
                result = cursor.fetchone()
                
                if result and check_password_hash(result[1], password):
                    return jsonify({
                        'success': True,
                        'message': 'Login successful',
                        'name': result[0]
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': 'Invalid email or password'
                    }), 401

    except oracledb.DatabaseError as e:
        # Handle specific database errors (like table not existing)
        error, = e.args
        if error.code == 942:  # ORA-00942: table or view does not exist
            return jsonify({
                'success': False,
                'message': 'System is not properly initialized'
            }), 500
        return jsonify({
            'success': False,
            'message': 'Database error occurred'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ----------------------------
# INVENTORY APIs
# Uses Inventory table from d.sql
# ----------------------------

@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    """Return all inventory items."""
    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT item_id, item_name, sku, quantity, price
                    FROM Inventory
                    ORDER BY created_at DESC
                """)
                rows = cursor.fetchall()

        items = []
        for row in rows:
            items.append({
                "id": int(row[0]) if row[0] is not None else None,
                "name": row[1],
                "sku": row[2],
                "quantity": int(row[3]) if row[3] is not None else 0,
                "price": float(row[4]) if row[4] is not None else 0.0
            })

        return jsonify({"success": True, "items": items})
    except oracledb.DatabaseError as e:
        error, = e.args
        return jsonify({
            "success": False,
            "message": f"Database error: {error.message}"
        }), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/inventory', methods=['POST'])
def create_inventory_item():
    """Add a new item to Inventory."""
    try:
        data = request.get_json()
        name = data.get("name")
        sku = data.get("sku")
        quantity = int(data.get("quantity", 0))
        price = float(data.get("price", 0))

        if not name or not sku:
            return jsonify({
                "success": False,
                "message": "name and sku are required"
            }), 400

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                # Insert item
                cursor.execute("""
                    INSERT INTO Inventory (item_name, sku, quantity, price)
                    VALUES (:name, :sku, :quantity, :price)
                """, {
                    "name": name,
                    "sku": sku,
                    "quantity": quantity,
                    "price": price
                })
                connection.commit()

                # Get the generated item_id using sku (which is UNIQUE)
                cursor.execute("""
                    SELECT item_id 
                    FROM Inventory 
                    WHERE sku = :sku
                """, {"sku": sku})
                row = cursor.fetchone()

        new_id = int(row[0]) if row else None

        return jsonify({
            "success": True,
            "item": {
                "id": new_id,
                "name": name,
                "sku": sku,
                "quantity": quantity,
                "price": price
            }
        }), 201

    except oracledb.DatabaseError as e:
        error, = e.args
        return jsonify({
            "success": False,
            "message": f"Database error: {error.message}"
        }), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/inventory/<int:item_id>', methods=['PUT'])
def update_inventory_item(item_id):
    """Edit an inventory item."""
    try:
        data = request.get_json()
        name = data.get("name")
        sku = data.get("sku")
        quantity = data.get("quantity")
        price = data.get("price")

        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE Inventory
                    SET 
                        item_name = :name,
                        sku = :sku,
                        quantity = :quantity,
                        price = :price,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE item_id = :item_id
                """, {
                    "name": name,
                    "sku": sku,
                    "quantity": int(quantity),
                    "price": float(price),
                    "item_id": item_id
                })
                if cursor.rowcount == 0:
                    return jsonify({
                        "success": False,
                        "message": "Item not found"
                    }), 404
                connection.commit()

        return jsonify({"success": True, "message": "Item updated successfully"})
    except oracledb.DatabaseError as e:
        error, = e.args
        return jsonify({
            "success": False,
            "message": f"Database error: {error.message}"
        }), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/inventory/<int:item_id>', methods=['DELETE'])
def delete_inventory_item(item_id):
    """Delete an inventory item."""
    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM Inventory
                    WHERE item_id = :item_id
                """, {"item_id": item_id})
                if cursor.rowcount == 0:
                    return jsonify({
                        "success": False,
                        "message": "Item not found"
                    }), 404
                connection.commit()

        return jsonify({"success": True, "message": "Item deleted successfully"})
    except oracledb.DatabaseError as e:
        error, = e.args
        return jsonify({
            "success": False,
            "message": f"Database error: {error.message}"
        }), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ----------------------------
# ORDERS APIs
# Uses Orders table from d.sql
# ----------------------------

@app.route('/api/orders', methods=['GET'])
def get_orders():
    """Return all orders."""
    try:
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT order_id, customer_name, order_date, total_amount, status
                    FROM Orders
                    ORDER BY order_date DESC
                """)
                rows = cursor.fetchall()

        orders = []
        for row in rows:
            orders.append({
                "order_id": int(row[0]),
                "customer_name": row[1],
                "order_date": row[2].isoformat() if row[2] is not None else None,
                "total_amount": float(row[3]) if row[3] is not None else 0.0,
                "status": row[4]
            })

        return jsonify({"success": True, "orders": orders})
    except oracledb.DatabaseError as e:
        error, = e.args
        return jsonify({
            "success": False,
            "message": f"Database error: {error.message}"
        }), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/orders/search', methods=['GET'])
def search_orders():
    """Basic search on orders (by customer, order_id, status)."""
    term = request.args.get("q", "").strip()
    if not term:
        # If no search term, just return all orders
        return get_orders()

    try:
        like_term = f"%{term.lower()}%"
        with get_db_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT order_id, customer_name, order_date, total_amount, status
                    FROM Orders
                    WHERE LOWER(customer_name) LIKE :term
                       OR LOWER(status) LIKE :term
                       OR TO_CHAR(order_id) LIKE :term
                       OR TO_CHAR(order_date, 'YYYY-MM-DD') LIKE :term
                    ORDER BY order_date DESC
                """, {"term": like_term})
                rows = cursor.fetchall()

        orders = []
        for row in rows:
            orders.append({
                "order_id": int(row[0]),
                "customer_name": row[1],
                "order_date": row[2].isoformat() if row[2] is not None else None,
                "total_amount": float(row[3]) if row[3] is not None else 0.0,
                "status": row[4]
            })

        return jsonify({"success": True, "orders": orders})
    except oracledb.DatabaseError as e:
        error, = e.args
        return jsonify({
            "success": False,
            "message": f"Database error: {error.message}"
        }), 500
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
