-- Schema + sample data for customer inventory/orders.
-- Loaded automatically by the Postgres Docker image on first start.

SET TIME ZONE 'UTC';

-- Session tracking (created at build time; app should not need to create/alter).
CREATE TABLE IF NOT EXISTS user_sessions (
  session_id UUID PRIMARY KEY,
  user_identifier TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  conversation_count INTEGER NOT NULL DEFAULT 0,
  -- kept for backward compatibility with earlier code paths
  session_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS customers (
  customer_id BIGSERIAL PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  full_name TEXT NOT NULL,
  phone TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS customer_addresses (
  address_id BIGSERIAL PRIMARY KEY,
  customer_id BIGINT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
  label TEXT NOT NULL,
  line1 TEXT NOT NULL,
  city TEXT NOT NULL,
  state TEXT NOT NULL,
  postal_code TEXT NOT NULL,
  country TEXT NOT NULL DEFAULT 'US',
  is_default BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS products (
  product_id BIGSERIAL PRIMARY KEY,
  sku TEXT UNIQUE NOT NULL,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  unit_price NUMERIC(10,2) NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS inventory (
  inventory_id BIGSERIAL PRIMARY KEY,
  product_id BIGINT NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
  location TEXT NOT NULL DEFAULT 'primary',
  on_hand INTEGER NOT NULL DEFAULT 0,
  reserved INTEGER NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
  order_id BIGSERIAL PRIMARY KEY,
  customer_id BIGINT NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'processing',
  total NUMERIC(12,2) NOT NULL DEFAULT 0,
  currency TEXT NOT NULL DEFAULT 'USD',
  placed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS order_items (
  order_item_id BIGSERIAL PRIMARY KEY,
  order_id BIGINT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
  product_id BIGINT NOT NULL REFERENCES products(product_id),
  quantity INTEGER NOT NULL,
  unit_price NUMERIC(10,2) NOT NULL,
  line_total NUMERIC(12,2) GENERATED ALWAYS AS (quantity * unit_price) STORED
);

-- Track per-session conversation length.
ALTER TABLE IF EXISTS user_sessions
  ADD COLUMN IF NOT EXISTS conversation_count INTEGER NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);

INSERT INTO customers (email, full_name, phone) VALUES
  ('alex.martin@example.com', 'Alex Martin', '+1-415-555-0101'),
  ('taylor.chen@example.com', 'Taylor Chen', '+1-206-555-0155'),
  ('jordan.ramirez@example.com', 'Jordan Ramirez', '+1-917-555-0199')
ON CONFLICT DO NOTHING;

INSERT INTO customer_addresses (customer_id, label, line1, city, state, postal_code, country, is_default) VALUES
  (1, 'Home', '742 Evergreen Terrace', 'Springfield', 'IL', '62701', 'US', TRUE),
  (2, 'HQ', '99 Pine St', 'Seattle', 'WA', '98101', 'US', TRUE),
  (3, 'Apartment', '501 Hudson Ave', 'Brooklyn', 'NY', '11201', 'US', TRUE)
ON CONFLICT DO NOTHING;

INSERT INTO products (sku, name, category, unit_price) VALUES
  ('SKU-CHAIR-001', 'ErgoFlex Chair', 'Furniture', 329.00),
  ('SKU-DESK-002', 'Lift Standing Desk', 'Furniture', 549.00),
  ('SKU-LAMP-003', 'Glow Desk Lamp', 'Lighting', 79.00),
  ('SKU-MAT-004', 'Balance Floor Mat', 'Accessories', 59.00)
ON CONFLICT DO NOTHING;

INSERT INTO inventory (product_id, location, on_hand, reserved) VALUES
  (1, 'primary', 45, 5),
  (2, 'primary', 30, 3),
  (3, 'primary', 80, 8),
  (4, 'primary', 120, 10)
ON CONFLICT DO NOTHING;

INSERT INTO orders (customer_id, status, total, currency, placed_at) VALUES
  (1, 'processing', 458.00, 'USD', NOW() - INTERVAL '1 day'),
  (2, 'shipped', 1007.00, 'USD', NOW() - INTERVAL '3 days'),
  (3, 'delivered', 408.00, 'USD', NOW() - INTERVAL '7 days')
ON CONFLICT DO NOTHING;

INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
  (1, 1, 1, 329.00),
  (1, 3, 2, 64.50), -- discounted lamp price
  (2, 2, 1, 549.00),
  (2, 1, 2, 229.00), -- promotional chair price
  (2, 4, 3, 59.00),
  (3, 4, 2, 59.00),
  (3, 3, 2, 145.00);

-- Create a restricted read-only role for application access.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'support_ro') THEN
    CREATE ROLE support_ro LOGIN PASSWORD 'support_ro';
  END IF;
END$$;

GRANT CONNECT ON DATABASE supportdb TO support_ro;
GRANT USAGE ON SCHEMA public TO support_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO support_ro;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO support_ro;
GRANT INSERT, UPDATE, DELETE ON TABLE user_sessions TO support_ro;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO support_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON SEQUENCES TO support_ro;

-- Ensure session_count column exists for existing deployments.
ALTER TABLE IF EXISTS user_sessions
  ADD COLUMN IF NOT EXISTS session_count INTEGER NOT NULL DEFAULT 0;

GRANT INSERT, update, DELETE ON TABLE orders TO support_ro;
GRANT USAGE, SELECT ON SEQUENCE orders_order_id_seq TO support_ro;
GRANT INSERT, update, DELETE ON TABLE order_items TO support_ro;
GRANT USAGE, SELECT ON SEQUENCE order_items_order_item_id_seq TO support_ro;

