# Customer Support & Inventory Queries
*Test set for PostgreSQL Schema: Customers, Products, Inventory, Orders*

## --- CATEGORY 1: SIMPLE LOOKUPS (Single Table) ---
# Goal: Test basic `SELECT ... WHERE` logic without joins.

1. What is the email address for the customer Jordan Ramirez?
2. Is the product with SKU 'SKU-MAT-004' currently active?
3. What is the unit price of the "Lift Standing Desk"?
4. How many "ErgoFlex Chair" units are currently reserved in inventory?
5. List all my orders that have the status 'shipped'.
6. Which customer has the phone number '+1-206-555-0155'?
7. What is the default currency used for our orders?
8. Show me all addresses labeled "Home".
9. Are there any products in the 'Lighting' category?
10. What is the current on-hand quantity for the product at the 'primary' location with inventory_id 3?

## --- CATEGORY 2: COMPLEX QUERIES (Joins Required) ---
# Goal: Test the ability to link `customers`, `orders`, `order_items`, and `products`.

11. What items were included in the order placed by Alex Martin on the last day?
12. List all products purchased by Taylor Chen, including the quantity and unit price paid.
13. Show me the shipping address (line1, city, state) for order #2.
14. Which customers have bought the "Glow Desk Lamp"?
15. What is the total revenue generated from the "Furniture" category?
16. Find the email addresses of customers who have an order in 'processing' status.
17. List the SKUs and names of products that are currently out of stock (on_hand = 0).
18. Compare the `unit_price` in the `products` table vs. the `unit_price` paid in `order_items` for Order #2.
19. Which city has the most delivered orders?
20. Display the full name of the customer and the total amount of their most recent order.

## --- CATEGORY 3: AGGREGATIONS & ANALYTICS ---
# Goal: Test `GROUP BY`, `SUM`, `COUNT`, and logic across multiple rows.

21. What is the total lifetime value (total spent) of customer Jordan Ramirez?
22. Which product has the highest total quantity sold across all orders?
23. Calculate the average order value (AOV) for all completed orders.
24. How many distinct customers have ordered items from the 'Accessories' category?
25. What is the total reserved inventory count for all products in the 'Furniture' category?

## --- CATEGORY 4: TRAP QUERIES (Hallucination Checks) ---
# Goal: Ask about columns or tables that do not exist to ensure the bot doesn't hallucinate.

26. Check the supplier name for the "Lift Standing Desk". 
(Trap: No `suppliers` table)
27. How many loyalty points does Taylor Chen have? 
(Trap: No `loyalty_points` column)
28. What is the return status of Order #1? 
(Trap: `status` exists, but 'return' logic is not defined in schema)
29. Show me the expiration date for the "Balance Floor Mat". 
(Trap: No `expiration_date` column)
30. Which warehouse location is 'SKU-LAMP-003' stored in? 
(Trap: `location` defaults to 'primary', checking if bot invents other locations)