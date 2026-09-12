-- 0017 portfolio screenshot derivatives.
--
-- A portfolio screenshot is uploaded once and displayed at three very
-- different sizes: a card thumbnail on a 375px phone, a gallery image, and
-- the full-size view. Serving the 1920px original to a phone is how a
-- portfolio page ends up costing eight megabytes on mobile data, so every
-- upload is re-encoded into the sizes the product actually renders.
--
-- The map is {format: {width: storage_key}}, the same shape developer_photos
-- uses, and it holds storage KEYS rather than URLs: a key is what a delete
-- needs, and moving to a CDN hostname must not orphan every screenshot.
ALTER TABLE portfolio_images
  ADD COLUMN derivatives jsonb NOT NULL DEFAULT '{}'::jsonb;
