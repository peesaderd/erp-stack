import csv
import json
import os
import paramiko
import sys

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    
    csv_file = "trending_affiliate_products.csv"
    sql_file = "import_products.sql"
    
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found!")
        return
        
    print(f"Reading products from {csv_file}...")
    sql_statements = []
    
    # We can also add a TRUNCATE products; or delete existing test rows if needed
    sql_statements.append("TRUNCATE products RESTART IDENTITY;\n")
    
    with open(csv_file, mode='r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row.get("Product Name")
            data = {
                "product_id": row.get("Product ID"),
                "category": row.get("Category"),
                "price": row.get("Price (THB)"),
                "commission_rate": row.get("Commission Rate"),
                "product_url": row.get("Product URL"),
                "google_sheets_link": row.get("Google Sheets Link"),
                "hook_concept": row.get("AI Video Hook / Concept"),
                "image_filename": row.get("Image Filename", "")
            }
            
            safe_name = name.replace("'", "''")
            safe_data_json = json.dumps(data, ensure_ascii=False).replace("'", "''")
            
            sql = f"INSERT INTO products (name, data) VALUES ('{safe_name}', '{safe_data_json}');"
            sql_statements.append(sql + "\n")
            
    with open(sql_file, "w", encoding="utf-8") as f_out:
        f_out.writelines(sql_statements)
        
    print(f"Generated {len(sql_statements) - 1} INSERT statements in {sql_file}")
    
    # Connect and upload via SSH/SFTP
    ssh_ip = "89.167.82.205"
    ssh_user = "openhands"
    ssh_pass = "OpenHands@ERP2026"
    remote_path = f"/home/openhands/calm-noether/{sql_file}"
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ssh_ip, username=ssh_user, password=ssh_pass, timeout=15)
        
        sftp = ssh.open_sftp()
        print(f"Uploading {sql_file} -> {remote_path}...")
        sftp.put(sql_file, remote_path)
        sftp.close()
        
        # Execute SQL inside the docker container
        print("Executing SQL script inside postgres db container...")
        cmd = f"sudo docker exec -i db psql -U openhands -d productdb < {remote_path}"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        print("Stdout:")
        print(stdout.read().decode('utf-8'))
        print("Stderr:")
        print(stderr.read().decode('utf-8'))
        
        # Verify the new count
        stdin, stdout, stderr = ssh.exec_command("sudo docker exec db psql -U openhands -d productdb -c \"SELECT count(*) FROM products;\"")
        print("New database count:")
        print(stdout.read().decode('utf-8'))
        
        ssh.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
