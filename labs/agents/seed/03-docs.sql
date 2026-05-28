-- Tiny docs table for the RAG sidebar (block 07).
-- Each row is a short snippet of "company knowledge" the agent may need to
-- ground answers in. The embedding column is filled in by the lesson code
-- using the OpenAI embeddings API; we ship the schema + raw text only.

CREATE TABLE IF NOT EXISTS docs (
    id          SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    embedding   vector(1536)
);

INSERT INTO docs (title, body) VALUES
    ('Late fee policy',
     'Customers are charged a $1.00 late fee for every day a rental is returned past the due date. The fee is capped at the replacement cost of the film.'),
    ('Membership tiers',
     'Pagila Video has three membership tiers: Basic ($0/mo, 2 rentals at a time), Plus ($9.99/mo, 5 rentals, no late fees under 3 days), and Family ($14.99/mo, 10 rentals, shared across up to 5 accounts).'),
    ('Refund policy',
     'Refunds are issued only for defective discs, billing errors, or store-confirmed equipment failures. Refund requests must be filed within 30 days of the transaction.'),
    ('Damaged disc procedure',
     'If a returned disc is visibly cracked or unplayable, the customer is charged the replacement cost on file in inventory. Customers may contest the charge in writing within 14 days.'),
    ('Hours of operation',
     'All Pagila locations are open Monday through Saturday from 10 AM to 10 PM. Sunday hours are 12 PM to 8 PM. Closed on Thanksgiving and Christmas Day.'),
    ('Pre-order policy',
     'New releases may be pre-ordered up to 30 days before their street date. Pre-orders are filled in the order received and are held for 48 hours after the release.');
