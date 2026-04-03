-- ============================================================
--  Sample E-Commerce Database for SQL Agent Testing
--  Run this in MySQL:
--    mysql -u root -p < sample_db.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS shop_db;
USE shop_db;

-- ── Tables ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS categories (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customers (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    first_name  VARCHAR(100) NOT NULL,
    last_name   VARCHAR(100) NOT NULL,
    email       VARCHAR(255) NOT NULL UNIQUE,
    city        VARCHAR(100),
    country     VARCHAR(100) DEFAULT 'India',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    name          VARCHAR(200) NOT NULL,
    category_id   INT NOT NULL,
    price         DECIMAL(10,2) NOT NULL,
    stock         INT NOT NULL DEFAULT 0,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS orders (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    customer_id   INT NOT NULL,
    status        ENUM('pending','processing','shipped','delivered','cancelled') DEFAULT 'pending',
    total_amount  DECIMAL(10,2) NOT NULL DEFAULT 0,
    ordered_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    order_id    INT NOT NULL,
    product_id  INT NOT NULL,
    quantity    INT NOT NULL,
    unit_price  DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id)   REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS reviews (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    product_id  INT NOT NULL,
    customer_id INT NOT NULL,
    rating      TINYINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment     TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id)  REFERENCES products(id),
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);

-- ── Seed Data ─────────────────────────────────────────────

INSERT INTO categories (name) VALUES
    ('Electronics'),
    ('Clothing'),
    ('Books'),
    ('Home & Kitchen'),
    ('Sports');

INSERT INTO customers (first_name, last_name, email, city) VALUES
    ('Aanya',   'Sharma',   'aanya.sharma@email.com',   'Mumbai'),
    ('Rohan',   'Verma',    'rohan.verma@email.com',    'Delhi'),
    ('Priya',   'Nair',     'priya.nair@email.com',     'Bangalore'),
    ('Vikram',  'Singh',    'vikram.singh@email.com',   'Chennai'),
    ('Meera',   'Patel',    'meera.patel@email.com',    'Ahmedabad'),
    ('Arjun',   'Menon',    'arjun.menon@email.com',    'Hyderabad'),
    ('Sneha',   'Joshi',    'sneha.joshi@email.com',    'Pune'),
    ('Karan',   'Gupta',    'karan.gupta@email.com',    'Kolkata'),
    ('Divya',   'Reddy',    'divya.reddy@email.com',    'Jaipur'),
    ('Nikhil',  'Iyer',     'nikhil.iyer@email.com',    'Surat');

INSERT INTO products (name, category_id, price, stock) VALUES
    ('Wireless Headphones',     1, 2499.00,  45),
    ('Smartphone Stand',        1,  599.00,  80),
    ('Bluetooth Speaker',       1, 1899.00,  30),
    ('USB-C Hub',               1, 1299.00,   8),
    ('Men\'s Running Shoes',    2, 3499.00,  60),
    ('Cotton Kurta',            2,  899.00, 120),
    ('Denim Jacket',            2, 2199.00,  25),
    ('Python Programming',      3,  799.00,  55),
    ('Data Structures & Algo',  3,  699.00,  40),
    ('The Lean Startup',        3,  499.00,  70),
    ('Non-stick Cookware Set',  4, 3299.00,  15),
    ('Air Fryer',               4, 5499.00,   6),
    ('Yoga Mat',                5,  899.00,  90),
    ('Cricket Bat',             5, 1799.00,  20),
    ('Resistance Bands Set',    5,  649.00,  75);

INSERT INTO orders (customer_id, status, total_amount, ordered_at) VALUES
    (1,  'delivered',  4997.00, '2024-11-01 10:00:00'),
    (2,  'delivered',  2499.00, '2024-11-05 14:30:00'),
    (3,  'shipped',    7697.00, '2024-11-10 09:15:00'),
    (4,  'delivered',  1498.00, '2024-11-12 16:45:00'),
    (5,  'processing', 5499.00, '2024-11-18 11:20:00'),
    (1,  'delivered',  3299.00, '2024-11-20 13:00:00'),
    (6,  'delivered',  1298.00, '2024-11-22 10:30:00'),
    (7,  'pending',    2698.00, '2024-11-25 08:45:00'),
    (8,  'cancelled',  4998.00, '2024-11-26 17:00:00'),
    (2,  'delivered',  1799.00, '2024-11-28 12:15:00'),
    (3,  'delivered',  2498.00, '2024-12-01 09:00:00'),
    (9,  'shipped',    6798.00, '2024-12-03 15:30:00'),
    (10, 'delivered',  3498.00, '2024-12-05 11:45:00'),
    (4,  'processing', 1898.00, '2024-12-08 14:00:00'),
    (5,  'delivered',  5698.00, '2024-12-10 10:20:00');

INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
    (1,  1,  1, 2499.00),
    (1,  5,  1, 2498.00),  -- intentional rounding for realism
    (2,  1,  1, 2499.00),
    (3,  12, 1, 5499.00),
    (3,  13, 2,  899.00),
    (4,  8,  1,  799.00),
    (4,  9,  1,  699.00),
    (5,  12, 1, 5499.00),
    (6,  11, 1, 3299.00),
    (7,  3,  1, 1899.00),  -- but order total shows 1298 to test discrepancies
    (7,  15, 1,  649.00),
    (8,  5,  1, 3499.00),
    (8,  7,  1, 2199.00),
    (9,  2,  1,  599.00),  -- cancelled order
    (10, 14, 1, 1799.00),
    (11, 6,  1,  899.00),
    (11, 13, 1,  899.00),
    (11, 15, 1,  649.00),
    (12, 12, 1, 5499.00),
    (12, 2,  1,  599.00),
    (13, 5,  1, 3499.00),
    (14, 3,  1, 1899.00),
    (15, 12, 1, 5499.00),
    (15, 4,  1,  199.00);

INSERT INTO reviews (product_id, customer_id, rating, comment) VALUES
    (1,  1, 5, 'Excellent sound quality, very comfortable.'),
    (1,  2, 4, 'Good headphones but a bit tight.'),
    (1,  6, 5, 'Best purchase this year!'),
    (5,  1, 4, 'Comfortable for long runs.'),
    (5,  4, 3, 'Sizing runs small, order a size up.'),
    (12, 3, 5, 'Makes cooking so much easier.'),
    (12, 5, 4, 'Great air fryer, heats up fast.'),
    (8,  4, 5, 'Clear explanations, great for beginners.'),
    (9,  4, 4, 'Solid book, good practice problems.'),
    (13, 3, 5, 'Perfect thickness, non-slip surface.'),
    (11, 6, 4, 'Good quality cookware, even heating.'),
    (3,  7, 3, 'Average sound, expected more bass.'),
    (14, 10,4, 'Nice bat, good balance.'),
    (6,  8, 5, 'Very comfortable, great fabric.'),
    (2,  9, 4, 'Sturdy stand, holds phone well.');

-- ── Verify ────────────────────────────────────────────────
SELECT 'Setup complete!' AS status;
SELECT TABLE_NAME, TABLE_ROWS
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'shop_db'
ORDER BY TABLE_NAME;