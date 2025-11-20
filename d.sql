

CREATE TABLE Inventory (
    item_id NUMBER PRIMARY KEY,
    item_name VARCHAR2(100) NOT NULL,
    sku VARCHAR2(20) UNIQUE NOT NULL,
    quantity NUMBER DEFAULT 0 CHECK (quantity >= 0),
    price NUMBER(10,2) CHECK (price >= 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    low_stock_threshold NUMBER DEFAULT 10
);

--create table for the orders
CREATE TABLE Orders (
    order_id NUMBER PRIMARY KEY,
    customer_name VARCHAR2(100) NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_amount NUMBER(10,2) CHECK (total_amount >= 0),
    status VARCHAR2(20) DEFAULT 'Pending'
);
-- create a trigger to check the quantity of the item in the inventory
CREATE OR REPLACE TRIGGER check_inventory_quantity
BEFORE INSERT ON Orders
FOR EACH ROW
BEGIN
    IF :NEW.quantity > (SELECT quantity FROM Inventory WHERE item_id = :NEW.item_id) THEN
        RAISE_APPLICATION_ERROR(-20001, 'Insufficient quantity in inventory');
    END IF;
END;
/

--create a function ot search button for the inventory in oracle sql
CREATE OR REPLACE FUNCTION search_inventory(
    p_search_term IN VARCHAR2
) RETURN SYS_REFCURSOR
IS
    v_result SYS_REFCURSOR;
BEGIN
    OPEN v_result FOR
        SELECT 
            item_name,
            sku,
            quantity,
            price,
            created_at,
            updated_at,
            low_stock_threshold
        FROM Inventory
        WHERE LOWER(item_name) LIKE '%' || LOWER(p_search_term) || '%'
        OR LOWER(sku) LIKE '%' || LOWER(p_search_term) || '%';
    
    RETURN v_result;
EXCEPTION
    WHEN OTHERS THEN
        RAISE_APPLICATION_ERROR(-20002, 'Error searching inventory: ' || SQLERRM);
END search_inventory;
/

--create a function to the add item button  in the oracke sql
CREATE OR REPLACE PROCEDURE add_item(
    p_item_name IN VARCHAR2,
    p_sku IN VARCHAR2,
    p_quantity IN NUMBER,
    p_price IN NUMBER
)
AS
BEGIN
    INSERT INTO Inventory (item_name, sku, quantity, price)
    VALUES (p_item_name, p_sku, p_quantity, p_price);
END add_item;
/

--create a function to edit button in oracle sql in the inventory table that can change any item or all items 
CREATE OR REPLACE PROCEDURE edit_item(
    p_item_id IN NUMBER,
    p_item_name IN VARCHAR2 DEFAULT NULL,
    p_sku IN VARCHAR2 DEFAULT NULL, 
    p_quantity IN NUMBER DEFAULT NULL,
    p_price IN NUMBER DEFAULT NULL,
    p_low_stock_threshold IN NUMBER DEFAULT NULL
)
AS
BEGIN
    UPDATE Inventory
    SET
        item_name = COALESCE(p_item_name, item_name),
        sku = COALESCE(p_sku, sku),
        quantity = COALESCE(p_quantity, quantity),
        price = COALESCE(p_price, price),
        low_stock_threshold = COALESCE(p_low_stock_threshold, low_stock_threshold),
        updated_at = CURRENT_TIMESTAMP
    WHERE item_id = p_item_id;

    IF SQL%ROWCOUNT = 0 THEN
        RAISE_APPLICATION_ERROR(-20003, 'Item not found with ID: ' || p_item_id);
    END IF;

    COMMIT;
EXCEPTION
    WHEN OTHERS THEN
        ROLLBACK;
        RAISE_APPLICATION_ERROR(-20004, 'Error updating item: ' || SQLERRM);
END edit_item;
/

--CREATE  A PROCEDURE TO DELETE BUTTON IN ORACLE SQL INVENTORY TABLE
CREATE OR REPLACE PROCEDURE delete_item(
    p_item_id IN NUMBER
)
AS
BEGIN
    DELETE FROM Inventory WHERE item_id = p_item_id;
END delete_item;
/

--create a function to search in the orders table using oracle sql  
CREATE OR REPLACE FUNCTION search_orders(
    p_search_term IN VARCHAR2
) RETURN SYS_REFCURSOR
AS
    v_result SYS_REFCURSOR;
BEGIN
    OPEN v_result FOR
        SELECT o.*, c.customer_name
        FROM Orders o
        LEFT JOIN Customers c ON o.customer_id = c.customer_id 
        WHERE LOWER(c.customer_name) LIKE '%' || LOWER(p_search_term) || '%'
        OR o.order_id LIKE '%' || p_search_term || '%'
        OR o.order_status LIKE '%' || LOWER(p_search_term) || '%'
        OR TO_CHAR(o.order_date, 'YYYY-MM-DD') LIKE '%' || p_search_term || '%'
        ORDER BY o.order_date DESC;
    
    RETURN v_result;
EXCEPTION
    WHEN OTHERS THEN
        RAISE_APPLICATION_ERROR(-20005, 'Error searching orders: ' || SQLERRM);
END search_orders;
/
--create a function to get monthly sales growth automatically
CREATE OR REPLACE FUNCTION get_monthly_sales_growth
RETURN SYS_REFCURSOR
AS
    v_result SYS_REFCURSOR;
BEGIN
    OPEN v_result FOR
        WITH monthly_sales AS (
            SELECT 
                TRUNC(order_date, 'MM') AS sales_month,
                SUM(total_amount) AS sales_amount
            FROM Orders 
            GROUP BY TRUNC(order_date, 'MM')
        ),
        sales_growth AS (
            SELECT 
                sales_month,
                sales_amount,
                LAG(sales_amount) OVER (ORDER BY sales_month) AS prev_month_sales,
                CASE 
                    WHEN LAG(sales_amount) OVER (ORDER BY sales_month) > 0 THEN
                        ROUND(((sales_amount - LAG(sales_amount) OVER (ORDER BY sales_month)) / 
                        LAG(sales_amount) OVER (ORDER BY sales_month)) * 100, 2)
                    ELSE NULL
                END AS growth_percentage
            FROM monthly_sales
        )
        SELECT 
            TO_CHAR(sales_month, 'Month YYYY') AS month,
            sales_amount,
            growth_percentage || '%' AS growth
        FROM sales_growth
        ORDER BY sales_month DESC;

    RETURN v_result;
EXCEPTION
    WHEN OTHERS THEN
        RAISE_APPLICATION_ERROR(-20006, 'Error calculating monthly sales growth: ' || SQLERRM);
END get_monthly_sales_growth;
/
