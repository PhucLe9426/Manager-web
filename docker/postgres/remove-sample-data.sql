BEGIN;

DELETE FROM websites
WHERE domain IN (
  'betongthuduc1.vn',
  'anphatinterior.vn',
  'minhphuclogistics.com',
  'nhakhoahikari.vn'
);

DELETE FROM customers
WHERE name IN (
  'Bê Tông Thủ Đức 1',
  'Nội thất An Phát',
  'Minh Phúc Logistics',
  'Nha khoa Hikari'
)
AND NOT EXISTS (SELECT 1 FROM websites WHERE websites.customer_id = customers.id);

DELETE FROM users WHERE email = 'admin@siteops.local';

COMMIT;
