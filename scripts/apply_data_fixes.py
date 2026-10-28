import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), "..", "data", "vulpix_vault.db")
conn = sqlite3.connect(db_path)
c = conn.cursor()

# 1. Delete duplicate Brock's Vulpix 327
c.execute("DELETE FROM master_set_catalog WHERE id = 327")

# 2. Update 326 (W-Stamp)
c.execute("""
    UPDATE master_set_catalog 
    SET edition = 'W-Stamp Promo',
        finish = 'W-Stamp',
        is_error = 0,
        notes = 'Distributed with TopDeck Magazine (Issue #9) featuring a gold foil Wizards W-stamp.'
    WHERE id = 326
""")

# 3. Update 325 (1st Edition)
c.execute("""
    UPDATE master_set_catalog 
    SET edition = '1st Edition',
        finish = '1st Edition',
        notes = 'Gym Challenge 1st Edition printing (October 2000).'
    WHERE id = 325
""")

# 4. Update 707 (Unlimited)
c.execute("""
    UPDATE master_set_catalog 
    SET edition = 'Unlimited',
        finish = 'Standard',
        notes = 'Gym Challenge Unlimited printing (Late 2000).'
    WHERE id = 707
""")

# 5. Fix corrupted Gym Heroes & Challenge editions
c.execute("UPDATE master_set_catalog SET edition = 'Unlimited', finish = 'Standard', notes = 'Gym Heroes Unlimited printing.' WHERE id = 317")
c.execute("UPDATE master_set_catalog SET edition = 'Unlimited', finish = 'Standard', notes = 'Gym Heroes Unlimited printing.' WHERE id = 322")
c.execute("UPDATE master_set_catalog SET edition = 'Unlimited', finish = 'Standard', notes = 'Gym Challenge Unlimited printing.' WHERE id = 329")

# 6. Fix Worlds deck 461
c.execute("UPDATE master_set_catalog SET edition = 'World Championships 2017', finish = 'World Championships Deck', notes = '2017 World Championships Diego Cassiraga Deck.' WHERE id = 461")

# 7. Fix Rainbow 504
c.execute("UPDATE master_set_catalog SET edition = 'Rainbow Rare', finish = 'Rainbow Holo', is_error = 0, notes = 'Silver Tempest Secret Rare Rainbow Holo #197/195.' WHERE id = 504")

# 8. Fix Darkness, and to Light 334
c.execute("""
    UPDATE master_set_catalog 
    SET card_name = 'Light Vulpix',
        card_number = 'No. 037',
        release_year = 2001,
        artist = 'Masako Yamashita',
        est_raw_price = 8.0,
        est_grade10_price = 95.0,
        pricecharting_raw = 8.0,
        pricecharting_grade10 = 95.0,
        image_url = 'dashboard/static/cards/vulpix-darkness-and-to-light-no-014.jpg',
        notes = 'Japanese Neo 4 Darkness, and to Light... (2001) illustrated by Masako Yamashita.'
    WHERE id = 334
""")

# 9. Ensure poncho cards have is_cameo = 0
c.execute("UPDATE master_set_catalog SET is_cameo = 0 WHERE card_name LIKE '%Poncho%'")

# 10. Clean up any remaining "Variant: ..." text in notes
c.execute("SELECT id, notes FROM master_set_catalog WHERE notes LIKE 'Variant:%'")
for cid, n in c.fetchall():
    cleaned = n.replace("Variant:", "").strip()
    c.execute("UPDATE master_set_catalog SET notes = ? WHERE id = ?", (cleaned, cid))

conn.commit()
print("All master set database fixes successfully applied!")
conn.close()
