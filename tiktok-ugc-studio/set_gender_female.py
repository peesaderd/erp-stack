"""Set gender=female for all products with empty gender (no unisex)."""
import sqlite3, logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("set_gender_female")

TUS_DB = "/home/openhands/erp-stack/tiktok-ugc-studio/tus_products.db"

def main():
    conn = sqlite3.connect(TUS_DB)
    rows = conn.execute("SELECT product_id, title FROM tus_products WHERE gender=\x27\x27 OR gender IS NULL").fetchall()
    logger.info("Found %d products with empty gender", len(rows))
    for product_id, title in rows:
        conn.execute("UPDATE tus_products SET gender=\x27female\x27 WHERE product_id=?", (product_id,))
        logger.info("%s -> female (%s)", product_id, title[:40])
    conn.commit()
    conn.close()
    logger.info("DONE: updated %d products to female", len(rows))

if __name__ == "__main__":
    main()
